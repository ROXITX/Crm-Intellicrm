import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, File, Query, UploadFile
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.ai import service as ai
from app.core.audit import audit, snapshot
from app.core.csvio import csv_response, read_csv
from app.core.db import get_db
from app.core.deps import Ctx, require
from app.core.errors import bad_request, conflict
from app.core.util import Page, get_or_404, paginate, ser
from app.models import Customer, Lead, LeadInteraction, OrganizationMember, User

router = APIRouter(prefix="/leads", tags=["leads"])
Status = Literal["new", "contacted", "qualified", "proposal", "negotiation", "won", "lost"]
LEAD_COLS = ["name", "company_name", "email", "phone", "source", "status", "estimated_value"]


class LeadIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    company_name: str | None = Field(None, max_length=200)
    email: EmailStr | None = None
    phone: str | None = Field(None, max_length=50)
    source: str | None = Field(None, max_length=100)
    status: Status = "new"
    owner_id: uuid.UUID | None = None
    estimated_value: Decimal | None = Field(None, ge=0, max_digits=14, decimal_places=2)


class LeadPatch(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    company_name: str | None = Field(None, max_length=200)
    email: EmailStr | None = None
    phone: str | None = Field(None, max_length=50)
    source: str | None = Field(None, max_length=100)
    status: Status | None = None
    owner_id: uuid.UUID | None = None
    estimated_value: Decimal | None = Field(None, ge=0, max_digits=14, decimal_places=2)


class InteractionIn(BaseModel):
    type: Literal["email", "call", "meeting", "note", "proposal_requested", "pricing_page", "inquiry", "reply"]
    channel: str | None = Field(None, max_length=50)
    content: str | None = Field(None, max_length=5000)
    occurred_at: datetime | None = None


class ConvertIn(BaseModel):
    existing_customer_id: uuid.UUID | None = None


def _check_owner(db, ctx, owner_id):
    if owner_id and not db.scalar(select(OrganizationMember.id).where(
            OrganizationMember.organization_id == ctx.org_id, OrganizationMember.user_id == owner_id,
            OrganizationMember.status == "active")):
        raise bad_request("Owner is not a member of this organization", "INVALID_OWNER")


def _lead(db, ctx, lead_id) -> Lead:
    return get_or_404(db, select(Lead).where(Lead.id == lead_id, Lead.organization_id == ctx.org_id,
                                              Lead.deleted_at.is_(None)), "Lead")


def _filters(ctx, q, status, source, owner_id, min_score, max_score, date_from, date_to):
    c = [Lead.organization_id == ctx.org_id, Lead.deleted_at.is_(None)]
    if q:
        like = f"%{q}%"
        c.append(or_(Lead.name.ilike(like), Lead.company_name.ilike(like), Lead.email.ilike(like)))
    if status: c.append(Lead.status == status)
    if source: c.append(Lead.source == source)
    if owner_id: c.append(Lead.owner_id == owner_id)
    if min_score is not None: c.append(Lead.score >= min_score)
    if max_score is not None: c.append(Lead.score <= max_score)
    if date_from: c.append(func.date(Lead.created_at) >= date_from)
    if date_to: c.append(func.date(Lead.created_at) <= date_to)
    return c


def _last_contact():
    return (select(func.max(LeadInteraction.occurred_at)).where(LeadInteraction.lead_id == Lead.id)
            .correlate(Lead).scalar_subquery())


@router.get("")
def list_leads(q: str | None = None, status: Status | None = None, source: str | None = None,
               owner_id: uuid.UUID | None = None, min_score: float | None = None, max_score: float | None = None,
               date_from: date | None = None, date_to: date | None = None,
               sort: Literal["created_at", "score", "name", "estimated_value"] = "created_at",
               order: Literal["asc", "desc"] = "desc",
               p: Page = Depends(), ctx: Ctx = Depends(require("leads.read")), db: Session = Depends(get_db)):
    col = getattr(Lead, sort)
    stmt = (select(Lead, User.first_name, _last_contact().label("last_contact"))
            .outerjoin(User, User.id == Lead.owner_id)
            .where(*_filters(ctx, q, status, source, owner_id, min_score, max_score, date_from, date_to))
            .order_by(col.asc().nulls_last() if order == "asc" else col.desc().nulls_last(), Lead.id))
    return paginate(db, stmt, p, lambda r: ser(r[0], extra={"owner_name": r[1],
                                                               "last_contact_at": r[2].isoformat() if r[2] else None}))


@router.post("", status_code=201)
def create_lead(body: LeadIn, ctx: Ctx = Depends(require("leads.write")), db: Session = Depends(get_db)):
    _check_owner(db, ctx, body.owner_id)
    lead = Lead(organization_id=ctx.org_id, **{**body.model_dump(), "owner_id": body.owner_id or ctx.user.id})
    db.add(lead)
    db.flush()
    ai.score_lead(db, lead)
    audit(db, ctx, "lead.create", "lead", lead.id, after=snapshot(lead))
    return ser(lead)


@router.get("/export")
def export_leads(ctx: Ctx = Depends(require("leads.read")), db: Session = Depends(get_db)):
    rows = db.scalars(select(Lead).where(Lead.organization_id == ctx.org_id, Lead.deleted_at.is_(None))
                      .order_by(Lead.created_at)).all()
    audit(db, ctx, "lead.export", "lead", meta={"count": len(rows)})
    return csv_response("leads.csv", LEAD_COLS + ["score"],
                        [[getattr(r, c) for c in LEAD_COLS] + [r.score] for r in rows])


@router.post("/import")
async def import_leads(file: UploadFile = File(...), confirm: bool = Query(False),
                       ctx: Ctx = Depends(require("leads.write")), db: Session = Depends(get_db)):
    """Validate a CSV and return a preview + errors. Nothing is stored until confirm=true."""
    rows = await read_csv(file, {"name"}, set(LEAD_COLS))
    valid, errors = [], []
    for i, r in enumerate(rows, start=2):
        try:
            data = LeadIn(name=r.get("name", ""), company_name=r.get("company_name") or None,
                          email=r.get("email") or None, phone=r.get("phone") or None, source=r.get("source") or None,
                          status=(r.get("status") or "new").lower(),
                          estimated_value=Decimal(r["estimated_value"]) if r.get("estimated_value") else None)
            valid.append(data)
        except Exception as e:  # pydantic ValidationError / decimal
            errors.append({"row": i, "message": str(e).splitlines()[0][:200] if not hasattr(e, "errors") else
                           "; ".join(f"{'.'.join(map(str, x['loc']))}: {x['msg']}" for x in e.errors())})
    if confirm:
        if errors:
            raise bad_request("Fix the CSV errors before importing", "INVALID_CSV")
        for d in valid:
            lead = Lead(organization_id=ctx.org_id, **{**d.model_dump(), "owner_id": ctx.user.id})
            db.add(lead)
            db.flush()
            ai.score_lead(db, lead)
        audit(db, ctx, "lead.import", "lead", meta={"count": len(valid)})
    return {"valid_rows": len(valid), "errors": errors, "imported": len(valid) if confirm else 0,
            "preview": [v.model_dump(mode="json") for v in valid[:10]]}


@router.get("/{lead_id}")
def lead_360(lead_id: uuid.UUID, ctx: Ctx = Depends(require("leads.read")), db: Session = Depends(get_db)):
    lead = _lead(db, ctx, lead_id)
    inter = db.scalars(select(LeadInteraction).where(LeadInteraction.lead_id == lead.id,
                                                      LeadInteraction.organization_id == ctx.org_id)
                       .order_by(LeadInteraction.occurred_at.desc())).all()
    return {**ser(lead), "interactions": [ser(i) for i in inter],
            "score_explanation": ai.latest_prediction(db, ctx.org_id, "lead", lead.id, "lead_conversion")}


@router.patch("/{lead_id}")
def update_lead(lead_id: uuid.UUID, body: LeadPatch, ctx: Ctx = Depends(require("leads.write")),
                db: Session = Depends(get_db)):
    lead = _lead(db, ctx, lead_id)
    data = body.model_dump(exclude_unset=True)
    if "owner_id" in data:
        _check_owner(db, ctx, data["owner_id"])
    if data.get("name") is None and "name" in data:
        raise bad_request("name cannot be empty")
    before = snapshot(lead)
    for k, v in data.items():
        setattr(lead, k, v)
    db.flush()
    ai.score_lead(db, lead)
    audit(db, ctx, "lead.update", "lead", lead.id, before, snapshot(lead))
    return ser(lead)


@router.delete("/{lead_id}", status_code=204)
def archive_lead(lead_id: uuid.UUID, ctx: Ctx = Depends(require("leads.write")), db: Session = Depends(get_db)):
    lead = _lead(db, ctx, lead_id)
    lead.deleted_at = datetime.now(timezone.utc)
    audit(db, ctx, "lead.archive", "lead", lead.id, before=snapshot(lead))


@router.post("/{lead_id}/interactions", status_code=201)
def add_interaction(lead_id: uuid.UUID, body: InteractionIn, ctx: Ctx = Depends(require("leads.write")),
                    db: Session = Depends(get_db)):
    lead = _lead(db, ctx, lead_id)
    i = LeadInteraction(organization_id=ctx.org_id, lead_id=lead.id, type=body.type, channel=body.channel,
                        content=body.content, occurred_at=body.occurred_at or datetime.now(timezone.utc),
                        created_by=ctx.user.id)
    db.add(i)
    db.flush()
    ai.score_lead(db, lead)
    return ser(i)


@router.post("/{lead_id}/score")
def rescore(lead_id: uuid.UUID, ctx: Ctx = Depends(require("leads.write", "ai.read")), db: Session = Depends(get_db)):
    lead = _lead(db, ctx, lead_id)
    pred = ai.score_lead(db, lead)
    audit(db, ctx, "ai.lead_score", "lead", lead.id)
    return pred


@router.post("/{lead_id}/convert", status_code=201)
def convert_lead(lead_id: uuid.UUID, body: ConvertIn | None = None, ctx: Ctx = Depends(require("leads.write", "customers.write")),
                 db: Session = Depends(get_db)):
    """Atomic conversion: create/link customer, mark lead won, keep lead + interactions as history."""
    lead = _lead(db, ctx, lead_id)
    if lead.converted_customer_id:
        raise conflict("Lead has already been converted", "ALREADY_CONVERTED")
    before = snapshot(lead)
    if body and body.existing_customer_id:
        cust = get_or_404(db, select(Customer).where(Customer.id == body.existing_customer_id,
                                                      Customer.organization_id == ctx.org_id,
                                                      Customer.deleted_at.is_(None)), "Customer")
    else:
        cust = Customer(organization_id=ctx.org_id, name=lead.name, company_name=lead.company_name, email=lead.email,
                        phone=lead.phone, account_owner_id=lead.owner_id or ctx.user.id, source_lead_id=lead.id,
                        tags=f"source:{lead.source}" if lead.source else None, health_status="healthy",
                        health_score=Decimal("75"), last_interaction_at=db.scalar(
                            select(func.max(LeadInteraction.occurred_at)).where(LeadInteraction.lead_id == lead.id)))
        db.add(cust)
        db.flush()
    lead.converted_customer_id = cust.id
    lead.status = "won"
    audit(db, ctx, "lead.convert", "lead", lead.id, before, snapshot(lead), {"customer_id": str(cust.id)})
    return {"lead": ser(lead), "customer": ser(cust)}
