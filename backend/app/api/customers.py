import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, File, Query, UploadFile
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.ai import service as ai
from app.core.audit import audit, snapshot
from app.core.csvio import csv_response, read_csv
from app.core.db import get_db
from app.core.deps import Ctx, require
from app.core.errors import bad_request, conflict
from app.core.scope import customer_cond
from app.core.security import hash_password
from app.core.util import Page, get_or_404, paginate, ser
from app.models import (AuditLog, Customer, CustomerContact, Invoice, OrganizationMember, Project, Role, Ticket, User)

router = APIRouter(prefix="/customers", tags=["customers"])
INTERNAL_ONLY = {"health_score", "health_status", "notes", "tags", "account_owner_id", "source_lead_id"}
Health = Literal["healthy", "watch", "at_risk", "critical"]
CSV_COLS = ["name", "company_name", "email", "phone", "industry"]


class CustomerIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    company_name: str | None = Field(None, max_length=200)
    email: EmailStr | None = None
    phone: str | None = Field(None, max_length=50)
    industry: str | None = Field(None, max_length=100)
    account_owner_id: uuid.UUID | None = None
    tags: str | None = Field(None, max_length=500)
    notes: str | None = Field(None, max_length=5000)


class CustomerPatch(CustomerIn):
    name: str | None = Field(None, min_length=1, max_length=200)


class ContactIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr | None = None
    phone: str | None = Field(None, max_length=50)
    job_title: str | None = Field(None, max_length=100)
    is_primary: bool = False


class PortalUserIn(BaseModel):
    email: EmailStr
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str | None = None
    password: str = Field(min_length=10, max_length=200)


def get_customer(db, ctx, cid) -> Customer:
    return get_or_404(db, select(Customer).where(Customer.id == cid, customer_cond(db, ctx)), "Customer")


def _out(c: Customer, ctx: Ctx, extra=None):
    return ser(c, INTERNAL_ONLY if ctx.is_client else frozenset(), extra)


@router.get("")
def list_customers(q: str | None = None, health: Health | None = None, owner_id: uuid.UUID | None = None,
                   industry: str | None = None, min_revenue: Decimal | None = None,
                   sort: Literal["created_at", "name", "revenue", "health_score", "last_interaction_at"] = "created_at",
                   order: Literal["asc", "desc"] = "desc", p: Page = Depends(),
                   ctx: Ctx = Depends(require("customers.read")), db: Session = Depends(get_db)):
    projects = (select(func.count(Project.id)).where(Project.customer_id == Customer.id, Project.deleted_at.is_(None))
                .correlate(Customer).scalar_subquery())
    open_t = (select(func.count(Ticket.id)).where(Ticket.customer_id == Customer.id, Ticket.deleted_at.is_(None),
                                                    Ticket.status.notin_(["resolved", "closed"]))
              .correlate(Customer).scalar_subquery())
    conds = [customer_cond(db, ctx)]
    if q:
        like = f"%{q}%"
        conds.append(or_(Customer.name.ilike(like), Customer.company_name.ilike(like), Customer.email.ilike(like)))
    if health and not ctx.is_client: conds.append(Customer.health_status == health)
    if owner_id: conds.append(Customer.account_owner_id == owner_id)
    if industry: conds.append(Customer.industry == industry)
    if min_revenue is not None: conds.append(Customer.revenue >= min_revenue)
    col = getattr(Customer, sort)
    stmt = (select(Customer, projects, open_t, User.first_name).outerjoin(User, User.id == Customer.account_owner_id)
            .where(*conds).order_by(col.asc().nulls_last() if order == "asc" else col.desc().nulls_last(), Customer.id))
    return paginate(db, stmt, p, lambda r: _out(r[0], ctx, {"project_count": r[1], "open_tickets": r[2],
                                                            "owner_name": None if ctx.is_client else r[3]}))


@router.post("", status_code=201)
def create_customer(body: CustomerIn, ctx: Ctx = Depends(require("customers.write")), db: Session = Depends(get_db)):
    if ctx.is_client:
        raise bad_request("Not allowed")
    c = Customer(organization_id=ctx.org_id, **{**body.model_dump(), "account_owner_id": body.account_owner_id or ctx.user.id},
                 health_status="healthy", health_score=Decimal("75"))
    db.add(c)
    db.flush()
    audit(db, ctx, "customer.create", "customer", c.id, after=snapshot(c))
    return ser(c)


@router.get("/export")
def export_customers(ctx: Ctx = Depends(require("customers.read")), db: Session = Depends(get_db)):
    if ctx.is_client:
        raise bad_request("Not allowed")
    rows = db.scalars(select(Customer).where(customer_cond(db, ctx)).order_by(Customer.created_at)).all()
    audit(db, ctx, "customer.export", "customer", meta={"count": len(rows)})
    return csv_response("customers.csv", CSV_COLS + ["revenue", "health_status"],
                        [[getattr(r, c) for c in CSV_COLS] + [r.revenue, r.health_status] for r in rows])


@router.post("/import")
async def import_customers(file: UploadFile = File(...), confirm: bool = Query(False),
                           ctx: Ctx = Depends(require("customers.write")), db: Session = Depends(get_db)):
    rows = await read_csv(file, {"name"}, set(CSV_COLS))
    valid, errors = [], []
    for i, r in enumerate(rows, start=2):
        try:
            valid.append(CustomerIn(**{k: (r.get(k) or None) for k in CSV_COLS}))
        except Exception as e:
            errors.append({"row": i, "message": "; ".join(f"{'.'.join(map(str, x['loc']))}: {x['msg']}" for x in e.errors())})
    if confirm:
        if errors:
            raise bad_request("Fix the CSV errors before importing", "INVALID_CSV")
        for d in valid:
            db.add(Customer(organization_id=ctx.org_id, account_owner_id=ctx.user.id, health_status="healthy",
                            health_score=Decimal("75"), **d.model_dump(exclude={"account_owner_id"})))
        audit(db, ctx, "customer.import", "customer", meta={"count": len(valid)})
    return {"valid_rows": len(valid), "errors": errors, "imported": len(valid) if confirm else 0,
            "preview": [v.model_dump(mode="json") for v in valid[:10]]}


@router.get("/{customer_id}")
def customer_360(customer_id: uuid.UUID, ctx: Ctx = Depends(require("customers.read")), db: Session = Depends(get_db)):
    c = get_customer(db, ctx, customer_id)
    open_t = db.scalar(select(func.count(Ticket.id)).where(Ticket.customer_id == c.id, Ticket.deleted_at.is_(None),
                                                            Ticket.status.notin_(["resolved", "closed"])))
    active_p = db.scalar(select(func.count(Project.id)).where(Project.customer_id == c.id, Project.deleted_at.is_(None),
                                                               Project.status.in_(["planning", "active", "at_risk", "delayed"])))
    outstanding = db.scalar(select(func.coalesce(func.sum(Invoice.total - Invoice.amount_paid), 0)).where(
        Invoice.customer_id == c.id, Invoice.status.in_(["sent", "partially_paid", "overdue"])))
    contacts = db.scalars(select(CustomerContact).where(CustomerContact.customer_id == c.id,
                                                         CustomerContact.organization_id == ctx.org_id)).all()
    owner = db.get(User, c.account_owner_id) if c.account_owner_id and not ctx.is_client else None
    out = _out(c, ctx, {"open_tickets": open_t, "active_projects": active_p, "outstanding_amount": str(outstanding),
                        "contacts": [ser(x, {"user_id"}) for x in contacts],
                        "owner_name": owner.first_name if owner else None})
    if not ctx.is_client and ctx.can("ai.read"):
        out["ai"] = {"churn": ai.latest_prediction(db, ctx.org_id, "customer", c.id, "customer_churn"),
                     "sentiment_trend": ai.sentiment_trend(db, ctx.org_id, c.id)}
    return out


@router.patch("/{customer_id}")
def update_customer(customer_id: uuid.UUID, body: CustomerPatch, ctx: Ctx = Depends(require("customers.write")),
                    db: Session = Depends(get_db)):
    c = get_customer(db, ctx, customer_id)
    data = body.model_dump(exclude_unset=True)
    if "name" in data and data["name"] is None:
        raise bad_request("name cannot be empty")
    if data.get("account_owner_id"):
        if not db.scalar(select(OrganizationMember.id).where(OrganizationMember.organization_id == ctx.org_id,
                                                               OrganizationMember.user_id == data["account_owner_id"])):
            raise bad_request("Owner is not a member of this organization", "INVALID_OWNER")
    before = snapshot(c)
    for k, v in data.items():
        setattr(c, k, v)
    audit(db, ctx, "customer.update", "customer", c.id, before, snapshot(c))
    return ser(c)


@router.delete("/{customer_id}", status_code=204)
def archive_customer(customer_id: uuid.UUID, ctx: Ctx = Depends(require("customers.write")), db: Session = Depends(get_db)):
    c = get_customer(db, ctx, customer_id)
    c.deleted_at = datetime.now(timezone.utc)
    audit(db, ctx, "customer.archive", "customer", c.id, before=snapshot(c))


@router.post("/{customer_id}/contacts", status_code=201)
def add_contact(customer_id: uuid.UUID, body: ContactIn, ctx: Ctx = Depends(require("customers.write")),
                db: Session = Depends(get_db)):
    c = get_customer(db, ctx, customer_id)
    if body.is_primary:
        for x in db.scalars(select(CustomerContact).where(CustomerContact.customer_id == c.id)):
            x.is_primary = False
    ct = CustomerContact(organization_id=ctx.org_id, customer_id=c.id, **body.model_dump())
    db.add(ct)
    db.flush()
    return ser(ct, {"user_id"})


@router.post("/{customer_id}/portal-users", status_code=201)
def create_portal_user(customer_id: uuid.UUID, body: PortalUserIn, ctx: Ctx = Depends(require("customers.write", "team.manage")),
                       db: Session = Depends(get_db)):
    """Give a customer contact a client-portal login (role: client)."""
    c = get_customer(db, ctx, customer_id)
    email = body.email.lower()
    if db.scalar(select(User.id).where(User.email == email)):
        raise conflict("An account with this email already exists", "EMAIL_TAKEN")
    role = db.scalar(select(Role).where(Role.name == "client", Role.is_system_role.is_(True)))
    u = User(email=email, password_hash=hash_password(body.password), first_name=body.first_name, last_name=body.last_name)
    db.add(u)
    db.flush()
    db.add(OrganizationMember(organization_id=ctx.org_id, user_id=u.id, role_id=role.id))
    db.add(CustomerContact(organization_id=ctx.org_id, customer_id=c.id, user_id=u.id,
                           name=f"{body.first_name} {body.last_name or ''}".strip(), email=email))
    audit(db, ctx, "portal_user.create", "customer", c.id, meta={"user_id": str(u.id)})
    return {"user_id": str(u.id), "email": email}


@router.get("/{customer_id}/activity")
def customer_activity(customer_id: uuid.UUID, ctx: Ctx = Depends(require("customers.read", "internal.view")),
                      db: Session = Depends(get_db)):
    c = get_customer(db, ctx, customer_id)
    logs = db.scalars(select(AuditLog).where(AuditLog.organization_id == ctx.org_id, AuditLog.entity_type == "customer",
                                             AuditLog.entity_id == c.id).order_by(AuditLog.created_at.desc()).limit(100))
    return [{"id": str(l.id), "action": l.action, "actor_id": str(l.actor_id) if l.actor_id else None,
             "created_at": l.created_at.isoformat()} for l in logs]
