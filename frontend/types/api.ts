export type Paged<T> = { items: T[]; page: number; page_size: number; total: number };
export type Me = {
  id: string; email: string; first_name: string; last_name: string | null; role: "owner" | "manager" | "staff" | "client";
  permissions: string[]; organization: { id: string; name: string; slug: string };
};
export type Factor = { feature?: string; label: string; impact: number | null; direction?: string };
export type Prediction = {
  id: string; probability: number | null; risk_level: string | null; confidence: number | null; summary: string | null;
  factors: Factor[]; recommended_actions: string[]; business_rules: string[]; disclaimer: string;
  model_name: string; model_version: string; created_at: string;
};
export type Lead = {
  id: string; name: string; company_name: string | null; email: string | null; phone: string | null; source: string | null;
  status: string; owner_id: string | null; owner_name?: string | null; estimated_value: string | null; score: string | null;
  score_probability: string | null; converted_customer_id: string | null; last_contact_at?: string | null; created_at: string;
};
export type Customer = {
  id: string; name: string; company_name: string | null; email: string | null; phone: string | null; industry: string | null;
  account_owner_id?: string | null; owner_name?: string | null; health_status?: string | null; health_score?: string | null;
  revenue: string; last_interaction_at: string | null; project_count?: number; open_tickets?: number; notes?: string | null; tags?: string | null;
};
export type Project = {
  id: string; customer_id: string; customer_name?: string; name: string; description: string | null; status: string; owner_id: string | null;
  owner_name?: string | null; progress: string; budget: string | null; start_date: string | null; due_date: string | null;
  delay_probability?: string | null; risk_level?: string | null;
};
export type Task = {
  id: string; project_id: string | null; project_name?: string | null; title: string; description: string | null; assignee_id: string | null;
  assignee_name?: string | null; priority: string; status: string; due_date: string | null; estimated_hours: string | null; actual_hours: string | null;
};
export type Ticket = {
  id: string; customer_id: string; customer_name?: string; subject: string; description: string; category: string | null; priority: string; status: string;
  sentiment?: string | null; sentiment_confidence?: string | null; predicted_priority?: string | null; priority_confidence?: string | null;
  assignee_name?: string | null; sla_due_at: string | null; created_at: string;
};
export type Invoice = {
  id: string; customer_id: string; customer_name?: string; invoice_number: string; status: string; issue_date: string; due_date: string;
  subtotal: string; tax: string; discount: string; total: string; amount_paid: string; balance?: string; currency: string;
};
export type Directory = { id: string; name: string; role: string }[];
