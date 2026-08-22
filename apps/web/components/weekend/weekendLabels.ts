/**
 * Shared label/symbol/color mapping for Weekend Intelligence's backend
 * semantic states. Every Weekend component must go through these
 * functions rather than re-deriving its own label — this is what keeps
 * "mixed" from silently becoming "bullish" somewhere and what satisfies
 * brief §26 (never communicate direction by color alone: every mapping
 * below pairs a color with a real symbol/word).
 */
import type { CompanyState, RiskSeverity, SectorDirection, WeekendBias, WeekendRisk, WeekendSectorRef } from "@/types/weekendIntelligence";

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

export interface SectorBreakdown {
  counts: { positive: number; negative: number; neutral: number; mixed: number };
  /** Highest-score positive-direction sector names, real backend `score`
   * ranking only — empty when none are positive (never invented). */
  leading: string[];
  /** Lowest-score negative-direction sector names — empty when none are
   * negative, which is the common/good case, not an error to paper over. */
  lagging: string[];
}

/**
 * Pure derivation over the real top_sectors array (no new backend field,
 * no free-text reason — WeekendSectorRef has none, see WeekendSectors.tsx's
 * own docstring) — used by the homepage's Overall Outlook card to answer
 * "which sectors, specifically" without fabricating a reason string.
 */
export function sectorBreakdown(sectors: WeekendSectorRef[]): SectorBreakdown {
  const counts = { positive: 0, negative: 0, neutral: 0, mixed: 0 };
  for (const s of sectors) counts[s.direction] += 1;

  const byScoreDesc = [...sectors].sort((a, b) => b.score - a.score);
  const leading = byScoreDesc.filter((s) => s.direction === "positive").slice(0, 2).map((s) => s.sector);
  const lagging = [...byScoreDesc].reverse().filter((s) => s.direction === "negative").slice(0, 2).map((s) => s.sector);

  return { counts, leading, lagging };
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

/**
 * "Tomorrow" is only ever the real next trading day Monday-Thursday —
 * Friday's "tomorrow" is Saturday (not a trading day), and the weekend's
 * "tomorrow" is Sunday/Monday itself, so both need the same explicit
 * "Monday" framing rather than the generic word. IST-based (market days
 * are IST, not the viewer's local timezone) — same explicit
 * `timeZone: "Asia/Kolkata"` conversion already used by PreMarketTab's
 * useCountdown for the identical Fri/Sat/Sun check, centralized here so
 * every "tomorrow"-framed label (After Market's Watchlist and Opening
 * Prediction, and any future one) reads off the same rule.
 */
export function nextTradingDayLabel(now: Date = new Date()): "Monday" | "Tomorrow" {
  const ist = new Date(now.toLocaleString("en-US", { timeZone: "Asia/Kolkata" }));
  const dow = ist.getDay(); // 0=Sun, 5=Fri, 6=Sat
  return dow === 5 || dow === 6 || dow === 0 ? "Monday" : "Tomorrow";
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

const MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** "2026-08-15" -> "15 Aug 2026" — same plain Y-M-D parsing convention as
 * weekdayNameFromISODate (no Date() timezone ambiguity), used everywhere a
 * short absolute date is shown (hero subtitle, metadata strip). */
export function formatDateShort(dateStr: string | null | undefined): string {
  if (!dateStr) return "Unknown";
  const parts = dateStr.split("-").map(Number);
  if (parts.length !== 3 || parts.some((n) => Number.isNaN(n))) return dateStr;
  const [y, m, d] = parts;
  if (!MONTH_ABBR[m - 1]) return dateStr;
  return `${d} ${MONTH_ABBR[m - 1]} ${y}`;
}

/** ISO timestamp -> "3:45 PM IST", explicit Asia/Kolkata timezone (safe
 * regardless of server runtime timezone, unlike formatDateShort's plain
 * component parsing — this one needs a real instant-to-wall-clock
 * conversion, which Intl's explicit timeZone option provides). */
export function formatTimeIST(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const ms = Date.parse(iso);
  if (Number.isNaN(ms)) return null;
  try {
    return `${new Intl.DateTimeFormat("en-IN", {
      hour: "numeric", minute: "2-digit", hour12: true, timeZone: "Asia/Kolkata",
    }).format(ms)} IST`;
  } catch {
    return null;
  }
}

/** ISO timestamp -> "16 Aug 2026", in Asia/Kolkata — the datetime
 * counterpart to formatDateShort (which only accepts a bare YYYY-MM-DD
 * date, not a full ISO instant with a time/offset component). */
export function formatDateFromISO(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const ms = Date.parse(iso);
  if (Number.isNaN(ms)) return null;
  try {
    return new Intl.DateTimeFormat("en-IN", {
      day: "numeric", month: "short", year: "numeric", timeZone: "Asia/Kolkata",
    }).format(ms);
  } catch {
    return null;
  }
}

/** "Baseline (Market Close)" metadata-strip value — last_trading_date is
 * the real backend field naming which session's close the snapshot is
 * anchored to; 3:30 PM IST is NSE's fixed, universal close time (not
 * derived per-snapshot, but a real unchanging market fact, same class of
 * constant as "Asia/Kolkata" itself). */
export function baselineLabel(lastTradingDate: string | null | undefined): string {
  if (!lastTradingDate) return "Unavailable";
  return `${formatDateShort(lastTradingDate)}, 3:30 PM IST`;
}

/** "Data Window" metadata-strip value — real elapsed hours between NSE's
 * fixed 3:30 PM IST close on last_trading_date and this snapshot's actual
 * generated_at, both real fields. 15:30 IST = 10:00 UTC, so the close
 * instant is constructed directly in UTC — safe duration arithmetic
 * regardless of server runtime timezone (only display formatting needs
 * the explicit Asia/Kolkata handling formatTimeIST uses). */
export function dataWindowLabel(lastTradingDate: string | null | undefined, generatedAt: string | null | undefined): string {
  if (!lastTradingDate || !generatedAt) return "Unavailable";
  const closeUtcMs = Date.parse(`${lastTradingDate}T10:00:00Z`);
  const generatedMs = Date.parse(generatedAt);
  if (Number.isNaN(closeUtcMs) || Number.isNaN(generatedMs)) return "Unavailable";
  const hours = Math.round((generatedMs - closeUtcMs) / 3_600_000);
  if (hours <= 0) return "Unavailable";
  return `~${hours} hour${hours === 1 ? "" : "s"}`;
}

export interface EvidenceQuality {
  label: "Good" | "Fair" | "Limited";
  description: string;
  tone: "positive" | "neutral" | "muted";
}

/** Evidence Quality — not a real backend field (checked: no such field
 * exists in WeekendIntelligenceSnapshotDTO). Rather than fabricate a
 * verdict, this derives one deterministically from fields the backend
 * DOES send: `status` (already the backend's own honest ok/degraded/
 * insufficient_evidence read of this run) and `confidence_warnings`
 * (already-synthesized, real caveats — high severity means something
 * concrete is actually wrong, not just present). Every word in the
 * description traces to a real count, never an invented adjective. */
export function evidenceQualityFor(snapshot: {
  status: string;
  confidence_warnings: { severity: string }[];
  evidence_summary: { total: number; by_source_type: Record<string, number> };
}): EvidenceQuality {
  const warningCount = snapshot.confidence_warnings.length;
  const hasHighSeverityWarning = snapshot.confidence_warnings.some((w) => w.severity === "high");
  const sourceTypeCount = Object.keys(snapshot.evidence_summary.by_source_type).length;

  let label: EvidenceQuality["label"] = "Good";
  if (snapshot.status === "degraded" || hasHighSeverityWarning) label = "Fair";
  if (snapshot.evidence_summary.total === 0) label = "Limited";

  const sourceText = sourceTypeCount > 0
    ? `${sourceTypeCount} source type${sourceTypeCount === 1 ? "" : "s"}`
    : "no sources yet";
  const warningText = warningCount === 0
    ? "no confidence caveats"
    : `${warningCount} confidence caveat${warningCount === 1 ? "" : "s"}`;

  return {
    label,
    description: `${sourceText}, ${warningText}`,
    tone: label === "Good" ? "positive" : label === "Fair" ? "neutral" : "muted",
  };
}

/**
 * Plain-English confidence tier from the real production_confidence
 * percentage — the same thresholds summaryTemplate already used inline,
 * extracted here so the metric card and the summary sentence never
 * silently drift onto different tier boundaries. No new number, just a
 * word for the one already shown.
 */
export function confidenceTierLabel(productionConfidence: number): "High" | "Moderate" | "Low" {
  if (productionConfidence >= 70) return "High";
  if (productionConfidence >= 45) return "Moderate";
  return "Low";
}

/**
 * "Weekend Intelligence Summary" — brief §15: if the backend does not
 * provide a summary, build one from a deterministic template over
 * already-present structured fields ONLY, never a new client-side AI
 * call. Every clause below reads a real field (overall_bias, the two
 * highest-evidence top_sectors, production_confidence,
 * baseline_available, status) — no free text is read or generated.
 * Returns null when there isn't enough real signal to say anything
 * (mirrors every other section's "render nothing over rendering a
 * hollow card" convention).
 */
export function summaryTemplate(snapshot: {
  overall_bias: string;
  top_sectors: { sector: string; direction: string }[];
  production_confidence: number;
  baseline_available: boolean;
  status: string;
}): string | null {
  if (snapshot.top_sectors.length === 0) return null;

  const sentences: string[] = [`Weekend signals remain ${biasLabel(snapshot.overall_bias).toLowerCase()}.`];

  const [a, b] = snapshot.top_sectors;
  if (a && b && sectorDirectionStyle(a.direction).label !== sectorDirectionStyle(b.direction).label) {
    sentences.push(
      `${a.sector} shows ${sectorDirectionStyle(a.direction).label.toLowerCase()} evidence while `
      + `${b.sector} is ${sectorDirectionStyle(b.direction).label.toLowerCase()}.`,
    );
  } else if (a) {
    sentences.push(
      `${a.sector} carries the most evidence this weekend, trending ${sectorDirectionStyle(a.direction).label.toLowerCase()}.`,
    );
  }

  const confidenceWord = confidenceTierLabel(snapshot.production_confidence).toLowerCase();
  const reasonSuffix = !snapshot.baseline_available
    ? " because the last trading session's closing baseline is unavailable"
    : snapshot.status === "degraded" ? " due to limited evidence this cycle" : "";
  sentences.push(`Confidence is ${confidenceWord}${reasonSuffix}.`);

  return sentences.join(" ");
}

const _SEVERITY_RANK: Record<string, number> = { high: 2, medium: 1, low: 0 };

/**
 * Key Risks presentation dedup (owner correction, 2026-08-15) — PURE
 * frontend deduplication over the real market_risks array, no backend
 * change. Every real risk_type the backend actually produces
 * (synthesize_market_risks) is "conflicting_evidence" for BOTH
 * sector-level ("finance: conflicting...") and company-level
 * ("BAJFINANCE: conflicting...") entries — when a sector-level risk of
 * a given type exists, its company-level entries of the SAME type are
 * dropped, since the sector-level one already communicates the issue at
 * the level a user cares about (the owner's own example: one Finance
 * risk instead of BAJFINANCE + LICHSGFIN + HDFCBANK separately). If no
 * sector-level risk of that type exists, the company-level ones are
 * kept as-is — nothing is fabricated or invented, only reordered/
 * filtered from the real array.
 */
export function dedupeMarketRisks(risks: WeekendRisk[]): WeekendRisk[] {
  const sectorTypesPresent = new Set(
    risks.filter((r) => r.related_sectors.length > 0).map((r) => r.risk_type),
  );
  const deduped = risks.filter((r) => {
    const isCompanyOnly = r.related_companies.length > 0 && r.related_sectors.length === 0;
    return !(isCompanyOnly && sectorTypesPresent.has(r.risk_type));
  });
  return [...deduped].sort((a, b) => _SEVERITY_RANK[b.severity] - _SEVERITY_RANK[a.severity]);
}

/**
 * Confidence Warnings presentation simplification (owner correction,
 * 2026-08-15) — PURE frontend transform over the real confidence_
 * warnings array, no backend change. Maps each real, known risk_type
 * (stale_or_missing_baseline / source_concentration /
 * weak_historical_analogue / insufficient_evidence / source_unavailable
 * — the complete real set synthesize_confidence_warnings produces) to
 * plain copy with no backend terminology (clusters/source_type/
 * synthesis) and no raw counts. Per-company source_concentration
 * entries (e.g. "BAJFINANCE: thesis rests on a single evidence source
 * type despite 22 clusters") are collapsed into ONE generic line rather
 * than one per company — the owner's own example. Any risk_type this
 * function doesn't recognize falls back to the real description
 * verbatim rather than silently dropping it.
 */
export function simplifyConfidenceWarnings(warnings: WeekendRisk[]): WeekendRisk[] {
  const out: WeekendRisk[] = [];
  let companySourceConcentration: WeekendRisk | null = null;

  for (const w of warnings) {
    switch (w.risk_type) {
      case "stale_or_missing_baseline":
        out.push({ ...w, description: "Last-session closing baseline is unavailable" });
        break;
      case "source_concentration":
        if (w.related_companies.length > 0) {
          // Collapse every per-company instance into a single
          // representative entry, keeping the highest severity seen.
          if (!companySourceConcentration) {
            companySourceConcentration = { ...w, description: "Some company signals rely on only one source type", related_companies: [] };
          } else if (_SEVERITY_RANK[w.severity] > _SEVERITY_RANK[companySourceConcentration.severity]) {
            const severity: RiskSeverity = w.severity;
            companySourceConcentration.severity = severity;
          }
        } else {
          out.push({ ...w, description: "Evidence this weekend leans heavily on one source type" });
        }
        break;
      case "weak_historical_analogue":
        out.push({ ...w, description: "No similar historical pattern was found this weekend" });
        break;
      case "insufficient_evidence":
        out.push({ ...w, description: "Evidence volume is limited this cycle" });
        break;
      default:
        // source_unavailable is already plain English from the backend
        // ("Company announcement data was unavailable during this
        // update.") — and any future/unrecognized type falls back to
        // its real description rather than being silently dropped.
        out.push(w);
    }
  }

  if (companySourceConcentration) out.push(companySourceConcentration);
  return out.sort((a, b) => _SEVERITY_RANK[b.severity] - _SEVERITY_RANK[a.severity]);
}
