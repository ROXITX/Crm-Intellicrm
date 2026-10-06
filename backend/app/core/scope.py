"""Object-level visibility rules. Every list/detail query goes through these helpers, always
combined with `organization_id == ctx.org_id` (never an org id supplied by the browser).

owner   -> everything in the organization
manager -> leads org-wide; customers/projects/tasks/tickets within their assigned scope
staff   -> only customers/projects/tasks/tickets assigned to them
client  -> only their own customer account (projects, tickets, non-draft invoices, documents)
"""
from sqlalchemy import and_, exists, or_, select, true
from sqlalchemy.orm import Session

from app.core.deps import Ctx, client_customer_id
from app.models import Customer, Document, Invoice, Project, ProjectMember, Task, Ticket


def _my_project_ids(ctx: Ctx):
    return select(Project.id).where(
        Project.organization_id == ctx.org_id, Project.deleted_at.is_(None),
        or_(Project.owner_id == ctx.user.id,
            exists().where(ProjectMember.project_id == Project.id, ProjectMember.user_id == ctx.user.id),
            exists().where(Task.project_id == Project.id, Task.assignee_id == ctx.user.id, Task.deleted_at.is_(None))))


def project_cond(db: Session, ctx: Ctx):
    base = and_(Project.organization_id == ctx.org_id, Project.deleted_at.is_(None))
    if ctx.sees_all:
        return base
    if ctx.is_client:
        return and_(base, Project.customer_id == client_customer_id(db, ctx))
    return and_(base, Project.id.in_(_my_project_ids(ctx)))


def customer_cond(db: Session, ctx: Ctx):
    base = and_(Customer.organization_id == ctx.org_id, Customer.deleted_at.is_(None))
    if ctx.sees_all:
        return base
    if ctx.is_client:
        return and_(base, Customer.id == client_customer_id(db, ctx))
    return and_(base, or_(
        Customer.account_owner_id == ctx.user.id,
        Customer.id.in_(select(Project.customer_id).where(Project.id.in_(_my_project_ids(ctx)))),
        Customer.id.in_(select(Ticket.customer_id).where(Ticket.organization_id == ctx.org_id, Ticket.assigned_to == ctx.user.id)),
        Customer.id.in_(select(Task.customer_id).where(Task.organization_id == ctx.org_id, Task.assignee_id == ctx.user.id,
                                                       Task.customer_id.is_not(None)))))


def task_cond(db: Session, ctx: Ctx):
    base = and_(Task.organization_id == ctx.org_id, Task.deleted_at.is_(None))
    if ctx.sees_all:
        return base
    if ctx.is_client:
        return false_()
    mine = or_(Task.assignee_id == ctx.user.id, Task.created_by == ctx.user.id)
    if ctx.role == "manager":
        mine = or_(mine, Task.project_id.in_(_my_project_ids(ctx)))
    return and_(base, mine)


def ticket_cond(db: Session, ctx: Ctx):
    base = and_(Ticket.organization_id == ctx.org_id, Ticket.deleted_at.is_(None))
    if ctx.sees_all:
        return base
    if ctx.is_client:
        return and_(base, Ticket.customer_id == client_customer_id(db, ctx))
    mine = or_(Ticket.assigned_to == ctx.user.id, Ticket.created_by == ctx.user.id)
    if ctx.role == "manager":
        mine = or_(mine, Ticket.customer_id.in_(select(Customer.id).where(customer_cond(db, ctx))))
    return and_(base, mine)


def invoice_cond(db: Session, ctx: Ctx):
    base = Invoice.organization_id == ctx.org_id
    if ctx.is_client:
        return and_(base, Invoice.customer_id == client_customer_id(db, ctx), Invoice.status != "draft")
    if ctx.sees_all:
        return base
    return and_(base, Invoice.customer_id.in_(select(Customer.id).where(customer_cond(db, ctx))))


def document_cond(db: Session, ctx: Ctx):
    base = and_(Document.organization_id == ctx.org_id, Document.deleted_at.is_(None))
    if ctx.sees_all:
        return base
    if ctx.is_client:
        cid = client_customer_id(db, ctx)
        return and_(base, or_(Document.customer_id == cid,
                              Document.project_id.in_(select(Project.id).where(Project.customer_id == cid)),
                              Document.ticket_id.in_(select(Ticket.id).where(Ticket.customer_id == cid))))
    return and_(base, or_(
        Document.uploaded_by == ctx.user.id,
        Document.customer_id.in_(select(Customer.id).where(customer_cond(db, ctx))),
        Document.project_id.in_(_my_project_ids(ctx)),
        Document.ticket_id.in_(select(Ticket.id).where(ticket_cond(db, ctx)))))


def false_():
    return Task.id.is_(None) & Task.id.is_not(None)
