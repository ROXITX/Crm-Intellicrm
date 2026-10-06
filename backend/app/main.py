import logging

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import ai, auth, billing, customers, dashboard, documents, leads, messages, misc, projects, reports, tasks, team, tickets
from app.core.config import settings
from app.core.errors import install_handlers

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="IntelliCRM API", version="1.0.0", docs_url="/api/docs", openapi_url="/api/openapi.json")
install_handlers(app)
app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

v1 = APIRouter(prefix="/api/v1")
for r in (auth.router, dashboard.router, leads.router, customers.router, projects.router, tasks.router, team.router,
          tickets.router, messages.router, billing.router, documents.router, reports.router, ai.router, misc.router):
    v1.include_router(r)
app.include_router(v1)


@app.get("/api/health")
def health():
    return {"status": "ok"}
