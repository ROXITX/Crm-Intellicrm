import { date, pct, title } from "@/lib/format";
import { Badge } from "@/components/common/ui";
import type { Prediction } from "@/types/api";

/** Standard explainable-AI panel: what / how likely / why / what to do / which model. Never a bare score. */
export function Explanation({ p, label = "Probability", empty }: { p: Prediction | null | undefined; label?: string; empty?: string }) {
  if (!p) return <p className="text-ink-2">{empty || "No prediction available yet."}</p>;
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3">
        {p.risk_level && <Badge value={p.risk_level} label={`${title(p.risk_level)} risk`} />}
        {p.probability != null && <span className="text-[22px] font-semibold">{pct(p.probability)}</span>}
        <span className="text-small text-ink-2">{label}{p.confidence != null && <> · Model confidence {pct(p.confidence)}</>}</span>
      </div>
      {p.summary && <p>{p.summary}</p>}
      {p.factors.length > 0 && (
        <div><p className="mb-1 text-small font-medium text-ink-2">Why</p>
          <ul className="space-y-1">{p.factors.map((f, i) => (
            <li key={i} className="flex items-start gap-2"><span className={f.direction === "decreases" ? "text-success" : "text-danger"} aria-hidden>{f.direction === "decreases" ? "−" : "+"}</span><span>{f.label}{f.impact != null && <span className="ml-1 text-small text-ink-2">({f.impact > 0 ? "+" : ""}{(f.impact * 100).toFixed(0)} pts)</span>}</span></li>
          ))}</ul></div>
      )}
      {p.business_rules.length > 0 && <ul className="text-small text-ink-2">{p.business_rules.map((r, i) => <li key={i}>Rule: {r}</li>)}</ul>}
      {p.recommended_actions.length > 0 && (
        <div className="rounded-ctl border border-line bg-muted p-3"><p className="mb-1 text-small font-medium text-ink-2">Recommended action</p>
          <ul className="list-disc space-y-0.5 pl-4">{p.recommended_actions.map((a, i) => <li key={i}>{a}</li>)}</ul></div>
      )}
      <p className="text-[11.5px] text-ink-2">{p.model_name} v{p.model_version} · {date(p.created_at)} · {p.disclaimer}</p>
    </div>
  );
}
