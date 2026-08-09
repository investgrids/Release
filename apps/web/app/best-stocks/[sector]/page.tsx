import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft, TrendingUp, TrendingDown, Activity } from "lucide-react";
import { getRankedCompaniesForSector, getSectorsWithCounts } from "@/lib/bestStocks";
import { safeJsonLd } from "@/lib/text";

const SITE = process.env.NEXT_PUBLIC_SITE_URL ?? "https://www.marketripple.in";

const TREND_ICON: Record<string, typeof TrendingUp> = { up: TrendingUp, down: TrendingDown };

async function resolveSector(slug: string): Promise<string | null> {
  const sectors = await getSectorsWithCounts();
  return sectors.find(s => s.slug === slug)?.sector ?? null;
}

export async function generateMetadata({ params }: { params: Promise<{ sector: string }> }): Promise<Metadata> {
  const { sector: slug } = await params;
  const url = `${SITE}/best-stocks/${slug}`;
  const sector = await resolveSector(slug);
  if (!sector) return { title: "Sector Not Found", alternates: { canonical: url } };
  const title = `Best ${sector} Stocks Right Now — Ranked by Real Opportunity Score`;
  const description = `Which ${sector} stocks are best positioned right now, ranked by MarketRipple's AI Company Intelligence Score — real signals from published analysis and Opportunity Radar — with the actual reason behind each ranking.`;
  return {
    title,
    description,
    openGraph: { type: "article", title, description, url, siteName: "MarketRipple" },
    twitter: { card: "summary_large_image", title, description },
    alternates: { canonical: url },
  };
}

const IMPACT_STYLE: Record<string, string> = {
  "Very High": "text-emerald-400 border-emerald-500/25 bg-emerald-500/10",
  High: "text-emerald-400 border-emerald-500/20 bg-emerald-500/5",
  Medium: "text-amber-400 border-amber-500/20 bg-amber-500/5",
  Low: "text-text-secondary border-surface-border/10 bg-text-primary/5",
};

export default async function BestStocksSectorPage({ params }: { params: Promise<{ sector: string }> }) {
  const { sector: slug } = await params;
  const sector = await resolveSector(slug);
  if (!sector) notFound();

  const companies = await getRankedCompaniesForSector(sector);
  if (companies.length < 3) notFound(); // thin-content guard, mirrors the hub's own filter

  const url = `${SITE}/best-stocks/${slug}`;
  const faqs = [
    {
      q: `What are the best ${sector} stocks right now?`,
      a: `Based on MarketRipple's AI Company Intelligence Score, the top-ranked ${sector} names right now are ${companies.slice(0, 3).map(c => c.name).join(", ")} — each backed by real signals from published analysis and Opportunity Radar.`,
    },
    {
      q: `Why is ${companies[0].name} the top-ranked ${sector} stock?`,
      a: companies[0].reason || `${companies[0].name} carries the highest AI Company Intelligence Score among ${sector} stocks tracked by MarketRipple.`,
    },
  ];

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": ["Article", "FAQPage"],
    headline: `Best ${sector} Stocks Right Now`,
    description: `Real, opportunity-scored ${sector} stock rankings from MarketRipple.`,
    author: { "@type": "Organization", name: "MarketRipple AI Intelligence Engine" },
    publisher: { "@type": "Organization", name: "MarketRipple" },
    mainEntityOfPage: url,
    breadcrumb: {
      "@type": "BreadcrumbList",
      itemListElement: [
        { "@type": "ListItem", position: 1, name: "MarketRipple", item: SITE },
        { "@type": "ListItem", position: 2, name: "Best Stocks", item: `${SITE}/best-stocks` },
        { "@type": "ListItem", position: 3, name: `Best ${sector} Stocks`, item: url },
      ],
    },
    mainEntity: faqs.map(f => ({ "@type": "Question", name: f.q, acceptedAnswer: { "@type": "Answer", text: f.a } })),
  };

  return (
    <main className="mx-auto max-w-[900px] py-8 pb-16">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: safeJsonLd(jsonLd) }} />

      <nav className="mb-5 flex items-center gap-2 text-[12px] text-text-muted">
        <Link href="/best-stocks" className="flex items-center gap-1 hover:text-text-secondary transition">
          <ArrowLeft className="h-3 w-3" /> Best Stocks
        </Link>
      </nav>

      <h1 className="text-[28px] font-black leading-tight text-text-primary md:text-[34px]">
        Best {sector} Stocks Right Now
      </h1>
      <p className="mt-3 max-w-[640px] text-[14px] leading-relaxed text-text-secondary">
        Ranked by MarketRipple&apos;s AI Company Intelligence Score — real signals from published
        analysis and Opportunity Radar, ties each company to the actual reason behind its ranking.
      </p>

      <div className="mt-8 space-y-2.5">
        {companies.slice(0, 15).map((c, i) => {
          const TrendIcon = TREND_ICON[c.trend] ?? Activity;
          const trendCls = c.trend === "up" ? "text-emerald-400" : c.trend === "down" ? "text-rose-400" : "text-text-muted";
          return (
            <div key={c.symbol} className="flex items-start gap-4 rounded-xl border border-surface-border/6 bg-text-primary/[0.02] p-4">
              <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-text-primary/[0.07] text-[11px] font-black text-text-secondary">
                {i + 1}
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <Link href={`/companies/${c.symbol}`} className="text-[15px] font-bold text-text-primary hover:text-emerald-600 dark:text-emerald-300 transition">
                    {c.name}
                  </Link>
                  <span className="text-[11px] text-text-muted">{c.symbol}</span>
                  {c.impactLabel && (
                    <span className={`rounded-full border px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider ${IMPACT_STYLE[c.impactLabel] ?? IMPACT_STYLE.Low}`}>
                      {c.impactLabel} Impact
                    </span>
                  )}
                </div>
                {c.reason && <p className="mt-1 text-[12.5px] leading-relaxed text-text-secondary">{c.reason}</p>}
                <p className="mt-1 text-[10.5px] text-text-muted">From: {c.fromOpportunity}</p>
              </div>
              <div className="shrink-0 text-right">
                <p className="flex items-center justify-end gap-1 text-[16px] font-black tabular-nums text-text-primary">
                  <TrendIcon className={`h-3.5 w-3.5 ${trendCls}`} /> {Math.round(c.impactScore)}
                </p>
                <p className="text-[9px] uppercase tracking-wide text-text-muted">Score</p>
              </div>
            </div>
          );
        })}
      </div>

      <section className="mt-10">
        <h2 className="mb-3 text-[11px] font-bold uppercase tracking-widest text-text-muted">Frequently Asked</h2>
        <div className="space-y-2">
          {faqs.map((f, i) => (
            <details key={i} className="group rounded-xl border border-surface-border/6 bg-text-primary/[0.02] p-4">
              <summary className="cursor-pointer text-[13px] font-semibold text-text-primary">{f.q}</summary>
              <p className="mt-2 text-[13px] leading-relaxed text-text-secondary">{f.a}</p>
            </details>
          ))}
        </div>
      </section>

      <div className="mt-10 flex items-center justify-between border-t border-surface-border/6 pt-5">
        <Link href="/best-stocks" className="text-[12px] font-semibold text-sky-400 hover:text-sky-600 dark:text-sky-300 transition">← All Sectors</Link>
        <Link href="/opportunity-radar" className="text-[12px] font-semibold text-text-muted hover:text-text-secondary transition">Full Opportunity Radar →</Link>
      </div>
    </main>
  );
}
