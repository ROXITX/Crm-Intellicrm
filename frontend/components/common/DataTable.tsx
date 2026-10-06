"use client";
import { DataState, Pagination } from "./ui";
import type { ApiError } from "@/lib/api";

export type Column<T> = { key: string; header: string; render: (row: T) => React.ReactNode; className?: string; sortKey?: string };

export function DataTable<T extends { id: string }>({ columns, rows, loading, error, onRetry, empty, onRowClick, page, pageSize, total, onPage, sort, onSort }: {
  columns: Column<T>[]; rows: T[] | undefined; loading: boolean; error: ApiError | null; onRetry: () => void;
  empty: { title: string; hint?: string; action?: React.ReactNode }; onRowClick?: (r: T) => void;
  page?: number; pageSize?: number; total?: number; onPage?: (p: number) => void;
  sort?: { key: string; order: "asc" | "desc" }; onSort?: (key: string) => void;
}) {
  return (
    <div className="card overflow-hidden">
      <DataState loading={loading && !rows} error={error} onRetry={onRetry} empty={!!rows && rows.length === 0 && empty}>
        <div className="overflow-x-auto">
          <table>
            <thead><tr>{columns.map((c) => (
              <th key={c.key} className={c.className} aria-sort={sort && c.sortKey === sort.key ? (sort.order === "asc" ? "ascending" : "descending") : undefined}>
                {c.sortKey && onSort ? <button className="font-medium hover:text-ink" onClick={() => onSort(c.sortKey!)}>{c.header}{sort?.key === c.sortKey ? (sort.order === "asc" ? " ↑" : " ↓") : ""}</button> : c.header}
              </th>))}</tr></thead>
            <tbody className={loading ? "opacity-60" : ""}>
              {rows?.map((r) => (
                <tr key={r.id} className={onRowClick ? "cursor-pointer hover:bg-muted" : ""} onClick={() => onRowClick?.(r)}
                  tabIndex={onRowClick ? 0 : undefined} onKeyDown={(e) => e.key === "Enter" && onRowClick?.(r)}>
                  {columns.map((c) => <td key={c.key} className={c.className}>{c.render(r)}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {total != null && page != null && pageSize != null && onPage && <Pagination page={page} pageSize={pageSize} total={total} onChange={onPage} />}
      </DataState>
    </div>
  );
}
