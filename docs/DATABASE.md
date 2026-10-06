# IntelliCRM --- DATABASE.md

## 1. Database Decision

### PRIMARY DATABASE: PostgreSQL

IntelliCRM will use **PostgreSQL as the source of truth**.

Do NOT use: - TXT files as a database - CSV files as a database - JSON
files as a database - browser localStorage as a database - SQLite for
the production architecture

SQLite may only be used for isolated local experiments/tests if
necessary.

### Why PostgreSQL?

It provides: - relational integrity - foreign keys - transactions -
indexing - full-text search - strong consistency - reporting/query
capability - production scalability

------------------------------------------------------------------------

# 2. Supporting Storage

## Redis --- optional but recommended

Use Redis for: - caching - rate limiting - background job queue -
temporary sessions/state - notification jobs

Redis is NOT the primary source of truth.

## File/Object Storage

Binary files: - documents - invoice PDFs - attachments

must be stored in: - local object/file storage for development -
S3-compatible/object storage in production

PostgreSQL stores metadata and storage references.

------------------------------------------------------------------------

# 3. Database Naming

Use: - lowercase snake_case - singular/plural consistently

Recommended: plural table names.

Examples: - users - organizations - customers - projects - tasks

Primary key:

``` sql
id UUID PRIMARY KEY
```

Use UUIDs for externally exposed IDs.

------------------------------------------------------------------------

# 4. Mandatory Organization Isolation

Most business tables must contain:

``` sql
organization_id UUID NOT NULL
```

Foreign key:

``` sql
FOREIGN KEY (organization_id)
REFERENCES organizations(id)
ON DELETE RESTRICT
```

Every backend query must enforce organization scope.

Example:

``` sql
SELECT *
FROM customers
WHERE organization_id = :current_org_id
  AND deleted_at IS NULL;
```

Never trust organization IDs from the frontend.

------------------------------------------------------------------------

# 5. Core Tables

## organizations

``` text
id UUID PK
name VARCHAR(200) NOT NULL
slug VARCHAR(100) UNIQUE NOT NULL
email VARCHAR(255)
phone VARCHAR(50)
logo_url TEXT
status VARCHAR(30) NOT NULL
created_at TIMESTAMPTZ NOT NULL
updated_at TIMESTAMPTZ NOT NULL
```

------------------------------------------------------------------------

## users

``` text
id UUID PK
email VARCHAR(255) UNIQUE NOT NULL
password_hash TEXT NOT NULL
first_name VARCHAR(100) NOT NULL
last_name VARCHAR(100)
avatar_url TEXT
is_active BOOLEAN NOT NULL DEFAULT true
email_verified_at TIMESTAMPTZ
last_login_at TIMESTAMPTZ
created_at TIMESTAMPTZ NOT NULL
updated_at TIMESTAMPTZ NOT NULL
```

Email must be normalized to lowercase.

------------------------------------------------------------------------

## organization_members

``` text
id UUID PK
organization_id UUID NOT NULL FK
user_id UUID NOT NULL FK
role_id UUID NOT NULL FK
status VARCHAR(30) NOT NULL
joined_at TIMESTAMPTZ NOT NULL
created_at TIMESTAMPTZ NOT NULL
updated_at TIMESTAMPTZ NOT NULL
```

Unique:

``` text
(organization_id, user_id)
```

------------------------------------------------------------------------

## roles

``` text
id UUID PK
organization_id UUID NULL FK
name VARCHAR(50) NOT NULL
description TEXT
is_system_role BOOLEAN DEFAULT false
created_at TIMESTAMPTZ
updated_at TIMESTAMPTZ
```

System roles: - owner - manager - staff - client

------------------------------------------------------------------------

## permissions

``` text
id UUID PK
code VARCHAR(100) UNIQUE NOT NULL
description TEXT
```

Examples: - customers.read - customers.write - projects.read -
projects.write - invoices.read - invoices.write - reports.read -
ai.read - ai.manage

------------------------------------------------------------------------

## role_permissions

``` text
role_id UUID FK
permission_id UUID FK
PRIMARY KEY(role_id, permission_id)
```

------------------------------------------------------------------------

# 6. CRM Tables

## leads

``` text
id UUID PK
organization_id UUID NOT NULL FK
name VARCHAR(200) NOT NULL
company_name VARCHAR(200)
email VARCHAR(255)
phone VARCHAR(50)
source VARCHAR(100)
status VARCHAR(30) NOT NULL
owner_id UUID FK users(id)
estimated_value NUMERIC(14,2)
score NUMERIC(5,2)
score_probability NUMERIC(5,4)
converted_customer_id UUID NULL FK customers(id)
created_at TIMESTAMPTZ
updated_at TIMESTAMPTZ
deleted_at TIMESTAMPTZ NULL
```

Checks:

``` text
score BETWEEN 0 AND 100
score_probability BETWEEN 0 AND 1
estimated_value >= 0
```

------------------------------------------------------------------------

## lead_interactions

``` text
id UUID PK
organization_id UUID NOT NULL FK
lead_id UUID NOT NULL FK
type VARCHAR(50) NOT NULL
channel VARCHAR(50)
content TEXT
occurred_at TIMESTAMPTZ NOT NULL
created_by UUID FK users(id)
created_at TIMESTAMPTZ
```

------------------------------------------------------------------------

## customers

``` text
id UUID PK
organization_id UUID NOT NULL FK
name VARCHAR(200) NOT NULL
company_name VARCHAR(200)
email VARCHAR(255)
phone VARCHAR(50)
industry VARCHAR(100)
account_owner_id UUID FK users(id)
health_status VARCHAR(30)
health_score NUMERIC(5,2)
revenue NUMERIC(14,2) DEFAULT 0
last_interaction_at TIMESTAMPTZ
created_at TIMESTAMPTZ
updated_at TIMESTAMPTZ
deleted_at TIMESTAMPTZ NULL
```

Checks: - health_score 0--100 - revenue \>= 0

------------------------------------------------------------------------

## customer_contacts

``` text
id UUID PK
organization_id UUID NOT NULL FK
customer_id UUID NOT NULL FK
name VARCHAR(200) NOT NULL
email VARCHAR(255)
phone VARCHAR(50)
job_title VARCHAR(100)
is_primary BOOLEAN DEFAULT false
created_at TIMESTAMPTZ
updated_at TIMESTAMPTZ
```

------------------------------------------------------------------------

# 7. Project Tables

## projects

``` text
id UUID PK
organization_id UUID NOT NULL FK
customer_id UUID NOT NULL FK
name VARCHAR(200) NOT NULL
description TEXT
status VARCHAR(30) NOT NULL
owner_id UUID FK users(id)
progress NUMERIC(5,2) DEFAULT 0
budget NUMERIC(14,2)
start_date DATE
due_date DATE
delay_probability NUMERIC(5,4)
risk_level VARCHAR(30)
created_at TIMESTAMPTZ
updated_at TIMESTAMPTZ
deleted_at TIMESTAMPTZ
```

Checks: - progress 0--100 - budget \>= 0 - delay_probability 0--1

------------------------------------------------------------------------

## project_members

``` text
project_id UUID FK
user_id UUID FK
role VARCHAR(50)
created_at TIMESTAMPTZ
PRIMARY KEY(project_id, user_id)
```

------------------------------------------------------------------------

## milestones

``` text
id UUID PK
organization_id UUID NOT NULL FK
project_id UUID NOT NULL FK
name VARCHAR(200) NOT NULL
description TEXT
due_date DATE
status VARCHAR(30)
progress NUMERIC(5,2)
created_at TIMESTAMPTZ
updated_at TIMESTAMPTZ
```

------------------------------------------------------------------------

## tasks

``` text
id UUID PK
organization_id UUID NOT NULL FK
project_id UUID NULL FK
customer_id UUID NULL FK
title VARCHAR(300) NOT NULL
description TEXT
assignee_id UUID FK users(id)
created_by UUID FK users(id)
priority VARCHAR(20) NOT NULL
status VARCHAR(30) NOT NULL
due_date TIMESTAMPTZ
estimated_hours NUMERIC(8,2)
actual_hours NUMERIC(8,2)
completed_at TIMESTAMPTZ
created_at TIMESTAMPTZ
updated_at TIMESTAMPTZ
deleted_at TIMESTAMPTZ
```

Checks: - estimated_hours \>= 0 - actual_hours \>= 0

------------------------------------------------------------------------

## task_dependencies

``` text
task_id UUID FK
depends_on_task_id UUID FK
PRIMARY KEY(task_id, depends_on_task_id)
```

Prevent self dependency.

------------------------------------------------------------------------

# 8. Ticket Tables

## tickets

``` text
id UUID PK
organization_id UUID NOT NULL FK
customer_id UUID NOT NULL FK
project_id UUID NULL FK
assigned_to UUID FK users(id)
subject VARCHAR(300) NOT NULL
description TEXT NOT NULL
category VARCHAR(100)
priority VARCHAR(20) NOT NULL
status VARCHAR(30) NOT NULL
sentiment VARCHAR(30)
sentiment_confidence NUMERIC(5,4)
predicted_priority VARCHAR(20)
priority_confidence NUMERIC(5,4)
sla_due_at TIMESTAMPTZ
resolved_at TIMESTAMPTZ
created_at TIMESTAMPTZ
updated_at TIMESTAMPTZ
```

Confidence values must be between 0 and 1.

------------------------------------------------------------------------

## ticket_comments

``` text
id UUID PK
organization_id UUID NOT NULL FK
ticket_id UUID NOT NULL FK
author_id UUID NOT NULL FK users(id)
body TEXT NOT NULL
is_internal BOOLEAN DEFAULT false
created_at TIMESTAMPTZ
updated_at TIMESTAMPTZ
```

Critical rule: Client users must never retrieve `is_internal = true`.

------------------------------------------------------------------------

# 9. Communication Tables

## conversations

``` text
id UUID PK
organization_id UUID NOT NULL FK
customer_id UUID NULL FK
project_id UUID NULL FK
ticket_id UUID NULL FK
type VARCHAR(30) NOT NULL
created_at TIMESTAMPTZ
updated_at TIMESTAMPTZ
```

## conversation_members

``` text
conversation_id UUID FK
user_id UUID FK
joined_at TIMESTAMPTZ
last_read_at TIMESTAMPTZ
PRIMARY KEY(conversation_id, user_id)
```

## messages

``` text
id UUID PK
organization_id UUID NOT NULL FK
conversation_id UUID NOT NULL FK
sender_id UUID NOT NULL FK users(id)
body TEXT NOT NULL
created_at TIMESTAMPTZ
edited_at TIMESTAMPTZ
deleted_at TIMESTAMPTZ
```

------------------------------------------------------------------------

# 10. Billing Tables

## invoices

``` text
id UUID PK
organization_id UUID NOT NULL FK
customer_id UUID NOT NULL FK
invoice_number VARCHAR(50) NOT NULL
status VARCHAR(30) NOT NULL
issue_date DATE NOT NULL
due_date DATE NOT NULL
subtotal NUMERIC(14,2) NOT NULL
tax NUMERIC(14,2) DEFAULT 0
discount NUMERIC(14,2) DEFAULT 0
total NUMERIC(14,2) NOT NULL
amount_paid NUMERIC(14,2) DEFAULT 0
currency CHAR(3) NOT NULL DEFAULT 'INR'
created_at TIMESTAMPTZ
updated_at TIMESTAMPTZ
```

Unique:

``` text
(organization_id, invoice_number)
```

All monetary values use `NUMERIC`, never floating-point.

------------------------------------------------------------------------

## invoice_items

``` text
id UUID PK
invoice_id UUID NOT NULL FK
description VARCHAR(300) NOT NULL
quantity NUMERIC(12,2) NOT NULL
unit_price NUMERIC(14,2) NOT NULL
tax_rate NUMERIC(5,2) DEFAULT 0
line_total NUMERIC(14,2) NOT NULL
```

Server calculates line totals.

------------------------------------------------------------------------

## payments

``` text
id UUID PK
organization_id UUID NOT NULL FK
invoice_id UUID NOT NULL FK
amount NUMERIC(14,2) NOT NULL
method VARCHAR(50)
status VARCHAR(30) NOT NULL
transaction_reference VARCHAR(200)
paid_at TIMESTAMPTZ
created_at TIMESTAMPTZ
updated_at TIMESTAMPTZ
```

------------------------------------------------------------------------

# 11. Documents

## documents

``` text
id UUID PK
organization_id UUID NOT NULL FK
uploaded_by UUID FK users(id)
customer_id UUID NULL FK
project_id UUID NULL FK
ticket_id UUID NULL FK
invoice_id UUID NULL FK
file_name VARCHAR(255) NOT NULL
storage_key TEXT NOT NULL
mime_type VARCHAR(100)
file_size BIGINT
version INTEGER DEFAULT 1
created_at TIMESTAMPTZ
updated_at TIMESTAMPTZ
deleted_at TIMESTAMPTZ
```

Never expose storage keys directly to unauthorized users.

Use signed URLs where applicable.

------------------------------------------------------------------------

# 12. Feedback

## feedback

``` text
id UUID PK
organization_id UUID NOT NULL FK
customer_id UUID NOT NULL FK
project_id UUID NULL FK
rating INTEGER
comment TEXT
created_at TIMESTAMPTZ
```

Constraint:

``` text
rating BETWEEN 1 AND 5
```

------------------------------------------------------------------------

# 13. AI Tables

## ai_predictions

``` text
id UUID PK
organization_id UUID NOT NULL FK
entity_type VARCHAR(50) NOT NULL
entity_id UUID NOT NULL
prediction_type VARCHAR(100) NOT NULL
prediction_value NUMERIC(10,6)
risk_level VARCHAR(30)
confidence NUMERIC(5,4)
model_name VARCHAR(100) NOT NULL
model_version VARCHAR(50) NOT NULL
explanation JSONB
created_at TIMESTAMPTZ NOT NULL
```

Examples: - lead_conversion - customer_churn - ticket_priority -
ticket_sentiment - project_delay

------------------------------------------------------------------------

## ai_recommendations

``` text
id UUID PK
organization_id UUID NOT NULL FK
prediction_id UUID NULL FK
entity_type VARCHAR(50)
entity_id UUID
title VARCHAR(300) NOT NULL
description TEXT NOT NULL
recommended_action TEXT
status VARCHAR(30) NOT NULL
created_at TIMESTAMPTZ
acted_at TIMESTAMPTZ
acted_by UUID FK users(id)
```

Statuses: - pending - accepted - rejected - completed - expired

------------------------------------------------------------------------

# 14. Notifications

## notifications

``` text
id UUID PK
organization_id UUID NOT NULL FK
user_id UUID NOT NULL FK
type VARCHAR(100) NOT NULL
title VARCHAR(300) NOT NULL
message TEXT NOT NULL
entity_type VARCHAR(50)
entity_id UUID
read_at TIMESTAMPTZ
created_at TIMESTAMPTZ
```

Index unread notifications by user.

------------------------------------------------------------------------

# 15. Audit Logs

## audit_logs

``` text
id UUID PK
organization_id UUID NOT NULL FK
actor_id UUID NULL FK users(id)
action VARCHAR(100) NOT NULL
entity_type VARCHAR(100)
entity_id UUID
before_data JSONB
after_data JSONB
metadata JSONB
created_at TIMESTAMPTZ NOT NULL
```

Audit logs should generally be append-only.

------------------------------------------------------------------------

# 16. Indexing Rules

At minimum index:

``` text
organization_id
customer_id
project_id
assigned_to / assignee_id
owner_id
status
created_at
updated_at
due_date
deleted_at
```

Composite examples:

``` sql
CREATE INDEX idx_customers_org_health
ON customers(organization_id, health_status);

CREATE INDEX idx_tasks_org_assignee_status
ON tasks(organization_id, assignee_id, status);

CREATE INDEX idx_tickets_org_status
ON tickets(organization_id, status);
```

Do not create indexes blindly. Add indexes based on query patterns.

------------------------------------------------------------------------

# 17. Foreign Key Rules

Default: - prevent accidental deletion of parent business records - use
`ON DELETE RESTRICT` for critical business entities - use
`ON DELETE CASCADE` for pure join tables where safe

Example: Deleting an organization should be a controlled application
operation, not an accidental cascading database operation.

------------------------------------------------------------------------

# 18. Timestamps

Use:

``` sql
TIMESTAMPTZ
```

Store timestamps in UTC.

Convert to user timezone only at presentation.

------------------------------------------------------------------------

# 19. Migrations

Use Alembic with SQLAlchemy.

Rules: 1. Never manually modify production schema. 2. Every schema
change requires migration. 3. Migration must be reversible where
practical. 4. Never delete columns containing production data without a
migration/data-retention decision.

------------------------------------------------------------------------

# 20. Transactions

Use transactions for: - lead conversion - invoice creation - payment
recording - permission changes - multi-table updates - important
workflow transitions

Lead conversion example:

``` text
BEGIN
  create/link customer
  update lead as converted
  preserve lead interactions
COMMIT
```

If any critical step fails, rollback.

------------------------------------------------------------------------

# 21. Data Integrity Rules

The database must enforce: - non-null required fields - foreign keys -
unique constraints - numeric ranges - valid status values where
practical - monetary non-negative constraints - timestamp consistency

Application validation alone is not enough.

------------------------------------------------------------------------

# 22. SQL vs CSV/TXT

The final architecture is:

``` text
PostgreSQL
    ↓
Primary business data
```

CSV: - import/export only

TXT: - not used for business data

JSON: - API payloads - JSONB only where flexible metadata is genuinely
required

Do NOT save customers/projects/tasks into JSON files.

------------------------------------------------------------------------

# 23. Backup

Production: - automated PostgreSQL backups - point-in-time recovery
where available - separate backup storage

Development: - seed scripts - migrations - sample data

Never commit production database dumps or credentials.
