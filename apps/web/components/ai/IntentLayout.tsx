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
import type { AIAnswer } from "./answerTypes";
import { assertNever } from "./answerTypes";
import { FactualLookupLayout } from "./layouts/FactualLookupLayout";
import { DegradedAnswerLayout } from "./layouts/DegradedAnswerLayout";

interface IntentLayoutProps {
  answer: AIAnswer;
  onNewSearch: () => void;
  onRefine?: () => void;
}

export function IntentLayout({ answer, onNewSearch, onRefine }: IntentLayoutProps) {
  switch (answer.ui_mode) {
    case "factual_lookup":
      return <FactualLookupLayout answer={answer} onNewSearch={onNewSearch} onRefine={onRefine} />;

    // Real, valid ui_modes with no dedicated layout built yet (see
    // answerTypes.ts's IMPLEMENTED_UI_MODES and the recommended build
    // order). toAIAnswer already routes these to a DegradedAnswer with
    // reason "not_yet_implemented" before this component normally sees
    // them, so in the live app these branches rarely fire — but the type
    // still allows them (any test fixture or future caller could build
    // one of these variants directly), so each case fails closed the
    // same way here too rather than relying solely on the upstream
    // transform. Each one moves to its own real case above as its
    // layout ships.
    case "direct_company_research":
    case "switch_analysis":
    case "company_comparison":
    case "policy_macro_impact":
    case "event_impact":
    case "sector_theme_research":
    case "market_pulse":
      return <DegradedAnswerLayout answer={{ ...answer, ui_mode: "degraded", reason: "not_yet_implemented", sourceUiMode: answer.ui_mode }} onNewSearch={onNewSearch} onRefine={onRefine} />;

    case "degraded":
      return <DegradedAnswerLayout answer={answer} onNewSearch={onNewSearch} onRefine={onRefine} />;

    default:
      return assertNever(answer);
  }
}
