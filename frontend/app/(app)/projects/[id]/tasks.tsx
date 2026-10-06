"use client";
import { api } from "@/lib/api";
import { useApi } from "@/hooks/useApi";
import { Badge, DataState, errMsg } from "@/components/common/ui";
import { useToast } from "@/components/common/toast";
import { date } from "@/lib/format";
import { TASK_STATUSES as STATUSES } from "@/components/crm/shared";
import type { Paged, Task } from "@/types/api";

export function ProjectTasks({ projectId }: { projectId: string }) {
  const { data, loading, error, reload } = useApi<Paged<Task>>("/tasks", { project_id: projectId, page_size: 100 });
  const toast = useToast();
  const set = async (id: string, status: string) => { try { await api(`/tasks/${id}`, { method: "PATCH", body: { status } }); reload(); } catch (e) { toast(errMsg(e), "err"); } };
  return (
    <div className="card overflow-hidden"><DataState loading={loading && !data} error={error} onRetry={reload} empty={!!data && data.items.length === 0 && { title: "No tasks yet" }}>
      <table><thead><tr><th>Task</th><th>Assignee</th><th>Priority</th><th>Due</th><th>Status</th></tr></thead><tbody>
        {data?.items.map((t) => <tr key={t.id}><td className="font-medium">{t.title}</td><td>{t.assignee_name || "-"}</td><td><Badge value={t.priority} /></td><td>{date(t.due_date)}</td>
          <td><select className="input w-36" aria-label={`Status of ${t.title}`} value={t.status} onChange={(e) => set(t.id, e.target.value)}>{STATUSES.map((s) => <option key={s} value={s}>{s.replace("_", " ")}</option>)}</select></td></tr>)}
      </tbody></table></DataState></div>
  );
}
