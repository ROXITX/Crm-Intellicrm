"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Area, AreaChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useApi } from "@/hooks/useApi";
import { useAuth } from "@/lib/auth";
import { Badge, Kpi, PageHeader, Progress, Skeleton, ErrorState } from "@/components/common/ui";
import { ago, date, money, num } from "@/lib/format";
import { Icon } from "@/components/common/Icon";

const ROUTES: Record<string, string> = { customer: "/customers", project: "/projects", ticket: "/tickets", invoice: "/invoices", lead: "/leads", task: "/tasks" };
const SEV: Record<string, string> = { critical: "danger", high: "danger", medium: "warning" };

export default function Dashboard() {
  const { me } = useAuth();
  const router = useRouter();
  const [range, setRange] = useState("30D");
  const { data: d, error, loading, reload } = useApi<any>("/dashboard", { range });
  useEffect(() => { if (me?.role === "client") router.replace("/portal"); }, [me, router]);

  if (error) return <ErrorState error={error} onRetry={reload} />;
  if (!d) return <div><PageHeader title="Dashboard" /><div className="grid grid-cols-2 gap-4 lg:grid-cols-5">{[0, 1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-24" />)}</div><Skeleton className="mt-4 h-72" /></div>;
  const k = d.kpis;
  return (
    <div>
      <PageHeader title="Dashboard" subtitle="Overview of your business performance and customer health" />
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
        <Kpi label="Total Customers" value={num(k.total_customers.value)} trend={k.total_customers.trend_pct} sub={`+${k.total_customers.new_this_month} this month`} />
        {k.new_leads && <Kpi label="New Leads" value={num(k.new_leads.value)} trend={k.new_leads.trend_pct} />}
        <Kpi label="Active Projects" value={num(k.active_projects.value)} sub="in progress" />
        <Kpi label="At Risk Customers" value={num(k.at_risk_customers.value)} sub="health: at risk / critical" />
        {k.revenue && <Kpi label="Revenue" value={money(k.revenue.value)} trend={k.revenue.trend_pct} />}
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-3">
        {d.revenue_pipeline && (
          <section className="card p-4 xl:col-span-2" aria-label="Revenue and pipeline">
            <div className="mb-3 flex items-center justify-between"><h2>Revenue &amp; Pipeline</h2>
              <div className="flex gap-1" role="group" aria-label="Range">{["7D", "30D", "90D", "12M"].map((r) => <button key={r} className={`btn btn-sm ${range === r ? "btn-primary" : ""}`} onClick={() => setRange(r)} aria-pressed={range === r}>{r}</button>)}</div></div>
            {d.revenue_pipeline.series.length === 0 ? <p className="py-16 text-center text-ink-2">No revenue or pipeline activity in this period.</p> : (
              <div className="h-64"><ResponsiveContainer><AreaChart data={d.revenue_pipeline.series} margin={{ left: 8, right: 8, top: 4 }}>
                <CartesianGrid stroke="var(--border)" vertical={false} />
                <XAxis dataKey="period" tickFormatter={(v) => date(v).slice(0, 6)} tick={{ fontSize: 12, fill: "var(--text-secondary)" }} stroke="var(--border)" />
                <YAxis tickFormatter={(v) => (v >= 1e7 ? `${+(v / 1e7).toFixed(1)}Cr` : v >= 1e5 ? `${+(v / 1e5).toFixed(1)}L` : v >= 1e3 ? `${+(v / 1e3).toFixed(0)}k` : `${v}`)} tick={{ fontSize: 12, fill: "var(--text-secondary)" }} stroke="var(--border)" width={44} />
                <Tooltip formatter={(v: number) => money(v)} labelFormatter={(l) => date(String(l))} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Area type="linear" dataKey="revenue" name="Revenue" stroke="var(--primary)" fill="var(--primary)" fillOpacity={0.12} strokeWidth={2} />
                <Area type="linear" dataKey="pipeline" name="Pipeline" stroke="var(--info)" fill="var(--info)" fillOpacity={0.06} strokeWidth={2} strokeDasharray="4 3" />
              </AreaChart></ResponsiveContainer></div>)}
          </section>
        )}
        {d.funnel && (
          <section className="card p-4" aria-label="Lead conversion funnel"><h2 className="mb-3">Lead Conversion Funnel</h2>
            <ul className="space-y-3">{d.funnel.map((f: any) => (
              <li key={f.stage}><div className="mb-1 flex justify-between text-small"><span className="capitalize">{f.stage}</span><span className="text-ink-2">{f.count} · {f.conversion_pct}%</span></div><Progress value={f.conversion_pct} tone="primary" /></li>))}</ul>
          </section>
        )}
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-3">
        <section className="card xl:col-span-2" aria-label="Attention required">
          <div className="border-b border-line px-4 py-3"><h2>Attention Required</h2></div>
          {d.attention_required.length === 0 ? <p className="p-6 text-center text-ink-2">Nothing needs your attention right now.</p> : (
            <ul>{d.attention_required.map((a: any, i: number) => (
              <li key={i} className="flex flex-wrap items-center gap-3 border-b border-line px-4 py-3 last:border-0">
                <Badge value={a.severity} tone={SEV[a.severity]} label={`${a.severity.toUpperCase()}`} />
                <div className="min-w-0 flex-1"><p className="truncate font-medium">{a.title}</p><p className="truncate text-small text-ink-2">{a.reason}</p></div>
                {ROUTES[a.entity_type] && <Link href={`${ROUTES[a.entity_type]}/${a.entity_id}`} className="btn btn-sm">Review</Link>}
              </li>))}</ul>)}
        </section>
        <section className="card p-4" aria-label="Project status"><h2 className="mb-3">Project Status</h2>
          {(() => { const p = d.project_status; const tot = p.on_track + p.at_risk + p.delayed + p.completed || 1; const seg = [["On track", p.on_track, "success"], ["At risk", p.at_risk, "warning"], ["Delayed", p.delayed, "danger"], ["Completed", p.completed, "info"]] as const;
            return (<><div className="flex h-2.5 overflow-hidden rounded-full bg-line" role="img" aria-label="Project status distribution">{seg.map(([l, v, c]) => <span key={l} style={{ width: `${(v / tot) * 100}%`, background: `var(--${c})` }} />)}</div>
              <ul className="mt-4 space-y-2">{seg.map(([l, v, c]) => <li key={l} className="flex items-center justify-between"><span className="flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-sm" style={{ background: `var(--${c})` }} />{l}</span><span className="font-medium">{v}</span></li>)}</ul></>); })()}
        </section>
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-3">
        {d.team_workload && (
          <section className="card xl:col-span-2" aria-label="Team workload"><div className="flex items-center justify-between border-b border-line px-4 py-3"><h2>Team Workload</h2><Link href="/team" className="text-small text-primary">View team</Link></div>
            <ul>{d.team_workload.map((m: any) => (
              <li key={m.user_id} className="grid grid-cols-[1fr_auto] items-center gap-x-4 gap-y-1 border-b border-line px-4 py-2.5 last:border-0 sm:grid-cols-[160px_90px_1fr_80px]">
                <span className="font-medium">{m.name}</span><span className="text-ink-2">{m.active_tasks} tasks{m.overdue_tasks ? ` · ${m.overdue_tasks} overdue` : ""}</span>
                <div className="col-span-2 sm:col-span-1"><Progress value={m.capacity_pct} /></div>
                <span className={`text-right ${m.status === "overloaded" ? "font-medium text-danger" : ""}`}>{Math.round(m.capacity_pct)}% {m.status === "overloaded" && <Icon name="warn" size={14} className="inline" />}</span>
              </li>))}</ul></section>
        )}
        <section className="card" aria-label="Recent activity"><div className="border-b border-line px-4 py-3"><h2>Recent Activity</h2></div>
          {d.recent_activity.length === 0 ? <p className="p-6 text-center text-ink-2">No recent activity.</p> : <ul>{d.recent_activity.map((a: any, i: number) => (
            <li key={i} className="border-b border-line px-4 py-2.5 last:border-0"><p><span className="font-medium">{a.actor}</span> {a.action}</p><p className="text-small text-ink-2">{ago(a.at)}</p></li>))}</ul>}
        </section>
      </div>

      {me?.role !== "staff" || d.insights.customers_need_attention ? (
        <section className="mt-4 flex flex-wrap items-center justify-between gap-4 rounded-card border border-line bg-surface-muted px-5 py-4" aria-label="Insights from IntelliCRM">
          <div><p className="font-semibold">Insights from IntelliCRM</p>
            <ul className="mt-1 text-ink-2"><li>{d.insights.customers_need_attention} customer(s) need attention</li><li>{d.insights.projects_may_miss_deadline} project(s) may miss their deadlines</li>
              {d.team_workload && <li>{d.insights.overloaded_members} team member(s) overloaded</li>}</ul></div>
          <Link href="/ai-insights" className="btn btn-primary">View AI Insights</Link>
        </section>
      ) : null}
    </div>
  );
}
