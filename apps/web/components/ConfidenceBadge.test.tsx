// CD3-D (D7) — same optional-claim contract as ScoreDisplay.test.tsx,
// for the sibling components/ConfidenceBadge.tsx (ConfidenceData shape).
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { ConfidenceBadge, type ConfidenceData } from "./ConfidenceBadge";
import type { AuthorizedClaim } from "@/lib/claimAuthorization";

const UNAVAILABLE: AuthorizedClaim = { capability: "evidence_quality", strength: "unavailable" };
const QUALIFIED: AuthorizedClaim = { capability: "evidence_quality", strength: "qualified" };

function data(overrides: Partial<ConfidenceData> = {}): ConfidenceData {
  return { level: "High", score: 78, reasons: ["real reason"], ...overrides };
}

describe("ConfidenceBadge (components/) — CD3-D (D7) optional claim field", () => {
  it("omitting claim renders the real level and score unchanged", () => {
    render(<ConfidenceBadge data={data()} />);
    expect(screen.getByText("High")).toBeInTheDocument();
    expect(screen.getByText(/78%/)).toBeInTheDocument();
  });

  it("a non-renderable claim forces Unscored, even with a real level/score", () => {
    render(<ConfidenceBadge data={data({ claim: UNAVAILABLE })} />);
    expect(screen.queryByText("High")).not.toBeInTheDocument();
    expect(screen.getByText("Unscored")).toBeInTheDocument();
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("a qualified claim hedges the score with a tilde but keeps the real level", () => {
    render(<ConfidenceBadge data={data({ claim: QUALIFIED })} />);
    expect(screen.getByText("High")).toBeInTheDocument();
    expect(screen.getByText(/~78%/)).toBeInTheDocument();
  });
});
