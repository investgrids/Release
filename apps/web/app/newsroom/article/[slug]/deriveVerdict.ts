// Split out of page.tsx (2026-08 fix) — Next.js's App Router type-checks
// page.tsx files against a strict export allowlist (default/metadata/
// generateMetadata/etc.); any other named export fails the generated
// route validator. deriveVerdict needs to be importable from a test file
// on its own, so it lives here instead.

export interface CompanyAffected { name: string; symbol: string | null; impact: "positive" | "negative" | "neutral"; reason?: string; timeframe?: string; }
export interface SectorAffected { name: string; impact?: "positive" | "negative" | "neutral"; magnitude?: "high" | "medium" | "low"; reason?: string; }

const HORIZON_LABEL: Record<string, string> = {
  immediate: "Today", short: "1 Week", weeks: "1 Week", medium: "1 Month", months: "1 Month", long: "Long Term",
};

// AI Investment Verdict — derived entirely from the article's own real,
// AI-generated company/sector impact calls. Never a fabricated buy/sell
// rating: no numeric "score" or "Strong Buy" exists in the data model, so
// none is invented here — the verdict is a real aggregate of real signals.
//
// Companies are the primary signal whenever the article names any —
// sectors are macro/supporting context, not the investment thesis
// driver. Blending both into one undifferentiated pool (the previous
// behavior) let a single, clearly-positive company get diluted or
// outright overridden by unrelated sector-level noise: a real case
// (Zydus USFDA approval, 1 company positive + 5 mixed sectors) produced
// a "Neutral" headline verdict directly above a "Positive" AI Impact row
// for that exact company in the table below it — a visible, user-
// reported self-contradiction on the same page. Sectors are only used
// to derive the stance when the article names no company at all (a pure
// macro/policy piece with nothing else to anchor on).
export function deriveVerdict(companies: CompanyAffected[], sectors: SectorAffected[]) {
  const companyPool = companies.filter(x => x.impact);
  const pool = companyPool.length > 0 ? companyPool : sectors.filter(x => x.impact);
  const counts = { positive: 0, negative: 0, neutral: 0 };
  pool.forEach(x => { counts[x.impact as keyof typeof counts]++; });
  const total = pool.length;
  let stance: "Bullish" | "Bearish" | "Neutral" | "Mixed" = "Neutral";
  if (total > 0) {
    if (counts.positive >= total * 0.55 && counts.positive > counts.negative) stance = "Bullish";
    else if (counts.negative >= total * 0.55 && counts.negative > counts.positive) stance = "Bearish";
    else if (counts.positive > 0 && counts.negative > 0) stance = "Mixed";
  }
  const focus = companies.find(c => c.impact === (stance === "Bearish" ? "negative" : "positive"))?.name
    ?? sectors.find(s => s.impact === (stance === "Bearish" ? "negative" : "positive"))?.name
    ?? null;
  const horizons = new Set<string>();
  companies.forEach(c => c.timeframe && horizons.add(HORIZON_LABEL[c.timeframe] ?? c.timeframe));
  return { stance, focus, horizons: [...horizons] };
}
