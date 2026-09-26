import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { fetchAPI } from "@/lib/api";
import { sectorSlug } from "@/lib/bestStocks";

/**
 * Company Rankings migration (2026-09-26) — this page used to rank every
 * sector by the older AI Company Score. Banking now redirects to the real
 * Company Rankings page (next.config.ts: /best-stocks/banking ->
 * /companies?tab=company-rankings) rather than duplicate it. Every other
 * sector has no approved MarketRipple Score methodology, so this page now
 * shows that honestly and lets the real company list for the sector stay
 * fully browsable — never a fallback to the retired score.
 */

const SITE = process.env.NEXT_PUBLIC_SITE_URL ?? "https://www.marketripple.in";

interface CompanyRow {
  symbol: string; name: string; sector: string; industry?: string | null;
  cap?: "large" | "mid" | "small" | null; price?: number | null; pct?: number | null; positive?: boolean | null;
}

async function resolveSector(slug: string): Promise<string | null> {
  const data = await fetchAPI<{ sectors: string[] }>("/api/companies/sectors").catch(() => null);
  return data?.sectors.find(s => sectorSlug(s) === slug) ?? null;
}

export async function generateMetadata({ params }: { params: Promise<{ sector: string }> }): Promise<Metadata> {
  const { sector: slug } = await params;
  const url = `${SITE}/best-stocks/${slug}`;
  const sector = await resolveSector(slug);
  if (!sector) return { title: "Sector Not Found", alternates: { canonical: url } };
  const title = `${sector} Companies on NSE — Browse the Full List`;
  const description = `Browse all ${sector} companies on NSE. MarketRipple Score is not yet available for this sector — Banking is the only sector with an approved scoring methodology today.`;
  return { title, description, alternates: { canonical: url } };
}

export default async function BestStocksSectorPage({ params }: { params: Promise<{ sector: string }> }) {
  const { sector: slug } = await params;
  const sector = await resolveSector(slug);
  if (!sector) notFound();

  const data = await fetchAPI<{ companies: CompanyRow[]; total: number }>(
    `/api/companies/?sector=${encodeURIComponent(sector)}&page_size=50&live=true`
  ).catch(() => null);
  const companies = data?.companies ?? [];

  return (
    <main className="mx-auto max-w-[900px] py-8 pb-16">
      <nav className="mb-5 flex items-center gap-2 text-[12px] text-text-muted">
        <Link href="/companies?tab=company-rankings" className="flex items-center gap-1 hover:text-text-secondary transition">
          <ArrowLeft className="h-3 w-3" /> Company Rankings
        </Link>
      </nav>

      <h1 className="text-[28px] font-black leading-tight text-text-primary md:text-[34px]">{sector} Companies</h1>

      <div className="mt-4 rounded-2xl border border-amber-500/20 bg-amber-500/[0.04] p-4">
        <p className="text-[13px] font-semibold text-text-primary">MarketRipple Score is not yet available for this sector.</p>
        <p className="mt-1 text-[12.5px] leading-relaxed text-text-secondary">
          Banking is the only sector with an approved scoring methodology today. {sector} companies remain fully
          searchable and browsable below — see{" "}
          <Link href="/companies?tab=company-rankings" className="text-sky-500 underline hover:text-sky-600 dark:text-sky-300">
            Company Rankings
          </Link>{" "}
          for real, published Banking rankings.
        </p>
      </div>

      {companies.length === 0 ? (
        <p className="mt-8 text-[13px] text-text-muted">No {sector} companies found.</p>
      ) : (
        <div className="mt-8 space-y-2">
          {companies.map(c => (
            <Link
              key={c.symbol}
              href={`/companies/${c.symbol}`}
              className="flex items-center justify-between rounded-xl border border-surface-border/6 bg-text-primary/[0.02] p-4 transition hover:border-violet-500/25"
            >
              <div className="min-w-0">
                <p className="truncate text-[14px] font-bold text-text-primary">{c.name}</p>
                <p className="text-[11px] text-text-muted">{c.symbol}{c.industry ? ` · ${c.industry}` : ""}</p>
              </div>
              {c.price != null && (
                <div className="shrink-0 text-right">
                  <p className="text-[13px] font-semibold tabular-nums text-text-primary">₹{c.price}</p>
                  {c.pct != null && (
                    <p className={`text-[11px] tabular-nums ${c.positive ? "text-emerald-600 dark:text-emerald-300" : "text-rose-600 dark:text-rose-300"}`}>
                      {c.positive ? "+" : ""}{c.pct}%
                    </p>
                  )}
                </div>
              )}
            </Link>
          ))}
        </div>
      )}

      <div className="mt-10 flex items-center justify-between border-t border-surface-border/6 pt-5">
        <Link href="/companies?tab=company-rankings" className="text-[12px] font-semibold text-sky-500 hover:text-sky-600 dark:text-sky-300 transition">← Company Rankings</Link>
        <Link href="/companies?tab=all-companies" className="text-[12px] font-semibold text-text-muted hover:text-text-secondary transition">Browse All Companies →</Link>
      </div>
    </main>
  );
}
