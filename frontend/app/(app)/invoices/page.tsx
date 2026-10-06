"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useFieldArray, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useList } from "@/hooks/useList";
import { useApi } from "@/hooks/useApi";
import { DataTable } from "@/components/common/DataTable";
import { Badge, Field, Kpi, Modal, PageHeader, errMsg } from "@/components/common/ui";
import { useToast } from "@/components/common/toast";
import { date, money, title } from "@/lib/format";
import type { Customer, Invoice, Paged } from "@/types/api";

const num = z.string().regex(/^\d+(\.\d{1,2})?$/, "Enter a valid number");
const schema = z.object({ customer_id: z.string().min(1, "Choose a customer"), due_date: z.string().min(1, "Due date is required"), discount: z.string().regex(/^\d*(\.\d{1,2})?$/, "Invalid amount").optional(),
  items: z.array(z.object({ description: z.string().min(1, "Required"), quantity: num, unit_price: num, tax_rate: z.string().regex(/^\d*(\.\d{1,2})?$/, "Invalid") })).min(1) });
type F = z.infer<typeof schema>;

function NewInvoice({ open, onClose, onDone }: { open: boolean; onClose: () => void; onDone: () => void }) {
  const { register, control, handleSubmit, reset, watch, formState: { errors, isSubmitting } } = useForm<F>({ resolver: zodResolver(schema), defaultValues: { items: [{ description: "", quantity: "1", unit_price: "", tax_rate: "18" }] } });
  const { fields, append, remove } = useFieldArray({ control, name: "items" });
  const { data: custs } = useApi<Paged<Customer>>(open ? "/customers" : null, { page_size: 100 });
  const toast = useToast();
  const items = watch("items");
  // Preview only - the server recalculates every amount and is the source of truth.
  const preview = (items || []).reduce((s, i) => s + (Number(i.quantity) || 0) * (Number(i.unit_price) || 0) * (1 + (Number(i.tax_rate) || 0) / 100), 0) - (Number(watch("discount")) || 0);
  return (
    <Modal open={open} onClose={onClose} title="New invoice" width="max-w-3xl">
      <form className="space-y-3" noValidate onSubmit={handleSubmit(async (v) => {
        try { const inv = await api<any>("/invoices", { body: { ...v, discount: v.discount || "0" } }); toast(`Draft ${inv.invoice_number} created`); reset(); onDone(); onClose(); } catch (e) { toast(errMsg(e), "err"); }
      })}>
        <div className="grid grid-cols-3 gap-3">
          <Field label="Customer" required error={errors.customer_id?.message}><select className="input" {...register("customer_id")}><option value="">Select...</option>{custs?.items.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></Field>
          <Field label="Due date" required error={errors.due_date?.message}><input className="input" type="date" {...register("due_date")} /></Field>
          <Field label="Discount (INR)" error={errors.discount?.message}><input className="input" inputMode="decimal" {...register("discount")} /></Field>
        </div>
        <table><thead><tr><th>Description</th><th className="w-24">Qty</th><th className="w-32">Unit price</th><th className="w-20">Tax %</th><th className="w-8" /></tr></thead><tbody>
          {fields.map((f, i) => (<tr key={f.id}><td><input className="input" aria-label="Description" {...register(`items.${i}.description`)} />{errors.items?.[i]?.description && <p className="text-small text-danger">{errors.items[i]!.description!.message}</p>}</td>
            <td><input className="input" inputMode="decimal" aria-label="Quantity" {...register(`items.${i}.quantity`)} /></td><td><input className="input" inputMode="decimal" aria-label="Unit price" {...register(`items.${i}.unit_price`)} />{errors.items?.[i]?.unit_price && <p className="text-small text-danger">{errors.items[i]!.unit_price!.message}</p>}</td>
            <td><input className="input" inputMode="decimal" aria-label="Tax rate" {...register(`items.${i}.tax_rate`)} /></td><td>{fields.length > 1 && <button type="button" className="text-danger" onClick={() => remove(i)} aria-label="Remove line">×</button>}</td></tr>))}
        </tbody></table>
        <div className="flex items-center justify-between"><button type="button" className="btn btn-sm" onClick={() => append({ description: "", quantity: "1", unit_price: "", tax_rate: "18" })}>Add line</button><p className="text-small text-ink-2">Estimated total: <b className="text-ink">{money(Math.max(preview, 0))}</b> (final amount calculated by the server)</p></div>
        <div className="flex justify-end gap-2 pt-2"><button type="button" className="btn" onClick={onClose}>Cancel</button><button className="btn btn-primary" disabled={isSubmitting}>Save draft</button></div>
      </form>
    </Modal>
  );
}

export default function InvoicesPage() {
  const router = useRouter();
  const { can } = useAuth();
  const L = useList<Invoice>("/invoices");
  const { data: s } = useApi<any>("/invoices/summary");
  const [add, setAdd] = useState(false);
  return (
    <div>
      <PageHeader title="Invoices" subtitle="Billing, balances and payment status" actions={can("invoices.write") && <button className="btn btn-primary" onClick={() => setAdd(true)}>New Invoice</button>} />
      {s && <div className="mb-4 grid grid-cols-2 gap-4 lg:grid-cols-4"><Kpi label="Outstanding" value={money(s.outstanding)} /><Kpi label="Overdue" value={money(s.overdue)} /><Kpi label="Paid this month" value={money(s.paid_this_month)} /><Kpi label="Revenue" value={money(s.revenue)} /></div>}
      <div className="card mb-4 grid grid-cols-2 gap-3 p-3 md:grid-cols-4">
        <input className="input col-span-2" placeholder="Search invoice number" aria-label="Search invoices" value={L.filters.q || ""} onChange={(e) => L.setFilter("q", e.target.value)} />
        <select className="input" aria-label="Status" value={L.filters.status || ""} onChange={(e) => L.setFilter("status", e.target.value)}><option value="">All statuses</option>{["draft", "sent", "partially_paid", "paid", "overdue", "cancelled"].map((x) => <option key={x} value={x}>{title(x)}</option>)}</select>
      </div>
      <DataTable<Invoice> rows={L.rows} loading={L.loading} error={L.error} onRetry={L.reload} page={L.page} pageSize={L.pageSize} total={L.total} onPage={L.setPage} onRowClick={(r) => router.push(`/invoices/${r.id}`)}
        empty={{ title: "No invoices found", hint: "Try changing your filters.", action: can("invoices.write") ? <button className="btn btn-primary" onClick={() => setAdd(true)}>New Invoice</button> : undefined }}
        columns={[
          { key: "n", header: "Invoice", render: (i) => <span className="font-medium">{i.invoice_number}</span> }, { key: "c", header: "Customer", render: (i) => i.customer_name },
          { key: "a", header: "Amount", render: (i) => money(i.total, i.currency) }, { key: "b", header: "Balance", render: (i) => money(i.balance, i.currency) },
          { key: "i", header: "Issued", render: (i) => date(i.issue_date) }, { key: "d", header: "Due", render: (i) => date(i.due_date) }, { key: "s", header: "Status", render: (i) => <Badge value={i.status} /> },
        ]} />
      <NewInvoice open={add} onClose={() => setAdd(false)} onDone={L.reload} />
    </div>
  );
}
