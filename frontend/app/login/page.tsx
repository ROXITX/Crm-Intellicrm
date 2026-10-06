"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useAuth } from "@/lib/auth";
import { Field } from "@/components/common/ui";
import { api, setToken } from "@/lib/api";

const loginSchema = z.object({ email: z.string().email("Enter a valid email"), password: z.string().min(1, "Password is required") });
const regSchema = z.object({
  organization_name: z.string().min(2, "At least 2 characters"), first_name: z.string().min(1, "Required"), last_name: z.string().optional(),
  email: z.string().email("Enter a valid email"), password: z.string().min(10, "At least 10 characters"),
});

export default function LoginPage() {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [err, setErr] = useState("");
  const { login } = useAuth();
  const router = useRouter();
  const l = useForm<z.infer<typeof loginSchema>>({ resolver: zodResolver(loginSchema) });
  const r = useForm<z.infer<typeof regSchema>>({ resolver: zodResolver(regSchema) });

  const doLogin = l.handleSubmit(async (v) => {
    setErr("");
    try { await login(v.email, v.password); const me = await api<any>("/auth/me"); router.replace(me.role === "client" ? "/portal" : "/dashboard"); }
    catch (e: any) { setErr(e.message); }
  });
  const doRegister = r.handleSubmit(async (v) => {
    setErr("");
    try { const t = await api<{ access_token: string }>("/auth/register", { body: v }); setToken(t.access_token); window.location.href = "/dashboard"; }
    catch (e: any) { setErr(e.message); }
  });

  return (
    <div className="grid min-h-screen place-items-center bg-bg p-4">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex items-center justify-center gap-2"><span className="grid h-9 w-9 place-items-center rounded-md bg-primary font-bold text-white">iC</span><span className="text-[22px] font-semibold">IntelliCRM</span></div>
        <div className="card p-6">
          <h2 className="mb-4">{mode === "login" ? "Sign in to your account" : "Create your organization"}</h2>
          {mode === "login" ? (
            <form onSubmit={doLogin} className="space-y-4" noValidate>
              <Field label="Email" required error={l.formState.errors.email?.message}><input className="input" type="email" autoComplete="username" {...l.register("email")} /></Field>
              <Field label="Password" required error={l.formState.errors.password?.message}><input className="input" type="password" autoComplete="current-password" {...l.register("password")} /></Field>
              {err && <p className="text-danger" role="alert">{err}</p>}
              <button className="btn btn-primary w-full" disabled={l.formState.isSubmitting}>{l.formState.isSubmitting ? "Signing in..." : "Sign in"}</button>
            </form>
          ) : (
            <form onSubmit={doRegister} className="space-y-3" noValidate>
              <Field label="Organization name" required error={r.formState.errors.organization_name?.message}><input className="input" {...r.register("organization_name")} /></Field>
              <div className="grid grid-cols-2 gap-3">
                <Field label="First name" required error={r.formState.errors.first_name?.message}><input className="input" {...r.register("first_name")} /></Field>
                <Field label="Last name"><input className="input" {...r.register("last_name")} /></Field>
              </div>
              <Field label="Email" required error={r.formState.errors.email?.message}><input className="input" type="email" {...r.register("email")} /></Field>
              <Field label="Password" required error={r.formState.errors.password?.message} hint="At least 10 characters"><input className="input" type="password" autoComplete="new-password" {...r.register("password")} /></Field>
              {err && <p className="text-danger" role="alert">{err}</p>}
              <button className="btn btn-primary w-full" disabled={r.formState.isSubmitting}>Create organization</button>
            </form>
          )}
          <button className="mt-4 w-full text-center text-small text-primary" onClick={() => { setMode(mode === "login" ? "register" : "login"); setErr(""); }}>
            {mode === "login" ? "New organization? Create an account" : "Already have an account? Sign in"}
          </button>
        </div>
        <p className="mt-4 text-center text-small text-ink-2">Demo: owner@acme-demo.example / Demo@12345 (after seeding)</p>
      </div>
    </div>
  );
}
