import { Sparkles } from "lucide-react";
import { API_BASE_URL as API } from "@/lib/api";
import { cleanText } from "@/lib/text";
import { HistoricalPatternsMasterDetail, type HistoricalListEvent, type CategoryStats } from "./HistoricalPatternsMasterDetail";

interface RawEvent {
  id: string; event_title: string; event_date: string; category: string;
  sentiment: string | null; sectors: string[];
  nifty_1w: number | null; nifty_1m: number | null;
  opportunity_score: number | null; risk_score: number | null;
}

async function fetchAll(): Promise<RawEvent[]> {
  try {
    const res = await fetch(`${API}/api/historical/all?limit=200`, { next: { revalidate: 3600 } });
    if (!res.ok) return [];
    const data = await res.json();
    return (data.events ?? []).map((e: RawEvent) => ({ ...e, event_title: cleanText(e.event_title), sectors: e.sectors ?? [] }));
  } catch {
    return [];
  }
}

export async function HistoricalPatternsContent({ headingLevel = "h1" }: { headingLevel?: "h1" | "h2" }) {
  const Heading = headingLevel;
  const raw = await fetchAll();

  const byCategory = new Map<string, RawEvent[]>();
  for (const e of raw) {
    const key = e.category || "General";
    if (!byCategory.has(key)) byCategory.set(key, []);
    byCategory.get(key)!.push(e);
  }

  // Real per-category stats (win rate / avg return / occurrences) power
  // the Pattern Snapshot sidebar for whichever event is selected.
  const categoryStats: CategoryStats[] = [...byCategory.entries()].map(([category, evs]) => {
    const impacts = evs.map(e => e.nifty_1m ?? e.nifty_1w).filter((v): v is number => v != null);
    const avgImpact = impacts.length ? impacts.reduce((a, b) => a + b, 0) / impacts.length : null;
    const successRate = impacts.length ? (impacts.filter(v => v > 0).length / impacts.length) * 100 : null;
    return { category, count: evs.length, avgImpact, successRate };
  });

  const events: HistoricalListEvent[] = raw as HistoricalListEvent[];

  return (
    <main className="mx-auto max-w-[1400px] py-8 pb-16">
      <div className="mb-2 flex items-center gap-2">
        <span className="flex items-center gap-1.5 rounded-full border border-sky-500/25 bg-sky-500/10 px-3 py-1 text-[11px] font-bold text-sky-600 dark:text-sky-300">
          <Sparkles className="h-3 w-3" /> AI VALIDATED
        </span>
      </div>
      <Heading className="text-[28px] font-black leading-tight text-text-primary md:text-[34px]">
        Historical Patterns
      </Heading>
      <p className="mt-3 max-w-[680px] text-[14px] leading-relaxed text-text-secondary">
        Discover how similar events impacted the market in the past so you can make smarter decisions today —
        {" "}{raw.length} real, dated market events with verified Nifty reactions, not AI estimates.
      </p>

      <div className="mt-6">
        <HistoricalPatternsMasterDetail events={events} categoryStats={categoryStats} />
      </div>
    </main>
  );
}
