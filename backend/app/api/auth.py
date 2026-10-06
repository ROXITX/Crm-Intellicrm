import re
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.config import settings
from app.core.db import get_db
from app.core.deps import Ctx, get_ctx
from app.core.errors import AppError, conflict
from app.core.ratelimit import hit
from app.core.permissions import ROLE_PERMISSIONS
from app.core.security import (create_access_token, hash_password, hash_token, new_refresh_token, verify_password)
from app.models import AuditLog, Organization, OrganizationMember, RefreshToken, Role, User

router = APIRouter(prefix="/auth", tags=["auth"])
REFRESH_COOKIE = "refresh_token"


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)
    organization_slug: str | None = None


class RegisterIn(BaseModel):
    organization_name: str = Field(min_length=2, max_length=200)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str | None = Field(None, max_length=100)
    email: EmailStr
    password: str = Field(min_length=10, max_length=200)


class RefreshIn(BaseModel):
    refresh_token: str | None = None


def _issue(db: Session, user: User, org: Organization, response: Response) -> dict:
    raw, hashed = new_refresh_token()
    db.add(RefreshToken(user_id=user.id, organization_id=org.id, token_hash=hashed,
                        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_ttl_days)))
    response.set_cookie(REFRESH_COOKIE, raw, httponly=True, samesite="lax", max_age=settings.refresh_ttl_days * 86400,
                        path="/api/v1/auth")
    return {"access_token": create_access_token(user.id, org.id), "refresh_token": raw, "token_type": "bearer",
            "expires_in": settings.access_ttl_minutes * 60}


def _me(db: Session, ctx: Ctx) -> dict:
    org = db.get(Organization, ctx.org_id)
    return {"id": str(ctx.user.id), "email": ctx.user.email, "first_name": ctx.user.first_name,
            "last_name": ctx.user.last_name, "role": ctx.role, "permissions": sorted(ctx.perms),
            "organization": {"id": str(org.id), "name": org.name, "slug": org.slug}}


@router.post("/register", status_code=201)
def register(body: RegisterIn, response: Response, db: Session = Depends(get_db)):
    """Create a new organization with its first user as Owner."""
    email = body.email.lower()
    if db.scalar(select(User.id).where(User.email == email)):
        raise conflict("An account with this email already exists", "EMAIL_TAKEN")
    slug = re.sub(r"[^a-z0-9]+", "-", body.organization_name.lower()).strip("-")[:80] or "org"
    base, i = slug, 1
    while db.scalar(select(Organization.id).where(Organization.slug == slug)):
        i += 1
        slug = f"{base}-{i}"
    org = Organization(name=body.organization_name, slug=slug, email=email, status="active")
    user = User(email=email, password_hash=hash_password(body.password), first_name=body.first_name,
                last_name=body.last_name)
    db.add_all([org, user])
    db.flush()
    owner_role = db.scalar(select(Role).where(Role.name == "owner", Role.is_system_role.is_(True)))
    db.add(OrganizationMember(organization_id=org.id, user_id=user.id, role_id=owner_role.id))
    db.add(AuditLog(organization_id=org.id, actor_id=user.id, action="org.register", entity_type="organization",
                    entity_id=org.id))
    return _issue(db, user, org, response)


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    hit(f"login:{request.client.host if request.client else '-'}:{body.email.lower()}", 10, 300)
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    # Constant-ish behavior: same error for unknown user / bad password / inactive.
    if not user or not user.is_active or not verify_password(body.password, user.password_hash):
        raise AppError(401, "INVALID_CREDENTIALS", "Incorrect email or password")
    q = (select(Organization).join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
         .where(OrganizationMember.user_id == user.id, OrganizationMember.status == "active",
                Organization.status == "active"))
    if body.organization_slug:
        q = q.where(Organization.slug == body.organization_slug)
    org = db.scalars(q.order_by(OrganizationMember.joined_at)).first()
    if not org:
        raise AppError(401, "INVALID_CREDENTIALS", "Incorrect email or password")
    user.last_login_at = datetime.now(timezone.utc)
    db.add(AuditLog(organization_id=org.id, actor_id=user.id, action="auth.login",
                    meta={"ip": request.client.host if request.client else None,
                          "user_agent": request.headers.get("user-agent")}))
    return _issue(db, user, org, response)


@router.post("/refresh")
def refresh(request: Request, response: Response, body: RefreshIn | None = None, db: Session = Depends(get_db)):
    raw = (body.refresh_token if body else None) or request.cookies.get(REFRESH_COOKIE)
    if not raw:
        raise AppError(401, "INVALID_TOKEN", "Missing refresh token")
    rec = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw)))
    now = datetime.now(timezone.utc)
    if not rec or rec.revoked_at or rec.expires_at < now:
        raise AppError(401, "INVALID_TOKEN", "Invalid or expired refresh token")
    user, org = db.get(User, rec.user_id), db.get(Organization, rec.organization_id)
    member = db.scalar(select(OrganizationMember.id).where(
        OrganizationMember.user_id == rec.user_id, OrganizationMember.organization_id == rec.organization_id,
        OrganizationMember.status == "active"))
    if not user.is_active or not member:
        raise AppError(401, "INVALID_TOKEN", "Session is no longer valid")
    rec.revoked_at = now  # rotation
    return _issue(db, user, org, response)


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, body: RefreshIn | None = None, db: Session = Depends(get_db)):
    raw = (body.refresh_token if body else None) or request.cookies.get(REFRESH_COOKIE)
    if raw:
        rec = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw)))
        if rec and not rec.revoked_at:
            rec.revoked_at = datetime.now(timezone.utc)
            db.add(AuditLog(organization_id=rec.organization_id, actor_id=rec.user_id, action="auth.logout"))
    response.delete_cookie(REFRESH_COOKIE, path="/api/v1/auth")


@router.get("/me")
def me(ctx: Ctx = Depends(get_ctx), db: Session = Depends(get_db)):
    return _me(db, ctx)
