import uuid
from dataclasses import dataclass, field

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.errors import AppError, forbidden
from app.core.security import decode_access_token
from app.models import (Customer, CustomerContact, OrganizationMember, Permission, Role, RolePermission, User)

bearer = HTTPBearer(auto_error=False)


@dataclass
class Ctx:
    user: User
    org_id: uuid.UUID
    role: str
    perms: set[str] = field(default_factory=set)
    ip: str | None = None
    user_agent: str | None = None
    _customer_id: uuid.UUID | None = None
    _customer_loaded: bool = False

    @property
    def is_client(self) -> bool:
        return self.role == "client"

    @property
    def is_owner(self) -> bool:
        return self.role == "owner"

    @property
    def sees_all(self) -> bool:
        return self.role == "owner"

    def can(self, perm: str) -> bool:
        return perm in self.perms


def get_ctx(request: Request, creds: HTTPAuthorizationCredentials | None = Depends(bearer),
            db: Session = Depends(get_db)) -> Ctx:
    """Authenticate, resolve org membership *server-side*, role and permissions."""
    if not creds:
        raise AppError(401, "UNAUTHENTICATED", "Authentication required")
    try:
        data = decode_access_token(creds.credentials)
        user_id, org_id = uuid.UUID(data["sub"]), uuid.UUID(data["org"])
    except (jwt.PyJWTError, ValueError, KeyError):
        raise AppError(401, "INVALID_TOKEN", "Invalid or expired token")
    row = db.execute(
        select(User, Role.name, Role.id)
        .join(OrganizationMember, OrganizationMember.user_id == User.id)
        .join(Role, Role.id == OrganizationMember.role_id)
        .where(User.id == user_id, OrganizationMember.organization_id == org_id,
               OrganizationMember.status == "active", User.is_active.is_(True))
    ).first()
    if not row:
        raise AppError(401, "INVALID_TOKEN", "Session is no longer valid")
    user, role_name, role_id = row
    perms = set(db.scalars(select(Permission.code).join(RolePermission, RolePermission.permission_id == Permission.id)
                           .where(RolePermission.role_id == role_id)))
    return Ctx(user=user, org_id=org_id, role=role_name, perms=perms,
               ip=request.client.host if request.client else None, user_agent=request.headers.get("user-agent"))


def require(*perms: str):
    def dep(ctx: Ctx = Depends(get_ctx)) -> Ctx:
        missing = [p for p in perms if p not in ctx.perms]
        if missing:
            raise forbidden(f"Missing permission: {', '.join(missing)}")
        return ctx
    return dep


def client_customer_id(db: Session, ctx: Ctx) -> uuid.UUID:
    """Customer account a client-portal user belongs to (via customer_contacts.user_id)."""
    if not ctx._customer_loaded:
        ctx._customer_id = db.scalar(
            select(CustomerContact.customer_id).join(Customer, Customer.id == CustomerContact.customer_id)
            .where(CustomerContact.user_id == ctx.user.id, CustomerContact.organization_id == ctx.org_id,
                   Customer.deleted_at.is_(None)))
        ctx._customer_loaded = True
    if ctx._customer_id is None:
        raise forbidden("Your login is not linked to a customer account")
    return ctx._customer_id
