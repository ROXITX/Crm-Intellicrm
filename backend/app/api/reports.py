from datetime import date, datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.registry import get_model
from app.core.audit import audit
from app.core.csvio import csv_response
from app.core.db import get_db
from app.core.deps import Ctx, require
from app.core.errors import forbidden
from app.core.scope import customer_cond, invoice_cond, project_cond, ticket_cond
from app.models import AIPrediction, Customer, Invoice, Lead, Payment, Project, Ticket
from app.services.workload import team_workload

router = APIRouter(prefix="/reports", tags=["reports"])
NAMES = Literal["lead_funnel", "conversion", "customer_health", "churn_risk", "project_performance", "support_performance",
                "revenue", "overdue_invoices", "workload", "ai_accuracy"]
NEEDS = {"lead_funnel": "leads.read", "conversion": "leads.read", "revenue": "invoices.read", "overdue_invoices": "invoices.read",
         "workload": "team.read", "ai_accuracy": "ai.read", "churn_risk": "ai.read", "customer_health": "customers.read",
         "project_performance": "projects.read", "support_performance": "tickets.read"}
STAGES = ["new", "contacted", "qualified", "proposal", "negotiation", "won", "lost"]


@router.get("/{name}")
def report(name: NAMES, date_from: date | None = None, date_to: date | None = None, format: Literal["json", "csv"] = "json",
           ctx: Ctx = Depends(require("reports.read")), db: Session = Depends(get_db)):
    if not ctx.can(NEEDS[name]):
        raise forbidden()
    df = date_from or (date.today() - timedelta(days=90))
    dt = date_to or date.today()
    cols, rows = [], []
    if name == "lead_funnel":
        counts = dict(db.execute(select(Lead.status, func.count()).where(Lead.organization_id == ctx.org_id, Lead.deleted_at.is_(None),
                                    func.date(Lead.created_at).between(df, dt)).group_by(Lead.status)).all())
        cols, rows = ["stage", "leads"], [[s, counts.get(s, 0)] for s in STAGES]
    elif name == "conversion":
        by = db.execute(select(Lead.source, func.count(), func.count().filter(Lead.status == "won")).where(
            Lead.organization_id == ctx.org_id, Lead.deleted_at.is_(None), func.date(Lead.created_at).between(df, dt)).group_by(Lead.source)).all()
        cols, rows = ["source", "leads", "won", "conversion_pct"], [[s or "unknown", n, w, round(w / n * 100, 1) if n else 0] for s, n, w in by]
    elif name == "customer_health":
        by = db.execute(select(Customer.health_status, func.count(), func.coalesce(func.sum(Customer.revenue), 0)).where(customer_cond(db, ctx)).group_by(Customer.health_status)).all()
        cols, rows = ["health", "customers", "revenue"], [[h or "unscored", n, str(r)] for h, n, r in by]
    elif name == "churn_risk":
        cids = select(Customer.id).where(customer_cond(db, ctx))
        sub = (select(AIPrediction.entity_id, func.max(AIPrediction.created_at).label("m")).where(
            AIPrediction.organization_id == ctx.org_id, AIPrediction.prediction_type == "customer_churn", AIPrediction.entity_id.in_(cids)).group_by(AIPrediction.entity_id).subquery())
        res = db.execute(select(Customer.name, AIPrediction.prediction_value, AIPrediction.risk_level, AIPrediction.model_version).join(
            AIPrediction, AIPrediction.entity_id == Customer.id).join(sub, (sub.c.entity_id == AIPrediction.entity_id) & (sub.c.m == AIPrediction.created_at)).where(
            AIPrediction.prediction_type == "customer_churn").order_by(AIPrediction.prediction_value.desc())).all()
        cols, rows = ["customer", "churn_probability", "risk_level", "model_version"], [[n, float(p), r, v] for n, p, r, v in res]
    elif name == "project_performance":
        res = db.execute(select(Project.name, Customer.name, Project.status, Project.progress, Project.due_date, Project.risk_level, Project.budget).join(
            Customer, Customer.id == Project.customer_id).where(project_cond(db, ctx)).order_by(Project.due_date)).all()
        cols, rows = ["project", "customer", "status", "progress", "due_date", "risk", "budget"], [[a, b, c, str(d), str(e), f, str(g)] for a, b, c, d, e, f, g in res]
    elif name == "support_performance":
        base = [ticket_cond(db, ctx), func.date(Ticket.created_at).between(df, dt)]
        total = db.scalar(select(func.count()).where(*base))
        resolved = db.scalar(select(func.count()).where(*base, Ticket.resolved_at.is_not(None)))
        avg_h = db.scalar(select(func.avg(func.extract("epoch", Ticket.resolved_at - Ticket.created_at) / 3600)).where(*base, Ticket.resolved_at.is_not(None)))
        breached = db.scalar(select(func.count()).where(*base, Ticket.resolved_at.is_not(None), Ticket.resolved_at > Ticket.sla_due_at))
        cols = ["metric", "value"]
        rows = [["tickets_created", total], ["tickets_resolved", resolved], ["avg_resolution_hours", round(float(avg_h or 0), 1)],
                ["sla_breaches_among_resolved", breached]]
    elif name == "revenue":
        b = func.date_trunc("month", Payment.paid_at)
        res = db.execute(select(b, func.sum(Payment.amount)).join(Invoice, Invoice.id == Payment.invoice_id).where(
            invoice_cond(db, ctx), Payment.status == "completed", func.date(Payment.paid_at).between(df, dt)).group_by(b).order_by(b)).all()
        cols, rows = ["month", "revenue"], [[m.date().isoformat(), str(v)] for m, v in res]
    elif name == "overdue_invoices":
        res = db.execute(select(Invoice.invoice_number, Customer.name, Invoice.due_date, Invoice.total - Invoice.amount_paid).join(Customer, Customer.id == Invoice.customer_id).where(
            invoice_cond(db, ctx), Invoice.status.in_(["sent", "partially_paid", "overdue"]), Invoice.due_date < date.today()).order_by(Invoice.due_date)).all()
        cols, rows = ["invoice", "customer", "due_date", "balance"], [[a, b, str(c), str(d)] for a, b, c, d in res]
    elif name == "workload":
        cols = ["name", "role", "active_tasks", "overdue_tasks", "capacity_pct", "status"]
        rows = [[m[c] for c in cols] for m in team_workload(db, ctx.org_id)]
    else:  # ai_accuracy
        cols = ["model", "version", "metric", "value"]
        for n in ("lead_conversion", "customer_churn", "project_delay", "ticket_sentiment", "ticket_priority"):
            _, meta = get_model(n)
            rows += [[n, meta["version"], k, v] for k, v in meta["metrics"].items() if isinstance(v, (int, float))]
        overridden = db.scalar(select(func.count()).where(ticket_cond(db, ctx), Ticket.predicted_priority.is_not(None), Ticket.priority != Ticket.predicted_priority))
        total_t = db.scalar(select(func.count()).where(ticket_cond(db, ctx), Ticket.predicted_priority.is_not(None)))
        rows.append(["ticket_priority", "live", "human_override_rate", round(overridden / total_t, 4) if total_t else 0])
    if format == "csv":
        audit(db, ctx, "report.export", meta={"report": name, "rows": len(rows)})
        return csv_response(f"{name}.csv", cols, rows)
    return {"report": name, "date_from": df.isoformat(), "date_to": dt.isoformat(), "columns": cols, "rows": rows}
