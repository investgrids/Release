import { describe, expect, it, vi, afterEach } from "vitest";
import LegacyThemeRedirect from "./page";

const notFoundMock = vi.fn(() => {
  throw new Error("NEXT_NOT_FOUND");
});
const permanentRedirectMock = vi.fn((_url: string) => {
  throw new Error("NEXT_REDIRECT");
});

vi.mock("next/navigation", () => ({
  notFound: () => notFoundMock(),
  permanentRedirect: (url: string) => permanentRedirectMock(url),
}));

function mockFetchOnce(items: unknown[]) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ ok: true, json: async () => ({ items }) }),
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  notFoundMock.mockClear();
  permanentRedirectMock.mockClear();
});

describe("Legacy /newsroom/themes/[slug] -- pure redirect layer (Batch G, 2026-09-20)", () => {
  it("permanently redirects a provably-mapped legacy opportunity slug to its real canonical /opportunity-radar/{id}", async () => {
    mockFetchOnce([{ id: 406, slug: "real-legacy-opportunity-slug" }]);

    await expect(
      LegacyThemeRedirect({ params: Promise.resolve({ slug: "real-legacy-opportunity-slug" }) }),
    ).rejects.toThrow("NEXT_REDIRECT");

    expect(permanentRedirectMock).toHaveBeenCalledWith("/opportunity-radar/406");
    expect(notFoundMock).not.toHaveBeenCalled();
  });

  it("returns a real 404 for an unknown slug -- never a guessed redirect target", async () => {
    mockFetchOnce([{ id: 406, slug: "some-other-real-slug" }]);

    await expect(
      LegacyThemeRedirect({ params: Promise.resolve({ slug: "this-slug-has-never-existed" }) }),
    ).rejects.toThrow("NEXT_NOT_FOUND");

    expect(notFoundMock).toHaveBeenCalled();
    expect(permanentRedirectMock).not.toHaveBeenCalled();
  });

  it("returns a real 404 when the upstream list fetch itself fails, never a fabricated redirect", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network down")));

    await expect(
      LegacyThemeRedirect({ params: Promise.resolve({ slug: "any-slug" }) }),
    ).rejects.toThrow("NEXT_NOT_FOUND");

    expect(notFoundMock).toHaveBeenCalled();
    expect(permanentRedirectMock).not.toHaveBeenCalled();
  });
});
