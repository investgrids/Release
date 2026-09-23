// buildEvidenceRows's real-event-source fix (2026-09-22, browser QA
// content-integrity review): a related_events row used to always show
// `category` (a classification like "Macro") in the evidence table's
// Source column, even when the backend's real Event.source field (the
// actual ingestion adapter, e.g. "nse_announcements") was available.
// Exercised indirectly via toAIAnswer() -> factual_lookup's baseFields,
// the one implemented mode whose evidenceRows are reachable without an
// AEV2 payload.
import { describe, it, expect } from "vitest";
import { toAIAnswer } from "./answerTypes";
import { baseSearchResult } from "./__fixtures__/directCompanyResearch";

function buildFactualAnswer(relatedEvents: Record<string, unknown>[]) {
  const result = baseSearchResult({ ui_mode: "factual_lookup", related_events: relatedEvents });
  const answer = toAIAnswer(result);
  if (answer.ui_mode !== "factual_lookup") throw new Error("expected factual_lookup");
  return answer;
}

describe("buildEvidenceRows — event source honesty", () => {
  it("uses the real Event.source field when present, never the category", () => {
    const answer = buildFactualAnswer([
      { id: "e1", title: "Reliance Jio completes 5G rollout", date: "2026-09-15", category: "Corporate", source: "nse_announcements" },
    ]);
    const row = answer.evidenceRows.find(r => r.id === "event-e1");
    expect(row?.source).toBe("nse_announcements");
  });

  it("falls back to '<category> event' (never a bare category) when no real source exists", () => {
    const answer = buildFactualAnswer([
      { id: "e2", title: "RBI holds repo rate steady", date: "2026-06-18", category: "Macro", source: "" },
    ]);
    const row = answer.evidenceRows.find(r => r.id === "event-e2");
    expect(row?.source).toBe("Macro event");
    expect(row?.source).not.toBe("Macro");
  });

  it("falls back to 'Market event' when category is also absent", () => {
    const answer = buildFactualAnswer([
      { id: "e3", title: "Untitled event", date: "2026-06-18", category: "", source: "" },
    ]);
    const row = answer.evidenceRows.find(r => r.id === "event-e3");
    expect(row?.source).toBe("Market event");
  });
});
