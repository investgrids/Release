/**
 * TypeScript types for the Weekend Intelligence read API
 * (GET /api/intelligence/weekend/current, /history).
 *
 * Fields mirror the backend response exactly (see
 * apps/backend/app/api/weekend_intelligence.py::_snapshot_response and
 * the resolved opportunities/historical_analogues attached alongside
 * it) — no fields are added here that the backend does not provide, and
 * no field is renamed. Backend is the source of truth for intelligence;
 * this file only describes its shape for the frontend.
 */

export type WeekendStatus = "ok" | "degraded" | "insufficient_evidence";

export type WeekendBias =
  | "strong_positive"
  | "positive"
  | "neutral"
  | "negative"
  | "strong_negative"
  | "mixed";

export type SectorDirection = "positive" | "negative" | "mixed" | "neutral";

export type CompanyState =
  | "high_conviction_watch"
  | "positive_watch"
  | "monitor"
  | "mixed"
  | "risk_watch";

export type RiskSeverity = "low" | "medium" | "high";

export interface WeekendSectorRef {
  sector: string;
  score: number; // 0-1 — the backend's own per-sector confidence, NOT production_confidence
  direction: SectorDirection;
  evidence_count: number;
}

export interface WeekendCompanyEvidenceRef {
  source_type: string;
  source_id: string;
}

export interface WeekendCompanyRef {
  symbol: string;
  state: CompanyState;
  confidence: number; // 0-1
  evidence_count: number;
  evidence_item_refs: WeekendCompanyEvidenceRef[];
}

export interface WeekendRisk {
  description: string;
  risk_type: string;
  severity: RiskSeverity;
  evidence_refs: WeekendCompanyEvidenceRef[];
  related_sectors: string[];
  related_companies: string[];
}

export interface WeekendNewSinceCloseItem {
  source_type: string;
  source_id: string;
  title: string;
  direction: SectorDirection | string;
  sectors: string[];
  companies: string[];
}

export interface WeekendChangeSincePrior {
  type: "new" | "strengthened" | "weakened" | "state_changed";
  entity_type: "sector" | "company";
  entity_id: string;
  direction: string | null;
  strength: string | null;
  reason: string;
  evidence_refs: WeekendCompanyEvidenceRef[];
}

export interface WeekendEvidenceSummary {
  total: number;
  by_source_type: Record<string, number>;
}

export interface WeekendOpportunity {
  id: number;
  title: string;
  sectors: string[];
  risk_level: string;
  opportunity_score: number;
  confidence: number;
}

export interface WeekendHistoricalAnalogue {
  id: string;
  event_title: string;
  event_date: string | null;
  category: string | null;
  key_lesson: string | null;
  nifty_1d: number | null;
}

export interface WeekendConfidenceComponents {
  raw: Record<string, number>;
  weights: Record<string, number>;
  weighted_contributions: Record<string, number>;
}

/** The real shape of a successful GET /current response (available: true). */
export interface WeekendIntelligenceSnapshotDTO {
  available: true;
  target_trading_date: string;
  last_trading_date: string;
  generated_at: string | null;
  checkpoint_label: string | null;
  version: number;
  status: WeekendStatus;
  baseline_available: boolean;
  overall_bias: WeekendBias;
  production_confidence: number; // 0-100
  confidence_components: WeekendConfidenceComponents | null;
  top_sectors: WeekendSectorRef[];
  top_companies: WeekendCompanyRef[];
  market_risks: WeekendRisk[];
  confidence_warnings: WeekendRisk[];
  new_since_close_count: number;
  new_since_close: WeekendNewSinceCloseItem[];
  changes_since_prior: WeekendChangeSincePrior[];
  evidence_summary: WeekendEvidenceSummary;
  opportunities: WeekendOpportunity[];
  historical_analogues: WeekendHistoricalAnalogue[];
}

/** available: false — no current snapshot exists yet (an honest, expected state). */
export interface WeekendIntelligenceUnavailableDTO {
  available: false;
  target_trading_date?: string;
  error?: string;
}

export type WeekendIntelligenceResponse =
  | WeekendIntelligenceSnapshotDTO
  | WeekendIntelligenceUnavailableDTO;

export interface WeekendHistoryVersion {
  version: number;
  checkpoint_label: string | null;
  generated_at: string | null;
  status: WeekendStatus;
  overall_bias: WeekendBias;
  production_confidence: number;
  is_current: boolean;
}

export interface WeekendHistoryResponse {
  target_trading_date: string;
  versions: WeekendHistoryVersion[];
  error?: string;
}
