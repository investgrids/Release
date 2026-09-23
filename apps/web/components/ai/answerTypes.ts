// The typed AI Answer registry boundary (2026-09-21 AI Answer UI work).
// A raw SearchResult is transformed ONCE, here, into a closed
// discriminated union — every intent-specific layout downstream reads
// the typed AIAnswer, never the raw API shape directly. This is also
// the one place a genuinely unrecognized or schema-invalid response
// fails closed into a DegradedAnswer, with telemetry, rather than
// falling through to a generic "successful answer" render.
import type { SearchResult, UIMode, ConfidenceContract } from "@/app/ai-search/AISearchClient";
import type { EvidenceRow, EvidenceCoverageSummary } from "./AIAnswerShell";
import type { AEV2Response, AEV2CompaniesAffected, AEV2SwitchAnalysis, AEV2Comparison, AEV2EventImpact, AEV2MarketPulse } from "./aev2Types";

interface AnswerBase {
  query: string;
  raw: SearchResult;
  sourceCount: number;
  confidence: ConfidenceContract | null;
  evidenceCoverage: EvidenceCoverageSummary | null;
  evidenceRows: EvidenceRow[];
}

// FactualLookupAnswer is sourced straight from the plain SearchResult
// (no AEV2 payload involved — factual lookups never needed the
// restructured presenter). PolicyMacroImpactAnswer/SectorThemeAnswer
// remain LIVE-WIRE placeholders: both modes stay in UNSUPPORTED_UI_MODES
// below (their own data-feasibility audits closed BLOCKED), so
// toAIAnswer() never actually constructs one — they exist only so
// IntentLayout's exhaustive switch has a real type to match against.
//
// The other five implemented modes (2026-09-22, activation-wiring
// commit) are NOT declared here — their real types are
// AEV2DirectCompanyAnswer/AEV2SwitchAnswer/AEV2ComparisonAnswer/
// AEV2EventImpactAnswer/AEV2MarketPulseAnswer, defined further down this
// file next to their own gate functions, and referenced directly in the
// AIAnswer union below.
export interface FactualLookupAnswer extends AnswerBase { ui_mode: "factual_lookup"; }
export interface PolicyMacroImpactAnswer extends AnswerBase { ui_mode: "policy_macro_impact"; }
export interface SectorThemeAnswer extends AnswerBase { ui_mode: "sector_theme_research"; }

// Not a backend ui_mode — a frontend-only discriminant covering every
// way an answer can fail to reach a real layout: a genuine synthesis
// failure (synthesis_incomplete), a ui_mode the backend didn't send or
// this frontend doesn't recognize (schema drift), or a ui_mode that IS
// valid and successfully answered but has no dedicated layout built yet
// (`reason: "not_yet_implemented"` — distinct from the other two, since
// nothing actually failed; see UnsupportedAnswerLayout for why it must
// not reuse this state's "analysis unavailable" copy).
export interface DegradedAnswer extends AnswerBase {
  ui_mode: "degraded";
  reason:
    | "synthesis_incomplete"
    | "unknown_ui_mode"
    | "not_yet_implemented"
    // direct_company_research's minimum eligibility contract (2026-09-22)
    // — a rejection here means "don't render this layout at all," never
    // "render it with a gap." See toDirectCompanyResearchAEV2Answer.
    | "ineligible_no_entity"
    | "ineligible_multi_entity"
    | "ineligible_entity_mismatch"
    | "ineligible_unvalidated_conclusion"
    | "ineligible_no_company_evidence"
    // switch_analysis's minimum eligibility contract (2026-09-22) —
    // reuses ineligible_entity_mismatch/ineligible_unvalidated_conclusion
    // above rather than inventing switch-specific duplicates of the
    // same two concepts.
    | "ineligible_wrong_entity_count"
    | "ineligible_not_switch_shaped"
    | "ineligible_no_comparable_dimension"
    // comparison's minimum eligibility contract (2026-09-22) — reuses
    // ineligible_wrong_entity_count/ineligible_entity_mismatch/
    // ineligible_unvalidated_conclusion/ineligible_no_company_evidence/
    // ineligible_no_comparable_dimension above; only the "backend never
    // built one" case needs its own reason, distinct from switch's.
    | "ineligible_not_comparison_shaped"
    // event_impact's minimum eligibility contract (2026-09-22) — reuses
    // ineligible_unvalidated_conclusion/ineligible_no_company_evidence/
    // ineligible_entity_mismatch above (a cited Event ID that doesn't
    // match what V3 itself resolved is the same "AEV2 attributed
    // something V3 didn't resolve" shape as a company mismatch);
    // "exactly one Event resolves" and "backend never assembled one"
    // are each different enough from every existing reason to need
    // their own.
    | "ineligible_wrong_event_count"
    | "ineligible_not_event_shaped"
    // 2026-09-22, intent-coverage audit — a real, named ui_mode this
    // codebase recognizes but cannot yet honestly answer (as opposed to
    // "not_yet_implemented," which means a real contract/layout already
    // exists locally and just isn't wired to HTTP yet). sourceUiMode
    // carries WHICH one, and UNSUPPORTED_MODE_INFO below supplies its
    // own specific message — never collapsed into "Analysis
    // unavailable" the way the generic reasons above are.
    | "unsupported_mode"
    // 2026-09-22, activation-wiring commit — a real, IMPLEMENTED mode
    // (its layout and gate function both exist and are wired here) whose
    // backend answer_experience_v2 payload simply wasn't attached to
    // this response. This is the ALWAYS case in today's production
    // traffic (AEV2_BUILD_COMPLETE stays False — see aev2/mode.py — so
    // should_return_to_client never lets the field reach a real HTTP
    // caller, in any AI_SEARCH_AEV2_MODE), but it's also a genuine
    // future runtime state once the latch flips: assemble_aev2 itself
    // can return None on an internal assembly failure. Distinct from
    // every "ineligible_*" reason below, which all fire INSIDE a gate
    // function once a payload IS present but doesn't meet that mode's
    // eligibility contract — this fires before a gate ever runs.
    | "aev2_unavailable";
  degradedNotice?: string;
  sourceUiMode?: string;
}

// 2026-09-22, activation-wiring commit — the five AEV2-sourced answer
// types (declared further down this file, next to their own gate
// functions) join the union in place of their former AnswerBase
// placeholders. Forward references are safe: these are `interface`
// declarations, and the gate functions below are `function`
// declarations — both hoisted, so toAIAnswer() (above them, textually)
// can already reference every one of these names.
export type AIAnswer =
  | AEV2DirectCompanyAnswer
  | AEV2SwitchAnswer
  | AEV2ComparisonAnswer
  | FactualLookupAnswer
  | PolicyMacroImpactAnswer
  | AEV2MarketPulseAnswer
  | AEV2EventImpactAnswer
  | SectorThemeAnswer
  | DegradedAnswer;

const KNOWN_UI_MODES: readonly UIMode[] = [
  "direct_company_research", "switch_analysis", "company_comparison",
  "factual_lookup", "policy_macro_impact", "market_pulse",
  "event_impact", "sector_theme_research",
  "technical_timing", "company_discovery", "portfolio_review",
  "earnings_preview", "multi_company_comparison",
];

// The six implemented modes (2026-09-22, activation-wiring commit —
// grew from just factual_lookup once the six-mode integration audit
// confirmed all five AEV2-sourced gate functions + layouts were
// fixture-tested and consistent). Any valid ui_mode NOT in this set
// still resolves to a typed answer above, but toAIAnswer degrades it
// ("not_yet_implemented" or "unsupported_mode") before IntentLayout ever
// sees it. Being IMPLEMENTED here is independent of whether a real
// response ever actually reaches these layouts in production — that's
// still gated separately by AEV2_BUILD_COMPLETE (backend) and
// NEXT_PUBLIC_AI_ANSWER_SHELL (frontend), both of which stay off. See
// "aev2_unavailable" above for the honest degrade every one of the five
// AEV2-sourced modes falls into today, every time, until the backend
// latch flips.
export const IMPLEMENTED_UI_MODES: ReadonlySet<UIMode> = new Set([
  "factual_lookup", "direct_company_research", "switch_analysis",
  "company_comparison", "event_impact", "market_pulse",
]);

// ── Explicit recognized-but-unsupported modes (2026-09-22, intent-
// coverage audit). Each is a REAL classification this codebase makes
// but cannot yet honestly answer — distinct from a mode that already
// has a real local contract/layout and is merely unwired from HTTP
// (IMPLEMENTED_UI_MODES/"not_yet_implemented" above). Every one of
// these gets its own specific reason and message; none collapse into
// the generic "Analysis unavailable" copy. policy_macro_impact and
// sector_theme_research were already established as unsupported by the
// respective data-feasibility audits; the other five are this audit's
// own findings (four decision-intent labels that used to silently
// collapse into an incompatible single-company/two-company contract,
// plus multi-company comparison).
export type UnsupportedUIMode =
  | "technical_timing"
  | "company_discovery"
  | "portfolio_review"
  | "earnings_preview"
  | "multi_company_comparison"
  | "policy_macro_impact"
  | "sector_theme_research";

export const UNSUPPORTED_MODE_INFO: Record<UnsupportedUIMode, string> = {
  technical_timing:
    "Technical timing is unavailable because verified price-series and indicator coverage is insufficient.",
  company_discovery:
    "A ranked stock-picks view isn't available yet — it needs its own data audit (candidate universe, sector membership, ranking inputs, and per-company evidence) before it can be built honestly.",
  portfolio_review:
    "MarketRipple doesn't store personal holdings or portfolios today, so this can't be a personalized answer. Check the Portfolio Coverage tool instead.",
  // Status: unsupported_pending_data_foundation (2026-09-22, earnings-
  // preview feasibility audit — promoted from the earlier "pending_data_
  // audit" label now that the audit itself is closed with a BLOCKED
  // verdict: no company-earnings-date calendar and no consensus-estimate
  // source exist anywhere in this codebase, confirmed by tracing real
  // models/services, not assumed. The dormant banking-only XBRL
  // FinancialFact pipeline is a real future input but is not itself
  // sufficient — see project memory for the full Data Foundation list
  // (verified NSE/BSE results calendar, general-company quarterly
  // filings with source URLs + disclosure timestamps, point-in-time
  // snapshots, structured guidance, licensed consensus estimates).
  earnings_preview:
    "A verified earnings date and analyst-estimate data are not available for this company.",
  multi_company_comparison:
    "Comparing three or more companies at once isn't supported yet — it needs its own contract beyond the current two-company comparison.",
  policy_macro_impact:
    "Policy and macro impact analysis isn't available yet — verified transmission-channel and market-reaction data doesn't exist for this today.",
  sector_theme_research:
    "Sector and theme analysis isn't available yet — no verified, non-fabricated sector performance data exists for this today.",
};

const UNSUPPORTED_UI_MODES: ReadonlySet<UIMode> = new Set(
  Object.keys(UNSUPPORTED_MODE_INFO) as UnsupportedUIMode[],
);

export function formatShortDate(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

function buildEvidenceRows(result: SearchResult): EvidenceRow[] {
  const rows: EvidenceRow[] = [];
  for (const n of result.news ?? []) {
    rows.push({ id: `news-${n.id}`, date: formatShortDate(n.published_at), source: n.source || "News", headline: n.headline });
  }
  for (const e of result.related_events ?? []) {
    // 2026-09-22 fix (browser QA content-integrity review): this used to
    // always show `e.category` (a classification like "Macro") in the
    // Source column, mislabeling a category as a source even when the
    // backend's real Event.source field (the actual ingestion adapter,
    // e.g. "nse_announcements" — see retrieval.py's _event_row_to_dict)
    // was available. Real source now takes precedence; only when it's
    // genuinely absent does this fall back to a category-derived label,
    // and that fallback now reads "Macro event" rather than a bare
    // "Macro" so it can't be mistaken for an identifiable outlet.
    rows.push({
      id: `event-${e.id}`, date: formatShortDate(e.date),
      source: e.source || `${e.category || "Market"} event`,
      headline: e.title, href: e.slug ? `/events/${e.slug}` : undefined,
    });
  }
  for (const p of result.policies ?? []) {
    rows.push({ id: `policy-${p.id}`, date: null, source: p.ministry || "Policy", headline: p.title });
  }
  return rows;
}

function buildEvidenceCoverage(result: SearchResult): EvidenceCoverageSummary {
  return {
    newsSourceCount: result.news?.length ?? 0,
    eventSourceCount: result.related_events?.length ?? 0,
    policySourceCount: result.policies?.length ?? 0,
    contradictionFlagged: !!result.validation?.contradiction_flagged,
  };
}

function baseFields(result: SearchResult): AnswerBase {
  return {
    query: result.query,
    raw: result,
    sourceCount: result.answer?.sources_count ?? 0,
    confidence: result.confidence ?? null,
    evidenceCoverage: buildEvidenceCoverage(result),
    evidenceRows: buildEvidenceRows(result),
  };
}

function toDegraded(
  result: SearchResult,
  reason: DegradedAnswer["reason"],
  degradedNotice?: string,
): DegradedAnswer {
  return { ...baseFields(result), ui_mode: "degraded", reason, degradedNotice, sourceUiMode: result.ui_mode };
}

// The one place a raw API response becomes a typed AIAnswer. Every
// caller (the results page, tests, a future preview tool) must go
// through this — never construct an AIAnswer by hand from a SearchResult.
export function toAIAnswer(result: SearchResult): AIAnswer {
  if (result.synthesis_incomplete) {
    return toDegraded(result, "synthesis_incomplete", result.answer?.bottom_line || result.answer?.summary);
  }
  const mode = result.ui_mode;
  if (!mode || !KNOWN_UI_MODES.includes(mode)) {
    if (typeof window !== "undefined") {
      // eslint-disable-next-line no-console
      console.error("ai_answer.unknown_ui_mode", { ui_mode: mode, query: result.query });
    }
    return toDegraded(result, "unknown_ui_mode");
  }
  if (UNSUPPORTED_UI_MODES.has(mode)) {
    return toDegraded(result, "unsupported_mode");
  }
  if (!IMPLEMENTED_UI_MODES.has(mode)) {
    return toDegraded(result, "not_yet_implemented");
  }
  if (mode === "factual_lookup") {
    return { ...baseFields(result), ui_mode: mode };
  }

  // The remaining five implemented modes (2026-09-22, activation-wiring
  // commit) are all AEV2-sourced — dispatched through the exact same
  // strict gate function every fixture-only test already exercises
  // (toDirectCompanyResearchAEV2Answer etc.), never a bespoke live-path
  // reimplementation of their eligibility rules. A missing/null payload
  // degrades honestly rather than throwing: see answer_experience_v2's
  // own doc comment on SearchResult (AISearchClient.tsx) for why this is
  // the ALWAYS case in today's real HTTP traffic, and a real future
  // state (assemble_aev2 can itself return None) once it isn't.
  const aev2 = result.answer_experience_v2;
  if (!aev2) {
    return toDegraded(result, "aev2_unavailable");
  }
  // IMPLEMENTED_UI_MODES already proved `mode` is one of exactly these 6
  // strings (factual_lookup handled above) — TS can't narrow through a
  // Set.has() check, so this switch's exhaustiveness is enforced at
  // runtime by that guard, not by the type system, the same tradeoff as
  // the factual_lookup branch's own return above.
  switch (mode) {
    case "market_pulse":
      return toMarketPulseAEV2Answer(result, aev2 as AEV2MarketPulse);
    case "direct_company_research":
      return toDirectCompanyResearchAEV2Answer(result, aev2 as AEV2Response);
    case "switch_analysis":
      return toSwitchAnalysisAEV2Answer(result, aev2 as AEV2Response);
    case "company_comparison":
      return toComparisonAEV2Answer(result, aev2 as AEV2Response);
    case "event_impact":
      return toEventImpactAEV2Answer(result, aev2 as AEV2Response);
    default:
      // Unreachable given the guards above — fails closed rather than
      // silently returning undefined if it somehow is.
      return toDegraded(result, "unknown_ui_mode");
  }
}

export function assertNever(x: never): never {
  throw new Error(`Unhandled AIAnswer variant: ${JSON.stringify(x)}`);
}

// ══════════════════════════════════════════════════════════════════════
// direct_company_research — sourced from assemble_aev2()'s real output
// ONLY (2026-09-22, owner's explicit sequencing). Deliberately NOT part
// of the AIAnswer union above and NOT reachable from toAIAnswer(): there
// is no live HTTP path to an AEV2Response yet (AEV2_BUILD_COMPLETE stays
// False), so this type, its gate function, and its layout are built and
// tested only against hand-authored fixtures that mirror exactly what
// aev2/assemble.py already produces server-side. Wiring this into
// SearchResults/toAIAnswer is explicitly deferred to a dedicated
// activation commit that also flips the readiness latch — see
// aev2/mode.py's own docstring for that sequencing.
//
// Deliberately carries NO reference to the raw SearchResult or any
// plain-V3 field (investment_verdict, engine_verdict, scenarios,
// top_picks, suitable_for, risk_level, ...) — those concepts don't exist
// anywhere in AEV2Response either (aev2/assemble.py's own docstring:
// "Deliberately absent, by design... verdict, scenarios, suitability,
// and top-pick concepts"), so excluding `raw` here makes it structurally
// impossible, not just conventionally forbidden, for
// DirectCompanyResearchLayout to render any of them.
export interface AEV2DirectCompanyAnswer {
  ui_mode: "direct_company_research";
  query: string;
  resolvedCompany: { symbol: string; name: string };
  aev2: AEV2Response;
}

function flattenCompaniesAffected(ca: AEV2CompaniesAffected): { symbol: string; name: string }[] {
  return [...ca.currently_higher, ...ca.currently_lower, ...ca.omitted_unattributed]
    .map(c => ({ symbol: c.symbol, name: c.name }));
}

// The minimum eligibility contract (2026-09-22) — every check must pass
// before this layout may render at all. A rejection returns the SAME
// universal DegradedAnswer every other mode fails closed into, never a
// bespoke "partial company page." Reads BOTH the plain SearchResult
// (only to confirm how many companies V3 itself resolved — a fact
// AEV2Response alone doesn't carry) and the AEV2Response (for
// everything the rendered layout actually uses) — this dual read lives
// only in this gate function, never in the component itself, which is
// exactly what the "component consumes only AEV2DirectCompanyAnswer"
// tests verify.
export function toDirectCompanyResearchAEV2Answer(
  result: SearchResult,
  aev2: AEV2Response,
): AEV2DirectCompanyAnswer | DegradedAnswer {
  if (result.synthesis_incomplete) {
    return toDegraded(result, "synthesis_incomplete");
  }

  const resolved = (result.companies ?? []).filter(c => !!c.symbol);
  if (resolved.length === 0) {
    return toDegraded(result, "ineligible_no_entity");
  }
  if (resolved.length > 1) {
    return toDegraded(result, "ineligible_multi_entity");
  }

  const attributed = flattenCompaniesAffected(aev2.companies_affected);
  const match = attributed.find(c => c.symbol.toUpperCase() === resolved[0].symbol.toUpperCase());
  if (!match) {
    return toDegraded(result, "ineligible_entity_mismatch");
  }

  // validation_status is the real, backend-emitted claim status
  // (schema.py's build_validated_claim, aev2.2) — no separate frontend
  // trust flag. Closes the blocker the direct-company review flagged:
  // "fixture metadata cannot become a production trust signal."
  if (aev2.direct_conclusion.validation_status !== "validated" || !aev2.direct_conclusion.text) {
    return toDegraded(result, "ineligible_unvalidated_conclusion");
  }
  const catalogIds = new Set(aev2.evidence.map(e => e.id));
  const hasRealAttributedEvidence = aev2.direct_conclusion.evidence_refs.some(ref => catalogIds.has(ref));
  if (!hasRealAttributedEvidence) {
    return toDegraded(result, "ineligible_no_company_evidence");
  }

  return {
    ui_mode: "direct_company_research",
    query: result.query,
    resolvedCompany: match,
    aev2,
  };
}

// ══════════════════════════════════════════════════════════════════════
// switch_analysis — sourced from assemble_aev2()'s switch_analysis field
// ONLY (2026-09-22), same dedicated-type rule as direct_company_research:
// no plain-V3 fields, not part of the AIAnswer union, not reachable from
// toAIAnswer(). Built and tested against fixtures until a dedicated
// activation commit.
//
// Carries the full AEV2Response (needed for the shared evidence catalog
// + confidence, exactly like AEV2DirectCompanyAnswer) plus `switch`, the
// non-null-narrowed switch_analysis object itself — callers never need
// to re-check `aev2.switch_analysis !== null` after the gate already did.
export interface AEV2SwitchAnswer {
  ui_mode: "switch_analysis";
  query: string;
  aev2: AEV2Response;
  switch: AEV2SwitchAnalysis;
}

// The minimum eligibility contract (2026-09-22). Every check must pass;
// a rejection returns the same universal DegradedAnswer every other mode
// fails closed into, never a bespoke partial comparison.
export function toSwitchAnalysisAEV2Answer(
  result: SearchResult,
  aev2: AEV2Response,
): AEV2SwitchAnswer | DegradedAnswer {
  if (result.synthesis_incomplete) {
    return toDegraded(result, "synthesis_incomplete");
  }

  // "exactly two companies resolve"
  const resolved = (result.companies ?? []).filter(c => !!c.symbol);
  if (resolved.length !== 2) {
    return toDegraded(result, "ineligible_wrong_entity_count");
  }

  // The backend never assembled a switch comparison for this query at
  // all (not a comparison specialist call, or holding/target didn't
  // resolve) — a genuinely different state from a low-quality one.
  const sw = aev2.switch_analysis;
  if (!sw) {
    return toDegraded(result, "ineligible_not_switch_shaped");
  }

  // "source/current and destination/alternative roles are preserved" +
  // "both roles agree with the original query" — both roles must be
  // among the SAME two companies V3 itself resolved, and must be two
  // distinct companies.
  const resolvedSymbols = new Set(resolved.map(c => c.symbol.toUpperCase()));
  const currentSymbol = sw.current_company.symbol.toUpperCase();
  const alternativeSymbol = sw.alternative_company.symbol.toUpperCase();
  const rolesPreserved =
    resolvedSymbols.has(currentSymbol) &&
    resolvedSymbols.has(alternativeSymbol) &&
    currentSymbol !== alternativeSymbol;
  if (!rolesPreserved) {
    return toDegraded(result, "ineligible_entity_mismatch");
  }

  // "both companies have attributable evidence" — recent_developments is
  // the dimension that actually represents company-attributed event/
  // announcement evidence; it must be comparable (i.e. BOTH sides have
  // at least one real attributed item), not just present for one side.
  const recentDevelopments = sw.dimensions.find(d => d.key === "recent_developments");
  if (!recentDevelopments || !recentDevelopments.comparable) {
    return toDegraded(result, "ineligible_no_company_evidence");
  }

  // "the comparison conclusion is validated and cited" + "no advisory-
  // language violation exists" — both collapse into validation_status,
  // the same shared claim-status field direct_company_research uses
  // (see aev2Types.ts's AEV2ValidationStatus doc comment for why).
  if (
    sw.direct_comparison.validation_status !== "validated" ||
    !sw.direct_comparison.text ||
    sw.direct_comparison.evidence_refs.length === 0
  ) {
    return toDegraded(result, "ineligible_unvalidated_conclusion");
  }

  // "at least one genuinely comparable dimension exists" — checked
  // independently of the recent_developments check above. With today's
  // fixed 3-dimension set this branch is effectively unreachable (a
  // comparable recent_developments already satisfies it), kept anyway
  // because the two are conceptually distinct spec requirements and a
  // future assembler could add/omit dimensions such that they diverge.
  const hasComparableDimension = sw.dimensions.some(d => d.comparable);
  if (!hasComparableDimension) {
    return toDegraded(result, "ineligible_no_comparable_dimension");
  }

  return { ui_mode: "switch_analysis", query: result.query, aev2, switch: sw };
}

// ══════════════════════════════════════════════════════════════════════
// comparison — sourced from assemble_aev2()'s comparison field ONLY
// (2026-09-22), the neutral, no-holding-relationship counterpart to
// switch_analysis. Same dedicated-type rule: no plain-V3 fields, not
// part of the AIAnswer union, not reachable from toAIAnswer(). Built and
// tested against fixtures until a dedicated activation commit.
export interface AEV2ComparisonAnswer {
  ui_mode: "company_comparison";
  query: string;
  aev2: AEV2Response;
  comparison: AEV2Comparison;
}

// The minimum eligibility contract (2026-09-22). Deliberately mirrors
// toSwitchAnalysisAEV2Answer's structure (same underlying checks, same
// shared reasons where they mean the same thing) — the two gates are
// intentionally similar since comparison IS the neutral case switch
// specializes, not a duplicated implementation.
export function toComparisonAEV2Answer(
  result: SearchResult,
  aev2: AEV2Response,
): AEV2ComparisonAnswer | DegradedAnswer {
  if (result.synthesis_incomplete) {
    return toDegraded(result, "synthesis_incomplete");
  }

  // "exactly two resolved companies"
  const resolved = (result.companies ?? []).filter(c => !!c.symbol);
  if (resolved.length !== 2) {
    return toDegraded(result, "ineligible_wrong_entity_count");
  }

  // The backend never assembled a comparison for this query at all (not
  // a comparison-specialist call, or it didn't resolve exactly 2 real
  // companies) — a genuinely different state from a low-quality one.
  const cmp = aev2.comparison;
  if (!cmp) {
    return toDegraded(result, "ineligible_not_comparison_shaped");
  }

  // "both entities agree with the query" — both sides must be among the
  // SAME two companies V3 itself resolved, and must be two distinct
  // companies. Query order itself is preserved by construction
  // (comparison.py never reorders core.companies) — this check only
  // confirms identity agreement, not order.
  const resolvedSymbols = new Set(resolved.map(c => c.symbol.toUpperCase()));
  const leftSymbol = cmp.left_company.symbol.toUpperCase();
  const rightSymbol = cmp.right_company.symbol.toUpperCase();
  const rolesPreserved =
    resolvedSymbols.has(leftSymbol) && resolvedSymbols.has(rightSymbol) && leftSymbol !== rightSymbol;
  if (!rolesPreserved) {
    return toDegraded(result, "ineligible_entity_mismatch");
  }

  // "both companies have attributable evidence" — recent_developments is
  // the dimension representing company-attributed event/announcement
  // evidence; it must be comparable (both sides have at least one real
  // attributed item).
  const recentDevelopments = cmp.dimensions.find(d => d.key === "recent_developments");
  if (!recentDevelopments || !recentDevelopments.comparable) {
    return toDegraded(result, "ineligible_no_company_evidence");
  }

  // "comparison claim is validated and cited" + "no advisory-language
  // violation exists" — both collapse into validation_status, the same
  // shared claim-status field every AEV2 claim uses.
  if (
    cmp.direct_comparison.validation_status !== "validated" ||
    !cmp.direct_comparison.text ||
    cmp.direct_comparison.evidence_refs.length === 0
  ) {
    return toDegraded(result, "ineligible_unvalidated_conclusion");
  }

  // "at least one dimension is genuinely comparable"
  const hasComparableDimension = cmp.dimensions.some(d => d.comparable);
  if (!hasComparableDimension) {
    return toDegraded(result, "ineligible_no_comparable_dimension");
  }

  return { ui_mode: "company_comparison", query: result.query, aev2, comparison: cmp };
}

// ══════════════════════════════════════════════════════════════════════
// event_impact — sourced from assemble_aev2()'s event_impact field ONLY
// (2026-09-22, narrow contract approved after the policy_macro_impact
// and event_impact read-only audits). Same dedicated-type rule as every
// other AEV2-sourced mode: no plain-V3 fields, not part of the AIAnswer
// union, not reachable from toAIAnswer(). Built and tested against
// fixtures until a dedicated activation commit.
//
// Deliberately carries no transmission-chain, beneficiary/loser,
// monitoring-checklist, Ripple-graph, or Intelligence-Graph-propagation
// field — AEV2EventImpact has none of these (aev2/event_impact.py's own
// "Deliberately absent" note), so EventImpactLayout cannot render any of
// them even by mistake.
export interface AEV2EventImpactAnswer {
  ui_mode: "event_impact";
  query: string;
  aev2: AEV2Response;
  eventImpact: AEV2EventImpact;
}

// The minimum eligibility contract (2026-09-22). Every check must pass;
// a rejection returns the same universal DegradedAnswer every other
// mode fails closed into, never a bespoke partial event page.
export function toEventImpactAEV2Answer(
  result: SearchResult,
  aev2: AEV2Response,
): AEV2EventImpactAnswer | DegradedAnswer {
  if (result.synthesis_incomplete) {
    return toDegraded(result, "synthesis_incomplete");
  }

  // "exactly one Event resolves" — checked directly against what V3
  // itself resolved, independent of whether the backend went on to
  // assemble an event_impact object at all (mirrors comparison/switch's
  // own "wrong entity count" check being separate from "backend never
  // built one").
  const resolvedEvents = result.related_events ?? [];
  if (resolvedEvents.length !== 1) {
    return toDegraded(result, "ineligible_wrong_event_count");
  }

  // The backend never assembled an event_impact object for this query at
  // all (not exactly one Event, or that Event failed the structural
  // gate — no source, no linked companies, missing title/summary/
  // published_at/internal_url) — a genuinely different state from a
  // low-quality one. See aev2/event_impact.py's assemble_event_impact
  // for the full, structural (never ID-blacklist) gate.
  const ei = aev2.event_impact;
  if (!ei) {
    return toDegraded(result, "ineligible_not_event_shaped");
  }

  // "cited Event ID matches the resolved Event" — the event AEV2
  // attributed this to must be the SAME one V3 itself resolved, not a
  // different id the backend somehow cited.
  if (String(resolvedEvents[0].id) !== ei.event.id) {
    return toDegraded(result, "ineligible_entity_mismatch");
  }

  // "linked companies are non-empty" — already guaranteed by the
  // backend gate; checked again here as defense in depth, same
  // precedent as every other AEV2-sourced gate re-verifying a backend
  // invariant rather than trusting it silently.
  if (ei.linked_companies.length === 0) {
    return toDegraded(result, "ineligible_no_company_evidence");
  }

  // "direct conclusion is validated and cited" + "advisory-language
  // safety passes" — both collapse into validation_status, the same
  // shared claim-status field every AEV2 claim uses.
  if (
    ei.direct_conclusion.validation_status !== "validated" ||
    !ei.direct_conclusion.text ||
    ei.direct_conclusion.evidence_refs.length === 0
  ) {
    return toDegraded(result, "ineligible_unvalidated_conclusion");
  }
  const catalogIds = new Set(aev2.evidence.map(e => e.id));
  const hasRealAttributedEvidence = ei.direct_conclusion.evidence_refs.some(ref => catalogIds.has(ref));
  if (!hasRealAttributedEvidence) {
    return toDegraded(result, "ineligible_no_company_evidence");
  }

  return { ui_mode: "event_impact", query: result.query, aev2, eventImpact: ei };
}

// ══════════════════════════════════════════════════════════════════════
// market_pulse — sourced from assemble_aev2()'s OWN, fully separate
// AEV2MarketPulse shape (2026-09-22, canonical-core audit), never
// nested inside AEV2Response the way event_impact/comparison/switch_
// analysis are. Same dedicated-type rule as every other AEV2-sourced
// mode: not part of the AIAnswer union, not reachable from toAIAnswer().
// Built and tested against fixtures until a dedicated activation
// commit — see aev2Types.ts's own AEV2MarketPulse doc comment for why
// this structural difference does not make Market Pulse "a second
// AI-answer pipeline" (it shares the identical finalizer/safety-gate/
// telemetry/cache/AEV2-dispatch/serialization boundary on the backend).
export interface AEV2MarketPulseAnswer {
  ui_mode: "market_pulse";
  query: string;
  aev2: AEV2MarketPulse;
}

// The minimum eligibility contract (2026-09-22). Deliberately thinner
// than the other AEV2-sourced gates: Market Pulse has no company/
// entity-count concept for a SearchResult to disagree with (that
// classification already happened upstream, at the decision-intent
// layer, before this ever runs), and assemble_market_pulse() always
// returns a full object — there is no backend "not applicable" None
// state to check for here the way event_impact/comparison have. The
// structured payload (indices/movers/sectors/drivers/themes/
// opportunity/risk/calendar) is never held back by this gate; only a
// genuine synthesis_incomplete fails closed to the universal
// DegradedAnswer, same as every other mode.
export function toMarketPulseAEV2Answer(
  result: SearchResult,
  aev2: AEV2MarketPulse,
): AEV2MarketPulseAnswer | DegradedAnswer {
  if (result.synthesis_incomplete) {
    return toDegraded(result, "synthesis_incomplete");
  }
  return { ui_mode: "market_pulse", query: result.query, aev2 };
}
