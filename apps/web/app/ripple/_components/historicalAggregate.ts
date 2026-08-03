import { API_BASE_URL as API } from "@/lib/api";
import { cleanText } from "@/lib/text";

// Shared aggregation logic for the Historical Winners / Historical Losers
// tabs — both need the SAME real underlying data (historical_winners /
// historical_losers are per-event fields, confirmed real and distinct via
// app/historical/[id]/page.tsx lines 33-34), just sorted in opposite
// directions, so the fetch+aggregate step lives once here.

export interface HistoricalWinner {
  symbol: string; name: string;
  return_1d?: number | null; return_1w?: number | null; return_1m?: number | null;
  reason: string;
}
interface HistoricalDetail {
  id: string; event_title: string; event_date: string; category: string;
  historical_winners: HistoricalWinner[];
  historical_losers: HistoricalWinner[];
}
interface HistoricalListItem { id: string; event_title: string; category: string; }

export interface AggregatedMover {
  symbol: string; name: string; returnPct: number; reason: string;
  eventId: string; eventTitle: string;
}

function bestReturn(w: HistoricalWinner): number {
  return w.return_1w ?? w.return_1m ?? w.return_1d ?? 0;
}

async function fetchEvent(id: string): Promise<HistoricalDetail | null> {
  try {
    const res = await fetch(`${API}/api/historical/${id}`, { next: { revalidate: 3600 } });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

// Bounded sample, not all ~200 events — "General"/auto-captured events are
// consistently thin (no real winner/loser data, confirmed via a live
// sample), so non-"General" categories are tried first to raise the hit
// rate within the fetch budget.
export async function aggregateHistoricalMovers(): Promise<{ winners: AggregatedMover[]; losers: AggregatedMover[] }> {
  const listRes = await fetch(`${API}/api/historical/all?limit=200`, { next: { revalidate: 3600 } }).catch(() => null);
  const list: HistoricalListItem[] = listRes && listRes.ok ? (await listRes.json()).events ?? [] : [];

  const prioritized = [...list].sort((a, b) => {
    const aGeneral = a.category === "General" ? 1 : 0;
    const bGeneral = b.category === "General" ? 1 : 0;
    return aGeneral - bGeneral;
  }).slice(0, 30);

  const details = (await Promise.all(prioritized.map(e => fetchEvent(e.id)))).filter((d): d is HistoricalDetail => d !== null);

  const winners: AggregatedMover[] = [];
  const losers: AggregatedMover[] = [];
  for (const d of details) {
    for (const w of d.historical_winners ?? []) {
      winners.push({ symbol: w.symbol, name: w.name, returnPct: bestReturn(w), reason: cleanText(w.reason), eventId: d.id, eventTitle: cleanText(d.event_title) });
    }
    for (const l of d.historical_losers ?? []) {
      losers.push({ symbol: l.symbol, name: l.name, returnPct: bestReturn(l), reason: cleanText(l.reason), eventId: d.id, eventTitle: cleanText(d.event_title) });
    }
  }

  winners.sort((a, b) => b.returnPct - a.returnPct);
  losers.sort((a, b) => a.returnPct - b.returnPct);

  return { winners: winners.slice(0, 15), losers: losers.slice(0, 15) };
}
