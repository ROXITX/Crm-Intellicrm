"use client";
import { useState } from "react";
import { useApi, useDebounced } from "./useApi";
import type { Paged } from "@/types/api";

/** Server-side filter/sort/pagination state shared by every list page. */
export function useList<T>(path: string, initial: Record<string, any> = {}, pageSize = 25) {
  const [filters, setFilters] = useState<Record<string, any>>(initial);
  const [page, setPage] = useState(1);
  const [sort, setSort] = useState<{ key: string; order: "asc" | "desc" } | undefined>(undefined);
  const dq = useDebounced(filters.q, 300);
  const params = { ...filters, q: dq, page, page_size: pageSize, ...(sort ? { sort: sort.key, order: sort.order } : {}) };
  const res = useApi<Paged<T>>(path, params);
  return {
    ...res, rows: res.data?.items, total: res.data?.total ?? 0, page, pageSize, setPage, filters, sort,
    setFilter: (k: string, v: any) => { setFilters((f) => ({ ...f, [k]: v })); setPage(1); },
    toggleSort: (key: string) => setSort((s) => (s?.key === key ? { key, order: s.order === "asc" ? "desc" : "asc" } : { key, order: "desc" })),
  };
}
