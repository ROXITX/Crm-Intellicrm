"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { api, download } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useApi } from "@/hooks/useApi";
import { Badge, Confirm, DataState, Field, Modal, PageHeader, errMsg } from "@/components/common/ui";
import { useToast } from "@/components/common/toast";
import { date, money, title } from "@/lib/format";

export default function InvoiceDetail() {
  const { id } = useParams<{ id: string }>();
  const { can } = useAuth();
  const toast = useToast();
  const { data: i, loading, error, reload } = useApi<any>(`/invoices/${id}`);
  const [pay, setPay] = useState(false);
  const [cancel, setCancel] = useState(false);
  const [amount, setAmount] = useState("");
  const [method, setMethod] = useState("bank_transfer");
  const [ref, setRef] = useState("");
  const act = async (path: string, ok: string) => { try { await api(path, { method: "POST" }); toast(ok); reload(); } catch (e) { toast(errMsg(e), "err"); } };
  return (
    <DataState loading={loading && !i} error={error} onRetry={reload}>
      {i && (<div>
        <PageHeader title={i.invoice_number} subtitle={`${i.customer_name} · issued ${date(i.issue_date)} · due ${date(i.due_date)}`} actions={<>
          <Link href="/invoices" className="btn">Back</Link><button className="btn" onClick={() => download(`/invoices/${id}/pdf`, `${i.invoice_number}.pdf`).catch((e) => toast(errMsg(e), "err"))}>Download PDF</button>
          {can("invoices.write") && i.status === "draft" && <button className="btn btn-primary" onClick={() => act(`/invoices/${id}/issue`, "Invoice issued")}>Issue invoice</button>}
          {can("payments.write") && ["sent", "partially_paid", "overdue"].includes(i.status) && <button className="btn btn-primary" onClick={() => { setAmount(i.balance); setPay(true); }}>Record payment</button>}
          {can("invoices.write") && !["paid", "cancelled"].includes(i.status) && Number(i.amount_paid) === 0 && <button className="btn btn-danger" onClick={() => setCancel(true)}>Cancel</button>}</>} />
        <div className="grid gap-4 lg:grid-cols-3">
          <section className="card overflow-hidden lg:col-span-2"><table><thead><tr><th>Description</th><th className="text-right">Qty</th><th className="text-right">Unit price</th><th className="text-right">Tax</th><th className="text-right">Total</th></tr></thead><tbody>
            {i.items.map((x: any) => <tr key={x.id}><td>{x.description}</td><td className="text-right">{x.quantity}</td><td className="text-right">{money(x.unit_price, i.currency)}</td><td className="text-right">{x.tax_rate}%</td><td className="text-right">{money(x.line_total, i.currency)}</td></tr>)}</tbody></table></section>
          <section className="card space-y-2 p-4"><div className="flex justify-between"><span className="text-ink-2">Status</span><Badge value={i.status} /></div>
            {[["Subtotal", i.subtotal], ["Tax", i.tax], ["Discount", `-${i.discount}`], ["Total", i.total], ["Paid", i.amount_paid]].map(([k, v]) => <div key={k} className="flex justify-between"><span className="text-ink-2">{k}</span><span>{money(v, i.currency)}</span></div>)}
            <div className="flex justify-between border-t border-line pt-2 text-[15px] font-semibold"><span>Balance due</span><span>{money(i.balance, i.currency)}</span></div></section>
          <section className="card lg:col-span-3"><div className="border-b border-line px-4 py-3"><h2>Payments</h2></div>{i.payments.length === 0 ? <p className="p-6 text-center text-ink-2">No payments recorded.</p> :
            <table><thead><tr><th>Date</th><th>Amount</th><th>Method</th><th>Reference</th><th>Status</th></tr></thead><tbody>{i.payments.map((p: any) => <tr key={p.id}><td>{date(p.paid_at)}</td><td>{money(p.amount, i.currency)}</td><td>{title(p.method)}</td><td>{p.transaction_reference || "-"}</td><td><Badge value={p.status} /></td></tr>)}</tbody></table>}</section>
        </div>
        <Modal open={pay} onClose={() => setPay(false)} title="Record payment" width="max-w-md">
          <form className="space-y-3" onSubmit={async (e) => { e.preventDefault(); try { await api(`/invoices/${id}/payments`, { body: { amount, method, transaction_reference: ref || null } }); toast("Payment recorded"); setPay(false); reload(); } catch (er) { toast(errMsg(er), "err"); } }}>
            <Field label="Amount" required hint={`Outstanding balance: ${money(i.balance, i.currency)}`}><input className="input" inputMode="decimal" required pattern="\d+(\.\d{1,2})?" value={amount} onChange={(e) => setAmount(e.target.value)} /></Field>
            <Field label="Method"><select className="input" value={method} onChange={(e) => setMethod(e.target.value)}>{["bank_transfer", "upi", "card", "cash", "cheque", "other"].map((m) => <option key={m} value={m}>{title(m)}</option>)}</select></Field>
            <Field label="Transaction reference" hint="Processor reference only - never enter card numbers or CVV"><input className="input" value={ref} maxLength={200} onChange={(e) => setRef(e.target.value)} /></Field>
            <div className="flex justify-end gap-2"><button type="button" className="btn" onClick={() => setPay(false)}>Cancel</button><button className="btn btn-primary">Record payment</button></div></form>
        </Modal>
        <Confirm open={cancel} onClose={() => setCancel(false)} danger title="Cancel invoice" message="This invoice will be marked as cancelled and can no longer be paid." confirmLabel="Cancel invoice" onConfirm={() => act(`/invoices/${id}/cancel`, "Invoice cancelled")} />
      </div>)}
    </DataState>
  );
}
