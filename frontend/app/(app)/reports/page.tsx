"use client";
import { useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { download } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useApi } from "@/hooks/useApi";
import { DataState, PageHeader, errMsg } from "@/components/common/ui";
import { useToast } from "@/components/common/toast";
import { title } from "@/lib/format";

const REPORTS = [
  ["lead_funnel", "Lead funnel", "Sales", "leads.read"], ["conversion", "Conversion by source", "Sales", "leads.read"], ["customer_health", "Customer health", "Customers", "customers.read"], ["churn_risk", "Churn risk", "Customers", "ai.read"],
  ["project_performance", "Project performance", "Projects", "projects.read"], ["support_performance", "Support performance", "Support", "tickets.read"], ["revenue", "Revenue", "Revenue", "invoices.read"],
  ["overdue_invoices", "Overdue invoices", "Revenue", "invoices.read"], ["workload", "Team workload", "Team", "team.read"], ["ai_accuracy", "AI model quality", "AI", "ai.read"],
] as const;

export default function ReportsPage() {
  const { can } = useAuth();
  const toast = useToast();
  const available = REPORTS.filter((r) => can(r[3]));
  const [name, setName] = useState<string>(available[0]?.[0] || "lead_funnel");
  const today = new Date(); const d0 = new Date(today.getTime() - 90 * 864e5);
  const [from, setFrom] = useState(d0.toISOString().slice(0, 10));
  const [to, setTo] = useState(today.toISOString().slice(0, 10));
  const { data, loading, error, reload } = useApi<any>(`/reports/${name}`, { date_from: from, date_to: to });
  const chartable = data && data.columns.length === 2 && data.rows.length > 1 && !isNaN(Number(data.rows[0][1]));
  return (
    <div>
      <PageHeader title="Reports" subtitle="All reports respect your role and organization boundaries" actions={<button className="btn" onClick={() => download(`/reports/${name}?format=csv&date_from=${from}&date_to=${to}`, `${name}.csv`).catch((e) => toast(errMsg(e), "err"))}>Export CSV</button>} />
      <div className="card mb-4 grid gap-3 p-3 md:grid-cols-4">
        <select className="input md:col-span-2" aria-label="Report" value={name} onChange={(e) => setName(e.target.value)}>{["Sales", "Customers", "Projects", "Support", "Revenue", "Team", "AI"].map((g) => <optgroup key={g} label={g}>{available.filter((r) => r[2] === g).map((r) => <option key={r[0]} value={r[0]}>{r[1]}</option>)}</optgroup>)}</select>
        <input className="input" type="date" aria-label="From" value={from} onChange={(e) => setFrom(e.target.value)} /><input className="input" type="date" aria-label="To" value={to} onChange={(e) => setTo(e.target.value)} />
      </div>
      {chartable && <section className="card mb-4 p-4"><div className="h-60"><ResponsiveContainer><BarChart data={data.rows.map((r: any[]) => ({ label: String(r[0]), value: Number(r[1]) }))}><CartesianGrid stroke="var(--border)" vertical={false} /><XAxis dataKey="label" tick={{ fontSize: 12, fill: "var(--text-secondary)" }} /><YAxis tick={{ fontSize: 12, fill: "var(--text-secondary)" }} width={50} /><Tooltip /><Bar dataKey="value" fill="var(--primary)" radius={[3, 3, 0, 0]} /></BarChart></ResponsiveContainer></div></section>}
      <div className="card overflow-hidden"><DataState loading={loading && !data} error={error} onRetry={reload} empty={!!data && data.rows.length === 0 && { title: "No data for this report", hint: "Try a wider date range." }}>
        <div className="overflow-x-auto"><table><thead><tr>{data?.columns.map((c: string) => <th key={c}>{title(c)}</th>)}</tr></thead><tbody>{data?.rows.map((r: any[], i: number) => <tr key={i}>{r.map((c, j) => <td key={j}>{String(c ?? "-")}</td>)}</tr>)}</tbody></table></div></DataState></div>
    </div>
  );
}
