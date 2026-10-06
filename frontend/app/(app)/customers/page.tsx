"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { api, download } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useList } from "@/hooks/useList";
import { DataTable } from "@/components/common/DataTable";
import { Badge, Field, Modal, PageHeader, errMsg } from "@/components/common/ui";
import { useToast } from "@/components/common/toast";
import { ago, money } from "@/lib/format";
import { ImportModal } from "@/components/crm/shared";
import type { Customer } from "@/types/api";

const schema = z.object({ name: z.string().min(1, "Name is required"), company_name: z.string().optional(), email: z.string().email("Invalid email").or(z.literal("")).optional(), phone: z.string().optional(), industry: z.string().optional() });

function AddCustomer({ open, onClose, onDone }: { open: boolean; onClose: () => void; onDone: () => void }) {
  const { register, handleSubmit, reset, formState: { errors, isSubmitting } } = useForm<z.infer<typeof schema>>({ resolver: zodResolver(schema) });
  const toast = useToast();
  return (
    <Modal open={open} onClose={onClose} title="Add customer">
      <form className="space-y-3" noValidate onSubmit={handleSubmit(async (v) => {
        try { await api("/customers", { body: Object.fromEntries(Object.entries(v).map(([k, x]) => [k, x || null])) }); toast("Customer created"); reset(); onDone(); onClose(); } catch (e) { toast(errMsg(e), "err"); }
      })}>
        <Field label="Name" required error={errors.name?.message}><input className="input" {...register("name")} /></Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Company"><input className="input" {...register("company_name")} /></Field>
          <Field label="Industry"><input className="input" {...register("industry")} /></Field>
          <Field label="Email" error={errors.email?.message}><input className="input" type="email" {...register("email")} /></Field>
          <Field label="Phone"><input className="input" {...register("phone")} /></Field>
        </div>
        <div className="flex justify-end gap-2 pt-2"><button type="button" className="btn" onClick={onClose}>Cancel</button><button className="btn btn-primary" disabled={isSubmitting}>Create customer</button></div>
      </form>
    </Modal>
  );
}

export default function CustomersPage() {
  const router = useRouter();
  const { can, me } = useAuth();
  const toast = useToast();
  const L = useList<Customer>("/customers");
  const [add, setAdd] = useState(false);
  const [imp, setImp] = useState(false);
  const client = me?.role === "client";
  const f = L.filters;
  return (
    <div>
      <PageHeader title="Customers" subtitle="Accounts, health and relationship history" actions={!client && <>
        <button className="btn" onClick={() => download("/customers/export", "customers.csv").catch((e) => toast(errMsg(e), "err"))}>Export</button>
        {can("customers.write") && <><button className="btn" onClick={() => setImp(true)}>Import</button><button className="btn btn-primary" onClick={() => setAdd(true)}>Add Customer</button></>}</>} />
      <div className="card mb-4 grid grid-cols-2 gap-3 p-3 md:grid-cols-4">
        <input className="input col-span-2" placeholder="Search customers" aria-label="Search customers" value={f.q || ""} onChange={(e) => L.setFilter("q", e.target.value)} />
        <select className="input" aria-label="Health" value={f.health || ""} onChange={(e) => L.setFilter("health", e.target.value)}><option value="">All health states</option>{["healthy", "watch", "at_risk", "critical"].map((h) => <option key={h} value={h}>{h.replace("_", " ")}</option>)}</select>
        <input className="input" aria-label="Industry" placeholder="Industry" value={f.industry || ""} onChange={(e) => L.setFilter("industry", e.target.value)} />
      </div>
      <DataTable<Customer> rows={L.rows} loading={L.loading} error={L.error} onRetry={L.reload} page={L.page} pageSize={L.pageSize} total={L.total} onPage={L.setPage} sort={L.sort} onSort={L.toggleSort}
        onRowClick={(r) => router.push(`/customers/${r.id}`)}
        empty={{ title: "No customers found", hint: "Try changing your filters or add your first customer.", action: can("customers.write") ? <button className="btn btn-primary" onClick={() => setAdd(true)}>Add Customer</button> : undefined }}
        columns={[
          { key: "name", header: "Customer", sortKey: "name", render: (r) => <div><p className="font-medium">{r.name}</p><p className="text-small text-ink-2">{r.industry || ""}</p></div> },
          { key: "company", header: "Company", render: (r) => r.company_name || "-" },
          ...(client ? [] : [{ key: "health", header: "Health", sortKey: "health_score", render: (r: Customer) => <span className="flex items-center gap-2"><Badge value={r.health_status} />{r.health_score && <span className="text-small text-ink-2">{Math.round(Number(r.health_score))}</span>}</span> }]),
          { key: "projects", header: "Projects", render: (r) => r.project_count ?? 0 },
          { key: "tickets", header: "Open tickets", render: (r) => r.open_tickets ?? 0 },
          { key: "last", header: "Last interaction", sortKey: "last_interaction_at", render: (r) => ago(r.last_interaction_at) },
          { key: "revenue", header: "Revenue", sortKey: "revenue", render: (r) => money(r.revenue) },
          ...(client ? [] : [{ key: "owner", header: "Owner", render: (r: Customer) => r.owner_name || "-" }]),
        ]} />
      <AddCustomer open={add} onClose={() => setAdd(false)} onDone={L.reload} />
      <ImportModal open={imp} onClose={() => setImp(false)} onDone={L.reload} path="/customers/import" noun="customers" />
    </div>
  );
}
