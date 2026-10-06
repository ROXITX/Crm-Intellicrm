"""Permission catalog and system-role mapping (seeded into the DB)."""

PERMISSIONS = {
    "customers.read": "View customers", "customers.write": "Create/edit customers",
    "leads.read": "View leads", "leads.write": "Create/edit/convert leads",
    "projects.read": "View projects", "projects.write": "Create/edit projects",
    "tasks.read": "View tasks", "tasks.write": "Create/update tasks", "tasks.assign": "Assign tasks",
    "tickets.read": "View tickets", "tickets.write": "Create/update tickets",
    "messages.read": "Read messages", "messages.write": "Send messages",
    "invoices.read": "View invoices", "invoices.write": "Create/edit invoices",
    "payments.write": "Record payments",
    "documents.read": "View documents", "documents.write": "Upload documents",
    "reports.read": "View reports", "ai.read": "View AI insights", "ai.manage": "Run/configure AI",
    "team.read": "View team & workload", "team.manage": "Manage users and roles",
    "audit.read": "View audit logs", "settings.manage": "Manage organization settings",
    "portal.access": "Use the client portal", "internal.view": "See internal-only data",
}

_ALL = set(PERMISSIONS) - {"portal.access"}

ROLE_PERMISSIONS = {
    "owner": _ALL,
    "manager": _ALL - {"team.manage", "audit.read", "settings.manage", "invoices.write", "payments.write"},
    "staff": {"customers.read", "projects.read", "tasks.read", "tasks.write", "tickets.read", "tickets.write",
              "messages.read", "messages.write", "documents.read", "documents.write", "ai.read", "internal.view"},
    "client": {"portal.access", "customers.read", "projects.read", "tickets.read", "tickets.write",
               "messages.read", "messages.write", "documents.read", "invoices.read"},
}
ROLE_DESCRIPTIONS = {
    "owner": "Organization owner/admin - full access",
    "manager": "Manages teams, projects and support within assigned scope",
    "staff": "Works on assigned customers, tasks and tickets",
    "client": "External customer using the client portal",
}
