# IntelliCRM --- ARCHITECTURE.md

## 1. Approved Architecture

Use a modular full-stack architecture:

``` text
                    ┌───────────────────────────┐
                    │        Web Client         │
                    │ React / Next.js + TS      │
                    └─────────────┬─────────────┘
                                  │ HTTPS
                                  ▼
                    ┌───────────────────────────┐
                    │       FastAPI API         │
                    │ Auth / RBAC / CRM /       │
                    │ Projects / Billing / AI   │
                    └───────┬─────────┬─────────┘
                            │         │
                    ┌───────▼───┐ ┌──▼──────────┐
                    │PostgreSQL │ │    Redis    │
                    │  SQL DB   │ │Cache/Queue  │
                    └───────────┘ └──────┬──────┘
                                         │
                                  Background Worker
                                         │
                  ┌──────────────────────┼──────────────────────┐
                  │                      │                      │
            ┌─────▼─────┐          ┌─────▼─────┐        ┌──────▼─────┐
            │ CPU ML    │          │ Email/     │        │ File/Object│
            │ Services  │          │Notify Jobs │        │  Storage   │
            └───────────┘          └───────────┘        └────────────┘

                         Optional
                            │
                            ▼
                    ┌────────────────┐
                    │ External LLM   │
                    │ API / Provider  │
                    └────────────────┘
```

------------------------------------------------------------------------

# 2. Frontend

Recommended: - Next.js - React - TypeScript - Tailwind CSS - Recharts -
React Hook Form - Zod

Responsibilities: - UI - client-side validation - routing - API calls -
charts - tables - responsive design

Frontend must NOT: - directly access PostgreSQL - contain secrets - make
authorization decisions - calculate trusted financial totals - trust
role information supplied only by local state

------------------------------------------------------------------------

# 3. Backend

Recommended: - Python - FastAPI - SQLAlchemy - Pydantic - Alembic

Modules:

``` text
backend/app/
  api/
  core/
  auth/
  users/
  organizations/
  leads/
  customers/
  projects/
  tasks/
  tickets/
  messages/
  billing/
  documents/
  notifications/
  reports/
  ai/
  audit/
  workers/
```

Use service/repository separation where it improves maintainability.

------------------------------------------------------------------------

# 4. API Structure

Base:

``` text
/api/v1
```

Examples:

``` text
POST   /auth/login
POST   /auth/refresh
POST   /auth/logout

GET    /dashboard
GET    /leads
POST   /leads
GET    /leads/{id}
PATCH  /leads/{id}

GET    /customers
POST   /customers
GET    /customers/{id}

GET    /projects
POST   /projects
GET    /projects/{id}

GET    /tasks
POST   /tasks

GET    /tickets
POST   /tickets
GET    /tickets/{id}

GET    /conversations
POST   /conversations/{id}/messages

GET    /invoices
POST   /invoices

GET    /ai/insights
POST   /ai/assistant/query
```

Use consistent pagination, filtering and error responses.

------------------------------------------------------------------------

# 5. Authentication Architecture

Recommended:

``` text
Login
 ↓
Verify password
 ↓
Issue short-lived access token
 ↓
Issue secure refresh token
 ↓
API authorization
```

Use secure cookies where appropriate for refresh tokens.

Never store passwords in plaintext.

------------------------------------------------------------------------

# 6. RBAC

Authorization flow:

``` text
Request
 ↓
Authenticate user
 ↓
Resolve organization membership
 ↓
Resolve role/permissions
 ↓
Check resource ownership/scope
 ↓
Execute service
```

Do not rely on frontend route hiding.

------------------------------------------------------------------------

# 7. Multi-Tenant Security

Every service query must be scoped:

``` python
query.where(Model.organization_id == current_user.organization_id)
```

Then apply object-level rules.

Example: A staff user may belong to Organization A but still only access
assigned projects.

------------------------------------------------------------------------

# 8. Real-Time Communication

Use WebSockets for: - messages - notification updates - typing status -
ticket updates where useful

Do not use WebSockets for normal CRUD operations.

Normal CRUD remains REST.

------------------------------------------------------------------------

# 9. Background Jobs

Use Redis + worker framework.

Jobs: - AI predictions - email sending - notification delivery - report
generation - scheduled customer health calculation - scheduled project
risk calculation

API should return quickly.

------------------------------------------------------------------------

# 10. AI/ML Architecture

Initial models are CPU-first.

``` text
PostgreSQL
    ↓
Feature extraction
    ↓
Pandas / NumPy
    ↓
Scikit-learn / XGBoost
    ↓
Prediction
    ↓
ai_predictions
    ↓
Explanation
    ↓
ai_recommendations
```

Models: - Logistic Regression / Random Forest / XGBoost for lead
conversion - Random Forest / XGBoost for churn - Logistic
Regression/Naive Bayes for sentiment - Classification model for ticket
priority - Regression/classification model for project delay

Use model versioning.

------------------------------------------------------------------------

# 11. LLM Architecture

LLM is optional and should not replace the ML models.

Use an LLM for: - natural language summaries - natural language business
questions - response drafting - meeting/message summarization -
explanation generation when appropriate

Do NOT use the LLM as the source of truth for: - invoice totals -
payment balances - permissions - customer IDs - project dates - business
metrics

For factual CRM answers:

``` text
User question
 ↓
Permission check
 ↓
Structured DB query / authorized retrieval
 ↓
Relevant data
 ↓
LLM formats explanation
 ↓
Response
```

This prevents hallucinated business data.

------------------------------------------------------------------------

# 12. AI Assistant Security

Never allow the LLM to directly execute arbitrary SQL.

Use predefined tools/services such as:

``` text
get_customer_health()
get_open_tickets()
get_project_status()
get_overdue_invoices()
get_team_workload()
get_lead_pipeline()
```

Each tool performs its own authorization.

------------------------------------------------------------------------

# 13. File Storage

Development: - local storage directory

Production: - S3-compatible object storage

Flow:

``` text
Upload
 ↓
Validate file type/size
 ↓
Generate safe storage key
 ↓
Store binary
 ↓
Store metadata in PostgreSQL
```

Never store arbitrary client filenames as filesystem paths.

------------------------------------------------------------------------

# 14. Email

Email provider can be SMTP or a transactional email provider.

Email should be sent through background jobs.

------------------------------------------------------------------------

# 15. Caching

Redis cache candidates: - dashboard summaries - frequently requested
reports - permission lookups - rate limiting

Do not cache sensitive data without clear invalidation rules.

------------------------------------------------------------------------

# 16. API Pagination

Default:

``` text
page_size = 25
max_page_size = 100
```

For very large datasets prefer cursor pagination.

------------------------------------------------------------------------

# 17. Security

Required: - HTTPS in production - password hashing - JWT/session
security - RBAC - tenant isolation - rate limiting - CORS restrictions -
CSRF protection where cookie auth requires it - input validation -
SQLAlchemy parameterization - secure file handling - audit logs - secret
management

Never commit: - API keys - database passwords - JWT secrets - SMTP
passwords

------------------------------------------------------------------------

# 18. Deployment

Recommended development:

``` text
Docker Compose
├── frontend
├── backend
├── postgres
├── redis
└── worker
```

Production can later move to: - managed PostgreSQL - managed Redis -
container hosting - object storage - external LLM API

The application should not depend on Docker for local development if the
developer prefers native services, but Docker Compose is the easiest
reproducible environment.

------------------------------------------------------------------------

# 19. Environment Variables

Example:

``` env
DATABASE_URL=
REDIS_URL=
JWT_SECRET=
JWT_REFRESH_SECRET=
STORAGE_BUCKET=
STORAGE_ENDPOINT=
SMTP_HOST=
SMTP_USER=
SMTP_PASSWORD=
LLM_API_KEY=
```

Use `.env.example` with empty placeholders.

Never commit `.env`.

------------------------------------------------------------------------

# 20. Observability

Log: - request ID - errors - background job failures - authentication
events - important AI jobs

Do not log: - passwords - access tokens - refresh tokens - raw payment
credentials - unnecessary private message content

------------------------------------------------------------------------

# 21. Testing Architecture

Backend: - unit tests - service tests - API tests - authorization
tests - tenant-isolation tests

Frontend: - component tests - critical workflow tests

AI: - train/test split - metrics - model versioning - prediction
validation

Critical security tests: - cross-organization access must fail - client
cannot read internal comments - staff cannot access unauthorized
customers - client cannot access another client's project
