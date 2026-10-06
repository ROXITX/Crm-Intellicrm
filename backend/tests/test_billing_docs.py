import io
from decimal import Decimal
from datetime import date, timedelta


def T(client, h, method, path, **kw):
    return getattr(client, method)(f"/api/v1/{path}", headers=h, **kw)


def _cust(client, H, q="Epsilon"):
    return T(client, H["owner"], "get", "customers", params={"q": q}).json()["items"][0]["id"]


def _invoice(client, H, **over):
    body = {"customer_id": _cust(client, H), "due_date": str(date.today() + timedelta(days=30)), "discount": "100.00",
            "items": [{"description": "Design", "quantity": "3", "unit_price": "1999.99", "tax_rate": "18"},
                      {"description": "Hosting", "quantity": "1.5", "unit_price": "1000.10", "tax_rate": "0"}]}
    body.update(over)
    return T(client, H["owner"], "post", "invoices", json=body)


def test_totals_computed_server_side_with_decimal_precision(client, H):
    r = _invoice(client, H, subtotal="1", total="1", tax="1")  # client-supplied totals must be ignored
    assert r.status_code == 201, r.text
    inv = r.json()
    # line1 net 5999.97 tax 1079.9946->1079.99 ; line2 net 1500.15
    assert inv["subtotal"] == "7500.12" and inv["tax"] == "1079.99" and inv["total"] == "8480.11"
    assert inv["status"] == "draft" and inv["invoice_number"].startswith("INV-")
    assert [i["line_total"] for i in inv["items"]] == ["7079.96", "1500.15"]
    assert Decimal(inv["total"]) == Decimal(inv["subtotal"]) + Decimal(inv["tax"]) - Decimal(inv["discount"])


def test_invoice_validation(client, H):
    assert _invoice(client, H, items=[]).status_code == 422
    assert _invoice(client, H, discount="-1").status_code == 422
    assert _invoice(client, H, due_date="2000-01-01").status_code == 400
    assert _invoice(client, H, discount="999999999").status_code == 400
    bad = [{"description": "x", "quantity": "0", "unit_price": "5"}]
    assert _invoice(client, H, items=bad).status_code == 422


def test_invoice_lifecycle_payments_and_overpayment(client, H):
    inv = _invoice(client, H).json()
    iid = inv["id"]
    assert T(client, H["owner"], "post", f"invoices/{iid}/payments", json={"amount": "10"}).status_code == 409  # draft
    assert T(client, H["owner"], "post", f"invoices/{iid}/issue").status_code == 200
    assert T(client, H["owner"], "patch", f"invoices/{iid}", json={"discount": "0"}).status_code == 409  # only drafts editable
    assert T(client, H["owner"], "post", f"invoices/{iid}/issue").status_code == 409
    assert T(client, H["owner"], "post", f"invoices/{iid}/payments", json={"amount": "0"}).status_code == 422
    over = T(client, H["owner"], "post", f"invoices/{iid}/payments", json={"amount": "9999999"})
    assert over.status_code == 400 and over.json()["error"]["code"] == "OVERPAYMENT"
    p1 = T(client, H["owner"], "post", f"invoices/{iid}/payments", json={"amount": "3000.00", "method": "upi", "transaction_reference": "UPI123"})
    assert p1.status_code == 201
    d = T(client, H["owner"], "get", f"invoices/{iid}").json()
    assert d["status"] == "partially_paid" and d["amount_paid"] == "3000.00" and d["balance"] == "5480.11"
    assert T(client, H["owner"], "post", f"invoices/{iid}/cancel").status_code == 409  # has payments
    p2 = T(client, H["owner"], "post", f"invoices/{iid}/payments", json={"amount": "5480.11"})
    assert p2.status_code == 201
    d = T(client, H["owner"], "get", f"invoices/{iid}").json()
    assert d["status"] == "paid" and d["balance"] == "0.00" and len(d["payments"]) == 2
    assert T(client, H["owner"], "post", f"invoices/{iid}/payments", json={"amount": "1"}).status_code == 409
    assert T(client, H["owner"], "post", f"invoices/{iid}/payments", json={"amount": "1", "method": "card", "card_number": "4111"}).status_code in (409, 201)


def test_payment_permissions(client, H):
    iid = _invoice(client, H).json()["id"]
    T(client, H["owner"], "post", f"invoices/{iid}/issue")
    assert T(client, H["manager"], "post", f"invoices/{iid}/payments", json={"amount": "1"}).status_code == 403
    assert T(client, H["manager"], "post", "invoices", json={"customer_id": _cust(client, H), "due_date": "2030-01-01", "items": [{"description": "x", "quantity": "1", "unit_price": "1"}]}).status_code == 403
    assert T(client, H["client"], "post", f"invoices/{iid}/payments", json={"amount": "1"}).status_code == 403


def test_overdue_detection_and_summary(client, H):
    s = T(client, H["owner"], "get", "invoices/summary").json()
    assert Decimal(s["overdue"]) > 0 and Decimal(s["outstanding"]) >= Decimal(s["overdue"]) and Decimal(s["revenue"]) > 0
    od = T(client, H["owner"], "get", "invoices", params={"status": "overdue", "page_size": 100}).json()["items"]
    assert od and all(date.fromisoformat(i["due_date"]) < date.today() for i in od)


def test_cancel_draft_and_pdf(client, H):
    iid = _invoice(client, H).json()["id"]
    pdf = T(client, H["owner"], "get", f"invoices/{iid}/pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF") and pdf.headers["content-type"] == "application/pdf"
    assert T(client, H["owner"], "post", f"invoices/{iid}/cancel").json()["status"] == "cancelled"


def test_customer_revenue_updates_with_payment(client, H):
    cid = _cust(client, H, "Theta")
    before = Decimal(T(client, H["owner"], "get", f"customers/{cid}").json()["revenue"])
    iid = _invoice(client, H, customer_id=cid).json()["id"]
    T(client, H["owner"], "post", f"invoices/{iid}/issue")
    T(client, H["owner"], "post", f"invoices/{iid}/payments", json={"amount": "1000"})
    assert Decimal(T(client, H["owner"], "get", f"customers/{cid}").json()["revenue"]) == before + Decimal("1000")


def test_database_constraints_enforced(client):
    import pytest
    from sqlalchemy import select, text
    from sqlalchemy.exc import IntegrityError
    from app.core.db import SessionLocal
    from app.models import Invoice
    with SessionLocal() as db:
        inv = db.scalar(select(Invoice).limit(1))
        with pytest.raises(IntegrityError):
            db.execute(text("update invoices set amount_paid = total + 1 where id = :i"), {"i": inv.id})
        db.rollback()
        with pytest.raises(IntegrityError):
            db.execute(text("update invoices set total = -1 where id = :i"), {"i": inv.id})
        db.rollback()


def test_document_upload_download_permissions(client, H):
    cid = _cust(client, H, "Acme")
    f = {"file": ("../../evil name.pdf", io.BytesIO(b"%PDF-1.4 test"), "application/pdf")}
    r = T(client, H["manager"], "post", "documents", files=f, data={"customer_id": cid})
    assert r.status_code == 201, r.text
    doc = r.json()
    assert "storage_key" not in doc and "/" not in doc["file_name"] and doc["file_size"] == 13
    dl = T(client, H["client"], "get", f"documents/{doc['id']}/download")  # Acme's own client
    assert dl.status_code == 200 and dl.content.startswith(b"%PDF")
    assert T(client, H["client2"], "get", f"documents/{doc['id']}/download").status_code == 404
    assert T(client, H["karthik"], "get", f"documents/{doc['id']}/download").status_code in (403, 404)
    docs = T(client, H["client2"], "get", "documents").json()["items"]
    assert all(d["id"] != doc["id"] for d in docs)
    assert all("storage_key" not in d for d in T(client, H["owner"], "get", "documents").json()["items"])


def test_document_upload_validation(client, H):
    cid = _cust(client, H, "Acme")
    exe = {"file": ("run.exe", io.BytesIO(b"MZ"), "application/octet-stream")}
    assert T(client, H["manager"], "post", "documents", files=exe, data={"customer_id": cid}).status_code == 400
    ok = {"file": ("a.txt", io.BytesIO(b"hello"), "text/plain")}
    assert T(client, H["manager"], "post", "documents", files=ok).status_code == 400  # no parent entity
    ok = {"file": ("a.txt", io.BytesIO(b"hello"), "text/plain")}
    import uuid
    assert T(client, H["manager"], "post", "documents", files=ok, data={"customer_id": str(uuid.uuid4())}).status_code == 404


def test_document_delete_is_soft_and_restricted(client, H):
    cid = _cust(client, H, "Acme")
    f = {"file": ("x.txt", io.BytesIO(b"1"), "text/plain")}
    doc = T(client, H["manager"], "post", "documents", files=f, data={"customer_id": cid}).json()
    assert T(client, H["client"], "delete", f"documents/{doc['id']}").status_code == 403
    assert T(client, H["manager"], "delete", f"documents/{doc['id']}").status_code == 204
    assert T(client, H["owner"], "get", f"documents/{doc['id']}/download").status_code == 404
