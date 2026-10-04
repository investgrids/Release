"use client";

// Candlestick + volume price chart (TradingView lightweight-charts, ~45 kB). Loaded with next/dynamic, client-only, so the
// library is only fetched when a visitor switches the price chart to Candle view.
import { useCallback, useEffect, useRef } from "react";
import type { IChartApi } from "lightweight-charts";
import { CandlestickSeries, ColorType, CrosshairMode, HistogramSeries, createChart } from "lightweight-charts";
import { toCandleData, type ChartRow } from "@/lib/candles";

const UP = "#22c55e";
const DOWN = "#f43f5e";

// The site themes are CSS variables holding space separated RGB channels ("15 23 42"): turn one into a colour string.
function themeColor(name: string, alpha = 1, fallback = "128,128,128"): string {
  try {
    const raw = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    const ch = raw ? raw.split(/\s+/).join(",") : fallback;
    return `rgba(${ch},${alpha})`;
  } catch {
    return `rgba(${fallback},${alpha})`;
  }
}

export function CandleChart({ chartData, intraday }: { chartData: ChartRow[]; intraday: boolean }) {
  const host = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);

  // Zoom around the middle of what is on screen. Mouse wheel, drag-to-pan and pinch are also on (library defaults).
  const zoom = useCallback((factor: number) => {
    const ts = chartRef.current?.timeScale();
    const r = ts?.getVisibleLogicalRange();
    if (!ts || !r) return;
    const mid = (r.from + r.to) / 2;
    const half = Math.max((r.to - r.from) / 2 * factor, 3);   // never fewer than ~6 bars on screen
    ts.setVisibleLogicalRange({ from: mid - half, to: mid + half });
  }, []);
  const reset = useCallback(() => chartRef.current?.timeScale().fitContent(), []);

  useEffect(() => {
    const el = host.current;
    if (!el) return;
    const { candles, volumes } = toCandleData(chartData, UP, DOWN);
    const text = themeColor("--text-muted", 1, "120,120,120");
    const grid = themeColor("--text-primary", 0.06, "128,128,128");
    const chart = createChart(el, {
      autoSize: true,
      layout: { background: { type: ColorType.Solid, color: "transparent" }, textColor: text, fontSize: 10, attributionLogo: false },
      grid: { vertLines: { color: grid }, horzLines: { color: grid } },
      rightPriceScale: { borderVisible: false, scaleMargins: { top: 0.06, bottom: 0.26 } },
      timeScale: { borderVisible: false, timeVisible: intraday, secondsVisible: false, rightOffset: 2 },
      crosshair: { mode: CrosshairMode.Normal },
      localization: { priceFormatter: (p: number) => `₹${p.toLocaleString("en-IN", { maximumFractionDigits: 2 })}` },
    });
    const series = chart.addSeries(CandlestickSeries, {
      upColor: UP, downColor: DOWN, borderUpColor: UP, borderDownColor: DOWN, wickUpColor: UP, wickDownColor: DOWN, priceLineVisible: false,
    });
    series.setData(candles as never);
    if (volumes.length > 0) {
      const vol = chart.addSeries(HistogramSeries, { priceFormat: { type: "volume" }, priceScaleId: "vol", priceLineVisible: false, lastValueVisible: false });
      chart.priceScale("vol").applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } });
      vol.setData(volumes as never);
    }
    chart.timeScale().fitContent();
    chartRef.current = chart;
    return () => { chartRef.current = null; chart.remove(); };
  }, [chartData, intraday]);

  const btn = "h-7 w-7 rounded-lg bg-surface-card/90 text-sm font-semibold text-text-secondary shadow-sm ring-1 ring-text-primary/10 hover:text-text-primary";
  return (
    <div className="relative h-full w-full">
      <div ref={host} className="h-full w-full" role="img" aria-label="Candlestick price chart" />
      <div className="absolute left-2 top-2 z-10 flex gap-1" role="group" aria-label="Chart zoom">
        <button type="button" className={btn} onClick={() => zoom(0.6)} aria-label="Zoom in" title="Zoom in">+</button>
        <button type="button" className={btn} onClick={() => zoom(1.6)} aria-label="Zoom out" title="Zoom out">−</button>
        <button type="button" className={btn} onClick={reset} aria-label="Reset zoom" title="Reset zoom">⟲</button>
      </div>
    </div>
  );
}
