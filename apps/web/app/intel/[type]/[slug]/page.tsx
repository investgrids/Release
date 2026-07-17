import type { Metadata } from "next";
import { notFound } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, TrendingUp, AlertTriangle, Building2, Globe, Clock, BookOpen } from "lucide-react";
import { API_BASE_URL as API } from "@/lib/api";


const VALID_TYPES = ["company", "event", "theme", "news"] as const;
type IntelType = (typeof VALID_TYPES)[number];

// ── Fetch intelligence server-side ───────────────────────────────────────────

async function fetchIntelligence(type: IntelType, slug: string) {
  const urls: Record<IntelType, string> = {
    company: `${API}/api/intelligence/company/${slug}`,
    event:   `${API}/api/intelligence/event/${slug}`,
    theme:   `${API}/api/intelligence/theme/${slug}`,
    news:    `${API}/api/intelligence/news/${slug}`,
  };
  try {
    const res = await fetch(urls[type], { next: { revalidate: 1800 } });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

// ── Metadata generation ───────────────────────────────────────────────────────

export async function generateMetadata(
  { params }: { params: Promise<{ type: string; slug: string }> }
): Promise<Metadata> {
  const { type: rawType, slug: rawSlug } = await params;
  const type = rawType as IntelType;
  if (!VALID_TYPES.includes(type)) return { title: "Not Found" };

  const intel = await fetchIntelligence(type, rawSlug);
  const slug = rawSlug.replace(/-/g, " ").replace(/\b\w/g, c => c.toUpperCase());
  const typeLabel = { company: "Company", event: "Market Event", theme: "Theme", news: "News" }[type];

  const title = intel?.market_story
    ? `${slug} — ${intel.key_takeaway?.slice(0, 60) ?? "Market Intelligence"} | InvestGrids`
    : `${slug} ${typeLabel} Intelligence | InvestGrids`;

  const description = intel?.market_story?.slice(0, 155)
    ?? `AI-powered market intelligence for ${slug} — opportunities, risks, sectors and themes.`;

  return {
    title,
    description,
    openGraph: {
      title,
      description,
      type: "article",
      siteName: "InvestGrids",
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
    },
    alternates: {
      canonical: `/intel/${type}/${rawSlug}`,
    },
  };
}

// ── Page ──────────────────────────────────────────────────────────────────────

const TYPE_META: Record<IntelType, { label: string; color: string; href: (slug: string) => string }> = {
  company: { label: "Company Intelligence", color: "text-sky-400 border-sky-500/30 bg-sky-500/10",    href: s => `/companies/${s}` },
  event:   { label: "Event Intelligence",   color: "text-violet-400 border-violet-500/30 bg-violet-500/10", href: s => `/events/${s}` },
  theme:   { label: "Theme Intelligence",   color: "text-amber-400 border-amber-500/30 bg-amber-500/10",  href: s => `/themes` },
  news:    { label: "News Intelligence",    color: "text-emerald-400 border-emerald-500/30 bg-emerald-500/10", href: s => `/news/${s}` },
};

export default async function IntelPage(
  { params }: { params: Promise<{ type: string; slug: string }> }
) {
  const { type: rawType, slug: rawSlug } = await params;
  const type = rawType as IntelType;
  if (!VALID_TYPES.includes(type)) notFound();

  const intel = await fetchIntelligence(type, rawSlug);
  if (!intel || !intel.market_story) notFound();

  const meta = TYPE_META[type];
  const humanSlug = rawSlug.replace(/-/g, " ").replace(/\b\w/g, c => c.toUpperCase());

  const conf = intel.confidence ?? {};
  const confScore: number = conf.score ?? 0;
  const confLevel: string = conf.level ?? "Medium";
  const confColor = confScore >= 75 ? "text-emerald-400" : confScore >= 50 ? "text-amber-400" : "text-rose-400";

  const opps: any[]    = intel.opportunities ?? [];
  const risks: any[]   = intel.risks ?? [];
  const companies: any[]= intel.companies ?? [];
  const sectors: any[] = intel.sectors ?? [];
  const themes: any[]  = intel.themes ?? [];
  const monitoring: string[] = intel.monitoring_points ?? [];
  const related: any[] = intel.related_intelligence ?? [];

  return (
    <main className="min-h-screen bg-[#040810] text-white">
      {/* Structured data for SEO */}
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify({
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": intel.key_takeaway,
            "description": intel.market_story,
            "datePublished": intel.generated_at,
            "publisher": { "@type": "Organization", "name": "InvestGrids" },
            "about": companies.map((c: any) => ({
              "@type": "Corporation", "name": c.name, "tickerSymbol": c.symbol,
            })),
          }),
        }}
      />

      <div className="mx-auto max-w-3xl px-4 py-10 sm:px-6">

        {/* Breadcrumb */}
        <nav className="mb-6 flex items-center gap-2 text-[11px] text-slate-600">
          <Link href="/" className="hover:text-slate-400 transition">InvestGrids</Link>
          <span>/</span>
          <Link href={`/${type === "news" ? "news" : type + "s"}`} className="hover:text-slate-400 transition capitalize">{type}s</Link>
          <span>/</span>
          <span className="text-slate-400">{humanSlug}</span>
        </nav>

        {/* Header */}
        <div className="mb-8">
          <span className={`mb-3 inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider ${meta.color}`}>
            <BookOpen className="h-2.5 w-2.5" /> {meta.label}
          </span>
          <h1 className="mt-2 text-[28px] font-black leading-tight text-white">
            {humanSlug}
          </h1>
          <div className="mt-3 flex items-center gap-3">
            <span className={`text-[12px] font-bold ${confColor}`}>
              Confidence: {confLevel} ({confScore}%)
            </span>
            {intel.generated_at && (
              <span className="flex items-center gap-1 text-[11px] text-slate-600">
                <Clock className="h-3 w-3" />
                {new Date(intel.generated_at).toLocaleString("en-IN", {
                  day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit",
                })}
              </span>
            )}
          </div>
        </div>

        {/* Key Takeaway */}
        {intel.key_takeaway && (
          <div className="mb-6 rounded-2xl border border-violet-500/20 bg-violet-500/[0.06] p-5">
            <p className="text-[10px] font-bold uppercase tracking-widest text-violet-400 mb-1.5">Key Takeaway</p>
            <p className="text-[15px] font-semibold leading-snug text-white">{intel.key_takeaway}</p>
          </div>
        )}

        {/* Market Story */}
        {intel.market_story && (
          <section className="mb-7">
            <h2 className="mb-3 text-[13px] font-bold uppercase tracking-widest text-slate-500">Market Story</h2>
            <p className="text-[14px] leading-7 text-slate-300">{intel.market_story}</p>
          </section>
        )}

        {/* Opportunities */}
        {opps.length > 0 && (
          <section className="mb-7">
            <h2 className="mb-3 flex items-center gap-2 text-[13px] font-bold uppercase tracking-widest text-slate-500">
              <TrendingUp className="h-3.5 w-3.5 text-emerald-400" /> Opportunities
            </h2>
            <div className="space-y-3">
              {opps.map((o: any, i: number) => (
                <div key={i} className="rounded-xl border border-emerald-500/15 bg-emerald-500/[0.04] p-4">
                  <div className="flex items-start justify-between gap-3">
                    <h3 className="text-[13px] font-semibold text-emerald-300">{o.title}</h3>
                    {o.horizon && (
                      <span className="shrink-0 rounded-full border border-emerald-500/20 bg-emerald-500/10 px-2 py-0.5 text-[10px] text-emerald-400">
                        {o.horizon}
                      </span>
                    )}
                  </div>
                  <p className="mt-1.5 text-[12px] leading-5 text-slate-400">{o.description}</p>
                  {o.companies?.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {o.companies.map((c: string) => (
                        <Link key={c} href={`/companies/${c}`}
                          className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[10px] text-slate-300 hover:text-sky-300 transition">
                          {c}
                        </Link>
                      ))}
                    </div>
                  )}
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
              {risks.map((r: any, i: number) => (
                <div key={i} className={`rounded-xl border p-4 ${
                  r.severity === "High" ? "border-rose-500/20 bg-rose-500/[0.04]"
                  : "border-amber-500/15 bg-amber-500/[0.04]"
                }`}>
                  <div className="flex items-start justify-between gap-3">
                    <h3 className={`text-[13px] font-semibold ${r.severity === "High" ? "text-rose-300" : "text-amber-300"}`}>
                      {r.title}
                    </h3>
                    {r.severity && (
                      <span className={`shrink-0 rounded-full border px-2 py-0.5 text-[10px] ${
                        r.severity === "High"
                          ? "border-rose-500/20 bg-rose-500/10 text-rose-400"
                          : "border-amber-500/20 bg-amber-500/10 text-amber-400"
                      }`}>{r.severity}</span>
                    )}
                  </div>
                  <p className="mt-1.5 text-[12px] leading-5 text-slate-400">{r.description}</p>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Companies */}
        {companies.length > 0 && (
          <section className="mb-7">
            <h2 className="mb-3 flex items-center gap-2 text-[13px] font-bold uppercase tracking-widest text-slate-500">
              <Building2 className="h-3.5 w-3.5 text-sky-400" /> Companies
            </h2>
            <div className="space-y-2">
              {companies.map((c: any, i: number) => (
                <div key={i} className="flex items-center justify-between rounded-xl border border-white/[0.07] bg-white/[0.03] px-4 py-3">
                  <div className="flex items-center gap-3">
                    <Link href={`/companies/${c.symbol}`}
                      className="text-[13px] font-semibold text-sky-300 hover:text-sky-200 transition">
                      {c.symbol}
                    </Link>
                    <span className="text-[12px] text-slate-500">{c.name}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={`rounded-full border px-2 py-0.5 text-[10px] font-medium ${
                      c.stance === "Bullish"  ? "border-emerald-500/25 bg-emerald-500/10 text-emerald-400" :
                      c.stance === "Bearish"  ? "border-rose-500/25 bg-rose-500/10 text-rose-400" :
                                                "border-white/10 bg-white/5 text-slate-400"
                    }`}>{c.stance ?? "Neutral"}</span>
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Sectors + Themes row */}
        {(sectors.length > 0 || themes.length > 0) && (
          <div className="mb-7 grid grid-cols-1 gap-5 sm:grid-cols-2">
            {sectors.length > 0 && (
              <section>
                <h2 className="mb-3 flex items-center gap-2 text-[13px] font-bold uppercase tracking-widest text-slate-500">
                  <Globe className="h-3.5 w-3.5 text-violet-400" /> Sectors
                </h2>
                <div className="space-y-2">
                  {sectors.map((s: any, i: number) => (
                    <div key={i} className="rounded-xl border border-white/[0.07] bg-white/[0.03] px-4 py-2.5">
                      <div className="flex items-center justify-between">
                        <span className="text-[12px] font-semibold text-white">{s.name}</span>
                        <span className={`text-[11px] font-medium ${
                          s.outlook === "Positive" ? "text-emerald-400" :
                          s.outlook === "Negative" ? "text-rose-400" : "text-slate-400"
                        }`}>{s.outlook ?? "Neutral"}</span>
                      </div>
                      {s.reason && <p className="mt-0.5 text-[10px] text-slate-600">{s.reason}</p>}
                    </div>
                  ))}
                </div>
              </section>
            )}
            {themes.length > 0 && (
              <section>
                <h2 className="mb-3 text-[13px] font-bold uppercase tracking-widest text-slate-500">Themes</h2>
                <div className="flex flex-wrap gap-2">
                  {themes.map((t: any, i: number) => (
                    <Link key={i} href={`/themes`}
                      className="rounded-full border border-violet-500/20 bg-violet-500/[0.06] px-3 py-1.5 text-[11px] font-medium text-violet-300 hover:text-violet-200 transition">
                      {t.name}
                      {t.strength && <span className="ml-1 text-[9px] opacity-60">{t.strength}</span>}
                    </Link>
                  ))}
                </div>
              </section>
            )}
          </div>
        )}

        {/* Historical context */}
        {intel.historical_context && (
          <section className="mb-7 rounded-xl border border-white/[0.06] bg-white/[0.02] p-5">
            <h2 className="mb-2 text-[12px] font-bold uppercase tracking-widest text-slate-600">Historical Context</h2>
            <p className="text-[13px] italic leading-6 text-slate-400">{intel.historical_context}</p>
          </section>
        )}

        {/* Monitoring points */}
        {monitoring.length > 0 && (
          <section className="mb-7">
            <h2 className="mb-3 text-[13px] font-bold uppercase tracking-widest text-slate-500">What to Watch</h2>
            <ul className="space-y-2">
              {monitoring.map((pt, i) => (
                <li key={i} className="flex items-start gap-2.5 text-[13px] text-slate-400">
                  <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-sky-500" />
                  {pt}
                </li>
              ))}
            </ul>
          </section>
        )}

        {/* Related Intelligence */}
        {related.length > 0 && (
          <section className="mb-7">
            <h2 className="mb-3 text-[13px] font-bold uppercase tracking-widest text-slate-500">Related Intelligence</h2>
            <div className="space-y-2">
              {related.slice(0, 5).map((r: any, i: number) => {
                const relType = r.type as IntelType;
                const href = VALID_TYPES.includes(relType)
                  ? `/intel/${relType}/${r.id}`
                  : "#";
                return (
                  <Link key={i} href={href}
                    className="flex items-center justify-between rounded-xl border border-white/[0.07] bg-white/[0.03] px-4 py-3 hover:border-white/20 transition">
                    <div>
                      <span className="text-[10px] uppercase tracking-wider text-slate-600 capitalize">{r.type}</span>
                      <p className="text-[12px] font-medium text-slate-300">{r.title}</p>
                    </div>
                    {r.relevance_score != null && (
                      <span className="text-[11px] font-bold text-violet-400">{Math.round(r.relevance_score * 100)}%</span>
                    )}
                  </Link>
                );
              })}
            </div>
          </section>
        )}

        {/* CTA */}
        <div className="mt-10 flex flex-col gap-3 rounded-2xl border border-white/[0.07] bg-white/[0.03] p-5 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-[13px] font-semibold text-white">Want deeper analysis?</p>
            <p className="text-[12px] text-slate-500">Ask our AI any question about this {type}.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link href={`/ai-search?q=${encodeURIComponent(`Tell me more about ${humanSlug}`)}`}
              className="rounded-full border border-violet-500/30 bg-violet-500/10 px-4 py-2 text-[12px] font-semibold text-violet-300 hover:bg-violet-500/15 transition">
              Ask AI →
            </Link>
            <Link href={meta.href(rawSlug)}
              className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-[12px] font-medium text-slate-300 hover:text-white transition">
              <ArrowLeft className="inline h-3 w-3 mr-1" /> Back to {type}
            </Link>
          </div>
        </div>

      </div>
    </main>
  );
}
