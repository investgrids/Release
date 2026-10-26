import { describe, expect, it } from "vitest";
import { buildSourceDetail } from "./sourceDetail";

describe("buildSourceDetail (plain-text source attribution, no clickable link)", () => {
  it("appends a valid https URL as plain text", () => {
    expect(buildSourceDetail("SEC EDGAR", "https://www.sec.gov/x-index.htm"))
      .toBe("SEC EDGAR — https://www.sec.gov/x-index.htm");
  });

  it("appends a valid http URL", () => {
    expect(buildSourceDetail("ECB", "http://example.org/a")).toBe("ECB — http://example.org/a");
  });

  it("omits missing / empty / whitespace URLs (treated as absent)", () => {
    expect(buildSourceDetail("Fed", null)).toBe("Fed");
    expect(buildSourceDetail("Fed", undefined)).toBe("Fed");
    expect(buildSourceDetail("Fed", "")).toBe("Fed");
    expect(buildSourceDetail("Fed", "   ")).toBe("Fed");
  });

  it("rejects non-http(s) / untrusted URL strings (never trusted)", () => {
    expect(buildSourceDetail("X", "javascript:alert(1)")).toBe("X");
    expect(buildSourceDetail("X", "ftp://h/x")).toBe("X");
    expect(buildSourceDetail("X", "not a url")).toBe("X");
    expect(buildSourceDetail("X", "//evil.com")).toBe("X");
    expect(buildSourceDetail("X", "data:text/html,evil")).toBe("X");
  });

  it("returns a plain string with no anchor/markup (policy: never a clickable link)", () => {
    const out = buildSourceDetail("SEC EDGAR", "https://sec.gov/x");
    expect(typeof out).toBe("string");
    expect(out.toLowerCase()).not.toContain("<a");
    expect(out.toLowerCase()).not.toContain("href");
  });
});
