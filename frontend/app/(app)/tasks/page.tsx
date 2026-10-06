"use client";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useList } from "@/hooks/useList";
import { useApi } from "@/hooks/useApi";
import { DataTable } from "@/components/common/DataTable";
import { Badge, Field, Modal, PageHeader, errMsg } from "@/components/common/ui";
import { useToast } from "@/components/common/toast";
import { TASK_STATUSES } from "@/components/crm/shared";
import { date, title } from "@/lib/format";
import type { Directory, Paged, Project, Task } from "@/types/api";

const schema = z.object({ title: z.string().min(1, "Title is required").max(300), project_id: z.string().optional(), assignee_id: z.string().optional(), priority: z.enum(["low", "medium", "high", "critical"]),
  due_date: z.string().optional(), estimated_hours: z.string().regex(/^\d*(\.\d{0,2})?$/, "Invalid number").optional() });

function AddTask({ open, onClose, onDone }: { open: boolean; onClose: () => void; onDone: () => void }) {
  const { can } = useAuth();
  const { register, handleSubmit, reset, formState: { errors, isSubmitting } } = useForm<z.infer<typeof schema>>({ resolver: zodResolver(schema), defaultValues: { priority: "medium" } });
  const { data: team } = useApi<Directory>(open ? "/team/directory" : null);
  const { data: projects } = useApi<Paged<Project>>(open ? "/projects" : null, { page_size: 100 });
  const toast = useToast();
  return (
    <Modal open={open} onClose={onClose} title="New task">
      <form className="space-y-3" noValidate onSubmit={handleSubmit(async (v) => {
        try { await api("/tasks", { body: { title: v.title, priority: v.priority, project_id: v.project_id || null, assignee_id: v.assignee_id || null, due_date: v.due_date ? new Date(v.due_date).toISOString() : null, estimated_hours: v.estimated_hours || null } }); toast("Task created"); reset(); onDone(); onClose(); } catch (e) { toast(errMsg(e), "err"); }
      })}>
        <Field label="Title" required error={errors.title?.message}><input className="input" {...register("title")} /></Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Project"><select className="input" {...register("project_id")}><option value="">None</option>{projects?.items.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</select></Field>
          <Field label="Assignee"><select className="input" {...register("assignee_id")} disabled={!can("tasks.assign")}><option value="">Me</option>{team?.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}</select></Field>
          <Field label="Priority"><select className="input" {...register("priority")}>{["low", "medium", "high", "critical"].map((p) => <option key={p} value={p}>{title(p)}</option>)}</select></Field>
          <Field label="Due date"><input className="input" type="date" {...register("due_date")} /></Field>
          <Field label="Estimated hours" error={errors.estimated_hours?.message}><input className="input" inputMode="decimal" {...register("estimated_hours")} /></Field>
        </div>
        <div className="flex justify-end gap-2 pt-2"><button type="button" className="btn" onClick={onClose}>Cancel</button><button className="btn btn-primary" disabled={isSubmitting}>Create task</button></div>
      </form>
    </Modal>
  );
}

export default function TasksPage() {
  const { can } = useAuth();
  const toast = useToast();
  const L = useList<Task>("/tasks");
  const [add, setAdd] = useState(false);
  const setStatus = async (t: Task, status: string) => { try { await api(`/tasks/${t.id}`, { method: "PATCH", body: { status } }); L.reload(); } catch (e) { toast(errMsg(e), "err"); } };
  const f = L.filters;
  return (
    <div>
      <PageHeader title="Tasks" subtitle="Work items ordered by priority and due date" actions={can("tasks.write") && <button className="btn btn-primary" onClick={() => setAdd(true)}>New Task</button>} />
      <div className="card mb-4 grid grid-cols-2 gap-3 p-3 md:grid-cols-5">
        <input className="input col-span-2" placeholder="Search tasks" aria-label="Search tasks" value={f.q || ""} onChange={(e) => L.setFilter("q", e.target.value)} />
        <select className="input" aria-label="Status" value={f.status || ""} onChange={(e) => L.setFilter("status", e.target.value)}><option value="">All statuses</option>{TASK_STATUSES.map((s) => <option key={s} value={s}>{title(s)}</option>)}</select>
        <select className="input" aria-label="Priority" value={f.priority || ""} onChange={(e) => L.setFilter("priority", e.target.value)}><option value="">All priorities</option>{["critical", "high", "medium", "low"].map((s) => <option key={s} value={s}>{title(s)}</option>)}</select>
        <label className="flex items-center gap-2 text-[13px]"><input type="checkbox" checked={!!f.mine} onChange={(e) => L.setFilter("mine", e.target.checked)} /> Assigned to me</label>
      </div>
      <DataTable<Task> rows={L.rows} loading={L.loading} error={L.error} onRetry={L.reload} page={L.page} pageSize={L.pageSize} total={L.total} onPage={L.setPage}
        empty={{ title: "No tasks found", hint: "Try changing your filters or create a task.", action: can("tasks.write") ? <button className="btn btn-primary" onClick={() => setAdd(true)}>New Task</button> : undefined }}
        columns={[
          { key: "t", header: "Task", render: (t) => <div><p className="font-medium">{t.title}</p><p className="text-small text-ink-2">{t.project_name || "No project"}</p></div> },
          { key: "a", header: "Assignee", render: (t) => t.assignee_name || "-" },
          { key: "p", header: "Priority", render: (t) => <Badge value={t.priority} tone={t.priority === "critical" ? "danger" : t.priority === "high" ? "warning" : "neutral"} /> },
          { key: "d", header: "Due", render: (t) => <span className={t.due_date && new Date(t.due_date) < new Date() && !["done", "cancelled"].includes(t.status) ? "text-danger" : ""}>{date(t.due_date)}</span> },
          { key: "h", header: "Est / actual h", render: (t) => `${t.estimated_hours ?? "-"} / ${t.actual_hours ?? "-"}` },
          { key: "s", header: "Status", render: (t) => <select className="input w-36" aria-label={`Status of ${t.title}`} value={t.status} onChange={(e) => setStatus(t, e.target.value)}>{TASK_STATUSES.map((s) => <option key={s} value={s}>{title(s)}</option>)}</select> },
        ]} />
      <AddTask open={add} onClose={() => setAdd(false)} onDone={L.reload} />
    </div>
  );
}
