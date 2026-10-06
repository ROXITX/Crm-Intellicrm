"use client";
import { useState } from "react";
import { api, download } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useList } from "@/hooks/useList";
import { useApi } from "@/hooks/useApi";
import { DataTable } from "@/components/common/DataTable";
import { Confirm, Field, Modal, PageHeader, errMsg } from "@/components/common/ui";
import { useToast } from "@/components/common/toast";
import { date, num } from "@/lib/format";
import type { Customer, Paged } from "@/types/api";

type D = { id: string; file_name: string; mime_type: string | null; file_size: number | null; created_at: string; customer_id: string | null; uploaded_by: string | null };

export default function DocumentsPage() {
  const { can, me } = useAuth();
  const toast = useToast();
  const L = useList<D>("/documents");
  const [up, setUp] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [cust, setCust] = useState("");
  const [del, setDel] = useState<D | null>(null);
  const { data: custs } = useApi<Paged<Customer>>(up ? "/customers" : null, { page_size: 100 });
  const upload = async () => {
    if (!file || !cust) return toast("Choose a file and a customer", "err");
    const f = new FormData(); f.append("file", file); f.append("customer_id", cust);
    try { await api("/documents", { form: f }); toast("Uploaded"); setUp(false); setFile(null); L.reload(); } catch (e) { toast(errMsg(e), "err"); }
  };
  return (
    <div>
      <PageHeader title="Documents" subtitle="Files attached to customers, projects, tickets and invoices" actions={can("documents.write") && <button className="btn btn-primary" onClick={() => setUp(true)}>Upload</button>} />
      <div className="card mb-4 p-3"><input className="input max-w-sm" placeholder="Search file name" aria-label="Search documents" value={L.filters.q || ""} onChange={(e) => L.setFilter("q", e.target.value)} /></div>
      <DataTable<D> rows={L.rows} loading={L.loading} error={L.error} onRetry={L.reload} page={L.page} pageSize={L.pageSize} total={L.total} onPage={L.setPage} empty={{ title: "No documents", hint: "Upload a file to get started." }}
        columns={[{ key: "n", header: "File", render: (d) => <span className="font-medium">{d.file_name}</span> }, { key: "t", header: "Type", render: (d) => d.mime_type || "-" }, { key: "s", header: "Size", render: (d) => d.file_size ? `${num(Math.ceil(d.file_size / 1024))} KB` : "-" }, { key: "c", header: "Uploaded", render: (d) => date(d.created_at) },
          { key: "a", header: "", render: (d) => <div className="flex justify-end gap-2"><button className="btn btn-sm" onClick={() => download(`/documents/${d.id}/download`, d.file_name).catch((e) => toast(errMsg(e), "err"))}>Download</button>{can("documents.write") && (me?.role === "owner" || d.uploaded_by === me?.id) && <button className="btn btn-sm" onClick={() => setDel(d)}>Delete</button>}</div> }]} />
      <Modal open={up} onClose={() => setUp(false)} title="Upload document" width="max-w-md"><div className="space-y-3">
        <Field label="Customer" required><select className="input" value={cust} onChange={(e) => setCust(e.target.value)}><option value="">Select...</option>{custs?.items.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></Field>
        <Field label="File" required hint="PDF, images, Office documents, CSV, TXT, ZIP - up to 10 MB"><input type="file" onChange={(e) => setFile(e.target.files?.[0] || null)} /></Field>
        <div className="flex justify-end gap-2"><button className="btn" onClick={() => setUp(false)}>Cancel</button><button className="btn btn-primary" onClick={upload}>Upload</button></div></div></Modal>
      <Confirm open={!!del} onClose={() => setDel(null)} danger title="Delete document" message={`Delete ${del?.file_name}? It will no longer be accessible.`} confirmLabel="Delete" onConfirm={async () => { try { await api(`/documents/${del!.id}`, { method: "DELETE" }); toast("Deleted"); L.reload(); } catch (e) { toast(errMsg(e), "err"); } }} />
    </div>
  );
}
