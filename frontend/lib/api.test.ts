import { afterEach, describe, expect, it, vi } from "vitest";
import { api, API_BASE } from "./api";

/**
 * The client is small, and what it gets wrong is quiet: a filter silently
 * dropped from a query string returns the unfiltered list, which looks like a
 * working request that found everything.
 */

type Call = [string, RequestInit?];

/** Stub fetch and hand back the calls it received. */
function stubFetch(body: unknown, { ok = true, status = 200, text = "" } = {}) {
  const mock = vi.fn(async (_url: string, _init?: RequestInit) => ({
    ok,
    status,
    statusText: ok ? "OK" : "Internal Server Error",
    json: async () => body,
    text: async () => text,
  }));
  vi.stubGlobal("fetch", mock);
  return mock;
}

const urlOf = (mock: { mock: { calls: Call[] } }) => mock.mock.calls[0][0];

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("insights", () => {
  it("asks for the whole list when given no filters", async () => {
    const mock = stubFetch([]);
    await api.insights();
    expect(urlOf(mock)).toBe(`${API_BASE}/insights`);
  });

  it("omits the question mark entirely when there is no query", async () => {
    // A trailing "?" would still work, but it turns up in logs and cache keys.
    const mock = stubFetch([]);
    await api.insights({});
    expect(urlOf(mock)).not.toContain("?");
  });

  it("passes a severity filter through", async () => {
    const mock = stubFetch([]);
    await api.insights({ severity: "critical" });
    expect(urlOf(mock)).toBe(`${API_BASE}/insights?severity=critical`);
  });

  it("passes a metric filter through", async () => {
    const mock = stubFetch([]);
    await api.insights({ metric_id: 7 });
    expect(urlOf(mock)).toBe(`${API_BASE}/insights?metric_id=7`);
  });

  it("combines both filters", async () => {
    const mock = stubFetch([]);
    await api.insights({ severity: "warn", metric_id: 3 });
    const url = String(urlOf(mock));
    expect(url).toContain("severity=warn");
    expect(url).toContain("metric_id=3");
  });

  it("returns the parsed body", async () => {
    stubFetch([{ id: 1, headline: "Signups fell" }]);
    expect(await api.insights()).toHaveLength(1);
  });

  it("throws with the status when the server rejects the request", async () => {
    stubFetch(null, { ok: false, status: 422 });
    await expect(api.insights()).rejects.toThrow(/422/);
  });

  it("throws rather than returning an empty list on failure", async () => {
    // Returning [] here would render "no insights" — indistinguishable from a
    // healthy account with nothing to report.
    stubFetch([], { ok: false, status: 500 });
    await expect(api.insights()).rejects.toThrow();
  });
});

describe("metrics", () => {
  it("requests the metrics list", async () => {
    const mock = stubFetch([]);
    await api.metrics();
    expect(urlOf(mock)).toBe(`${API_BASE}/metrics`);
  });

  it("propagates a 404", async () => {
    stubFetch(null, { ok: false, status: 404 });
    await expect(api.metrics()).rejects.toThrow(/404/);
  });
});

describe("chat", () => {
  it("posts the message with its history", async () => {
    const mock = stubFetch({ answer: "ok", trace: [] });
    const history = [{ role: "user" as const, content: "hi" }];
    await api.chat(history, "why did signups drop?");

    const [url, init] = mock.mock.calls[0] as Call;
    expect(url).toBe(`${API_BASE}/chat`);
    expect(init?.method).toBe("POST");
    expect(JSON.parse(String(init?.body))).toEqual({
      history,
      message: "why did signups drop?",
    });
  });

  it("declares JSON, since the endpoint parses a body", async () => {
    const mock = stubFetch({ answer: "ok", trace: [] });
    await api.chat([], "hello");
    const [, init] = mock.mock.calls[0] as Call;
    expect((init?.headers as Record<string, string>)["Content-Type"]).toBe("application/json");
  });

  it("sends an empty history on the first turn", async () => {
    const mock = stubFetch({ answer: "ok", trace: [] });
    await api.chat([], "first question");
    expect(JSON.parse(String((mock.mock.calls[0] as Call)[1]?.body)).history).toEqual([]);
  });

  it("returns the answer and the tool trace", async () => {
    stubFetch({
      answer: "Signups fell 12% in the EU segment.",
      trace: [{ tool: "query_metric", args: { metric_id: 1 }, result_summary: "45 points" }],
    });
    const result = await api.chat([], "why?");
    expect(result.answer).toContain("12%");
    expect(result.trace[0].tool).toBe("query_metric");
  });

  it("surfaces the server's own message, not just the status", async () => {
    // The agent fails in ways worth reading — a tool budget exhausted, a metric
    // that does not exist — and the status code alone says none of it.
    stubFetch(null, { ok: false, status: 500, text: "agent exceeded its tool budget" });
    await expect(api.chat([], "why?")).rejects.toThrow(/agent exceeded its tool budget/);
  });

  it("includes the status alongside the message", async () => {
    stubFetch(null, { ok: false, status: 503, text: "model unavailable" });
    await expect(api.chat([], "why?")).rejects.toThrow(/503/);
  });
});

describe("base URL", () => {
  it("prefixes every request, so a deployed build reaches its own API", async () => {
    const mock = stubFetch([]);
    await api.metrics();
    expect(String(urlOf(mock)).startsWith(API_BASE)).toBe(true);
  });

  it("falls back to localhost when nothing is configured", async () => {
    // The variable is inlined at build time, so this documents the default a
    // developer gets with no .env rather than reading it back from the process.
    expect(API_BASE).toBe(process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000");
  });
});
