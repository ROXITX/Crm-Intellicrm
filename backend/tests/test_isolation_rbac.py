"""Organization isolation, role permissions and client-visibility rules (security-critical)."""
import uuid


def _first(client, h, path, **params):
    r = client.get(f"/api/v1/{path}", headers=h, params=params)
    assert r.status_code == 200, r.text
    return r.json()["items"]


def test_cross_org_cannot_see_data(client, H, other_org):
    for path in ("customers", "leads", "projects", "tasks", "tickets", "invoices", "documents"):
        assert _first(client, other_org, path) == [], path
    owner_customer = _first(client, H["owner"], "customers")[0]["id"]
    assert client.get(f"/api/v1/customers/{owner_customer}", headers=other_org).status_code == 404
    lead = _first(client, H["owner"], "leads")[0]["id"]
    assert client.get(f"/api/v1/leads/{lead}", headers=other_org).status_code == 404
    assert client.patch(f"/api/v1/leads/{lead}", headers=other_org, json={"name": "hijack"}).status_code == 404
    inv = _first(client, H["owner"], "invoices")[0]["id"]
    assert client.get(f"/api/v1/invoices/{inv}", headers=other_org).status_code == 404
    assert client.post(f"/api/v1/invoices/{inv}/payments", headers=other_org, json={"amount": "1"}).status_code == 404


def test_cross_org_references_rejected(client, H, other_org):
    cust = _first(client, H["owner"], "customers")[0]["id"]
    r = client.post("/api/v1/projects", headers=other_org, json={"customer_id": cust, "name": "Steal"})
    assert r.status_code == 404
    r = client.post("/api/v1/tickets", headers=other_org, json={"customer_id": cust, "subject": "hello there", "description": "hello there"})
    assert r.status_code == 404


def test_org_id_from_client_is_ignored(client, H, other_org):
    other_org_id = client.get("/api/v1/auth/me", headers=H["owner"]).json()["organization"]["id"]
    r = client.post("/api/v1/leads", headers=other_org, json={"name": "Injected", "organization_id": other_org_id})
    assert r.status_code == 201
    assert all(l["name"] != "Injected" for l in _first(client, H["owner"], "leads", q="Injected"))


def test_staff_sees_only_assigned(client, H):
    owner_total = client.get("/api/v1/customers", headers=H["owner"], params={"page_size": 100}).json()["total"]
    staff_total = client.get("/api/v1/customers", headers=H["meera"], params={"page_size": 100}).json()["total"]
    assert 0 < staff_total < owner_total
    ids = {c["id"] for c in _first(client, H["owner"], "customers", page_size=100)} - {c["id"] for c in _first(client, H["meera"], "customers", page_size=100)}
    hidden = next(iter(ids))
    assert client.get(f"/api/v1/customers/{hidden}", headers=H["meera"]).status_code == 404


def test_staff_has_no_lead_or_invoice_access(client, H):
    assert client.get("/api/v1/leads", headers=H["ananya"]).status_code == 403
    assert client.get("/api/v1/invoices", headers=H["ananya"]).status_code == 403
    assert client.get("/api/v1/audit-logs", headers=H["ananya"]).status_code == 403
    assert client.get("/api/v1/team", headers=H["ananya"]).status_code == 403


def test_manager_cannot_manage_team_or_audit(client, H):
    assert client.get("/api/v1/audit-logs", headers=H["manager"]).status_code == 403
    r = client.post("/api/v1/team/members", headers=H["manager"], json={"email": "x@y.example", "first_name": "X", "role": "staff", "password": "Passw0rd!123"})
    assert r.status_code == 403


def test_client_scoped_to_own_account(client, H):
    custs = _first(client, H["client"], "customers")
    assert len(custs) == 1 and custs[0]["name"] == "Acme Industries"
    assert "health_score" not in custs[0] and "notes" not in custs[0]
    assert client.get("/api/v1/leads", headers=H["client"]).status_code == 403
    assert client.get("/api/v1/tasks", headers=H["client"]).status_code == 403
    assert client.get("/api/v1/team", headers=H["client"]).status_code == 403
    assert client.get("/api/v1/dashboard", headers=H["client"]).status_code in (200, 403)
    projects = _first(client, H["client"], "projects")
    assert projects and all("delay_probability" not in p and "risk_level" not in p for p in projects)
    # cannot reach another client's project
    other = _first(client, H["client2"], "projects")
    assert other
    assert client.get(f"/api/v1/projects/{other[0]['id']}", headers=H["client"]).status_code == 404


def test_client_cannot_see_internal_comments_or_ai_fields(client, H):
    tickets = _first(client, H["client"], "tickets")
    assert tickets and all("sentiment" not in t and "predicted_priority" not in t for t in tickets)
    t = next(t for t in tickets if t["subject"].startswith("Repeated failures"))
    detail = client.get(f"/api/v1/tickets/{t['id']}", headers=H["client"]).json()
    assert all(not c["is_internal"] for c in detail["comments"])
    assert not any("INTERNAL" in c["body"] for c in detail["comments"])
    staff_detail = client.get(f"/api/v1/tickets/{t['id']}", headers=H["owner"]).json()
    assert any(c["is_internal"] for c in staff_detail["comments"])
    r = client.post(f"/api/v1/tickets/{t['id']}/comments", headers=H["client"], json={"body": "secret", "is_internal": True})
    assert r.status_code == 403


def test_client_sees_no_draft_invoices_and_only_own(client, H):
    inv = _first(client, H["client"], "invoices", page_size=100)
    assert inv and all(i["status"] != "draft" for i in inv)
    assert {i["customer_name"] for i in inv} == {"Acme Industries"}
    r = client.post("/api/v1/invoices", headers=H["client"], json={"customer_id": inv[0]["customer_id"], "due_date": "2030-01-01", "items": [{"description": "x", "quantity": "1", "unit_price": "1"}]})
    assert r.status_code == 403


def test_client_cannot_use_ai_insights(client, H):
    assert client.get("/api/v1/ai/insights", headers=H["client"]).status_code == 403
    assert client.get("/api/v1/ai/models", headers=H["client"]).status_code == 403


def test_privilege_escalation_blocked(client, H):
    uid = client.get("/api/v1/auth/me", headers=H["ananya"]).json()["id"]
    assert client.patch(f"/api/v1/team/members/{uid}", headers=H["ananya"], json={"role": "owner"}).status_code == 403
    assert client.patch(f"/api/v1/team/members/{uid}", headers=H["manager"], json={"role": "owner"}).status_code == 403


def test_last_owner_protected(client, H):
    uid = client.get("/api/v1/auth/me", headers=H["owner"]).json()["id"]
    r = client.patch(f"/api/v1/team/members/{uid}", headers=H["owner"], json={"role": "staff"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "LAST_OWNER"


def test_error_format_not_found(client, H):
    r = client.get(f"/api/v1/customers/{uuid.uuid4()}", headers=H["owner"])
    assert r.status_code == 404
    assert set(r.json()["error"]) >= {"code", "message", "request_id"} and r.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
