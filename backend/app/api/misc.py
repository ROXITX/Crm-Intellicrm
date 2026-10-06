import re
import uuid
from datetime import date, datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, literal_column, or_, select, text
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.db import get_db
from app.core.deps import Ctx, get_ctx, require
from app.core.errors import AppError, bad_request
from app.core.scope import customer_cond, invoice_cond, project_cond, task_cond, ticket_cond
from app.core.security import hash_password, hash_token, verify_password
from app.core.util import Page, get_or_404, paginate, ser
from app.models import (AuditLog, Conversation, ConversationMember, Customer, CustomerContact, Invoice, Lead, Message,
                        Notification, Organization, Project, RefreshToken, Task, Ticket, User)

router = APIRouter(tags=["misc"])


# ------------------------------------------------------------------ notifications
@router.get("/notifications")
def list_notifications(unread: bool = False, p: Page = Depends(), ctx: Ctx = Depends(get_ctx), db: Session = Depends(get_db)):
    conds = [Notification.user_id == ctx.user.id, Notification.organization_id == ctx.org_id]
    if unread:
        conds.append(Notification.read_at.is_(None))
    unread_count = db.scalar(select(func.count()).select_from(Notification).where(
        Notification.user_id == ctx.user.id, Notification.organization_id == ctx.org_id, Notification.read_at.is_(None)))
    res = paginate(db, select(Notification).where(*conds).order_by(Notification.created_at.desc(), Notification.id), p, lambda r: ser(r[0]))
    res["unread_count"] = unread_count
    return res


@router.post("/notifications/{nid}/read", status_code=204)
def mark_read(nid: uuid.UUID, ctx: Ctx = Depends(get_ctx), db: Session = Depends(get_db)):
    n = get_or_404(db, select(Notification).where(Notification.id == nid, Notification.user_id == ctx.user.id,
                                                  Notification.organization_id == ctx.org_id), "Notification")
    n.read_at = n.read_at or datetime.now().astimezone()


@router.post("/notifications/read-all", status_code=204)
def mark_all_read(ctx: Ctx = Depends(get_ctx), db: Session = Depends(get_db)):
    db.execute(Notification.__table__.update().where(Notification.user_id == ctx.user.id, Notification.organization_id == ctx.org_id,
                                                      Notification.read_at.is_(None)).values(read_at=func.now()))


# ------------------------------------------------------------------ profile & settings
class ProfilePatch(BaseModel):
    first_name: str | None = Field(None, min_length=1, max_length=100)
    last_name: str | None = Field(None, max_length=100)
    notification_preferences: dict[str, bool] | None = None


class PasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=10, max_length=200)


class OrgPatch(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=200)
    email: EmailStr | None = None
    phone: str | None = Field(None, max_length=50)


@router.patch("/me")
def update_profile(body: ProfilePatch, ctx: Ctx = Depends(get_ctx), db: Session = Depends(get_db)):
    u = ctx.user
    if body.first_name: u.first_name = body.first_name
    if body.last_name is not None: u.last_name = body.last_name
    if body.notification_preferences is not None:
        u.preferences = {**(u.preferences or {}), "notifications": body.notification_preferences}
    return {"first_name": u.first_name, "last_name": u.last_name, "preferences": u.preferences or {}}


@router.get("/me/preferences")
def get_preferences(ctx: Ctx = Depends(get_ctx)):
    return ctx.user.preferences or {}


@router.post("/me/password", status_code=204)
def change_password(body: PasswordIn, ctx: Ctx = Depends(get_ctx), db: Session = Depends(get_db)):
    if not verify_password(body.current_password, ctx.user.password_hash):
        raise AppError(400, "INVALID_CREDENTIALS", "Current password is incorrect")
    ctx.user.password_hash = hash_password(body.new_password)
    db.execute(RefreshToken.__table__.update().where(RefreshToken.user_id == ctx.user.id, RefreshToken.revoked_at.is_(None)).values(revoked_at=func.now()))
    audit(db, ctx, "auth.password_change", "user", ctx.user.id)


@router.get("/settings/organization")
def get_org(ctx: Ctx = Depends(require("settings.manage")), db: Session = Depends(get_db)):
    return ser(db.get(Organization, ctx.org_id))


@router.patch("/settings/organization")
def update_org(body: OrgPatch, ctx: Ctx = Depends(require("settings.manage")), db: Session = Depends(get_db)):
    org = db.get(Organization, ctx.org_id)
    before = {"name": org.name, "email": org.email, "phone": org.phone}
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(org, k, v)
    audit(db, ctx, "organization.update", "organization", org.id, before, {"name": org.name, "email": org.email, "phone": org.phone})
    return ser(org)


# ------------------------------------------------------------------ audit log
@router.get("/audit-logs")
def audit_logs(action: str | None = None, entity_type: str | None = None, actor_id: uuid.UUID | None = None,
               date_from: date | None = None, date_to: date | None = None, p: Page = Depends(),
               ctx: Ctx = Depends(require("audit.read")), db: Session = Depends(get_db)):
    conds = [AuditLog.organization_id == ctx.org_id]
    if action: conds.append(AuditLog.action.ilike(f"{action}%"))
    if entity_type: conds.append(AuditLog.entity_type == entity_type)
    if actor_id: conds.append(AuditLog.actor_id == actor_id)
    if date_from: conds.append(func.date(AuditLog.created_at) >= date_from)
    if date_to: conds.append(func.date(AuditLog.created_at) <= date_to)
    stmt = select(AuditLog, User.email).outerjoin(User, User.id == AuditLog.actor_id).where(*conds).order_by(AuditLog.created_at.desc(), AuditLog.id)
    return paginate(db, stmt, p, lambda r: ser(r[0], extra={"actor_email": r[1], "metadata": r[0].meta}, exclude={"meta"}))


# ------------------------------------------------------------------ global search (PostgreSQL full-text)
def _tsq(q: str) -> str | None:
    toks = re.findall(r"\w+", q.lower())[:6]
    return " & ".join(f"{t}:*" for t in toks) or None


def fts(*cols):
    """tsvector expression; mirrors the GIN index definitions in migration 0003 (immutable `||`, constant regconfig)."""
    expr = func.coalesce(cols[0], "")
    for c in cols[1:]:
        expr = expr.op("||")(literal_column("' '")).op("||")(func.coalesce(c, ""))
    return func.to_tsvector(literal_column("'simple'::regconfig"), expr)


@router.get("/search")
def search(q: str = Query(min_length=2, max_length=100), limit: int = Query(5, ge=1, le=20),
           ctx: Ctx = Depends(get_ctx), db: Session = Depends(get_db)):
    tsq = _tsq(q)
    if not tsq:
        return {"query": q, "results": []}
    query = func.to_tsquery(literal_column("'simple'::regconfig"), tsq)
    res = []

    def add(kind, rows, mk):
        res.extend({"type": kind, **mk(r)} for r in rows)

    if ctx.can("leads.read"):
        add("lead", db.execute(select(Lead.id, Lead.name, Lead.company_name).where(
            Lead.organization_id == ctx.org_id, Lead.deleted_at.is_(None), fts(Lead.name, Lead.company_name, Lead.email).op("@@")(query)).limit(limit)).all(),
            lambda r: {"id": str(r[0]), "title": r[1], "subtitle": r[2]})
    if ctx.can("customers.read"):
        add("customer", db.execute(select(Customer.id, Customer.name, Customer.company_name).where(
            customer_cond(db, ctx), fts(Customer.name, Customer.company_name, Customer.email).op("@@")(query)).limit(limit)).all(),
            lambda r: {"id": str(r[0]), "title": r[1], "subtitle": r[2]})
    if ctx.can("projects.read"):
        add("project", db.execute(select(Project.id, Project.name, Project.status).where(
            project_cond(db, ctx), fts(Project.name, Project.description).op("@@")(query)).limit(limit)).all(),
            lambda r: {"id": str(r[0]), "title": r[1], "subtitle": r[2]})
    if ctx.can("tasks.read") and not ctx.is_client:
        add("task", db.execute(select(Task.id, Task.title, Task.status).where(
            task_cond(db, ctx), fts(Task.title, Task.description).op("@@")(query)).limit(limit)).all(),
            lambda r: {"id": str(r[0]), "title": r[1], "subtitle": r[2]})
    if ctx.can("tickets.read"):
        add("ticket", db.execute(select(Ticket.id, Ticket.subject, Ticket.status).where(
            ticket_cond(db, ctx), fts(Ticket.subject, Ticket.description).op("@@")(query)).limit(limit)).all(),
            lambda r: {"id": str(r[0]), "title": r[1], "subtitle": r[2]})
    if ctx.can("invoices.read"):
        add("invoice", db.execute(select(Invoice.id, Invoice.invoice_number, Invoice.status).where(
            invoice_cond(db, ctx), Invoice.invoice_number.ilike(f"%{q}%")).limit(limit)).all(),
            lambda r: {"id": str(r[0]), "title": r[1], "subtitle": r[2]})
    if ctx.can("messages.read"):  # only conversations the user belongs to
        add("message", db.execute(select(Message.id, Message.body, Message.conversation_id).join(
            ConversationMember, ConversationMember.conversation_id == Message.conversation_id).where(
            ConversationMember.user_id == ctx.user.id, Message.organization_id == ctx.org_id, Message.deleted_at.is_(None),
            fts(Message.body).op("@@")(query)).limit(limit)).all(),
            lambda r: {"id": str(r[0]), "title": r[1][:100], "subtitle": "Message", "conversation_id": str(r[2])})
    return {"query": q, "results": res}


# ------------------------------------------------------------------ client portal
@router.get("/portal/home")
def portal_home(ctx: Ctx = Depends(require("portal.access")), db: Session = Depends(get_db)):
    from app.core.deps import client_customer_id
    cid = client_customer_id(db, ctx)
    cust = db.get(Customer, cid)
    projects = db.scalars(select(Project).where(project_cond(db, ctx)).order_by(Project.due_date)).all()
    from app.models import Milestone
    milestones = db.execute(select(Milestone, Project.name).join(Project, Project.id == Milestone.project_id).where(
        project_cond(db, ctx), Milestone.status != "completed", Milestone.due_date >= date.today()).order_by(Milestone.due_date).limit(5)).all()
    open_tickets = db.scalar(select(func.count()).select_from(Ticket).where(ticket_cond(db, ctx), Ticket.status.notin_(["resolved", "closed"])))
    outstanding = db.scalar(select(func.coalesce(func.sum(Invoice.total - Invoice.amount_paid), 0)).where(
        invoice_cond(db, ctx), Invoice.status.in_(["sent", "partially_paid", "overdue"])))
    inv = db.scalars(select(Invoice).where(invoice_cond(db, ctx)).order_by(Invoice.issue_date.desc()).limit(3)).all()
    return {"customer_name": cust.name,
            "projects": [{"id": str(p.id), "name": p.name, "status": p.status, "progress": str(p.progress), "due_date": p.due_date.isoformat() if p.due_date else None} for p in projects],
            "upcoming_milestones": [{"name": m.name, "project": pn, "due_date": m.due_date.isoformat()} for m, pn in milestones],
            "open_requests": open_tickets, "outstanding_amount": str(outstanding),
            "recent_invoices": [ser(i) for i in inv]}
