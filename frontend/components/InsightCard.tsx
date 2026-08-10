import { AlertTriangle, Flame, Info, MinusCircle, TrendingDown, TrendingUp, Waves } from "lucide-react";
import type { Insight } from "@/lib/api";
import { Sparkline } from "./Sparkline";

const SEVERITY: Record<
  Insight["severity"],
  { label: string; icon: typeof Info; chip: string; ring: string; dot: string }
> = {
  info: {
    label: "Info",
    icon: Info,
    chip: "border-border text-muted bg-panel",
    ring: "ring-border",
    dot: "bg-muted",
  },
  warn: {
    label: "Warn",
    icon: AlertTriangle,
    chip: "border-warn/40 text-warn bg-warn/5",
    ring: "ring-warn/20",
    dot: "bg-warn",
  },
  critical: {
    label: "Critical",
    icon: Flame,
    chip: "border-critical/50 text-critical bg-critical/5",
    ring: "ring-critical/20",
    dot: "bg-critical",
  },
};

const PATTERN: Record<string, { label: string; icon: typeof Info }> = {
  spike: { label: "Spike", icon: TrendingUp },
  drop: { label: "Drop", icon: TrendingDown },
  plateau: { label: "Plateau", icon: MinusCircle },
  volatility: { label: "Volatility", icon: Waves },
};

function fmtPct(n: number) {
  const sign = n >= 0 ? "+" : "";
  return `${sign}${(n * 100).toFixed(1)}%`;
}

export function InsightCard({ insight, index = 0 }: { insight: Insight; index?: number }) {
  const ev = insight.evidence_json;
  const sev = SEVERITY[insight.severity];
  const pat = PATTERN[ev.pattern] ?? { label: ev.pattern, icon: Info };
  const SevIcon = sev.icon;
  const PatIcon = pat.icon;
  const topSegments = (ev.segments ?? []).slice(0, 3);
  const trend: "up" | "down" | "neutral" =
    ev.pattern === "spike" ? "up" : ev.pattern === "drop" ? "down" : "neutral";

  return (
    <article
      style={{ animationDelay: `${index * 60}ms` }}
      className={`group relative rounded-2xl border border-border bg-grad-panel shadow-card overflow-hidden animate-fade-in transition hover:border-border-strong hover:shadow-glow`}
    >
      {/* severity rail */}
      <span className={`absolute left-0 top-0 h-full w-[3px] ${sev.dot}`} />

      <div className="p-5">
        <header className="flex items-start justify-between gap-4 mb-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2 mb-2 flex-wrap">
              <span
                className={`inline-flex items-center gap-1 text-[10px] uppercase tracking-[0.08em] px-2 py-0.5 rounded-full border ${sev.chip}`}
              >
                <SevIcon className="h-3 w-3" /> {sev.label}
              </span>
              <span className="inline-flex items-center gap-1 text-[10px] uppercase tracking-[0.08em] px-2 py-0.5 rounded-full border border-border text-muted bg-panel">
                <PatIcon className="h-3 w-3" /> {pat.label}
              </span>
              <span className="text-[11px] text-muted font-mono truncate">{insight.metric_name}</span>
            </div>
            <h3 className="text-[15px] font-semibold text-text leading-snug tracking-tight">
              {insight.headline}
            </h3>
          </div>
          <div className="shrink-0 text-right">
            <div className="font-mono tabular-nums text-sm text-text">
              {fmtPct(ev.delta_pct)}
            </div>
            <div className="font-mono text-[10px] text-muted">z {ev.z_score.toFixed(2)}</div>
          </div>
        </header>

        <p className="text-[13.5px] text-text/85 leading-relaxed mb-4">{insight.summary}</p>

        <div className="mb-4 -mx-1">
          <Sparkline metricId={insight.metric_id} trend={trend} />
        </div>

        {topSegments.length > 0 && (
          <div className="mb-4">
            <div className="text-[10px] uppercase tracking-[0.08em] text-muted mb-2">
              Top contributing segments
            </div>
            <ul className="space-y-1.5">
              {topSegments.map((s) => {
                const pct = Math.min(100, Math.abs(s.contribution) * 100);
                const positive = s.contribution >= 0;
                return (
                  <li key={`${s.dimension}-${s.value}`} className="text-[13px]">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-text/85">
                        <span className="text-muted">{s.dimension}:</span> {s.value}
                      </span>
                      <span
                        className={`font-mono tabular-nums ${
                          positive ? "text-accent" : "text-ok"
                        }`}
                      >
                        {fmtPct(s.contribution)}
                      </span>
                    </div>
                    <div className="h-1 rounded-full bg-elevated overflow-hidden">
                      <div
                        className={`h-full rounded-full ${
                          positive ? "bg-grad-accent" : "bg-ok/70"
                        }`}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </li>
                );
              })}
            </ul>
          </div>
        )}

        {insight.suggested_followup && (
          <footer className="pt-3 border-t border-border text-[12.5px] text-muted-strong leading-relaxed">
            <span className="inline-block text-[10px] uppercase tracking-[0.08em] text-muted mr-2 align-middle">
              Next step
            </span>
            {insight.suggested_followup}
          </footer>
        )}
      </div>
    </article>
  );
}
