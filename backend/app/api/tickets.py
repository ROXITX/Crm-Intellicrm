import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.ai import service as ai
from app.core.audit import audit, notify, snapshot
from app.core.db import get_db
from app.core.deps import Ctx, client_customer_id, require
from app.core.errors import bad_request, forbidden
from app.core.scope import customer_cond, project_cond, ticket_cond
from app.core.util import Page, get_or_404, paginate, ser
from app.models import Customer, OrganizationMember, Project, Ticket, TicketComment, User, Role

router = APIRouter(prefix="/tickets", tags=["tickets"])
Priority = Literal["low", "medium", "high", "critical"]
Status = Literal["open", "in_progress", "waiting_customer", "waiting_internal", "resolved", "closed"]
SLA_HOURS = {"critical": 4, "high": 8, "medium": 24, "low": 72}
AI_FIELDS = {"sentiment", "sentiment_confidence", "predicted_priority", "priority_confidence"}
CLIENT_HIDE = AI_FIELDS | {"assigned_to"}


class TicketIn(BaseModel):
    customer_id: uuid.UUID | None = None  # ignored for clients (derived server-side)
    project_id: uuid.UUID | None = None
    subject: str = Field(min_length=3, max_length=300)
    description: str = Field(min_length=3, max_length=10000)
    category: str | None = Field(None, max_length=100)
    priority: Priority | None = None  # clients cannot choose; staff may override the AI suggestion


class TicketPatch(BaseModel):
    status: Status | None = None
    priority: Priority | None = None
    category: str | None = Field(None, max_length=100)
    assigned_to: uuid.UUID | None = None


class CommentIn(BaseModel):
    body: str = Field(min_length=1, max_length=10000)
    is_internal: bool = False


def get_ticket(db, ctx, tid) -> Ticket:
    return get_or_404(db, select(Ticket).where(Ticket.id == tid, ticket_cond(db, ctx)), "Ticket")


def _out(t: Ticket, ctx: Ctx, extra=None):
    return ser(t, CLIENT_HIDE if ctx.is_client else frozenset(), extra)


@router.get("")
def list_tickets(q: str | None = None, status: Status | None = None, priority: Priority | None = None,
                 customer_id: uuid.UUID | None = None, assigned_to: uuid.UUID | None = None, mine: bool = False,
                 p: Page = Depends(), ctx: Ctx = Depends(require("tickets.read")), db: Session = Depends(get_db)):
    conds = [ticket_cond(db, ctx)]
    if q: conds.append(or_(Ticket.subject.ilike(f"%{q}%"), Ticket.description.ilike(f"%{q}%")))
    if status: conds.append(Ticket.status == status)
    if priority: conds.append(Ticket.priority == priority)
    if customer_id: conds.append(Ticket.customer_id == customer_id)
    if assigned_to: conds.append(Ticket.assigned_to == assigned_to)
    if mine: conds.append(Ticket.assigned_to == ctx.user.id)
    prio = func.array_position(["critical", "high", "medium", "low"], Ticket.priority)
    stmt = (select(Ticket, Customer.name, User.first_name).join(Customer, Customer.id == Ticket.customer_id)
            .outerjoin(User, User.id == Ticket.assigned_to).where(*conds).order_by(prio, Ticket.created_at.desc(), Ticket.id))
    return paginate(db, stmt, p, lambda r: _out(r[0], ctx, {"customer_name": r[1],
                                                           **({} if ctx.is_client else {"assignee_name": r[2]})}))


@router.post("", status_code=201)
def create_ticket(body: TicketIn, ctx: Ctx = Depends(require("tickets.write")), db: Session = Depends(get_db)):
    if ctx.is_client:
        customer_id = client_customer_id(db, ctx)
    else:
        if not body.customer_id:
            raise bad_request("customer_id is required", "VALIDATION_ERROR")
        customer_id = get_or_404(db, select(Customer).where(Customer.id == body.customer_id, customer_cond(db, ctx)),
                                 "Customer").id
    if body.project_id:
        get_or_404(db, select(Project).where(Project.id == body.project_id, Project.customer_id == customer_id,
                                              project_cond(db, ctx)), "Project")
    analysis = ai.analyze_ticket(body.subject, body.description)
    priority = body.priority if (body.priority and not ctx.is_client) else analysis["predicted_priority"]
    now = datetime.now(timezone.utc)
    t = Ticket(organization_id=ctx.org_id, customer_id=customer_id, project_id=body.project_id, created_by=ctx.user.id,
               subject=body.subject, description=body.description, category=body.category or analysis["category"],
               priority=priority, status="open", sentiment=analysis["sentiment"],
               sentiment_confidence=analysis["sentiment_confidence"], predicted_priority=analysis["predicted_priority"],
               priority_confidence=analysis["priority_confidence"], sla_due_at=now + timedelta(hours=SLA_HOURS[priority]))
    cust = db.get(Customer, customer_id)
    if not ctx.is_client:
        t.assigned_to = cust.account_owner_id
    else:
        t.assigned_to = cust.account_owner_id
    db.add(t)
    db.flush()
    ai.record_ticket_predictions(db, t, analysis)
    cust.last_interaction_at = now
    notify(db, ctx.org_id, t.assigned_to, "ticket_assigned", "New ticket", t.subject, "ticket", t.id)
    if priority in ("critical", "high"):
        for uid in db.scalars(select(OrganizationMember.user_id).join(Role, Role.id == OrganizationMember.role_id).where(
                OrganizationMember.organization_id == ctx.org_id, Role.name.in_(["owner", "manager"]))):
            if uid != t.assigned_to:
                notify(db, ctx.org_id, uid, "ticket_escalation", f"{priority.title()} ticket", t.subject, "ticket", t.id)
    audit(db, ctx, "ticket.create", "ticket", t.id, after=snapshot(t, ["subject", "priority", "status", "customer_id"]))
    return _out(t, ctx)


@router.get("/{ticket_id}")
def ticket_detail(ticket_id: uuid.UUID, ctx: Ctx = Depends(require("tickets.read")), db: Session = Depends(get_db)):
    t = get_ticket(db, ctx, ticket_id)
    q = select(TicketComment, User.first_name).join(User, User.id == TicketComment.author_id).where(
        TicketComment.ticket_id == t.id, TicketComment.organization_id == ctx.org_id)
    if ctx.is_client or not ctx.can("internal.view"):
        q = q.where(TicketComment.is_internal.is_(False))  # clients can NEVER read internal notes
    comments = db.execute(q.order_by(TicketComment.created_at)).all()
    cust = db.get(Customer, t.customer_id)
    return _out(t, ctx, {"customer_name": cust.name,
                         "comments": [ser(c, extra={"author_name": n}) for c, n in comments]})


@router.patch("/{ticket_id}")
def update_ticket(ticket_id: uuid.UUID, body: TicketPatch, ctx: Ctx = Depends(require("tickets.write")),
                  db: Session = Depends(get_db)):
    t = get_ticket(db, ctx, ticket_id)
    data = body.model_dump(exclude_unset=True)
    if ctx.is_client:
        # clients may only close their own ticket / reopen
        if set(data) - {"status"} or data.get("status") not in ("closed", "open"):
            raise forbidden("Clients can only close or reopen their tickets")
    if data.get("assigned_to"):
        if not db.scalar(select(OrganizationMember.id).where(OrganizationMember.organization_id == ctx.org_id,
                                                              OrganizationMember.user_id == data["assigned_to"],
                                                              OrganizationMember.status == "active")):
            raise bad_request("Assignee is not a member of this organization", "INVALID_ASSIGNEE")
    before = snapshot(t, ["status", "priority", "assigned_to", "category"])
    for k, v in data.items():
        setattr(t, k, v)
    if "priority" in data:  # human override re-baselines the SLA
        t.sla_due_at = t.created_at + timedelta(hours=SLA_HOURS[t.priority])
    if data.get("status") in ("resolved", "closed") and not t.resolved_at:
        t.resolved_at = datetime.now(timezone.utc)
    elif data.get("status") in ("open", "in_progress"):
        t.resolved_at = None
    if data.get("assigned_to") and data["assigned_to"] != ctx.user.id:
        notify(db, ctx.org_id, data["assigned_to"], "ticket_assigned", "Ticket assigned", t.subject, "ticket", t.id)
    audit(db, ctx, "ticket.update", "ticket", t.id, before, snapshot(t, ["status", "priority", "assigned_to", "category"]))
    return _out(t, ctx)


@router.post("/{ticket_id}/escalate")
def escalate(ticket_id: uuid.UUID, ctx: Ctx = Depends(require("tickets.write", "internal.view")), db: Session = Depends(get_db)):
    t = get_ticket(db, ctx, ticket_id)
    order = ["low", "medium", "high", "critical"]
    before = t.priority
    t.priority = order[min(order.index(t.priority) + 1, 3)]
    t.sla_due_at = datetime.now(timezone.utc) + timedelta(hours=SLA_HOURS[t.priority])
    for uid in db.scalars(select(OrganizationMember.user_id).join(Role, Role.id == OrganizationMember.role_id).where(
            OrganizationMember.organization_id == ctx.org_id, Role.name.in_(["owner", "manager"]))):
        notify(db, ctx.org_id, uid, "ticket_escalation", "Ticket escalated", t.subject, "ticket", t.id)
    audit(db, ctx, "ticket.escalate", "ticket", t.id, {"priority": before}, {"priority": t.priority})
    return _out(t, ctx)


@router.post("/{ticket_id}/comments", status_code=201)
def add_comment(ticket_id: uuid.UUID, body: CommentIn, ctx: Ctx = Depends(require("tickets.write")),
                db: Session = Depends(get_db)):
    t = get_ticket(db, ctx, ticket_id)
    if body.is_internal and (ctx.is_client or not ctx.can("internal.view")):
        raise forbidden("Clients cannot create internal notes")
    c = TicketComment(organization_id=ctx.org_id, ticket_id=t.id, author_id=ctx.user.id, body=body.body,
                      is_internal=body.is_internal)
    db.add(c)
    db.flush()
    if not body.is_internal:
        if ctx.is_client:
            notify(db, ctx.org_id, t.assigned_to, "ticket_comment", "Customer replied", t.subject, "ticket", t.id)
            if t.status == "waiting_customer":
                t.status = "open"
        elif t.status == "open":
            t.status = "in_progress"
        db.get(Customer, t.customer_id).last_interaction_at = datetime.now(timezone.utc)
    return ser(c, extra={"author_name": ctx.user.first_name})


@router.get("/{ticket_id}/assist")
def assist(ticket_id: uuid.UUID, ctx: Ctx = Depends(require("tickets.read", "ai.read", "internal.view")), db: Session = Depends(get_db)):
    """AI summary + suggested reply. A draft only - a human must review and send it."""
    t = get_ticket(db, ctx, ticket_id)
    comments = db.scalars(select(TicketComment).where(TicketComment.ticket_id == t.id).order_by(TicketComment.created_at)).all()
    return ai.ticket_assist(t, comments)
