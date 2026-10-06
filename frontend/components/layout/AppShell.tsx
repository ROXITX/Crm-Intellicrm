"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { useAuth } from "@/lib/auth";
import { api, getToken } from "@/lib/api";
import { CLIENT_NAV, STAFF_NAV } from "@/lib/nav";
import { ago, initials, title } from "@/lib/format";
import { useApi, useDebounced } from "@/hooks/useApi";
import { Icon } from "@/components/common/Icon";
import { AskDrawer } from "@/components/ai/AskDrawer";
import { ToastProvider } from "@/components/common/toast";

const ROUTES: Record<string, string> = { lead: "/leads", customer: "/customers", project: "/projects", task: "/tasks", ticket: "/tickets", invoice: "/invoices", message: "/messages" };

function Sidebar({ onNavigate, onAsk }: { onNavigate?: () => void; onAsk: () => void }) {
  const { me, can, logout } = useAuth();
  const path = usePathname();
  const groups = me?.role === "client" ? CLIENT_NAV : STAFF_NAV;
  return (
    <aside className="flex h-full w-64 flex-col bg-sidebar text-slate-200">
      <div className="flex h-16 items-center gap-2 px-5">
        <span className="grid h-7 w-7 place-items-center rounded-md bg-primary text-[13px] font-bold text-white">iC</span>
        <div className="leading-tight"><p className="text-[15px] font-semibold text-white">IntelliCRM</p><p className="max-w-[150px] truncate text-[11px] text-slate-400">{me?.organization.name}</p></div>
      </div>
      <nav className="flex-1 space-y-5 overflow-y-auto px-3 py-3" aria-label="Main navigation">
        {groups.map((g) => {
          const items = g.items.filter((i) => !i.perm || can(i.perm));
          if (!items.length) return null;
          return (
            <div key={g.title || "x"}>
              {g.title && <p className="mb-1.5 px-3 text-[11px] font-medium uppercase tracking-wider text-slate-500">{g.title}</p>}
              <ul className="space-y-0.5">
                {items.map((i) => {
                  const active = i.action ? false : path === i.href || path.startsWith(i.href + "/");
                  return (
                    <li key={i.href}>
                      {i.action === "ask" ? (
                        <button className="nav-item w-full text-left" onClick={() => { onAsk(); onNavigate?.(); }}><Icon name={i.icon} /> {i.label}</button>
                      ) : (
                        <Link href={i.href} className="nav-item" aria-current={active ? "page" : undefined} onClick={onNavigate}><Icon name={i.icon} /> {i.label}</Link>
                      )}
                    </li>
                  );
                })}
              </ul>
            </div>
          );
        })}
      </nav>
      <div className="flex items-center gap-3 border-t border-white/10 px-4 py-3.5">
        <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-sidebar-hover text-[12px] font-semibold text-white">{initials(`${me?.first_name} ${me?.last_name || ""}`)}</span>
        <div className="min-w-0 flex-1 leading-tight">
          <p className="truncate text-[13px] font-medium text-white">{me?.first_name} {me?.last_name}</p>
          <p className="text-[11.5px] capitalize text-slate-400">{me?.role}</p>
        </div>
        <button onClick={logout} className="rounded p-1.5 text-slate-400 hover:bg-sidebar-hover hover:text-white" aria-label="Log out" title="Log out"><Icon name="logout" size={16} /></button>
      </div>
    </aside>
  );
}

function GlobalSearch() {
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const dq = useDebounced(q, 250);
  const { data } = useApi<{ results: any[] }>(dq.trim().length >= 2 ? "/search" : null, { q: dq.trim() });
  const router = useRouter();
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const h = (e: MouseEvent) => !box.current?.contains(e.target as Node) && setOpen(false);
    document.addEventListener("mousedown", h);
    const k = (e: KeyboardEvent) => { if ((e.metaKey || e.ctrlKey) && e.key === "k") { e.preventDefault(); document.getElementById("global-search")?.focus(); } };
    document.addEventListener("keydown", k);
    return () => { document.removeEventListener("mousedown", h); document.removeEventListener("keydown", k); };
  }, []);
  const go = (r: any) => { setOpen(false); setQ(""); router.push(r.type === "message" ? `/messages?c=${r.conversation_id}` : `${ROUTES[r.type]}/${r.id}`); };
  return (
    <div ref={box} className="relative w-full max-w-md">
      <Icon name="search" size={16} className="pointer-events-none absolute left-3 top-2.5 text-ink-2" />
      <input id="global-search" className="input pl-9 pr-12" placeholder="Search customers, leads, projects..." value={q} aria-label="Global search"
        onChange={(e) => { setQ(e.target.value); setOpen(true); }} onFocus={() => setOpen(true)} />
      <kbd className="absolute right-2.5 top-2 hidden rounded sm:block border border-line px-1.5 text-[11px] text-ink-2">Ctrl K</kbd>
      {open && q.trim().length >= 2 && (
        <div className="absolute z-40 mt-1 max-h-96 w-full overflow-auto rounded-card border border-line bg-surface shadow-pop">
          {!data ? <p className="p-3 text-ink-2">Searching...</p> : data.results.length === 0 ? <p className="p-3 text-ink-2">No results</p> : data.results.map((r) => (
            <button key={r.type + r.id} onClick={() => go(r)} className="flex w-full items-center gap-3 px-3 py-2 text-left hover:bg-muted">
              <span className="badge badge-neutral w-16 justify-center capitalize">{r.type}</span>
              <span className="min-w-0"><span className="block truncate">{r.title}</span>{r.subtitle && <span className="block truncate text-small text-ink-2">{title(r.subtitle)}</span>}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function Bell() {
  const [open, setOpen] = useState(false);
  const { data, reload } = useApi<{ items: any[]; unread_count: number }>("/notifications", { page_size: 8 });
  useEffect(() => { const t = setInterval(reload, 60000); const h = () => reload(); window.addEventListener("crm:ws", h); return () => { clearInterval(t); window.removeEventListener("crm:ws", h); }; }, [reload]);
  const read = async (id?: string) => { await api(id ? `/notifications/${id}/read` : "/notifications/read-all", { method: "POST" }); reload(); };
  return (
    <div className="relative">
      <button className="relative rounded-ctl p-2 text-ink-2 hover:bg-muted" onClick={() => { setOpen(!open); reload(); }} aria-label={`Notifications (${data?.unread_count || 0} unread)`}>
        <Icon name="bell" />
        {!!data?.unread_count && <span className="absolute right-0.5 top-0.5 grid h-4 min-w-4 place-items-center rounded-full bg-danger px-1 text-[10px] font-semibold text-white">{data.unread_count}</span>}
      </button>
      {open && (
        <div className="absolute right-0 z-40 mt-1 w-80 rounded-card border border-line bg-surface shadow-pop">
          <div className="flex items-center justify-between border-b border-line px-3 py-2"><span className="font-medium">Notifications</span><button className="text-small text-primary" onClick={() => read()}>Mark all read</button></div>
          <div className="max-h-96 overflow-auto">
            {!data?.items.length ? <p className="p-4 text-ink-2">You're all caught up.</p> : data.items.map((n) => (
              <button key={n.id} onClick={() => read(n.id)} className={`block w-full border-b border-line px-3 py-2.5 text-left last:border-0 hover:bg-muted ${n.read_at ? "" : "bg-primary/5"}`}>
                <p className="font-medium">{n.title}</p><p className="truncate text-small text-ink-2">{n.message}</p><p className="text-[11px] text-ink-2">{ago(n.created_at)}</p>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const { me, loading } = useAuth();
  const router = useRouter();
  const [drawer, setDrawer] = useState(false);
  const [ask, setAsk] = useState(false);
  const [help, setHelp] = useState(false);
  const path = usePathname();

  useEffect(() => { if (!loading && !me) router.replace("/login"); }, [loading, me, router]);
  useEffect(() => { setDrawer(false); }, [path]);
  useEffect(() => { // real-time channel (messages, notifications, typing)
    if (!me) return;
    const base = process.env.NEXT_PUBLIC_WS_URL || `${location.protocol === "https:" ? "wss" : "ws"}://${location.hostname}:8000/api/v1/ws`;
    let ws: WebSocket | null = null; let stop = false; let retry: any;
    const open = () => {
      const t = getToken(); if (!t || stop) return;
      ws = new WebSocket(`${base}?token=${encodeURIComponent(t)}`);
      ws.onmessage = (e) => window.dispatchEvent(new CustomEvent("crm:ws", { detail: JSON.parse(e.data) }));
      ws.onclose = () => { if (!stop) retry = setTimeout(open, 5000); };
    };
    open();
    (window as any).__crmWs = () => ws;
    return () => { stop = true; clearTimeout(retry); ws?.close(); };
  }, [me]);

  if (loading || !me) return <div className="grid h-screen place-items-center text-ink-2" role="status">Loading...</div>;
  return (
    <ToastProvider>
      <div className="flex h-screen">
        <div className="hidden lg:block"><Sidebar onAsk={() => setAsk(true)} /></div>
        {drawer && (
          <div className="fixed inset-0 z-50 lg:hidden">
            <div className="absolute inset-0 bg-slate-900/50" onClick={() => setDrawer(false)} />
            <div className="absolute inset-y-0 left-0"><Sidebar onNavigate={() => setDrawer(false)} onAsk={() => setAsk(true)} /></div>
          </div>
        )}
        <div className="flex min-w-0 flex-1 flex-col">
          <header className="flex h-16 shrink-0 items-center gap-3 border-b border-line bg-surface px-4 lg:px-8">
            <button className="rounded p-2 hover:bg-muted lg:hidden" onClick={() => setDrawer(true)} aria-label="Open menu"><Icon name="menu" /></button>
            <div className="flex flex-1 justify-center lg:justify-start"><GlobalSearch /></div>
            <Bell />
            <button className="rounded-ctl p-2 text-ink-2 hover:bg-muted" aria-label="Help" onClick={() => setHelp(!help)}><Icon name="help" /></button>
          </header>
          {help && (
            <div className="border-b border-line bg-muted px-8 py-2.5 text-small text-ink-2">
              Tip: press <kbd className="rounded border border-line px-1">Ctrl K</kbd> to search. {me.role !== "client" && "Use Ask IntelliCRM in the sidebar for quick answers. "}
              Full guide: <code>docs/USER_GUIDE.md</code>. <button className="ml-2 text-primary" onClick={() => setHelp(false)}>Dismiss</button>
            </div>
          )}
          <main className="flex-1 overflow-y-auto p-4 lg:p-8" id="main">{children}</main>
        </div>
      </div>
      <AskDrawer open={ask} onClose={() => setAsk(false)} />
    </ToastProvider>
  );
}
