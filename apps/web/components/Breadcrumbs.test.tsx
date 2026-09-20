/**
 * Global <Breadcrumbs/> route suppression (2026-09-20) — complements
 * app/opportunity-radar/[id]/page.test.tsx, which proves the route's OWN
 * <StaticBreadcrumbs> output has exactly one BreadcrumbList. This proves
 * the OTHER half: the global, auto-derived <Breadcrumbs/> (rendered once
 * in the root layout for every page) actually steps aside on an
 * opportunity-radar detail route instead of emitting a second, competing
 * schema with the raw humanized slug — the real bug this whole fix closes.
 */
import { describe, expect, it, vi, afterEach } from "vitest";
import { render } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { usePathname } from "next/navigation";
import { Breadcrumbs } from "./Breadcrumbs";

vi.mock("next/navigation", () => ({ usePathname: vi.fn() }));

afterEach(() => {
  vi.restoreAllMocks();
});

describe("Breadcrumbs — server-rendered-route suppression", () => {
  it("renders nothing on an opportunity-radar detail route (V2 slug)", () => {
    vi.mocked(usePathname).mockReturnValue("/opportunity-radar/adani-s-2500mw-rtc-power-ppa-execution-catalyst-96b5d32b");
    const { container } = render(<Breadcrumbs />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing on an opportunity-radar detail route (V1 numeric id)", () => {
    vi.mocked(usePathname).mockReturnValue("/opportunity-radar/406");
    const { container } = render(<Breadcrumbs />);
    expect(container).toBeEmptyDOMElement();
  });

  it("still renders normally on the bare opportunity-radar list page", () => {
    vi.mocked(usePathname).mockReturnValue("/opportunity-radar");
    const { container } = render(<Breadcrumbs />);
    expect(container).not.toBeEmptyDOMElement();
  });

  it("still renders normally on an unrelated route", () => {
    vi.mocked(usePathname).mockReturnValue("/newsroom");
    const { container } = render(<Breadcrumbs />);
    expect(container).not.toBeEmptyDOMElement();
  });
});
