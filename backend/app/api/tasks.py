import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.audit import audit, notify, snapshot
from app.core.db import get_db
from app.core.deps import Ctx, require
from app.core.errors import bad_request, conflict, forbidden
from app.core.scope import customer_cond, project_cond, task_cond
from app.core.util import Page, get_or_404, paginate, ser
from app.models import (Customer, OrganizationMember, Project, Task, TaskDependency, User)

router = APIRouter(prefix="/tasks", tags=["tasks"])
Status = Literal["todo", "in_progress", "blocked", "review", "done", "cancelled"]
Priority = Literal["low", "medium", "high", "critical"]
OPEN = ["todo", "in_progress", "blocked", "review"]


class TaskIn(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str | None = Field(None, max_length=5000)
    project_id: uuid.UUID | None = None
    customer_id: uuid.UUID | None = None
    assignee_id: uuid.UUID | None = None
    priority: Priority = "medium"
    status: Status = "todo"
    due_date: datetime | None = None
    estimated_hours: Decimal | None = Field(None, ge=0, max_digits=8, decimal_places=2)
    actual_hours: Decimal | None = Field(None, ge=0, max_digits=8, decimal_places=2)


class TaskPatch(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=300)
    description: str | None = Field(None, max_length=5000)
    assignee_id: uuid.UUID | None = None
    priority: Priority | None = None
    status: Status | None = None
    due_date: datetime | None = None
    estimated_hours: Decimal | None = Field(None, ge=0, max_digits=8, decimal_places=2)
    actual_hours: Decimal | None = Field(None, ge=0, max_digits=8, decimal_places=2)


class DepIn(BaseModel):
    depends_on_task_id: uuid.UUID


def get_task(db, ctx, tid) -> Task:
    return get_or_404(db, select(Task).where(Task.id == tid, task_cond(db, ctx)), "Task")


def _assignee_ok(db, ctx, uid):
    if uid and not db.scalar(select(OrganizationMember.id).where(
            OrganizationMember.organization_id == ctx.org_id, OrganizationMember.user_id == uid,
            OrganizationMember.status == "active")):
        raise bad_request("Assignee is not a member of this organization", "INVALID_ASSIGNEE")


def recalc_project_progress(db: Session, project_id):
    """Deterministic business rule: progress = done / (all non-cancelled tasks)."""
    if not project_id:
        return
    total, done = db.execute(select(func.count(), func.count().filter(Task.status == "done")).where(
        Task.project_id == project_id, Task.deleted_at.is_(None), Task.status != "cancelled")).one()
    proj = db.get(Project, project_id)
    if proj and total and proj.status not in ("completed", "archived"):
        proj.progress = (Decimal(done) * 100 / Decimal(total)).quantize(Decimal("0.01"))


def _unfinished_deps(db, task_id):
    return db.scalars(select(Task.title).join(TaskDependency, TaskDependency.depends_on_task_id == Task.id)
                      .where(TaskDependency.task_id == task_id, Task.status.notin_(["done", "cancelled"]))).all()


@router.get("")
def list_tasks(q: str | None = None, status: Status | None = None, priority: Priority | None = None,
               assignee_id: uuid.UUID | None = None, project_id: uuid.UUID | None = None, mine: bool = False,
               overdue: bool = False, p: Page = Depends(), ctx: Ctx = Depends(require("tasks.read")),
               db: Session = Depends(get_db)):
    conds = [task_cond(db, ctx)]
    if q: conds.append(Task.title.ilike(f"%{q}%"))
    if status: conds.append(Task.status == status)
    if priority: conds.append(Task.priority == priority)
    if assignee_id: conds.append(Task.assignee_id == assignee_id)
    if mine: conds.append(Task.assignee_id == ctx.user.id)
    if project_id: conds.append(Task.project_id == project_id)
    if overdue: conds.append((Task.due_date < func.now()) & Task.status.in_(OPEN))
    prio = func.array_position(["critical", "high", "medium", "low"], Task.priority)
    stmt = (select(Task, User.first_name, Project.name).outerjoin(User, User.id == Task.assignee_id)
            .outerjoin(Project, Project.id == Task.project_id).where(*conds)
            .order_by(prio, Task.due_date.asc().nulls_last(), Task.id))
    return paginate(db, stmt, p, lambda r: ser(r[0], extra={"assignee_name": r[1], "project_name": r[2]}))


@router.post("", status_code=201)
def create_task(body: TaskIn, ctx: Ctx = Depends(require("tasks.write")), db: Session = Depends(get_db)):
    if body.assignee_id and body.assignee_id != ctx.user.id and not ctx.can("tasks.assign"):
        raise forbidden("You cannot assign tasks to other people")
    _assignee_ok(db, ctx, body.assignee_id)
    if body.project_id:
        get_or_404(db, select(Project).where(Project.id == body.project_id, project_cond(db, ctx)), "Project")
    if body.customer_id:
        get_or_404(db, select(Customer).where(Customer.id == body.customer_id, customer_cond(db, ctx)), "Customer")
    t = Task(organization_id=ctx.org_id, created_by=ctx.user.id, **{**body.model_dump(),
             "assignee_id": body.assignee_id or ctx.user.id})
    if t.status == "done":
        t.completed_at = datetime.now(timezone.utc)
    db.add(t)
    db.flush()
    if t.assignee_id != ctx.user.id:
        notify(db, ctx.org_id, t.assignee_id, "assignment", "Task assigned", t.title, "task", t.id)
    recalc_project_progress(db, t.project_id)
    audit(db, ctx, "task.create", "task", t.id, after=snapshot(t))
    return ser(t)


@router.get("/{task_id}")
def task_detail(task_id: uuid.UUID, ctx: Ctx = Depends(require("tasks.read")), db: Session = Depends(get_db)):
    t = get_task(db, ctx, task_id)
    deps = db.execute(select(Task.id, Task.title, Task.status).join(TaskDependency, TaskDependency.depends_on_task_id == Task.id)
                      .where(TaskDependency.task_id == t.id)).all()
    return ser(t, extra={"dependencies": [{"id": str(i), "title": ti, "status": s} for i, ti, s in deps]})


@router.patch("/{task_id}")
def update_task(task_id: uuid.UUID, body: TaskPatch, ctx: Ctx = Depends(require("tasks.write")), db: Session = Depends(get_db)):
    t = get_task(db, ctx, task_id)
    data = body.model_dump(exclude_unset=True)
    if "title" in data and not data["title"]:
        raise bad_request("title cannot be empty")
    # Staff may only progress their own work (status/hours/description), not reassign or reprioritise.
    if not ctx.can("tasks.assign"):
        if t.assignee_id != ctx.user.id and t.created_by != ctx.user.id:
            raise forbidden()
        if {"assignee_id", "priority", "due_date"} & data.keys():
            raise forbidden("Only managers can change assignee, priority or due date")
    if "assignee_id" in data:
        _assignee_ok(db, ctx, data["assignee_id"])
    new_status = data.get("status")
    if new_status in ("in_progress", "review", "done"):
        pending = _unfinished_deps(db, t.id)
        if pending:
            raise conflict(f"Blocked by unfinished dependencies: {', '.join(pending)}", "DEPENDENCY_PENDING")
    before = snapshot(t)
    for k, v in data.items():
        setattr(t, k, v)
    if new_status == "done" and not t.completed_at:
        t.completed_at = datetime.now(timezone.utc)
    elif new_status and new_status != "done":
        t.completed_at = None
    if "assignee_id" in data and data["assignee_id"] and data["assignee_id"] != before["assignee_id"] \
            and data["assignee_id"] != ctx.user.id:
        notify(db, ctx.org_id, data["assignee_id"], "assignment", "Task assigned", t.title, "task", t.id)
    db.flush()
    recalc_project_progress(db, t.project_id)
    audit(db, ctx, "task.update", "task", t.id, before, snapshot(t))
    return ser(t)


@router.delete("/{task_id}", status_code=204)
def delete_task(task_id: uuid.UUID, ctx: Ctx = Depends(require("tasks.assign")), db: Session = Depends(get_db)):
    t = get_task(db, ctx, task_id)
    t.deleted_at = datetime.now(timezone.utc)
    db.flush()
    recalc_project_progress(db, t.project_id)
    audit(db, ctx, "task.delete", "task", t.id, before=snapshot(t))


def _creates_cycle(db, task_id, dep_id) -> bool:
    seen, stack = set(), [dep_id]
    while stack:
        cur = stack.pop()
        if cur == task_id:
            return True
        if cur in seen:
            continue
        seen.add(cur)
        stack.extend(db.scalars(select(TaskDependency.depends_on_task_id).where(TaskDependency.task_id == cur)))
    return False


@router.post("/{task_id}/dependencies", status_code=201)
def add_dependency(task_id: uuid.UUID, body: DepIn, ctx: Ctx = Depends(require("tasks.assign")), db: Session = Depends(get_db)):
    t = get_task(db, ctx, task_id)
    dep = get_task(db, ctx, body.depends_on_task_id)
    if dep.id == t.id or _creates_cycle(db, t.id, dep.id):
        raise bad_request("Dependency would create a cycle", "DEPENDENCY_CYCLE")
    if not db.get(TaskDependency, (t.id, dep.id)):
        db.add(TaskDependency(task_id=t.id, depends_on_task_id=dep.id))
    return {"task_id": str(t.id), "depends_on_task_id": str(dep.id)}


@router.delete("/{task_id}/dependencies/{dep_id}", status_code=204)
def remove_dependency(task_id: uuid.UUID, dep_id: uuid.UUID, ctx: Ctx = Depends(require("tasks.assign")),
                      db: Session = Depends(get_db)):
    t = get_task(db, ctx, task_id)
    d = get_or_404(db, select(TaskDependency).where(TaskDependency.task_id == t.id, TaskDependency.depends_on_task_id == dep_id), "Dependency")
    db.delete(d)
