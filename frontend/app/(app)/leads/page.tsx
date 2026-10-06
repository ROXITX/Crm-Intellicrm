"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { api, download } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useList } from "@/hooks/useList";
import { useApi } from "@/hooks/useApi";
import { DataTable } from "@/components/common/DataTable";
import { Badge, Field, Modal, PageHeader, errMsg } from "@/components/common/ui";
import { useToast } from "@/components/common/toast";
import { ago, money, title } from "@/lib/format";
import { ImportModal, LEAD_STATUSES as STATUSES, ScoreBadge } from "@/components/crm/shared";
import type { Directory, Lead } from "@/types/api";


const schema = z.object({
  name: z.string().min(1, "Name is required").max(200), company_name: z.string().max(200).optional(), email: z.string().email("Invalid email").or(z.literal("")).optional(),
  phone: z.string().max(50).optional(), source: z.string().optional(), estimated_value: z.string().regex(/^\d*(\.\d{0,2})?$/, "Enter a valid amount").optional(), owner_id: z.string().optional(),
});

function AddLead({ open, onClose, onDone }: { open: boolean; onClose: () => void; onDone: () => void }) {
  const { register, handleSubmit, reset, formState: { errors, isSubmitting } } = useForm<z.infer<typeof schema>>({ resolver: zodResolver(schema) });
  const { data: team } = useApi<Directory>("/team/directory");
  const toast = useToast();
  const submit = handleSubmit(async (v) => {
    try {
      await api("/leads", { body: { ...v, email: v.email || null, company_name: v.company_name || null, phone: v.phone || null, source: v.source || null, estimated_value: v.estimated_value || null, owner_id: v.owner_id || null } });
      toast("Lead created"); reset(); onDone(); onClose();
    } catch (e) { toast(errMsg(e), "err"); }
  });
  return (
    <Modal open={open} onClose={onClose} title="Add lead">
      <form onSubmit={submit} className="space-y-3" noValidate>
        <Field label="Name" required error={errors.name?.message}><input className="input" {...register("name")} /></Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Company"><input className="input" {...register("company_name")} /></Field>
          <Field label="Source"><select className="input" {...register("source")}><option value="">-</option>{["referral", "website", "linkedin", "cold_outreach", "event", "other"].map((s) => <option key={s} value={s}>{title(s)}</option>)}</select></Field>
          <Field label="Email" error={errors.email?.message}><input className="input" type="email" {...register("email")} /></Field>
          <Field label="Phone"><input className="input" {...register("phone")} /></Field>
          <Field label="Estimated value (INR)" error={errors.estimated_value?.message}><input className="input" inputMode="decimal" {...register("estimated_value")} /></Field>
          <Field label="Owner"><select className="input" {...register("owner_id")}><option value="">Me</option>{team?.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}</select></Field>
        </div>
        <div className="flex justify-end gap-2 pt-2"><button type="button" className="btn" onClick={onClose}>Cancel</button><button className="btn btn-primary" disabled={isSubmitting}>Create lead</button></div>
      </form>
    </Modal>
  );
}

export default function LeadsPage() {
  const router = useRouter();
  const { can } = useAuth();
  const toast = useToast();
  const L = useList<Lead>("/leads");
  const [add, setAdd] = useState(false);
  const [imp, setImp] = useState(false);
  const { data: team } = useApi<Directory>("/team/directory");
  const f = L.filters;
  return (
    <div>
      <PageHeader title="Leads" subtitle="Track prospects and see AI-scored conversion likelihood" actions={<>
        <button className="btn" onClick={() => download("/leads/export", "leads.csv").catch((e) => toast(errMsg(e), "err"))}>Export</button>
        {can("leads.write") && <><button className="btn" onClick={() => setImp(true)}>Import</button><button className="btn btn-primary" onClick={() => setAdd(true)}>Add Lead</button></>}</>} />
      <div className="card mb-4 grid grid-cols-2 gap-3 p-3 md:grid-cols-4 xl:grid-cols-6">
        <input className="input col-span-2" placeholder="Search name, company, email" aria-label="Search leads" value={f.q || ""} onChange={(e) => L.setFilter("q", e.target.value)} />
        <select className="input" aria-label="Status" value={f.status || ""} onChange={(e) => L.setFilter("status", e.target.value)}><option value="">All statuses</option>{STATUSES.map((s) => <option key={s} value={s}>{title(s)}</option>)}</select>
        <select className="input" aria-label="Source" value={f.source || ""} onChange={(e) => L.setFilter("source", e.target.value)}><option value="">All sources</option>{["referral", "website", "linkedin", "cold_outreach", "event", "other"].map((s) => <option key={s} value={s}>{title(s)}</option>)}</select>
        <select className="input" aria-label="Owner" value={f.owner_id || ""} onChange={(e) => L.setFilter("owner_id", e.target.value)}><option value="">All owners</option>{team?.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}</select>
        <select className="input" aria-label="Score" value={f.min_score || ""} onChange={(e) => L.setFilter("min_score", e.target.value)}><option value="">Any score</option><option value="80">High (80+)</option><option value="50">Medium (50+)</option></select>
        <input className="input" type="date" aria-label="Created from" value={f.date_from || ""} onChange={(e) => L.setFilter("date_from", e.target.value)} />
        <input className="input" type="date" aria-label="Created to" value={f.date_to || ""} onChange={(e) => L.setFilter("date_to", e.target.value)} />
      </div>
      <DataTable<Lead> rows={L.rows} loading={L.loading} error={L.error} onRetry={L.reload} page={L.page} pageSize={L.pageSize} total={L.total} onPage={L.setPage}
        sort={L.sort} onSort={L.toggleSort} onRowClick={(r) => router.push(`/leads/${r.id}`)}
        empty={{ title: "No leads found", hint: "Try changing your filters or add your first lead.", action: can("leads.write") ? <button className="btn btn-primary" onClick={() => setAdd(true)}>Add Lead</button> : undefined }}
        columns={[
          { key: "name", header: "Lead", sortKey: "name", render: (r) => <span className="font-medium">{r.name}</span> },
          { key: "company", header: "Company", render: (r) => r.company_name || "-" },
          { key: "source", header: "Source", render: (r) => title(r.source) },
          { key: "owner", header: "Owner", render: (r) => r.owner_name || "-" },
          { key: "score", header: "Score", sortKey: "score", render: (r) => <ScoreBadge s={r.score} /> },
          { key: "status", header: "Status", render: (r) => <Badge value={r.status} /> },
          { key: "value", header: "Est. value", sortKey: "estimated_value", render: (r) => money(r.estimated_value) },
          { key: "last", header: "Last contact", render: (r) => ago(r.last_contact_at) },
        ]} />
      <AddLead open={add} onClose={() => setAdd(false)} onDone={L.reload} />
      <ImportModal open={imp} onClose={() => setImp(false)} onDone={L.reload} path="/leads/import" noun="leads" />
    </div>
  );
}
