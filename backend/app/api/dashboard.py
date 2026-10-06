from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import Ctx, require
from app.core.scope import customer_cond, invoice_cond, project_cond, task_cond, ticket_cond
from app.models import (AIRecommendation, AuditLog, Customer, Invoice, Lead, Payment, Project, Task, Ticket, User)
from app.services.workload import team_workload

router = APIRouter(tags=["dashboard"])
RANGES = {"7D": (7, "day"), "30D": (30, "day"), "90D": (90, "week"), "12M": (365, "month")}
FUNNEL = ["new", "contacted", "qualified", "proposal", "won"]
ACTIONS = {"lead.create": "created lead", "lead.convert": "converted lead", "customer.create": "created customer",
           "ticket.create": "opened ticket", "payment.record": "recorded payment", "task.update": "updated task",
           "task.create": "created task", "project.create": "created project", "project.update": "updated project",
           "invoice.create": "created invoice", "invoice.issue": "issued invoice", "document.upload": "uploaded document"}


def _pct(cur, prev):
    if not prev:
        return None
    return round((float(cur) - float(prev)) / float(prev) * 100, 1)


def _revenue_series(db, ctx, days, bucket):
    since = datetime.now(timezone.utc) - timedelta(days=days)
    b = func.date_trunc(bucket, Payment.paid_at)
    rev = dict(db.execute(select(b, func.sum(Payment.amount)).join(Invoice, Invoice.id == Payment.invoice_id).where(
        invoice_cond(db, ctx), Payment.status == "completed", Payment.paid_at >= since).group_by(b)).all())
    lb = func.date_trunc(bucket, Lead.created_at)
    pipe = dict(db.execute(select(lb, func.sum(Lead.estimated_value)).where(
        Lead.organization_id == ctx.org_id, Lead.deleted_at.is_(None), Lead.status.notin_(["won", "lost"]),
        Lead.created_at >= since).group_by(lb)).all()) if ctx.can("leads.read") else {}
    keys = sorted({*rev, *pipe})
    return [{"period": k.date().isoformat(), "revenue": float(rev.get(k, 0)), "pipeline": float(pipe.get(k, 0))} for k in keys]


@router.get("/dashboard")
def dashboard(range: Literal["7D", "30D", "90D", "12M"] = "30D", ctx: Ctx = Depends(require("customers.read")),
              db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    d30, d60 = now - timedelta(days=30), now - timedelta(days=60)
    cust = customer_cond(db, ctx)
    kpis = {}
    total = db.scalar(select(func.count()).select_from(Customer).where(cust))
    new_c = db.scalar(select(func.count()).select_from(Customer).where(cust, Customer.created_at >= d30))
    prev_c = db.scalar(select(func.count()).select_from(Customer).where(cust, Customer.created_at >= d60, Customer.created_at < d30))
    kpis["total_customers"] = {"value": total, "trend_pct": _pct(new_c, prev_c), "new_this_month": new_c}
    if ctx.can("leads.read"):
        nl = db.scalar(select(func.count()).select_from(Lead).where(Lead.organization_id == ctx.org_id, Lead.deleted_at.is_(None), Lead.created_at >= d30))
        pl = db.scalar(select(func.count()).select_from(Lead).where(Lead.organization_id == ctx.org_id, Lead.deleted_at.is_(None),
                                                                    Lead.created_at >= d60, Lead.created_at < d30))
        kpis["new_leads"] = {"value": nl, "trend_pct": _pct(nl, pl)}
    kpis["active_projects"] = {"value": db.scalar(select(func.count()).select_from(Project).where(
        project_cond(db, ctx), Project.status.in_(["active", "at_risk", "delayed"])))}
    kpis["at_risk_customers"] = {"value": db.scalar(select(func.count()).select_from(Customer).where(
        cust, Customer.health_status.in_(["at_risk", "critical"])))}
    if ctx.can("invoices.read"):
        def rev(a, b):
            return db.scalar(select(func.coalesce(func.sum(Payment.amount), 0)).join(Invoice, Invoice.id == Payment.invoice_id).where(
                invoice_cond(db, ctx), Payment.status == "completed", Payment.paid_at >= a, Payment.paid_at < b))
        cur, prev = rev(d30, now + timedelta(days=1)), rev(d60, d30)
        kpis["revenue"] = {"value": str(cur), "trend_pct": _pct(cur, prev)}

    out = {"kpis": kpis}
    if ctx.can("invoices.read"):
        days, bucket = RANGES[range]
        out["revenue_pipeline"] = {"range": range, "series": _revenue_series(db, ctx, days, bucket)}
    if ctx.can("leads.read"):
        counts = dict(db.execute(select(Lead.status, func.count()).where(Lead.organization_id == ctx.org_id, Lead.deleted_at.is_(None))
                                 .group_by(Lead.status)).all())
        # cumulative funnel: a lead at a later stage has passed earlier stages
        reached = {s: sum(counts.get(x, 0) for x in FUNNEL[i:]) for i, s in enumerate(FUNNEL)}
        top = reached["new"] or 1
        out["funnel"] = [{"stage": s, "count": reached[s], "conversion_pct": round(reached[s] / top * 100, 1)} for s in FUNNEL]

    # Attention Required: pending AI recommendations + overdue invoices + critical tickets
    attention = []
    if ctx.can("ai.read"):
        recs = db.scalars(select(AIRecommendation).where(AIRecommendation.organization_id == ctx.org_id, AIRecommendation.status == "pending")
                          .order_by(AIRecommendation.created_at.desc()).limit(30)).all()
        visible_c = set(db.scalars(select(Customer.id).where(cust)))
        visible_p = set(db.scalars(select(Project.id).where(project_cond(db, ctx))))
        for r in recs:
            if (r.entity_type == "customer" and r.entity_id in visible_c) or (r.entity_type == "project" and r.entity_id in visible_p):
                attention.append({"severity": "high", "kind": f"{r.entity_type}_risk", "title": r.title, "entity_type": r.entity_type,
                                  "entity_id": str(r.entity_id), "reason": r.description, "action": r.recommended_action,
                                  "recommendation_id": str(r.id)})
    crit = db.execute(select(Ticket.id, Ticket.subject, Customer.name).join(Customer, Customer.id == Ticket.customer_id).where(
        ticket_cond(db, ctx), Ticket.priority == "critical", Ticket.status.notin_(["resolved", "closed"])).limit(5)).all()
    attention += [{"severity": "critical", "kind": "critical_ticket", "title": subj, "entity_type": "ticket", "entity_id": str(i),
                   "reason": f"Critical ticket for {cn}", "action": "Review"} for i, subj, cn in crit]
    if ctx.can("invoices.read"):
        od = db.execute(select(Invoice.id, Invoice.invoice_number, Invoice.total - Invoice.amount_paid, Customer.name).join(
            Customer, Customer.id == Invoice.customer_id).where(invoice_cond(db, ctx), Invoice.status.in_(["sent", "partially_paid", "overdue"]),
                                                                  Invoice.due_date < date.today()).order_by(Invoice.due_date).limit(5)).all()
        attention += [{"severity": "medium", "kind": "overdue_payment", "title": f"{cn}: {num} overdue", "entity_type": "invoice",
                       "entity_id": str(i), "reason": f"Outstanding balance {bal}", "action": "Review"} for i, num, bal, cn in od]
    out["attention_required"] = attention[:10]

    if ctx.can("team.read"):
        out["team_workload"] = team_workload(db, ctx.org_id)
    pc = dict(db.execute(select(Project.status, func.count()).where(project_cond(db, ctx)).group_by(Project.status)).all())
    risky = db.scalar(select(func.count()).select_from(Project).where(project_cond(db, ctx), Project.status == "active", Project.risk_level == "high"))
    out["project_status"] = {"on_track": max(pc.get("active", 0) + pc.get("planning", 0) - risky, 0), "at_risk": pc.get("at_risk", 0) + risky,
                             "delayed": pc.get("delayed", 0), "completed": pc.get("completed", 0)}
    aq = select(AuditLog, User.first_name).outerjoin(User, User.id == AuditLog.actor_id).where(
        AuditLog.organization_id == ctx.org_id, AuditLog.action.in_(list(ACTIONS)))
    if not ctx.is_owner:
        aq = aq.where(AuditLog.actor_id == ctx.user.id)
    out["recent_activity"] = [{"actor": n or "System", "action": ACTIONS[a.action], "entity_type": a.entity_type,
                               "entity_id": str(a.entity_id) if a.entity_id else None, "at": a.created_at.isoformat()}
                              for a, n in db.execute(aq.order_by(AuditLog.created_at.desc()).limit(10)).all()]
    over = sum(1 for m in out.get("team_workload", []) if m["status"] == "overloaded")
    out["insights"] = {"customers_need_attention": sum(1 for a in attention if a["kind"] == "customer_risk"),
                       "projects_may_miss_deadline": sum(1 for a in attention if a["kind"] == "project_risk"),
                       "overloaded_members": over}
    out["my_work"] = {"open_tasks": db.scalar(select(func.count()).select_from(Task).where(
        task_cond(db, ctx), Task.assignee_id == ctx.user.id, Task.status.in_(["todo", "in_progress", "blocked", "review"]))),
        "assigned_tickets": db.scalar(select(func.count()).select_from(Ticket).where(
            ticket_cond(db, ctx), Ticket.assigned_to == ctx.user.id, Ticket.status.notin_(["resolved", "closed"])))}
    return out
