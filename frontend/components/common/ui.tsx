"use client";
import { cloneElement, isValidElement, useEffect, useId, useRef } from "react";
import type { ApiError } from "@/lib/api";
import { title } from "@/lib/format";
import { Icon } from "./Icon";

const TONE: Record<string, string> = {
  healthy: "success", watch: "warning", at_risk: "danger", critical: "danger", low: "neutral", medium: "warning", high: "danger",
  new: "info", contacted: "primary", qualified: "primary", proposal: "warning", negotiation: "warning", won: "success", lost: "neutral",
  planning: "neutral", active: "info", delayed: "danger", completed: "success", archived: "neutral",
  todo: "neutral", in_progress: "info", blocked: "danger", review: "warning", done: "success", cancelled: "neutral",
  open: "info", waiting_customer: "warning", waiting_internal: "warning", resolved: "success", closed: "neutral",
  draft: "neutral", sent: "info", partially_paid: "warning", paid: "success", overdue: "danger",
  pending: "warning", failed: "danger", refunded: "neutral", accepted: "success", rejected: "neutral", expired: "neutral",
  positive: "success", neutral: "neutral", negative: "danger", normal: "success", overloaded: "danger", on_track: "success",
  owner: "primary", manager: "info", staff: "neutral", client: "neutral",
};
export function Badge({ value, tone, label }: { value: string | null | undefined; tone?: string; label?: string }) {
  if (!value) return <span className="text-ink-2">-</span>;
  return <span className={`badge badge-${tone || TONE[value] || "neutral"}`}>{label || title(value)}</span>;
}

export function PageHeader({ title: t, subtitle, actions }: { title: string; subtitle?: string; actions?: React.ReactNode }) {
  return (
    <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
      <div><h1>{t}</h1>{subtitle && <p className="mt-1 text-ink-2">{subtitle}</p>}</div>
      <div className="flex flex-wrap items-center gap-2">{actions}</div>
    </div>
  );
}

export const Skeleton = ({ className = "h-4 w-full" }: { className?: string }) => <div className={`skeleton ${className}`} />;
export const TableSkeleton = ({ rows = 6 }: { rows?: number }) => (
  <div className="space-y-3 p-4" role="status" aria-label="Loading">{Array.from({ length: rows }).map((_, i) => <Skeleton key={i} className="h-5" />)}</div>
);

export function EmptyState({ title: t, hint, action }: { title: string; hint?: string; action?: React.ReactNode }) {
  return (
    <div className="px-6 py-12 text-center">
      <p className="font-medium">{t}</p>
      {hint && <p className="mt-1 text-ink-2">{hint}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: ApiError | Error; onRetry?: () => void }) {
  return (
    <div className="px-6 py-10 text-center" role="alert">
      <p className="font-medium text-danger">Something went wrong</p>
      <p className="mt-1 text-ink-2">{error.message}{(error as any).requestId ? ` (ref ${(error as any).requestId.slice(0, 8)})` : ""}</p>
      {onRetry && <button className="btn mt-4" onClick={onRetry}>Retry</button>}
    </div>
  );
}

/** Standard loading / error / empty wrapper used by every list and detail panel. */
export function DataState({ loading, error, onRetry, empty, children }: { loading: boolean; error: ApiError | null; onRetry: () => void; empty?: { title: string; hint?: string; action?: React.ReactNode } | false; children: React.ReactNode }) {
  if (loading) return <TableSkeleton />;
  if (error) return <ErrorState error={error} onRetry={onRetry} />;
  if (empty) return <EmptyState {...empty} />;
  return <>{children}</>;
}

export function Pagination({ page, pageSize, total, onChange }: { page: number; pageSize: number; total: number; onChange: (p: number) => void }) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  return (
    <div className="flex items-center justify-between border-t border-line px-3 py-2.5 text-small text-ink-2">
      <span>{total === 0 ? "0 results" : `${(page - 1) * pageSize + 1}-${Math.min(page * pageSize, total)} of ${total}`}</span>
      <div className="flex items-center gap-2">
        <button className="btn btn-sm" disabled={page <= 1} onClick={() => onChange(page - 1)}>Previous</button>
        <span>Page {page} / {pages}</span>
        <button className="btn btn-sm" disabled={page >= pages} onClick={() => onChange(page + 1)}>Next</button>
      </div>
    </div>
  );
}

export function Modal({ open, onClose, title: t, children, width = "max-w-lg" }: { open: boolean; onClose: () => void; title: string; children: React.ReactNode; width?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    ref.current?.querySelector<HTMLElement>("input,select,textarea,button")?.focus();
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-slate-900/40 p-4 pt-[8vh]" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div ref={ref} role="dialog" aria-modal="true" aria-label={t} className={`w-full ${width} rounded-xl border border-line bg-surface shadow-pop`}>
        <div className="flex items-center justify-between border-b border-line px-5 py-3.5">
          <h2>{t}</h2>
          <button className="rounded p-1 text-ink-2 hover:bg-muted" onClick={onClose} aria-label="Close"><Icon name="close" /></button>
        </div>
        <div className="p-5">{children}</div>
      </div>
    </div>
  );
}

export function Confirm({ open, onClose, onConfirm, title: t, message, confirmLabel = "Confirm", danger }: { open: boolean; onClose: () => void; onConfirm: () => void; title: string; message: string; confirmLabel?: string; danger?: boolean }) {
  return (
    <Modal open={open} onClose={onClose} title={t} width="max-w-md">
      <p className="text-ink-2">{message}</p>
      <div className="mt-5 flex justify-end gap-2">
        <button className="btn" onClick={onClose}>Cancel</button>
        <button className={`btn ${danger ? "btn-danger" : "btn-primary"}`} onClick={() => { onConfirm(); onClose(); }}>{confirmLabel}</button>
      </div>
    </Modal>
  );
}

export function Field({ label, required, error, children, hint }: { label: string; required?: boolean; error?: string; children: React.ReactNode; hint?: string }) {
  const id = useId();
  // associate the label (and error text) with the control for screen readers / keyboard users
  const control = isValidElement(children)
    ? cloneElement(children as React.ReactElement<any>, { id, "aria-invalid": error ? true : undefined, "aria-describedby": error ? `${id}-err` : undefined })
    : children;
  return (
    <div>
      <label className="label" htmlFor={id}>{label}{required && <span className="ml-0.5 text-danger" aria-hidden> *</span>}</label>
      {control}
      {hint && !error && <p className="mt-1 text-small text-ink-2">{hint}</p>}
      {error && <p id={`${id}-err`} className="mt-1 text-small text-danger" role="alert">{error}</p>}
    </div>
  );
}

export function Progress({ value, tone }: { value: number; tone?: "success" | "warning" | "danger" | "primary" }) {
  const t = tone || (value > 100 ? "danger" : value >= 80 ? "warning" : "primary");
  return <div className="bar" role="progressbar" aria-valuenow={Math.round(value)} aria-valuemin={0} aria-valuemax={100}><span style={{ width: `${Math.min(100, Math.max(0, value))}%`, background: `var(--${t})` }} /></div>;
}

export function Tabs({ tabs, value, onChange }: { tabs: { id: string; label: string }[]; value: string; onChange: (id: string) => void }) {
  return (
    <div className="mb-4 flex gap-1 overflow-x-auto border-b border-line" role="tablist">
      {tabs.map((t) => (
        <button key={t.id} role="tab" aria-selected={value === t.id} onClick={() => onChange(t.id)}
          className={`whitespace-nowrap border-b-2 px-3 py-2 text-[13.5px] ${value === t.id ? "border-primary font-medium text-primary" : "border-transparent text-ink-2 hover:text-ink"}`}>{t.label}</button>
      ))}
    </div>
  );
}

export function Kpi({ label, value, trend, sub }: { label: string; value: React.ReactNode; trend?: number | null; sub?: string }) {
  return (
    <div className="card px-4 py-3.5">
      <p className="text-[11.5px] font-medium uppercase tracking-wide text-ink-2">{label}</p>
      <p className="mt-1 text-[26px] font-bold leading-8">{value}</p>
      <p className="mt-0.5 text-small text-ink-2">
        {trend != null ? <span className={trend >= 0 ? "text-success" : "text-danger"}>{trend >= 0 ? "↑" : "↓"} {Math.abs(trend)}%</span> : null} {sub || (trend != null ? "vs previous 30 days" : "")}
      </p>
    </div>
  );
}

export const errMsg = (e: unknown) => (e as any)?.message || "Request failed";
