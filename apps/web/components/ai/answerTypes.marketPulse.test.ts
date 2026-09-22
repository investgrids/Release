// market_pulse's minimum eligibility contract (2026-09-22, canonical-
// core audit). Exercises toMarketPulseAEV2Answer directly against
// hand-authored fixtures mirroring aev2/market_pulse.py's real
// assemble_market_pulse() output — no live HTTP path exists yet
// (AEV2_BUILD_COMPLETE is False), so these fixtures ARE the test
// surface.
import { describe, it, expect } from "vitest";
import { toMarketPulseAEV2Answer, toAIAnswer, IMPLEMENTED_UI_MODES } from "./answerTypes";
import {
  completeMarketPulseAnswer, marketPulseSynthesisIncompleteAnswer, synthesisUnavailableMarketPulseAnswer,
} from "./__fixtures__/marketPulse";

describe("toMarketPulseAEV2Answer — eligibility contract", () => {
  it("accepts a complete, fully synthesized market pulse", () => {
    const answer = toMarketPulseAEV2Answer(completeMarketPulseAnswer.result, completeMarketPulseAnswer.aev2);
    expect(answer.ui_mode).toBe("market_pulse");
    if (answer.ui_mode === "market_pulse") {
      expect(answer.aev2.indices.length).toBeGreaterThan(0);
    }
  });

  it("a degraded (synthesis_incomplete) response never reaches the successful layout", () => {
    const answer = toMarketPulseAEV2Answer(
      marketPulseSynthesisIncompleteAnswer.result, marketPulseSynthesisIncompleteAnswer.aev2,
    );
    expect(answer.ui_mode).toBe("degraded");
    if (answer.ui_mode === "degraded") expect(answer.reason).toBe("synthesis_incomplete");
  });

  it("structured output still renders when synthesis is unavailable — provider failure never hides real data", () => {
    const answer = toMarketPulseAEV2Answer(
      synthesisUnavailableMarketPulseAnswer.result, synthesisUnavailableMarketPulseAnswer.aev2,
    );
    expect(answer.ui_mode).toBe("market_pulse");
    if (answer.ui_mode === "market_pulse") {
      expect(answer.aev2.synthesis_status).toBe("unavailable");
      expect(answer.aev2.generated_summary).toBeNull();
      expect(answer.aev2.indices.length).toBeGreaterThan(0);
      expect(answer.aev2.movers.gainers.length).toBeGreaterThan(0);
    }
  });

  it("market_pulse is wired through the live toAIAnswer()/SearchResults path once answer_experience_v2 is attached (2026-09-22, activation-wiring commit)", () => {
    expect(IMPLEMENTED_UI_MODES.has("market_pulse")).toBe(true);
    const withPayload = toAIAnswer({ ...completeMarketPulseAnswer.result, answer_experience_v2: completeMarketPulseAnswer.aev2 });
    expect(withPayload.ui_mode).toBe("market_pulse");
  });

  it("market_pulse degrades honestly on aev2_unavailable when the backend didn't attach a payload — today's ALWAYS case in real production traffic (AEV2_BUILD_COMPLETE stays False)", () => {
    const withoutPayload = toAIAnswer(completeMarketPulseAnswer.result);
    expect(withoutPayload.ui_mode).toBe("degraded");
    if (withoutPayload.ui_mode === "degraded") expect(withoutPayload.reason).toBe("aev2_unavailable");
  });

  it("is a pure function — identical input twice yields deep-equal output, no fixture mutation", () => {
    const first = toMarketPulseAEV2Answer(completeMarketPulseAnswer.result, completeMarketPulseAnswer.aev2);
    const snapshot = JSON.parse(JSON.stringify(completeMarketPulseAnswer.aev2));
    const second = toMarketPulseAEV2Answer(completeMarketPulseAnswer.result, completeMarketPulseAnswer.aev2);
    expect(first).toEqual(second);
    expect(completeMarketPulseAnswer.aev2).toEqual(snapshot);
  });
});
