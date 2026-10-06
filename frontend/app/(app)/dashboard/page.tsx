"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Bar, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useApi } from "@/hooks/useApi";
import { useAuth } from "@/lib/auth";
import { Badge, ErrorState, Progress, Skeleton } from "@/components/common/ui";
import { Avatar } from "@/components/common/Avatar";
import { Icon } from "@/components/common/Icon";
import { ago, money, num, title } from "@/lib/format";

const SPAN: Record<number, string> = { 12: "xl:col-span-12", 8: "xl:col-span-8", 6: "xl:col-span-6", 5: "xl:col-span-5", 4: "xl:col-span-4", 3: "xl:col-span-3" };
const ROUTES: Record<string, string> = { customer: "/customers", project: "/projects", ticket: "/tickets", invoice: "/invoices", lead: "/leads", task: "/tasks" };
const lakh = (v: string | number) => { const n = Number(v); return n >= 1e7 ? `₹${+(n / 1e7).toFixed(2)}Cr` : n >= 1e5 ? `₹${+(n / 1e5).toFixed(2)}L` : money(n); };
const compact = (v: number) => (v >= 1e7 ? `${+(v / 1e7).toFixed(1)}Cr` : v >= 1e5 ? `${+(v / 1e5).toFixed(1)}L` : v >= 1e3 ? `${+(v / 1e3).toFixed(0)}k` : `${v}`);
const RANGES = [["12M", "Last 12 months"], ["90D", "Last 90 days"], ["30D", "Last 30 days"], ["7D", "Last 7 days"]];

const TONES: Record<string, { fg: string; bg: string }> = {
  primary: { fg: "var(--primary)", bg: "color-mix(in srgb, var(--primary) 11%, white)" },
  success: { fg: "var(--success)", bg: "color-mix(in srgb, var(--success) 12%, white)" },
  warning: { fg: "var(--warning)", bg: "color-mix(in srgb, var(--warning) 14%, white)" },
  danger: { fg: "var(--danger)", bg: "color-mix(in srgb, var(--danger) 11%, white)" },
  info: { fg: "var(--info)", bg: "color-mix(in srgb, var(--info) 13%, white)" },
};
const IconTile = ({ icon, tone, size = 44 }: { icon: string; tone: keyof typeof TONES; size?: number }) => (
  <span className="grid shrink-0 place-items-center rounded-[11px]" style={{ width: size, height: size, background: TONES[tone].bg, color: TONES[tone].fg }}><Icon name={icon} size={size * 0.5} /></span>
);

function Card({ title: t, action, children, className = "", pad = true }: { title: string; action?: React.ReactNode; children: React.ReactNode; className?: string; pad?: boolean }) {
  return (
    <section className={`card flex flex-col ${className}`} aria-label={t}>
      <header className="flex items-center justify-between px-5 pb-1 pt-4"><h2 className="text-[16px]">{t}</h2>{action}</header>
      <div className={`flex-1 ${pad ? "px-5 pb-4 pt-2" : ""}`}>{children}</div>
    </section>
  );
}
const ViewAll = ({ href }: { href: string }) => <Link href={href} className="text-small font-medium text-primary hover:underline">View all</Link>;

function Kpi({ icon, tone, label, value, trend, invert }: { icon: string; tone: keyof typeof TONES; label: string; value: React.ReactNode; trend?: number | null; invert?: boolean }) {
  const good = trend == null ? true : invert ? trend <= 0 : trend >= 0;
  return (
    <div className="card flex items-center gap-3.5 px-4 py-4">
      <IconTile icon={icon} tone={tone} />
      <div className="min-w-0">
        <p className="whitespace-nowrap text-small text-ink-2">{label}</p>
        <p className="text-[26px] font-bold leading-9 tracking-tight">{value}</p>
        {trend != null ? <p className="text-small"><span className={`font-semibold ${good ? "text-success" : "text-danger"}`}>{trend >= 0 ? "↑" : "↓"} {Math.abs(trend)}%</span> <span className="whitespace-nowrap text-ink-2">vs last month</span></p> : <p className="text-small text-ink-2">&nbsp;</p>}
      </div>
    </div>
  );
}

function Funnel({ stages }: { stages: { stage: string; count: number; conversion_pct: number }[] }) {
  const max = Math.max(...stages.map((s) => s.count), 1);
  const colors = ["#2F80F5", "#5BA4F8", "#2BA3B8", "#27A66A", "#1E9A5A"];
  const ROW = 48;
  const width = (c: number) => Math.max(c / max, 0.3) * 100;
  return (
    <div className="flex items-start gap-4" role="img" aria-label={`Funnel: ${stages.map((s) => `${s.count} ${s.stage}`).join(", ")}`}>
      <div className="w-[48%] shrink-0">
        {stages.map((s, i) => {
          const w = width(s.count), nw = i < stages.length - 1 ? width(stages[i + 1].count) : w * 0.7;
          const inset = ((1 - nw / w) / 2) * 100;
          return (
            <div key={s.stage} style={{ height: ROW, paddingBottom: 4 }}>
              <div className="mx-auto h-full" style={{ width: `${w}%`, background: colors[i], clipPath: `polygon(0 0, 100% 0, ${100 - inset}% 100%, ${inset}% 100%)` }} />
            </div>
          );
        })}
      </div>
      <ul className="flex-1">
        {stages.map((s, i) => (
          <li key={s.stage} className="flex items-center gap-2.5" style={{ height: ROW }}>
            <span className="w-9 text-[21px] font-semibold tabular-nums">{s.count}</span>
            <span className="text-[13.5px] text-ink-2">{title(s.stage)}{i === stages.length - 1 ? ` (${s.conversion_pct}%)` : ""}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

const ACT_TONE: Record<string, [string, keyof typeof TONES]> = { lead: ["lead", "success"], won: ["check", "success"], customer: ["customer", "primary"], ticket: ["ticket", "warning"], payment: ["rupee", "success"], task: ["task", "info"], project: ["project", "primary"], invoice: ["invoice", "info"], document: ["document", "info"] };

export default function Dashboard() {
  const { me } = useAuth();
  const router = useRouter();
  const [range, setRange] = useState("12M");
  const { data: d, error, reload } = useApi<any>("/dashboard", { range });
  useEffect(() => { if (me?.role === "client") router.replace("/portal"); }, [me, router]);
  const [now, setNow] = useState<Date | null>(null);
  useEffect(() => setNow(new Date()), [d]);

  if (error) return <ErrorState error={error} onRetry={reload} />;
  const hour = now?.getHours() ?? 9;
  const greet = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";
  const header = (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-[30px]">{greet}, {me?.first_name} <span aria-hidden>👋</span></h1>
        <p className="mt-1 text-[15px] text-ink-2">Here&apos;s what&apos;s happening with your business today.</p>
      </div>
      <div className="text-right text-small text-ink-2">
        <p className="text-[14px] text-ink">{now?.toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "short", year: "numeric" })}</p>
        <p>Last updated {now?.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" })}</p>
      </div>
    </div>
  );
  if (!d) return <div>{header}<div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">{[0, 1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-[100px]" />)}</div><Skeleton className="mt-4 h-72" /></div>;

  const k = d.kpis;
  const ins = d.insights;
  const topUsed = (d.revenue_pipeline ? 5 : 0) + (d.funnel ? 3 : 0);
  const attnSpan = SPAN[12 - topUsed] || SPAN[12];
  const rowCount = (d.team_workload ? 1 : 0) + 2;
  const rowSpan = SPAN[12 / rowCount];
  return (
    <div>
      {header}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <Kpi icon="team" tone="primary" label="Total Customers" value={num(k.total_customers.value)} trend={k.total_customers.trend_pct} />
        {k.new_leads && <Kpi icon="leads" tone="primary" label="New Leads" value={num(k.new_leads.value)} trend={k.new_leads.trend_pct} />}
        <Kpi icon="clipboard" tone="success" label="Active Projects" value={num(k.active_projects.value)} />
        <Kpi icon="alert" tone="danger" label="At Risk Customers" value={num(k.at_risk_customers.value)} />
        {k.revenue && <Kpi icon="rupee" tone="success" label="Revenue (30d)" value={lakh(k.revenue.value)} trend={k.revenue.trend_pct} />}
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-12">
        {d.revenue_pipeline && (
          <Card title="Revenue & Pipeline" className="xl:col-span-5" action={
            <select className="rounded-ctl border border-line bg-surface px-2.5 py-1 text-small" aria-label="Chart range" value={range} onChange={(e) => setRange(e.target.value)}>{RANGES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>}>
            {d.revenue_pipeline.series.every((x: any) => !x.revenue && !x.pipeline) ? <p className="py-16 text-center text-ink-2">No revenue or pipeline activity in this period.</p> : (
              <div className="h-[250px]"><ResponsiveContainer>
                <ComposedChart data={d.revenue_pipeline.series} margin={{ left: -8, right: 4, top: 8 }}>
                  <CartesianGrid stroke="var(--border)" vertical={false} strokeDasharray="3 3" />
                  <XAxis dataKey="period" tickFormatter={(v) => new Date(v).toLocaleDateString("en-GB", range === "12M" ? { month: "short" } : { day: "numeric", month: "short" })} tick={{ fontSize: 12, fill: "var(--text-secondary)" }} axisLine={false} tickLine={false} />
                  <YAxis tickFormatter={compact} tick={{ fontSize: 12, fill: "var(--text-secondary)" }} axisLine={false} tickLine={false} width={44} />
                  <Tooltip formatter={(v: number, n: string) => [money(v), n]} labelFormatter={(l) => new Date(String(l)).toLocaleDateString("en-GB", { month: "long", year: "numeric", ...(range === "12M" ? {} : { day: "numeric" }) })} contentStyle={{ borderRadius: 8, border: "1px solid var(--border)", fontSize: 12 }} />
                  <Bar dataKey="revenue" name="Revenue" fill="var(--primary)" radius={[4, 4, 0, 0]} maxBarSize={22} />
                  <Line type="linear" dataKey="pipeline" name="Pipeline Value" stroke="#7BB0F7" strokeWidth={2} dot={{ r: 3, fill: "#fff", stroke: "#7BB0F7", strokeWidth: 2 }} />
                </ComposedChart></ResponsiveContainer></div>)}
            <div className="mt-1 flex justify-center gap-5 text-small text-ink-2"><span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-sm bg-primary" />Revenue</span><span className="flex items-center gap-1.5"><span className="h-0.5 w-4 bg-[#7BB0F7]" />Pipeline Value</span></div>
          </Card>
        )}
        {d.funnel && <Card title="Lead Conversion Funnel" className="xl:col-span-3"><Funnel stages={d.funnel} /></Card>}
        <Card title="Attention Required" className={attnSpan} action={<ViewAll href="/ai-insights" />} pad={false}>
          {d.attention_required.length === 0 ? <p className="p-6 text-center text-ink-2">Nothing needs your attention right now.</p> : (
            <ul>{d.attention_required.slice(0, 5).map((a: any, i: number) => {
              const high = a.severity === "critical" || a.severity === "high";
              const href = ROUTES[a.entity_type] ? `${ROUTES[a.entity_type]}/${a.entity_id}` : "/ai-insights";
              return (
                <li key={i}><Link href={href} className="flex items-center gap-3 px-5 py-2.5 hover:bg-muted">
                  <IconTile icon={a.kind === "overdue_payment" ? "rupee" : "alert"} tone={high ? "danger" : "warning"} size={36} />
                  <span className="min-w-0 flex-1"><span className="block truncate text-[13.5px] font-semibold">{a.title.split(":")[0]}</span><span className="block truncate text-small text-ink-2">{a.reason}</span></span>
                  <Badge value={high ? "high" : "medium"} tone={high ? "danger" : "warning"} label={high ? "High" : "Medium"} />
                </Link></li>);
            })}</ul>)}
        </Card>
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-12">
        {d.team_workload && (
          <Card title="Team Workload" className={rowSpan} action={<ViewAll href="/team" />}>
            <ul className="space-y-3.5">{d.team_workload.filter((m: any) => m.member_status === "active").slice(0, 6).map((m: any) => {
              const tone = m.capacity_pct > 100 ? "danger" : m.capacity_pct >= 80 ? "warning" : m.capacity_pct >= 50 ? "primary" : "success";
              return (
                <li key={m.user_id} className="flex items-center gap-3">
                  <Avatar name={m.name} size={36} />
                  <div className="w-24 shrink-0 leading-tight"><p className="truncate text-[13.5px] font-semibold">{m.name}</p><p className="text-small capitalize text-ink-2">{m.role}</p></div>
                  <div className="flex-1"><Progress value={m.capacity_pct} tone={tone as any} /></div>
                  <span className="w-12 text-right text-[13px] font-medium tabular-nums">{Math.round(m.capacity_pct)}%</span>
                </li>);
            })}</ul>
          </Card>
        )}
        <Card title="Project Status" className={rowSpan} action={<ViewAll href="/projects" />}>
          {d.projects.length === 0 ? <p className="py-8 text-center text-ink-2">No projects yet.</p> : (
            <ul className="space-y-3.5">{d.projects.map((p: any) => {
              const st = p.status === "completed" ? ["Completed", "success"] : p.status === "delayed" ? ["Delayed", "warning"] : p.status === "at_risk" || p.risk_level === "high" ? ["At Risk", "danger"] : ["On Track", "success"];
              return (
                <li key={p.id}><Link href={`/projects/${p.id}`} className="flex items-center gap-3">
                  <IconTile icon="project" tone={st[1] as any} size={34} />
                  <span className="w-[38%] min-w-0 leading-tight"><span className="block truncate text-[13.5px] font-semibold">{p.name}</span><span className="block truncate text-small text-ink-2">{p.customer_name}</span></span>
                  <span className="flex-1"><Progress value={p.progress} tone={st[1] === "danger" ? "danger" : st[1] === "warning" ? "warning" : "primary"} /></span>
                  <span className="w-9 text-right text-small tabular-nums">{Math.round(p.progress)}%</span>
                  <Badge value={st[0]} tone={st[1]} label={st[0]} />
                </Link></li>);
            })}</ul>)}
        </Card>
        <Card title="Recent Activity" className={rowSpan} action={<ViewAll href="/notifications" />}>
          {d.recent_activity.length === 0 ? <p className="py-8 text-center text-ink-2">No recent activity.</p> : (
            <ul className="space-y-3.5">{d.recent_activity.slice(0, 5).map((a: any, i: number) => {
              const [icon, tone] = ACT_TONE[a.icon] || ["task", "info"];
              return (
                <li key={i} className="flex items-center gap-3"><IconTile icon={icon} tone={tone} size={34} />
                  <span className="min-w-0 flex-1 leading-tight"><span className="block truncate text-[13.5px] font-semibold">{a.action.charAt(0).toUpperCase() + a.action.slice(1)}</span><span className="block truncate text-small text-ink-2">{a.detail || a.actor}</span></span>
                  <span className="shrink-0 text-small text-ink-2">{ago(a.at)}</span></li>);
            })}</ul>)}
        </Card>
      </div>

      <section className="mt-4 rounded-card border border-line bg-[color-mix(in_srgb,var(--primary)_6%,white)] p-4" aria-label="Insights from IntelliCRM">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3"><IconTile icon="sparkle" tone="primary" size={36} /><p className="text-[16px] font-semibold">Insights from IntelliCRM</p><span className="badge badge-primary">BETA</span></div>
          <button className="btn btn-primary px-4 py-2" onClick={() => window.dispatchEvent(new Event("crm:ask"))}><Icon name="sparkle" size={16} /> Ask IntelliCRM <Icon name="chevron" size={14} /></button>
        </div>
        <div className={`grid gap-3 ${ins.lead_conversion ? "md:grid-cols-3" : "md:grid-cols-2"}`}>
          {ins.lead_conversion && <div className="flex items-start gap-3 rounded-card border border-line bg-surface p-3.5"><IconTile icon="trend" tone="success" size={36} />
            <div className="min-w-0 text-small"><p className="text-[13.5px] font-semibold">{ins.lead_conversion?.rate_pct != null ? `Lead conversion is ${ins.lead_conversion.rate_pct}%` : "Lead conversion"}{ins.lead_conversion?.delta_pct ? ` (${ins.lead_conversion.delta_pct > 0 ? "+" : ""}${ins.lead_conversion.delta_pct} pts)` : ""}</p><p className="text-ink-2">Compared with the previous 30 days.</p></div></div>}
          <div className="flex items-start gap-3 rounded-card border border-line bg-surface p-3.5"><IconTile icon="alert" tone="warning" size={36} />
            <div className="min-w-0 text-small"><p className="text-[13.5px] font-semibold">{ins.projects_may_miss_deadline} project(s) may face delays</p><p className="text-ink-2">Based on current progress and team workload.</p><Link href="/ai-insights" className="font-medium text-primary">View details →</Link></div></div>
          <div className="flex items-start gap-3 rounded-card border border-line bg-surface p-3.5"><IconTile icon="customers" tone="primary" size={36} />
            <div className="min-w-0 text-small"><p className="text-[13.5px] font-semibold">{ins.customers_need_attention} customer(s) show churn risk</p><p className="text-ink-2">Engagement, tickets and payments are trending down.</p><Link href="/ai-insights" className="font-medium text-primary">View details →</Link></div></div>
        </div>
      </section>
    </div>
  );
}
