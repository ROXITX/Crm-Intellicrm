"use client";
import { useList } from "@/hooks/useList";
import { DataTable } from "@/components/common/DataTable";
import { Badge, PageHeader } from "@/components/common/ui";
import { date, money, title } from "@/lib/format";

type P = { id: string; invoice_number: string; customer_name: string; amount: string; method: string; status: string; transaction_reference: string | null; paid_at: string | null };

export default function PaymentsPage() {
  const L = useList<P>("/payments");
  return (
    <div>
      <PageHeader title="Payments" subtitle="Recorded payments across invoices" />
      <DataTable<P> rows={L.rows} loading={L.loading} error={L.error} onRetry={L.reload} page={L.page} pageSize={L.pageSize} total={L.total} onPage={L.setPage} empty={{ title: "No payments recorded yet", hint: "Payments appear here when recorded against an invoice." }}
        columns={[{ key: "d", header: "Date", render: (p) => date(p.paid_at) }, { key: "i", header: "Invoice", render: (p) => <span className="font-medium">{p.invoice_number}</span> }, { key: "c", header: "Customer", render: (p) => p.customer_name },
          { key: "a", header: "Amount", render: (p) => money(p.amount) }, { key: "m", header: "Method", render: (p) => title(p.method) }, { key: "r", header: "Reference", render: (p) => p.transaction_reference || "-" }, { key: "s", header: "Status", render: (p) => <Badge value={p.status} /> }]} />
    </div>
  );
}
