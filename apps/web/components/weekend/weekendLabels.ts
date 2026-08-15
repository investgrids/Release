/**
 * Shared label/symbol/color mapping for Weekend Intelligence's backend
 * semantic states. Every Weekend component must go through these
 * functions rather than re-deriving its own label — this is what keeps
 * "mixed" from silently becoming "bullish" somewhere and what satisfies
 * brief §26 (never communicate direction by color alone: every mapping
 * below pairs a color with a real symbol/word).
 */
import type { CompanyState, RiskSeverity, SectorDirection, WeekendBias } from "@/types/weekendIntelligence";

export interface DirectionStyle {
  label: string;
  symbol: string; // ↑ / ↔ / ↓ / — — never rely on color alone (brief §26)
  textClass: string;
  chipClass: string;
}

const SECTOR_DIRECTION: Record<SectorDirection, DirectionStyle> = {
  positive: { label: "Positive", symbol: "↑", textClass: "text-emerald-400", chipClass: "border-emerald-500/25 bg-emerald-500/10 text-emerald-400" },
  negative: { label: "Negative", symbol: "↓", textClass: "text-rose-400", chipClass: "border-rose-500/25 bg-rose-500/10 text-rose-400" },
  mixed: { label: "Mixed", symbol: "↔", textClass: "text-amber-400", chipClass: "border-amber-500/25 bg-amber-500/10 text-amber-400" },
  neutral: { label: "Neutral", symbol: "—", textClass: "text-text-muted", chipClass: "border-surface-border/25 bg-surface-border/10 text-text-muted" },
};

export function sectorDirectionStyle(direction: string): DirectionStyle {
  return SECTOR_DIRECTION[direction as SectorDirection] ?? SECTOR_DIRECTION.neutral;
}

const COMPANY_STATE: Record<CompanyState, DirectionStyle> = {
  high_conviction_watch: { label: "High Conviction Watch", symbol: "↑", textClass: "text-emerald-400", chipClass: "border-emerald-500/25 bg-emerald-500/10 text-emerald-400" },
  positive_watch: { label: "Positive Watch", symbol: "↑", textClass: "text-emerald-400", chipClass: "border-emerald-500/25 bg-emerald-500/10 text-emerald-400" },
  monitor: { label: "Monitor", symbol: "—", textClass: "text-text-muted", chipClass: "border-surface-border/25 bg-surface-border/10 text-text-muted" },
  mixed: { label: "Mixed", symbol: "↔", textClass: "text-amber-400", chipClass: "border-amber-500/25 bg-amber-500/10 text-amber-400" },
  risk_watch: { label: "Risk Watch", symbol: "↓", textClass: "text-rose-400", chipClass: "border-rose-500/25 bg-rose-500/10 text-rose-400" },
};

export function companyStateStyle(state: string): DirectionStyle {
  return COMPANY_STATE[state as CompanyState] ?? COMPANY_STATE.monitor;
}

const BIAS_LABEL: Record<WeekendBias, string> = {
  strong_positive: "Strong Positive",
  positive: "Positive",
  neutral: "Neutral",
  negative: "Negative",
  strong_negative: "Strong Negative",
  mixed: "Mixed",
};

export function biasLabel(bias: string): string {
  return BIAS_LABEL[bias as WeekendBias] ?? bias;
}

export function biasStyle(bias: string): DirectionStyle {
  if (bias === "strong_positive" || bias === "positive") return SECTOR_DIRECTION.positive;
  if (bias === "strong_negative" || bias === "negative") return SECTOR_DIRECTION.negative;
  if (bias === "mixed") return SECTOR_DIRECTION.mixed;
  return SECTOR_DIRECTION.neutral;
}

const SEVERITY: Record<RiskSeverity, { label: string; textClass: string }> = {
  high: { label: "High", textClass: "text-rose-400" },
  medium: { label: "Medium", textClass: "text-amber-400" },
  low: { label: "Low", textClass: "text-text-muted" },
};

export function severityStyle(severity: string): { label: string; textClass: string } {
  return SEVERITY[severity as RiskSeverity] ?? SEVERITY.medium;
}

/** "2026-08-17" -> "Monday" — parsed as plain date components (no Date()
 * timezone ambiguity from a bare YYYY-MM-DD string) since this is only
 * used for display, never for date arithmetic. */
export function weekdayNameFromISODate(dateStr: string | undefined | null): string {
  if (!dateStr) return "the next session";
  const parts = dateStr.split("-").map(Number);
  if (parts.length !== 3 || parts.some((n) => Number.isNaN(n))) return "the next session";
  const [y, m, d] = parts;
  const date = new Date(y, m - 1, d);
  return date.toLocaleDateString("en-US", { weekday: "long" });
}

/** Human-friendly relative/absolute label for an ISO timestamp — checkpoint
 * label from the backend is preferred when present (e.g. "Sunday 18:00 IST");
 * this is only a fallback formatter, never a re-derivation of session logic. */
export function formatUpdatedAt(iso: string | null, checkpointLabel: string | null): string {
  if (checkpointLabel) return checkpointLabel;
  if (!iso) return "Unknown";
  try {
    return new Date(iso).toLocaleString("en-IN", {
      weekday: "long", hour: "numeric", minute: "2-digit", hour12: true, timeZone: "Asia/Kolkata",
    });
  } catch {
    return iso;
  }
}
