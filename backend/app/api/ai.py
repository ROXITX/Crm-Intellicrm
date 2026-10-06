import json
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai import service as ai
from app.ai.training import model_dir
from app.core.audit import audit
from app.core.db import SessionLocal, get_db
from app.core.deps import Ctx, require
from app.core.errors import conflict, not_found
from app.core.scope import customer_cond, invoice_cond, project_cond, task_cond, ticket_cond
from app.core.util import Page, get_or_404, paginate, ser
from app.models import (AIPrediction, AIRecommendation, Customer, Invoice, Lead, Project, Task, Ticket)
from app.services.workload import team_workload

router = APIRouter(prefix="/ai", tags=["ai"])


class DecisionIn(BaseModel):
    decision: Literal["accepted", "rejected", "completed"]


class AskIn(BaseModel):
    question: str = Field(min_length=2, max_length=500)


def _insight(kind, title, pred: dict | None = None, **kw):
    base = {"kind": kind, "title": title}
    if pred:
        base.update(prediction=pred["summary"], probability=pred["probability"], confidence=pred["confidence"], risk_level=pred["risk_level"],
                    factors=pred["factors"], recommended_actions=pred["recommended_actions"], model_name=pred["model_name"],
                    model_version=pred["model_version"], generated_at=pred["created_at"])
    base.update(kw)
    return base


def _latest_preds(db, ctx, etype, ptype, ids=None, min_prob=None, limit=8):
    sub = (select(AIPrediction.entity_id, func.max(AIPrediction.created_at).label("m")).where(
        AIPrediction.organization_id == ctx.org_id, AIPrediction.entity_type == etype, AIPrediction.prediction_type == ptype)
        .group_by(AIPrediction.entity_id).subquery())
    q = select(AIPrediction).join(sub, (sub.c.entity_id == AIPrediction.entity_id) & (sub.c.m == AIPrediction.created_at)).where(
        AIPrediction.organization_id == ctx.org_id, AIPrediction.prediction_type == ptype)
    if ids is not None:
        q = q.where(AIPrediction.entity_id.in_(ids))
    if min_prob is not None:
        q = q.where(AIPrediction.prediction_value >= min_prob)
    return db.scalars(q.order_by(AIPrediction.prediction_value.desc()).limit(limit)).all()


@router.get("/insights")
def insights(ctx: Ctx = Depends(require("ai.read", "internal.view")), db: Session = Depends(get_db)):
    """Business-intelligence view: each insight carries prediction, probability, factors, action, model version, timestamp."""
    out = {"customer_risks": [], "lead_opportunities": [], "project_delays": [], "ticket_risks": [], "revenue_anomalies": [], "workload_warnings": []}
    cids = {c.id: c for c in db.scalars(select(Customer).where(customer_cond(db, ctx)))}
    for p in _latest_preds(db, ctx, "customer", "customer_churn", ids=list(cids), min_prob=0.3):
        out["customer_risks"].append(_insight("customer_churn", cids[p.entity_id].name, ai.prediction_dict(p), entity_type="customer", entity_id=str(p.entity_id)))
    if ctx.can("leads.read"):
        leads = {l.id: l for l in db.scalars(select(Lead).where(Lead.organization_id == ctx.org_id, Lead.deleted_at.is_(None),
                                                                 Lead.status.notin_(["won", "lost"]), Lead.score >= 70))}
        for p in _latest_preds(db, ctx, "lead", "lead_conversion", ids=list(leads), limit=8):
            out["lead_opportunities"].append(_insight("lead_conversion", leads[p.entity_id].name, ai.prediction_dict(p), entity_type="lead", entity_id=str(p.entity_id)))
    projs = {p.id: p for p in db.scalars(select(Project).where(project_cond(db, ctx), Project.status.notin_(["completed", "archived"])))}
    for p in _latest_preds(db, ctx, "project", "project_delay", ids=list(projs), min_prob=0.3):
        out["project_delays"].append(_insight("project_delay", projs[p.entity_id].name, ai.prediction_dict(p), entity_type="project", entity_id=str(p.entity_id)))
    now = datetime.now(timezone.utc)
    for t, cn in db.execute(select(Ticket, Customer.name).join(Customer, Customer.id == Ticket.customer_id).where(
            ticket_cond(db, ctx), Ticket.status.notin_(["resolved", "closed"]),
            (Ticket.priority.in_(["critical", "high"])) | (Ticket.sentiment == "negative") | (Ticket.sla_due_at < now)).limit(8)).all():
        breached = t.sla_due_at and t.sla_due_at < now
        out["ticket_risks"].append(_insight("ticket_risk", f"{cn}: {t.subject}", entity_type="ticket", entity_id=str(t.id), prediction=
            f"{t.priority.title()} priority, {t.sentiment or 'unknown'} sentiment" + (", SLA breached" if breached else ""),
            confidence=float(t.priority_confidence) if t.priority_confidence else None, risk_level="high" if breached or t.priority == "critical" else "medium",
            factors=[{"label": f"Sentiment: {t.sentiment}", "impact": None}, {"label": f"Priority: {t.priority}", "impact": None}],
            recommended_actions=["Respond immediately - SLA breached." if breached else "Review and respond within SLA."], model_name="ticket_priority", model_version=ai.get_model("ticket_priority")[1]["version"],
            generated_at=t.updated_at.isoformat()))
    if ctx.can("invoices.read"):
        od_total, od_n = db.execute(select(func.coalesce(func.sum(Invoice.total - Invoice.amount_paid), 0), func.count()).where(
            invoice_cond(db, ctx), Invoice.status.in_(["sent", "partially_paid", "overdue"]), Invoice.due_date < date.today())).one()
        if od_n:
            out["revenue_anomalies"].append({"kind": "overdue_receivables", "title": f"{od_n} overdue invoice(s) totalling {od_total}",
                "prediction": "Overdue receivables are putting cash flow at risk.", "probability": None, "confidence": None, "risk_level": "high" if od_n >= 3 else "medium",
                "factors": [{"label": f"{od_n} invoice(s) past due date", "impact": None}], "recommended_actions": ["Send payment reminders to the customers concerned."],
                "model_name": "rule:overdue_receivables", "model_version": "1", "generated_at": now.isoformat()})
    if ctx.can("team.read"):
        for m in team_workload(db, ctx.org_id):
            if m["status"] != "normal":
                out["workload_warnings"].append({"kind": "workload", "title": f"{m['name']} at {m['capacity_pct']:.0f}% capacity",
                    "prediction": f"{m['name']} is {m['status']} ({m['active_tasks']} active, {m['overdue_tasks']} overdue tasks).", "probability": None, "confidence": None,
                    "risk_level": "high" if m["status"] == "overloaded" else "medium", "factors": [{"label": f"{m['allocated_hours']}h allocated vs {m['available_hours']}h available", "impact": None}],
                    "recommended_actions": ["Review assignments and consider reassigning lower-priority tasks (a manager decides)."],
                    "model_name": "rule:capacity", "model_version": "1", "generated_at": now.isoformat()})
    return out


@router.get("/recommendations")
def recommendations(status: Literal["pending", "accepted", "rejected", "completed", "expired"] | None = "pending", p: Page = Depends(),
                    ctx: Ctx = Depends(require("ai.read", "internal.view")), db: Session = Depends(get_db)):
    conds = [AIRecommendation.organization_id == ctx.org_id]
    if status: conds.append(AIRecommendation.status == status)
    if not ctx.sees_all:  # restrict to entities within the caller's scope
        cids = select(Customer.id).where(customer_cond(db, ctx)); pids = select(Project.id).where(project_cond(db, ctx))
        conds.append(AIRecommendation.entity_id.in_(cids) | AIRecommendation.entity_id.in_(pids))
    return paginate(db, select(AIRecommendation).where(*conds).order_by(AIRecommendation.created_at.desc(), AIRecommendation.id), p, lambda r: ser(r[0]))


@router.post("/recommendations/{rid}/decision")
def decide(rid: uuid.UUID, body: DecisionIn, ctx: Ctx = Depends(require("ai.read", "internal.view")), db: Session = Depends(get_db)):
    """Human decision step of the recommendation lifecycle - recommendations are never executed automatically."""
    rec = get_or_404(db, select(AIRecommendation).where(AIRecommendation.id == rid, AIRecommendation.organization_id == ctx.org_id), "Recommendation")
    if not ctx.sees_all:
        visible = set(db.scalars(select(Customer.id).where(customer_cond(db, ctx)))) | set(db.scalars(select(Project.id).where(project_cond(db, ctx))))
        if rec.entity_id not in visible:
            raise not_found("Recommendation")
    if rec.status in ("rejected", "completed", "expired"):
        raise conflict(f"Recommendation is already {rec.status}", "INVALID_STATE")
    before = rec.status
    rec.status, rec.acted_at, rec.acted_by = body.decision, datetime.now(timezone.utc), ctx.user.id
    audit(db, ctx, f"ai.recommendation_{body.decision}", "ai_recommendation", rec.id, {"status": before}, {"status": rec.status})
    return ser(rec)


def _run_job(org_id):
    with SessionLocal() as db:
        ai.run_all(db, org_id)
        db.commit()


@router.post("/run", status_code=202)
def run_predictions(bg: BackgroundTasks, ctx: Ctx = Depends(require("ai.manage")), db: Session = Depends(get_db)):
    """Queues a background refresh of all predictions so the request returns immediately."""
    audit(db, ctx, "ai.run_all", "organization", ctx.org_id)
    db.commit()
    bg.add_task(_run_job, ctx.org_id)
    return {"status": "queued"}


@router.get("/models")
def model_cards(ctx: Ctx = Depends(require("ai.read", "internal.view"))):
    out = []
    for name in ("lead_conversion", "customer_churn", "project_delay", "ticket_sentiment", "ticket_priority"):
        _, meta = ai.get_model(name)
        out.append({k: meta[k] for k in ("name", "algorithm", "version", "features", "trained_at", "training_data", "metrics")})
    return out


@router.get("/predictions/{entity_type}/{entity_id}")
def entity_predictions(entity_type: Literal["lead", "customer", "project", "ticket"], entity_id: uuid.UUID,
                       ctx: Ctx = Depends(require("ai.read", "internal.view")), db: Session = Depends(get_db)):
    scope = {"customer": customer_cond, "project": project_cond, "ticket": ticket_cond}
    model = {"customer": Customer, "project": Project, "ticket": Ticket, "lead": Lead}[entity_type]
    if entity_type == "lead":
        ctx_ok = ctx.can("leads.read") and db.scalar(select(Lead.id).where(Lead.id == entity_id, Lead.organization_id == ctx.org_id))
    else:
        ctx_ok = db.scalar(select(model.id).where(model.id == entity_id, scope[entity_type](db, ctx)))
    if not ctx_ok:
        raise not_found(entity_type.title())
    rows = db.scalars(select(AIPrediction).where(AIPrediction.organization_id == ctx.org_id, AIPrediction.entity_type == entity_type,
                                                 AIPrediction.entity_id == entity_id).order_by(AIPrediction.created_at.desc()).limit(20)).all()
    return [ai.prediction_dict(r) for r in rows]


# ------------------------------------------------------------------ Ask IntelliCRM
def _tool_customers_attention(db, ctx):
    cids = {c.id: c for c in db.scalars(select(Customer).where(customer_cond(db, ctx)))}
    items = []
    for p in _latest_preds(db, ctx, "customer", "customer_churn", ids=list(cids), min_prob=ai.HIGH_RISK, limit=5):
        pd_ = ai.prediction_dict(p)
        items.append({"title": cids[p.entity_id].name, "detail": f"Churn probability {pd_['probability']:.0%}: " + "; ".join(f["label"] for f in pd_["factors"][:2]),
                      "entity_type": "customer", "entity_id": str(p.entity_id)})
    return f"{len(items)} customer(s) need attention." if items else "No customers currently show a high churn risk.", items


def _tool_project_risks(db, ctx):
    projs = {p.id: p for p in db.scalars(select(Project).where(project_cond(db, ctx), Project.status.notin_(["completed", "archived"])))}
    items = []
    for p in _latest_preds(db, ctx, "project", "project_delay", ids=list(projs), min_prob=ai.HIGH_RISK, limit=5):
        d = ai.prediction_dict(p)
        items.append({"title": projs[p.entity_id].name, "detail": f"Delay probability {d['probability']:.0%}: " + "; ".join(f["label"] for f in d["factors"][:2]),
                      "entity_type": "project", "entity_id": str(p.entity_id)})
    return f"{len(items)} project(s) are likely to be delayed." if items else "No projects are currently predicted to be delayed.", items


def _tool_next_tasks(db, ctx):
    prio = func.array_position(["critical", "high", "medium", "low"], Task.priority)
    rows = db.scalars(select(Task).where(task_cond(db, ctx), Task.assignee_id == ctx.user.id, Task.status.in_(["todo", "in_progress", "blocked", "review"]))
                      .order_by(prio, Task.due_date.asc().nulls_last()).limit(5)).all()
    return (f"Here are your top {len(rows)} task(s), ordered by priority and due date." if rows else "You have no open tasks."), \
           [{"title": t.title, "detail": f"{t.priority} priority, {t.status.replace('_', ' ')}" + (f", due {t.due_date:%d %b}" if t.due_date else ""),
             "entity_type": "task", "entity_id": str(t.id)} for t in rows]


def _tool_overdue_invoices(db, ctx):
    rows = db.execute(select(Invoice, Customer.name).join(Customer, Customer.id == Invoice.customer_id).where(
        invoice_cond(db, ctx), Invoice.status.in_(["sent", "partially_paid", "overdue"]), Invoice.due_date < date.today()).order_by(Invoice.due_date).limit(8)).all()
    return (f"{len(rows)} invoice(s) are overdue." if rows else "No invoices are overdue."), \
           [{"title": f"{i.invoice_number} - {cn}", "detail": f"Balance {i.total - i.amount_paid} {i.currency}, {(date.today() - i.due_date).days} day(s) overdue",
             "entity_type": "invoice", "entity_id": str(i.id)} for i, cn in rows]


def _tool_workload(db, ctx):
    rows = [m for m in team_workload(db, ctx.org_id) if m["status"] != "normal"]
    return (f"{len(rows)} team member(s) are above normal capacity." if rows else "Everyone is within normal capacity."), \
           [{"title": m["name"], "detail": f"{m['capacity_pct']:.0f}% capacity, {m['active_tasks']} active tasks ({m['status']})", "entity_type": "user", "entity_id": m["user_id"]} for m in rows]


def _tool_lead_pipeline(db, ctx):
    rows = db.execute(select(Lead.status, func.count(), func.coalesce(func.sum(Lead.estimated_value), 0)).where(
        Lead.organization_id == ctx.org_id, Lead.deleted_at.is_(None), Lead.status.notin_(["won", "lost"])).group_by(Lead.status)).all()
    hot = db.scalars(select(Lead).where(Lead.organization_id == ctx.org_id, Lead.deleted_at.is_(None), Lead.status.notin_(["won", "lost"]), Lead.score >= 80)
                     .order_by(Lead.score.desc()).limit(3)).all()
    items = [{"title": s.title(), "detail": f"{n} lead(s), value {v}", "entity_type": None, "entity_id": None} for s, n, v in rows]
    items += [{"title": f"Hot lead: {l.name}", "detail": f"Score {l.score}", "entity_type": "lead", "entity_id": str(l.id)} for l in hot]
    return f"Open pipeline has {sum(n for _, n, _ in rows)} lead(s); {len(hot)} high-scoring.", items


def _tool_open_tickets(db, ctx):
    prio = func.array_position(["critical", "high", "medium", "low"], Ticket.priority)
    rows = db.execute(select(Ticket, Customer.name).join(Customer, Customer.id == Ticket.customer_id).where(
        ticket_cond(db, ctx), Ticket.status.notin_(["resolved", "closed"])).order_by(prio, Ticket.created_at).limit(6)).all()
    return (f"{len(rows)} open ticket(s), most urgent first." if rows else "No open tickets."), \
           [{"title": t.subject, "detail": f"{cn} - {t.priority} priority, {t.status.replace('_', ' ')}", "entity_type": "ticket", "entity_id": str(t.id)} for t, cn in rows]


def _tool_project_status(db, ctx):
    rows = db.scalars(select(Project).where(project_cond(db, ctx), Project.status.notin_(["archived"])).order_by(Project.due_date).limit(6)).all()
    return (f"You have {len(rows)} project(s)." if rows else "No projects found."), \
           [{"title": p.name, "detail": f"{p.status.replace('_', ' ').title()}, {p.progress}% complete" + (f", due {p.due_date:%d %b %Y}" if p.due_date else ""),
             "entity_type": "project", "entity_id": str(p.id)} for p in rows]


# (regex, tool name, required permissions, handler); every handler applies the caller's own scope - the assistant
# has no SQL access and no path around RBAC.
TOOLS = [
    (r"attention|churn|at.risk|unhappy", "get_customer_health", ("customers.read", "ai.read", "internal.view"), _tool_customers_attention),
    (r"delay|late|deadline|behind|miss", "get_project_risks", ("projects.read", "ai.read", "internal.view"), _tool_project_risks),
    (r"work on|next|my tasks|todo|to.do", "get_my_tasks", ("tasks.read",), _tool_next_tasks),
    (r"overdue|invoice|payment|unpaid|owe", "get_overdue_invoices", ("invoices.read",), _tool_overdue_invoices),
    (r"workload|overload|capacity|busy", "get_team_workload", ("team.read",), _tool_workload),
    (r"pipeline|lead|opportunit", "get_lead_pipeline", ("leads.read",), _tool_lead_pipeline),
    (r"ticket|support|request", "get_open_tickets", ("tickets.read",), _tool_open_tickets),
    (r"status|project|progress", "get_project_status", ("projects.read",), _tool_project_status),
]


@router.post("/assistant/query")
def ask(body: AskIn, ctx: Ctx = Depends(require("messages.read")), db: Session = Depends(get_db)):
    """Role-aware assistant. Questions are routed to a fixed set of permission-checked tools - never to free-form SQL."""
    q = body.question.lower()
    for rx, name, perms, fn in TOOLS:
        if re.search(rx, q):
            if not all(ctx.can(p) for p in perms):
                audit(db, ctx, "ai.assistant.denied", meta={"tool": name})
                return {"answer": "That information isn't available to your role.", "items": [], "tools_used": [], "suggestions": _suggest(ctx)}
            answer, items = fn(db, ctx)
            audit(db, ctx, "ai.assistant.query", meta={"tool": name, "question": body.question[:200]})
            return {"answer": answer, "items": items, "tools_used": [name], "suggestions": []}
    audit(db, ctx, "ai.assistant.query", meta={"tool": None, "question": body.question[:200]})
    return {"answer": "I can answer questions about the data you have access to. Try one of the suggestions below.", "items": [], "tools_used": [], "suggestions": _suggest(ctx)}


def _suggest(ctx):
    out = []
    for _, name, perms, _fn in TOOLS:
        if all(ctx.can(p) for p in perms):
            out.append({"get_customer_health": "Which customers need attention today?", "get_project_risks": "Which projects are likely to be delayed?",
                        "get_my_tasks": "What should I work on next?", "get_overdue_invoices": "Which invoices are overdue?",
                        "get_team_workload": "Who is overloaded?", "get_lead_pipeline": "Show me the lead pipeline",
                        "get_open_tickets": "What tickets are open?", "get_project_status": "What is the status of my projects?"}[name])
    return out
