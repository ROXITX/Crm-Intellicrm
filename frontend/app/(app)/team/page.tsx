"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useApi } from "@/hooks/useApi";
import { Badge, DataState, Field, Modal, PageHeader, Progress, errMsg } from "@/components/common/ui";
import { useToast } from "@/components/common/toast";

type M = { user_id: string; name: string; email: string; role: string; member_status: string; active_tasks: number; overdue_tasks: number; allocated_hours: string; available_hours: string; capacity_pct: number; status: string };

export default function TeamPage() {
  const { can } = useAuth();
  const toast = useToast();
  const { data, loading, error, reload } = useApi<M[]>("/team");
  const [open, setOpen] = useState(false);
  const [f, setF] = useState({ email: "", first_name: "", last_name: "", role: "staff", password: "", weekly_capacity_hours: "40" });
  const change = async (id: string, body: any) => { try { await api(`/team/members/${id}`, { method: "PATCH", body }); toast("Updated"); reload(); } catch (e) { toast(errMsg(e), "err"); } };
  return (
    <div>
      <PageHeader title="Team" subtitle="Workload and capacity across your people (task data only - no activity surveillance)" actions={can("team.manage") && <button className="btn btn-primary" onClick={() => setOpen(true)}>Add team member</button>} />
      <div className="card overflow-hidden"><DataState loading={loading && !data} error={error} onRetry={reload} empty={!!data && data.length === 0 && { title: "No team members" }}>
        <div className="overflow-x-auto"><table><thead><tr><th>Member</th><th>Role</th><th>Active tasks</th><th>Overdue</th><th className="w-56">Capacity (2 weeks)</th><th>Workload</th>{can("team.manage") && <th>Access</th>}</tr></thead><tbody>
          {data?.map((m) => <tr key={m.user_id}><td><p className="font-medium">{m.name}</p><p className="text-small text-ink-2">{m.email}</p></td><td><Badge value={m.role} /></td><td>{m.active_tasks}</td><td className={m.overdue_tasks ? "text-danger" : ""}>{m.overdue_tasks}</td>
            <td><div className="flex items-center gap-2"><Progress value={m.capacity_pct} /><span className="w-24 text-small text-ink-2">{m.allocated_hours}h / {m.available_hours}h</span></div></td><td><Badge value={m.status} label={`${Math.round(m.capacity_pct)}% · ${m.status}`} /></td>
            {can("team.manage") && <td><div className="flex gap-2"><select className="input w-28" aria-label={`Role of ${m.name}`} value={m.role} onChange={(e) => change(m.user_id, { role: e.target.value })}>{["owner", "manager", "staff"].map((r) => <option key={r} value={r}>{r}</option>)}</select>
              <button className="btn btn-sm" onClick={() => change(m.user_id, { status: m.member_status === "active" ? "suspended" : "active" })}>{m.member_status === "active" ? "Suspend" : "Activate"}</button></div></td>}</tr>)}</tbody></table></div></DataState></div>
      <Modal open={open} onClose={() => setOpen(false)} title="Add team member" width="max-w-md">
        <form className="space-y-3" onSubmit={async (e) => { e.preventDefault(); try { await api("/team/members", { body: { ...f, last_name: f.last_name || null } }); toast("Member added"); setOpen(false); reload(); } catch (er) { toast(errMsg(er), "err"); } }}>
          <div className="grid grid-cols-2 gap-3"><Field label="First name" required><input className="input" required value={f.first_name} onChange={(e) => setF({ ...f, first_name: e.target.value })} /></Field><Field label="Last name"><input className="input" value={f.last_name} onChange={(e) => setF({ ...f, last_name: e.target.value })} /></Field></div>
          <Field label="Email" required><input className="input" type="email" required value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} /></Field>
          <div className="grid grid-cols-2 gap-3"><Field label="Role"><select className="input" value={f.role} onChange={(e) => setF({ ...f, role: e.target.value })}>{["staff", "manager", "owner"].map((r) => <option key={r}>{r}</option>)}</select></Field><Field label="Weekly capacity (h)"><input className="input" inputMode="decimal" value={f.weekly_capacity_hours} onChange={(e) => setF({ ...f, weekly_capacity_hours: e.target.value })} /></Field></div>
          <Field label="Temporary password" required hint="At least 10 characters"><input className="input" type="password" minLength={10} required value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} /></Field>
          <div className="flex justify-end gap-2"><button type="button" className="btn" onClick={() => setOpen(false)}>Cancel</button><button className="btn btn-primary">Add member</button></div></form>
      </Modal>
    </div>
  );
}
