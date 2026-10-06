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
import { Badge, Field, Modal, PageHeader, errMsg } from "@/components/common/ui";
import { useToast } from "@/components/common/toast";
import { ago, title } from "@/lib/format";
import type { Customer, Paged, Ticket } from "@/types/api";

const schema = z.object({ customer_id: z.string().optional(), subject: z.string().min(3, "At least 3 characters").max(300), description: z.string().min(3, "Please describe the issue"), priority: z.string().optional() });

function AddTicket({ open, onClose, onDone, client }: { open: boolean; onClose: () => void; onDone: () => void; client: boolean }) {
  const { register, handleSubmit, reset, formState: { errors, isSubmitting } } = useForm<z.infer<typeof schema>>({ resolver: zodResolver(schema) });
  const { data: custs } = useApi<Paged<Customer>>(open && !client ? "/customers" : null, { page_size: 100 });
  const toast = useToast();
  return (
    <Modal open={open} onClose={onClose} title={client ? "New request" : "New ticket"}>
      <form className="space-y-3" noValidate onSubmit={handleSubmit(async (v) => {
        if (!client && !v.customer_id) return toast("Choose a customer", "err");
        try { await api("/tickets", { body: { subject: v.subject, description: v.description, customer_id: client ? null : v.customer_id, priority: client || !v.priority ? null : v.priority } }); toast("Submitted"); reset(); onDone(); onClose(); } catch (e) { toast(errMsg(e), "err"); }
      })}>
        {!client && <Field label="Customer" required><select className="input" {...register("customer_id")}><option value="">Select...</option>{custs?.items.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></Field>}
        <Field label="Subject" required error={errors.subject?.message}><input className="input" {...register("subject")} /></Field>
        <Field label="Description" required error={errors.description?.message}><textarea className="input min-h-28" {...register("description")} /></Field>
        {!client && <Field label="Priority" hint="Leave blank to use the AI-suggested priority"><select className="input" {...register("priority")}><option value="">AI suggested</option>{["low", "medium", "high", "critical"].map((p) => <option key={p} value={p}>{title(p)}</option>)}</select></Field>}
        <div className="flex justify-end gap-2 pt-2"><button type="button" className="btn" onClick={onClose}>Cancel</button><button className="btn btn-primary" disabled={isSubmitting}>Submit</button></div>
      </form>
    </Modal>
  );
}

export default function TicketsPage() {
  const router = useRouter();
  const { can, me } = useAuth();
  const client = me?.role === "client";
  const L = useList<Ticket>("/tickets");
  const [add, setAdd] = useState(false);
  const f = L.filters;
  return (
    <div>
      <PageHeader title={client ? "Requests" : "Tickets"} subtitle={client ? "Your support requests" : "Support queue, sorted by urgency"} actions={can("tickets.write") && <button className="btn btn-primary" onClick={() => setAdd(true)}>{client ? "New Request" : "New Ticket"}</button>} />
      <div className="card mb-4 grid grid-cols-2 gap-3 p-3 md:grid-cols-4">
        <input className="input col-span-2" placeholder="Search" aria-label="Search tickets" value={f.q || ""} onChange={(e) => L.setFilter("q", e.target.value)} />
        <select className="input" aria-label="Status" value={f.status || ""} onChange={(e) => L.setFilter("status", e.target.value)}><option value="">All statuses</option>{["open", "in_progress", "waiting_customer", "waiting_internal", "resolved", "closed"].map((s) => <option key={s} value={s}>{title(s)}</option>)}</select>
        <select className="input" aria-label="Priority" value={f.priority || ""} onChange={(e) => L.setFilter("priority", e.target.value)}><option value="">All priorities</option>{["critical", "high", "medium", "low"].map((s) => <option key={s} value={s}>{title(s)}</option>)}</select>
      </div>
      <DataTable<Ticket> rows={L.rows} loading={L.loading} error={L.error} onRetry={L.reload} page={L.page} pageSize={L.pageSize} total={L.total} onPage={L.setPage} onRowClick={(r) => router.push(`/tickets/${r.id}`)}
        empty={{ title: "No tickets found", hint: "Try changing your filters.", action: can("tickets.write") ? <button className="btn btn-primary" onClick={() => setAdd(true)}>{client ? "New Request" : "New Ticket"}</button> : undefined }}
        columns={[
          { key: "s", header: "Subject", render: (t) => <div><p className="font-medium">{t.subject}</p>{!client && <p className="text-small text-ink-2">{t.customer_name}</p>}</div> },
          { key: "p", header: "Priority", render: (t) => <Badge value={t.priority} tone={t.priority === "critical" ? "danger" : t.priority === "high" ? "warning" : "neutral"} /> },
          { key: "st", header: "Status", render: (t) => <Badge value={t.status} /> },
          ...(client ? [] : [{ key: "se", header: "Sentiment", render: (t: Ticket) => <Badge value={t.sentiment} /> }, { key: "a", header: "Assignee", render: (t: Ticket) => t.assignee_name || "-" }]),
          { key: "sla", header: "SLA due", render: (t) => <span className={t.sla_due_at && new Date(t.sla_due_at) < new Date() && !["resolved", "closed"].includes(t.status) ? "font-medium text-danger" : ""}>{ago(t.sla_due_at)}</span> },
          { key: "c", header: "Created", render: (t) => ago(t.created_at) },
        ]} />
      <AddTicket open={add} onClose={() => setAdd(false)} onDone={L.reload} client={!!client} />
    </div>
  );
}
