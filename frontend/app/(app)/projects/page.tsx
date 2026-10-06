"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useList } from "@/hooks/useList";
import { useApi } from "@/hooks/useApi";
import { DataTable } from "@/components/common/DataTable";
import { Badge, Field, Modal, PageHeader, Progress, errMsg } from "@/components/common/ui";
import { useToast } from "@/components/common/toast";
import { date, money, title } from "@/lib/format";
import type { Customer, Paged, Project } from "@/types/api";

const schema = z.object({ customer_id: z.string().min(1, "Choose a customer"), name: z.string().min(1, "Name is required"), budget: z.string().regex(/^\d*(\.\d{0,2})?$/, "Invalid amount").optional(), start_date: z.string().optional(), due_date: z.string().optional() })
  .refine((v) => !v.start_date || !v.due_date || v.due_date >= v.start_date, { path: ["due_date"], message: "Due date must be after start date" });

function AddProject({ open, onClose, onDone }: { open: boolean; onClose: () => void; onDone: () => void }) {
  const { register, handleSubmit, reset, formState: { errors, isSubmitting } } = useForm<z.infer<typeof schema>>({ resolver: zodResolver(schema) });
  const { data: custs } = useApi<Paged<Customer>>(open ? "/customers" : null, { page_size: 100 });
  const toast = useToast();
  return (
    <Modal open={open} onClose={onClose} title="New project">
      <form className="space-y-3" noValidate onSubmit={handleSubmit(async (v) => {
        try { await api("/projects", { body: { ...v, budget: v.budget || null, start_date: v.start_date || null, due_date: v.due_date || null } }); toast("Project created"); reset(); onDone(); onClose(); } catch (e) { toast(errMsg(e), "err"); }
      })}>
        <Field label="Customer" required error={errors.customer_id?.message}><select className="input" {...register("customer_id")}><option value="">Select...</option>{custs?.items.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></Field>
        <Field label="Project name" required error={errors.name?.message}><input className="input" {...register("name")} /></Field>
        <div className="grid grid-cols-3 gap-3">
          <Field label="Budget (INR)" error={errors.budget?.message}><input className="input" inputMode="decimal" {...register("budget")} /></Field>
          <Field label="Start"><input className="input" type="date" {...register("start_date")} /></Field>
          <Field label="Due" error={errors.due_date?.message}><input className="input" type="date" {...register("due_date")} /></Field>
        </div>
        <div className="flex justify-end gap-2 pt-2"><button type="button" className="btn" onClick={onClose}>Cancel</button><button className="btn btn-primary" disabled={isSubmitting}>Create project</button></div>
      </form>
    </Modal>
  );
}

export default function ProjectsPage() {
  const router = useRouter();
  const { can, me } = useAuth();
  const L = useList<Project>("/projects");
  const [add, setAdd] = useState(false);
  const client = me?.role === "client";
  return (
    <div>
      <PageHeader title={client ? "My Projects" : "Projects"} subtitle="Delivery status, deadlines and risk" actions={can("projects.write") && <button className="btn btn-primary" onClick={() => setAdd(true)}>New Project</button>} />
      <div className="card mb-4 grid grid-cols-2 gap-3 p-3 md:grid-cols-4">
        <input className="input col-span-2" placeholder="Search projects" aria-label="Search projects" value={L.filters.q || ""} onChange={(e) => L.setFilter("q", e.target.value)} />
        <select className="input" aria-label="Status" value={L.filters.status || ""} onChange={(e) => L.setFilter("status", e.target.value)}><option value="">All statuses</option>{["planning", "active", "at_risk", "delayed", "completed", "archived"].map((s) => <option key={s} value={s}>{title(s)}</option>)}</select>
        {!client && <select className="input" aria-label="Risk" value={L.filters.risk || ""} onChange={(e) => L.setFilter("risk", e.target.value)}><option value="">Any risk</option>{["low", "medium", "high"].map((s) => <option key={s} value={s}>{title(s)}</option>)}</select>}
      </div>
      <DataTable<Project> rows={L.rows} loading={L.loading} error={L.error} onRetry={L.reload} page={L.page} pageSize={L.pageSize} total={L.total} onPage={L.setPage} onRowClick={(r) => router.push(`/projects/${r.id}`)}
        empty={{ title: "No projects found", hint: "Try changing your filters or create a project.", action: can("projects.write") ? <button className="btn btn-primary" onClick={() => setAdd(true)}>New Project</button> : undefined }}
        columns={[
          { key: "name", header: "Project", render: (r) => <span className="font-medium">{r.name}</span> },
          ...(client ? [] : [{ key: "cust", header: "Customer", render: (r: Project) => r.customer_name }, { key: "mgr", header: "Manager", render: (r: Project) => r.owner_name || "-" }]),
          { key: "progress", header: "Progress", render: (r) => <div className="flex w-32 items-center gap-2"><Progress value={Number(r.progress)} /><span className="text-small">{Math.round(Number(r.progress))}%</span></div> },
          { key: "status", header: "Status", render: (r) => <Badge value={r.status} /> },
          { key: "due", header: "Due", render: (r) => date(r.due_date) },
          ...(client ? [] : [{ key: "risk", header: "Risk", render: (r: Project) => <Badge value={r.risk_level} /> }, { key: "budget", header: "Budget", render: (r: Project) => money(r.budget) }]),
        ]} />
      <AddProject open={add} onClose={() => setAdd(false)} onDone={L.reload} />
    </div>
  );
}
