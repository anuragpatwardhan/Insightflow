"use client";

import { useMutation } from "@tanstack/react-query";
import { ArrowUp, Bot, ChevronDown, Sparkles, User2, Wrench } from "lucide-react";
import { FormEvent, useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api, type ChatMessage, type ChatTraceItem } from "@/lib/api";
import { LogoMark } from "./Logo";

const SUGGESTIONS = [
  { title: "What should I worry about right now?", hint: "Surfaces critical insights" },
  { title: "Why did ticket resolution time go up?", hint: "Explains a recent change" },
  { title: "Which team had the biggest DAU drop?", hint: "Compares segments" },
  { title: "How is deployment_failures trending?", hint: "Overview + trend" },
];

type Turn = ChatMessage & { trace?: ChatTraceItem[] };

export function ChatPanel() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const mutation = useMutation({
    mutationFn: async (text: string) => {
      const history: ChatMessage[] = turns.map(({ role, content }) => ({ role, content }));
      return api.chat(history, text);
    },
    onSuccess: (res) => {
      setTurns((t) => [...t, { role: "assistant", content: res.answer, trace: res.trace }]);
    },
    onError: (err: Error) => {
      setTurns((t) => [
        ...t,
        { role: "assistant", content: `**Error.** ${err.message}\n\nIs Ollama running and the model pulled?` },
      ]);
    },
  });

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns, mutation.isPending]);

  const send = (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || mutation.isPending) return;
    setTurns((t) => [...t, { role: "user", content: trimmed }]);
    setInput("");
    mutation.mutate(trimmed);
  };

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    send(input);
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send(input);
    }
  };

  return (
    <div className="flex flex-col h-full border-l border-border bg-bg/40">
      <header className="px-5 py-4 border-b border-border flex items-center justify-between bg-surface/40 backdrop-blur-sm">
        <div className="flex items-center gap-2.5">
          <span className="inline-flex h-7 w-7 items-center justify-center rounded-lg bg-grad-accent shadow-glow">
            <Sparkles className="h-4 w-4 text-bg" />
          </span>
          <div>
            <h2 className="text-[13px] font-semibold tracking-tight text-text">Ask InsightFlow</h2>
            <p className="text-[11px] text-muted">Grounded answers · powered by a local model</p>
          </div>
        </div>
        {turns.length > 0 && (
          <button
            onClick={() => setTurns([])}
            className="text-[11px] text-muted hover:text-text border border-border rounded-md px-2 py-1 transition"
          >
            New chat
          </button>
        )}
      </header>

      <div className="flex-1 overflow-y-auto px-5 py-5 space-y-5">
        {turns.length === 0 && <Welcome onPick={send} />}

        {turns.map((t, i) => (
          <Bubble key={i} turn={t} />
        ))}

        {mutation.isPending && <TypingIndicator />}

        <div ref={endRef} />
      </div>

      <form onSubmit={onSubmit} className="border-t border-border p-3 bg-surface/30 backdrop-blur-sm">
        <div className="relative flex items-end gap-2 rounded-2xl border border-border bg-panel focus-within:border-accent/60 focus-within:shadow-glow transition">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Ask about a metric or a recent change…"
            rows={1}
            className="flex-1 bg-transparent resize-none px-4 py-3 text-[13.5px] text-text placeholder:text-muted focus:outline-none max-h-40"
            disabled={mutation.isPending}
          />
          <button
            type="submit"
            disabled={mutation.isPending || !input.trim()}
            aria-label="Send"
            className="m-1.5 inline-flex h-9 w-9 items-center justify-center rounded-xl bg-grad-accent text-bg disabled:opacity-30 disabled:bg-none disabled:bg-elevated disabled:text-muted transition hover:brightness-110"
          >
            <ArrowUp className="h-4 w-4" />
          </button>
        </div>
        <p className="mt-2 text-[10.5px] text-muted/80 px-1">
          Enter to send · Shift+Enter for newline · Answers ground on tool results, numbers are not invented.
        </p>
      </form>
    </div>
  );
}

function Welcome({ onPick }: { onPick: (s: string) => void }) {
  return (
    <div className="animate-fade-in-slow">
      <div className="flex items-center gap-3 mb-4">
        <LogoMark size={36} />
        <div>
          <h3 className="text-[15px] font-semibold tracking-tight">How can I help?</h3>
          <p className="text-[12px] text-muted">Ask a question in plain English. I'll pull the data and explain.</p>
        </div>
      </div>
      <div className="grid sm:grid-cols-2 gap-2">
        {SUGGESTIONS.map((s) => (
          <button
            key={s.title}
            onClick={() => onPick(s.title)}
            className="group text-left p-3 rounded-xl border border-border bg-panel hover:border-accent/40 hover:bg-elevated transition"
          >
            <div className="text-[13px] text-text leading-snug font-medium group-hover:text-accent-strong">
              {s.title}
            </div>
            <div className="text-[11px] text-muted mt-1">{s.hint}</div>
          </button>
        ))}
      </div>
    </div>
  );
}

function Bubble({ turn }: { turn: Turn }) {
  const isUser = turn.role === "user";
  return (
    <div className={`flex gap-3 animate-fade-in ${isUser ? "flex-row-reverse" : "flex-row"}`}>
      <div
        className={`shrink-0 mt-0.5 inline-flex h-7 w-7 items-center justify-center rounded-full border ${
          isUser
            ? "bg-accent/15 border-accent/40 text-accent"
            : "bg-panel border-border text-muted-strong"
        }`}
      >
        {isUser ? <User2 className="h-3.5 w-3.5" /> : <Bot className="h-3.5 w-3.5" />}
      </div>
      <div
        className={`max-w-[82%] rounded-2xl px-4 py-3 text-[13.5px] leading-relaxed border ${
          isUser
            ? "bg-accent/10 border-accent/30 text-text"
            : "bg-panel border-border text-text/95"
        }`}
      >
        <div className="prose-chat">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{turn.content}</ReactMarkdown>
        </div>
        {turn.trace && turn.trace.length > 0 && <TraceDetails trace={turn.trace} />}
      </div>
    </div>
  );
}

function TraceDetails({ trace }: { trace: ChatTraceItem[] }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="mt-3 pt-2.5 border-t border-border/70">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1.5 text-[11px] text-muted hover:text-accent transition"
      >
        <Wrench className="h-3 w-3" />
        <span>Tools used · {trace.length}</span>
        <ChevronDown className={`h-3 w-3 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <ul className="mt-2 space-y-1.5">
          {trace.map((t, i) => (
            <li key={i} className="font-mono text-[11px] flex items-center gap-2">
              <span className="text-accent">{t.tool}</span>
              <span className="text-muted">·</span>
              <span className="text-muted">{t.result_summary}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function TypingIndicator() {
  return (
    <div className="flex gap-3 animate-fade-in">
      <div className="shrink-0 mt-0.5 inline-flex h-7 w-7 items-center justify-center rounded-full border bg-panel border-border">
        <Bot className="h-3.5 w-3.5 text-muted-strong" />
      </div>
      <div className="rounded-2xl px-4 py-3 bg-panel border border-border">
        <div className="flex items-center gap-1.5">
          <span className="h-1.5 w-1.5 rounded-full bg-muted-strong animate-pulse-dot" style={{ animationDelay: "0ms" }} />
          <span className="h-1.5 w-1.5 rounded-full bg-muted-strong animate-pulse-dot" style={{ animationDelay: "180ms" }} />
          <span className="h-1.5 w-1.5 rounded-full bg-muted-strong animate-pulse-dot" style={{ animationDelay: "360ms" }} />
        </div>
      </div>
    </div>
  );
}
