// Green / amber / red colouring for headline valuation and quality metrics.
// Green = healthy, amber = middling, red = weak. The direction is per metric:
// a high P/E, P/B or D/E is red, but a high ROE, ROCE, margin or yield is green.
// Bands are broad rules of thumb for Indian listed companies, not sector-
// adjusted; a missing or unparseable value ("—") always stays neutral.

export type MetricKey = "pe" | "pb" | "de_pct" | "roe" | "roce" | "net_margin" | "dividend_yield";

const GOOD = "text-emerald-600 dark:text-emerald-400";
const MID = "text-amber-600 dark:text-amber-400";
const BAD = "text-rose-600 dark:text-rose-400";
export const NEUTRAL = "text-text-primary";

// [greenLimit, amberLimit, higherIsBetter]
const BANDS: Record<MetricKey, [number, number, boolean]> = {
  pe: [20, 40, false],
  pb: [3, 6, false],
  // Yahoo reports debtToEquity as a percentage (10.2 = 0.10x).
  de_pct: [50, 150, false],
  roe: [15, 8, true],
  roce: [15, 8, true],
  net_margin: [15, 5, true],
  dividend_yield: [2, 0.5, true],
};

export function parseMetric(value: string | number | null | undefined): number | null {
  if (value == null) return null;
  if (typeof value === "number") return Number.isFinite(value) ? value : null;
  const cleaned = value.replace(/[₹,%x\s]/gi, "");
  if (!/^-?\d+(\.\d+)?$/.test(cleaned)) return null;
  return Number(cleaned);
}

export function metricTone(key: MetricKey, value: string | number | null | undefined): string {
  const n = parseMetric(value);
  if (n == null) return NEUTRAL;
  // A negative P/E means the company is loss-making, not "cheap".
  if (key === "pe" && n < 0) return BAD;
  const [green, amber, higherIsBetter] = BANDS[key];
  if (higherIsBetter) return n >= green ? GOOD : n >= amber ? MID : BAD;
  return n <= green ? GOOD : n <= amber ? MID : BAD;
}

// Display labels used across the Company page, mapped to their metric.
export const LABEL_METRIC: Record<string, MetricKey> = {
  "P/E (TTM)": "pe", "PE Ratio (TTM)": "pe", "Forward PE": "pe", "P/E": "pe",
  "P/B": "pb", "PB Ratio": "pb",
  "ROE": "roe", "ROCE": "roce",
  "D/E Ratio": "de_pct", "D/E": "de_pct", "Debt/Equity": "de_pct",
  "Margin": "net_margin", "Net margin": "net_margin",
  "Dividend yield": "dividend_yield", "Dividend Yield": "dividend_yield",
};

export function labelTone(label: string, value: string | number | null | undefined): string {
  const key = LABEL_METRIC[label];
  return key ? metricTone(key, value) : NEUTRAL;
}
