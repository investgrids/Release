// Explicit recognized-but-unsupported modes (2026-09-22, intent-coverage
// audit). Proves each of the 7 UnsupportedUIMode values gets its OWN
// specific message via toAIAnswer(), never collapsed into the generic
// "not_yet_implemented"/"Analysis unavailable" bucket the 6 locally-
// implemented-but-unwired modes still correctly use.
import { describe, it, expect } from "vitest";
import {
  toAIAnswer, IMPLEMENTED_UI_MODES, UNSUPPORTED_MODE_INFO, type UnsupportedUIMode,
} from "./answerTypes";
import { baseSearchResult } from "./__fixtures__/directCompanyResearch";
import type { UIMode } from "@/app/ai-search/AISearchClient";

const UNSUPPORTED_MODES: UnsupportedUIMode[] = [
  "technical_timing", "company_discovery", "portfolio_review",
  "earnings_preview", "multi_company_comparison", "policy_macro_impact",
  "sector_theme_research",
];

describe("toAIAnswer — explicit unsupported modes", () => {
  it.each(UNSUPPORTED_MODES)("routes %s to reason unsupported_mode with its own sourceUiMode", (mode) => {
    const result = baseSearchResult({ ui_mode: mode as UIMode });
    const answer = toAIAnswer(result);
    expect(answer.ui_mode).toBe("degraded");
    if (answer.ui_mode === "degraded") {
      expect(answer.reason).toBe("unsupported_mode");
      expect(answer.sourceUiMode).toBe(mode);
    }
  });

  it("none of the 7 unsupported modes are ever in IMPLEMENTED_UI_MODES", () => {
    for (const mode of UNSUPPORTED_MODES) {
      expect(IMPLEMENTED_UI_MODES.has(mode)).toBe(false);
    }
  });

  it("every unsupported mode has its own distinct, non-empty message", () => {
    const messages = UNSUPPORTED_MODES.map(m => UNSUPPORTED_MODE_INFO[m]);
    expect(new Set(messages).size).toBe(UNSUPPORTED_MODES.length);
    for (const msg of messages) {
      expect(msg.length).toBeGreaterThan(20);
    }
  });

  it("technical_timing's message matches the approved exact wording", () => {
    expect(UNSUPPORTED_MODE_INFO.technical_timing).toBe(
      "Technical timing is unavailable because verified price-series and indicator coverage is insufficient.",
    );
  });

  it("a still-unwired-but-locally-implemented mode keeps the generic not_yet_implemented reason, not unsupported_mode", () => {
    const result = baseSearchResult({ ui_mode: "direct_company_research" as UIMode });
    const answer = toAIAnswer(result);
    expect(answer.ui_mode).toBe("degraded");
    if (answer.ui_mode === "degraded") {
      expect(answer.reason).toBe("not_yet_implemented");
    }
  });

  it("a genuinely unrecognized ui_mode still fails closed to unknown_ui_mode, not unsupported_mode", () => {
    const result = baseSearchResult({ ui_mode: "totally_made_up_mode" as unknown as UIMode });
    const answer = toAIAnswer(result);
    expect(answer.ui_mode).toBe("degraded");
    if (answer.ui_mode === "degraded") {
      expect(answer.reason).toBe("unknown_ui_mode");
    }
  });

  it("synthesis_incomplete still wins over an unsupported ui_mode", () => {
    const result = baseSearchResult({ ui_mode: "technical_timing" as UIMode, synthesis_incomplete: true });
    const answer = toAIAnswer(result);
    expect(answer.ui_mode).toBe("degraded");
    if (answer.ui_mode === "degraded") {
      expect(answer.reason).toBe("synthesis_incomplete");
    }
  });
});
