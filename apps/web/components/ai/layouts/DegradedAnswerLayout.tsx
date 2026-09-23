"use client";

// The universal degraded state's registry entry (2026-09-21 AI Answer UI
// work). AIAnswerShell already owns the actual degraded rendering
// (synthesisIncomplete gate) — this component's only job is supplying
// the right chrome/copy for the 3 distinct ways an answer can land here,
// so a genuine synthesis failure is never shown with the same "analysis
// unavailable" framing as a merely-unbuilt layout (that would overstate
// what actually went wrong).
import { AIAnswerShell, type ShellMode } from "../AIAnswerShell";
import type { UIMode } from "@/app/ai-search/AISearchClient";
import type { DegradedAnswer, UnsupportedUIMode } from "../answerTypes";
import { UNSUPPORTED_MODE_INFO } from "../answerTypes";

const NOTICE_BY_REASON: Record<DegradedAnswer["reason"], string> = {
  synthesis_incomplete:
    "The real evidence found is shown below, with no generated conclusion, confidence score, or outlook.",
  unknown_ui_mode:
    "This question's answer type wasn't recognized by this version of AI Search. The real evidence found is shown below.",
  not_yet_implemented:
    "A dedicated view for this kind of question is still being built. The real evidence found is shown below.",
  // direct_company_research's minimum eligibility contract (2026-09-22)
  // — none of these are reachable via live HTTP yet (that layout isn't
  // wired to toAIAnswer), but the reasons are real and exhaustively
  // handled here so DegradedAnswerLayout stays a true universal fallback
  // once it is.
  ineligible_no_entity:
    "This question didn't resolve to a specific company. The real evidence found is shown below.",
  ineligible_multi_entity:
    "This question involves more than one company, which needs a comparison view, not a single-company one. The real evidence found is shown below.",
  ineligible_entity_mismatch:
    "The company this answer was generated for doesn't match the one this question resolved to. The real evidence found is shown below.",
  ineligible_unvalidated_conclusion:
    "The generated conclusion didn't pass the research-language or citation check. The real evidence found is shown below, with no generated conclusion.",
  ineligible_no_company_evidence:
    "No evidence directly attributable to this company was found. The real evidence found is shown below.",
  // switch_analysis's minimum eligibility contract (2026-09-22).
  ineligible_wrong_entity_count:
    "This question doesn't resolve to exactly two companies, which a switch comparison needs. The real evidence found is shown below.",
  ineligible_not_switch_shaped:
    "This question wasn't recognized as a holding-vs-alternative comparison. The real evidence found is shown below.",
  ineligible_no_comparable_dimension:
    "There wasn't enough matching evidence for both companies to build a fair comparison. The real evidence found is shown below.",
  // comparison's minimum eligibility contract (2026-09-22).
  ineligible_not_comparison_shaped:
    "This question wasn't recognized as a side-by-side company comparison. The real evidence found is shown below.",
  // event_impact's minimum eligibility contract (2026-09-22).
  ineligible_wrong_event_count:
    "This question doesn't resolve to exactly one event. The real evidence found is shown below.",
  ineligible_not_event_shaped:
    "This event didn't have the source, company attribution, or other structured fields this view needs. The real evidence found is shown below.",
  // 2026-09-22, intent-coverage audit — a real, named ui_mode this
  // codebase recognizes but cannot yet honestly answer. This generic
  // string is only ever a fallback: the actual notice shown below
  // always prefers UNSUPPORTED_MODE_INFO[answer.sourceUiMode], which
  // carries each mode's own specific reason (see that registry's own
  // doc comment for why none of these collapse into one shared line).
  unsupported_mode:
    "This kind of question isn't supported yet. The real evidence found is shown below.",
  // 2026-09-22, activation-wiring commit — a real, implemented mode
  // whose enhanced payload simply wasn't returned for this response
  // (see answerTypes.ts's own doc comment on this reason for why this
  // is the ALWAYS case in today's production traffic).
  aev2_unavailable:
    "This answer's enhanced view isn't available for this response. The real evidence found is shown below.",
};

// answer_availability-driven copy (2026-09-23, Phase 1.2) — the backend's
// own honest account of WHY synthesis_incomplete is true, replacing the
// evidenceRows.length-only inference below (which could not distinguish
// "retrieval never completed due to a provider/capacity failure" from
// "retrieval completed and genuinely found nothing"). See
// response_finalize.py's _derive_answer_availability for how `state` is
// computed — never inferred client-side.
const AVAILABILITY_BADGE: Record<string, string> = {
  temporarily_unavailable: "TEMPORARILY UNAVAILABLE",
  no_verified_evidence: "NO VERIFIED EVIDENCE",
  limited_evidence: "LIMITED EVIDENCE",
};
const AVAILABILITY_NOTICE: Record<string, string> = {
  temporarily_unavailable: "We couldn't complete evidence retrieval and analysis right now. Please try again later.",
  no_verified_evidence: "No related verified news, events, or policy evidence was found for this query.",
  limited_evidence: "The verified evidence found is shown below, but the full analysis could not be completed.",
};

const KNOWN_UI_MODES = new Set<string>([
  "direct_company_research", "switch_analysis", "company_comparison",
  "factual_lookup", "policy_macro_impact", "market_pulse",
  "event_impact", "sector_theme_research",
  "technical_timing", "company_discovery", "portfolio_review",
  "earnings_preview", "multi_company_comparison",
]);

export function DegradedAnswerLayout({
  answer, onNewSearch, onRefine,
}: {
  answer: DegradedAnswer;
  onNewSearch: () => void;
  onRefine?: () => void;
}) {
  // A real synthesis failure or a genuinely unrecognized ui_mode has
  // nothing honest to label with — everything else here (an unbuilt
  // layout, or direct_company_research's own eligibility rejections)
  // still carries a real, valid ui_mode the backend actually resolved,
  // so the chrome shows its real kind label rather than the generic
  // "Analysis unavailable" one.
  const usesRealChrome = answer.reason !== "synthesis_incomplete" && answer.reason !== "unknown_ui_mode";
  const chromeMode: ShellMode =
    usesRealChrome && answer.sourceUiMode && KNOWN_UI_MODES.has(answer.sourceUiMode)
      ? (answer.sourceUiMode as UIMode)
      : "degraded";

  // Each explicit unsupported mode gets its OWN specific message — never
  // collapsed into the generic "not supported yet" fallback above, which
  // only fires if sourceUiMode is somehow missing or unrecognized.
  //
  // 2026-09-23 fix (real browser QA finding): every NOTICE_BY_REASON
  // string above claims "the real evidence found is shown below" —
  // true when answer.evidenceRows is non-empty, false and misleading
  // when a query genuinely matched zero news/events/policies (a real,
  // common case — e.g. "What is the impact of RBI rate cut on banking
  // stocks?" resolves no company and matches no keyword-searched
  // evidence at all). Fixed for the 3 reasons actually reachable via
  // live HTTP today (synthesis_incomplete, unknown_ui_mode, aev2_
  // unavailable — see this codebase's own invariant test proving every
  // other reason is either an eligibility-gate rejection unreachable
  // until AEV2 activates, or provably unreachable full stop); the
  // remaining reasons keep their static text pending the same fix once
  // they become live-reachable.
  const hasEvidence = answer.evidenceRows.length > 0;
  // Only meaningful for reason === "synthesis_incomplete" — every other
  // DegradedAnswer reason is a frontend-side gate rejection of an
  // otherwise "available" backend response (answer_availability.state
  // would say "available" for those, which is correct but not useful
  // copy here), so this is read only inside that branch.
  const availabilityState = answer.raw.answer_availability?.state;
  let notice: string;
  let badgeLabelOverride: string | undefined;
  if (answer.reason === "unsupported_mode" && answer.sourceUiMode && answer.sourceUiMode in UNSUPPORTED_MODE_INFO) {
    notice = UNSUPPORTED_MODE_INFO[answer.sourceUiMode as UnsupportedUIMode];
  } else if (answer.reason === "synthesis_incomplete") {
    if (availabilityState && availabilityState !== "available" && availabilityState in AVAILABILITY_NOTICE) {
      notice = AVAILABILITY_NOTICE[availabilityState];
      badgeLabelOverride = AVAILABILITY_BADGE[availabilityState];
    } else {
      // Fails back to the older, more conservative evidence-length-based
      // copy for a response that predates this contract (e.g. a stale
      // cached shape) rather than crash on a missing field.
      notice = hasEvidence
        ? "The real evidence found is shown below, with no generated conclusion, confidence score, or outlook."
        : "No related news, events, or policy evidence was found for this query, and the analysis itself didn't complete.";
    }
  } else if (answer.reason === "unknown_ui_mode") {
    notice = hasEvidence
      ? "This question's answer type wasn't recognized by this version of AI Search. The real evidence found is shown below."
      : "This question's answer type wasn't recognized by this version of AI Search, and no related evidence was found.";
  } else if (answer.reason === "aev2_unavailable") {
    notice = hasEvidence
      ? "This answer's enhanced view isn't available for this response. The real evidence found is shown below."
      : "This answer's enhanced view isn't available for this response, and no related evidence was found.";
  } else {
    notice = NOTICE_BY_REASON[answer.reason];
  }

  return (
    <AIAnswerShell
      query={answer.query}
      uiMode={chromeMode}
      sourceCount={answer.sourceCount}
      // A real synthesis failure has nothing trustworthy to score or
      // relate — an unbuilt-but-successful layout still does, so only
      // gate the shell's own degraded body on a genuine failure.
      synthesisIncomplete={answer.reason === "synthesis_incomplete"}
      degradedNotice={notice}
      evidenceRows={answer.evidenceRows}
      confidence={answer.reason === "synthesis_incomplete" ? null : answer.confidence}
      evidenceCoverage={answer.evidenceCoverage}
      showConfidence={answer.reason !== "synthesis_incomplete"}
      badgeLabelOverride={badgeLabelOverride}
      onNewSearch={onNewSearch}
      onRefine={onRefine}
    >
      <div className="rounded-[16px] border border-violet-500/20 bg-violet-500/[0.05] px-4 py-3">
        <p className="text-[12.5px] leading-5 text-text-secondary">{notice}</p>
      </div>
    </AIAnswerShell>
  );
}
