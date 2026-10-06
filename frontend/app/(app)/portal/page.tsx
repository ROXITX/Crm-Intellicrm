"use client";
import Link from "next/link";
import { useApi } from "@/hooks/useApi";
import { useAuth } from "@/lib/auth";
import { Badge, DataState, Kpi, PageHeader, Progress } from "@/components/common/ui";
import { date, money } from "@/lib/format";

export default function Portal() {
  const { me } = useAuth();
  const { data, loading, error, reload } = useApi<any>("/portal/home");
  return (
    <div>
      <PageHeader title={`Welcome, ${me?.first_name}`} subtitle={data ? `Your account with ${me?.organization.name}` : undefined} />
      <DataState loading={loading && !data} error={error} onRetry={reload}>
        {data && (<>
          <div className="mb-4 grid grid-cols-2 gap-4 lg:grid-cols-3"><Kpi label="Projects" value={data.projects.length} sub="in your account" /><Kpi label="Open requests" value={data.open_requests} sub="awaiting resolution" /><Kpi label="Outstanding" value={money(data.outstanding_amount)} sub="unpaid invoices" /></div>
          <div className="grid gap-4 lg:grid-cols-2">
            <section className="card"><div className="border-b border-line px-4 py-3"><h2>Project progress</h2></div><ul>{data.projects.map((p: any) => <li key={p.id} className="border-b border-line px-4 py-3 last:border-0"><div className="flex items-center justify-between"><Link href={`/projects/${p.id}`} className="font-medium hover:underline">{p.name}</Link><Badge value={p.status} /></div><div className="mt-2 flex items-center gap-3"><Progress value={Number(p.progress)} /><span className="text-small">{Math.round(Number(p.progress))}%</span></div><p className="mt-1 text-small text-ink-2">Due {date(p.due_date)}</p></li>)}</ul></section>
            <div className="space-y-4">
              <section className="card"><div className="border-b border-line px-4 py-3"><h2>Upcoming milestones</h2></div>{data.upcoming_milestones.length === 0 ? <p className="p-5 text-ink-2">No upcoming milestones.</p> : <ul>{data.upcoming_milestones.map((m: any, i: number) => <li key={i} className="flex justify-between border-b border-line px-4 py-2.5 last:border-0"><span>{m.name} <span className="text-ink-2">· {m.project}</span></span><span className="text-ink-2">{date(m.due_date)}</span></li>)}</ul>}</section>
              <section className="card"><div className="flex items-center justify-between border-b border-line px-4 py-3"><h2>Recent invoices</h2><Link href="/invoices" className="text-small text-primary">View all</Link></div>{data.recent_invoices.length === 0 ? <p className="p-5 text-ink-2">No invoices yet.</p> : <ul>{data.recent_invoices.map((i: any) => <li key={i.id} className="flex items-center justify-between border-b border-line px-4 py-2.5 last:border-0"><Link href={`/invoices/${i.id}`} className="hover:underline">{i.invoice_number}</Link><span className="flex items-center gap-3">{money(i.total, i.currency)}<Badge value={i.status} /></span></li>)}</ul>}</section>
              <div className="flex gap-2"><Link href="/tickets" className="btn btn-primary">Submit a request</Link><Link href="/messages" className="btn">Message your team</Link></div>
            </div>
          </div></>)}
      </DataState>
    </div>
  );
}
