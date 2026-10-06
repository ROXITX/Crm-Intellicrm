# IntelliCRM --- PROJECT.md

## 1. Project Title

**IntelliCRM --- AI-Powered Collaborative Customer, Staff and Business
Relationship Management System**

------------------------------------------------------------------------

# 2. One-Sentence Definition

IntelliCRM is a professional multi-role CRM for service businesses that
centralizes leads, customers, projects, tasks, support, communication,
billing and business intelligence while using CPU-friendly ML to predict
customer, sales, support and project risks.

------------------------------------------------------------------------

# 3. Problem

Service businesses commonly split information across: - spreadsheets -
WhatsApp - email - separate project tools - support systems - accounting
tools - personal notes

This causes: - missed follow-ups - poor customer visibility - delayed
projects - overloaded employees - slow support - payment follow-up
problems - customer churn - fragmented communication

IntelliCRM combines these workflows into one system.

------------------------------------------------------------------------

# 4. Target Users

### Owner/Admin

Needs: - company overview - revenue - customers - projects - risks -
employee workload - AI recommendations

### Manager

Needs: - team management - assignments - project monitoring - ticket
management - workload visibility

### Staff

Needs: - assigned work - customer context - tasks - tickets -
communication - prioritized next actions

### Client

Needs: - project visibility - requests - communication - documents -
invoices - approvals

------------------------------------------------------------------------

# 5. Approved Technology Stack

## Frontend

-   Next.js
-   React
-   TypeScript
-   Tailwind CSS
-   Recharts
-   React Hook Form
-   Zod

## Backend

-   Python 3.11+
-   FastAPI
-   SQLAlchemy
-   Pydantic
-   Alembic

## Database

**PostgreSQL**

This is the primary database.

## Cache/Queue

**Redis**

Optional initially but recommended for background jobs.

## AI/ML

-   Python
-   Pandas
-   NumPy
-   Scikit-learn
-   XGBoost
-   optional Transformers

## LLM

Optional external LLM API.

Do not make the entire system dependent on an LLM.

## File storage

-   local filesystem in development
-   S3-compatible object storage in production

------------------------------------------------------------------------

# 6. CPU-First Requirement

The entire MVP must work without a GPU.

Do NOT make GPU installation a requirement.

Initial AI models: - Logistic Regression - Random Forest - XGBoost -
TF-IDF - Naive Bayes

Optional advanced Transformer models may be added later.

The developer's RTX 5060 can be used later, but the architecture must
remain CPU-compatible.

------------------------------------------------------------------------

# 7. Database Decision

Use:

**PostgreSQL + SQLAlchemy + Alembic**

Do NOT use TXT/CSV files as application storage.

CSV is only for: - importing leads/customers - exporting reports/data

TXT is not a database.

JSON is only: - API payload format - flexible JSONB metadata where
appropriate

------------------------------------------------------------------------

# 8. Major Modules

``` text
Authentication
RBAC
Organizations
Dashboard
Leads
Customers
Customer 360
Projects
Tasks
Tickets
Messages
Documents
Invoices
Payments
Reports
Notifications
AI Insights
Ask IntelliCRM
Audit Logs
Settings
Client Portal
```

------------------------------------------------------------------------

# 9. AI/ML Modules

## 9.1 Lead Conversion Prediction

Input: - interactions - engagement - source - response behavior -
company information - proposal/pricing interactions

Output: - conversion probability - score - explanation

Models: - Logistic Regression - Random Forest - XGBoost

------------------------------------------------------------------------

## 9.2 Customer Churn Prediction

Input: - interaction recency - ticket volume - negative sentiment -
project delays - payment behavior - feedback

Output: - churn probability - risk level - contributing factors -
recommended action

------------------------------------------------------------------------

## 9.3 Sentiment Analysis

Initial:

``` text
TF-IDF
+
Logistic Regression
```

Output: - Positive - Neutral - Negative - confidence

------------------------------------------------------------------------

## 9.4 Ticket Priority Prediction

Predict: - Low - Medium - High - Critical

Inputs: - ticket text - sentiment - category - customer impact - SLA -
historical ticket data

Human can override prediction.

------------------------------------------------------------------------

## 9.5 Project Delay Prediction

Inputs: - task completion - overdue tasks - milestone status -
dependencies - team capacity - remaining time

Output: - delay probability - risk level - explanation - recommended
actions

------------------------------------------------------------------------

## 9.6 Workload Intelligence

Calculate employee capacity.

Recommend: - task reassignment - priority changes - workload balancing

Do not automatically reassign without authorization.

------------------------------------------------------------------------

# 10. Explainable AI Requirement

Every major prediction must answer:

``` text
What happened?
How likely is it?
Why does the model think this?
What should the user do?
```

Example:

``` text
Customer Risk: HIGH
Churn probability: 82%

Why:
- No interaction for 41 days
- 3 unresolved tickets
- Negative recent sentiment
- Current project is delayed

Recommended:
Schedule a customer check-in and resolve open ticket #218.
```

Avoid unexplained "AI score: 82%" displays.

------------------------------------------------------------------------

# 11. AI Assistant

The assistant is role-aware.

Owner:

``` text
Which customers need attention today?
```

Manager:

``` text
Which projects are likely to be delayed?
```

Staff:

``` text
What should I work on next?
```

Client:

``` text
What is the status of my project?
```

The assistant must only access authorized data.

------------------------------------------------------------------------

# 12. Master Data Flow

``` text
User
 ↓
Next.js UI
 ↓ HTTPS
FastAPI
 ↓
Authentication + RBAC
 ↓
Business Service
 ↓
PostgreSQL
 ↓
Response
```

AI:

``` text
Business Data
 ↓
Feature Engineering
 ↓
CPU ML Model
 ↓
Prediction
 ↓
Explanation
 ↓
PostgreSQL
 ↓
Dashboard / Recommendation
```

LLM:

``` text
Authorized CRM Data
 ↓
Business Tool / Retrieval
 ↓
LLM
 ↓
Natural-language answer
```

------------------------------------------------------------------------

# 13. Important Security Rule

The frontend is never trusted.

Every API request must independently verify: - identity - organization -
role - permission - object ownership/access

------------------------------------------------------------------------

# 14. Required UI Screens

Minimum implementation:

1.  Login
2.  Dashboard
3.  Leads
4.  Lead 360
5.  Customers
6.  Customer 360
7.  Projects
8.  Project Detail
9.  Tasks
10. Tickets
11. Ticket Detail
12. Messages
13. Invoices
14. Payments
15. Documents
16. Team
17. Reports
18. AI Insights
19. Ask IntelliCRM
20. Client Portal
21. Notifications
22. Settings
23. Audit Logs

------------------------------------------------------------------------

# 15. Visual Requirement

The dashboard and application must follow DESIGN.md exactly.

The approved visual direction is: - enterprise SaaS - light workspace -
dark navy sidebar - white cards - restrained blue accent - professional
charts - compact tables - subtle AI insights

Do not introduce: - neon - purple AI gradients - excessive
glassmorphism - giant chatbot UI - cartoon illustrations - unnecessary
animations

------------------------------------------------------------------------

# 16. Dashboard Priority

The owner dashboard should immediately answer:

### What is happening?

-   customers
-   leads
-   projects
-   revenue

### What is going wrong?

-   churn risk
-   project delays
-   critical tickets
-   overdue invoices
-   overloaded staff

### What should I do?

-   AI recommended actions

------------------------------------------------------------------------

# 17. Core Database Entities

``` text
organizations
users
roles
permissions
organization_members
role_permissions

leads
lead_interactions

customers
customer_contacts

projects
project_members
milestones

tasks
task_dependencies

tickets
ticket_comments

conversations
conversation_members
messages

documents

invoices
invoice_items
payments

feedback
notifications

ai_predictions
ai_recommendations

audit_logs
```

See DATABASE.md for authoritative fields and constraints.

------------------------------------------------------------------------

# 18. API Rules

All APIs: - use `/api/v1` - return consistent JSON - validate inputs -
enforce RBAC - enforce organization isolation - paginate large lists -
use server-side calculations for trusted values

Never: - expose database credentials - expose model files
unnecessarily - trust client-side role checks - trust frontend invoice
totals - allow arbitrary SQL through the AI assistant

------------------------------------------------------------------------

# 19. Development Order

Build in this order:

### Phase 1 --- Foundation

-   repository structure
-   environment configuration
-   Docker Compose
-   PostgreSQL
-   Redis
-   FastAPI
-   Next.js
-   Alembic

### Phase 2 --- Authentication

-   users
-   organizations
-   roles
-   permissions
-   login
-   refresh
-   protected routes

### Phase 3 --- CRM

-   leads
-   customers
-   customer 360
-   interactions

### Phase 4 --- Operations

-   projects
-   milestones
-   tasks
-   workload
-   tickets

### Phase 5 --- Communication

-   conversations
-   messages
-   notifications
-   attachments

### Phase 6 --- Billing

-   invoices
-   invoice items
-   payments
-   PDFs

### Phase 7 --- AI/ML

-   data preparation
-   lead scoring
-   churn
-   sentiment
-   ticket priority
-   project delay
-   explainability

### Phase 8 --- AI Assistant

-   authorized tools
-   natural language queries
-   summaries
-   recommendations

### Phase 9 --- Reports

-   dashboards
-   exports
-   AI insights

### Phase 10 --- Hardening

-   tests
-   security
-   performance
-   accessibility
-   error handling
-   audit
-   deployment

------------------------------------------------------------------------

# 20. ML Dataset Strategy

Do not wait for a perfect public CRM dataset.

Use three stages:

### Stage A --- Seed/demo data

Create realistic synthetic CRM data for development.

### Stage B --- Model training data

Use: - public datasets where relevant - synthetic data for initial
prototype - eventually real anonymized organization data

### Stage C --- Production learning

Only use properly consented/anonymized business data.

Never expose personal information in training datasets.

------------------------------------------------------------------------

# 21. ML Evaluation

Lead/churn classification: - Accuracy - Precision - Recall - F1 -
ROC-AUC - PR-AUC where appropriate

Sentiment: - Accuracy - Precision - Recall - F1 - Confusion matrix

Regression: - MAE - RMSE - R²

Do not select a model using accuracy alone when classes are imbalanced.

------------------------------------------------------------------------

# 22. Model Lifecycle

Store: - model name - model version - training date - features -
evaluation metrics

Every prediction records: - model - version - confidence - timestamp -
explanation

This makes AI results auditable.

------------------------------------------------------------------------

# 23. Sample End-to-End Workflow

``` text
Lead enters CRM
        ↓
Lead interactions recorded
        ↓
ML generates conversion probability
        ↓
Sales owner sees high score
        ↓
Lead converted
        ↓
Customer created
        ↓
Project created
        ↓
Tasks assigned
        ↓
Customer sends support request
        ↓
Ticket created
        ↓
Sentiment + priority predicted
        ↓
Staff resolves issue
        ↓
Project starts falling behind
        ↓
Delay model detects risk
        ↓
Owner receives recommendation
        ↓
Owner acts
        ↓
Customer health improves
```

This demonstrates the value of the entire platform.

------------------------------------------------------------------------

# 24. Definition of Done for MVP

MVP is complete only when:

-   authentication works
-   RBAC works
-   organization isolation works
-   dashboard works
-   leads work
-   customers work
-   projects work
-   tasks work
-   tickets work
-   communication works
-   invoices/payments work
-   PostgreSQL is authoritative
-   migrations work
-   at least 3 meaningful ML models work
-   AI predictions are explainable
-   AI assistant respects permissions
-   audit logs work
-   UI matches DESIGN.md
-   responsive behavior works
-   tests cover critical workflows

------------------------------------------------------------------------

# 25. Non-Goals for MVP

Do not waste implementation time initially on: - native mobile apps -
blockchain - complex microservices - Kubernetes - custom GPU
infrastructure - custom LLM training - advanced computer vision - voice
assistant - WhatsApp integration - huge enterprise integrations

These can be future extensions.

------------------------------------------------------------------------

# 26. Future Features

Possible: - WhatsApp integration - email synchronization - meeting
transcription - AI meeting summaries - voice assistant - invoice OCR -
predictive revenue - automated follow-up - advanced RAG - mobile app -
external integrations - advanced recommendation engine

------------------------------------------------------------------------

# 27. Final Architecture Decision

The project is a **modular monolith first**, not microservices.

``` text
Next.js
   ↓
FastAPI modular backend
   ↓
PostgreSQL
   +
Redis/worker
   +
File storage
   +
CPU ML services
   +
Optional external LLM
```

This is intentionally simpler to build, test, demonstrate and deploy.

Do NOT split into microservices unless there is a measured reason.

------------------------------------------------------------------------

# 28. Source-of-Truth Documents

When implementation decisions conflict, use this priority:

1.  DATABASE.md --- database/schema rules
2.  DESIGN.md --- UI/UX rules
3.  FUNCTIONALITY.md --- product behavior
4.  ARCHITECTURE.md --- system architecture
5.  PROJECT.md --- overall project scope

If a feature is not specified, implement the simplest secure version
consistent with these documents.

Do not introduce a new framework/library merely because it is
fashionable.

------------------------------------------------------------------------

# 29. Claude Implementation Rule

Before writing substantial code: 1. Read all five specification files.
2. Follow the approved architecture. 3. Do not ask the user to choose
between technologies already specified. 4. Do not redesign the UI. 5. Do
not replace PostgreSQL with files. 6. Do not introduce GPU requirements.
7. Do not add unnecessary dependencies. 8. Build incrementally and keep
the application runnable after each phase. 9. Use migrations for schema
changes. 10. Test authorization and tenant isolation. 11. Keep AI
predictions explainable. 12. Prefer reusable components/services. 13. Do
not generate placeholder functionality that is presented as completed.
14. Keep secrets in environment variables. 15. If a requirement is
ambiguous, choose the smallest implementation that preserves the
architecture.

------------------------------------------------------------------------

# 30. Expected Repository Structure

``` text
intellicrm/
├── frontend/
│   ├── app/
│   ├── components/
│   ├── lib/
│   ├── hooks/
│   ├── types/
│   └── public/
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   ├── auth/
│   │   ├── organizations/
│   │   ├── users/
│   │   ├── leads/
│   │   ├── customers/
│   │   ├── projects/
│   │   ├── tasks/
│   │   ├── tickets/
│   │   ├── messages/
│   │   ├── billing/
│   │   ├── documents/
│   │   ├── notifications/
│   │   ├── reports/
│   │   ├── ai/
│   │   └── audit/
│   └── tests/
│
├── ml/
│   ├── data/
│   ├── features/
│   ├── models/
│   ├── training/
│   ├── evaluation/
│   └── artifacts/
│
├── storage/
│
├── docker-compose.yml
├── .env.example
├── README.md
├── DESIGN.md
├── FUNCTIONALITY.md
├── DATABASE.md
├── ARCHITECTURE.md
└── PROJECT.md
```

------------------------------------------------------------------------

# 31. Final Product Positioning

IntelliCRM should feel like a real product that a service company could
use.

It should not feel like: - a college CRUD project - a chatbot demo - an
AI-generated dashboard - a collection of disconnected ML notebooks

The final product should demonstrate:

**CRM + Collaboration + Operations + Billing + Explainable AI + Business
Intelligence**

in one coherent professional system.
