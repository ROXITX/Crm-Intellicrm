"use client";
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, refreshSession, setToken } from "@/lib/api";
import type { Me } from "@/types/api";

type AuthCtx = { me: Me | null; loading: boolean; login: (email: string, password: string) => Promise<void>; logout: () => Promise<void>; can: (p: string) => boolean };
const Ctx = createContext<AuthCtx>(null as any);
export const useAuth = () => useContext(Ctx);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);

  const loadMe = useCallback(async () => { setMe(await api<Me>("/auth/me")); }, []);
  useEffect(() => {
    (async () => {
      try { if (await refreshSession()) await loadMe(); } finally { setLoading(false); }
    })();
  }, [loadMe]);

  const login = async (email: string, password: string) => {
    const r = await api<{ access_token: string }>("/auth/login", { body: { email, password } });
    setToken(r.access_token);
    await loadMe();
  };
  const logout = async () => { try { await api("/auth/logout", { method: "POST" }); } finally { setToken(null); setMe(null); window.location.href = "/login"; } };
  const can = (p: string) => !!me?.permissions.includes(p);
  return <Ctx.Provider value={{ me, loading, login, logout, can }}>{children}</Ctx.Provider>;
}
