// CD3-D (D7) — same optional-claim contract as ScoreDisplay.test.tsx.
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { ConfidenceBadge, getConfidenceLevel } from "./ConfidenceBadge";
import type { AuthorizedClaim } from "@/lib/claimAuthorization";

const UNAVAILABLE: AuthorizedClaim = { capability: "evidence_quality", strength: "unavailable" };
const QUALIFIED: AuthorizedClaim = { capability: "evidence_quality", strength: "qualified" };

describe("getConfidenceLevel — CD3-D (D7) optional claim param", () => {
  it("omitting claim behaves exactly as before", () => {
    expect(getConfidenceLevel(80)).toBe("high");
  });

  it("a non-renderable claim forces unscored regardless of a real score", () => {
    expect(getConfidenceLevel(80, UNAVAILABLE)).toBe("unscored");
  });
});

describe("ConfidenceBadge — CD3-D (D7) optional claim prop", () => {
  it("omitting claim renders the real score unchanged", () => {
    render(<ConfidenceBadge score={82} />);
    expect(screen.getByText(/82%/)).toBeInTheDocument();
  });

  it("a non-renderable claim forces Unscored, even with a real numeric score", () => {
    render(<ConfidenceBadge score={82} claim={UNAVAILABLE} />);
    expect(screen.queryByText(/82%/)).not.toBeInTheDocument();
    expect(screen.getByText("Unscored")).toBeInTheDocument();
  });

  it("a qualified claim hedges the score with a tilde", () => {
    render(<ConfidenceBadge score={82} claim={QUALIFIED} />);
    expect(screen.getByText(/~82%/)).toBeInTheDocument();
  });
});
