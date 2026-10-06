def T(client, h, method, path, **kw):
    return getattr(client, method)(f"/api/v1/{path}", headers=h, **kw)


def test_dashboard_owner_shape(client, H):
    d = T(client, H["owner"], "get", "dashboard").json()
    assert set(d["kpis"]) >= {"total_customers", "new_leads", "active_projects", "at_risk_customers", "revenue"}
    assert d["kpis"]["total_customers"]["value"] >= 8
    assert [f["stage"] for f in d["funnel"]] == ["new", "contacted", "qualified", "proposal", "won"]
    assert d["funnel"][0]["conversion_pct"] == 100.0 and d["funnel"][0]["count"] >= d["funnel"][-1]["count"]
    assert d["attention_required"] and {"severity", "title", "reason", "action"} <= set(d["attention_required"][0])
    assert d["team_workload"] and set(d["project_status"]) == {"on_track", "at_risk", "delayed", "completed"}
    assert d["recent_activity"] and d["insights"]["customers_need_attention"] >= 1
    for r in ("7D", "30D", "90D", "12M"):
        assert T(client, H["owner"], "get", "dashboard", params={"range": r}).status_code == 200
    assert T(client, H["owner"], "get", "dashboard", params={"range": "1Y"}).status_code == 422


def test_dashboard_scoped_for_staff(client, H):
    d = T(client, H["meera"], "get", "dashboard").json()
    assert "revenue" not in d["kpis"] and "new_leads" not in d["kpis"] and "team_workload" not in d and "revenue_pipeline" not in d
    assert d["kpis"]["total_customers"]["value"] < T(client, H["owner"], "get", "dashboard").json()["kpis"]["total_customers"]["value"]
    assert d["my_work"]["open_tasks"] >= 10


def test_portal_home(client, H):
    h = T(client, H["client"], "get", "portal/home").json()
    assert h["customer_name"] == "Acme Industries" and h["projects"] and h["open_requests"] >= 3
    assert all("risk_level" not in p for p in h["projects"])
    assert T(client, H["owner"], "get", "portal/home").status_code == 403


def test_search_permissions_and_scope(client, H, other_org):
    r = T(client, H["owner"], "get", "search", params={"q": "acme"}).json()["results"]
    assert {x["type"] for x in r} >= {"customer", "project"}
    r2 = T(client, H["owner"], "get", "search", params={"q": "migrat"}).json()["results"]
    assert any(x["type"] == "task" for x in r2) and any(x["type"] == "project" for x in r2)  # prefix match
    assert T(client, other_org, "get", "search", params={"q": "acme"}).json()["results"] == []
    client_hits = T(client, H["client"], "get", "search", params={"q": "migration"}).json()["results"]
    assert all(x["type"] in ("project", "ticket", "invoice", "message", "customer") for x in client_hits)
    assert not any(x["type"] == "task" for x in client_hits)
    staff = T(client, H["meera"], "get", "search", params={"q": "lead"}).json()["results"]
    assert not any(x["type"] == "lead" for x in staff)
    assert T(client, H["owner"], "get", "search", params={"q": "a"}).status_code == 422
    # query is parameterised
    assert T(client, H["owner"], "get", "search", params={"q": "x'); drop table users;--"}).status_code == 200


def test_search_uses_fulltext_index(client):
    from sqlalchemy import text
    from app.core.db import engine
    with engine.begin() as c:
        c.execute(text("SET enable_seqscan = off"))
        plan = "\n".join(r[0] for r in c.execute(text("EXPLAIN SELECT id FROM customers WHERE to_tsvector('simple'::regconfig, coalesce(name,'') || ' ' || coalesce(company_name,'') || ' ' || coalesce(email,'')) @@ to_tsquery('simple'::regconfig, 'acme:*')")))
    assert "idx_customers_fts" in plan


def test_reports_rbac_and_csv(client, H):
    for name in ("lead_funnel", "conversion", "customer_health", "churn_risk", "project_performance", "support_performance", "revenue", "overdue_invoices", "workload", "ai_accuracy"):
        r = T(client, H["owner"], "get", f"reports/{name}")
        assert r.status_code == 200, name
        assert r.json()["columns"]
    assert T(client, H["owner"], "get", "reports/overdue_invoices").json()["rows"]
    csv = T(client, H["owner"], "get", "reports/revenue", params={"format": "csv"})
    assert csv.headers["content-type"].startswith("text/csv") and csv.text.startswith("month,revenue")
    assert T(client, H["manager"], "get", "reports/workload").status_code == 200
    assert T(client, H["manager"], "get", "reports/bogus").status_code == 422
    assert T(client, H["meera"], "get", "reports/revenue").status_code == 403
    assert T(client, H["client"], "get", "reports/revenue").status_code == 403


def test_report_isolation(client, other_org):
    assert T(client, other_org, "get", "reports/customer_health").json()["rows"] == []
    assert T(client, other_org, "get", "reports/overdue_invoices").json()["rows"] == []


def test_audit_log_records_sensitive_actions(client, H):
    logs = T(client, H["owner"], "get", "audit-logs", params={"page_size": 100}).json()["items"]
    actions = {l["action"] for l in logs}
    assert {"auth.login", "lead.convert", "payment.record", "invoice.create", "team.permission_change"} & actions
    pay = next(l for l in logs if l["action"] == "payment.record")
    assert pay["before_data"] and pay["after_data"] and pay["actor_id"] and pay["metadata"]["ip"] is not None
    assert T(client, H["owner"], "get", "audit-logs", params={"action": "lead."}).json()["total"] >= 1


def test_audit_logs_org_scoped(client, other_org):
    items = T(client, other_org, "get", "audit-logs", params={"page_size": 100}).json()["items"]
    assert items and all(l["actor_email"] in ("eve@rival.example", None) for l in items)
    assert not {"payment.record", "lead.convert", "invoice.create"} & {l["action"] for l in items}


def test_org_settings_and_profile(client, H):
    assert T(client, H["owner"], "patch", "settings/organization", json={"phone": "+91 11 2222 3333"}).json()["phone"] == "+91 11 2222 3333"
    assert T(client, H["manager"], "get", "settings/organization").status_code == 403
    r = T(client, H["manager"], "patch", "me", json={"notification_preferences": {"message": False}})
    assert r.json()["preferences"]["notifications"] == {"message": False}


def test_notification_preferences_respected(client, H):
    T(client, H["manager"], "patch", "me", json={"notification_preferences": {"assignment": False}})
    me = T(client, H["manager"], "get", "auth/me").json()["id"]
    before = T(client, H["manager"], "get", "notifications").json()["total"]
    T(client, H["owner"], "post", "tasks", json={"title": "Muted assignment", "assignee_id": me})
    assert T(client, H["manager"], "get", "notifications").json()["total"] == before
    T(client, H["manager"], "patch", "me", json={"notification_preferences": {}})


def test_password_change_revokes_sessions(client):
    r = client.post("/api/v1/auth/register", json={"organization_name": "PW Org", "first_name": "P", "email": "pw@pworg.example", "password": "OldPassword#1"})
    tok = r.json()["access_token"]; refresh = r.json()["refresh_token"]
    h = {"Authorization": f"Bearer {tok}"}
    assert client.post("/api/v1/me/password", headers=h, json={"current_password": "wrong-password", "new_password": "NewPassword#12"}).status_code == 400
    assert client.post("/api/v1/me/password", headers=h, json={"current_password": "OldPassword#1", "new_password": "NewPassword#12"}).status_code == 204
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": refresh}).status_code == 401
    assert client.post("/api/v1/auth/login", json={"email": "pw@pworg.example", "password": "NewPassword#12"}).status_code == 200


def test_health_endpoint_and_request_id(client):
    r = client.get("/api/health", headers={"x-request-id": "abc123"})
    assert r.json() == {"status": "ok"} and r.headers["x-request-id"] == "abc123"


def test_unhandled_errors_do_not_leak(client, H):
    r = client.get("/api/v1/customers/not-a-uuid", headers=H["owner"])
    assert r.status_code == 422 and "Traceback" not in r.text
