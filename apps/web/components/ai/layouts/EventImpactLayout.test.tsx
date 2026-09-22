// Component tests for EventImpactLayout (2026-09-22). Proves the narrow
// event_impact contract renders only its permitted sections, never
// surfaces a prohibited plain-V3/ai_summary/Ripple concept, and states
// price association without causation.
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { EventImpactLayout } from "./EventImpactLayout";
import { toEventImpactAEV2Answer } from "../answerTypes";
import {
  completeEventImpactAnswer, eventImpactNoSectorsAnswer, eventImpactWithPriceReactionAnswer,
} from "../__fixtures__/eventImpact";
import type { AEV2EventImpactAnswer } from "../answerTypes";

function buildAnswer(fixture: typeof completeEventImpactAnswer): AEV2EventImpactAnswer {
  const answer = toEventImpactAEV2Answer(fixture.result, fixture.aev2);
  if (answer.ui_mode !== "event_impact") {
    throw new Error("fixture expected to be eligible for event_impact");
  }
  return answer;
}

const PROHIBITED_TEXT = [
  "Buy", "Sell", "Hold", "Verdict", "Recommendation", "Beneficiary", "Loser",
  "Affected company", "caused by", "This caused",
];

// Checked against `answer.eventImpact` specifically (not the whole
// AEV2Response) — related_intelligence.ripple/opportunities/events are
// pre-existing, always-empty/null general AEV2Response fields unrelated
// to event_impact, not a leak this test should flag.
const PROHIBITED_KEYS = [
  "investment_verdict", "engine_verdict", "rating", "suitable_for", "risk_level",
  "top_picks", "scenarios", "raw", "ai_summary", "impact_type", "reason",
  "ripple", "graph", "transmission_channels", "affected_segments", "beneficiaries",
  "monitoring_items", "contradictions",
];

function collectKeys(value: unknown, found: Set<string>, seen = new Set<unknown>()) {
  if (value == null || typeof value !== "object") return;
  if (seen.has(value)) return;
  seen.add(value);
  for (const key of Object.keys(value as Record<string, unknown>)) {
    found.add(key);
    collectKeys((value as Record<string, unknown>)[key], found, seen);
  }
}

describe("EventImpactLayout", () => {
  it("renders the evidence-based summary and the what-happened section from source-derived text", () => {
    const answer = buildAnswer(completeEventImpactAnswer);
    render(<EventImpactLayout answer={answer} onNewSearch={() => {}} />);

    expect(screen.getByText(/Jio's completion of its nationwide 5G rollout/)).toBeInTheDocument();
    // Appears twice: the "What happened" headline and the Key Evidence
    // row's own title (same source text, shown in two places).
    expect(screen.getAllByText("Reliance Jio completes pan-India 5G network rollout").length).toBeGreaterThan(0);
    expect(screen.getByText(/Reliance Jio Infocomm Limited informed the Exchange/)).toBeInTheDocument();
    expect(screen.getByText(/Source: nse_announcements/)).toBeInTheDocument();
  });

  it("renders companies connected using neutral language only", () => {
    const answer = buildAnswer(completeEventImpactAnswer);
    render(<EventImpactLayout answer={answer} onNewSearch={() => {}} />);
    expect(screen.getByText(/Reliance Industries Ltd/)).toBeInTheDocument();
    expect(screen.getAllByText(/Connected company/).length).toBeGreaterThan(0);
  });

  it("shows the documented fallback notice when the original publisher URL is absent", () => {
    const answer = buildAnswer(completeEventImpactAnswer);
    render(<EventImpactLayout answer={answer} onNewSearch={() => {}} />);
    expect(screen.getByText(/Original source link unavailable\./)).toBeInTheDocument();
    expect(screen.getByText(/View the structured MarketRipple Event record\./)).toBeInTheDocument();
  });

  it("omits the sectors section cleanly when none are linked — no blank card", () => {
    const answer = buildAnswer(eventImpactNoSectorsAnswer);
    render(<EventImpactLayout answer={answer} onNewSearch={() => {}} />);
    expect(screen.queryByText("Sectors connected")).not.toBeInTheDocument();
  });

  it("omits the observed price reactions section entirely when empty — the current real state", () => {
    const answer = buildAnswer(completeEventImpactAnswer);
    render(<EventImpactLayout answer={answer} onNewSearch={() => {}} />);
    expect(screen.queryByText("Observed price reactions")).not.toBeInTheDocument();
  });

  it("renders a price reaction as an observed association, never a causal claim, when present", () => {
    const answer = buildAnswer(eventImpactWithPriceReactionAnswer);
    render(<EventImpactLayout answer={answer} onNewSearch={() => {}} />);
    expect(screen.getByText("Observed price reactions")).toBeInTheDocument();
    expect(screen.getByText(/\+1% observed Next session/)).toBeInTheDocument();
    expect(screen.getByText(/An observed association, not a causal claim/)).toBeInTheDocument();
    const { container } = render(<EventImpactLayout answer={answer} onNewSearch={() => {}} />);
    expect((container.textContent ?? "").toLowerCase()).not.toContain("caused");
  });

  it("never renders a prohibited advisory or beneficiary/loser label", () => {
    const answer = buildAnswer(completeEventImpactAnswer);
    const { container } = render(<EventImpactLayout answer={answer} onNewSearch={() => {}} />);
    for (const word of PROHIBITED_TEXT) {
      expect(container.textContent ?? "").not.toContain(word);
    }
  });

  it("the eventImpact object graph never carries a prohibited excluded-concept key (recursive regression net)", () => {
    const answer = buildAnswer(completeEventImpactAnswer);
    const found = new Set<string>();
    collectKeys(answer.eventImpact, found);
    for (const key of PROHIBITED_KEYS) {
      expect(found.has(key)).toBe(false);
    }
  });

  it("each Key Evidence row shows which claim it supports", () => {
    const answer = buildAnswer(completeEventImpactAnswer);
    render(<EventImpactLayout answer={answer} onNewSearch={() => {}} />);
    expect(screen.getAllByText(/Cited by: Summary/).length).toBeGreaterThan(0);
  });
});
