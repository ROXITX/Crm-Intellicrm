export type NavItem = { href: string; label: string; icon: string; perm?: string; internalOnly?: boolean; action?: "ask" };
export type NavGroup = { title: string; items: NavItem[] };

export const STAFF_NAV: NavGroup[] = [
  { title: "Main", items: [
    { href: "/dashboard", label: "Dashboard", icon: "dashboard", perm: "customers.read" },
    { href: "/leads", label: "Leads", icon: "leads", perm: "leads.read" },
    { href: "/customers", label: "Customers", icon: "customers", perm: "customers.read" },
    { href: "/projects", label: "Projects", icon: "projects", perm: "projects.read" },
    { href: "/tasks", label: "Tasks", icon: "tasks", perm: "tasks.read" },
    { href: "/tickets", label: "Tickets", icon: "tickets", perm: "tickets.read" },
    { href: "/messages", label: "Messages", icon: "messages", perm: "messages.read" },
  ] },
  { title: "Business", items: [
    { href: "/invoices", label: "Invoices", icon: "invoices", perm: "invoices.read" },
    { href: "/payments", label: "Payments", icon: "payments", perm: "invoices.read" },
    { href: "/documents", label: "Documents", icon: "documents", perm: "documents.read" },
    { href: "/reports", label: "Reports", icon: "reports", perm: "reports.read" },
  ] },
  { title: "Intelligence", items: [
    { href: "/ai-insights", label: "AI Insights", icon: "ai", perm: "ai.read" },
    { href: "#ask", label: "Ask IntelliCRM", icon: "ask", perm: "messages.read", action: "ask" },
  ] },
  { title: "Administration", items: [
    { href: "/team", label: "Team", icon: "team", perm: "team.read" },
    { href: "/settings", label: "Settings", icon: "settings", perm: "settings.manage" },
    { href: "/audit-logs", label: "Audit Logs", icon: "audit", perm: "audit.read" },
  ] },
];

// Clients never see internal CRM terminology (DESIGN.md section 22).
export const CLIENT_NAV: NavGroup[] = [
  { title: "", items: [
    { href: "/portal", label: "Home", icon: "home" },
    { href: "/projects", label: "My Projects", icon: "projects" },
    { href: "/tickets", label: "Requests", icon: "tickets" },
    { href: "/messages", label: "Messages", icon: "messages" },
    { href: "/documents", label: "Documents", icon: "documents" },
    { href: "/invoices", label: "Invoices", icon: "invoices" },
    { href: "/settings", label: "Profile", icon: "settings" },
  ] },
];
