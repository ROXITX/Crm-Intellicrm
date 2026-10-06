"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import { Badge, Modal, errMsg } from "@/components/common/ui";
import { useToast } from "@/components/common/toast";

export const LEAD_STATUSES = ["new", "contacted", "qualified", "proposal", "negotiation", "won", "lost"];
export const TASK_STATUSES = ["todo", "in_progress", "blocked", "review", "done", "cancelled"];
export const ScoreBadge = ({ s }: { s: string | null }) => s == null ? <span className="text-ink-2">-</span> : <Badge value={Number(s) >= 80 ? "high" : Number(s) >= 50 ? "medium" : "low"} tone={Number(s) >= 80 ? "success" : Number(s) >= 50 ? "warning" : "neutral"} label={`${Math.round(Number(s))}`} />;

export function ImportModal({ open, onClose, onDone, path, noun }: { open: boolean; onClose: () => void; onDone: () => void; path: string; noun: string }) {
  const [file, setFile] = useState<File | null>(null);
  const [prev, setPrev] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const toast = useToast();
  const send = async (confirm: boolean) => {
    if (!file) return; setBusy(true);
    try {
      const f = new FormData(); f.append("file", file);
      const r = await api<any>(`${path}?confirm=${confirm}`, { form: f });
      if (confirm) { toast(`Imported ${r.imported} ${noun}`); setPrev(null); setFile(null); onDone(); onClose(); } else setPrev(r);
    } catch (e) { toast(errMsg(e), "err"); } finally { setBusy(false); }
  };
  return (
    <Modal open={open} onClose={onClose} title={`Import ${noun} from CSV`} width="max-w-xl">
      <p className="mb-3 text-ink-2">Upload a UTF-8 CSV with a header row. Rows are validated first; nothing is saved until you confirm.</p>
      <input type="file" accept=".csv,text/csv" onChange={(e) => { setFile(e.target.files?.[0] || null); setPrev(null); }} aria-label="CSV file" />
      {prev && (
        <div className="mt-4 space-y-2">
          <p><b>{prev.valid_rows}</b> valid row(s), <b className={prev.errors.length ? "text-danger" : ""}>{prev.errors.length}</b> error(s).</p>
          {prev.errors.length > 0 && <ul className="max-h-32 overflow-auto rounded-ctl border border-line p-2 text-small text-danger">{prev.errors.map((e: any) => <li key={e.row}>Row {e.row}: {e.message}</li>)}</ul>}
          {prev.preview.length > 0 && <p className="text-small text-ink-2">Preview: {prev.preview.slice(0, 3).map((p: any) => p.name).join(", ")}{prev.valid_rows > 3 ? "…" : ""}</p>}
        </div>
      )}
      <div className="mt-5 flex justify-end gap-2">
        <button className="btn" onClick={onClose}>Cancel</button>
        <button className="btn" disabled={!file || busy} onClick={() => send(false)}>Validate</button>
        <button className="btn btn-primary" disabled={!prev || prev.errors.length > 0 || prev.valid_rows === 0 || busy} onClick={() => send(true)}>Confirm import</button>
      </div>
    </Modal>
  );
}

