"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { useAuth } from "@/lib/auth";
import { api, getToken } from "@/lib/api";
import { CLIENT_NAV, STAFF_NAV } from "@/lib/nav";
import { ago, title } from "@/lib/format";
import { Avatar } from "@/components/common/Avatar";
import { useApi, useDebounced } from "@/hooks/useApi";
import { Icon } from "@/components/common/Icon";
import { AskDrawer } from "@/components/ai/AskDrawer";
import { ToastProvider } from "@/components/common/toast";

const ROUTES: Record<string, string> = { lead: "/leads", customer: "/customers", project: "/projects", task: "/tasks", ticket: "/tickets", invoice: "/invoices", message: "/messages" };

function Sidebar({ onNavigate, onAsk, unread }: { onNavigate?: () => void; onAsk: () => void; unread: number }) {
  const { me, can } = useAuth();
  const path = usePathname();
  const groups = me?.role === "client" ? CLIENT_NAV : STAFF_NAV;
  const roleLabel = me?.role === "owner" ? "Owner Plan" : title(me?.role);
  return (
    <aside className="flex h-full w-[248px] flex-col bg-sidebar text-slate-200">
      <div className="flex h-16 items-center gap-2.5 px-5">
        <span className="grid h-8 w-8 place-items-center rounded-[9px] bg-primary text-white"><Icon name="sparkle" size={18} /></span>
        <p className="text-[19px] font-semibold tracking-tight text-white">IntelliCRM</p>
      </div>
      <nav className="flex-1 overflow-y-auto px-3 py-2" aria-label="Main navigation">
        {groups.map((g, gi) => {
          const items = g.items.filter((i) => !i.perm || can(i.perm));
          if (!items.length) return null;
          return (
            <ul key={gi} className={`space-y-0.5 ${gi > 0 ? "mt-3 border-t border-white/10 pt-3" : ""}`}>
              {items.map((i) => {
                const active = i.action ? false : path === i.href || path.startsWith(i.href + "/");
                const inner = (<><Icon name={i.icon} size={19} /><span className="flex-1">{i.label}</span>{i.badge === "messages" && unread > 0 && <span className="grid h-5 min-w-5 place-items-center rounded-md bg-danger px-1.5 text-[11px] font-semibold text-white">{unread}</span>}</>);
                return (
                  <li key={i.href}>
                    {i.action === "ask" ? <button className="nav-item w-full text-left" onClick={() => { onAsk(); onNavigate?.(); }}>{inner}</button>
                      : <Link href={i.href} className="nav-item" aria-current={active ? "page" : undefined} onClick={onNavigate}>{inner}</Link>}
                  </li>
                );
              })}
            </ul>
          );
        })}
      </nav>
      <div className="p-3">
        <div className="flex items-center gap-3 rounded-[10px] bg-sidebar-hover/60 px-3 py-2.5">
          <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-white/10 text-white"><Icon name="projects" size={18} /></span>
          <div className="min-w-0 flex-1 leading-tight"><p className="truncate text-[13.5px] font-semibold text-white">{me?.organization.name}</p><p className="text-[11.5px] text-slate-400">{roleLabel}</p></div>
          <Icon name="chevron" size={16} className="text-slate-400" />
        </div>
      </div>
    </aside>
  );
}

function UserMenu() {
  const { me, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => { const h = (e: MouseEvent) => !box.current?.contains(e.target as Node) && setOpen(false); document.addEventListener("mousedown", h); return () => document.removeEventListener("mousedown", h); }, []);
  const name = `${me?.first_name} ${me?.last_name || ""}`.trim();
  return (
    <div ref={box} className="relative">
      <button className="flex items-center gap-2.5 rounded-lg py-1 pl-1 pr-2 hover:bg-muted" onClick={() => setOpen(!open)} aria-haspopup="menu" aria-expanded={open}>
        <Avatar name={name} size={38} />
        <span className="hidden text-left leading-tight sm:block"><span className="block text-[13.5px] font-semibold">{name}</span><span className="block text-[12px] capitalize text-ink-2">{me?.role}</span></span>
        <Icon name="chevdown" size={16} className="text-ink-2" />
      </button>
      {open && (
        <div role="menu" className="absolute right-0 z-40 mt-1 w-56 rounded-card border border-line bg-surface py-1 shadow-pop">
          <p className="truncate border-b border-line px-3 py-2 text-small text-ink-2">{me?.email}</p>
          <Link role="menuitem" href="/settings" className="block px-3 py-2 hover:bg-muted" onClick={() => setOpen(false)}>{me?.role === "client" ? "Profile" : "Settings"}</Link>
          <Link role="menuitem" href="/notifications" className="block px-3 py-2 hover:bg-muted" onClick={() => setOpen(false)}>Notifications</Link>
          <button role="menuitem" className="block w-full px-3 py-2 text-left text-danger hover:bg-muted" onClick={logout}>Log out</button>
        </div>
      )}
    </div>
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
    <div ref={box} className="relative w-full max-w-xl">
      <Icon name="search" size={16} className="pointer-events-none absolute left-3 top-2.5 text-ink-2" />
      <input id="global-search" className="input pl-9 pr-12" placeholder="Search customers, projects, tasks, or ask IntelliCRM..." value={q} aria-label="Global search"
        onChange={(e) => { setQ(e.target.value); setOpen(true); }} onFocus={() => setOpen(true)} />
      <kbd className="absolute right-2.5 top-2 hidden rounded border border-line px-1.5 text-[11px] text-ink-2 sm:block">Ctrl K</kbd>
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
        {!!data?.unread_count && <span className="absolute right-1.5 top-1.5 h-2.5 w-2.5 rounded-full border-2 border-surface bg-danger" />}
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
  const convs = useApi<any[]>(me ? "/conversations" : null);
  const unreadMsgs = (convs.data || []).reduce((n, c) => n + (c.unread || 0), 0);
  useEffect(() => { const h = () => convs.reload(); window.addEventListener("crm:ws", h); return () => window.removeEventListener("crm:ws", h); }, [convs.reload]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { if (!loading && !me) router.replace("/login"); }, [loading, me, router]);
  useEffect(() => { setDrawer(false); }, [path]);
  useEffect(() => { const h = () => setAsk(true); window.addEventListener("crm:ask", h); return () => window.removeEventListener("crm:ask", h); }, []);
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
        <div className="hidden lg:block"><Sidebar onAsk={() => setAsk(true)} unread={unreadMsgs} /></div>
        {drawer && (
          <div className="fixed inset-0 z-50 lg:hidden">
            <div className="absolute inset-0 bg-slate-900/50" onClick={() => setDrawer(false)} />
            <div className="absolute inset-y-0 left-0"><Sidebar onNavigate={() => setDrawer(false)} onAsk={() => setAsk(true)} unread={unreadMsgs} /></div>
          </div>
        )}
        <div className="flex min-w-0 flex-1 flex-col">
          <header className="flex h-16 shrink-0 items-center gap-3 border-b border-line bg-surface px-4 lg:px-8">
            <button className="rounded p-2 hover:bg-muted lg:hidden" onClick={() => setDrawer(true)} aria-label="Open menu"><Icon name="menu" /></button>
            <div className="flex flex-1 justify-center lg:justify-start"><GlobalSearch /></div>
            <Bell />
            <button className="rounded-ctl p-2 text-ink-2 hover:bg-muted" aria-label="Help" onClick={() => setHelp(!help)}><Icon name="help" /></button>
            <UserMenu />
          </header>
          {help && (
            <div className="border-b border-line bg-muted px-8 py-2.5 text-small text-ink-2">
              Tip: press <kbd className="rounded border border-line px-1">Ctrl K</kbd> to search. {me.role !== "client" && "Use Ask IntelliCRM in the sidebar for quick answers. "}
              Full guide: <code>docs/USER_GUIDE.md</code>. <button className="ml-2 text-primary" onClick={() => setHelp(false)}>Dismiss</button>
            </div>
          )}
          <main className="flex-1 overflow-y-auto p-4 lg:px-8 lg:py-7" id="main">{children}</main>
        </div>
      </div>
      <AskDrawer open={ask} onClose={() => setAsk(false)} />
    </ToastProvider>
  );
}
