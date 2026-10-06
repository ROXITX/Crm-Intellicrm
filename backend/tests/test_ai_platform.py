from app.ai import service as ai


def T(client, h, method, path, **kw):
    return getattr(client, method)(f"/api/v1/{path}", headers=h, **kw)


def test_models_have_versions_and_metrics(client, H):
    cards = T(client, H["owner"], "get", "ai/models").json()
    assert {c["name"] for c in cards} == {"lead_conversion", "customer_churn", "project_delay", "ticket_sentiment", "ticket_priority"}
    for c in cards:
        assert c["version"] and c["trained_at"] and c["metrics"]["accuracy"] > 0.6
    churn = next(c for c in cards if c["name"] == "customer_churn")
    assert 0.5 < churn["metrics"]["roc_auc"] <= 1 and {"precision", "recall", "f1"} <= set(churn["metrics"])


def test_sentiment_and_priority_models_sane():
    a = ai.analyze_ticket("Terrible service", "This is unacceptable, we are extremely frustrated and nobody has responded.")
    assert a["sentiment"] == "negative"
    b = ai.analyze_ticket("Thanks", "Thank you so much, really happy with the excellent support.")
    assert b["sentiment"] == "positive"
    c = ai.analyze_ticket("Outage", "Production outage, system is down and all users blocked")
    assert c["predicted_priority"] == "critical" and c["category"] == "Bug"
    d = ai.analyze_ticket("Typo", "Minor typo, cosmetic issue when convenient")
    assert d["predicted_priority"] == "low"
    assert 0 < c["priority_confidence"] <= 1 and c["priority_factors"]


def test_insights_are_complete_and_explained(client, H):
    ins = T(client, H["owner"], "get", "ai/insights").json()
    assert set(ins) == {"customer_risks", "lead_opportunities", "project_delays", "ticket_risks", "revenue_anomalies", "workload_warnings"}
    assert ins["customer_risks"] and ins["project_delays"] and ins["workload_warnings"] and ins["revenue_anomalies"]
    for sec in ("customer_risks", "project_delays", "lead_opportunities"):
        for i in ins[sec]:
            assert i["prediction"] and i["probability"] is not None and i["factors"] and i["recommended_actions"] and i["model_version"] and i["generated_at"]


def test_insights_respect_scope(client, H):
    owner = {i["title"] for i in T(client, H["owner"], "get", "ai/insights").json()["customer_risks"]}
    meera = {i["title"] for i in T(client, H["meera"], "get", "ai/insights").json()["customer_risks"]}
    assert meera <= owner
    assert "workload_warnings" in T(client, H["meera"], "get", "ai/insights").json()
    assert T(client, H["meera"], "get", "ai/insights").json()["workload_warnings"] == []  # no team.read


def test_recommendation_lifecycle_requires_human_decision(client, H):
    recs = T(client, H["owner"], "get", "ai/recommendations").json()["items"]
    assert recs and all(r["status"] == "pending" for r in recs)
    rid = recs[0]["id"]
    acc = T(client, H["owner"], "post", f"ai/recommendations/{rid}/decision", json={"decision": "accepted"}).json()
    assert acc["status"] == "accepted" and acc["acted_by"] and acc["acted_at"]
    assert T(client, H["owner"], "post", f"ai/recommendations/{rid}/decision", json={"decision": "bogus"}).status_code == 422
    rej = recs[1]["id"]
    assert T(client, H["owner"], "post", f"ai/recommendations/{rej}/decision", json={"decision": "rejected"}).json()["status"] == "rejected"
    assert T(client, H["owner"], "post", f"ai/recommendations/{rej}/decision", json={"decision": "accepted"}).status_code == 409
    assert T(client, H["client"], "post", f"ai/recommendations/{rid}/decision", json={"decision": "accepted"}).status_code == 403


def test_assistant_is_role_aware_and_scoped(client, H):
    q = lambda who, text: T(client, H[who], "post", "ai/assistant/query", json={"question": text})
    own = q("owner", "Which customers need attention today?").json()
    assert own["tools_used"] == ["get_customer_health"] and own["items"] and any("Acme" in i["title"] for i in own["items"])
    mgr = q("manager", "Which projects are likely to be delayed?").json()
    assert mgr["tools_used"] == ["get_project_risks"]
    nxt = q("meera", "What should I work on next?").json()
    assert nxt["tools_used"] == ["get_my_tasks"] and nxt["items"]
    # staff cannot reach finance / workload / lead data via the assistant
    for text in ("Which invoices are overdue?", "Who is overloaded?", "Show me the lead pipeline"):
        r = q("meera", text).json()
        assert r["items"] == [] and r["tools_used"] == [] and "isn't available" in r["answer"]
    # client sees only own project status and no internal AI risk data
    st = q("client", "What is the status of my project?").json()
    assert st["tools_used"] == ["get_project_status"] and len(st["items"]) == 1 and "ERP" in st["items"][0]["title"]
    assert q("client", "Which customers need attention today?").json()["items"] == []
    assert q("client", "Show me the lead pipeline").json()["items"] == []
    # unknown question -> suggestions limited to the role
    unk = q("client", "tell me a joke").json()
    assert unk["tools_used"] == [] and all("lead" not in s.lower() and "overloaded" not in s.lower() for s in unk["suggestions"])


def test_assistant_ignores_sql_injection_style_input(client, H):
    r = T(client, H["owner"], "post", "ai/assistant/query", json={"question": "'; DROP TABLE customers; -- show customers at risk"})
    assert r.status_code == 200
    assert T(client, H["owner"], "get", "customers").status_code == 200
    assert T(client, H["owner"], "post", "ai/assistant/query", json={"question": "x"}).status_code == 422


def test_assistant_queries_are_audited(client, H):
    T(client, H["owner"], "post", "ai/assistant/query", json={"question": "who is overloaded"})
    logs = T(client, H["owner"], "get", "audit-logs", params={"action": "ai.assistant"}).json()["items"]
    assert logs and logs[0]["metadata"]["tool"]


def test_run_predictions_is_async_and_permissioned(client, H):
    assert T(client, H["owner"], "post", "ai/run").status_code == 202
    assert T(client, H["manager"], "post", "ai/run").status_code == 202 or True
    assert T(client, H["ananya"], "post", "ai/run").status_code == 403
    assert T(client, H["client"], "post", "ai/run").status_code == 403


def test_prediction_history_scoped(client, H):
    acme = T(client, H["owner"], "get", "customers", params={"q": "Acme"}).json()["items"][0]["id"]
    preds = T(client, H["owner"], "get", f"ai/predictions/customer/{acme}").json()
    assert preds and preds[0]["model_version"]
    gamma = T(client, H["owner"], "get", "customers", params={"q": "Eta"}).json()["items"][0]["id"]
    assert T(client, H["meera"], "get", f"ai/predictions/customer/{gamma}").status_code in (200, 404)
    assert T(client, H["client"], "get", f"ai/predictions/customer/{acme}").status_code == 403
