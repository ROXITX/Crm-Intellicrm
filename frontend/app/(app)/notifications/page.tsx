"use client";
import { api } from "@/lib/api";
import { useList } from "@/hooks/useList";
import { DataState, PageHeader, Pagination } from "@/components/common/ui";
import { ago } from "@/lib/format";

export default function Notifications() {
  const L = useList<any>("/notifications");
  const readAll = async () => { await api("/notifications/read-all", { method: "POST" }); L.reload(); };
  return (
    <div>
      <PageHeader title="Notifications" actions={<button className="btn" onClick={readAll}>Mark all read</button>} />
      <div className="card"><DataState loading={L.loading && !L.rows} error={L.error} onRetry={L.reload} empty={!!L.rows && L.rows.length === 0 && { title: "You're all caught up", hint: "New assignments, mentions and alerts appear here." }}>
        <ul>{L.rows?.map((n) => <li key={n.id} className={`border-b border-line px-4 py-3 last:border-0 ${n.read_at ? "" : "bg-primary/5"}`}><p className="font-medium">{n.title}</p><p className="text-ink-2">{n.message}</p><p className="text-small text-ink-2">{ago(n.created_at)}</p></li>)}</ul>
        <Pagination page={L.page} pageSize={L.pageSize} total={L.total} onChange={L.setPage} /></DataState></div>
    </div>
  );
}
