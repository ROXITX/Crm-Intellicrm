import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai import service as ai
from app.core.audit import audit, notify, snapshot
from app.core.db import get_db
from app.core.deps import Ctx, require
from app.core.errors import bad_request
from app.core.scope import customer_cond, project_cond
from app.core.util import Page, get_or_404, paginate, ser
from app.models import Customer, Milestone, OrganizationMember, Project, ProjectMember, Task, User

router = APIRouter(prefix="/projects", tags=["projects"])
Status = Literal["planning", "active", "at_risk", "delayed", "completed", "archived"]
AI_FIELDS = {"delay_probability", "risk_level"}


class ProjectIn(BaseModel):
    customer_id: uuid.UUID
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(None, max_length=5000)
    status: Status = "planning"
    owner_id: uuid.UUID | None = None
    budget: Decimal | None = Field(None, ge=0, max_digits=14, decimal_places=2)
    start_date: date | None = None
    due_date: date | None = None

    @model_validator(mode="after")
    def _dates(self):
        if self.start_date and self.due_date and self.due_date < self.start_date:
            raise ValueError("due_date must not be before start_date")
        return self


class ProjectPatch(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = Field(None, max_length=5000)
    status: Status | None = None
    owner_id: uuid.UUID | None = None
    budget: Decimal | None = Field(None, ge=0, max_digits=14, decimal_places=2)
    start_date: date | None = None
    due_date: date | None = None


class MilestoneIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    due_date: date | None = None
    status: Literal["pending", "in_progress", "completed"] = "pending"
    progress: Decimal = Field(0, ge=0, le=100)


class MemberIn(BaseModel):
    user_id: uuid.UUID
    role: str | None = Field(None, max_length=50)


def get_project(db, ctx, pid) -> Project:
    return get_or_404(db, select(Project).where(Project.id == pid, project_cond(db, ctx)), "Project")


def _member_check(db, ctx, uid):
    if uid and not db.scalar(select(OrganizationMember.id).where(
            OrganizationMember.organization_id == ctx.org_id, OrganizationMember.user_id == uid,
            OrganizationMember.status == "active")):
        raise bad_request("User is not a member of this organization", "INVALID_USER")


def _out(p: Project, ctx: Ctx, extra=None):
    return ser(p, AI_FIELDS if ctx.is_client else frozenset(), extra)


@router.get("")
def list_projects(q: str | None = None, status: Status | None = None, customer_id: uuid.UUID | None = None,
                  risk: str | None = None, p: Page = Depends(),
                  ctx: Ctx = Depends(require("projects.read")), db: Session = Depends(get_db)):
    conds = [project_cond(db, ctx)]
    if q: conds.append(Project.name.ilike(f"%{q}%"))
    if status: conds.append(Project.status == status)
    if customer_id: conds.append(Project.customer_id == customer_id)
    if risk and not ctx.is_client: conds.append(Project.risk_level == risk)
    stmt = (select(Project, Customer.name, User.first_name).join(Customer, Customer.id == Project.customer_id)
            .outerjoin(User, User.id == Project.owner_id).where(*conds).order_by(Project.due_date.asc().nulls_last(), Project.id))
    return paginate(db, stmt, p, lambda r: _out(r[0], ctx, {"customer_name": r[1], "owner_name": r[2]}))


@router.post("", status_code=201)
def create_project(body: ProjectIn, ctx: Ctx = Depends(require("projects.write")), db: Session = Depends(get_db)):
    get_or_404(db, select(Customer).where(Customer.id == body.customer_id, customer_cond(db, ctx)), "Customer")
    _member_check(db, ctx, body.owner_id)
    proj = Project(organization_id=ctx.org_id, **{**body.model_dump(), "owner_id": body.owner_id or ctx.user.id})
    db.add(proj)
    db.flush()
    db.add(ProjectMember(project_id=proj.id, user_id=proj.owner_id, organization_id=ctx.org_id, role="lead"))
    audit(db, ctx, "project.create", "project", proj.id, after=snapshot(proj))
    return ser(proj)


@router.get("/{project_id}")
def project_detail(project_id: uuid.UUID, ctx: Ctx = Depends(require("projects.read")), db: Session = Depends(get_db)):
    proj = get_project(db, ctx, project_id)
    cust = db.get(Customer, proj.customer_id)
    ms = db.scalars(select(Milestone).where(Milestone.project_id == proj.id, Milestone.organization_id == ctx.org_id)
                    .order_by(Milestone.due_date)).all()
    members = db.execute(select(ProjectMember, User).join(User, User.id == ProjectMember.user_id)
                         .where(ProjectMember.project_id == proj.id, ProjectMember.organization_id == ctx.org_id)).all()
    counts = dict(db.execute(select(Task.status, func.count()).where(Task.project_id == proj.id, Task.deleted_at.is_(None))
                             .group_by(Task.status)).all())
    out = _out(proj, ctx, {"customer_name": cust.name, "milestones": [ser(m) for m in ms],
                           "members": [{"user_id": str(u.id), "name": f"{u.first_name} {u.last_name or ''}".strip(),
                                        "role": m.role} for m, u in members] if not ctx.is_client else [],
                           "task_counts": counts})
    if not ctx.is_client and ctx.can("ai.read"):
        out["ai_risk"] = ai.latest_prediction(db, ctx.org_id, "project", proj.id, "project_delay")
    return out


@router.patch("/{project_id}")
def update_project(project_id: uuid.UUID, body: ProjectPatch, ctx: Ctx = Depends(require("projects.write")),
                   db: Session = Depends(get_db)):
    proj = get_project(db, ctx, project_id)
    data = body.model_dump(exclude_unset=True)
    if data.get("name") is None and "name" in data:
        raise bad_request("name cannot be empty")
    _member_check(db, ctx, data.get("owner_id"))
    sd, dd = data.get("start_date", proj.start_date), data.get("due_date", proj.due_date)
    if sd and dd and dd < sd:
        raise bad_request("due_date must not be before start_date", "VALIDATION_ERROR")
    before = snapshot(proj)
    for k, v in data.items():
        setattr(proj, k, v)
    if data.get("status") == "completed":
        proj.progress = Decimal(100)
    audit(db, ctx, "project.update", "project", proj.id, before, snapshot(proj))
    if "owner_id" in data and data["owner_id"] != before["owner_id"]:
        notify(db, ctx.org_id, data["owner_id"], "assignment", "Project assigned", f"You now own {proj.name}", "project", proj.id)
    return ser(proj)


@router.delete("/{project_id}", status_code=204)
def archive_project(project_id: uuid.UUID, ctx: Ctx = Depends(require("projects.write")), db: Session = Depends(get_db)):
    proj = get_project(db, ctx, project_id)
    proj.deleted_at = datetime.now(timezone.utc)
    audit(db, ctx, "project.archive", "project", proj.id, before=snapshot(proj))


@router.post("/{project_id}/milestones", status_code=201)
def add_milestone(project_id: uuid.UUID, body: MilestoneIn, ctx: Ctx = Depends(require("projects.write")),
                  db: Session = Depends(get_db)):
    proj = get_project(db, ctx, project_id)
    m = Milestone(organization_id=ctx.org_id, project_id=proj.id, **body.model_dump())
    db.add(m)
    db.flush()
    return ser(m)


@router.patch("/{project_id}/milestones/{milestone_id}")
def update_milestone(project_id: uuid.UUID, milestone_id: uuid.UUID, body: MilestoneIn,
                     ctx: Ctx = Depends(require("projects.write")), db: Session = Depends(get_db)):
    proj = get_project(db, ctx, project_id)
    m = get_or_404(db, select(Milestone).where(Milestone.id == milestone_id, Milestone.project_id == proj.id,
                                                Milestone.organization_id == ctx.org_id), "Milestone")
    for k, v in body.model_dump().items():
        setattr(m, k, v)
    return ser(m)


@router.post("/{project_id}/members", status_code=201)
def add_member(project_id: uuid.UUID, body: MemberIn, ctx: Ctx = Depends(require("projects.write")),
               db: Session = Depends(get_db)):
    proj = get_project(db, ctx, project_id)
    _member_check(db, ctx, body.user_id)
    if db.get(ProjectMember, (proj.id, body.user_id)):
        raise bad_request("User is already a project member", "ALREADY_MEMBER")
    db.add(ProjectMember(project_id=proj.id, user_id=body.user_id, organization_id=ctx.org_id, role=body.role))
    notify(db, ctx.org_id, body.user_id, "assignment", "Added to project", f"You were added to {proj.name}", "project", proj.id)
    audit(db, ctx, "project.member_add", "project", proj.id, meta={"user_id": str(body.user_id)})
    return {"project_id": str(proj.id), "user_id": str(body.user_id)}


@router.delete("/{project_id}/members/{user_id}", status_code=204)
def remove_member(project_id: uuid.UUID, user_id: uuid.UUID, ctx: Ctx = Depends(require("projects.write")),
                  db: Session = Depends(get_db)):
    proj = get_project(db, ctx, project_id)
    m = get_or_404(db, select(ProjectMember).where(ProjectMember.project_id == proj.id, ProjectMember.user_id == user_id), "Member")
    db.delete(m)


@router.post("/{project_id}/risk")
def run_project_risk(project_id: uuid.UUID, ctx: Ctx = Depends(require("projects.read", "ai.read", "internal.view")),
                     db: Session = Depends(get_db)):
    proj = get_project(db, ctx, project_id)
    pred = ai.predict_project_delay(db, proj)
    audit(db, ctx, "ai.project_delay", "project", proj.id)
    return pred
