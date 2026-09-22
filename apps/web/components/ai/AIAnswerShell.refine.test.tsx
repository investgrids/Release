// Refine is always disabled in the AEV2 shell (2026-09-22, intent-
// coverage audit) — the legacy Refine endpoint returns investment_
// verdict/decision_engine_v2/ai_conclusion directly, never a CoreAnswer
// or AEV2 payload, so wiring an AEV2 answer's onRefine into it would
// route an AEV2 user into exactly the prohibited plain-V3 concepts this
// shell exists to keep unreachable. Legacy Refine (RefineAnalysisPanel,
// the pre-AEV2-shell UI) is a completely separate component tree and is
// unaffected by any of this.
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { AIAnswerShell } from "./AIAnswerShell";

function renderShell(onRefine?: () => void) {
  return render(
    <AIAnswerShell
      query="Should I research HDFC Bank now?"
      uiMode="direct_company_research"
      sourceCount={1}
      evidenceRows={[]}
      evidenceCoverage={null}
      showConfidence={false}
      onNewSearch={() => {}}
      onRefine={onRefine}
    >
      <p>body</p>
    </AIAnswerShell>,
  );
}

describe("AIAnswerShell — Refine gating", () => {
  it("always renders a disabled Refine button, even when no onRefine is passed", () => {
    renderShell();
    const button = screen.getByRole("button", { name: /Refine/ });
    expect(button).toBeDisabled();
  });

  it("stays disabled even when a real onRefine handler IS passed — the shell owns this decision, not the caller", () => {
    renderShell(() => {});
    const button = screen.getByRole("button", { name: /Refine/ });
    expect(button).toBeDisabled();
  });

  it("shows the exact upgrade-in-progress tooltip", () => {
    renderShell();
    const button = screen.getByRole("button", { name: /Refine/ });
    expect(button).toHaveAttribute("title", "Refinement is being upgraded for this answer format.");
  });

  it("never calls onRefine even if a click is somehow dispatched (disabled buttons don't fire click handlers)", () => {
    const onRefine = vi.fn();
    renderShell(onRefine);
    const button = screen.getByRole("button", { name: /Refine/ });
    fireEvent.click(button);
    expect(onRefine).not.toHaveBeenCalled();
  });
});
