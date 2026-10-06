# IntelliCRM --- CLAUDE_BUILD_RULES.md

## Read This Before Coding

You are implementing IntelliCRM from the specification files.

Required reading: 1. PROJECT.md 2. DESIGN.md 3. FUNCTIONALITY.md 4.
DATABASE.md 5. ARCHITECTURE.md

These files are the product contract.

------------------------------------------------------------------------

## Hard Rules

### Stack

Use: - Next.js + React + TypeScript - Tailwind CSS - FastAPI + Python -
SQLAlchemy - Alembic - PostgreSQL - Redis where background jobs/caching
are required - Scikit-learn/XGBoost for initial ML

Do not replace the stack without a real technical reason.

### Database

PostgreSQL is the source of truth.

Never use: - TXT - CSV - JSON files - localStorage

as the primary application database.

CSV is only for import/export.

### Architecture

Build a modular monolith first.

Do not create microservices.

### GPU

GPU is not required.

All MVP ML functionality must run on CPU.

### UI

The reference design is authoritative.

Do not: - add purple AI gradients - add glassmorphism - add neon
effects - add giant chatbot panels - make everything rounded - redesign
the sidebar - replace professional tables with card-only layouts

### Security

Every API request must enforce: - authentication - organization scope -
permissions - resource access

Never trust frontend authorization.

### AI

AI predictions must be explainable.

Never display only: `Risk = 82%`

Instead show: - probability - confidence - contributing factors -
recommended action

### LLM

LLM must not directly execute arbitrary SQL.

Use controlled backend tools.

### Financial data

All invoice/payment calculations happen server-side.

Use NUMERIC for money.

### Files

Store binary files in file/object storage.

Store metadata in PostgreSQL.

### Migrations

Every schema change goes through Alembic.

### Testing

Before marking a module complete: - happy path - validation -
authorization - organization isolation - error handling

must be tested.

------------------------------------------------------------------------

## Implementation Style

Prefer: - small reusable components - typed APIs - service functions -
clear module boundaries - consistent naming - explicit error handling

Avoid: - giant files - duplicated components - hard-coded business rules
everywhere - unnecessary dependencies - premature abstractions

------------------------------------------------------------------------

## Build Sequence

1.  Repository and Docker setup
2.  Database + migrations
3.  Authentication/RBAC
4.  Leads
5.  Customers
6.  Dashboard
7.  Projects/tasks
8.  Tickets
9.  Communication
10. Billing
11. AI/ML
12. AI assistant
13. Reports
14. Client portal
15. Tests/security/performance

Keep the application runnable after every major phase.

------------------------------------------------------------------------

## Do Not Fake Completion

If a feature is not implemented: - mark it as TODO - do not pretend it
works - do not create fake API responses as production functionality

Seed data may be used for development/demo mode and must be clearly
separated from production logic.

------------------------------------------------------------------------

## Token Efficiency

Avoid repeatedly explaining architecture decisions.

Read the specification files once, then implement against them.

When coding: - reuse established patterns - create shared components -
create shared API utilities - avoid repeating boilerplate - keep
comments for non-obvious decisions only

------------------------------------------------------------------------

## Final Acceptance

The implementation is successful when IntelliCRM behaves as one coherent
application and satisfies all source-of-truth documents.
