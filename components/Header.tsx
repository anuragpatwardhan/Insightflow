import { Activity, Sparkles } from "lucide-react";
import { Logo } from "./Logo";

export function Header() {
  return (
    <header className="relative border-b border-border bg-surface/60 backdrop-blur-xl">
      <div className="absolute inset-x-0 -bottom-px h-px bg-gradient-to-r from-transparent via-accent/30 to-transparent" />
      <div className="px-6 py-3.5 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Logo />
          <span className="hidden md:inline-block h-4 w-px bg-border" />
          <p className="hidden md:block text-xs text-muted">
            Decision intelligence for KPIs · explainable insights, not raw dashboards
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="hidden sm:inline-flex items-center gap-1.5 text-[11px] uppercase tracking-wider text-muted border border-border rounded-full px-2.5 py-1">
            <span className="relative flex h-1.5 w-1.5">
              <span className="absolute inline-flex h-full w-full rounded-full bg-ok opacity-60 animate-ping" />
              <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-ok" />
            </span>
            Live
          </span>
          <span className="inline-flex items-center gap-1.5 text-[11px] uppercase tracking-wider text-muted border border-border rounded-full px-2.5 py-1">
            <Sparkles className="h-3 w-3" />
            v0.1
          </span>
          <span className="hidden lg:inline-flex items-center gap-1.5 text-[11px] uppercase tracking-wider text-muted border border-border rounded-full px-2.5 py-1">
            <Activity className="h-3 w-3" />
            Llama 3.1
          </span>
        </div>
      </div>
    </header>
  );
}
