export const money = (v: string | number | null | undefined, currency = "INR") =>
  v == null ? "-" : new Intl.NumberFormat("en-IN", { style: "currency", currency, maximumFractionDigits: 0 }).format(Number(v));
export const num = (v: number | string | null | undefined) => (v == null ? "-" : new Intl.NumberFormat("en-IN").format(Number(v)));
export const pct = (v: number | null | undefined, digits = 0) => (v == null ? "-" : `${(v * 100).toFixed(digits)}%`);
export const date = (v: string | null | undefined) => (v ? new Date(v).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" }) : "-");
export const title = (s: string | null | undefined) => (s ? s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()) : "-");
export function ago(v: string | null | undefined) {
  if (!v) return "never";
  const diff = (Date.now() - new Date(v).getTime()) / 1000;
  const future = diff < 0;
  const s = Math.abs(diff);
  const fmt = (txt: string) => (future ? `in ${txt}` : `${txt} ago`);
  if (s < 90) return future ? "in a moment" : "just now";
  if (s < 3600) return fmt(`${Math.floor(s / 60)} min`);
  if (s < 86400) return fmt(`${Math.floor(s / 3600)} h`);
  if (s < 86400 * 30) return fmt(`${Math.floor(s / 86400)} d`);
  return date(v);
}
export const initials = (name: string) => name.split(" ").filter(Boolean).slice(0, 2).map((p) => p[0]?.toUpperCase()).join("");
