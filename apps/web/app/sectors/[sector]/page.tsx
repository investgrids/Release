import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { API_BASE_URL as API } from "@/lib/api";
import { AskAICta } from "@/components/AskAICta";

/**
 * Sector landing page (SEO Phase 2, §2.1 — the single largest programmatic-
 * SEO gap identified in the audit: real sector data was used throughout
 * the product but had no dedicated, indexable URL of its own). Server
 * Component from the start — no client-fetch SSR gap to retrofit here,
 * unlike the Phase 1 pages. Every field comes from /api/sectors/{id}/
 * intelligence, itself a pure aggregation of existing tables (see
 * sectors.py's own docstring) — no new intelligence generated.
 */

const SITE = process.env.NEXT_PUBLIC_SITE_URL ?? "https://marketripple.in";

interface SectorStock { symbol: string; name: string; price: string; change: string; positive: boolean }
interface SectorOpportunity { id: number; slug: string; title: string; opportunity_score: number | null; confidence: number | null }
interface SectorEvent { id: string; title: string; impact_score: number | null; date: string | null }
interface SectorIntelligence {
  id: string; name: string;
  // null for sectors with real constituent stocks + opportunities/events
  // but no live-momentum SectorData row (e.g. Defence, Chemicals, Telecom,
  // Finance) — an honest "no live index for this one" rather than a
  // fabricated 0%.
  value: string | null; positive: boolean | null;
  stocks: SectorStock[]; opportunities: SectorOpportunity[]; events: SectorEvent[];
}

async function fetchSector(sector: string): Promise<SectorIntelligence | null> {
  try {
    const res = await fetch(`${API}/api/sectors/${sector}/intelligence`, { next: { revalidate: 300 } });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function generateMetadata({ params }: { params: Promise<{ sector: string }> }): Promise<Metadata> {
  const { sector } = await params;
  const url = `${SITE}/sectors/${sector}`;
  const d = await fetchSector(sector);
  if (!d) return { title: "Sector — MarketRipple", alternates: { canonical: url } };
  const desc = `${d.name} sector on NSE${d.value ? ` — live performance (${d.value})` : ""}, constituent stocks, and AI-driven opportunity and event analysis on MarketRipple.`;
  return {
    title: `${d.name} Sector — AI Analysis`,
    description: desc,
    openGraph: { type: "website", title: `${d.name} Sector — MarketRipple`, description: desc, url, siteName: "MarketRipple" },
    twitter: { card: "summary_large_image", title: `${d.name} Sector`, description: desc },
    alternates: { canonical: url },
  };
}

export default async function SectorPage({ params }: { params: Promise<{ sector: string }> }) {
  const { sector } = await params;
  const d = await fetchSector(sector);
  if (!d) notFound();

  const url = `${SITE}/sectors/${sector}`;
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "CollectionPage",
    name: `${d.name} Sector — MarketRipple`,
    url,
    breadcrumb: {
      "@type": "BreadcrumbList",
      itemListElement: [
        { "@type": "ListItem", position: 1, name: "MarketRipple", item: SITE },
        { "@type": "ListItem", position: 2, name: "Sectors", item: `${SITE}/sectors` },
        { "@type": "ListItem", position: 3, name: `${d.name} Sector`, item: url },
      ],
    },
    mainEntity: {
      "@type": "ItemList",
      itemListElement: d.stocks.map((s, i) => ({
        "@type": "ListItem", position: i + 1, name: s.name,
        url: `${SITE}/companies/${s.symbol}`,
      })),
    },
  };

  return (
    <main className="mx-auto max-w-[1400px] space-y-6 px-6 py-6 pb-16">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />

      <nav className="flex items-center gap-2 text-[12px] text-slate-500">
        <Link href="/sectors" className="hover:text-slate-300 transition">Sectors</Link>
        <span>/</span>
        <span className="text-slate-400">{d.name}</span>
      </nav>

      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-[11px] font-bold uppercase tracking-[0.2em] text-sky-400">Sector Intelligence</p>
          <h1 className="mt-2 text-3xl font-black tracking-tight text-white">{d.name} Sector</h1>
          <p className="mt-1 text-sm text-slate-400">
            Live NSE {d.name} sector performance, constituent stocks, and AI-driven opportunity and event analysis.
          </p>
        </div>
        {d.value ? (
          <div className={`rounded-2xl border px-5 py-3 ${d.positive ? "bg-emerald-500/10 border-emerald-500/20" : "bg-rose-500/10 border-rose-500/20"}`}>
            <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-500">Today</p>
            <p className={`mt-1 text-2xl font-black ${d.positive ? "text-emerald-300" : "text-rose-300"}`}>{d.value}</p>
          </div>
        ) : (
          <div className="rounded-2xl border border-white/10 bg-white/[0.03] px-5 py-3">
            <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-500">Companies</p>
            <p className="mt-1 text-2xl font-black text-white">{d.stocks.length}</p>
          </div>
        )}
      </div>

      {/* Constituent stocks */}
      {d.stocks.length > 0 && (
        <section>
          <h2 className="mb-3 text-[15px] font-semibold text-white">Companies in {d.name}</h2>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {d.stocks.map((s) => (
              <Link key={s.symbol} href={`/companies/${s.symbol}`}
                className="group flex items-center justify-between rounded-[16px] border border-white/[0.08] bg-[#0c1422] px-4 py-3 transition hover:border-white/[0.15]">
                <div>
                  <p className="text-[13px] font-bold text-white">{s.symbol}</p>
                  <p className="text-[11px] text-slate-500">{s.price !== "—" ? `₹${s.price.replace("₹", "")}` : "—"}</p>
                </div>
                <span className={`text-[12px] font-semibold tabular-nums ${s.positive ? "text-emerald-400" : "text-rose-400"}`}>{s.change}</span>
              </Link>
            ))}
          </div>
        </section>
      )}

      {/* Opportunities + Events */}
      <div className="grid gap-6 lg:grid-cols-2">
        <section>
          <h2 className="mb-3 text-[15px] font-semibold text-white">Opportunities in {d.name}</h2>
          {d.opportunities.length > 0 ? (
            <div className="space-y-2">
              {d.opportunities.map((o) => (
                <Link key={o.id} href={`/opportunity-radar/${o.id}`}
                  className="flex items-center justify-between rounded-[14px] border border-white/[0.07] bg-white/[0.02] px-4 py-3 transition hover:border-emerald-500/25">
                  <p className="text-[13px] text-slate-200 line-clamp-1">{o.title}</p>
                  {o.opportunity_score != null && (
                    <span className="shrink-0 rounded-full bg-emerald-500/10 px-2 py-0.5 text-[11px] font-bold text-emerald-300">{Math.round(o.opportunity_score)}</span>
                  )}
                </Link>
              ))}
            </div>
          ) : (
            <p className="text-[12px] text-slate-500">No sector-specific opportunities identified right now.</p>
          )}
        </section>
        <section>
          <h2 className="mb-3 text-[15px] font-semibold text-white">Recent Events Affecting {d.name}</h2>
          {d.events.length > 0 ? (
            <div className="space-y-2">
              {d.events.map((e) => (
                <Link key={e.id} href={`/events/${e.id}`}
                  className="flex items-center justify-between rounded-[14px] border border-white/[0.07] bg-white/[0.02] px-4 py-3 transition hover:border-violet-500/25">
                  <p className="text-[13px] text-slate-200 line-clamp-1">{e.title}</p>
                  {e.impact_score != null && (
                    <span className="shrink-0 rounded-full bg-violet-500/10 px-2 py-0.5 text-[11px] font-bold text-violet-300">{Math.round(e.impact_score)}</span>
                  )}
                </Link>
              ))}
            </div>
          ) : (
            <p className="text-[12px] text-slate-500">No recent events specifically affecting {d.name} right now.</p>
          )}
        </section>
      </div>

      <div className="rounded-[16px] border border-violet-500/20 bg-violet-500/[0.04] px-5 py-4">
        <p className="text-[13px] text-slate-300">
          Want a deeper read on {d.name}?{" "}
          <AskAICta query={`What is the outlook for the ${d.name} sector?`} source="sector_page" />
        </p>
      </div>
    </main>
  );
}
