import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { WhatToWatchNext } from "./WhatToWatchNext";
import type { WatchItem } from "@/lib/whatToWatchNext";

const CONDITION: WatchItem = { kind: "condition", entity: "Bank Nifty", detail: "Whether today's weakness recovers" };
const TRIGGER: WatchItem = { kind: "trigger", entity: "RBI liquidity data", detail: "2:30 PM", meta: "monetary_policy" };

describe("WhatToWatchNext — Homepage Hero component (2026-09-03)", () => {
  // ── 9. Component hides gracefully when there is no trustworthy input ────
  it("renders nothing (no placeholder card) when items is empty", () => {
    const { container } = render(<WhatToWatchNext items={[]} />);
    expect(container).toBeEmptyDOMElement();
    expect(screen.queryByText(/no data/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/no watch items/i)).not.toBeInTheDocument();
  });

  it("renders a single valid item in compact form rather than hiding or padding", () => {
    render(<WhatToWatchNext items={[CONDITION]} />);
    expect(screen.getByText("What To Watch Next")).toBeInTheDocument();
    expect(screen.getByText("Bank Nifty")).toBeInTheDocument();
    expect(screen.getByText("Whether today's weakness recovers")).toBeInTheDocument();
  });

  it("renders both a trigger item and a condition item with their own detail styling", () => {
    render(<WhatToWatchNext items={[TRIGGER, CONDITION]} />);
    expect(screen.getByText("RBI liquidity data")).toBeInTheDocument();
    expect(screen.getByText("2:30 PM")).toBeInTheDocument();
    expect(screen.getByText("monetary_policy")).toBeInTheDocument();
    expect(screen.getByText("Bank Nifty")).toBeInTheDocument();
    // "Monitor" badge only on the condition item, not the trigger.
    expect(screen.getByText("Monitor")).toBeInTheDocument();
  });

  it("caps visual rendering at whatever the caller passed — never renders a 5th row from 4 items", () => {
    const items: WatchItem[] = [
      { kind: "condition", entity: "Bank Nifty", detail: "Whether today's weakness recovers" },
      { kind: "condition", entity: "Brent Crude", detail: "Whether today's decline reverses" },
      { kind: "condition", entity: "USD/INR", detail: "Whether rupee strength persists" },
      { kind: "condition", entity: "US Futures", detail: "Whether weakness persists into the US session" },
    ];
    render(<WhatToWatchNext items={items} />);
    expect(screen.getAllByText("Monitor")).toHaveLength(4);
  });

  // Never uses directional (emerald/rose) coloring on the monitoring items
  // themselves — the task's explicit rule: "Do NOT use green/red
  // directional colors for these items unless displaying an actual
  // observed numeric movement" (this component never renders one).
  it("never applies emerald/rose directional color classes to condition rows", () => {
    const items: WatchItem[] = [CONDITION, { kind: "condition", entity: "Brent Crude", detail: "Whether today's rise continues" }];
    const { container } = render(<WhatToWatchNext items={items} />);
    expect(container.querySelectorAll(".text-emerald-400, .text-rose-400").length).toBe(0);
  });

  // ── 10. Mobile layout remains valid ──────────────────────────────────────
  // JSDOM has no real layout engine, so this asserts what's actually
  // checkable statically: the component never introduces fixed pixel
  // widths or a horizontal-scroll container, matching the hero's existing
  // sibling cards (Since Previous Session / Opportunity-Risk strip), which
  // already stack correctly under the page's responsive grid with no
  // component-level breakpoint logic of their own.
  it("introduces no horizontal-scroll or fixed-width markup", () => {
    const { container } = render(<WhatToWatchNext items={[CONDITION, TRIGGER]} />);
    const html = container.innerHTML;
    expect(html).not.toMatch(/overflow-x-auto/);
    expect(html).not.toMatch(/min-w-\[\d+px\]/);
    expect(container.querySelector("[style*='width']")).toBeNull();
  });
});
