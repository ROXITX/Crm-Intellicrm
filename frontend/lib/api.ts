// Thin fetch wrapper: bearer token in memory, silent refresh via the httpOnly cookie, consistent errors.
export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public requestId?: string, public details?: { field: string; message: string }[]) {
    super(message);
  }
}

const BASE = "/api/v1";
let accessToken: string | null = null;
let refreshing: Promise<boolean> | null = null;
export const setToken = (t: string | null) => { accessToken = t; };
export const getToken = () => accessToken;

async function parse(res: Response) {
  if (res.status === 204) return null;
  const ct = res.headers.get("content-type") || "";
  const body = ct.includes("json") ? await res.json() : await res.text();
  if (!res.ok) {
    const e = (body as any)?.error;
    throw new ApiError(res.status, e?.code || "HTTP_ERROR", e?.message || res.statusText, e?.request_id, e?.details);
  }
  return body;
}

export async function refreshSession(): Promise<boolean> {
  refreshing ??= fetch(`${BASE}/auth/refresh`, { method: "POST", credentials: "include" })
    .then(async (r) => { if (!r.ok) return false; setToken((await r.json()).access_token); return true; })
    .catch(() => false)
    .finally(() => { refreshing = null; });
  return refreshing;
}

export async function api<T = any>(path: string, opts: { method?: string; body?: unknown; form?: FormData; params?: Record<string, any> } = {}): Promise<T> {
  const qs = opts.params ? "?" + new URLSearchParams(Object.entries(opts.params).filter(([, v]) => v !== undefined && v !== null && v !== "").map(([k, v]) => [k, String(v)])).toString() : "";
  const run = () => fetch(`${BASE}${path}${qs}`, {
    method: opts.method || (opts.body || opts.form ? "POST" : "GET"), credentials: "include",
    headers: { ...(opts.body ? { "Content-Type": "application/json" } : {}), ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}) },
    body: opts.form ?? (opts.body ? JSON.stringify(opts.body) : undefined),
  });
  let res = await run();
  if (res.status === 401 && !path.startsWith("/auth/") && (await refreshSession())) res = await run();
  if (res.status === 401 && !path.startsWith("/auth/")) { setToken(null); if (typeof window !== "undefined") window.location.href = "/login"; }
  return parse(res);
}

/** Authenticated file download (the API never exposes storage keys; access is checked per request). */
export async function download(path: string, filename: string) {
  const res = await fetch(`${BASE}${path}`, { headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {}, credentials: "include" });
  if (!res.ok) throw new ApiError(res.status, "DOWNLOAD_FAILED", "Download failed");
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement("a"); a.href = url; a.download = filename; a.click(); URL.revokeObjectURL(url);
}
