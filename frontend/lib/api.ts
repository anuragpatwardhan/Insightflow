export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export type Severity = "info" | "warn" | "critical";

export type Insight = {
  id: number;
  metric_id: number;
  metric_name: string | null;
  headline: string;
  summary: string;
  evidence_json: {
    pattern: string;
    delta: number;
    delta_pct: number;
    z_score: number;
    significance: number;
    window_days: number;
    segments: { dimension: string; value: string; contribution: number }[];
  };
  suggested_followup: string | null;
  severity: Severity;
  created_at: string;
};

export type Metric = {
  id: number;
  name: string;
  owner: string;
  unit: string | null;
  direction: string;
  description: string | null;
};

async function getJSON<T>(path: string): Promise<T> {
  const r = await fetch(`${API_BASE}${path}`);
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return (await r.json()) as T;
}

export type ChatMessage = { role: "user" | "assistant"; content: string };

export type ChatTraceItem = { tool: string; args: Record<string, unknown>; result_summary: string };

export type ChatResponse = { answer: string; trace: ChatTraceItem[] };

export const api = {
  insights: (params: { severity?: Severity; metric_id?: number } = {}) => {
    const q = new URLSearchParams();
    if (params.severity) q.set("severity", params.severity);
    if (params.metric_id) q.set("metric_id", String(params.metric_id));
    const qs = q.toString();
    return getJSON<Insight[]>(`/insights${qs ? `?${qs}` : ""}`);
  },
  metrics: () => getJSON<Metric[]>("/metrics"),
  chat: async (history: ChatMessage[], message: string): Promise<ChatResponse> => {
    const r = await fetch(`${API_BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ history, message }),
    });
    if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
    return (await r.json()) as ChatResponse;
  },
};
