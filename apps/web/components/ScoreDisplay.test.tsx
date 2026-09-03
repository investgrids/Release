// CD3-D (D7) — ScoreDisplay used to accept a bare score with no
// measurement_type/integrity_status parameter at all: a DEGRADED or
// FALLBACK-but-non-null value rendered identically to a VALID one (the
// audit's own structural finding). `claim` is optional and additive;
// these tests confirm both halves of that contract: omitting it changes
// nothing for existing callers, and passing a non-renderable claim
// forces the same honest "unscored" state a null score already gets.
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { ScoreDisplay } from "./ScoreDisplay";
import type { AuthorizedClaim } from "@/lib/claimAuthorization";

const UNAVAILABLE: AuthorizedClaim = { capability: "evidence_quality", strength: "unavailable", reason: "test" };
const QUALIFIED: AuthorizedClaim = { capability: "evidence_quality", strength: "qualified" };
const AUTHORIZED: AuthorizedClaim = { capability: "evidence_quality", strength: "authorized" };

describe("ScoreDisplay — CD3-D (D7) optional claim prop", () => {
  it("omitting claim entirely renders the real score exactly as before this prop existed", () => {
    render(<ScoreDisplay score={72} variant="pill" />);
    expect(screen.getByText(/72/)).toBeInTheDocument();
  });

  it("a non-renderable (unavailable) claim forces the unscored state, even with a real numeric score", () => {
    render(<ScoreDisplay score={72} variant="pill" claim={UNAVAILABLE} />);
    expect(screen.queryByText(/72/)).not.toBeInTheDocument();
    expect(screen.getByText("test")).toBeInTheDocument();
  });

  it("a qualified claim renders the real score but visibly hedged with a tilde", () => {
    render(<ScoreDisplay score={72} variant="pill" claim={QUALIFIED} />);
    expect(screen.getByText(/~72/)).toBeInTheDocument();
  });

  it("an authorized claim renders the bare number, no hedge", () => {
    render(<ScoreDisplay score={72} variant="pill" claim={AUTHORIZED} />);
    expect(screen.getByText(/72/)).toBeInTheDocument();
    expect(screen.queryByText(/~72/)).not.toBeInTheDocument();
  });

  it("circle variant also hedges a qualified claim", () => {
    render(<ScoreDisplay score={55} variant="circle" claim={QUALIFIED} />);
    expect(screen.getByText(/~55/)).toBeInTheDocument();
  });
});
