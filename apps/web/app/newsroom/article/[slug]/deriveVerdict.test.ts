/**
 * deriveVerdict() — the AI Investment Verdict headline shown at the top
 * of every newsroom article, directly above the CompanyImpactTable.
 *
 * Real bug (user-reported, screenshot): a Zydus USFDA-approval article
 * with 1 company (positive) + 5 sectors (mixed) produced a "Neutral"
 * headline verdict sitting directly above a "Positive" AI Impact row for
 * that exact company in the table below — a visible self-contradiction
 * on the same page. Root cause: the old pool blended companies and
 * sectors together, letting sector noise dilute/override a single clear
 * company signal. Fixed to prioritize companies as the primary signal
 * whenever the article names any.
 */
import { describe, it, expect } from "vitest";
import { deriveVerdict, type CompanyAffected, type SectorAffected } from "./deriveVerdict";

function company(impact: CompanyAffected["impact"], name = "Company"): CompanyAffected {
  return { name, symbol: name.toUpperCase(), impact };
}
function sector(impact: SectorAffected["impact"], name = "Sector"): SectorAffected {
  return { name, impact };
}

describe("deriveVerdict", () => {
  it("the exact reported bug: 1 positive company + 5 mixed sectors must not contradict the company's own impact", () => {
    const companies = [company("positive", "ZYDUSLIFE")];
    const sectors = [
      sector("positive", "Pharma"), sector("negative", "Banking"), sector("neutral", "IT"),
      sector("negative", "Auto"), sector("neutral", "Energy"),
    ];
    const result = deriveVerdict(companies, sectors);
    expect(result.stance).toBe("Bullish");
    expect(result.focus).toBe("ZYDUSLIFE");
  });

  it("single negative company is Bearish regardless of unrelated sector mix", () => {
    const companies = [company("negative", "YESBANK")];
    const sectors = [sector("positive", "IT"), sector("positive", "Pharma"), sector("neutral", "Auto")];
    const result = deriveVerdict(companies, sectors);
    expect(result.stance).toBe("Bearish");
  });

  it("multiple companies, clear positive majority -> Bullish", () => {
    const companies = [company("positive", "A"), company("positive", "B"), company("neutral", "C")];
    const result = deriveVerdict(companies, []);
    expect(result.stance).toBe("Bullish");
  });

  it("multiple companies, genuinely split -> Mixed, not silently Neutral", () => {
    const companies = [company("positive", "A"), company("negative", "B")];
    const result = deriveVerdict(companies, []);
    expect(result.stance).toBe("Mixed");
  });

  it("no companies at all falls back to sector-level aggregation", () => {
    const sectors = [sector("positive", "Banking"), sector("positive", "Finance"), sector("neutral", "IT")];
    const result = deriveVerdict([], sectors);
    expect(result.stance).toBe("Bullish");
    expect(result.focus).toBe("Banking");
  });

  it("no companies and no sectors -> Neutral, no crash", () => {
    const result = deriveVerdict([], []);
    expect(result.stance).toBe("Neutral");
    expect(result.focus).toBeNull();
  });

  it("companies with no impact field set are excluded from the pool, not treated as neutral votes", () => {
    const companies = [company("positive", "A"), { name: "B", symbol: "B", impact: undefined as any }];
    const result = deriveVerdict(companies, []);
    expect(result.stance).toBe("Bullish");
  });
});
