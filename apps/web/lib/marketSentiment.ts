// Mirror of apps/backend/app/services/market_sentiment.py::index_sentiment_score, for the one screen that computes the score
// client-side from /api/indices/. Keep the two in step. null means "no usable data", never a neutral default.
export type IndexQuoteLike = { name?: string; value?: string; pct?: number };

const clamp = (x: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, x));

export function indexSentimentScore(indices: IndexQuoteLike[]): number | null {
  const moves: number[] = [];
  let vixMove: number | null = null;
  for (const q of indices) {
    if (!q || q.value == null || q.value === "" || q.value === "—" || typeof q.pct !== "number") continue;
    if ((q.name ?? "").toUpperCase().includes("VIX")) vixMove = q.pct;
    else moves.push(q.pct);
  }
  if (moves.length === 0) return null;
  const mean = moves.reduce((a, b) => a + b, 0) / moves.length;
  let score = 50 + clamp(mean / 1.5, -1, 1) * 35;
  if (vixMove !== null) score -= clamp(vixMove / 10, -1, 1) * 5;
  return Math.round(clamp(score, 20, 90));
}
