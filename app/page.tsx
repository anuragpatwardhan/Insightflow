import { ChatPanel } from "@/components/ChatPanel";
import { Header } from "@/components/Header";
import { InsightFeed } from "@/components/InsightFeed";

export default function Page() {
  return (
    <main className="h-screen flex flex-col">
      <Header />

      <div className="flex-1 grid grid-cols-1 lg:grid-cols-[2fr_3fr] overflow-hidden">
        <section className="overflow-y-auto px-6 lg:px-8 py-6 border-r border-border">
          <div className="max-w-2xl">
            <div className="flex items-baseline justify-between mb-5">
              <div>
                <h2 className="text-[11px] uppercase tracking-[0.12em] text-muted">Insights</h2>
                <p className="text-[18px] font-semibold tracking-tight text-text mt-0.5">
                  Today's signal, ranked
                </p>
              </div>
            </div>
            <InsightFeed />
          </div>
        </section>
        <section className="overflow-hidden">
          <ChatPanel />
        </section>
      </div>
    </main>
  );
}
