"use client";

import { useQuery } from "@tanstack/react-query";
import { API_BASE } from "@/lib/api";

type Point = { ts: string; value: number };

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

  if (!data || data.length < 2) {
    return <div className="skeleton animate-shimmer" style={{ width, height }} />;
  }

  const values = data.map((d) => d.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const stepX = width / (values.length - 1);

  const points = values.map((v, i) => {
    const x = i * stepX;
    const y = height - ((v - min) / span) * (height - 4) - 2;
    return [x, y] as const;
  });

  const path = points.map(([x, y], i) => (i === 0 ? `M${x},${y}` : `L${x},${y}`)).join(" ");
  const areaPath = `${path} L${width},${height} L0,${height} Z`;

  const stroke =
    trend === "up" ? "#ef6b6b" : trend === "down" ? "#5cd9a3" : "#7aa2ff";
  const gid = `spark-${metricId}-${trend}`;

  const [lastX, lastY] = points[points.length - 1];

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
      <circle cx={lastX} cy={lastY} r="2.4" fill={stroke} />
      <circle cx={lastX} cy={lastY} r="5" fill={stroke} opacity="0.18" />
    </svg>
  );
}
