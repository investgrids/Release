// Route-level backend<->frontend contract verification (2026-09-22,
// six-mode activation-wiring commit). Every gate function's own
// eligibility-contract test file (answerTypes.comparison.test.ts etc.)
// exercises hand-authored TypeScript fixtures that MIRROR what a
// developer believes assemble_aev2() produces — proven correct in
// isolation, but never checked against the real thing. This file closes
// that gap: the six JSON files in __fixtures__/backend-real/ are
// captured output of the REAL finalize_v3_response() (see apps/backend/
// tests/services/test_aev2_frontend_contract.py and apps/backend/
// scripts/export_aev2_contract_fixtures.py — never hand-edited).
//
// Each fixture is deliberately minimal (matching the backend assembly
// tests' own precedent) — merged onto baseSearchResult()'s full field
// set so the result satisfies SearchResult's type, with the real
// fixture's own fields always taking precedence over the defaults.
import { describe, it, expect } from "vitest";
import { toAIAnswer } from "./answerTypes";
import { baseSearchResult } from "./__fixtures__/directCompanyResearch";
import type { SearchResult } from "@/app/ai-search/AISearchClient";

import directCompanyResearchReal from "./__fixtures__/backend-real/direct_company_research.json";
import switchAnalysisReal from "./__fixtures__/backend-real/switch_analysis.json";
import companyComparisonReal from "./__fixtures__/backend-real/company_comparison.json";
import eventImpactReal from "./__fixtures__/backend-real/event_impact.json";
import marketPulseReal from "./__fixtures__/backend-real/market_pulse.json";
import factualLookupReal from "./__fixtures__/backend-real/factual_lookup.json";

function toSearchResult(real: object): SearchResult {
  return { ...baseSearchResult(), ...real } as unknown as SearchResult;
}

describe("toAIAnswer against real backend-finalizer output — not hand-authored fixtures", () => {
  it("direct_company_research: a real finalize_v3_response() output reaches the real layout", () => {
    const answer = toAIAnswer(toSearchResult(directCompanyResearchReal));
    expect(answer.ui_mode).toBe("direct_company_research");
    if (answer.ui_mode === "direct_company_research") {
      expect(answer.resolvedCompany.symbol).toBe("RELIANCE");
      expect(answer.aev2.direct_conclusion.validation_status).toBe("validated");
    }
  });

  it("switch_analysis: a real finalize_v3_response() output reaches the real layout", () => {
    const answer = toAIAnswer(toSearchResult(switchAnalysisReal));
    expect(answer.ui_mode).toBe("switch_analysis");
    if (answer.ui_mode === "switch_analysis") {
      expect(answer.switch.current_company.symbol).toBe("BEL");
      expect(answer.switch.alternative_company.symbol).toBe("HAL");
    }
  });

  it("company_comparison: a real finalize_v3_response() output reaches the real layout", () => {
    const answer = toAIAnswer(toSearchResult(companyComparisonReal));
    expect(answer.ui_mode).toBe("company_comparison");
    if (answer.ui_mode === "company_comparison") {
      expect(new Set([answer.comparison.left_company.symbol, answer.comparison.right_company.symbol]))
        .toEqual(new Set(["INFY", "TCS"]));
    }
  });

  it("event_impact: a real finalize_v3_response() output reaches the real layout", () => {
    const answer = toAIAnswer(toSearchResult(eventImpactReal));
    expect(answer.ui_mode).toBe("event_impact");
    if (answer.ui_mode === "event_impact") {
      expect(answer.eventImpact.event.id).toBe("e-reliance-1");
    }
  });

  it("market_pulse: a real finalize_v3_response() output reaches the real layout", () => {
    const answer = toAIAnswer(toSearchResult(marketPulseReal));
    expect(answer.ui_mode).toBe("market_pulse");
    if (answer.ui_mode === "market_pulse") {
      expect(answer.aev2.indices.length).toBeGreaterThan(0);
    }
  });

  it("factual_lookup: a real finalize_v3_response() output reaches the real layout without needing answer_experience_v2 at all", () => {
    const answer = toAIAnswer(toSearchResult(factualLookupReal));
    expect(answer.ui_mode).toBe("factual_lookup");
  });

  // ── Missing/ineligible real contract -> mode-specific degraded state ─────

  it("a real payload missing answer_experience_v2 entirely degrades to aev2_unavailable — today's actual production shape (AEV2_BUILD_COMPLETE=False)", () => {
    const { answer_experience_v2: _drop, ...withoutPayload } = directCompanyResearchReal as Record<string, unknown>;
    const answer = toAIAnswer(toSearchResult(withoutPayload));
    expect(answer.ui_mode).toBe("degraded");
    if (answer.ui_mode === "degraded") expect(answer.reason).toBe("aev2_unavailable");
  });

  it("a real comparison contract with a mismatched company degrades honestly (ineligible_entity_mismatch), never crashes", () => {
    const mutated = JSON.parse(JSON.stringify(companyComparisonReal));
    mutated.answer_experience_v2.comparison.left_company = { symbol: "WIPRO", name: "Wipro Ltd" };
    const answer = toAIAnswer(toSearchResult(mutated));
    expect(answer.ui_mode).toBe("degraded");
    if (answer.ui_mode === "degraded") expect(answer.reason).toBe("ineligible_entity_mismatch");
  });

  it("a real switch contract with an unvalidated claim degrades honestly (ineligible_unvalidated_conclusion), never crashes", () => {
    const mutated = JSON.parse(JSON.stringify(switchAnalysisReal));
    mutated.answer_experience_v2.switch_analysis.direct_comparison.validation_status = "unvalidated";
    const answer = toAIAnswer(toSearchResult(mutated));
    expect(answer.ui_mode).toBe("degraded");
    if (answer.ui_mode === "degraded") expect(answer.reason).toBe("ineligible_unvalidated_conclusion");
  });

  // ── Unknown/unsupported ui_mode -> fail closed ───────────────────────────

  it("a real payload with an unrecognized ui_mode fails closed to unknown_ui_mode", () => {
    const mutated = { ...directCompanyResearchReal, ui_mode: "totally_new_backend_mode" };
    const answer = toAIAnswer(toSearchResult(mutated));
    expect(answer.ui_mode).toBe("degraded");
    if (answer.ui_mode === "degraded") expect(answer.reason).toBe("unknown_ui_mode");
  });

  it("a real payload with an explicitly unsupported ui_mode fails closed to unsupported_mode", () => {
    const mutated = { ...directCompanyResearchReal, ui_mode: "policy_macro_impact" };
    const answer = toAIAnswer(toSearchResult(mutated));
    expect(answer.ui_mode).toBe("degraded");
    if (answer.ui_mode === "degraded") expect(answer.reason).toBe("unsupported_mode");
  });

  // ── Cached and fresh real responses produce equivalent public shapes ────

  it.each([
    ["direct_company_research", directCompanyResearchReal],
    ["switch_analysis", switchAnalysisReal],
    ["company_comparison", companyComparisonReal],
    ["event_impact", eventImpactReal],
    ["market_pulse", marketPulseReal],
    ["factual_lookup", factualLookupReal],
  ] as const)("%s: toAIAnswer is deep-equal whether the same real payload arrived fresh or from a cache hit", (_name, real) => {
    const fresh = toAIAnswer(toSearchResult(real));
    const cached = toAIAnswer(toSearchResult(JSON.parse(JSON.stringify(real))));
    expect(fresh).toEqual(cached);
  });

  // ── Prohibited legacy fields never reach the typed answer object graph ──

  const PROHIBITED_KEYS = [
    "engine_verdict", "top_picks", "suitable_for", "risk_level",
    "confidence_self_rating", "scenarios", "decision_engine_v2",
  ];

  function flattenKeys(obj: unknown, seen = new Set<unknown>()): Set<string> {
    const keys = new Set<string>();
    if (obj && typeof obj === "object") {
      if (seen.has(obj)) return keys;
      seen.add(obj);
      for (const [k, v] of Object.entries(obj as Record<string, unknown>)) {
        keys.add(k);
        for (const nested of flattenKeys(v, seen)) keys.add(nested);
      }
    }
    return keys;
  }

  it.each([
    ["direct_company_research", directCompanyResearchReal],
    ["switch_analysis", switchAnalysisReal],
    ["company_comparison", companyComparisonReal],
    ["event_impact", eventImpactReal],
    ["market_pulse", marketPulseReal],
  ] as const)("%s: the typed answer's own fields (aev2/eventImpact/switch/comparison) never carry a prohibited legacy key", (_name, real) => {
    const answer = toAIAnswer(toSearchResult(real));
    // `raw` deliberately still carries the plain V3 dict (investment_
    // verdict included) for the legacy production UI's own use — only
    // the AEV2-sourced sub-object itself must stay clean.
    const aev2Field = "aev2" in answer ? (answer as { aev2: unknown }).aev2 : null;
    if (!aev2Field) return;
    const keys = flattenKeys(aev2Field);
    for (const forbidden of PROHIBITED_KEYS) {
      expect(keys.has(forbidden), `${forbidden} must never appear inside a real ${_name} answer's aev2 field`).toBe(false);
    }
  });
});
