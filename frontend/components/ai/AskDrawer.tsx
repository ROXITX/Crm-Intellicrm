"use client";
import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { Icon } from "@/components/common/Icon";

type Answer = { answer: string; items: { title: string; detail: string; entity_type: string | null; entity_id: string | null }[]; tools_used: string[]; suggestions: string[] };
const ROUTES: Record<string, string> = { customer: "/customers", project: "/projects", task: "/tasks", ticket: "/tickets", invoice: "/invoices", lead: "/leads" };

/** Right-side drawer (never a permanent panel). The backend only answers via permission-checked tools. */
export function AskDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [q, setQ] = useState("");
  const [res, setRes] = useState<(Answer & { question: string }) | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const router = useRouter();
  const input = useRef<HTMLInputElement>(null);

  const ask = async (question: string) => {
    if (question.trim().length < 2) return;
    setBusy(true); setErr("");
    try { setRes({ ...(await api<Answer>("/ai/assistant/query", { body: { question } })), question }); setQ(""); }
    catch (e: any) { setErr(e.message); }
    finally { setBusy(false); }
  };
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50">
      <div className="absolute inset-0 bg-slate-900/30" onClick={onClose} />
      <aside role="dialog" aria-label="Ask IntelliCRM" className="absolute inset-y-0 right-0 flex w-full max-w-md flex-col border-l border-line bg-surface shadow-pop">
        <div className="flex items-center justify-between border-b border-line px-5 py-3.5"><h2>Ask IntelliCRM</h2><button className="rounded p-1 hover:bg-muted" onClick={onClose} aria-label="Close"><Icon name="close" /></button></div>
        <div className="flex-1 space-y-4 overflow-y-auto p-5">
          {!res && <p className="text-ink-2">Ask about the data you have access to. Answers come from your permitted records only.</p>}
          {res && (
            <div>
              <p className="text-small text-ink-2">{res.question}</p>
              <p className="mt-2 font-medium">{res.answer}</p>
              <ol className="mt-3 space-y-2">
                {res.items.map((i, k) => (
                  <li key={k} className="rounded-ctl border border-line p-3">
                    <p className="font-medium">{k + 1}. {i.title}</p><p className="text-small text-ink-2">{i.detail}</p>
                    {i.entity_type && ROUTES[i.entity_type] && <button className="mt-1 text-small text-primary" onClick={() => { router.push(`${ROUTES[i.entity_type!]}/${i.entity_id}`); onClose(); }}>View details</button>}
                  </li>
                ))}
              </ol>
              {res.tools_used.length > 0 && <p className="mt-3 text-[11px] text-ink-2">Source: {res.tools_used.join(", ")} (live data, your permissions)</p>}
              {res.suggestions.length > 0 && <div className="mt-3 flex flex-wrap gap-2">{res.suggestions.map((s) => <button key={s} className="btn btn-sm" onClick={() => ask(s)}>{s}</button>)}</div>}
            </div>
          )}
          {err && <p className="text-danger" role="alert">{err}</p>}
          {!res && <div className="flex flex-wrap gap-2">{["Which customers need attention today?", "What should I work on next?", "What is the status of my projects?"].map((s) => <button key={s} className="btn btn-sm" onClick={() => ask(s)}>{s}</button>)}</div>}
        </div>
        <form className="flex gap-2 border-t border-line p-4" onSubmit={(e) => { e.preventDefault(); ask(q); }}>
          <input ref={input} className="input" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Ask a question..." aria-label="Question" maxLength={500} />
          <button className="btn btn-primary" disabled={busy} aria-label="Send"><Icon name="send" size={16} /></button>
        </form>
      </aside>
    </div>
  );
}
