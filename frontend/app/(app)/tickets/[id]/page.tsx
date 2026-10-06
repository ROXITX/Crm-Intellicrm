"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useApi } from "@/hooks/useApi";
import { Badge, DataState, PageHeader, errMsg } from "@/components/common/ui";
import { useToast } from "@/components/common/toast";
import { ago, pct, title } from "@/lib/format";
import type { Directory } from "@/types/api";

export default function TicketDetail() {
  const { id } = useParams<{ id: string }>();
  const { me, can } = useAuth();
  const toast = useToast();
  const client = me?.role === "client";
  const { data: t, loading, error, reload } = useApi<any>(`/tickets/${id}`);
  const { data: team } = useApi<Directory>(!client ? "/team/directory" : null);
  const [body, setBody] = useState("");
  const [internal, setInternal] = useState(false);
  const [assist, setAssist] = useState<any>(null);
  const patch = async (b: any, ok = "Updated") => { try { await api(`/tickets/${id}`, { method: "PATCH", body: b }); toast(ok); reload(); } catch (e) { toast(errMsg(e), "err"); } };
  const post = async () => { if (!body.trim()) return; try { await api(`/tickets/${id}/comments`, { body: { body, is_internal: internal } }); setBody(""); setInternal(false); reload(); } catch (e) { toast(errMsg(e), "err"); } };
  const loadAssist = async () => { try { setAssist(await api(`/tickets/${id}/assist`)); } catch (e) { toast(errMsg(e), "err"); } };
  return (
    <DataState loading={loading && !t} error={error} onRetry={reload}>
      {t && (<div>
        <PageHeader title={t.subject} subtitle={`${t.customer_name} · opened ${ago(t.created_at)}`} actions={<><Link href="/tickets" className="btn">Back</Link>
          {client ? (t.status !== "closed" ? <button className="btn" onClick={() => patch({ status: "closed" }, "Request closed")}>Close request</button> : <button className="btn" onClick={() => patch({ status: "open" }, "Reopened")}>Reopen</button>)
            : <>{can("internal.view") && <button className="btn" onClick={async () => { try { await api(`/tickets/${id}/escalate`, { method: "POST" }); toast("Escalated"); reload(); } catch (e) { toast(errMsg(e), "err"); } }}>Escalate</button>}</>}</>} />
        <div className="grid gap-4 lg:grid-cols-3">
          <div className="space-y-4 lg:col-span-2">
            <section className="card p-4"><p className="whitespace-pre-wrap">{t.description}</p></section>
            <section className="card"><div className="border-b border-line px-4 py-3"><h2>Conversation</h2></div>
              {t.comments.length === 0 ? <p className="p-6 text-center text-ink-2">No replies yet.</p> : <ul>{t.comments.map((c: any) => (
                <li key={c.id} className={`border-b border-line px-4 py-3 last:border-0 ${c.is_internal ? "bg-warning/5" : ""}`}><p className="text-small text-ink-2"><span className="font-medium text-ink">{c.author_name}</span> · {ago(c.created_at)} {c.is_internal && <Badge value="internal" tone="warning" label="Internal note" />}</p><p className="mt-1 whitespace-pre-wrap">{c.body}</p></li>))}</ul>}
              {can("tickets.write") && <div className="border-t border-line p-3">
                <textarea className="input min-h-20" placeholder={internal ? "Internal note (not visible to the customer)" : "Write a reply..."} aria-label="Reply" value={body} onChange={(e) => setBody(e.target.value)} />
                <div className="mt-2 flex items-center justify-between">{!client && can("internal.view") ? <label className="flex items-center gap-2 text-small"><input type="checkbox" checked={internal} onChange={(e) => setInternal(e.target.checked)} /> Internal note</label> : <span />}<button className="btn btn-primary" onClick={post}>{internal ? "Add note" : "Send reply"}</button></div></div>}
            </section>
          </div>
          <div className="space-y-4">
            <section className="card space-y-3 p-4"><h2>Details</h2>
              <div><p className="text-small text-ink-2">Status</p>{client ? <Badge value={t.status} /> : <select className="input" aria-label="Status" value={t.status} onChange={(e) => patch({ status: e.target.value })}>{["open", "in_progress", "waiting_customer", "waiting_internal", "resolved", "closed"].map((s) => <option key={s} value={s}>{title(s)}</option>)}</select>}</div>
              <div><p className="text-small text-ink-2">Priority</p>{client ? <Badge value={t.priority} /> : <select className="input" aria-label="Priority" value={t.priority} onChange={(e) => patch({ priority: e.target.value }, "Priority overridden")}>{["low", "medium", "high", "critical"].map((s) => <option key={s} value={s}>{title(s)}</option>)}</select>}</div>
              {!client && <div><p className="text-small text-ink-2">Assignee</p><select className="input" aria-label="Assignee" value={t.assigned_to || ""} onChange={(e) => e.target.value && patch({ assigned_to: e.target.value }, "Reassigned")}><option value="">Unassigned</option>{team?.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}</select></div>}
              <div><p className="text-small text-ink-2">Category</p><p>{t.category || "-"}</p></div>
              <div><p className="text-small text-ink-2">SLA due</p><p className={t.sla_due_at && new Date(t.sla_due_at) < new Date() && !["resolved", "closed"].includes(t.status) ? "text-danger" : ""}>{ago(t.sla_due_at)}</p></div>
            </section>
            {!client && (<section className="card space-y-3 p-4"><h2>AI assistance</h2>
              <p className="text-small">Sentiment: <Badge value={t.sentiment} /> {t.sentiment_confidence && <span className="text-ink-2">({pct(Number(t.sentiment_confidence))} confidence)</span>}</p>
              <p className="text-small">Predicted priority: <Badge value={t.predicted_priority} /> {t.priority_confidence && <span className="text-ink-2">({pct(Number(t.priority_confidence))})</span>}{t.predicted_priority && t.predicted_priority !== t.priority && <span className="ml-1 text-ink-2">· overridden by a human</span>}</p>
              {can("internal.view") && (assist ? (<div className="space-y-2"><p className="text-small font-medium text-ink-2">Summary</p><p>{assist.summary}</p><p className="text-small font-medium text-ink-2">Suggested reply (draft)</p><p className="rounded-ctl bg-muted p-3">{assist.suggested_reply}</p>
                <div className="flex gap-2"><button className="btn btn-sm" onClick={() => { setBody(assist.suggested_reply); setInternal(false); }}>Accept &amp; edit</button><button className="btn btn-sm" onClick={() => setAssist(null)}>Reject</button></div><p className="text-[11.5px] text-ink-2">{assist.note}</p></div>) : <button className="btn btn-sm" onClick={loadAssist}>Summarise &amp; suggest reply</button>)}
            </section>)}
          </div>
        </div>
      </div>)}
    </DataState>
  );
}
