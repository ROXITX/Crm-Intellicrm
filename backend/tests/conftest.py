import os
import subprocess
import sys

os.environ["DATABASE_URL"] = "postgresql+psycopg://intellicrm:intellicrm@localhost:5432/intellicrm_test"
os.environ["STORAGE_DIR"] = "/tmp/intellicrm_test_storage"
os.environ["MODEL_DIR"] = "/tmp/intellicrm_test_models"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

BACKEND = os.path.dirname(os.path.dirname(__file__))


@pytest.fixture(scope="session", autouse=True)
def _db():
    from app.core.db import engine
    with engine.begin() as c:
        c.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=BACKEND, check=True, env=os.environ)
    from app.core.db import SessionLocal
    from app.seed import demo
    with SessionLocal() as db:
        demo.seed(db)
    yield


@pytest.fixture(scope="session")
def client(_db):
    from app.main import app
    with TestClient(app) as c:
        yield c


PASSWORD = "Demo@12345"
USERS = {"owner": "owner@acme-demo.example", "manager": "manager@acme-demo.example", "ananya": "staff.ananya@acme-demo.example",
         "karthik": "staff.karthik@acme-demo.example", "meera": "staff.meera@acme-demo.example", "client": "client@acme-industries.example",
         "client2": "client@beta-systems.example"}


@pytest.fixture(scope="session")
def tokens(client):
    out = {}
    for k, email in USERS.items():
        r = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
        assert r.status_code == 200, r.text
        out[k] = r.json()["access_token"]
    return out


@pytest.fixture(scope="session")
def H(tokens):
    return {k: {"Authorization": f"Bearer {t}"} for k, t in tokens.items()}


@pytest.fixture(scope="session")
def other_org(client):
    """A second, independent organization used for tenant-isolation tests."""
    r = client.post("/api/v1/auth/register", json={"organization_name": "Rival Corp", "first_name": "Eve", "email": "eve@rival.example", "password": "Rival@123456"})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}
