"use client";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useApi } from "@/hooks/useApi";
import { Badge, Confirm, DataState, PageHeader, errMsg } from "@/components/common/ui";
import { Explanation } from "@/components/ai/Explanation";
import { useToast } from "@/components/common/toast";
import { ago, date, money, title } from "@/lib/format";
import { LEAD_STATUSES as STATUSES, ScoreBadge } from "@/components/crm/shared";

const TYPES = ["email", "call", "meeting", "note", "reply", "inquiry", "pricing_page", "proposal_requested"];

export default function Lead360() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { can } = useAuth();
  const toast = useToast();
  const { data: l, error, loading, reload } = useApi<any>(`/leads/${id}`);
  const [type, setType] = useState("note");
  const [content, setContent] = useState("");
  const [conv, setConv] = useState(false);
  const act = async (fn: () => Promise<any>, ok: string) => { try { await fn(); toast(ok); reload(); } catch (e) { toast(errMsg(e), "err"); } };
  const w = can("leads.write");
  return (
    <DataState loading={loading && !l} error={error} onRetry={reload}>
      {l && (<div>
        <PageHeader title={l.name} subtitle={[l.company_name, l.email, l.phone].filter(Boolean).join(" · ") || "Lead"} actions={<>
          <Link href="/leads" className="btn">Back</Link>
          {w && !l.converted_customer_id && <button className="btn btn-primary" onClick={() => setConv(true)}>Convert to customer</button>}
          {l.converted_customer_id && <Link className="btn" href={`/customers/${l.converted_customer_id}`}>View customer</Link>}</>} />
        <div className="grid gap-4 lg:grid-cols-3">
          <div className="space-y-4 lg:col-span-2">
            <section className="card p-4"><h2 className="mb-3">Lead profile</h2>
              <dl className="grid grid-cols-2 gap-3 md:grid-cols-4">
                {[["Status", <Badge key="s" value={l.status} />], ["Source", title(l.source)], ["Est. value", money(l.estimated_value)], ["Created", date(l.created_at)]].map(([k, v]) => <div key={k as string}><dt className="text-small text-ink-2">{k}</dt><dd className="mt-0.5">{v}</dd></div>)}
              </dl>
              {w && !l.converted_customer_id && <div className="mt-4 flex items-center gap-2"><label className="text-small text-ink-2" htmlFor="st">Move stage</label>
                <select id="st" className="input w-44" value={l.status} onChange={(e) => act(() => api(`/leads/${id}`, { method: "PATCH", body: { status: e.target.value } }), "Stage updated")}>{STATUSES.map((s) => <option key={s} value={s}>{title(s)}</option>)}</select></div>}
            </section>
            <section className="card"><div className="border-b border-line px-4 py-3"><h2>Interaction timeline</h2></div>
              {w && <form className="flex flex-wrap gap-2 border-b border-line p-3" onSubmit={(e) => { e.preventDefault(); act(() => api(`/leads/${id}/interactions`, { body: { type, content: content || null } }), "Interaction logged").then(() => setContent("")); }}>
                <select className="input w-44" aria-label="Interaction type" value={type} onChange={(e) => setType(e.target.value)}>{TYPES.map((t) => <option key={t} value={t}>{title(t)}</option>)}</select>
                <input className="input min-w-0 flex-1" placeholder="Notes (optional)" value={content} maxLength={5000} onChange={(e) => setContent(e.target.value)} aria-label="Notes" />
                <button className="btn btn-primary">Log</button></form>}
              {l.interactions.length === 0 ? <p className="p-6 text-center text-ink-2">No interactions yet.</p> : <ul>{l.interactions.map((i: any) => (
                <li key={i.id} className="flex gap-3 border-b border-line px-4 py-3 last:border-0"><Badge value={i.type} tone="primary" /><div><p>{i.content || title(i.type)}</p><p className="text-small text-ink-2">{ago(i.occurred_at)}</p></div></li>))}</ul>}
            </section>
          </div>
          <section className="card h-fit p-4"><div className="mb-3 flex items-center justify-between"><h2>Lead score</h2>{w && <button className="btn btn-sm" onClick={() => act(() => api(`/leads/${id}/score`, { method: "POST" }), "Score refreshed")}>Refresh</button>}</div>
            <p className="mb-3 text-[28px] font-semibold">{l.score != null ? Math.round(Number(l.score)) : "-"}<span className="text-[15px] font-normal text-ink-2"> / 100</span> <ScoreBadge s={l.score} /></p>
            <Explanation p={l.score_explanation} label="Estimated conversion probability" />
          </section>
        </div>
        <Confirm open={conv} onClose={() => setConv(false)} title="Convert lead" message="This creates a customer from the lead and marks the lead as won. The lead and its interaction history are kept." confirmLabel="Convert"
          onConfirm={async () => { try { const r = await api<any>(`/leads/${id}/convert`, { method: "POST" }); toast("Lead converted"); router.push(`/customers/${r.customer.id}`); } catch (e) { toast(errMsg(e), "err"); } }} />
      </div>)}
    </DataState>
  );
}
