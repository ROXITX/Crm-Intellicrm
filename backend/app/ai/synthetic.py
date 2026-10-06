"""Synthetic training data (Stage A in PROJECT.md). Contains no personal data.

Labels are drawn from explicit, documented relationships plus noise, so the trained models learn
recognisable patterns. Replace with anonymised, consented production data (Stage C) when available.
"""
import numpy as np
import pandas as pd

SOURCES = ["referral", "website", "linkedin", "cold_outreach", "event", "other"]
SOURCE_BOOST = {"referral": 0.9, "event": 0.5, "website": 0.4, "linkedin": 0.1, "cold_outreach": -0.5, "other": -0.2}

LEAD_FEATURES = ["interactions_30d", "days_since_last_interaction", "inquiries", "proposal_requested", "pricing_page_visits",
                 "response_rate", "source_quality", "has_company", "log_estimated_value"]
CHURN_FEATURES = ["days_since_last_interaction", "tickets_90d", "open_tickets", "negative_sentiment_ratio",
                  "project_delay_ratio", "overdue_invoice_ratio", "interactions_30d", "avg_feedback"]
PROJECT_FEATURES = ["progress_pct", "elapsed_pct", "schedule_gap", "overdue_task_ratio", "blocked_task_ratio",
                    "milestone_completion", "remaining_days", "team_capacity_pct"]


def _sig(x):
    return 1 / (1 + np.exp(-x))


def lead_data(n=3000, seed=1) -> pd.DataFrame:
    r = np.random.default_rng(seed)
    d = pd.DataFrame({
        "interactions_30d": r.poisson(4, n), "days_since_last_interaction": r.integers(0, 90, n),
        "inquiries": r.poisson(1.2, n), "proposal_requested": r.binomial(1, 0.25, n),
        "pricing_page_visits": r.poisson(1.5, n), "response_rate": r.beta(2, 2, n),
        "source_quality": r.choice(list(SOURCE_BOOST.values()), n), "has_company": r.binomial(1, 0.7, n),
        "log_estimated_value": r.normal(10, 1.2, n)})
    z = (-1.6 + 0.18 * d.interactions_30d - 0.035 * d.days_since_last_interaction + 0.3 * d.inquiries + 1.4 * d.proposal_requested
         + 0.3 * d.pricing_page_visits + 1.6 * d.response_rate + 0.8 * d.source_quality + 0.3 * d.has_company
         + 0.1 * (d.log_estimated_value - 10) + r.normal(0, 0.6, n))
    d["label"] = (r.random(n) < _sig(z)).astype(int)
    return d


def churn_data(n=3000, seed=2) -> pd.DataFrame:
    r = np.random.default_rng(seed)
    d = pd.DataFrame({
        "days_since_last_interaction": r.integers(0, 120, n), "tickets_90d": r.poisson(2, n), "open_tickets": r.poisson(0.8, n),
        "negative_sentiment_ratio": r.beta(1.2, 4, n), "project_delay_ratio": r.beta(1.2, 4, n),
        "overdue_invoice_ratio": r.beta(1, 6, n), "interactions_30d": r.poisson(5, n), "avg_feedback": r.uniform(1, 5, n)})
    z = (-4.3 + 0.035 * d.days_since_last_interaction + 0.12 * d.tickets_90d + 0.35 * d.open_tickets + 2.4 * d.negative_sentiment_ratio
         + 1.8 * d.project_delay_ratio + 1.6 * d.overdue_invoice_ratio - 0.12 * d.interactions_30d - 0.35 * (d.avg_feedback - 3)
         + r.normal(0, 0.5, n))
    d["label"] = (r.random(n) < _sig(z)).astype(int)
    return d


def project_data(n=3000, seed=3) -> pd.DataFrame:
    r = np.random.default_rng(seed)
    elapsed = r.uniform(0, 100, n)
    progress = np.clip(elapsed + r.normal(-5, 20, n), 0, 100)
    d = pd.DataFrame({"progress_pct": progress, "elapsed_pct": elapsed, "schedule_gap": progress - elapsed,
                      "overdue_task_ratio": r.beta(1.2, 5, n), "blocked_task_ratio": r.beta(1, 8, n),
                      "milestone_completion": np.clip(progress / 100 + r.normal(0, 0.15, n), 0, 1),
                      "remaining_days": r.integers(0, 180, n), "team_capacity_pct": r.uniform(30, 140, n)})
    z = (-0.4 - 0.07 * d.schedule_gap + 3.2 * d.overdue_task_ratio + 3.5 * d.blocked_task_ratio - 1.5 * d.milestone_completion
         + 0.025 * (d.team_capacity_pct - 80) - 0.004 * d.remaining_days + 0.01 * d.elapsed_pct + r.normal(0, 0.6, n))
    d["label"] = (r.random(n) < _sig(z)).astype(int)
    return d


# ---- text corpora (sentiment / ticket priority) ----
_POS = ["thank you so much", "great work", "really happy with the service", "excellent support", "works perfectly now",
        "very pleased", "appreciate the quick help", "fantastic experience", "love the new dashboard", "smooth and easy"]
_NEG = ["this is unacceptable", "very disappointed", "still not working", "terrible service", "repeated failures",
        "missed the deadline again", "extremely frustrated", "worst experience", "nobody has responded", "completely broken",
        "we are losing money", "I want to cancel"]
_NEU = ["please find the attached report", "can you share the schedule", "what is the status", "need a copy of the invoice",
        "requesting a meeting next week", "how do I change my address", "please update the contact details", "checking in on progress"]
_TOPICS = ["the invoice", "the project portal", "the login page", "the report export", "the mobile app", "the integration",
           "the monthly report", "the account settings", "the data upload", "the dashboard"]
_CRIT = ["system is down", "production outage", "data loss", "security breach", "all users blocked", "payment failing for every customer"]
_HIGH = ["cannot access", "error blocks our work", "deadline at risk", "urgent", "major issue affecting the team", "not working since morning"]
_MED = ["intermittent error", "slow performance", "wrong value shown", "feature behaves unexpectedly", "needs fixing this week"]
_LOW = ["minor typo", "cosmetic issue", "how do I", "question about", "feature suggestion", "when convenient"]


def sentiment_data(n=1800, seed=4):
    r = np.random.default_rng(seed)
    rows = []
    for _ in range(n):
        label = r.choice(["positive", "neutral", "negative"], p=[0.3, 0.35, 0.35])
        pool = {"positive": _POS, "neutral": _NEU, "negative": _NEG}[label]
        parts = list(r.choice(pool, size=r.integers(1, 3), replace=False)) + [str(r.choice(_TOPICS))]
        if r.random() < 0.15:  # label noise via mixed signal
            parts.append(str(r.choice(_NEU)))
        r.shuffle(parts)
        if r.random() < 0.08:  # label noise: real tickets are ambiguous
            label = str(r.choice(["positive", "neutral", "negative"]))
        rows.append((" ".join(parts), label))
    return pd.DataFrame(rows, columns=["text", "label"])


def priority_data(n=2400, seed=5):
    r = np.random.default_rng(seed)
    pools = {"critical": _CRIT, "high": _HIGH, "medium": _MED, "low": _LOW}
    rows = []
    for _ in range(n):
        label = r.choice(list(pools), p=[0.1, 0.25, 0.35, 0.3])
        parts = [str(r.choice(pools[label])), str(r.choice(_TOPICS))]
        if r.random() < 0.2:
            parts.append(str(r.choice(_NEG if label in ("critical", "high") else _NEU)))
        r.shuffle(parts)
        if r.random() < 0.08:
            label = str(r.choice(list(pools)))
        rows.append((" ".join(parts), label))
    return pd.DataFrame(rows, columns=["text", "label"])
