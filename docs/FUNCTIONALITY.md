# IntelliCRM --- FUNCTIONALITY.md

## 1. Product Definition

IntelliCRM is a collaborative CRM for service businesses that
connects: - Owner/Admin - Manager - Staff - Client

The system combines conventional CRM functions with CPU-friendly ML
predictions and role-aware AI assistance.

The system is not merely a chatbot.

------------------------------------------------------------------------

# 2. Roles and Permissions

## Owner/Admin

Can: - manage organization - manage users/roles - view all customers -
manage leads - manage projects - manage tasks - manage tickets - view
revenue - manage invoices/payments - view reports - configure AI - view
audit logs - configure workflows

## Manager

Can: - manage assigned teams - view assigned customers/projects - assign
tasks - manage tickets - monitor project health - view team workload -
access permitted reports - use AI insights for authorized data

Cannot: - change organization ownership - access restricted admin
configuration unless granted

## Staff

Can: - view assigned customers/projects - work on assigned tasks -
respond to assigned tickets - communicate with authorized clients -
upload permitted documents - view relevant AI recommendations

Cannot: - view unrelated customer data - view company-wide financial
data unless permitted

## Client

Can: - view own account - view own projects - submit requests/tickets -
communicate with assigned team - view own documents - view own
invoices/payments - approve/request changes where enabled

Cannot: - see internal notes - see staff workload - see lead scoring -
see internal AI risk details - see other clients

------------------------------------------------------------------------

# 3. Authentication

Use: - email/password - secure password hashing - access token - refresh
token - logout/revocation - optional email verification - password reset

Passwords must never be stored directly.

Use Argon2id or bcrypt with a strong cost factor.

------------------------------------------------------------------------

# 4. Organization / Multi-Tenant Model

Every business belongs to an organization.

All business data must contain `organization_id`.

Authorization must always enforce organization isolation.

Example:

``` text
User A -> Organization 1
User B -> Organization 2

User A must NEVER retrieve Organization 2 data.
```

Never trust `organization_id` supplied by the frontend.

Resolve it from the authenticated user's server-side membership.

------------------------------------------------------------------------

# 5. Lead Management

Features: - create lead - edit lead - delete/archive lead - assign
owner - track source - record company/contact information - record
interactions - add notes - create follow-up - convert lead - import
leads - export leads

Lead lifecycle:

``` text
New
 ↓
Contacted
 ↓
Qualified
 ↓
Proposal
 ↓
Negotiation
 ↓
Won / Lost
```

Lead conversion should preserve history.

When converted: - lead remains as historical record - customer/account
is created or linked - interactions are retained - source attribution is
retained

------------------------------------------------------------------------

# 6. Lead Scoring

Calculate score using configurable ML model plus business rules.

Features may include: - interaction frequency - days since last
interaction - number of inquiries - proposal requested - pricing-page
interaction if tracked - response rate - source - company size -
previous engagement

Output: - score 0--100 - probability of conversion - model version -
prediction timestamp - explanation factors

Never claim the score is a fact.

------------------------------------------------------------------------

# 7. Customer Management

Features: - create customer - contacts - company information - account
owner - tags - notes - projects - tickets - communication - documents -
invoices - payments - feedback - activity history

Customer health score combines: - engagement - support sentiment -
ticket frequency - project status - payment behavior - interaction
recency

Output: - Healthy - Watch - At Risk - Critical

------------------------------------------------------------------------

# 8. Customer Churn Prediction

CPU-friendly initial model: - Random Forest - XGBoost

Features: - interaction recency - ticket count - negative sentiment -
project delays - payment delays - engagement frequency - feedback score

Output:

``` text
churn_probability: 0.82
risk_level: HIGH
```

Store prediction metadata.

Do not automatically terminate or alter customer relationships.

------------------------------------------------------------------------

# 9. Project Management

Features: - create project - customer association - project owner - team
members - milestones - tasks - dependencies - progress - due dates -
budget - documents - communication - activity log

Project lifecycle:

``` text
Planning
Active
At Risk
Delayed
Completed
Archived
```

------------------------------------------------------------------------

# 10. Project Delay Prediction

Possible features: - percentage completed - overdue tasks - remaining
days - task velocity - team capacity - blocked tasks - dependency
delays - milestone completion rate

Output: - delay probability - risk level - contributing factors -
recommended actions

------------------------------------------------------------------------

# 11. Task Management

Features: - create task - assign task - priority - status - due date -
estimated hours - actual hours - dependencies - comments - attachments -
checklist

Statuses: - Todo - In Progress - Blocked - Review - Done - Cancelled

Priority: - Low - Medium - High - Critical

AI can recommend priority but cannot silently change a task.

------------------------------------------------------------------------

# 12. Workload Intelligence

Calculate:

``` text
capacity_usage =
allocated_estimated_hours / available_hours
```

Show: - normal - high - overloaded

Use this for task assignment recommendations.

Do not create employee surveillance or hidden scoring.

------------------------------------------------------------------------

# 13. Ticket / Support Management

Features: - create ticket - assign staff - categories - priority - SLA -
comments - attachments - status - escalation - customer context

Statuses: - Open - In Progress - Waiting for Customer - Waiting for
Internal - Resolved - Closed

AI: - priority prediction - category suggestion - sentiment - response
suggestion - summary

Human override is mandatory.

------------------------------------------------------------------------

# 14. Sentiment Analysis

Initial CPU implementation: - text cleaning - TF-IDF - Logistic
Regression or Naive Bayes

Optional advanced: - DistilBERT

Input: - ticket/message text

Output: - Positive - Neutral - Negative - confidence

Store model version.

------------------------------------------------------------------------

# 15. Communication

Two communication scopes:

### Client communication

Customer-facing.

### Internal communication

Employee-only.

Messages must contain authorization context.

Features: - real-time messaging - attachments - read status - mentions -
search - conversation history - customer/project/ticket linking

WebSockets may be used for real-time updates.

------------------------------------------------------------------------

# 16. Documents

Features: - upload - download - preview where supported - associate with
customer/project/ticket/invoice - permission checking - metadata -
versioning if implemented

Do not store large binary files directly in PostgreSQL.

Store files in object/file storage and store metadata in SQL.

------------------------------------------------------------------------

# 17. Invoices

Features: - create - edit draft - issue - send - record payment - mark
overdue - cancel - generate PDF

Invoice totals must be calculated server-side.

Never trust totals sent from the browser.

------------------------------------------------------------------------

# 18. Payments

Track: - invoice - amount - payment date - method - transaction
reference - status

Payment statuses: - Pending - Completed - Failed - Refunded

Never store raw card numbers or CVV.

------------------------------------------------------------------------

# 19. Notifications

Trigger notifications for: - assignment - mention - overdue task -
ticket escalation - payment - invoice overdue - project risk - customer
risk - new message

Notification preferences must be configurable.

------------------------------------------------------------------------

# 20. AI Assistant

Assistant must be: - role-aware - organization-aware -
permission-aware - auditable

The assistant must query authorized application data.

Example:

Owner: `Which customers need attention today?`

Staff: `What should I work on next?`

Client: `What is the current status of my project?`

The assistant must never bypass API authorization.

------------------------------------------------------------------------

# 21. AI Recommendation Lifecycle

Every recommendation:

``` text
Prediction
↓
Explanation
↓
Recommended action
↓
Human decision
↓
Optional outcome tracking
```

Do not silently execute business-critical actions.

------------------------------------------------------------------------

# 22. Search

Global search across permitted: - leads - customers - projects - tasks -
tickets - messages - invoices

Use PostgreSQL full-text search initially.

Do not add Elasticsearch unless scale actually requires it.

------------------------------------------------------------------------

# 23. Audit Logging

Audit: - login/logout - permission changes - customer changes - lead
conversion - project changes - invoice changes - payment changes - AI
prediction generation - AI recommendation acceptance/rejection -
destructive operations

Record: - actor - action - entity - entity ID - timestamp -
IP/user-agent where appropriate - before/after metadata where
appropriate

------------------------------------------------------------------------

# 24. Reporting

Reports: - lead funnel - conversion - customer health - churn risk -
project performance - support performance - revenue - overdue invoices -
employee workload

All reports must respect RBAC and organization boundaries.

------------------------------------------------------------------------

# 25. Import/Export

CSV import: - validate headers - validate rows - show errors - preview -
confirm import - create audit record

CSV export: - only authorized records - no hidden fields - record export
activity if sensitive

CSV is an import/export format, NOT the primary database.

------------------------------------------------------------------------

# 26. Error Handling

API errors should use a consistent format:

``` json
{
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "Customer not found",
    "request_id": "..."
  }
}
```

Do not expose stack traces in production.

------------------------------------------------------------------------

# 27. Data Validation

Validation occurs: 1. Frontend for UX 2. Backend for
security/correctness 3. Database constraints for integrity

Frontend validation is never sufficient.

------------------------------------------------------------------------

# 28. Soft Delete

Use soft deletion for important business entities where history matters.

Recommended: - customers - leads - projects - tickets - documents

Use: `deleted_at`

Do not physically delete audit-critical records unless legally required.

------------------------------------------------------------------------

# 29. Background Jobs

Use a worker system for: - AI prediction generation - email -
notifications - report generation - document processing - scheduled
health calculations

Redis may be used as the queue/backend.

Do not block API requests for long ML tasks.
