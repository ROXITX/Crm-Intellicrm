"use client";
import Link from "next/link";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useApi } from "@/hooks/useApi";
import { Badge, DataState, PageHeader, errMsg } from "@/components/common/ui";
import { useToast } from "@/components/common/toast";
import { date, pct, title } from "@/lib/format";

const SECTIONS: [string, string, string?][] = [["customer_risks", "Customer risks", "/customers"], ["lead_opportunities", "Lead opportunities", "/leads"], ["project_delays", "Project delays", "/projects"], ["ticket_risks", "Ticket risks", "/tickets"], ["revenue_anomalies", "Revenue anomalies"], ["workload_warnings", "Team workload warnings"]];

function Insight({ i, base }: { i: any; base?: string }) {
  return (
    <li className="border-b border-line px-4 py-3.5 last:border-0">
      <div className="flex flex-wrap items-center gap-2"><Badge value={i.risk_level || "medium"} /><span className="font-medium">{base && i.entity_id ? <Link className="hover:underline" href={`${base}/${i.entity_id}`}>{i.title}</Link> : i.title}</span>
        {i.probability != null && <span className="text-small text-ink-2">{pct(i.probability)} probability{i.confidence != null && ` · ${pct(i.confidence)} confidence`}</span>}</div>
      <p className="mt-1">{i.prediction}</p>
      {i.factors?.length > 0 && <ul className="mt-1 list-disc pl-5 text-small text-ink-2">{i.factors.slice(0, 4).map((f: any, k: number) => <li key={k}>{f.label}</li>)}</ul>}
      {i.recommended_actions?.length > 0 && <p className="mt-1.5 rounded-ctl bg-muted px-3 py-2 text-small"><b>Recommended:</b> {i.recommended_actions[0]}</p>}
      <p className="mt-1 text-[11.5px] text-ink-2">{i.model_name} v{i.model_version} · {date(i.generated_at)}</p>
    </li>
  );
}

export default function AIInsights() {
  const { can } = useAuth();
  const toast = useToast();
  const { data, loading, error, reload } = useApi<any>("/ai/insights");
  const recs = useApi<any>("/ai/recommendations", { page_size: 20 });
  const decide = async (id: string, decision: string) => { try { await api(`/ai/recommendations/${id}/decision`, { body: { decision } }); toast(`Recommendation ${decision}`); recs.reload(); } catch (e) { toast(errMsg(e), "err"); } };
  return (
    <div>
      <PageHeader title="AI Insights" subtitle="Predictions with their reasons, confidence and recommended actions. You decide what happens next." actions={can("ai.manage") && <button className="btn" onClick={async () => { try { await api("/ai/run", { method: "POST" }); toast("Refresh queued - reload in a few seconds"); setTimeout(() => { reload(); recs.reload(); }, 4000); } catch (e) { toast(errMsg(e), "err"); } }}>Refresh predictions</button>} />
      <section className="card mb-4"><div className="border-b border-line px-4 py-3"><h2>Pending recommendations</h2></div>
        <DataState loading={recs.loading && !recs.data} error={recs.error} onRetry={recs.reload} empty={!!recs.data && recs.data.items.length === 0 && { title: "No pending recommendations" }}>
          <ul>{recs.data?.items.map((r: any) => (<li key={r.id} className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-4 py-3 last:border-0"><div className="min-w-0 flex-1"><p className="font-medium">{r.title}</p><p className="text-small text-ink-2">{r.description}</p>{r.recommended_action && <p className="mt-0.5 text-small">→ {r.recommended_action}</p>}</div>
            <div className="flex gap-2"><button className="btn btn-sm btn-primary" onClick={() => decide(r.id, "accepted")}>Accept</button><button className="btn btn-sm" onClick={() => decide(r.id, "rejected")}>Reject</button></div></li>))}</ul></DataState></section>
      <DataState loading={loading && !data} error={error} onRetry={reload}>
        <div className="grid gap-4 xl:grid-cols-2">{data && SECTIONS.map(([k, label, base]) => (<section key={k} className="card"><div className="border-b border-line px-4 py-3"><h2>{label}</h2></div>
          {data[k].length === 0 ? <p className="p-6 text-center text-ink-2">Nothing to flag.</p> : <ul>{data[k].map((i: any, n: number) => <Insight key={n} i={i} base={base} />)}</ul>}</section>))}</div>
      </DataState>
    </div>
  );
}
