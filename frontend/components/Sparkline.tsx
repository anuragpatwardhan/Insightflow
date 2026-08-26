"use client";

import { useQuery } from "@tanstack/react-query";
import { API_BASE } from "@/lib/api";
import { buildSparkline, type SparklinePoint as Point } from "@/lib/sparkline";

async function fetchSeries(metricId: number, days: number): Promise<Point[]> {
  const r = await fetch(`${API_BASE}/metrics/${metricId}/series?days=${days}`);
  if (!r.ok) throw new Error(`${r.status}`);
  return (await r.json()) as Point[];
}

export function Sparkline({
  metricId,
  days = 45,
  trend = "neutral",
  width = 160,
  height = 44,
}: {
  metricId: number;
  days?: number;
  trend?: "up" | "down" | "neutral";
  width?: number;
  height?: number;
}) {
  const { data } = useQuery({
    queryKey: ["series", metricId, days],
    queryFn: () => fetchSeries(metricId, days),
    staleTime: 60_000,
  });

  const geometry = data ? buildSparkline(data, width, height) : null;
  if (!geometry) {
    return <div className="skeleton animate-shimmer" style={{ width, height }} />;
  }

  const { path, areaPath, last } = geometry;

  const stroke =
    trend === "up" ? "#ef6b6b" : trend === "down" ? "#5cd9a3" : "#7aa2ff";
  const gid = `spark-${metricId}-${trend}`;

  return (
    <svg width={width} height={height} className="overflow-visible" aria-hidden>
      <defs>
        <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={stroke} stopOpacity="0.35" />
          <stop offset="100%" stopColor={stroke} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={areaPath} fill={`url(#${gid})`} />
      <path d={path} stroke={stroke} strokeWidth="1.5" fill="none" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={last.x} cy={last.y} r="2.4" fill={stroke} />
      <circle cx={last.x} cy={last.y} r="5" fill={stroke} opacity="0.18" />
    </svg>
  );
}
