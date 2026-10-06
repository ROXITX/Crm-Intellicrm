# IntelliCRM

AI-powered collaborative CRM for service businesses: leads, customers, projects, tasks, support tickets, messaging,
billing and explainable CPU-only ML in one modular monolith.

> **Full documentation:** [`docs/USER_GUIDE.md`](docs/USER_GUIDE.md) - how to use it, every feature, and how it works inside.
> The product specification that drove the build is in [`docs/`](docs/) (`PROJECT`, `DESIGN`, `FUNCTIONALITY`, `DATABASE`, `ARCHITECTURE`, `CLAUDE_BUILD_RULES`).

## Stack

Next.js 15 + React 19 + TypeScript + Tailwind + Recharts + React Hook Form + Zod · FastAPI + SQLAlchemy 2 + Alembic ·
PostgreSQL 16 (source of truth) · Redis (optional: rate-limit + worker lock) · scikit-learn (CPU only, no GPU needed).

## Quick start (native)

Prerequisites: Python 3.11+, Node 20+, PostgreSQL 14+ (Redis optional).

```bash
# 1. database
createuser -P intellicrm            # password: intellicrm (or choose your own and set DATABASE_URL)
createdb -O intellicrm intellicrm

# 2. backend (http://localhost:8000, API docs at /api/docs)
cd backend
python -m venv ../.venv && source ../.venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env   # fill in JWT_SECRET / JWT_REFRESH_SECRET (dev defaults exist but are NOT safe for production)
alembic upgrade head      # create the schema
python -m app.seed.demo   # OPTIONAL demo data (clearly separated from production code)
uvicorn app.main:app --reload --port 8000

# 3. frontend (http://localhost:3000)
cd ../frontend
npm install
npm run dev               # proxies /api/* to http://localhost:8000 (override with BACKEND_URL)

# 4. optional background worker (periodic prediction/health refresh, overdue invoices)
cd ../backend && python -m app.workers.scheduler
```

Demo logins (after seeding) - password `Demo@12345`:

| Role | Login |
| --- | --- |
| Owner | `owner@acme-demo.example` |
| Manager | `manager@acme-demo.example` |
| Staff | `staff.ananya@acme-demo.example`, `staff.karthik@acme-demo.example`, `staff.meera@acme-demo.example` |
| Client (portal) | `client@acme-industries.example`, `client@beta-systems.example` |

Or register a brand-new organization from the login screen ("Create an account").

## Docker

```bash
cp .env.example .env       # set JWT_SECRET and JWT_REFRESH_SECRET (long random strings)
docker compose up --build  # postgres, redis, backend (runs migrations), worker, frontend
docker compose exec backend python -m app.seed.demo   # optional demo data
```

> The compose file was written to match the native setup but **could not be executed in the build environment (no Docker daemon)** - treat it as untested.

## Tests

```bash
cd backend  && pytest                       # 79 tests: auth, RBAC, tenant isolation, billing, AI, search, reports (uses DB intellicrm_test)
cd frontend && npm test && npm run lint     # 11 unit tests + TypeScript check
node frontend/scripts/e2e-smoke.mjs         # browser smoke test against a running, seeded stack (needs Playwright)
```

The backend tests need a PostgreSQL database named `intellicrm_test` owned by the `intellicrm` user; they drop and recreate its schema.

## Repository layout

```
backend/app/{core,models,api,services,ai,seed,workers}   FastAPI modular monolith
backend/alembic/versions                                 migrations 0001-0004
backend/tests                                            pytest suite
frontend/{app,components,lib,hooks,types,tests}          Next.js app
ml/artifacts                                             trained model files (generated, git-ignored)
storage/                                                 uploaded files in development (git-ignored)
docs/                                                    specification + USER_GUIDE.md
```

## Configuration

All configuration is via environment variables (see `.env.example`; never commit `.env`):
`DATABASE_URL`, `REDIS_URL`, `JWT_SECRET`, `JWT_REFRESH_SECRET`, `STORAGE_DIR`, `MODEL_DIR`, `CORS_ORIGINS`, `LLM_API_KEY` (reserved), SMTP/S3 placeholders (reserved).
