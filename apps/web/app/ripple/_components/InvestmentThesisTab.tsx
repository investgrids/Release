import { Target } from "lucide-react";
import { API_BASE_URL as API } from "@/lib/api";
import { cleanText } from "@/lib/text";
import { InvestmentThesisCard } from "@/components/intelligence/InvestmentThesis";

interface RippleFeaturedItem {
  id: string; title: string; summary: string; categories: string[];
}

async function getFeaturedRippleEvents(): Promise<RippleFeaturedItem[]> {
  const res = await fetch(`${API}/api/ripple/featured?limit=4`, { next: { revalidate: 900 } }).catch(() => null);
  if (!res || !res.ok) return [];
  return await res.json();
}

// Reuses the existing InvestmentThesisCard (components/intelligence/
// InvestmentThesis.tsx) exactly as-is — it already self-fetches real,
// per-entity thesis content from /api/thesis/ripple/{id} (confirmed live,
// 200 OK with real generated content), so this tab is real synthesis of
// existing Ripple + AI thesis data, not new fabricated copy.
export async function InvestmentThesisTab() {
  const events = await getFeaturedRippleEvents();

  if (events.length === 0) {
    return <p className="rounded-2xl border border-surface-border/7 bg-surface-card p-8 text-center text-[13px] text-text-muted">No ripple events available to generate a thesis from right now.</p>;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <Target className="h-4 w-4 text-accent-violet" />
        <h2 className="text-[15px] font-bold text-text-primary">Investment Thesis</h2>
      </div>
      <p className="text-[12.5px] text-text-secondary max-w-2xl">
        For each of today's top traced ripple effects — what the case for (or against) it actually is, synthesized from the event, its cascading impact, and historical precedent.
      </p>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {events.map(ev => (
          <InvestmentThesisCard
            key={ev.id}
            entityType="ripple"
            entityId={ev.id}
            entityTitle={cleanText(ev.title)}
            entityDescription={cleanText(ev.summary)}
            entitySector={ev.categories?.[0]}
          />
        ))}
      </div>
    </div>
  );
}
