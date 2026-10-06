"use client";
import { useState } from "react";
import { useList } from "@/hooks/useList";
import { DataTable } from "@/components/common/DataTable";
import { Modal, PageHeader } from "@/components/common/ui";
import { ago, date } from "@/lib/format";

type A = { id: string; action: string; entity_type: string | null; entity_id: string | null; actor_email: string | null; before_data: any; after_data: any; metadata: any; created_at: string };

export default function AuditLogs() {
  const L = useList<A>("/audit-logs", {}, 50);
  const [sel, setSel] = useState<A | null>(null);
  return (
    <div>
      <PageHeader title="Audit Logs" subtitle="Append-only record of security- and business-relevant actions" />
      <div className="card mb-4 grid grid-cols-2 gap-3 p-3 md:grid-cols-4">
        <input className="input" placeholder="Action prefix (e.g. invoice.)" aria-label="Action" value={L.filters.action || ""} onChange={(e) => L.setFilter("action", e.target.value)} />
        <input className="input" placeholder="Entity type" aria-label="Entity type" value={L.filters.entity_type || ""} onChange={(e) => L.setFilter("entity_type", e.target.value)} />
        <input className="input" type="date" aria-label="From" value={L.filters.date_from || ""} onChange={(e) => L.setFilter("date_from", e.target.value)} /><input className="input" type="date" aria-label="To" value={L.filters.date_to || ""} onChange={(e) => L.setFilter("date_to", e.target.value)} />
      </div>
      <DataTable<A> rows={L.rows} loading={L.loading} error={L.error} onRetry={L.reload} page={L.page} pageSize={L.pageSize} total={L.total} onPage={L.setPage} onRowClick={setSel} empty={{ title: "No audit entries match", hint: "Try widening the filters." }}
        columns={[{ key: "t", header: "When", render: (a) => <span title={a.created_at}>{ago(a.created_at)}</span> }, { key: "a", header: "Action", render: (a) => <span className="font-medium">{a.action}</span> }, { key: "e", header: "Entity", render: (a) => a.entity_type || "-" }, { key: "u", header: "Actor", render: (a) => a.actor_email || "system" }, { key: "ip", header: "IP", render: (a) => a.metadata?.ip || "-" }]} />
      <Modal open={!!sel} onClose={() => setSel(null)} title={sel?.action || ""} width="max-w-2xl">{sel && <div className="space-y-3 text-small"><p>{date(sel.created_at)} · {sel.actor_email || "system"} · {sel.entity_type} {sel.entity_id}</p>
        {[["Before", sel.before_data], ["After", sel.after_data], ["Metadata", sel.metadata]].map(([k, v]) => v ? <div key={k as string}><p className="font-medium">{k as string}</p><pre className="overflow-auto rounded-ctl bg-muted p-3">{JSON.stringify(v, null, 2)}</pre></div> : null)}</div>}</Modal>
    </div>
  );
}
