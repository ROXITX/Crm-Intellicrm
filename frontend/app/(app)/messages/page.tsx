"use client";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useApi, useDebounced } from "@/hooks/useApi";
import { Badge, DataState, EmptyState, Modal, PageHeader, errMsg } from "@/components/common/ui";
import { useToast } from "@/components/common/toast";
import { ago } from "@/lib/format";
import type { Directory, Paged, Customer } from "@/types/api";

function Messages() {
  const { me, can } = useAuth();
  const toast = useToast();
  const sp = useSearchParams();
  const client = me?.role === "client";
  const { data: convs, loading, error, reload } = useApi<any[]>("/conversations");
  const [active, setActive] = useState<string | null>(sp.get("c"));
  const [msgs, setMsgs] = useState<any[]>([]);
  const [text, setText] = useState("");
  const [q, setQ] = useState("");
  const dq = useDebounced(q);
  const [typing, setTyping] = useState(false);
  const [create, setCreate] = useState(!!sp.get("customer"));
  const bottom = useRef<HTMLDivElement>(null);
  const lastTyping = useRef(0);

  const load = useCallback(async (id: string) => {
    try { const r = await api<any>(`/conversations/${id}/messages`, { params: { q: dq } }); setMsgs(r.messages); } catch (e) { toast(errMsg(e), "err"); }
  }, [dq, toast]);
  useEffect(() => { if (active) load(active); }, [active, load]);
  useEffect(() => { if (!active && convs?.length) setActive(convs[0].id); }, [convs, active]);
  useEffect(() => { bottom.current?.scrollIntoView({ block: "end" }); }, [msgs]);
  useEffect(() => { // real-time updates over the WebSocket opened by AppShell
    const h = (e: Event) => {
      const d = (e as CustomEvent).detail;
      if (d.type === "message") { reload(); if (d.conversation_id === active) load(active!); }
      if (d.type === "typing" && d.conversation_id === active) { setTyping(true); setTimeout(() => setTyping(false), 2500); }
    };
    window.addEventListener("crm:ws", h); return () => window.removeEventListener("crm:ws", h);
  }, [active, load, reload]);

  const send = async () => {
    if (!text.trim() || !active) return;
    try { await api(`/conversations/${active}/messages`, { body: { body: text } }); setText(""); load(active); reload(); } catch (e) { toast(errMsg(e), "err"); }
  };
  const onType = (v: string) => { setText(v); const ws: WebSocket | null = (window as any).__crmWs?.(); if (ws?.readyState === 1 && Date.now() - lastTyping.current > 2000 && active) { lastTyping.current = Date.now(); ws.send(JSON.stringify({ type: "typing", conversation_id: active })); } };
  const current = convs?.find((c) => c.id === active);

  return (
    <div>
      <PageHeader title="Messages" subtitle={client ? "Talk to your team" : "Client and internal conversations"} actions={can("messages.write") && <button className="btn btn-primary" onClick={() => setCreate(true)}>New conversation</button>} />
      <div className="card grid h-[calc(100vh-14rem)] min-h-[420px] overflow-hidden md:grid-cols-[300px_1fr]">
        <div className="overflow-y-auto border-b border-line md:border-b-0 md:border-r">
          <DataState loading={loading && !convs} error={error} onRetry={reload} empty={!!convs && convs.length === 0 && { title: "No conversations yet" }}>
            <ul>{convs?.map((c) => (
              <li key={c.id}><button onClick={() => setActive(c.id)} className={`block w-full border-b border-line px-4 py-3 text-left hover:bg-muted ${active === c.id ? "bg-primary/5" : ""}`}>
                <div className="flex items-center justify-between gap-2"><span className="truncate font-medium">{c.title || c.customer_name || "Conversation"}</span>{c.unread > 0 && <span className="grid h-5 min-w-5 place-items-center rounded-full bg-primary px-1.5 text-[11px] text-white">{c.unread}</span>}</div>
                <div className="mt-0.5 flex items-center gap-2">{!client && <Badge value={c.type} tone={c.type === "client" ? "info" : "neutral"} />}<span className="truncate text-small text-ink-2">{c.last_message || "No messages"}</span></div></button></li>))}</ul>
          </DataState>
        </div>
        <div className="flex min-h-0 flex-col">
          {!current ? <EmptyState title="Select a conversation" /> : (<>
            <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-2.5"><div><p className="font-medium">{current.title || current.customer_name}</p>{!client && <Badge value={current.type} tone={current.type === "client" ? "info" : "neutral"} label={current.type === "client" ? "Client-facing" : "Internal only"} />}</div>
              <input className="input w-44" placeholder="Search messages" aria-label="Search messages" value={q} onChange={(e) => setQ(e.target.value)} /></div>
            <div className="flex-1 space-y-3 overflow-y-auto p-4">
              {msgs.length === 0 && <p className="text-center text-ink-2">No messages.</p>}
              {msgs.map((m) => { const mine = m.sender_id === me?.id; return (
                <div key={m.id} className={`flex ${mine ? "justify-end" : ""}`}><div className={`max-w-[75%] rounded-lg px-3 py-2 ${mine ? "bg-primary text-white" : "bg-muted"}`}>
                  {!mine && <p className="text-[11.5px] font-medium opacity-70">{m.sender_name}</p>}<p className="whitespace-pre-wrap">{m.body}</p>
                  <p className={`mt-0.5 text-[11px] ${mine ? "text-white/70" : "text-ink-2"}`}>{ago(m.created_at)}{mine && (m.read_by_all ? " · Read" : " · Sent")}</p></div></div>); })}
              <div ref={bottom} />
            </div>
            <div className="border-t border-line p-3">{typing && <p className="mb-1 text-small text-ink-2" aria-live="polite">Someone is typing...</p>}
              <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); send(); }}><input className="input" value={text} onChange={(e) => onType(e.target.value)} placeholder="Write a message..." aria-label="Message" maxLength={5000} /><button className="btn btn-primary">Send</button></form></div>
          </>)}
        </div>
      </div>
      <NewConversation open={create} onClose={() => setCreate(false)} client={!!client} presetCustomer={sp.get("customer")} onCreated={(id) => { reload(); setActive(id); }} />
    </div>
  );
}

function NewConversation({ open, onClose, client, presetCustomer, onCreated }: { open: boolean; onClose: () => void; client: boolean; presetCustomer: string | null; onCreated: (id: string) => void }) {
  const toast = useToast();
  const { data: team } = useApi<Directory>(open && !client ? "/team/directory" : null);
  const { data: custs } = useApi<Paged<Customer>>(open && !client ? "/customers" : null, { page_size: 100 });
  const [type, setType] = useState<"client" | "internal">(client ? "client" : presetCustomer ? "client" : "internal");
  const [title, setTitle] = useState("");
  const [customer, setCustomer] = useState(presetCustomer || "");
  const [members, setMembers] = useState<string[]>([]);
  const go = async () => {
    try { const c = await api<any>("/conversations", { body: { type, title: title || null, customer_id: type === "client" && !client ? customer || null : null, member_ids: members } }); toast("Conversation created"); onCreated(c.id); onClose(); } catch (e) { toast(errMsg(e), "err"); }
  };
  return (
    <Modal open={open} onClose={onClose} title="New conversation">
      <div className="space-y-3">
        {!client && <div><label className="label">Type</label><select className="input" value={type} onChange={(e) => setType(e.target.value as any)}><option value="internal">Internal (team only)</option><option value="client">Client conversation</option></select></div>}
        <div><label className="label">Title</label><input className="input" value={title} onChange={(e) => setTitle(e.target.value)} /></div>
        {!client && type === "client" && <div><label className="label">Customer</label><select className="input" value={customer} onChange={(e) => setCustomer(e.target.value)}><option value="">Select...</option>{custs?.items.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></div>}
        {!client && <div><label className="label">Members</label><div className="max-h-36 space-y-1 overflow-auto rounded-ctl border border-line p-2">{team?.map((m) => <label key={m.id} className="flex items-center gap-2 text-[13px]"><input type="checkbox" checked={members.includes(m.id)} onChange={(e) => setMembers(e.target.checked ? [...members, m.id] : members.filter((x) => x !== m.id))} />{m.name} <span className="text-ink-2">({m.role})</span></label>)}</div></div>}
        <div className="flex justify-end gap-2"><button className="btn" onClick={onClose}>Cancel</button><button className="btn btn-primary" onClick={go}>Create</button></div>
      </div>
    </Modal>
  );
}

export default function MessagesPage() { return <Suspense fallback={<p className="text-ink-2">Loading...</p>}><Messages /></Suspense>; }
