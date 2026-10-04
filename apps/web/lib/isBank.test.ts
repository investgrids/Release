import { describe, expect, it } from "vitest";
import { isBank } from "@/app/companies/[symbol]/CompanyPageClient";

describe("isBank", () => {
  it("matches Yahoo's bank industries only", () => {
    expect(isBank("Banks - Regional")).toBe(true);
    expect(isBank("Banks - Diversified")).toBe(true);
    expect(isBank("Credit Services")).toBe(false);
    expect(isBank("Information Technology Services")).toBe(false);
    expect(isBank(undefined)).toBe(false);
  });
});
