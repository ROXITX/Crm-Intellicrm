"""AI orchestration: feature extraction from PostgreSQL -> CPU model -> explanation -> ai_predictions / ai_recommendations.

Every prediction records model name/version/confidence/timestamp and an explanation with the factors, so AI output
is auditable. Nothing here changes business state silently: recommendations wait for a human decision.
"""
import re
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import numpy as np
import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai import synthetic as syn
from app.ai.registry import get_model
from app.core.audit import notify
from app.models import (AIPrediction, AIRecommendation, Customer, Feedback, Invoice, Lead, LeadInteraction, Message,
                        Milestone, OrganizationMember, Project, ProjectMember, Role, Task, Ticket, Conversation)
from app.services.workload import team_workload

DISCLAIMER = "Model estimate based on historical patterns - not a certain outcome."


HIGH_RISK = 0.50  # probability at/above which risk is "high" (recommendations + alerts are created)


def risk_level(p: float) -> str:
    return "low" if p < 0.30 else "medium" if p < HIGH_RISK else "high"


def _now():
    return datetime.now(timezone.utc)


def _days(dt, default=60) -> float:
    return max((_now() - dt).total_seconds() / 86400, 0) if dt else float(default)


# --------------------------------------------------------------------------- explanations
def _tabular_explain(model, meta, row: dict, labels: dict, reference: dict | None = None, top=4) -> list[dict]:
    """Local sensitivity explanation: change in P(positive) when one feature is set to its reference value."""
    feats = meta["features"]
    ref = reference or meta["baseline"]
    X = pd.DataFrame([row])[feats]
    p0 = float(model.predict_proba(X)[0, 1])
    out = []
    for f in feats:
        alt = X.copy()
        alt[f] = ref[f]
        impact = p0 - float(model.predict_proba(alt)[0, 1])
        out.append({"feature": f, "label": labels[f](row[f]), "impact": round(impact, 4),
                    "direction": "increases" if impact > 0 else "decreases"})
    out.sort(key=lambda x: abs(x["impact"]), reverse=True)
    return [o for o in out if abs(o["impact"]) >= 0.005][:top]


def _text_explain(pipe, text: str, cls: str, top=3) -> list[dict]:
    vec, clf = pipe.steps[0][1], pipe.steps[-1][1]
    X = vec.transform([text])
    ci = list(clf.classes_).index(cls)
    names = vec.get_feature_names_out()
    contrib = X.multiply(clf.coef_[ci]).tocoo()
    items = sorted(zip(contrib.col, contrib.data), key=lambda t: t[1], reverse=True)[:top]
    return [{"term": names[i], "weight": round(float(w), 3)} for i, w in items if w > 0]


# --------------------------------------------------------------------------- persistence helpers
def latest_prediction(db: Session, org_id, entity_type: str, entity_id, ptype: str) -> dict | None:
    p = db.scalars(select(AIPrediction).where(AIPrediction.organization_id == org_id, AIPrediction.entity_type == entity_type,
                                              AIPrediction.entity_id == entity_id, AIPrediction.prediction_type == ptype)
                   .order_by(AIPrediction.created_at.desc(), AIPrediction.id).limit(1)).first()
    return prediction_dict(p) if p else None


def prediction_dict(p: AIPrediction) -> dict:
    e = p.explanation or {}
    return {"id": str(p.id), "entity_type": p.entity_type, "entity_id": str(p.entity_id), "prediction_type": p.prediction_type,
            "probability": float(p.prediction_value) if p.prediction_value is not None else None, "risk_level": p.risk_level,
            "confidence": float(p.confidence) if p.confidence is not None else None, "summary": e.get("summary"),
            "factors": e.get("factors", []), "recommended_actions": e.get("recommended_actions", []),
            "business_rules": e.get("business_rules", []), "disclaimer": e.get("disclaimer", DISCLAIMER),
            "model_name": p.model_name, "model_version": p.model_version, "created_at": p.created_at.isoformat()}


def _store(db, org_id, etype, eid, ptype, prob, level, conf, meta, explanation) -> AIPrediction:
    last = db.scalars(select(AIPrediction).where(AIPrediction.organization_id == org_id, AIPrediction.entity_type == etype,
                                                 AIPrediction.entity_id == eid, AIPrediction.prediction_type == ptype)
                      .order_by(AIPrediction.created_at.desc()).limit(1)).first()
    if last and last.model_version == meta["version"] and abs(float(last.prediction_value or 0) - prob) < 0.01 \
            and (_now() - last.created_at) < timedelta(hours=12):
        return last  # unchanged - avoid bloating history
    pred = AIPrediction(organization_id=org_id, entity_type=etype, entity_id=eid, prediction_type=ptype,
                        prediction_value=round(prob, 6), risk_level=level, confidence=round(conf, 4),
                        model_name=meta["name"], model_version=meta["version"], explanation=explanation)
    db.add(pred)
    db.flush()
    return pred


def _recommend(db, org_id, pred: AIPrediction, etype, eid, title, desc, action, notify_users=()):
    """Create a pending recommendation once per (entity, title); humans accept/reject it later."""
    exists = db.scalar(select(AIRecommendation.id).where(AIRecommendation.organization_id == org_id, AIRecommendation.entity_type == etype,
                                                          AIRecommendation.entity_id == eid, AIRecommendation.title == title,
                                                          AIRecommendation.status == "pending"))
    if exists:
        return None
    rec = AIRecommendation(organization_id=org_id, prediction_id=pred.id, entity_type=etype, entity_id=eid, title=title,
                           description=desc, recommended_action=action, status="pending")
    db.add(rec)
    for uid in set(u for u in notify_users if u):
        notify(db, org_id, uid, "customer_risk" if etype == "customer" else "project_risk", title, desc, etype, eid)
    return rec


def _owners_and_managers(db, org_id):
    return list(db.scalars(select(OrganizationMember.user_id).join(Role, Role.id == OrganizationMember.role_id).where(
        OrganizationMember.organization_id == org_id, Role.name == "owner", OrganizationMember.status == "active")))


# --------------------------------------------------------------------------- LEADS
LEAD_LABELS = {
    "interactions_30d": lambda v: f"{v:.0f} interaction(s) in the last 30 days",
    "days_since_last_interaction": lambda v: f"Last interaction {v:.0f} day(s) ago",
    "inquiries": lambda v: f"{v:.0f} inquiry/inquiries received",
    "proposal_requested": lambda v: "Requested a proposal" if v else "No proposal requested yet",
    "pricing_page_visits": lambda v: f"{v:.0f} pricing-page interaction(s)",
    "response_rate": lambda v: f"{v:.0%} response rate to outreach",
    "source_quality": lambda v: "Strong lead source" if v > 0.3 else "Weak lead source" if v < 0 else "Average lead source",
    "has_company": lambda v: "Company information provided" if v else "No company information",
    "log_estimated_value": lambda v: f"Estimated deal value ~{np.expm1(v):,.0f}",
}


def lead_features(db: Session, lead: Lead) -> dict:
    ints = db.execute(select(LeadInteraction.type, LeadInteraction.occurred_at).where(
        LeadInteraction.lead_id == lead.id, LeadInteraction.organization_id == lead.organization_id)).all()
    now = _now()
    last = max((i[1] for i in ints), default=None)
    outbound = sum(1 for t, _ in ints if t in ("email", "call", "meeting"))
    replies = sum(1 for t, _ in ints if t == "reply")
    return {"interactions_30d": sum(1 for _, at in ints if (now - at).days <= 30),
            "days_since_last_interaction": _days(last, default=90) if ints else 90.0,
            "inquiries": sum(1 for t, _ in ints if t == "inquiry"),
            "proposal_requested": int(any(t == "proposal_requested" for t, _ in ints) or lead.status in ("proposal", "negotiation")),
            "pricing_page_visits": sum(1 for t, _ in ints if t == "pricing_page"),
            "response_rate": min(replies / outbound, 1.0) if outbound else 0.0,
            "source_quality": syn.SOURCE_BOOST.get((lead.source or "other").lower(), -0.2),
            "has_company": int(bool(lead.company_name)),
            "log_estimated_value": float(np.log1p(float(lead.estimated_value or 0))) if lead.estimated_value else 9.0}


def score_lead(db: Session, lead: Lead) -> dict:
    model, meta = get_model("lead_conversion")
    row = lead_features(db, lead)
    X = pd.DataFrame([row])[meta["features"]]
    p = float(model.predict_proba(X)[0, 1])
    rules = []
    if lead.status == "lost":
        p = min(p, 0.05); rules.append("Lead is marked Lost - score capped at 5.")
    elif lead.status == "negotiation":
        if p < 0.5: p = 0.5; rules.append("Lead is in Negotiation - score floored at 50.")
    elif lead.status == "proposal":
        if p < 0.4: p = 0.4; rules.append("Lead is at Proposal stage - score floored at 40.")
    if row["days_since_last_interaction"] >= 90 and lead.status not in ("won", "lost"):
        p = min(p, 0.35); rules.append("No interaction on record - score capped at 35.")
    factors = _tabular_explain(model, meta, row, LEAD_LABELS)
    score = round(p * 100, 2)
    level = "high" if score >= 80 else "medium" if score >= 50 else "low"
    actions = []
    if level == "high":
        actions.append("Prioritise this lead: schedule a call or send the proposal within 48 hours.")
    if row["days_since_last_interaction"] > 14 and lead.status not in ("won", "lost"):
        actions.append(f"Re-engage: no interaction for {row['days_since_last_interaction']:.0f} days.")
    if not row["proposal_requested"] and level != "low":
        actions.append("Offer a tailored proposal to move the lead forward.")
    if not actions:
        actions.append("Continue nurturing with periodic value-adding touchpoints.")
    conf = float(max(model.predict_proba(X)[0]))
    lead.score, lead.score_probability = Decimal(str(score)), Decimal(str(round(p, 4)))
    explanation = {"summary": f"Lead score {score:.0f}/100 ({level}); estimated conversion probability {p:.0%}.",
                   "factors": factors, "recommended_actions": actions, "business_rules": rules, "disclaimer": DISCLAIMER}
    pred = _store(db, lead.organization_id, "lead", lead.id, "lead_conversion", p, level, conf, meta, explanation)
    return prediction_dict(pred)


# --------------------------------------------------------------------------- CUSTOMERS
CHURN_LABELS = {
    "days_since_last_interaction": lambda v: f"No interaction for {v:.0f} days",
    "tickets_90d": lambda v: f"{v:.0f} support ticket(s) in the last 90 days",
    "open_tickets": lambda v: f"{v:.0f} unresolved ticket(s)",
    "negative_sentiment_ratio": lambda v: f"{v:.0%} of recent tickets have negative sentiment",
    "project_delay_ratio": lambda v: f"{v:.0%} of active projects are delayed/at risk",
    "overdue_invoice_ratio": lambda v: f"{v:.0%} of invoices are overdue",
    "interactions_30d": lambda v: f"{v:.0f} interaction(s) in the last 30 days",
    "avg_feedback": lambda v: f"Average feedback rating {v:.1f}/5",
}
CHURN_REFERENCE = {"days_since_last_interaction": 7, "tickets_90d": 1, "open_tickets": 0, "negative_sentiment_ratio": 0.05,
                   "project_delay_ratio": 0.0, "overdue_invoice_ratio": 0.0, "interactions_30d": 8, "avg_feedback": 4.2}


def customer_features(db: Session, c: Customer) -> dict:
    org, now = c.organization_id, _now()
    since90, since30 = now - timedelta(days=90), now - timedelta(days=30)
    t90 = db.execute(select(Ticket.sentiment, Ticket.status).where(Ticket.customer_id == c.id, Ticket.organization_id == org,
                                                                    Ticket.created_at >= since90, Ticket.deleted_at.is_(None))).all()
    open_t = db.scalar(select(func.count()).where(Ticket.customer_id == c.id, Ticket.organization_id == org,
                                                   Ticket.deleted_at.is_(None), Ticket.status.notin_(["resolved", "closed"])))
    projects = db.execute(select(Project.status, Project.risk_level).where(Project.customer_id == c.id, Project.organization_id == org,
                                                                           Project.deleted_at.is_(None),
                                                                           Project.status.in_(["planning", "active", "at_risk", "delayed"]))).all()
    delayed = sum(1 for s, r in projects if s in ("delayed", "at_risk") or r == "high")
    inv = db.execute(select(Invoice.status).where(Invoice.customer_id == c.id, Invoice.organization_id == org,
                                                  Invoice.status.in_(["sent", "partially_paid", "overdue", "paid"]))).all()
    overdue = sum(1 for (s,) in inv if s == "overdue")
    msgs = db.scalar(select(func.count()).select_from(Message).join(Conversation, Conversation.id == Message.conversation_id).where(
        Conversation.customer_id == c.id, Message.organization_id == org, Message.created_at >= since30))
    t30 = sum(1 for _ in db.scalars(select(Ticket.id).where(Ticket.customer_id == c.id, Ticket.created_at >= since30)))
    fb = db.scalar(select(func.avg(Feedback.rating)).where(Feedback.customer_id == c.id, Feedback.organization_id == org))
    return {"days_since_last_interaction": _days(c.last_interaction_at or c.created_at),
            "tickets_90d": len(t90), "open_tickets": open_t,
            "negative_sentiment_ratio": (sum(1 for s, _ in t90 if s == "negative") / len(t90)) if t90 else 0.0,
            "project_delay_ratio": delayed / len(projects) if projects else 0.0,
            "overdue_invoice_ratio": overdue / len(inv) if inv else 0.0,
            "interactions_30d": (msgs or 0) + t30, "avg_feedback": float(fb) if fb is not None else 3.5}


def health_from_features(f: dict) -> float:
    """Transparent, rule-based health score (0-100): engagement, sentiment, tickets, projects, payments, recency."""
    pen = (min(25, f["days_since_last_interaction"] / 90 * 25) + min(15, f["open_tickets"] * 5)
           + f["negative_sentiment_ratio"] * 20 + f["project_delay_ratio"] * 15 + f["overdue_invoice_ratio"] * 15
           + (min(10, (3 - f["avg_feedback"]) * 5) if f["avg_feedback"] < 3 else 0) + (10 if f["interactions_30d"] == 0 else 0))
    return round(max(0.0, min(100.0, 100 - pen)), 2)


def health_status(score: float) -> str:
    return "healthy" if score >= 70 else "watch" if score >= 50 else "at_risk" if score >= 30 else "critical"


def predict_churn(db: Session, c: Customer, create_recommendations=True) -> dict:
    model, meta = get_model("customer_churn")
    f = customer_features(db, c)
    X = pd.DataFrame([f])[meta["features"]]
    p = float(model.predict_proba(X)[0, 1])
    level = risk_level(p)
    factors = [x for x in _tabular_explain(model, meta, f, CHURN_LABELS, CHURN_REFERENCE, top=5) if x["direction"] == "increases"][:4]
    actions = []
    if f["days_since_last_interaction"] > 30:
        actions.append("Schedule a customer check-in call.")
    if f["open_tickets"] > 0:
        actions.append(f"Resolve the {f['open_tickets']:.0f} open support ticket(s) for this customer.")
    if f["negative_sentiment_ratio"] > 0.3:
        actions.append("Review recent negative support interactions with the account owner.")
    if f["overdue_invoice_ratio"] > 0:
        actions.append("Follow up on overdue invoices with a friendly payment reminder.")
    if f["project_delay_ratio"] > 0:
        actions.append("Review the delayed project plan and agree a recovery timeline with the customer.")
    if not actions:
        actions.append("No action required - keep the regular cadence of contact.")
    # keep health fields in sync with the latest features
    c.health_score = Decimal(str(health_from_features(f)))
    c.health_status = health_status(float(c.health_score))
    explanation = {"summary": f"Churn probability {p:.0%} - risk level {level.upper()}.", "factors": factors,
                   "recommended_actions": actions, "business_rules": [f"Health score {c.health_score} ({c.health_status}) is "
                   "computed from recency, tickets, sentiment, projects, payments and feedback."], "disclaimer": DISCLAIMER}
    pred = _store(db, c.organization_id, "customer", c.id, "customer_churn", p, level, float(max(model.predict_proba(X)[0])), meta, explanation)
    if create_recommendations and level == "high":
        _recommend(db, c.organization_id, pred, "customer", c.id, f"{c.name}: high churn risk ({p:.0%})",
                   "; ".join(x["label"] for x in factors) or "Multiple risk signals", actions[0],
                   notify_users=[c.account_owner_id, *_owners_and_managers(db, c.organization_id)])
    return prediction_dict(pred)


def sentiment_trend(db: Session, org_id, customer_id) -> dict:
    rows = db.execute(select(Ticket.sentiment, Ticket.created_at).where(Ticket.customer_id == customer_id, Ticket.organization_id == org_id,
                                                                         Ticket.sentiment.is_not(None)).order_by(Ticket.created_at.desc()).limit(10)).all()
    counts = {"positive": 0, "neutral": 0, "negative": 0}
    for s, _ in rows:
        counts[s] = counts.get(s, 0) + 1
    return {"recent": [{"sentiment": s, "at": at.isoformat()} for s, at in reversed(rows)], "counts": counts}


# --------------------------------------------------------------------------- PROJECTS
PROJECT_LABELS = {
    "progress_pct": lambda v: f"Progress is {v:.0f}%",
    "elapsed_pct": lambda v: f"{v:.0f}% of the schedule has elapsed",
    "schedule_gap": lambda v: f"Progress is {abs(v):.0f} points {'behind' if v < 0 else 'ahead of'} schedule",
    "overdue_task_ratio": lambda v: f"{v:.0%} of tasks are overdue",
    "blocked_task_ratio": lambda v: f"{v:.0%} of tasks are blocked",
    "milestone_completion": lambda v: f"{v:.0%} of milestones completed",
    "remaining_days": lambda v: f"{v:.0f} day(s) remaining",
    "team_capacity_pct": lambda v: f"Team capacity usage {v:.0f}%",
}


def project_features(db: Session, p: Project) -> dict:
    org, today, now = p.organization_id, date.today(), _now()
    tasks = db.execute(select(Task.status, Task.due_date).where(Task.project_id == p.id, Task.organization_id == org,
                                                                Task.deleted_at.is_(None), Task.status != "cancelled")).all()
    n = len(tasks)
    overdue = sum(1 for s, d in tasks if d and d < now and s not in ("done", "cancelled"))
    blocked = sum(1 for s, _ in tasks if s == "blocked")
    ms = db.execute(select(Milestone.status).where(Milestone.project_id == p.id)).all()
    if p.start_date and p.due_date and p.due_date > p.start_date:
        elapsed = min(max((today - p.start_date).days / (p.due_date - p.start_date).days * 100, 0), 100)
    else:
        elapsed = 50.0
    progress = float(p.progress or 0)
    members = list(db.scalars(select(ProjectMember.user_id).where(ProjectMember.project_id == p.id)))
    cap = team_workload(db, org, user_ids=members) if members else []
    return {"progress_pct": progress, "elapsed_pct": elapsed, "schedule_gap": progress - elapsed,
            "overdue_task_ratio": overdue / n if n else 0.0, "blocked_task_ratio": blocked / n if n else 0.0,
            "milestone_completion": (sum(1 for (s,) in ms if s == "completed") / len(ms)) if ms else progress / 100,
            "remaining_days": float(max((p.due_date - today).days, 0)) if p.due_date else 90.0,
            "team_capacity_pct": float(np.mean([m["capacity_pct"] for m in cap])) if cap else 70.0}


def predict_project_delay(db: Session, p: Project, create_recommendations=True) -> dict:
    model, meta = get_model("project_delay")
    f = project_features(db, p)
    X = pd.DataFrame([f])[meta["features"]]
    prob = float(model.predict_proba(X)[0, 1])
    if p.status in ("completed", "archived"):
        prob = 0.0
    level = risk_level(prob)
    ref = {"progress_pct": f["progress_pct"], "elapsed_pct": f["elapsed_pct"], "schedule_gap": 0.0, "overdue_task_ratio": 0.0,
           "blocked_task_ratio": 0.0, "milestone_completion": min(1.0, f["elapsed_pct"] / 100), "remaining_days": f["remaining_days"],
           "team_capacity_pct": 75.0}
    factors = [x for x in _tabular_explain(model, meta, f, PROJECT_LABELS, ref, top=5) if x["direction"] == "increases"][:4]
    actions = []
    if f["overdue_task_ratio"] > 0:
        actions.append("Re-plan the overdue tasks and confirm new dates with the assignees.")
    if f["blocked_task_ratio"] > 0:
        actions.append("Unblock blocked tasks - resolve or escalate their dependencies.")
    if f["team_capacity_pct"] > 100:
        actions.append(f"Rebalance workload: team capacity usage is {f['team_capacity_pct']:.0f}%.")
    if f["schedule_gap"] < -10:
        actions.append(f"Progress is {abs(f['schedule_gap']):.0f} points behind schedule - review scope or deadline with the customer.")
    if not actions:
        actions.append("On track - keep monitoring.")
    p.delay_probability, p.risk_level = Decimal(str(round(prob, 4))), level
    explanation = {"summary": f"Delay probability {prob:.0%} - risk level {level.upper()}.", "factors": factors,
                   "recommended_actions": actions, "business_rules": ["Project status is never changed automatically; "
                   "a manager decides whether to mark it At Risk/Delayed."], "disclaimer": DISCLAIMER}
    pred = _store(db, p.organization_id, "project", p.id, "project_delay", prob, level, float(max(model.predict_proba(X)[0])), meta, explanation)
    if create_recommendations and level == "high" and p.status not in ("completed", "archived"):
        _recommend(db, p.organization_id, pred, "project", p.id, f"{p.name}: likely to miss its deadline ({prob:.0%})",
                   "; ".join(x["label"] for x in factors) or "Multiple schedule risk signals", actions[0],
                   notify_users=[p.owner_id, *_owners_and_managers(db, p.organization_id)])
    return prediction_dict(pred)


# --------------------------------------------------------------------------- TICKETS
CATEGORY_RULES = [("Billing", r"invoice|payment|billing|refund|charge"), ("Access", r"\blogin\b|password|\baccess\b|sign in|\blocked out\b"),
                  ("Bug", r"error|bug|crash|broken|not working|fail|outage|down"), ("Data", r"report|export|data|upload|import"),
                  ("Question", r"how do i|how to|question|\?")]


def suggest_category(text: str) -> str:
    t = text.lower()
    return next((name for name, rx in CATEGORY_RULES if re.search(rx, t)), "General")


def analyze_ticket(subject: str, description: str) -> dict:
    text = f"{subject}. {description}"
    s_model, s_meta = get_model("ticket_sentiment")
    p_model, p_meta = get_model("ticket_priority")
    sp = s_model.predict_proba([text])[0]
    sent = str(s_model.classes_[int(np.argmax(sp))])
    if float(max(sp)) < 0.5:  # too uncertain (e.g. unfamiliar wording) - do not assert a polarity
        sent = "neutral"
    pp = p_model.predict_proba([text])[0]
    prio = str(p_model.classes_[int(np.argmax(pp))])
    rules = []
    if sent == "negative" and float(max(sp)) >= 0.65 and prio == "low":
        prio = "medium"
        rules.append("Negative sentiment raised the suggested priority from Low to Medium.")
    return {"sentiment": sent, "sentiment_confidence": round(float(max(sp)), 4), "predicted_priority": prio,
            "priority_confidence": round(float(max(pp)), 4), "category": suggest_category(text),
            "sentiment_factors": _text_explain(s_model, text, sent), "priority_factors": _text_explain(p_model, text, prio),
            "business_rules": rules, "model_versions": {"sentiment": s_meta["version"], "priority": p_meta["version"]}}


def record_ticket_predictions(db: Session, t: Ticket, a: dict):
    rows = [("ticket_sentiment", "ticket_sentiment", a["sentiment"], a["sentiment_confidence"], a["sentiment_factors"], a["model_versions"]["sentiment"]),
            ("ticket_priority", "ticket_priority", a["predicted_priority"], a["priority_confidence"], a["priority_factors"], a["model_versions"]["priority"])]
    for ptype, mname, label, conf, factors, ver in rows:
        db.add(AIPrediction(organization_id=t.organization_id, entity_type="ticket", entity_id=t.id, prediction_type=ptype,
                            prediction_value=conf, risk_level=label, confidence=conf, model_name=mname, model_version=ver,
                            explanation={"summary": f"Predicted {label} ({conf:.0%} confidence).",
                                         "factors": [{"label": f"Key term '{f['term']}'", "impact": f["weight"]} for f in factors],
                                         "recommended_actions": ["Human review required - staff can override this prediction."],
                                         "business_rules": a["business_rules"], "disclaimer": DISCLAIMER}))


REPLIES = {
    "negative": "Hi {name}, I'm sorry for the trouble this has caused. I've escalated your request and will personally follow up "
                "with an update by {when}. Could you share any additional details (screenshots, steps, timing) to speed things up?",
    "neutral": "Hi {name}, thanks for getting in touch. I'm looking into this now and will update you by {when}.",
    "positive": "Hi {name}, thank you for the kind words! Let us know if there's anything else we can help with.",
}


def ticket_assist(t: Ticket, comments) -> dict:
    first = re.split(r"(?<=[.!?])\s", t.description.strip())[0][:240]
    n_pub = sum(1 for c in comments if not c.is_internal)
    summary = (f"Customer reports: {first} Category: {t.category or 'General'}; priority {t.priority}; status {t.status.replace('_', ' ')}; "
               f"{n_pub} public and {len(comments) - n_pub} internal comment(s).")
    when = {"critical": "within 4 hours", "high": "today", "medium": "tomorrow", "low": "this week"}[t.priority]
    return {"summary": summary, "suggested_reply": REPLIES.get(t.sentiment or "neutral", REPLIES["neutral"]).format(name="there", when=when),
            "is_draft": True, "note": "Draft only - review and edit before sending. Never sent automatically."}


# --------------------------------------------------------------------------- batch job
def run_all(db: Session, org_id) -> dict:
    """Scheduled/background refresh of all predictions for an organization (also exposed via POST /ai/run)."""
    n = {"leads": 0, "customers": 0, "projects": 0}
    for lead in db.scalars(select(Lead).where(Lead.organization_id == org_id, Lead.deleted_at.is_(None), Lead.status.notin_(["won", "lost"]))):
        score_lead(db, lead); n["leads"] += 1
    for c in db.scalars(select(Customer).where(Customer.organization_id == org_id, Customer.deleted_at.is_(None))):
        predict_churn(db, c); n["customers"] += 1
    for p in db.scalars(select(Project).where(Project.organization_id == org_id, Project.deleted_at.is_(None),
                                              Project.status.notin_(["completed", "archived"]))):
        predict_project_delay(db, p); n["projects"] += 1
    return n
