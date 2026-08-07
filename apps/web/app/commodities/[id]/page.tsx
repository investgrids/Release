import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft, TrendingUp, TrendingDown } from "lucide-react";
import { getCommodities, findCommodity, weekTrend } from "@/lib/commodities";

const SITE = process.env.NEXT_PUBLIC_SITE_URL ?? "https://www.marketripple.in";

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }): Promise<Metadata> {
  const { id } = await params;
  const url = `${SITE}/commodities/${id}`;
  const data = await getCommodities();
  const found = data ? findCommodity(data, id) : null;
  if (!found) return { title: "Commodity Not Found", alternates: { canonical: url } };
  const { item } = found;
  const title = `${item.name} Price Today — Live ${item.unit}`;
  const description = `Live ${item.name} price: ${item.price} ${item.unit}, ${item.change} (${item.pct >= 0 ? "+" : ""}${item.pct}%) today, with a real 7-day trend chart.`;
  return {
    title,
    description,
    openGraph: {
      type: "website", title, description, url, siteName: "MarketRipple",
      images: [{ url: "/opengraph-image", width: 1200, height: 630, alt: "MarketRipple — AI-Powered Market Intelligence" }],
    },
    twitter: { card: "summary", title, description, images: ["/opengraph-image"] },
    alternates: { canonical: url },
  };
}

export default async function CommodityDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const data = await getCommodities();
  const found = data ? findCommodity(data, id) : null;
  if (!data || !found) notFound();

  const { item, group } = found;
  const trend = weekTrend(item.chart);
  const groupInsight = data.insights?.[group];
  const showInsight = !data.insights?.degraded && groupInsight;

  const maxVal = Math.max(...item.chart.map(c => c.value), 0);
  const minVal = Math.min(...item.chart.map(c => c.value), maxVal);
  const range = maxVal - minVal || 1;

  return (
    <main className="mx-auto max-w-[760px] px-5 py-8 pb-16 sm:px-6">
      <nav className="mb-5 flex items-center gap-2 text-[12px] text-text-muted">
        <Link href="/commodities" className="flex items-center gap-1 hover:text-text-secondary transition">
          <ArrowLeft className="h-3 w-3" /> Commodities
        </Link>
      </nav>

      <h1 className="text-[28px] font-black leading-tight text-text-primary md:text-[34px]">{item.name} Price Today</h1>
      <p className="mt-1 text-[12px] text-text-muted">{item.unit}</p>

      <div className="mt-6 flex items-end gap-4">
        <span className="text-[40px] font-black tabular-nums text-text-primary">{item.price}</span>
        <span className={`mb-1.5 flex items-center gap-1 text-[16px] font-bold tabular-nums ${item.positive ? "text-emerald-400" : "text-rose-400"}`}>
          {item.positive ? <TrendingUp className="h-4 w-4" /> : <TrendingDown className="h-4 w-4" />}
          {item.change} ({item.positive ? "+" : ""}{item.pct.toFixed(2)}%)
        </span>
      </div>

      <div className="mt-6 grid grid-cols-2 gap-3 rounded-2xl border border-surface-border/8 bg-text-primary/[0.03] p-5 sm:grid-cols-3">
        <div>
          <p className="text-[9px] font-bold uppercase tracking-widest text-text-muted">Day High</p>
          <p className="mt-1 text-[16px] font-black text-text-primary">{item.high}</p>
        </div>
        <div>
          <p className="text-[9px] font-bold uppercase tracking-widest text-text-muted">Day Low</p>
          <p className="mt-1 text-[16px] font-black text-text-primary">{item.low}</p>
        </div>
        {trend && (
          <div>
            <p className="text-[9px] font-bold uppercase tracking-widest text-text-muted">7-Day Trend</p>
            <p className={`mt-1 text-[16px] font-black tabular-nums ${trend.positive ? "text-emerald-400" : "text-rose-400"}`}>
              {trend.positive ? "+" : ""}{trend.pct.toFixed(2)}%
            </p>
          </div>
        )}
      </div>

      {item.chart.length >= 2 && (
        <section className="mt-8">
          <h2 className="mb-3 text-[11px] font-bold uppercase tracking-widest text-text-muted">7-Day Price Trend</h2>
          <div className="flex h-32 gap-2 rounded-xl border border-surface-border/6 bg-text-primary/[0.02] p-4">
            {item.chart.map((c, i) => {
              const heightPct = Math.max(8, ((c.value - minVal) / range) * 100);
              return (
                // h-full (not the parent's `items-end`) is what makes the
                // bar's percentage height resolve against something real —
                // a flex item with no explicit height has an auto/content
                // height, so `height: X%` on its child collapses to 0.
                // Caught in local screenshot review: the chart rendered
                // with visible date labels but completely invisible bars.
                <div key={i} className="flex h-full flex-1 flex-col items-center justify-end gap-1.5">
                  <div
                    className={`w-full rounded-t ${item.positive ? "bg-emerald-500/60" : "bg-rose-500/60"}`}
                    style={{ height: `${heightPct}%` }}
                  />
                  <span className="text-[8px] text-text-muted">{c.label}</span>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {showInsight && groupInsight && (
        <section className="mt-8">
          <h2 className="mb-3 text-[11px] font-bold uppercase tracking-widest text-text-muted">
            {group === "metals" ? "Metals" : "Energy"} Market Impact — {groupInsight.impact}
          </h2>
          <div className="space-y-2">
            {groupInsight.items.map((it, i) => (
              <div key={i} className="rounded-xl border border-surface-border/6 bg-text-primary/[0.02] p-3.5">
                <p className="text-[13px] leading-relaxed text-text-secondary">{it.text}</p>
                <p className="mt-1 text-[10px] font-semibold uppercase tracking-wide text-amber-500/70">{it.impact}</p>
              </div>
            ))}
          </div>
          {/* This context is group-level (all metals, or all energy), not
              specific to this one commodity — labeled honestly rather than
              implying it's {item.name}-specific analysis. */}
          <p className="mt-2 text-[10px] text-text-muted">Context for the broader {group} group, not {item.name}-specific.</p>
        </section>
      )}

      <div className="mt-10 border-t border-surface-border/6 pt-5">
        <Link href="/commodities" className="text-[12px] font-semibold text-sky-400 hover:text-sky-600 dark:text-sky-300 transition">← All Commodities</Link>
      </div>
    </main>
  );
}
