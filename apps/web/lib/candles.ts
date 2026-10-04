// Chart rows from /api/stocks/{symbol}/chart -> data for a candlestick + volume chart.
// Pure and framework-free so it can be tested without a canvas.

export type ChartRow = {
  label?: string;
  value?: number;
  time?: number | string | null;
  open?: number | null;
  high?: number | null;
  low?: number | null;
  close?: number | null;
  volume?: number | null;
};

export type Candle = { time: number | string; open: number; high: number; low: number; close: number };
export type VolumeBar = { time: number | string; value: number; color: string };

// The exchange runs on IST. Intraday times arrive as UTC epoch seconds, and the chart library prints UTC, so shift
// them by IST's fixed +05:30 offset: the axis then reads exchange time for every viewer.
export const IST_OFFSET_SECONDS = 19800;

const finite = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);

export function toCandleData(rows: ChartRow[], upColor = "#22c55e", downColor = "#f43f5e"): { candles: Candle[]; volumes: VolumeBar[] } {
  const byTime = new Map<number | string, { c: Candle; v: number }>();
  for (const r of rows ?? []) {
    if (r == null || r.time == null || !finite(r.open) || !finite(r.high) || !finite(r.low) || !finite(r.close)) continue;
    const time = typeof r.time === "number" ? r.time + IST_OFFSET_SECONDS : r.time;
    const high = Math.max(r.high, r.open, r.close);
    const low = Math.min(r.low, r.open, r.close);
    byTime.set(time, { c: { time, open: r.open, high, low, close: r.close }, v: finite(r.volume) && r.volume > 0 ? r.volume : 0 });   // a repeated time keeps the last bar
  }
  const ordered = [...byTime.values()].sort((a, b) => (a.c.time < b.c.time ? -1 : a.c.time > b.c.time ? 1 : 0));
  return {
    candles: ordered.map(x => x.c),
    volumes: ordered.filter(x => x.v > 0).map(x => ({ time: x.c.time, value: x.v, color: x.c.close >= x.c.open ? upColor + "66" : downColor + "66" })),
  };
}

// True when the rows can be drawn as candles (older cached responses carried only close).
export const hasCandles = (rows: ChartRow[]): boolean => toCandleData(rows).candles.length > 0;
