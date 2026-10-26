import { describe, expect, it } from "vitest";
import { showsIndiaSidebar, INDIA_SIDEBAR_HIDDEN_TABS } from "./marketTabs";

describe("showsIndiaSidebar (§2.5 sidebar scoping)", () => {
  it("HIDES the India sidebar on Global Markets and Crypto", () => {
    expect(showsIndiaSidebar("global-markets")).toBe(false);
    expect(showsIndiaSidebar("crypto")).toBe(false);
  });

  it("KEEPS the India sidebar on Overview and After-Market (India context)", () => {
    expect(showsIndiaSidebar("overview")).toBe(true);
    expect(showsIndiaSidebar("after-market")).toBe(true);
  });

  it("preserves the pre-existing exclusions (unchanged behavior)", () => {
    for (const tab of ["live-market", "pre-market", "commodities", "calendar", "sector-intelligence"]) {
      expect(showsIndiaSidebar(tab)).toBe(false);
    }
  });

  it("an unknown tab defaults to showing the sidebar (no silent new hide)", () => {
    expect(showsIndiaSidebar("something-else")).toBe(true);
  });

  it("the hidden set contains the two newly-scoped tabs", () => {
    expect(INDIA_SIDEBAR_HIDDEN_TABS).toContain("global-markets");
    expect(INDIA_SIDEBAR_HIDDEN_TABS).toContain("crypto");
  });
});
