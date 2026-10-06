"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useApi } from "@/hooks/useApi";
import { Badge, DataState, PageHeader, Progress, Tabs, errMsg } from "@/components/common/ui";
import { Explanation } from "@/components/ai/Explanation";
import { useToast } from "@/components/common/toast";
import { date, money, title } from "@/lib/format";
import { ProjectTasks } from "./tasks";

export default function ProjectDetail() {
  const { id } = useParams<{ id: string }>();
  const { me, can } = useAuth();
  const toast = useToast();
  const { data: p, loading, error, reload } = useApi<any>(`/projects/${id}`);
  const internal = me?.role !== "client";
  const [tab, setTab] = useState("overview");
  const tabs = [{ id: "overview", label: "Overview" }, ...(internal ? [{ id: "tasks", label: "Tasks" }] : []), { id: "milestones", label: "Milestones" }, ...(internal ? [{ id: "team", label: "Team" }] : []), { id: "files", label: "Files" }, ...(internal ? [{ id: "risk", label: "AI Risk" }] : [])];
  const status = async (s: string) => { try { await api(`/projects/${id}`, { method: "PATCH", body: { status: s } }); toast("Status updated"); reload(); } catch (e) { toast(errMsg(e), "err"); } };
  return (
    <DataState loading={loading && !p} error={error} onRetry={reload}>
      {p && (<div>
        <PageHeader title={p.name} subtitle={`${p.customer_name}${p.due_date ? ` · due ${date(p.due_date)}` : ""}`} actions={<><Link href="/projects" className="btn">Back</Link>
          {can("projects.write") && <select className="input w-40" aria-label="Project status" value={p.status} onChange={(e) => status(e.target.value)}>{["planning", "active", "at_risk", "delayed", "completed", "archived"].map((s) => <option key={s} value={s}>{title(s)}</option>)}</select>}</>} />
        <div className="card mb-4 grid gap-4 p-4 md:grid-cols-4">
          <div><p className="text-small text-ink-2">Status</p><Badge value={p.status} /></div>
          <div><p className="text-small text-ink-2">Progress</p><div className="mt-1.5 flex items-center gap-2"><Progress value={Number(p.progress)} /><span>{Math.round(Number(p.progress))}%</span></div></div>
          <div><p className="text-small text-ink-2">Deadline</p><p>{date(p.due_date)}</p></div>
          {internal ? <div><p className="text-small text-ink-2">Budget</p><p>{money(p.budget)}</p></div> : <div />}
        </div>
        <Tabs tabs={tabs} value={tab} onChange={setTab} />
        {tab === "overview" && <section className="card p-4"><p>{p.description || "No description."}</p>{internal && <p className="mt-3 text-small text-ink-2">Tasks: {Object.entries(p.task_counts).map(([k, v]) => `${title(k)} ${v}`).join(" · ") || "none"}</p>}</section>}
        {tab === "tasks" && <ProjectTasks projectId={id} />}
        {tab === "milestones" && <div className="card">{p.milestones.length === 0 ? <p className="p-6 text-center text-ink-2">No milestones.</p> : <ul>{p.milestones.map((m: any) => <li key={m.id} className="flex items-center justify-between gap-4 border-b border-line px-4 py-3 last:border-0"><div><p className="font-medium">{m.name}</p><p className="text-small text-ink-2">Due {date(m.due_date)}</p></div><div className="flex w-48 items-center gap-3"><Badge value={m.status} /><Progress value={Number(m.progress || 0)} /></div></li>)}</ul>}</div>}
        {tab === "team" && <div className="card"><ul>{p.members.map((m: any) => <li key={m.user_id} className="flex justify-between border-b border-line px-4 py-3 last:border-0"><span className="font-medium">{m.name}</span><Badge value={m.role || "member"} /></li>)}</ul></div>}
        {tab === "files" && <FilesTab id={id} />}
        {tab === "risk" && <section className="card p-4"><div className="mb-3 flex items-center justify-between"><h2>Delay risk</h2>{can("ai.read") && <button className="btn btn-sm" onClick={async () => { try { await api(`/projects/${id}/risk`, { method: "POST" }); toast("Risk recalculated"); reload(); } catch (e) { toast(errMsg(e), "err"); } }}>Recalculate</button>}</div><Explanation p={p.ai_risk} label="Delay probability" /></section>}
      </div>)}
    </DataState>
  );
}

function FilesTab({ id }: { id: string }) {
  const { data, loading, error, reload } = useApi<any>("/documents", { project_id: id });
  return <div className="card"><DataState loading={loading && !data} error={error} onRetry={reload} empty={!!data && data.items.length === 0 && { title: "No files", hint: "Upload files from the Documents page." }}><ul>{data?.items.map((d: any) => <li key={d.id} className="border-b border-line px-4 py-3 last:border-0">{d.file_name}</li>)}</ul></DataState></div>;
}
