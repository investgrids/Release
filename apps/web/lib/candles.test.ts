import { describe, expect, it } from "vitest";
import { IST_OFFSET_SECONDS, hasCandles, toCandleData } from "./candles";

const row = (time: number | string, o: number, h: number, l: number, c: number, volume = 100) => ({ label: "x", value: c, time, open: o, high: h, low: l, close: c, volume });

describe("toCandleData", () => {
  it("maps daily rows to candles and colours volume by direction", () => {
    const { candles, volumes } = toCandleData([row("2026-09-29", 100, 105, 98, 103, 1000), row("2026-09-30", 103, 104, 99, 100, 2000)]);
    expect(candles).toEqual([
      { time: "2026-09-29", open: 100, high: 105, low: 98, close: 103 },
      { time: "2026-09-30", open: 103, high: 104, low: 99, close: 100 },
    ]);
    expect(volumes.map(v => v.value)).toEqual([1000, 2000]);
    expect(volumes[0].color.startsWith("#22c55e")).toBe(true);   // up bar
    expect(volumes[1].color.startsWith("#f43f5e")).toBe(true);   // down bar
  });

  it("sorts by time, keeps the last bar of a duplicated time and drops bars with a missing or non-finite price", () => {
    const { candles } = toCandleData([
      row("2026-10-01", 1, 2, 0.5, 1.5), row("2026-09-29", 1, 2, 0.5, 1.2), row("2026-10-01", 1, 3, 0.4, 2.5),
      { time: "2026-09-30", open: null, high: 2, low: 1, close: 1.5 }, { time: "2026-09-28", open: NaN, high: 2, low: 1, close: 1.5 },
    ]);
    expect(candles.map(c => c.time)).toEqual(["2026-09-29", "2026-10-01"]);
    expect(candles[1].close).toBe(2.5);
  });

  it("widens high/low so they always contain open and close", () => {
    const { candles } = toCandleData([row("2026-09-29", 100, 99, 101, 102)]);
    expect(candles[0].high).toBeGreaterThanOrEqual(102);
    expect(candles[0].low).toBeLessThanOrEqual(100);
  });

  it("shifts intraday epoch seconds to IST and leaves date strings alone", () => {
    const { candles } = toCandleData([row(1_790_000_000, 10, 11, 9, 10.5)]);
    expect(candles[0].time).toBe(1_790_000_000 + IST_OFFSET_SECONDS);
  });

  it("reports rows from an older response (close only) as not drawable", () => {
    expect(hasCandles([{ label: "Sep 29", value: 100 }])).toBe(false);
    expect(hasCandles([row("2026-09-29", 1, 2, 0.5, 1.5)])).toBe(true);
    expect(hasCandles([])).toBe(false);
  });

  it("omits volume bars with no volume", () => {
    expect(toCandleData([row("2026-09-29", 1, 2, 0.5, 1.5, 0)]).volumes).toEqual([]);
  });
});
