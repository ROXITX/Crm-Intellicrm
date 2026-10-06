from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import OrganizationMember, Role, Task, User

OPEN = ["todo", "in_progress", "blocked", "review"]
WINDOW_WEEKS = 2


def workload_status(pct: float) -> str:
    return "overloaded" if pct > 100 else "high" if pct >= 80 else "normal"


def team_workload(db: Session, org_id, only_user=None, user_ids=None) -> list[dict]:
    """capacity_usage = allocated_estimated_hours / available_hours (2-week window), per DESIGN/FUNCTIONALITY."""
    q = (select(User, Role.name, OrganizationMember.status).join(OrganizationMember, OrganizationMember.user_id == User.id)
         .join(Role, Role.id == OrganizationMember.role_id)
         .where(OrganizationMember.organization_id == org_id, Role.name != "client"))
    if only_user:
        q = q.where(User.id == only_user)
    if user_ids is not None:
        q = q.where(User.id.in_(user_ids))
    now = datetime.now(timezone.utc)
    out = []
    for u, role, mstatus in db.execute(q.order_by(User.first_name)).all():
        active, overdue, alloc = db.execute(select(
            func.count(), func.count().filter(Task.due_date < now),
            func.coalesce(func.sum(func.greatest(func.coalesce(Task.estimated_hours, 0) - func.coalesce(Task.actual_hours, 0), 0)), 0)
        ).where(Task.organization_id == org_id, Task.assignee_id == u.id, Task.deleted_at.is_(None),
                Task.status.in_(OPEN))).one()
        avail = Decimal(u.weekly_capacity_hours) * WINDOW_WEEKS
        pct = float(Decimal(alloc) / avail * 100) if avail else 0.0
        out.append({"user_id": str(u.id), "name": f"{u.first_name} {u.last_name or ''}".strip(), "email": u.email,
                    "role": role, "member_status": mstatus, "active_tasks": active, "overdue_tasks": overdue,
                    "allocated_hours": str(alloc), "available_hours": str(avail),
                    "capacity_pct": round(pct, 1), "status": workload_status(pct)})
    return out
