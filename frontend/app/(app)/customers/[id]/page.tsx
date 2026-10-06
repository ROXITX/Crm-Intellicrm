"use client";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useApi } from "@/hooks/useApi";
import { Badge, Confirm, DataState, Field, Kpi, Modal, PageHeader, Progress, Tabs, errMsg } from "@/components/common/ui";
import { Explanation } from "@/components/ai/Explanation";
import { useToast } from "@/components/common/toast";
import { ago, date, money, title } from "@/lib/format";

function Mini({ path, params, render, empty }: { path: string; params: any; render: (r: any) => React.ReactNode; empty: string }) {
  const { data, loading, error, reload } = useApi<any>(path, params);
  return <div className="card"><DataState loading={loading && !data} error={error} onRetry={reload} empty={!!data && data.items.length === 0 && { title: empty }}><ul>{data?.items.map((r: any) => <li key={r.id} className="border-b border-line px-4 py-3 last:border-0">{render(r)}</li>)}</ul></DataState></div>;
}

export default function Customer360() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { can, me } = useAuth();
  const toast = useToast();
  const { data: c, error, loading, reload } = useApi<any>(`/customers/${id}`);
  const internal = me?.role !== "client";
  const [tab, setTab] = useState("overview");
  const [del, setDel] = useState(false);
  const [portal, setPortal] = useState(false);
  const [pu, setPu] = useState({ email: "", first_name: "", password: "" });
  const tabs = [{ id: "overview", label: "Overview" }, { id: "projects", label: "Projects" }, { id: "tickets", label: "Tickets" }, { id: "billing", label: "Billing" }, { id: "communication", label: "Communication" }, { id: "documents", label: "Documents" },
    ...(internal ? [{ id: "activity", label: "Activity" }, { id: "ai", label: "AI Insights" }] : [])];
  return (
    <DataState loading={loading && !c} error={error} onRetry={reload}>
      {c && (<div>
        <PageHeader title={c.name} subtitle={[c.company_name, c.industry].filter(Boolean).join(" · ")} actions={<>
          <Link href="/customers" className="btn">Back</Link>
          {internal && <Link href={`/messages?customer=${id}`} className="btn">Message</Link>}
          {can("team.manage") && <button className="btn" onClick={() => setPortal(true)}>Add portal login</button>}
          {can("customers.write") && <button className="btn btn-danger" onClick={() => setDel(true)}>Archive</button>}</>} />
        <div className="mb-4 grid grid-cols-2 gap-4 lg:grid-cols-4">
          {internal && <div className="card px-4 py-3.5"><p className="text-[11.5px] font-medium uppercase tracking-wide text-ink-2">Health</p><p className="mt-1 flex items-center gap-2 text-[22px] font-semibold">{c.health_score ? Math.round(Number(c.health_score)) : "-"} <Badge value={c.health_status} /></p><p className="text-small text-ink-2">Owner: {c.owner_name || "-"}</p></div>}
          <Kpi label="Revenue" value={money(c.revenue)} sub="lifetime paid" /><Kpi label="Active projects" value={c.active_projects} sub={`${c.open_tickets} open ticket(s)`} /><Kpi label="Outstanding" value={money(c.outstanding_amount)} sub="unpaid invoices" />
        </div>
        <Tabs tabs={tabs} value={tab} onChange={setTab} />
        {tab === "overview" && (<div className="grid gap-4 lg:grid-cols-2">
          <section className="card p-4"><h2 className="mb-3">Contacts</h2>{c.contacts.length === 0 ? <p className="text-ink-2">No contacts yet.</p> : <ul className="space-y-2">{c.contacts.map((x: any) => <li key={x.id}><span className="font-medium">{x.name}</span> {x.is_primary && <Badge value="primary" tone="primary" label="Primary" />}<p className="text-small text-ink-2">{[x.job_title, x.email, x.phone].filter(Boolean).join(" · ")}</p></li>)}</ul>}</section>
          <section className="card p-4"><h2 className="mb-3">Details</h2><dl className="grid grid-cols-2 gap-3"><div><dt className="text-small text-ink-2">Email</dt><dd>{c.email || "-"}</dd></div><div><dt className="text-small text-ink-2">Phone</dt><dd>{c.phone || "-"}</dd></div><div><dt className="text-small text-ink-2">Last interaction</dt><dd>{ago(c.last_interaction_at)}</dd></div>{internal && <div><dt className="text-small text-ink-2">Tags</dt><dd>{c.tags || "-"}</dd></div>}</dl>{internal && c.notes && <p className="mt-3 rounded-ctl bg-muted p-3 text-small">{c.notes}</p>}</section>
        </div>)}
        {tab === "projects" && <Mini path="/projects" params={{ customer_id: id }} empty="No projects" render={(p) => <Link href={`/projects/${p.id}`} className="flex items-center justify-between gap-4"><span className="font-medium">{p.name}</span><span className="flex items-center gap-3"><Badge value={p.status} /><span className="w-24"><Progress value={Number(p.progress)} /></span></span></Link>} />}
        {tab === "tickets" && <Mini path="/tickets" params={{ customer_id: id }} empty="No tickets" render={(t) => <Link href={`/tickets/${t.id}`} className="flex items-center justify-between gap-4"><span className="font-medium">{t.subject}</span><span className="flex gap-2"><Badge value={t.priority} /><Badge value={t.status} /></span></Link>} />}
        {tab === "billing" && <Mini path="/invoices" params={{ customer_id: id }} empty="No invoices" render={(i) => <Link href={`/invoices/${i.id}`} className="flex items-center justify-between gap-4"><span><span className="font-medium">{i.invoice_number}</span> <span className="text-ink-2">due {date(i.due_date)}</span></span><span className="flex items-center gap-3">{money(i.total, i.currency)}<Badge value={i.status} /></span></Link>} />}
        {tab === "communication" && <CommTab id={id} />}
        {tab === "documents" && <Mini path="/documents" params={{ customer_id: id }} empty="No documents" render={(d) => <span className="font-medium">{d.file_name} <span className="text-small text-ink-2">· {date(d.created_at)}</span></span>} />}
        {tab === "activity" && <ActivityTab id={id} />}
        {tab === "ai" && (<div className="grid gap-4 lg:grid-cols-2">
          <section className="card p-4"><h2 className="mb-3">Churn risk</h2><Explanation p={c.ai?.churn} label="Churn probability" /></section>
          <section className="card p-4"><h2 className="mb-3">Support sentiment trend</h2>{c.ai?.sentiment_trend.recent.length ? <><div className="flex gap-1.5">{c.ai.sentiment_trend.recent.map((s: any, i: number) => <span key={i} title={`${s.sentiment} · ${date(s.at)}`} className="h-8 w-5 rounded-sm" style={{ background: `var(--${s.sentiment === "positive" ? "success" : s.sentiment === "negative" ? "danger" : "border"})` }} />)}</div><p className="mt-2 text-small text-ink-2">Positive {c.ai.sentiment_trend.counts.positive} · Neutral {c.ai.sentiment_trend.counts.neutral} · Negative {c.ai.sentiment_trend.counts.negative} (last 10 tickets)</p></> : <p className="text-ink-2">No ticket sentiment yet.</p>}</section>
        </div>)}
        <Confirm open={del} onClose={() => setDel(false)} danger title="Archive customer" message="The customer will be hidden from lists. Projects, invoices and history are retained." confirmLabel="Archive"
          onConfirm={async () => { try { await api(`/customers/${id}`, { method: "DELETE" }); toast("Customer archived"); router.push("/customers"); } catch (e) { toast(errMsg(e), "err"); } }} />
        <Modal open={portal} onClose={() => setPortal(false)} title="Create client portal login">
          <form className="space-y-3" onSubmit={async (e) => { e.preventDefault(); try { await api(`/customers/${id}/portal-users`, { body: pu }); toast("Portal login created"); setPortal(false); setPu({ email: "", first_name: "", password: "" }); reload(); } catch (er) { toast(errMsg(er), "err"); } }}>
            <Field label="Email" required><input className="input" type="email" required value={pu.email} onChange={(e) => setPu({ ...pu, email: e.target.value })} /></Field>
            <Field label="First name" required><input className="input" required value={pu.first_name} onChange={(e) => setPu({ ...pu, first_name: e.target.value })} /></Field>
            <Field label="Temporary password" required hint="At least 10 characters"><input className="input" type="password" minLength={10} required value={pu.password} onChange={(e) => setPu({ ...pu, password: e.target.value })} /></Field>
            <div className="flex justify-end gap-2"><button type="button" className="btn" onClick={() => setPortal(false)}>Cancel</button><button className="btn btn-primary">Create login</button></div>
          </form>
        </Modal>
      </div>)}
    </DataState>
  );
}

function ActivityTab({ id }: { id: string }) {
  const { data, loading, error, reload } = useApi<any[]>(`/customers/${id}/activity`);
  return <div className="card"><DataState loading={loading && !data} error={error} onRetry={reload} empty={!!data && data.length === 0 && { title: "No activity recorded" }}><ul>{data?.map((a) => <li key={a.id} className="flex justify-between border-b border-line px-4 py-2.5 last:border-0"><span>{title(a.action.replace(".", " "))}</span><span className="text-small text-ink-2">{ago(a.created_at)}</span></li>)}</ul></DataState></div>;
}

function CommTab({ id }: { id: string }) {
  const { data, loading, error, reload } = useApi<any[]>("/conversations", { customer_id: id });
  return <div className="card"><DataState loading={loading && !data} error={error} onRetry={reload} empty={!!data && data.length === 0 && { title: "No conversations with this customer yet", hint: "Start one from the Messages page." }}>
    <ul>{data?.map((c) => <li key={c.id} className="border-b border-line px-4 py-3 last:border-0"><Link href={`/messages?c=${c.id}`} className="flex items-center justify-between gap-4"><span><span className="font-medium">{c.title || "Conversation"}</span> <Badge value={c.type} tone={c.type === "client" ? "info" : "neutral"} /><span className="block truncate text-small text-ink-2">{c.last_message || "No messages"}</span></span><span className="text-small text-ink-2">{ago(c.last_message_at)}</span></Link></li>)}</ul></DataState></div>;
}
