"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useApi } from "@/hooks/useApi";
import { Field, PageHeader, errMsg } from "@/components/common/ui";
import { useToast } from "@/components/common/toast";

const NOTIF = [["assignment", "Assignments"], ["message", "New messages"], ["ticket_assigned", "Ticket assigned"], ["ticket_escalation", "Ticket escalations"], ["payment", "Payments"], ["invoice", "Invoices"], ["customer_risk", "Customer risk"], ["project_risk", "Project risk"]];

export default function Settings() {
  const { me, can } = useAuth();
  const toast = useToast();
  const [pw, setPw] = useState({ current_password: "", new_password: "" });
  const prefs = useApi<any>("/me/preferences");
  const org = useApi<any>(can("settings.manage") ? "/settings/organization" : null);
  const [orgF, setOrgF] = useState<any>(null);
  const [name, setName] = useState({ first_name: me?.first_name || "", last_name: me?.last_name || "" });
  const np = prefs.data?.notifications || {};
  const togglePref = async (k: string, on: boolean) => { try { await api("/me", { method: "PATCH", body: { notification_preferences: { ...np, [k]: on } } }); prefs.reload(); toast("Preference saved"); } catch (e) { toast(errMsg(e), "err"); } };
  const o = orgF || org.data;
  return (
    <div>
      <PageHeader title={me?.role === "client" ? "Profile" : "Settings"} />
      <div className="grid gap-4 lg:grid-cols-2">
        <section className="card space-y-3 p-4"><h2>Profile</h2><p className="text-small text-ink-2">{me?.email} · {me?.role}</p>
          <form className="space-y-3" onSubmit={async (e) => { e.preventDefault(); try { await api("/me", { method: "PATCH", body: name }); toast("Profile saved"); } catch (er) { toast(errMsg(er), "err"); } }}>
            <div className="grid grid-cols-2 gap-3"><Field label="First name"><input className="input" value={name.first_name} onChange={(e) => setName({ ...name, first_name: e.target.value })} /></Field><Field label="Last name"><input className="input" value={name.last_name} onChange={(e) => setName({ ...name, last_name: e.target.value })} /></Field></div><button className="btn btn-primary">Save profile</button></form></section>
        <section className="card space-y-3 p-4"><h2>Change password</h2>
          <form className="space-y-3" onSubmit={async (e) => { e.preventDefault(); try { await api("/me/password", { body: pw }); toast("Password changed - please sign in again"); setTimeout(() => (window.location.href = "/login"), 1200); } catch (er) { toast(errMsg(er), "err"); } }}>
            <Field label="Current password" required><input className="input" type="password" autoComplete="current-password" required value={pw.current_password} onChange={(e) => setPw({ ...pw, current_password: e.target.value })} /></Field>
            <Field label="New password" required hint="At least 10 characters"><input className="input" type="password" autoComplete="new-password" minLength={10} required value={pw.new_password} onChange={(e) => setPw({ ...pw, new_password: e.target.value })} /></Field><button className="btn btn-primary">Change password</button></form></section>
        <section className="card p-4"><h2 className="mb-3">Notification preferences</h2><ul className="space-y-2">{NOTIF.map(([k, l]) => <li key={k}><label className="flex items-center gap-2"><input type="checkbox" checked={np[k] !== false} onChange={(e) => togglePref(k, e.target.checked)} /> {l}</label></li>)}</ul></section>
        {can("settings.manage") && o && <section className="card space-y-3 p-4"><h2>Organization</h2>
          <form className="space-y-3" onSubmit={async (e) => { e.preventDefault(); try { await api("/settings/organization", { method: "PATCH", body: { name: o.name, email: o.email || null, phone: o.phone || null } }); toast("Organization saved"); org.reload(); } catch (er) { toast(errMsg(er), "err"); } }}>
            <Field label="Name" required><input className="input" required value={o.name || ""} onChange={(e) => setOrgF({ ...o, name: e.target.value })} /></Field>
            <div className="grid grid-cols-2 gap-3"><Field label="Email"><input className="input" type="email" value={o.email || ""} onChange={(e) => setOrgF({ ...o, email: e.target.value })} /></Field><Field label="Phone"><input className="input" value={o.phone || ""} onChange={(e) => setOrgF({ ...o, phone: e.target.value })} /></Field></div><button className="btn btn-primary">Save organization</button></form></section>}
      </div>
    </div>
  );
}
