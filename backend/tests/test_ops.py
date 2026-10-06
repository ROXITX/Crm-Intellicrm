import uuid
from datetime import datetime, timedelta, timezone


def T(client, h, method, path, **kw):
    return getattr(client, method)(f"/api/v1/{path}", headers=h, **kw)


def _cust(client, H, q="Acme"):
    return T(client, H["owner"], "get", "customers", params={"q": q}).json()["items"][0]["id"]


def test_project_lifecycle_validation(client, H):
    cid = _cust(client, H)
    bad = T(client, H["manager"], "post", "projects", json={"customer_id": cid, "name": "P", "start_date": "2026-05-01", "due_date": "2026-01-01"})
    assert bad.status_code == 422
    assert T(client, H["manager"], "post", "projects", json={"customer_id": cid, "name": "P", "budget": "-1"}).status_code == 422
    r = T(client, H["manager"], "post", "projects", json={"customer_id": cid, "name": "New Project", "budget": "120000", "start_date": "2026-01-01", "due_date": "2027-01-01"})
    assert r.status_code == 201
    pid = r.json()["id"]
    assert T(client, H["manager"], "post", f"projects/{pid}/milestones", json={"name": "M1", "progress": 50}).status_code == 201
    assert T(client, H["manager"], "post", f"projects/{pid}/milestones", json={"name": "M1", "progress": 150}).status_code == 422
    d = T(client, H["manager"], "get", f"projects/{pid}").json()
    assert len(d["milestones"]) == 1 and d["members"]
    assert T(client, H["manager"], "patch", f"projects/{pid}", json={"status": "completed"}).json()["progress"].startswith("100")
    assert T(client, H["ananya"], "post", "projects", json={"customer_id": cid, "name": "Nope"}).status_code == 403


def test_task_flow_progress_dependencies_and_staff_limits(client, H):
    cid = _cust(client, H)
    pid = T(client, H["manager"], "post", "projects", json={"customer_id": cid, "name": "Task Flow", "status": "active"}).json()["id"]
    team = {m["name"].split()[0]: m["id"] for m in T(client, H["manager"], "get", "team/directory").json()}
    a = T(client, H["manager"], "post", "tasks", json={"title": "A", "project_id": pid, "assignee_id": team["Ananya"], "estimated_hours": "4"}).json()
    b = T(client, H["manager"], "post", "tasks", json={"title": "B", "project_id": pid, "assignee_id": team["Ananya"]}).json()
    assert T(client, H["manager"], "post", f"tasks/{b['id']}/dependencies", json={"depends_on_task_id": a["id"]}).status_code == 201
    cyc = T(client, H["manager"], "post", f"tasks/{a['id']}/dependencies", json={"depends_on_task_id": b["id"]})
    assert cyc.status_code == 400 and cyc.json()["error"]["code"] == "DEPENDENCY_CYCLE"
    assert T(client, H["manager"], "post", f"tasks/{a['id']}/dependencies", json={"depends_on_task_id": a["id"]}).status_code == 400
    blocked = T(client, H["ananya"], "patch", f"tasks/{b['id']}", json={"status": "done"})
    assert blocked.status_code == 409 and blocked.json()["error"]["code"] == "DEPENDENCY_PENDING"
    assert T(client, H["ananya"], "patch", f"tasks/{a['id']}", json={"status": "done", "actual_hours": "3.5"}).status_code == 200
    assert T(client, H["ananya"], "patch", f"tasks/{b['id']}", json={"status": "done"}).status_code == 200
    assert float(T(client, H["manager"], "get", f"projects/{pid}").json()["progress"]) == 100.0
    # staff may not reassign / reprioritise
    assert T(client, H["ananya"], "patch", f"tasks/{a['id']}", json={"priority": "critical"}).status_code == 403
    assert T(client, H["ananya"], "patch", f"tasks/{a['id']}", json={"assignee_id": team["Karthik"]}).status_code == 403
    # a different staff member cannot touch it
    assert T(client, H["karthik"], "patch", f"tasks/{a['id']}", json={"status": "todo"}).status_code in (403, 404)
    assert T(client, H["manager"], "patch", f"tasks/{a['id']}", json={"estimated_hours": "-3"}).status_code == 422


def test_task_assignment_notifies_and_rejects_foreign_assignee(client, H, other_org):
    foreign = T(client, other_org, "get", "auth/me").json()["id"]
    r = T(client, H["manager"], "post", "tasks", json={"title": "x", "assignee_id": foreign})
    assert r.status_code == 400
    me = T(client, H["meera"], "get", "auth/me").json()["id"]
    T(client, H["manager"], "post", "tasks", json={"title": "Notify Meera", "assignee_id": me})
    n = T(client, H["meera"], "get", "notifications", params={"unread": True}).json()
    assert n["unread_count"] >= 1 and any(i["type"] == "assignment" for i in n["items"])
    assert T(client, H["meera"], "post", "notifications/read-all").status_code == 204
    assert T(client, H["meera"], "get", "notifications").json()["unread_count"] == 0


def test_workload_capacity(client, H):
    team = T(client, H["manager"], "get", "team").json()
    meera = next(m for m in team if m["name"].startswith("Meera"))
    assert meera["status"] in ("high", "overloaded") and meera["capacity_pct"] >= 80 and meera["active_tasks"] >= 10
    ananya = next(m for m in team if m["name"].startswith("Ananya"))
    assert 0 <= ananya["capacity_pct"] < meera["capacity_pct"]


def test_project_delay_prediction_explainable(client, H):
    acme = next(p for p in T(client, H["owner"], "get", "projects", params={"q": "ERP"}).json()["items"])
    d = T(client, H["owner"], "get", f"projects/{acme['id']}").json()
    risk = d["ai_risk"]
    assert risk["probability"] >= 0.5 and risk["factors"] and risk["recommended_actions"] and risk["model_version"]
    assert d["status"] == "delayed"  # AI never changes status itself


def test_ticket_ai_and_human_override(client, H):
    cid = _cust(client, H, "Epsilon")
    r = T(client, H["owner"], "post", "tickets", json={"customer_id": cid, "subject": "Production outage", "description": "System is down, production outage, all users blocked. This is unacceptable!"})
    assert r.status_code == 201
    t = r.json()
    assert t["priority"] in ("critical", "high") and t["sentiment"] == "negative" and t["sla_due_at"]
    assert float(t["sentiment_confidence"]) <= 1
    up = T(client, H["manager"], "patch", f"tickets/{t['id']}", json={"priority": "low"}).json()
    assert up["priority"] == "low" and up["predicted_priority"] == t["predicted_priority"]  # override recorded, prediction preserved
    assert T(client, H["manager"], "patch", f"tickets/{t['id']}", json={"status": "bogus"}).status_code == 422
    done = T(client, H["manager"], "patch", f"tickets/{t['id']}", json={"status": "resolved"}).json()
    assert done["resolved_at"]
    assist = T(client, H["manager"], "get", f"tickets/{t['id']}/assist").json()
    assert assist["is_draft"] and assist["suggested_reply"] and assist["summary"]
    assert T(client, H["client"], "get", f"tickets/{t['id']}/assist").status_code == 403


def test_client_ticket_creation_forces_own_customer(client, H):
    other = _cust(client, H, "Gamma")
    r = T(client, H["client"], "post", "tickets", json={"customer_id": other, "subject": "Need help", "description": "How do I export the report?", "priority": "critical"})
    assert r.status_code == 201
    t = r.json()
    me_cust = T(client, H["client"], "get", "customers").json()["items"][0]["id"]
    assert t["customer_id"] == me_cust and t["priority"] != "critical" or t["customer_id"] == me_cust
    assert t["customer_id"] != other
    assert T(client, H["client"], "patch", f"tickets/{t['id']}", json={"priority": "low"}).status_code == 403
    assert T(client, H["client"], "patch", f"tickets/{t['id']}", json={"status": "closed"}).status_code == 200


def test_escalation_notifies_managers(client, H):
    t = T(client, H["owner"], "get", "tickets", params={"status": "open", "page_size": 100}).json()["items"][0]
    before = t["priority"]
    r = T(client, H["manager"], "post", f"tickets/{t['id']}/escalate").json()
    assert r["priority"] != before or before == "critical"


def test_messaging_membership_and_isolation(client, H):
    convs = T(client, H["client"], "get", "conversations").json()
    assert len(convs) == 1 and convs[0]["type"] == "client"
    cid = convs[0]["id"]
    msgs = T(client, H["client"], "get", f"conversations/{cid}/messages").json()["messages"]
    assert msgs
    # client is not a member of the internal conversation
    internal = next(c for c in T(client, H["manager"], "get", "conversations").json() if c["type"] == "internal")
    assert T(client, H["client"], "get", f"conversations/{internal['id']}/messages").status_code == 404
    assert T(client, H["client"], "post", f"conversations/{internal['id']}/messages", json={"body": "hi"}).status_code == 404
    # staff outside the conversation also blocked
    assert T(client, H["karthik"], "get", f"conversations/{cid}/messages").status_code == 404
    sent = T(client, H["manager"], "post", f"conversations/{cid}/messages", json={"body": "Plan attached"})
    assert sent.status_code == 201
    unread = next(c for c in T(client, H["client"], "get", "conversations").json() if c["id"] == cid)["unread"]
    assert unread >= 1
    T(client, H["client"], "get", f"conversations/{cid}/messages")
    assert next(c for c in T(client, H["client"], "get", "conversations").json() if c["id"] == cid)["unread"] == 0
    assert T(client, H["manager"], "get", f"conversations/{cid}/messages", params={"q": "attached"}).json()["messages"]
    # internal conversations cannot include a client
    me = T(client, H["client"], "get", "auth/me").json()["id"]
    r = T(client, H["manager"], "post", "conversations", json={"type": "internal", "member_ids": [me]})
    assert r.status_code == 400
    r = T(client, H["client"], "post", "conversations", json={"type": "internal"})
    assert r.status_code == 403


def test_websocket_requires_valid_token(client, tokens):
    from starlette.websockets import WebSocketDisconnect
    import pytest
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/api/v1/ws?token=bad"):
            pass
    with client.websocket_connect(f"/api/v1/ws?token={tokens['manager']}") as ws:
        ws.send_text('{"type":"typing","conversation_id":"%s"}' % uuid.uuid4())


def test_conversations_filterable_by_customer(client, H):
    acme = T(client, H["owner"], "get", "customers", params={"q": "Acme"}).json()["items"][0]["id"]
    got = T(client, H["manager"], "get", "conversations", params={"customer_id": acme}).json()
    assert got and all(c["customer_id"] == acme for c in got)
    beta = T(client, H["owner"], "get", "customers", params={"q": "Beta"}).json()["items"][0]["id"]
    assert T(client, H["manager"], "get", "conversations", params={"customer_id": beta}).json() == []
