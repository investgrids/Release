import { describe, expect, it } from "vitest";
import { isWeekendSession } from "./weekendSession";

/**
 * Brief §38 — Session switch tests. Each scenario maps to the exact
 * real value apps/backend/app/api/market.py's market_session() returns
 * for that day/time (verified against the live backend source — see
 * weekendSession.ts's own docstring). This tests OUR interpretation of
 * that value, not the backend's day-of-week arithmetic (already tested
 * backend-side).
 */
describe("isWeekendSession", () => {
  it("Saturday -> weekend homepage", () => {
    expect(isWeekendSession({ session: "weekend" })).toBe(true);
  });

  it("Sunday -> weekend homepage", () => {
    expect(isWeekendSession({ session: "weekend" })).toBe(true);
  });

  it("Monday pre-market -> normal homepage", () => {
    expect(isWeekendSession({ session: "pre_market" })).toBe(false);
  });

  it("Monday pre-open (9:00-9:15 IST) -> normal homepage", () => {
    expect(isWeekendSession({ session: "pre_open" })).toBe(false);
  });

  it("Monday market-open -> normal homepage", () => {
    expect(isWeekendSession({ session: "open" })).toBe(false);
  });

  it("weekday after-market -> normal homepage", () => {
    expect(isWeekendSession({ session: "after_market" })).toBe(false);
  });

  it("null session response -> normal homepage (fail safe, never blank-screens on a backend hiccup)", () => {
    expect(isWeekendSession(null)).toBe(false);
  });

  it("undefined session field -> normal homepage", () => {
    expect(isWeekendSession({})).toBe(false);
  });

  it("unrecognized session value -> normal homepage (never assume weekend)", () => {
    expect(isWeekendSession({ session: "something_new_and_unexpected" })).toBe(false);
  });
});
