import type { Metadata } from "next";
import { notFound } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft, TrendingUp, AlertTriangle, Building2, Clock,
  BookOpen, HelpCircle, Eye, ListChecks,
} from "lucide-react";
import { API_BASE_URL as API } from "@/lib/api";

// ── Article type metadata ────────────────────────────────────────────────────

const TYPE_META: Record<string, { label: string; color: string }> = {
  breaking:               { label: "Breaking Intelligence",  color: "text-rose-400 border-rose-500/30 bg-rose-500/10" },
  morning_intelligence:   { label: "Morning Intelligence",    color: "text-amber-400 border-amber-500/30 bg-amber-500/10" },
  company_intelligence:   { label: "Company Intelligence",    color: "text-sky-400 border-sky-500/30 bg-sky-500/10" },
  sector_intelligence:    { label: "Sector Intelligence",     color: "text-violet-400 border-violet-500/30 bg-violet-500/10" },
  theme_intelligence:     { label: "Theme Intelligence",      color: "text-violet-400 border-violet-500/30 bg-violet-500/10" },
  policy_intelligence:    { label: "Policy Intelligence",     color: "text-indigo-400 border-indigo-500/30 bg-indigo-500/10" },
  ripple_intelligence:    { label: "Ripple Intelligence",     color: "text-cyan-400 border-cyan-500/30 bg-cyan-500/10" },
  opportunity_intelligence: { label: "Opportunity Intelligence", color: "text-emerald-400 border-emerald-500/30 bg-emerald-500/10" },
  market_wrap:             { label: "Market Wrap",            color: "text-amber-400 border-amber-500/30 bg-amber-500/10" },
  weekly_intelligence:     { label: "Weekly Intelligence",    color: "text-sky-400 border-sky-500/30 bg-sky-500/10" },
  monthly_intelligence:    { label: "Monthly Intelligence",   color: "text-sky-400 border-sky-500/30 bg-sky-500/10" },
  educational_intelligence:{ label: "Investor Education",     color: "text-emerald-400 border-emerald-500/30 bg-emerald-500/10" },
};
const DEFAULT_TYPE_META = { label: "Market Intelligence", color: "text-slate-400 border-white/20 bg-white/5" };

// ── Types ─────────────────────────────────────────────────────────────────────

interface CompanyAffected { name: string; symbol: string; impact: "positive" | "negative" | "neutral"; reason?: string; timeframe?: string; }
interface Risk { title: string; description: string; severity?: string; mitigation?: string; }
interface HistoricalEvent { event?: string; date?: string; category?: string; outcome?: number | null; sentiment?: string; }
interface Faq { question: string; answer: string; }
interface RelatedCompany { symbol: string; name: string; link: string; }
interface RelatedTheme { theme: string; link: string; }

interface InsightDetail {
  id: string; slug: string; article_type: string;
  headline: string; key_takeaway?: string; executive_summary?: string;
  seo_title?: string; meta_description?: string;
  why_it_matters?: string; what_happened?: string;
  companies_affected: CompanyAffected[];
  sectors_affected: { name: string; impact?: string; reason?: string }[];
  risks: Risk[];
  historical_events: HistoricalEvent[];
  what_to_watch_next: string[];
  faqs: Faq[];
  sources: string[];
  related_companies: RelatedCompany[];
  related_themes: RelatedTheme[];
  confidence_score?: number;
  canonical_url?: string;
  json_ld?: Record<string, unknown>;
  published_at?: string;
  last_updated?: string;
}

// ── Fetch ─────────────────────────────────────────────────────────────────────

async function fetchInsight(slug: string): Promise<InsightDetail | null> {
  try {
    const res = await fetch(`${API}/api/insights/${slug}`, { next: { revalidate: 1800 } });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

function fmtDate(iso?: string) {
  if (!iso) return null;
  return new Date(iso).toLocaleString("en-IN", {
    day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

const IMPACT_STYLE: Record<string, string> = {
  positive: "border-emerald-500/25 bg-emerald-500/10 text-emerald-400",
  negative: "border-rose-500/25 bg-rose-500/10 text-rose-400",
  neutral:  "border-white/10 bg-white/5 text-slate-400",
};

// ── Metadata ──────────────────────────────────────────────────────────────────

export async function generateMetadata(
  { params }: { params: Promise<{ slug: string }> }
): Promise<Metadata> {
  const { slug } = await params;
  const article = await fetchInsight(slug);
  if (!article) return { title: "Not Found" };

  const title = article.seo_title || article.headline;
  const description = article.meta_description || article.executive_summary || article.key_takeaway || "";

  return {
    title: `${title} | MarketRipple`,
    description,
    openGraph: {
      title,
      description,
      type: "article",
      siteName: "MarketRipple",
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
    },
    alternates: {
      canonical: article.canonical_url || `/insights/${slug}`,
    },
  };
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default async function InsightPage(
  { params }: { params: Promise<{ slug: string }> }
) {
  const { slug } = await params;
  const article = await fetchInsight(slug);
  if (!article || !article.headline) notFound();

  const meta = TYPE_META[article.article_type] ?? DEFAULT_TYPE_META;
  const companies = article.companies_affected ?? [];
  const winners = companies.filter(c => c.impact === "positive");
  const risks = article.risks ?? [];
  const historical = article.historical_events ?? [];
  const watch = article.what_to_watch_next ?? [];
  const faqs = article.faqs ?? [];
  const relatedCompanies = article.related_companies ?? [];
  const relatedThemes = article.related_themes ?? [];
  const sources = article.sources ?? [];

  return (
    <main className="min-h-screen bg-[#040810] text-white">
      {article.json_ld && (
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(article.json_ld) }}
        />
      )}

      <div className="mx-auto max-w-3xl px-4 py-10 sm:px-6">

        {/* Breadcrumb */}
        <nav className="mb-6 flex items-center gap-2 text-[11px] text-slate-600">
          <Link href="/" className="hover:text-slate-400 transition">MarketRipple</Link>
          <span>/</span>
          <Link href="/insights" className="hover:text-slate-400 transition">Insights</Link>
          <span>/</span>
          <span className="truncate text-slate-400">{article.headline}</span>
        </nav>

        {/* Header */}
        <div className="mb-8">
          <span className={`mb-3 inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider ${meta.color}`}>
            <BookOpen className="h-2.5 w-2.5" /> {meta.label}
          </span>
          <h1 className="mt-2 text-[28px] font-black leading-tight text-white">
            {article.headline}
          </h1>
          <div className="mt-3 flex flex-wrap items-center gap-3">
            {article.confidence_score != null && (
              <span className="text-[12px] font-bold text-sky-400">
                Confidence: {Math.round(article.confidence_score * 100)}%
              </span>
            )}
            {article.published_at && (
              <span className="flex items-center gap-1 text-[11px] text-slate-600">
                <Clock className="h-3 w-3" /> Published {fmtDate(article.published_at)}
              </span>
            )}
            {article.last_updated && article.last_updated !== article.published_at && (
              <span className="flex items-center gap-1 text-[11px] text-slate-600">
                <Eye className="h-3 w-3" /> Updated {fmtDate(article.last_updated)}
              </span>
            )}
          </div>
        </div>

        {/* TLDR */}
        {article.key_takeaway && (
          <div className="mb-6 rounded-2xl border border-violet-500/20 bg-violet-500/[0.06] p-5">
            <p className="text-[10px] font-bold uppercase tracking-widest text-violet-400 mb-1.5">TLDR</p>
            <p className="text-[15px] font-semibold leading-snug text-white">{article.key_takeaway}</p>
          </div>
        )}

        {/* Why it matters */}
        {article.why_it_matters && (
          <section className="mb-7">
            <h2 className="mb-3 text-[13px] font-bold uppercase tracking-widest text-slate-500">Why It Matters</h2>
            <p className="whitespace-pre-line text-[14px] leading-7 text-slate-300">{article.why_it_matters}</p>
          </section>
        )}

        {/* What happened */}
        {article.what_happened && (
          <section className="mb-7">
            <h2 className="mb-3 text-[13px] font-bold uppercase tracking-widest text-slate-500">What Happened</h2>
            <p className="whitespace-pre-line text-[14px] leading-7 text-slate-300">{article.what_happened}</p>
          </section>
        )}

        {/* Winners */}
        {winners.length > 0 && (
          <section className="mb-7">
            <h2 className="mb-3 flex items-center gap-2 text-[13px] font-bold uppercase tracking-widest text-slate-500">
              <TrendingUp className="h-3.5 w-3.5 text-emerald-400" /> Winners
            </h2>
            <div className="flex flex-wrap gap-2">
              {winners.map((c, i) => (
                <Link key={i} href={`/companies/${c.symbol}`}
                  className="rounded-full border border-emerald-500/25 bg-emerald-500/10 px-3 py-1.5 text-[12px] font-semibold text-emerald-300 hover:text-emerald-200 transition">
                  {c.name} ({c.symbol})
                </Link>
              ))}
            </div>
          </section>
        )}

        {/* Companies affected */}
        {companies.length > 0 && (
          <section className="mb-7">
            <h2 className="mb-3 flex items-center gap-2 text-[13px] font-bold uppercase tracking-widest text-slate-500">
              <Building2 className="h-3.5 w-3.5 text-sky-400" /> Companies Affected
            </h2>
            <div className="space-y-2">
              {companies.map((c, i) => (
                <div key={i} className="rounded-xl border border-white/[0.07] bg-white/[0.03] px-4 py-3">
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-3">
                      <Link href={`/companies/${c.symbol}`}
                        className="text-[13px] font-semibold text-sky-300 hover:text-sky-200 transition">
                        {c.symbol}
                      </Link>
                      <span className="text-[12px] text-slate-500">{c.name}</span>
                    </div>
                    <span className={`shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-medium capitalize ${IMPACT_STYLE[c.impact] ?? IMPACT_STYLE.neutral}`}>
                      {c.impact}
                    </span>
                  </div>
                  {c.reason && <p className="mt-1.5 text-[12px] leading-5 text-slate-400">{c.reason}</p>}
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Risks */}
        {risks.length > 0 && (
          <section className="mb-7">
            <h2 className="mb-3 flex items-center gap-2 text-[13px] font-bold uppercase tracking-widest text-slate-500">
              <AlertTriangle className="h-3.5 w-3.5 text-amber-400" /> Risks
            </h2>
            <div className="space-y-3">
              {risks.map((r, i) => (
                <div key={i} className={`rounded-xl border p-4 ${
                  r.severity === "high" ? "border-rose-500/20 bg-rose-500/[0.04]" : "border-amber-500/15 bg-amber-500/[0.04]"
                }`}>
                  <div className="flex items-start justify-between gap-3">
                    <h3 className={`text-[13px] font-semibold ${r.severity === "high" ? "text-rose-300" : "text-amber-300"}`}>
                      {r.title}
                    </h3>
                    {r.severity && (
                      <span className={`shrink-0 rounded-full border px-2 py-0.5 text-[10px] capitalize ${
                        r.severity === "high"
                          ? "border-rose-500/20 bg-rose-500/10 text-rose-400"
                          : "border-amber-500/20 bg-amber-500/10 text-amber-400"
                      }`}>{r.severity}</span>
                    )}
                  </div>
                  <p className="mt-1.5 text-[12px] leading-5 text-slate-400">{r.description}</p>
                  {r.mitigation && (
                    <p className="mt-1.5 text-[11px] leading-5 text-slate-600">
                      <span className="font-semibold text-slate-500">How to manage: </span>{r.mitigation}
                    </p>
                  )}
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Historical examples */}
        {historical.length > 0 && (
          <section className="mb-7 rounded-xl border border-white/[0.06] bg-white/[0.02] p-5">
            <h2 className="mb-3 text-[12px] font-bold uppercase tracking-widest text-slate-600">Historical Examples</h2>
            <div className="space-y-2.5">
              {historical.map((h, i) => (
                <div key={i} className="flex items-start justify-between gap-3 text-[13px]">
                  <div>
                    <span className="text-slate-300">{h.event}</span>
                    {h.category && <span className="ml-2 text-[10px] uppercase tracking-wider text-slate-600">{h.category}</span>}
                  </div>
                  <div className="flex shrink-0 items-center gap-2 text-slate-500">
                    <span>{h.date}</span>
                    {h.outcome != null && (
                      <span className={h.outcome >= 0 ? "text-emerald-400" : "text-rose-400"}>
                        {h.outcome >= 0 ? "+" : ""}{h.outcome}%
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* What to watch next */}
        {watch.length > 0 && (
          <section className="mb-7">
            <h2 className="mb-3 flex items-center gap-2 text-[13px] font-bold uppercase tracking-widest text-slate-500">
              <ListChecks className="h-3.5 w-3.5 text-sky-400" /> What to Watch Next
            </h2>
            <ul className="space-y-2">
              {watch.map((pt, i) => (
                <li key={i} className="flex items-start gap-2.5 text-[13px] text-slate-400">
                  <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-sky-500" />
                  {pt}
                </li>
              ))}
            </ul>
          </section>
        )}

        {/* FAQ */}
        {faqs.length > 0 && (
          <section className="mb-7">
            <h2 className="mb-3 flex items-center gap-2 text-[13px] font-bold uppercase tracking-widest text-slate-500">
              <HelpCircle className="h-3.5 w-3.5 text-violet-400" /> Frequently Asked Questions
            </h2>
            <div className="space-y-2">
              {faqs.map((f, i) => (
                <details key={i} className="group rounded-xl border border-white/[0.07] bg-white/[0.03] px-4 py-3 open:bg-white/[0.045]">
                  <summary className="cursor-pointer list-none text-[13px] font-semibold text-slate-200 marker:content-none">
                    {f.question}
                  </summary>
                  <p className="mt-2 text-[12px] leading-6 text-slate-400">{f.answer}</p>
                </details>
              ))}
            </div>
          </section>
        )}

        {/* Related opportunities/companies/themes */}
        {(relatedCompanies.length > 0 || relatedThemes.length > 0) && (
          <section className="mb-7">
            <h2 className="mb-3 text-[13px] font-bold uppercase tracking-widest text-slate-500">Related Intelligence</h2>
            <div className="flex flex-wrap gap-2">
              {relatedCompanies.map((c, i) => (
                <Link key={`co-${i}`} href={c.link}
                  className="rounded-full border border-sky-500/20 bg-sky-500/[0.06] px-3 py-1.5 text-[11px] font-medium text-sky-300 hover:text-sky-200 transition">
                  {c.name}
                </Link>
              ))}
              {relatedThemes.map((t, i) => (
                <Link key={`th-${i}`} href={t.link}
                  className="rounded-full border border-violet-500/20 bg-violet-500/[0.06] px-3 py-1.5 text-[11px] font-medium text-violet-300 hover:text-violet-200 transition">
                  {t.theme}
                </Link>
              ))}
            </div>
          </section>
        )}

        {/* Sources / disclaimer */}
        <div className="mt-10 rounded-xl border border-white/[0.06] bg-white/[0.02] p-4">
          {sources.length > 0 && (
            <p className="text-[11px] text-slate-600">
              <span className="font-semibold text-slate-500">Sources: </span>{sources.join(", ")}
            </p>
          )}
          <p className="mt-1.5 text-[10px] leading-5 text-slate-700">
            Generated by MarketRipple&apos;s AI Intelligence Engine from real market data and events.
            Not investment advice — always do your own research before making investment decisions.
          </p>
        </div>

        {/* CTA */}
        <div className="mt-6 flex flex-col gap-3 rounded-2xl border border-white/[0.07] bg-white/[0.03] p-5 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-[13px] font-semibold text-white">Want deeper analysis?</p>
            <p className="text-[12px] text-slate-500">Ask our AI any question about this story.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link href={`/ai-search?q=${encodeURIComponent(article.headline)}`}
              className="rounded-full border border-violet-500/30 bg-violet-500/10 px-4 py-2 text-[12px] font-semibold text-violet-300 hover:bg-violet-500/15 transition">
              Ask AI →
            </Link>
            <Link href="/insights"
              className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-[12px] font-medium text-slate-300 hover:text-white transition">
              <ArrowLeft className="inline h-3 w-3 mr-1" /> More Insights
            </Link>
          </div>
        </div>

      </div>
    </main>
  );
}
