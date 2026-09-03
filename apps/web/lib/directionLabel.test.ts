import { describe, it, expect } from "vitest";
import { directionLabel, sessionChangeLabel } from "./directionLabel";

describe("directionLabel — CD3-D (D5) 'BALUFORGE: Positive' wording fix", () => {
  it("qualified positive/negative gets hedged with 'Likely'", () => {
    expect(directionLabel("positive", "qualified")).toBe("Likely positive");
    expect(directionLabel("negative", "qualified")).toBe("Likely negative");
  });

  it("authorized direction renders bare, unhedged", () => {
    expect(directionLabel("positive", "authorized")).toBe("positive");
    expect(directionLabel("negative", "authorized")).toBe("negative");
  });

  it("neutral/mixed pass through unchanged regardless of strength -- not a direction-strength claim", () => {
    expect(directionLabel("neutral", "qualified")).toBe("neutral");
    expect(directionLabel("mixed", "qualified")).toBe("mixed");
  });

  it("unavailable strength passes the raw direction through -- callers are expected to have already excluded these rows", () => {
    expect(directionLabel("positive", "unavailable")).toBe("positive");
  });
});

describe("sessionChangeLabel — CD3-D (D5) 'Banking: Improving' wording fix", () => {
  it("existing sector delta hedges to Likely Improving/Weakening, never the bare claim", () => {
    expect(sessionChangeLabel(false, true)).toBe("Likely Improving");
    expect(sessionChangeLabel(false, false)).toBe("Likely Weakening");
  });

  it("newly-surfaced sector hedges to Possible New Opportunity/Risk", () => {
    expect(sessionChangeLabel(true, true)).toBe("Possible New Opportunity");
    expect(sessionChangeLabel(true, false)).toBe("Possible New Risk");
  });

  it("never returns the old bare, unhedged labels", () => {
    for (const isNew of [true, false]) {
      for (const up of [true, false]) {
        const label = sessionChangeLabel(isNew, up);
        expect(label).not.toBe("Improving");
        expect(label).not.toBe("Weakening");
        expect(label).not.toBe("New Opportunity");
        expect(label).not.toBe("New Risk");
      }
    }
  });
});
