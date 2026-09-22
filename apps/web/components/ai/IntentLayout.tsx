"use client";

// The exhaustive typed intent dispatcher (2026-09-21 AI Answer UI work).
// Switches on the CLOSED AIAnswer union from answerTypes.ts — every
// member must have an explicit case; `assertNever` in the default branch
// means adding a 9th union member without adding a case here is a
// compile error, not a silent generic-success fallback. There is
// deliberately no `default: return <SomeGenericLayout />` case: an
// answer that reaches this component has already been fully classified
// by `toAIAnswer` (including failing closed to "degraded" for anything
// unrecognized), so every remaining branch is a real, known case.
import type { AIAnswer, DegradedAnswer } from "./answerTypes";
import { assertNever } from "./answerTypes";
import { FactualLookupLayout } from "./layouts/FactualLookupLayout";
import { DirectCompanyResearchLayout } from "./layouts/DirectCompanyResearchLayout";
import { SwitchAnalysisLayout } from "./layouts/SwitchAnalysisLayout";
import { ComparisonLayout } from "./layouts/ComparisonLayout";
import { EventImpactLayout } from "./layouts/EventImpactLayout";
import { MarketPulseLayout } from "./layouts/MarketPulseLayout";
import { DegradedAnswerLayout } from "./layouts/DegradedAnswerLayout";

interface IntentLayoutProps {
  answer: AIAnswer;
  onNewSearch: () => void;
  onRefine?: () => void;
}

// PolicyMacroImpactAnswer/SectorThemeAnswer's own AnswerBase shape still
// spreads cleanly into a DegradedAnswer (both stay in
// UNSUPPORTED_UI_MODES, so toAIAnswer never actually constructs one —
// this branch exists only so the switch below stays exhaustive against
// the type). The five AEV2-sourced answer types no longer share that
// shape (2026-09-22, activation-wiring commit) — each now has its own
// real case above instead.
type StillUnwiredAnswer = Extract<AIAnswer, { ui_mode: "policy_macro_impact" | "sector_theme_research" }>;

function toNotYetImplemented(answer: StillUnwiredAnswer): DegradedAnswer {
  return { ...answer, ui_mode: "degraded", reason: "not_yet_implemented", sourceUiMode: answer.ui_mode };
}

export function IntentLayout({ answer, onNewSearch, onRefine }: IntentLayoutProps) {
  switch (answer.ui_mode) {
    case "factual_lookup":
      return <FactualLookupLayout answer={answer} onNewSearch={onNewSearch} onRefine={onRefine} />;

    // 2026-09-22, activation-wiring commit — each dispatches to the
    // exact same real layout every fixture-only test already exercises.
    // Whether a real user can ever actually hit one of these branches is
    // controlled entirely upstream of this component: NEXT_PUBLIC_AI_
    // ANSWER_SHELL gates whether IntentLayout renders at all, and
    // AEV2_BUILD_COMPLETE gates whether toAIAnswer ever receives a
    // populated answer_experience_v2 to build one of these from in the
    // first place (see answerTypes.ts's "aev2_unavailable" degrade path)
    // — this component itself makes no activation decision.
    case "direct_company_research":
      return <DirectCompanyResearchLayout answer={answer} onNewSearch={onNewSearch} onRefine={onRefine} />;
    case "switch_analysis":
      return <SwitchAnalysisLayout answer={answer} onNewSearch={onNewSearch} onRefine={onRefine} />;
    case "company_comparison":
      return <ComparisonLayout answer={answer} onNewSearch={onNewSearch} onRefine={onRefine} />;
    case "event_impact":
      return <EventImpactLayout answer={answer} onNewSearch={onNewSearch} onRefine={onRefine} />;
    case "market_pulse":
      return <MarketPulseLayout answer={answer} onNewSearch={onNewSearch} onRefine={onRefine} />;

    // Real, valid ui_modes with no dedicated layout built yet — both
    // stay unsupported by their own data-feasibility audits (see
    // UNSUPPORTED_UI_MODES), so toAIAnswer never actually constructs one
    // of these; kept only so this switch stays exhaustive against the
    // type.
    case "policy_macro_impact":
    case "sector_theme_research":
      return <DegradedAnswerLayout answer={toNotYetImplemented(answer)} onNewSearch={onNewSearch} onRefine={onRefine} />;

    case "degraded":
      return <DegradedAnswerLayout answer={answer} onNewSearch={onNewSearch} onRefine={onRefine} />;

    default:
      return assertNever(answer);
  }
}
