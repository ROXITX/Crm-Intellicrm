def test_login_ok_and_me(client, H):
    r = client.get("/api/v1/auth/me", headers=H["owner"])
    assert r.status_code == 200
    body = r.json()
    assert body["role"] == "owner" and "customers.write" in body["permissions"]


def test_login_wrong_password(client):
    r = client.post("/api/v1/auth/login", json={"email": "owner@acme-demo.example", "password": "nope-nope-nope"})
    assert r.status_code == 401 and r.json()["error"]["code"] == "INVALID_CREDENTIALS"
    assert r.json()["error"]["request_id"]


def test_unknown_user_same_error(client):
    r = client.post("/api/v1/auth/login", json={"email": "ghost@nowhere.example", "password": "whatever123"})
    assert r.status_code == 401 and r.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_requires_auth(client):
    assert client.get("/api/v1/customers").status_code == 401
    assert client.get("/api/v1/customers", headers={"Authorization": "Bearer garbage"}).status_code == 401


def test_refresh_rotation_and_logout(client):
    r = client.post("/api/v1/auth/login", json={"email": "manager@acme-demo.example", "password": "Demo@12345"})
    refresh = r.json()["refresh_token"]
    r2 = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert r2.status_code == 200
    # the old refresh token was rotated and must now be rejected
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": refresh}).status_code == 401
    new = r2.json()["refresh_token"]
    assert client.post("/api/v1/auth/logout", json={"refresh_token": new}).status_code == 204
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": new}).status_code == 401


def test_register_validation(client):
    r = client.post("/api/v1/auth/register", json={"organization_name": "X", "first_name": "A", "email": "bad", "password": "short"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_password_is_hashed(client):
    from sqlalchemy import select
    from app.core.db import SessionLocal
    from app.models import User
    with SessionLocal() as db:
        h = db.scalar(select(User.password_hash).where(User.email == "owner@acme-demo.example"))
    assert h.startswith("$argon2id$") and "Demo@12345" not in h


def test_login_rate_limited(client):
    from app.core import ratelimit
    ratelimit.reset()
    codes = [client.post("/api/v1/auth/login", json={"email": "victim@nowhere.example", "password": "wrong-pass-123"}).status_code for _ in range(12)]
    assert codes[:10] == [401] * 10 and codes[10:] == [429, 429]
    ratelimit.reset()
