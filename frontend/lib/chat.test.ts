import { describe, expect, it } from "vitest";
import { errorTurn, historyFor, isReplyCurrent, type Turn } from "./chat";

/**
 * Both of these fail quietly. A polluted history still produces an answer, just
 * a worse one, and a stale reply still renders, just under a question the user
 * has already cleared.
 */

const user = (content: string): Turn => ({ role: "user", content });
const assistant = (content: string, trace?: Turn["trace"]): Turn => ({
  role: "assistant",
  content,
  trace,
});

describe("historyFor", () => {
  it("keeps an ordinary exchange in order", () => {
    const turns = [user("why did signups drop?"), assistant("EU traffic fell 12%.")];
    expect(historyFor(turns)).toEqual([
      { role: "user", content: "why did signups drop?" },
      { role: "assistant", content: "EU traffic fell 12%." },
    ]);
  });

  it("drops a failed turn", () => {
    // The bug this replaced. An error bubble is written by this client, so
    // replaying it teaches the model that an error message is the sort of
    // thing it says.
    const turns = [user("why?"), errorTurn("503 model unavailable")];
    expect(historyFor(turns)).toEqual([{ role: "user", content: "why?" }]);
  });

  it("keeps the question that failed, so a retry has context", () => {
    const turns = [user("why?"), errorTurn("boom")];
    expect(historyFor(turns)[0].content).toBe("why?");
  });

  it("drops every failed turn, not just the last", () => {
    const turns = [
      user("first"),
      errorTurn("boom"),
      user("second"),
      errorTurn("boom again"),
      user("third"),
    ];
    expect(historyFor(turns).map((m) => m.content)).toEqual(["first", "second", "third"]);
  });

  it("keeps real answers that happen to mention an error", () => {
    // Filtering on the flag rather than on the text, so a genuine answer about
    // errors survives.
    const turns = [user("what broke?"), assistant("**Error.** rates doubled on Tuesday.")];
    expect(historyFor(turns)).toHaveLength(2);
  });

  it("strips the tool trace", () => {
    // The trace is the model's own scratch work. Replayed as message content it
    // reads like an observation made this turn.
    const turns = [
      assistant("Signups fell.", [
        { tool: "query_metric", args: { metric_id: 1 }, result_summary: "45 points" },
      ]),
    ];
    expect(historyFor(turns)).toEqual([{ role: "assistant", content: "Signups fell." }]);
    expect(Object.keys(historyFor(turns)[0])).toEqual(["role", "content"]);
  });

  it("strips the failed flag from what goes over the wire", () => {
    const turns = [user("hi")];
    expect(Object.keys(historyFor(turns)[0]).sort()).toEqual(["content", "role"]);
  });

  it("returns nothing for an empty conversation", () => {
    expect(historyFor([])).toEqual([]);
  });

  it("returns nothing when every turn failed", () => {
    expect(historyFor([errorTurn("a"), errorTurn("b")])).toEqual([]);
  });

  it("does not modify the turns it was given", () => {
    const turns = [user("hi"), errorTurn("boom")];
    const before = JSON.parse(JSON.stringify(turns));
    historyFor(turns);
    expect(turns).toEqual(before);
  });
});

describe("errorTurn", () => {
  it("carries the underlying message", () => {
    expect(errorTurn("503 model unavailable").content).toContain("503 model unavailable");
  });

  it("is marked so it never becomes context", () => {
    expect(errorTurn("boom").failed).toBe(true);
  });

  it("renders as an assistant bubble", () => {
    // It belongs on the assistant side visually, which is exactly why the flag
    // is needed to tell it apart from a real answer.
    expect(errorTurn("boom").role).toBe("assistant");
  });

  it("suggests the usual cause", () => {
    expect(errorTurn("boom").content).toContain("Ollama");
  });
});

describe("isReplyCurrent", () => {
  it("accepts a reply from the open conversation", () => {
    expect(isReplyCurrent(3, 3)).toBe(true);
  });

  it("rejects a reply from a conversation that was cleared", () => {
    // "New chat" is reachable while a request is in flight, since the button
    // appears as soon as there is one turn.
    expect(isReplyCurrent(3, 4)).toBe(false);
  });

  it("rejects it however many resets have happened since", () => {
    expect(isReplyCurrent(0, 7)).toBe(false);
  });

  it("accepts the first reply of a fresh session", () => {
    expect(isReplyCurrent(0, 0)).toBe(true);
  });
});
