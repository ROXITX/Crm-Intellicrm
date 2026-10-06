export type NavItem = { href: string; label: string; icon: string; perm?: string; action?: "ask"; badge?: "messages" };
export type NavGroup = { title: string; items: NavItem[] };

// Flat list matching the approved reference; items you lack permission for are hidden.
export const STAFF_NAV: NavGroup[] = [
  { title: "", items: [
    { href: "/dashboard", label: "Dashboard", icon: "home", perm: "customers.read" },
    { href: "/leads", label: "Leads", icon: "leads", perm: "leads.read" },
    { href: "/customers", label: "Customers", icon: "customers", perm: "customers.read" },
    { href: "/projects", label: "Projects", icon: "projects", perm: "projects.read" },
    { href: "/tasks", label: "Tasks", icon: "tasks", perm: "tasks.read" },
    { href: "/tickets", label: "Tickets", icon: "tickets", perm: "tickets.read" },
    { href: "/messages", label: "Messages", icon: "messages", perm: "messages.read", badge: "messages" },
    { href: "/invoices", label: "Invoices", icon: "invoices", perm: "invoices.read" },
    { href: "/payments", label: "Payments", icon: "payments", perm: "invoices.read" },
    { href: "/documents", label: "Documents", icon: "documents", perm: "documents.read" },
    { href: "/team", label: "Team", icon: "team", perm: "team.read" },
    { href: "/ai-insights", label: "AI Insights", icon: "ai", perm: "ai.read" },
    { href: "/reports", label: "Reports", icon: "reports", perm: "reports.read" },
  ] },
  { title: "secondary", items: [
    { href: "/audit-logs", label: "Audit Logs", icon: "audit", perm: "audit.read" },
    { href: "/settings", label: "Settings", icon: "settings" },
    { href: "#ask", label: "Ask IntelliCRM", icon: "ask", perm: "messages.read", action: "ask" },
  ] },
];

// Clients never see internal CRM terminology (DESIGN.md section 22).
export const CLIENT_NAV: NavGroup[] = [
  { title: "", items: [
    { href: "/portal", label: "Home", icon: "home" },
    { href: "/projects", label: "My Projects", icon: "projects" },
    { href: "/tickets", label: "Requests", icon: "tickets" },
    { href: "/messages", label: "Messages", icon: "messages", badge: "messages" },
    { href: "/documents", label: "Documents", icon: "documents" },
    { href: "/invoices", label: "Invoices", icon: "invoices" },
  ] },
  { title: "secondary", items: [{ href: "/settings", label: "Profile", icon: "settings" }] },
];
