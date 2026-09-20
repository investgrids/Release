import { describe, expect, it, vi, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import ThemesIndexPage, { metadata } from "./page";

function mockFetchOnce(items: unknown[]) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ ok: true, json: async () => ({ items }) }),
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("Theme Intelligence index — Batch G rewrite (2026-09-20)", () => {
  it("has a self-referencing canonical and is genuinely indexable (real, non-duplicate content now)", () => {
    expect(metadata.robots).toEqual({ index: true, follow: true });
    expect((metadata.alternates as any).canonical).toBe("https://www.marketripple.in/newsroom/themes");
  });

  it("fetches published theme_intelligence articles, not V1 opportunity data", async () => {
    mockFetchOnce([]);
    await ThemesIndexPage();
    const calledUrl = (fetch as any).mock.calls[0][0] as string;
    expect(calledUrl).toContain("/api/insights/");
    expect(calledUrl).toContain("article_type=theme_intelligence");
    expect(calledUrl).not.toContain("/api/radar/");
  });

  it("links each real article directly to /newsroom/article/{slug} -- no intermediate redirect", async () => {
    mockFetchOnce([
      {
        slug: "real-theme-article-rss-aa11",
        headline: "Real Theme Headline",
        key_takeaway: "Real key takeaway.",
        executive_summary: null,
        sectors_affected: [{ name: "Banking" }],
        companies_affected: [{ symbol: "HDFCBANK", name: "HDFC Bank" }],
        published_at: "2026-09-20T00:00:00Z",
      },
    ]);
    const el = await ThemesIndexPage();
    render(el);

    const link = screen.getByRole("link", { name: /Real Theme Headline/i });
    expect(link).toHaveAttribute("href", "/newsroom/article/real-theme-article-rss-aa11");
  });

  it("renders no V1 Opportunity fields anywhere (no opportunity_score, confidence, risk_level, trend)", async () => {
    mockFetchOnce([
      {
        slug: "real-theme-article-rss-bb22",
        headline: "Another Real Theme",
        key_takeaway: "Takeaway.",
        executive_summary: null,
        sectors_affected: [],
        companies_affected: [],
        published_at: null,
      },
    ]);
    const el = await ThemesIndexPage();
    render(el);

    expect(screen.queryByText(/risk$/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/confidence/i)).not.toBeInTheDocument();
  });

  it("shows an honest empty state, never a fabricated theme, when nothing is published", async () => {
    mockFetchOnce([]);
    const el = await ThemesIndexPage();
    render(el);
    expect(screen.getByText(/No theme intelligence published right now/i)).toBeInTheDocument();
  });
});
