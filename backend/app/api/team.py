import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.db import get_db
from app.core.deps import Ctx, get_ctx, require
from app.core.errors import bad_request, conflict, forbidden
from app.core.security import hash_password
from app.core.util import get_or_404
from app.services.workload import team_workload
from app.models import OrganizationMember, Role, Task, User

router = APIRouter(prefix="/team", tags=["team"])

class InviteIn(BaseModel):
    email: EmailStr
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str | None = None
    role: Literal["owner", "manager", "staff"]
    password: str = Field(min_length=10, max_length=200)
    weekly_capacity_hours: Decimal = Field(40, gt=0, le=168)


class RoleIn(BaseModel):
    role: Literal["owner", "manager", "staff"] | None = None
    status: Literal["active", "suspended"] | None = None


@router.get("")
def list_team(ctx: Ctx = Depends(require("team.read")), db: Session = Depends(get_db)):
    return team_workload(db, ctx.org_id)


@router.get("/directory")
def directory(ctx: Ctx = Depends(get_ctx), db: Session = Depends(get_db)):
    """Minimal list (id + name) of internal members for assignment pickers."""
    if ctx.is_client:
        raise forbidden()
    rows = db.execute(select(User.id, User.first_name, User.last_name, Role.name).join(
        OrganizationMember, OrganizationMember.user_id == User.id).join(Role, Role.id == OrganizationMember.role_id).where(
        OrganizationMember.organization_id == ctx.org_id, OrganizationMember.status == "active", Role.name != "client"
    ).order_by(User.first_name)).all()
    return [{"id": str(i), "name": f"{f} {l or ''}".strip(), "role": r} for i, f, l, r in rows]


@router.post("/members", status_code=201)
def invite(body: InviteIn, ctx: Ctx = Depends(require("team.manage")), db: Session = Depends(get_db)):
    if body.role == "owner" and not ctx.is_owner:
        raise forbidden("Only an owner can create another owner")
    email = body.email.lower()
    if db.scalar(select(User.id).where(User.email == email)):
        raise conflict("An account with this email already exists", "EMAIL_TAKEN")
    role = db.scalar(select(Role).where(Role.name == body.role, Role.is_system_role.is_(True)))
    u = User(email=email, password_hash=hash_password(body.password), first_name=body.first_name,
             last_name=body.last_name, weekly_capacity_hours=body.weekly_capacity_hours)
    db.add(u)
    db.flush()
    db.add(OrganizationMember(organization_id=ctx.org_id, user_id=u.id, role_id=role.id))
    audit(db, ctx, "team.member_add", "user", u.id, after={"email": email, "role": body.role})
    return {"user_id": str(u.id), "email": email, "role": body.role}


@router.patch("/members/{user_id}")
def change_member(user_id: uuid.UUID, body: RoleIn, ctx: Ctx = Depends(require("team.manage")), db: Session = Depends(get_db)):
    m = get_or_404(db, select(OrganizationMember).where(OrganizationMember.user_id == user_id,
                                                         OrganizationMember.organization_id == ctx.org_id), "Member")
    cur = db.get(Role, m.role_id)
    if cur.name == "client":
        raise bad_request("Client users are managed from the customer record")
    before = {"role": cur.name, "status": m.status}
    owners = db.scalar(select(func.count()).select_from(OrganizationMember).join(Role, Role.id == OrganizationMember.role_id).where(
        OrganizationMember.organization_id == ctx.org_id, Role.name == "owner", OrganizationMember.status == "active"))
    demoting_owner = cur.name == "owner" and ((body.role and body.role != "owner") or body.status == "suspended")
    if demoting_owner and owners <= 1:
        raise conflict("The organization must keep at least one active owner", "LAST_OWNER")
    if (cur.name == "owner" or body.role == "owner") and not ctx.is_owner:
        raise forbidden("Only an owner can change ownership")
    if body.role:
        m.role_id = db.scalar(select(Role.id).where(Role.name == body.role, Role.is_system_role.is_(True)))
    if body.status:
        m.status = body.status
    audit(db, ctx, "team.permission_change", "user", user_id, before, {"role": body.role or cur.name, "status": m.status})
    return {"user_id": str(user_id), "role": body.role or cur.name, "status": m.status}
