"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Flame, Inbox, Info, LayoutList, RefreshCw } from "lucide-react";
import { useState } from "react";
import { api, type Severity } from "@/lib/api";
import { InsightCard } from "./InsightCard";
import { FeedSkeleton } from "./Skeletons";

const FILTERS: { label: string; value: Severity | "all"; icon: typeof Info }[] = [
  { label: "All", value: "all", icon: LayoutList },
  { label: "Critical", value: "critical", icon: Flame },
  { label: "Warn", value: "warn", icon: AlertTriangle },
  { label: "Info", value: "info", icon: Info },
];

export function InsightFeed() {
  const [filter, setFilter] = useState<Severity | "all">("all");

  const { data, isLoading, isError, error, refetch, isFetching } = useQuery({
    queryKey: ["insights", filter],
    queryFn: () => api.insights(filter === "all" ? {} : { severity: filter }),
  });

  return (
    <section>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-1.5 flex-wrap">
          {FILTERS.map((f) => {
            const Icon = f.icon;
            const active = filter === f.value;
            return (
              <button
                key={f.value}
                onClick={() => setFilter(f.value)}
                className={`inline-flex items-center gap-1.5 text-[12px] px-2.5 py-1.5 rounded-full border transition ${
                  active
                    ? "border-accent/60 text-accent bg-accent/10 shadow-glow"
                    : "border-border text-muted hover:text-text hover:border-border-strong"
                }`}
              >
                <Icon className="h-3 w-3" />
                {f.label}
              </button>
            );
          })}
        </div>
        <button
          onClick={() => refetch()}
          className="inline-flex items-center gap-1.5 text-[11px] text-muted hover:text-text border border-border rounded-md px-2 py-1.5 transition"
          aria-label="Refresh"
        >
          <RefreshCw className={`h-3 w-3 ${isFetching ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </div>

      {isLoading && <FeedSkeleton count={3} />}

      {isError && (
        <div className="rounded-xl border border-critical/40 bg-critical/5 p-4 text-[13px] text-critical">
          Failed to load insights: {(error as Error).message}. Is the API running on :8000?
        </div>
      )}

      {data && data.length === 0 && (
        <div className="rounded-2xl border border-dashed border-border bg-panel/40 p-8 text-center">
          <Inbox className="h-6 w-6 mx-auto mb-3 text-muted" />
          <div className="text-[13px] text-text mb-1">No insights yet</div>
          <p className="text-[12px] text-muted">
            Run <code className="text-accent font-mono">python scripts/run_analysis.py</code> to populate the feed.
          </p>
        </div>
      )}

      <div className="grid gap-4">
        {data?.map((i, idx) => <InsightCard key={i.id} insight={i} index={idx} />)}
      </div>
    </section>
  );
}
