import { describe, it, expect } from "vitest";
import { companyDirection } from "./companyDirection";

describe("companyDirection — CD3-D (D3) fix for page.tsx's hardcoded-positive bug", () => {
  it("maps beneficiary/loser (Event impact_type vocabulary) correctly", () => {
    expect(companyDirection("beneficiary")).toBe("positive");
    expect(companyDirection("loser")).toBe("negative");
    expect(companyDirection("neutral")).toBe("neutral");
  });

  it("maps positive/negative/neutral (CompanyImpact impact vocabulary) correctly, case-insensitively", () => {
    expect(companyDirection("Positive")).toBe("positive");
    expect(companyDirection("Negative")).toBe("negative");
    expect(companyDirection("Neutral")).toBe("neutral");
    expect(companyDirection("negative")).toBe("negative");
  });

  it("a real loser is never reported as positive — the exact old bug", () => {
    // The bug this replaces: page.tsx used to hardcode impact="positive"
    // unconditionally regardless of what the real value said.
    expect(companyDirection("loser")).not.toBe("positive");
    expect(companyDirection("Negative")).not.toBe("positive");
  });

  it("absent/null/undefined defaults to positive only as documented (the real beneficiaries[]-absence case)", () => {
    expect(companyDirection(null)).toBe("positive");
    expect(companyDirection(undefined)).toBe("positive");
    expect(companyDirection("")).toBe("positive");
  });
});
