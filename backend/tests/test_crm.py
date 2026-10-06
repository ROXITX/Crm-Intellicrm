import io
import uuid


def T(client, h, method, path, **kw):
    return getattr(client, method)(f"/api/v1/{path}", headers=h, **kw)


def test_lead_crud_scoring_and_validation(client, H):
    r = T(client, H["owner"], "post", "leads", json={"name": "Test Prospect", "company_name": "TP Ltd", "email": "tp@prospect.example", "source": "referral", "estimated_value": "150000.50"})
    assert r.status_code == 201, r.text
    lead = r.json()
    assert 0 <= float(lead["score"]) <= 100 and 0 <= float(lead["score_probability"]) <= 1
    assert T(client, H["owner"], "post", "leads", json={"name": "", "email": "nope"}).status_code == 422
    assert T(client, H["owner"], "post", "leads", json={"name": "Neg", "estimated_value": "-5"}).status_code == 422
    assert T(client, H["owner"], "post", "leads", json={"name": "BadStatus", "status": "weird"}).status_code == 422
    # interactions change the score and the explanation is always present
    before = float(lead["score"])
    for t in ("proposal_requested", "pricing_page", "inquiry", "email", "reply"):
        assert T(client, H["owner"], "post", f"leads/{lead['id']}/interactions", json={"type": t}).status_code == 201
    d = T(client, H["owner"], "get", f"leads/{lead['id']}").json()
    assert float(d["score"]) > before
    ex = d["score_explanation"]
    assert ex["factors"] and ex["recommended_actions"] and ex["model_name"] == "lead_conversion" and ex["model_version"] and ex["disclaimer"]
    assert len(d["interactions"]) == 5


def test_lead_filters_sorting_pagination(client, H):
    r = T(client, H["owner"], "get", "leads", params={"page_size": 5, "sort": "score", "order": "desc"}).json()
    assert r["page_size"] == 5 and len(r["items"]) == 5 and r["total"] >= 30
    scores = [float(i["score"]) for i in r["items"] if i["score"] is not None]
    assert scores == sorted(scores, reverse=True)
    assert T(client, H["owner"], "get", "leads", params={"page_size": 1000}).status_code == 422
    won = T(client, H["owner"], "get", "leads", params={"status": "won", "page_size": 100}).json()["items"]
    assert all(l["status"] == "won" for l in won)


def test_lead_conversion_is_atomic_and_keeps_history(client, H):
    lead = T(client, H["owner"], "post", "leads", json={"name": "Convert Me", "company_name": "CM Inc", "email": "cm@prospect.example", "source": "event"}).json()
    T(client, H["owner"], "post", f"leads/{lead['id']}/interactions", json={"type": "call"})
    r = T(client, H["owner"], "post", f"leads/{lead['id']}/convert")
    assert r.status_code == 201, r.text
    cust = r.json()["customer"]
    assert cust["name"] == "Convert Me" and cust["source_lead_id"] == lead["id"]
    d = T(client, H["owner"], "get", f"leads/{lead['id']}").json()
    assert d["status"] == "won" and d["converted_customer_id"] == cust["id"] and len(d["interactions"]) == 1
    assert T(client, H["owner"], "post", f"leads/{lead['id']}/convert").status_code == 409
    assert T(client, H["owner"], "get", f"customers/{cust['id']}").status_code == 200


def test_lead_archive_hides(client, H):
    lead = T(client, H["owner"], "post", "leads", json={"name": "Archive Me"}).json()
    assert T(client, H["owner"], "delete", f"leads/{lead['id']}").status_code == 204
    assert T(client, H["owner"], "get", f"leads/{lead['id']}").status_code == 404


def test_lead_csv_import_preview_confirm_export(client, H):
    csv = "name,company_name,email,source,status,estimated_value\nCSV One,Co1,one@csv.example,website,new,1000\nCSV Two,Co2,not-an-email,website,new,5\n"
    f = {"file": ("leads.csv", io.BytesIO(csv.encode()), "text/csv")}
    prev = T(client, H["owner"], "post", "leads/import", files=f).json()
    assert prev["valid_rows"] == 1 and len(prev["errors"]) == 1 and prev["errors"][0]["row"] == 3 and prev["imported"] == 0
    f = {"file": ("leads.csv", io.BytesIO(csv.encode()), "text/csv")}
    assert T(client, H["owner"], "post", "leads/import", params={"confirm": True}, files=f).status_code == 400  # errors block import
    good = "name,email\nCSV Good,good@csv.example\n"
    f = {"file": ("g.csv", io.BytesIO(good.encode()), "text/csv")}
    done = T(client, H["owner"], "post", "leads/import", params={"confirm": True}, files=f).json()
    assert done["imported"] == 1
    bad_header = {"file": ("b.csv", io.BytesIO(b"foo,bar\n1,2\n"), "text/csv")}
    assert T(client, H["owner"], "post", "leads/import", files=bad_header).status_code == 400
    exp = T(client, H["owner"], "get", "leads/export")
    assert exp.status_code == 200 and "CSV Good" in exp.text and exp.headers["content-type"].startswith("text/csv")


def test_csv_formula_injection_neutralised(client, H):
    T(client, H["owner"], "post", "leads", json={"name": "=HYPERLINK(\"http://evil\")"})
    exp = T(client, H["owner"], "get", "leads/export").text
    assert "'=HYPERLINK" in exp and ",=HYPERLINK" not in exp


def test_customer_crud_contacts_360(client, H):
    c = T(client, H["manager"], "post", "customers", json={"name": "New Customer", "email": "nc@cust.example", "industry": "Retail"}).json()
    assert T(client, H["manager"], "post", f"customers/{c['id']}/contacts", json={"name": "Jane", "email": "jane@cust.example", "is_primary": True}).status_code == 201
    d = T(client, H["manager"], "get", f"customers/{c['id']}").json()
    assert d["contacts"][0]["name"] == "Jane" and "ai" in d
    assert T(client, H["manager"], "patch", f"customers/{c['id']}", json={"name": "Renamed"}).json()["name"] == "Renamed"
    assert T(client, H["manager"], "patch", f"customers/{c['id']}", json={"name": None}).status_code == 400
    assert T(client, H["manager"], "patch", f"customers/{c['id']}", json={"account_owner_id": str(uuid.uuid4())}).status_code == 400
    assert T(client, H["manager"], "delete", f"customers/{c['id']}").status_code == 204
    assert T(client, H["manager"], "get", f"customers/{c['id']}").status_code == 404


def test_customer_list_filters_and_health(client, H):
    r = T(client, H["owner"], "get", "customers", params={"health": "at_risk"}).json()
    for c in r["items"]:
        assert c["health_status"] == "at_risk"
    all_ = T(client, H["owner"], "get", "customers", params={"page_size": 100}).json()["items"]
    assert all({"project_count", "open_tickets"} <= set(c) for c in all_)
    acme = next(c for c in all_ if c["name"] == "Acme Industries")
    assert acme["health_status"] in ("at_risk", "critical", "watch") and acme["open_tickets"] >= 3


def test_customer_churn_prediction_is_explainable(client, H):
    acme = next(c for c in T(client, H["owner"], "get", "customers", params={"q": "Acme"}).json()["items"])
    d = T(client, H["owner"], "get", f"customers/{acme['id']}").json()
    churn = d["ai"]["churn"]
    assert churn["probability"] >= 0.5 and churn["risk_level"] == "high"
    assert churn["factors"] and churn["recommended_actions"] and churn["model_name"] == "customer_churn" and churn["confidence"] is not None
    assert any("41" in f["label"] or "ticket" in f["label"].lower() for f in churn["factors"])


def test_portal_user_creation_requires_permission(client, H):
    acme = next(c for c in T(client, H["owner"], "get", "customers", params={"q": "Eta"}).json()["items"])
    body = {"email": "p@eta-health.example", "first_name": "P", "password": "Portal@12345"}
    assert T(client, H["manager"], "post", f"customers/{acme['id']}/portal-users", json=body).status_code == 403
    assert T(client, H["owner"], "post", f"customers/{acme['id']}/portal-users", json=body).status_code == 201
    assert T(client, H["owner"], "post", f"customers/{acme['id']}/portal-users", json=body).status_code == 409
    tok = client.post("/api/v1/auth/login", json={"email": "p@eta-health.example", "password": "Portal@12345"}).json()["access_token"]
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tok}"}).json()
    assert me["role"] == "client"
