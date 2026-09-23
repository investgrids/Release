// Content-integrity fixes found via real browser QA (2026-09-22): a
// degraded answer whose only evidence was a single structured Event with
// no real source field was rendered with an overstated "1 verified
// source" badge, a logically invalid "views are consistent across
// sources" conclusion drawn from that single item, two permanently dead
// nav links (Ripple impact / Related intelligence), an internal
// "DEGRADED" badge, and a "Not investment advice" pill duplicating the
// footer disclaimer verbatim. Each is pinned here directly.
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { AIAnswerShell, type EvidenceCoverageSummary } from "./AIAnswerShell";

function renderShell(overrides: Partial<React.ComponentProps<typeof AIAnswerShell>> = {}) {
  return render(
    <AIAnswerShell
      query="Should I research HDFC Bank now?"
      uiMode="direct_company_research"
      sourceCount={0}
      evidenceRows={[]}
      evidenceCoverage={null}
      showConfidence={false}
      onNewSearch={() => {}}
      {...overrides}
    >
      <p>body</p>
    </AIAnswerShell>,
  );
}

const eventOnlyCoverage: EvidenceCoverageSummary = {
  newsSourceCount: 0, eventSourceCount: 1, policySourceCount: 0,
};

const mixedCoverage: EvidenceCoverageSummary = {
  newsSourceCount: 2, eventSourceCount: 1, policySourceCount: 0,
};

describe("AIAnswerShell — header source-count badge honesty", () => {
  it("a single bare structured event with no other provenance is called a linked market event, never a verified source", () => {
    renderShell({ sourceCount: 1, evidenceCoverage: eventOnlyCoverage });
    expect(screen.getByText("1 linked market event")).toBeInTheDocument();
    expect(screen.queryByText(/verified source/)).not.toBeInTheDocument();
  });

  it("a mix that includes a real named source (news/policy/filing) is still called a verified source", () => {
    renderShell({ sourceCount: 3, evidenceCoverage: mixedCoverage });
    expect(screen.getByText("3 verified sources")).toBeInTheDocument();
  });

  it("with no evidenceCoverage at all, defaults to the conservative linked-event wording rather than assuming verified provenance", () => {
    renderShell({ sourceCount: 1, evidenceCoverage: null });
    expect(screen.getByText("1 linked market event")).toBeInTheDocument();
  });
});

describe("AIAnswerShell — one-source conflict-assessment logic", () => {
  it("with exactly one source, never concludes sources are consistent or conflicting", () => {
    renderShell({
      evidenceCoverage: { newsSourceCount: 0, eventSourceCount: 1, policySourceCount: 0, contradictionFlagged: false },
    });
    expect(screen.queryByText(/consistent across sources/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Conflicting evidence found/)).not.toBeInTheDocument();
    expect(screen.getByText("Conflict assessment requires additional independent evidence.")).toBeInTheDocument();
  });

  it("with two or more sources, shows the real conflict assessment", () => {
    renderShell({
      evidenceCoverage: { newsSourceCount: 1, eventSourceCount: 1, policySourceCount: 0, contradictionFlagged: false },
    });
    expect(screen.getByText(/consistent across sources/)).toBeInTheDocument();
  });

  it("with zero sources, omits the conflict line entirely even if a conflict signal is technically present", () => {
    renderShell({
      evidenceCoverage: { newsSourceCount: 0, eventSourceCount: 0, policySourceCount: 0, contradictionFlagged: false },
    });
    expect(screen.queryByText(/consistent across sources/)).not.toBeInTheDocument();
    expect(screen.queryByText(/additional independent evidence/)).not.toBeInTheDocument();
  });
});

describe("AIAnswerShell — dead nav links removed, Methodology kept", () => {
  it("never renders Ripple impact or Related intelligence", () => {
    renderShell();
    expect(screen.queryByText("Ripple impact")).not.toBeInTheDocument();
    expect(screen.queryByText("Related intelligence")).not.toBeInTheDocument();
  });

  it("still renders Methodology, linking to the real knowledge-base page", () => {
    renderShell();
    const link = screen.getByText("Methodology").closest("a");
    expect(link).toHaveAttribute("href", "/knowledge/ai-methodology");
  });
});

describe("AIAnswerShell — Evidence Coverage card hides entirely when there's nothing to show", () => {
  it("real browser QA finding (2026-09-23): a query matching zero news/events/policies used to render an empty 'Evidence Coverage' header with no rows and no conflict line beneath it — the card must not render at all", () => {
    // contradictionFlagged is ALWAYS a real boolean (never undefined) —
    // see buildEvidenceCoverage's `!!result.validation?.contradiction_
    // flagged` — so this exact shape (all counts 0, a defined boolean)
    // is the real one every zero-evidence response produces, not a
    // contrived edge case.
    renderShell({
      evidenceCoverage: { newsSourceCount: 0, eventSourceCount: 0, policySourceCount: 0, contradictionFlagged: false },
    });
    expect(screen.queryByText("Evidence Coverage")).not.toBeInTheDocument();
  });

  it("still renders normally once at least one real source exists", () => {
    renderShell({
      evidenceCoverage: { newsSourceCount: 1, eventSourceCount: 0, policySourceCount: 0, contradictionFlagged: false },
    });
    expect(screen.getByText("Evidence Coverage")).toBeInTheDocument();
  });
});

describe("AIAnswerShell — degraded badge wording and disclaimer deduplication", () => {
  it("shows Limited evidence, never the internal DEGRADED label", () => {
    renderShell({ uiMode: "degraded" });
    expect(screen.getByText("Limited evidence")).toBeInTheDocument();
    expect(screen.queryByText(/^Degraded$/)).not.toBeInTheDocument();
  });

  it("shows only one investment-advice disclaimer, not a duplicate header pill", () => {
    renderShell();
    expect(screen.queryByText("Not investment advice")).not.toBeInTheDocument();
    expect(screen.getByText(/should not be considered investment advice/)).toBeInTheDocument();
  });
});
