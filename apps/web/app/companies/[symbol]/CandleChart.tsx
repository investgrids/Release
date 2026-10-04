"use client";

// Candlestick + volume price chart (TradingView lightweight-charts, ~45 kB). Loaded with next/dynamic, client-only, so the
// library is only fetched when a visitor switches the price chart to Candle view.
import { useEffect, useRef } from "react";
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
    return () => chart.remove();
  }, [chartData, intraday]);

  return <div ref={host} className="h-full w-full" role="img" aria-label="Candlestick price chart" />;
}
