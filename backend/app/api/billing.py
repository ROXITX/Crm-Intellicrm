import io
import uuid
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.audit import audit, notify, snapshot
from app.core.config import settings
from app.core.db import get_db
from app.core.deps import Ctx, require
from app.core.errors import bad_request, conflict
from app.core.scope import customer_cond, invoice_cond
from app.core.util import Page, get_or_404, money, paginate, ser
from app.models import Customer, Invoice, InvoiceItem, Payment

router = APIRouter(tags=["billing"])
Q = Decimal("0.01")


class ItemIn(BaseModel):
    description: str = Field(min_length=1, max_length=300)
    quantity: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    unit_price: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    tax_rate: Decimal = Field(0, ge=0, le=100, max_digits=5, decimal_places=2)


class InvoiceIn(BaseModel):
    customer_id: uuid.UUID
    issue_date: date | None = None
    due_date: date
    discount: Decimal = Field(0, ge=0, max_digits=14, decimal_places=2)
    currency: str = Field("INR", min_length=3, max_length=3)
    items: list[ItemIn] = Field(min_length=1, max_length=200)
    # NOTE: no subtotal/tax/total fields - totals are always computed server-side.


class InvoicePatch(BaseModel):
    due_date: date | None = None
    discount: Decimal | None = Field(None, ge=0, max_digits=14, decimal_places=2)
    items: list[ItemIn] | None = Field(None, min_length=1, max_length=200)


class PaymentIn(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    method: Literal["bank_transfer", "upi", "card", "cash", "cheque", "other"] = "bank_transfer"
    transaction_reference: str | None = Field(None, max_length=200)
    paid_at: datetime | None = None
    # Never accept card numbers / CVV: only a processor reference.


def compute_totals(items: list[ItemIn], discount: Decimal):
    lines, subtotal, tax = [], Decimal(0), Decimal(0)
    for it in items:
        net = (it.quantity * it.unit_price).quantize(Q, ROUND_HALF_UP)
        line_tax = (net * it.tax_rate / 100).quantize(Q, ROUND_HALF_UP)
        lines.append((it, (net + line_tax).quantize(Q)))
        subtotal += net
        tax += line_tax
    total = subtotal + tax - discount
    if total < 0:
        raise bad_request("Discount cannot exceed the invoice amount", "INVALID_DISCOUNT")
    return lines, subtotal.quantize(Q), tax.quantize(Q), total.quantize(Q)


def _number(db, org_id) -> str:
    year = date.today().year
    n = db.scalar(select(func.count()).select_from(Invoice).where(Invoice.organization_id == org_id)) + 1
    num = f"INV-{year}-{n:05d}"
    while db.scalar(select(Invoice.id).where(Invoice.organization_id == org_id, Invoice.invoice_number == num)):
        n += 1
        num = f"INV-{year}-{n:05d}"
    return num


def get_invoice(db, ctx, iid, lock=False) -> Invoice:
    stmt = select(Invoice).where(Invoice.id == iid, invoice_cond(db, ctx))
    return get_or_404(db, stmt.with_for_update() if lock else stmt, "Invoice")


def _items(db, inv):
    return db.scalars(select(InvoiceItem).where(InvoiceItem.invoice_id == inv.id).order_by(InvoiceItem.position)).all()


def effective_status(inv: Invoice) -> str:
    if inv.status in ("sent", "partially_paid") and inv.due_date < date.today():
        return "overdue"
    return inv.status


def refresh_overdue(db: Session, org_id):
    """Mark past-due sent/partially paid invoices as overdue (also run by the scheduled worker)."""
    for inv in db.scalars(select(Invoice).where(Invoice.organization_id == org_id, Invoice.status.in_(["sent", "partially_paid"]),
                                                  Invoice.due_date < date.today())):
        inv.status = "overdue"


@router.get("/invoices")
def list_invoices(status: str | None = None, customer_id: uuid.UUID | None = None, q: str | None = None,
                  p: Page = Depends(), ctx: Ctx = Depends(require("invoices.read")), db: Session = Depends(get_db)):
    refresh_overdue(db, ctx.org_id)
    conds = [invoice_cond(db, ctx)]
    if status: conds.append(Invoice.status == status)
    if customer_id: conds.append(Invoice.customer_id == customer_id)
    if q: conds.append(Invoice.invoice_number.ilike(f"%{q}%"))
    stmt = (select(Invoice, Customer.name).join(Customer, Customer.id == Invoice.customer_id).where(*conds)
            .order_by(Invoice.issue_date.desc(), Invoice.invoice_number.desc()))
    return paginate(db, stmt, p, lambda r: ser(r[0], extra={"customer_name": r[1], "balance": str(r[0].total - r[0].amount_paid)}))


@router.get("/invoices/summary")
def invoice_summary(ctx: Ctx = Depends(require("invoices.read")), db: Session = Depends(get_db)):
    refresh_overdue(db, ctx.org_id)
    base = [invoice_cond(db, ctx)]
    outstanding = db.scalar(select(func.coalesce(func.sum(Invoice.total - Invoice.amount_paid), 0)).where(
        *base, Invoice.status.in_(["sent", "partially_paid", "overdue"])))
    overdue = db.scalar(select(func.coalesce(func.sum(Invoice.total - Invoice.amount_paid), 0)).where(*base, Invoice.status == "overdue"))
    month_start = date.today().replace(day=1)
    paid_month = db.scalar(select(func.coalesce(func.sum(Payment.amount), 0)).join(Invoice, Invoice.id == Payment.invoice_id).where(
        *base, Payment.status == "completed", Payment.paid_at >= month_start))
    revenue = db.scalar(select(func.coalesce(func.sum(Payment.amount), 0)).join(Invoice, Invoice.id == Payment.invoice_id).where(
        *base, Payment.status == "completed"))
    return {"outstanding": str(outstanding), "overdue": str(overdue), "paid_this_month": str(paid_month), "revenue": str(revenue)}


@router.post("/invoices", status_code=201)
def create_invoice(body: InvoiceIn, ctx: Ctx = Depends(require("invoices.write")), db: Session = Depends(get_db)):
    get_or_404(db, select(Customer).where(Customer.id == body.customer_id, customer_cond(db, ctx)), "Customer")
    issue = body.issue_date or date.today()
    if body.due_date < issue:
        raise bad_request("due_date must not be before issue_date", "VALIDATION_ERROR")
    lines, subtotal, tax, total = compute_totals(body.items, body.discount)
    inv = Invoice(organization_id=ctx.org_id, customer_id=body.customer_id, invoice_number=_number(db, ctx.org_id),
                  status="draft", issue_date=issue, due_date=body.due_date, subtotal=subtotal, tax=tax,
                  discount=body.discount, total=total, currency=body.currency.upper())
    db.add(inv)
    db.flush()
    for pos, (it, line_total) in enumerate(lines):
        db.add(InvoiceItem(invoice_id=inv.id, description=it.description, quantity=it.quantity, unit_price=it.unit_price,
                           tax_rate=it.tax_rate, line_total=line_total, position=pos))
    db.flush()
    audit(db, ctx, "invoice.create", "invoice", inv.id, after=snapshot(inv))
    return ser(inv, extra={"items": [ser(i) for i in _items(db, inv)]})


@router.get("/invoices/{invoice_id}")
def invoice_detail(invoice_id: uuid.UUID, ctx: Ctx = Depends(require("invoices.read")), db: Session = Depends(get_db)):
    inv = get_invoice(db, ctx, invoice_id)
    pays = db.scalars(select(Payment).where(Payment.invoice_id == inv.id, Payment.organization_id == ctx.org_id)
                      .order_by(Payment.created_at)).all()
    cust = db.get(Customer, inv.customer_id)
    return ser(inv, extra={"status": effective_status(inv), "customer_name": cust.name, "balance": str(inv.total - inv.amount_paid),
                           "items": [ser(i) for i in _items(db, inv)], "payments": [ser(p) for p in pays]})


@router.patch("/invoices/{invoice_id}")
def edit_invoice(invoice_id: uuid.UUID, body: InvoicePatch, ctx: Ctx = Depends(require("invoices.write")), db: Session = Depends(get_db)):
    inv = get_invoice(db, ctx, invoice_id, lock=True)
    if inv.status != "draft":
        raise conflict("Only draft invoices can be edited", "INVOICE_NOT_DRAFT")
    before = snapshot(inv)
    if body.due_date:
        if body.due_date < inv.issue_date:
            raise bad_request("due_date must not be before issue_date", "VALIDATION_ERROR")
        inv.due_date = body.due_date
    if body.discount is not None:
        inv.discount = body.discount
    if body.items is not None or body.discount is not None:
        items = body.items
        if items is None:
            items = [ItemIn(description=i.description, quantity=i.quantity, unit_price=i.unit_price, tax_rate=i.tax_rate)
                     for i in _items(db, inv)]
        lines, inv.subtotal, inv.tax, inv.total = compute_totals(items, inv.discount)
        if body.items is not None:
            for old in _items(db, inv):
                db.delete(old)
            db.flush()
            for pos, (it, lt) in enumerate(lines):
                db.add(InvoiceItem(invoice_id=inv.id, description=it.description, quantity=it.quantity, unit_price=it.unit_price,
                                   tax_rate=it.tax_rate, line_total=lt, position=pos))
    audit(db, ctx, "invoice.update", "invoice", inv.id, before, snapshot(inv))
    return ser(inv)


def _transition(db, ctx, invoice_id, allowed_from, new_status, action):
    inv = get_invoice(db, ctx, invoice_id, lock=True)
    if inv.status not in allowed_from:
        raise conflict(f"Cannot {action} an invoice that is {inv.status}", "INVALID_STATE")
    before = inv.status
    inv.status = new_status
    audit(db, ctx, f"invoice.{action}", "invoice", inv.id, {"status": before}, {"status": new_status})
    return inv


@router.post("/invoices/{invoice_id}/issue")
def issue_invoice(invoice_id: uuid.UUID, ctx: Ctx = Depends(require("invoices.write")), db: Session = Depends(get_db)):
    inv = _transition(db, ctx, invoice_id, {"draft"}, "sent", "issue")
    cust = db.get(Customer, inv.customer_id)
    from app.models import CustomerContact
    for uid in db.scalars(select(CustomerContact.user_id).where(CustomerContact.customer_id == cust.id, CustomerContact.user_id.is_not(None))):
        notify(db, ctx.org_id, uid, "invoice", "New invoice", f"{inv.invoice_number} - due {inv.due_date}", "invoice", inv.id)
    return ser(inv)


@router.post("/invoices/{invoice_id}/cancel")
def cancel_invoice(invoice_id: uuid.UUID, ctx: Ctx = Depends(require("invoices.write")), db: Session = Depends(get_db)):
    inv = get_invoice(db, ctx, invoice_id, lock=True)
    if inv.amount_paid > 0 or inv.status in ("paid", "cancelled"):
        raise conflict("Invoices with payments or already closed cannot be cancelled", "INVALID_STATE")
    inv.status = "cancelled"
    audit(db, ctx, "invoice.cancel", "invoice", inv.id)
    return ser(inv)


@router.post("/invoices/{invoice_id}/payments", status_code=201)
def record_payment(invoice_id: uuid.UUID, body: PaymentIn, ctx: Ctx = Depends(require("payments.write")), db: Session = Depends(get_db)):
    """Row-locks the invoice so concurrent payments cannot overpay; whole operation is one transaction."""
    inv = get_invoice(db, ctx, invoice_id, lock=True)
    if inv.status in ("draft", "cancelled", "paid"):
        raise conflict(f"Cannot record a payment on a {inv.status} invoice", "INVALID_STATE")
    balance = inv.total - inv.amount_paid
    if body.amount > balance:
        raise bad_request(f"Payment exceeds outstanding balance of {balance}", "OVERPAYMENT")
    pay = Payment(organization_id=ctx.org_id, invoice_id=inv.id, amount=body.amount, method=body.method, status="completed",
                  transaction_reference=body.transaction_reference, paid_at=body.paid_at or datetime.now(timezone.utc))
    db.add(pay)
    before = snapshot(inv, ["status", "amount_paid"])
    inv.amount_paid = money(inv.amount_paid + body.amount)
    inv.status = "paid" if inv.amount_paid == inv.total else "partially_paid"
    cust = db.get(Customer, inv.customer_id)
    cust.revenue = money(cust.revenue + body.amount)
    db.flush()
    audit(db, ctx, "payment.record", "invoice", inv.id, before, snapshot(inv, ["status", "amount_paid"]), {"payment_id": str(pay.id)})
    notify(db, ctx.org_id, cust.account_owner_id, "payment", "Payment received", f"{inv.invoice_number}: {body.amount}", "invoice", inv.id)
    return ser(pay)


@router.get("/payments")
def list_payments(p: Page = Depends(), ctx: Ctx = Depends(require("invoices.read")), db: Session = Depends(get_db)):
    stmt = (select(Payment, Invoice.invoice_number, Customer.name).join(Invoice, Invoice.id == Payment.invoice_id)
            .join(Customer, Customer.id == Invoice.customer_id).where(invoice_cond(db, ctx), Payment.organization_id == ctx.org_id)
            .order_by(Payment.paid_at.desc().nulls_last(), Payment.id))
    return paginate(db, stmt, p, lambda r: ser(r[0], extra={"invoice_number": r[1], "customer_name": r[2]}))


@router.get("/invoices/{invoice_id}/pdf")
def invoice_pdf(invoice_id: uuid.UUID, ctx: Ctx = Depends(require("invoices.read")), db: Session = Depends(get_db)):
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    inv = get_invoice(db, ctx, invoice_id)
    cust = db.get(Customer, inv.customer_id)
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    y = h - 60
    c.setFont("Helvetica-Bold", 18); c.drawString(50, y, f"Invoice {inv.invoice_number}")
    c.setFont("Helvetica", 10); y -= 22
    c.drawString(50, y, f"Billed to: {cust.name}" + (f" ({cust.company_name})" if cust.company_name else ""))
    y -= 14; c.drawString(50, y, f"Issued: {inv.issue_date}   Due: {inv.due_date}   Status: {effective_status(inv)}")
    y -= 30; c.setFont("Helvetica-Bold", 10)
    for x, t in ((50, "Description"), (300, "Qty"), (350, "Unit price"), (430, "Tax %"), (490, "Total")):
        c.drawString(x, y, t)
    c.setFont("Helvetica", 10)
    for it in _items(db, inv):
        y -= 16
        c.drawString(50, y, it.description[:45]); c.drawString(300, y, str(it.quantity)); c.drawString(350, y, str(it.unit_price))
        c.drawString(430, y, str(it.tax_rate)); c.drawString(490, y, str(it.line_total))
    y -= 30
    for label, v in (("Subtotal", inv.subtotal), ("Tax", inv.tax), ("Discount", -inv.discount), ("Total", inv.total),
                     ("Paid", inv.amount_paid), ("Balance due", inv.total - inv.amount_paid)):
        c.drawString(380, y, label); c.drawRightString(550, y, f"{inv.currency} {v}"); y -= 14
    c.showPage(); c.save()
    audit(db, ctx, "invoice.pdf", "invoice", inv.id)
    return Response(buf.getvalue(), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{inv.invoice_number}.pdf"'})
