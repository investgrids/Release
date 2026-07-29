import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Radar, GitBranch, Rocket, History, ArrowRight, Sparkles, BookOpen, TrendingUp, TrendingDown, HelpCircle } from "lucide-react";
import { API_BASE_URL as API } from "@/lib/api";
import { safeJsonLd } from "@/lib/text";
import { SignalActions } from "@/components/intelligence/SignalActions";

/**
 * Live Intelligence signal pages — premium redesign pass.
 *
 * UI-only. No new backend calls: everything below is derived from the
 * single existing GET /api/insights/{slug} response (fetchSignal), same as
 * before — Next's fetch cache (`revalidate: 300`) is this Server
 * Component's equivalent of "reuse the cache, don't refetch," there's no
 * TanStack Query in this codebase to defer to.
 *
 * A few things the requested mockup asked for that this deliberately does
 * NOT fabricate, because the persisted signal payload genuinely doesn't
 * carry them and inventing them would violate this app's "never invent a
 * claim" rule (see live_intelligence.py's own module docstring):
 *   - No "Growing/Confirmed/Peak" stage badge — there's no real evolution
 *     state machine behind this yet (flagged as future work in the
 *     Live Intelligence audit). occurrence_count + first/last-seen
 *     timestamps are the real, honest substitute shown here instead.
 *   - No granular multi-step timeline ("10:30 — 3 more companies
 *     joined") — only first_detected_at/last_seen_at/occurrence_count are
 *     actually tracked, so the timeline has exactly those real points.
 *   - No "Related Signals" rail and no fetched Related Events / full
 *     Opportunities grid — building those honestly needs either a new API
 *     call (explicitly out of scope for this pass) or fabricated content.
 *     What IS real and already in this response — a matched opportunity_id
 *     (early_theme) — gets a real single card; the rest link out to the
 *     real hub pages (/research, /opportunity-radar, /ai-search) instead
 *     of faking previews.
 *   - No company logos or per-company confidence — not present in
 *     companies_affected; a plain ticker chip is the honest fallback.
 */

const SITE = process.env.NEXT_PUBLIC_SITE_URL ?? "https://marketripple.in";

interface SignalPayload {
  type: "anomaly" | "policy_ripple" | "early_theme" | "historical_match";
  headline: string;
  companies?: string[];
  why_it_matters?: string | null;
  similarity?: number | null;
  sector?: string | null;
  path?: string[];
  is_fallback?: boolean;
  opportunity_score?: number | null;
  opportunity_id?: string | number | null;
  winners?: string[];
  losers?: string[];
  key_lesson?: string | null;
  detected_at?: string | null;
}

interface SignalArticle {
  slug: string; headline: string; seo_title?: string; meta_description?: string;
  executive_summary?: string;
  companies_affected: { name: string; symbol: string; impact?: string }[];
  published_at?: string; last_updated?: string;
  canonical_url?: string;
  market_context?: {
    kind: string; signal_type: string; payload: SignalPayload;
    first_detected_at?: string; last_seen_at?: string; occurrence_count?: number;
  } | null;
  // Populated by signal_publisher.py's async enrichment pass (run_signal_
  // enrichment_cycle), not at initial publish — null/undefined on a signal
  // that hasn't been enriched yet, which is a real, expected state (the
  // request-time publish path stays fast/LLM-free on purpose), not a bug.
  why_it_matters?: string | null;
  what_happened?: string | null;
  opportunities?: { title: string; description: string; timeframe?: string; risk?: string }[];
  risks?: { title: string; description: string; severity?: string; mitigation?: string }[];
  faqs?: { question: string; answer: string }[];
}

async function fetchSignal(slug: string): Promise<SignalArticle | null> {
  try {
    const res = await fetch(`${API}/api/insights/${slug}`, { next: { revalidate: 300 } });
    if (!res.ok) return null;
    const data = await res.json();
    if (data.market_context?.kind !== "live_signal") return null;
    return data;
  } catch {
    return null;
  }
}

const TYPE_META: Record<string, { label: string; icon: React.ReactNode; cls: string; glow: string }> = {
  anomaly:          { label: "Intelligence Detection", icon: <Radar className="h-3.5 w-3.5" />,    cls: "text-violet-300 border-violet-500/25 bg-violet-500/[0.08]",   glow: "from-violet-500/10" },
  policy_ripple:    { label: "Policy Intelligence",     icon: <GitBranch className="h-3.5 w-3.5" />, cls: "text-sky-300 border-sky-500/25 bg-sky-500/[0.08]",           glow: "from-sky-500/10" },
  early_theme:      { label: "Emerging Theme",          icon: <Rocket className="h-3.5 w-3.5" />,    cls: "text-emerald-300 border-emerald-500/25 bg-emerald-500/[0.08]", glow: "from-emerald-500/10" },
  historical_match: { label: "Pattern Detected",        icon: <History className="h-3.5 w-3.5" />,   cls: "text-amber-300 border-amber-500/25 bg-amber-500/[0.08]",     glow: "from-amber-500/10" },
};

function timeAgo(iso: string | null | undefined): string {
  if (!iso) return "";
  const mins = Math.floor((Date.now() - new Date(iso).getTime()) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  if (mins < 1440) return `${Math.floor(mins / 60)}h ago`;
  return `${Math.floor(mins / 1440)}d ago`;
}
function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short" });
}

// A visible, crawlable SEO summary paragraph — same reasoning as the SSR
// "kicker" blocks added to companies/events/opportunity pages earlier this
// session: real, natural-language sentences built only from data already
// on the page (sector, tickers, score), never invented copy, positioned as
// genuinely readable content (never sr-only — that would be a cloaking-
// adjacent pattern). Doubles as the meta-description fallback below.
function buildSeoSummary(signalType: string, headline: string, p: SignalPayload, companies: string[], detectedLabel: string): string {
  const tickers = companies.slice(0, 6).join(", ");
  if (signalType === "anomaly") {
    const sector = p.sector ? `${p.sector} sector` : "sector";
    return `MarketRipple's Live Intelligence engine detected simultaneous market activity across ${companies.length} ${sector} stocks${tickers ? ` — ${tickers}` : ""}, based on real triaged NSE events within a 72-hour window. This ${p.sector ?? ""} sector signal was ${detectedLabel}, using MarketRipple's AI-powered event-clustering intelligence, not simulated data.`.replace(/\s+/g, " ");
  }
  if (signalType === "policy_ripple") {
    const chain = p.path?.join(" → ") ?? headline;
    return `MarketRipple's Ripple Intelligence graph traced a real policy causal chain: ${chain}.${tickers ? ` This ripple effect connects to ${tickers} in the Indian stock market.` : ""} ${p.is_fallback ? "This is a recurring structural pattern in MarketRipple's intelligence graph, not a fresh policy trigger today." : ""}`.replace(/\s+/g, " ").trim();
  }
  if (signalType === "early_theme") {
    return `${headline} is a rising investment theme on MarketRipple, ${p.opportunity_score != null ? `carrying a live Opportunity Score of ${p.opportunity_score}/100. ` : ""}${tickers ? `Leading ${headline} stocks include ${tickers}, ` : ""}identified through MarketRipple's real-time theme-momentum and opportunity-matching engine.`.replace(/\s+/g, " ");
  }
  if (signalType === "historical_match") {
    const sim = p.similarity != null ? `${Math.round(p.similarity)}% similarity` : "a real precedent match";
    const w = p.winners?.[0], l = p.losers?.[0];
    return `Today's real market context shows ${sim} to a historical precedent on MarketRipple: "${headline}."${w || l ? ` Historical pattern data shows ${w ? `${w} among the winners` : ""}${w && l ? " and " : ""}${l ? `${l} among the laggards` : ""} in similar past episodes.` : ""} ${p.key_lesson ?? ""}`.replace(/\s+/g, " ").trim();
  }
  return headline;
}

function Card({ title, icon, children, className = "" }: { title?: string; icon?: React.ReactNode; children: React.ReactNode; className?: string }) {
  return (
    <section className={`rounded-[18px] border border-white/[0.08] bg-white/[0.02] p-5 backdrop-blur transition hover:border-white/[0.12] ${className}`}>
      {title && (
        <div className="mb-3.5 flex items-center gap-2">
          {icon}
          <h2 className="text-[11px] font-bold uppercase tracking-[0.12em] text-slate-400">{title}</h2>
        </div>
      )}
      {children}
    </section>
  );
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  const fallbackUrl = `${SITE}/intelligence/signal/${slug}`;
  const a = await fetchSignal(slug);
  if (!a) return { title: "Signal — MarketRipple Live Intelligence", alternates: { canonical: fallbackUrl } };
  // Trust the backend's canonical_url (settings.frontend_url, always
  // "https://www.marketripple.in") over this page's own SITE constant —
  // they previously disagreed (this page fell back to a non-www domain
  // when NEXT_PUBLIC_SITE_URL wasn't set at build time), producing two
  // live pages for the same slug with two contradictory canonical tags.
  const url = a.canonical_url || fallbackUrl;
  const ctx0 = a.market_context;
  const seoFallback = ctx0
    ? buildSeoSummary(ctx0.signal_type, a.headline, ctx0.payload, a.companies_affected?.map(c => c.symbol) ?? [], "recently detected")
    : a.headline;
  const desc = (a.meta_description || a.executive_summary || seoFallback).slice(0, 160);
  return {
    title: a.seo_title || a.headline,
    description: desc,
    openGraph: { type: "article", title: a.headline, description: desc, url, siteName: "MarketRipple" },
    twitter: { card: "summary", title: a.headline, description: desc },
    alternates: { canonical: url },
  };
}

export default async function SignalPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const a = await fetchSignal(slug);
  if (!a || !a.market_context) notFound();

  const ctx = a.market_context;
  const p = ctx.payload;
  const meta = TYPE_META[ctx.signal_type] ?? { label: "Live Intelligence", icon: <Sparkles className="h-3.5 w-3.5" />, cls: "text-slate-300 border-white/20 bg-white/[0.05]", glow: "from-slate-500/10" };
  const url = a.canonical_url || `${SITE}/intelligence/signal/${slug}`;
  const companies = a.companies_affected?.map(c => c.symbol) ?? [];

  // Real score, honestly labeled per type — never a generic invented
  // "confidence" number when the underlying detector doesn't produce one.
  const score = ctx.signal_type === "early_theme" ? p.opportunity_score
              : (ctx.signal_type === "anomaly" || ctx.signal_type === "historical_match") ? p.similarity
              : null;
  const scoreLabel = ctx.signal_type === "early_theme" ? "Opportunity Score"
                    : ctx.signal_type === "historical_match" ? "Similarity to Today"
                    : "Historical Similarity";

  const whyItMatters: string[] = [];
  if (ctx.signal_type === "anomaly") {
    if (p.companies?.length) whyItMatters.push(`${p.companies.length} real companies in ${p.sector ?? "the same sector"} moving together in the last 72 hours`);
    if (p.why_it_matters) whyItMatters.push(p.why_it_matters);
    if (p.similarity != null) whyItMatters.push(`${Math.round(p.similarity)}% similarity to a real historical precedent`);
  } else if (ctx.signal_type === "policy_ripple") {
    if (p.path?.length) whyItMatters.push(`A ${p.path.length}-step causal chain traced through the intelligence graph`);
    if (p.is_fallback) whyItMatters.push("This is a recurring structural pattern, not a fresh policy trigger today");
    if (companies.length) whyItMatters.push(`Directly affects ${companies.join(", ")}`);
  } else if (ctx.signal_type === "early_theme") {
    whyItMatters.push("Real rising momentum, cross-referenced against a live Opportunity score");
    if (p.opportunity_score != null) whyItMatters.push(`Opportunity score of ${p.opportunity_score}/100`);
    if (companies.length) whyItMatters.push(`Leading names: ${companies.join(", ")}`);
  } else if (ctx.signal_type === "historical_match") {
    if (p.similarity != null) whyItMatters.push(`${Math.round(p.similarity)}% match to today's real sector/sentiment context`);
    if (p.key_lesson) whyItMatters.push(p.key_lesson);
  }

  const detectedLabel = p.is_fallback
    ? "identified as a recurring pattern in MarketRipple's intelligence graph"
    : ctx.first_detected_at ? `first detected ${timeAgo(ctx.first_detected_at)}` : "recently identified";
  const seoSummary = buildSeoSummary(ctx.signal_type, a.headline, p, companies, detectedLabel);
  // Same domain `url` already resolves to (a.canonical_url when the
  // backend has it) — previously hardcoded to the local SITE constant,
  // which could disagree with `url` itself (see the canonical_url fix
  // above) and made the breadcrumb's own "MarketRipple" item point at a
  // different domain than the page's own canonical tag.
  const siteOrigin = url.replace(/\/intelligence\/signal\/.*$/, "");

  // NewsArticle (not the plain Article this page previously always sent) —
  // this page's own hardcoded value was a separate, dead-end JSON-LD
  // construction that never picked up the backend's schema-type or FAQPage
  // work (comparison_publisher.py/publisher.py/signal_publisher.py all
  // compute a real json_ld field on the row, but this page has always
  // built its own from scratch instead of rendering it) — fixed at the
  // source that's actually used rather than plumbing through the unused
  // backend field, to avoid two parallel JSON-LD constructions drifting
  // further apart.
  const jsonLd: Record<string, unknown> = {
    "@context": "https://schema.org",
    "@type": a.faqs && a.faqs.length > 0 ? ["NewsArticle", "FAQPage"] : "NewsArticle",
    headline: a.headline,
    description: a.meta_description || a.executive_summary || seoSummary,
    datePublished: ctx.first_detected_at || a.published_at,
    dateModified: a.last_updated,
    author: { "@type": "Organization", name: "MarketRipple AI Intelligence Engine" },
    publisher: { "@type": "Organization", name: "MarketRipple" },
    mainEntityOfPage: url,
    breadcrumb: {
      "@type": "BreadcrumbList",
      itemListElement: [
        { "@type": "ListItem", position: 1, name: "MarketRipple", item: siteOrigin },
        { "@type": "ListItem", position: 2, name: "Live Intelligence", item: `${siteOrigin}/#live-intelligence` },
        { "@type": "ListItem", position: 3, name: a.headline, item: url },
      ],
    },
  };
  if (a.faqs && a.faqs.length > 0) {
    jsonLd.mainEntity = a.faqs.slice(0, 5).map(f => ({
      "@type": "Question", name: f.question,
      acceptedAnswer: { "@type": "Answer", text: f.answer },
    }));
  }

  return (
    <main className="mx-auto max-w-[1280px] px-5 py-6 pb-16 sm:px-6">
      {/* JSON.stringify (not safeJsonLd) previously left "<" unescaped —
          a literal "</script>" inside any AI-generated string field
          (headline, description, key_lesson, etc.) could close this tag
          early and inject arbitrary HTML. Same stored-XSS class lib/text.ts's
          safeJsonLd() already guards against on the main article page. */}
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: safeJsonLd(jsonLd) }} />

      <nav className="mb-4 flex items-center gap-2 text-[12px] text-slate-500">
        <Link href="/" className="hover:text-slate-300 transition">Home</Link>
        <span>/</span>
        <span className="text-slate-400">Live Intelligence</span>
      </nav>

      {/* ── Hero ────────────────────────────────────────────────────────── */}
      <div className={`relative overflow-hidden rounded-[22px] border border-white/[0.08] bg-gradient-to-br ${meta.glow} to-transparent p-6 sm:p-7`}>
        <div className="flex flex-wrap items-center gap-2">
          <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider ${meta.cls}`}>
            {meta.icon} {meta.label}
          </span>
          {p.is_fallback ? (
            <span className="inline-flex items-center rounded-full border border-white/10 bg-white/[0.04] px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider text-slate-500">
              Recurring — not today&apos;s news
            </span>
          ) : ctx.first_detected_at ? (
            <span className="inline-flex items-center rounded-full border border-white/10 bg-white/[0.04] px-2.5 py-1 text-[10px] font-semibold text-slate-400">
              Detected {timeAgo(ctx.first_detected_at)}
            </span>
          ) : null}
          {p.sector && (
            <span className="inline-flex items-center rounded-full border border-white/10 bg-white/[0.04] px-2.5 py-1 text-[10px] font-semibold capitalize text-slate-400">
              {p.sector} Sector
            </span>
          )}
        </div>
        <h1 className="mt-3.5 text-2xl font-black leading-tight tracking-tight text-white sm:text-[32px]">{a.headline}</h1>
        <p className="mt-2.5 max-w-[760px] text-[13.5px] leading-relaxed text-slate-400">{seoSummary}</p>
      </div>

      {/* ── Two-column workspace ──────────────────────────────────────────── */}
      <div className="mt-5 grid grid-cols-1 gap-5 md:grid-cols-[1fr_280px]">

        {/* LEFT — main content */}
        <div className="min-w-0 space-y-5">

          {a.executive_summary && (
            <Card title="Executive Summary">
              <p className="line-clamp-4 text-[14px] leading-relaxed text-slate-300">{a.executive_summary}</p>
            </Card>
          )}

          {whyItMatters.length > 0 && (
            <Card title="Why This Matters">
              <ul className="space-y-2">
                {whyItMatters.map((w, i) => (
                  <li key={i} className="flex items-start gap-2.5 text-[13.5px] leading-snug text-slate-300">
                    <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-violet-400" />
                    {w}
                  </li>
                ))}
              </ul>
            </Card>
          )}

          {/* Ripple Analysis — real data only: the full causal chain for
              policy_ripple (the one type that actually has a multi-hop
              path), a real 3-tier signal→sector→companies flow for the
              other three (no fabricated intermediate nodes). */}
          <Card title="Ripple Analysis" icon={<GitBranch className="h-3.5 w-3.5 text-slate-500" />}>
            {ctx.signal_type === "policy_ripple" && p.path && p.path.length > 0 ? (
              <div className="flex flex-wrap items-center gap-2 py-1">
                {p.path.map((node, i) => (
                  <span key={i} className="flex items-center gap-2">
                    {i > 0 && <ArrowRight className="h-3.5 w-3.5 shrink-0 text-slate-600" />}
                    <span className="rounded-[10px] border border-sky-500/20 bg-sky-500/[0.06] px-3 py-1.5 text-[12.5px] font-semibold text-sky-200">{node}</span>
                  </span>
                ))}
              </div>
            ) : (
              <div className="flex flex-wrap items-center gap-2 py-1">
                <span className={`rounded-[10px] border px-3 py-1.5 text-[12.5px] font-semibold ${meta.cls}`}>{meta.label}</span>
                {p.sector && (
                  <>
                    <ArrowRight className="h-3.5 w-3.5 shrink-0 text-slate-600" />
                    <span className="rounded-[10px] border border-white/10 bg-white/[0.04] px-3 py-1.5 text-[12.5px] font-semibold capitalize text-slate-200">{p.sector}</span>
                  </>
                )}
                {companies.slice(0, 4).map((c, i) => (
                  <span key={c} className="flex items-center gap-2">
                    <ArrowRight className="h-3.5 w-3.5 shrink-0 text-slate-600" />
                    <Link href={`/companies/${c}`} className="rounded-[10px] border border-white/10 bg-white/[0.04] px-3 py-1.5 text-[12.5px] font-semibold text-slate-200 transition hover:border-violet-500/30 hover:text-violet-300">{c}</Link>
                  </span>
                ))}
              </div>
            )}
          </Card>

          {/* Timeline — exactly the real points this app actually tracks;
              no invented intermediate events. */}
          <Card title="Timeline">
            <div className="space-y-0">
              {[
                { label: "First Detected", value: fmtDate(ctx.first_detected_at), sub: timeAgo(ctx.first_detected_at) },
                ...(ctx.occurrence_count && ctx.occurrence_count > 1
                  ? [{ label: "Confirmed Again", value: `Seen ${ctx.occurrence_count}× total`, sub: "still active" }]
                  : []),
                { label: "Last Updated", value: fmtDate(ctx.last_seen_at), sub: timeAgo(ctx.last_seen_at) },
              ].map((row, i, arr) => (
                <div key={i} className="relative flex gap-3 pb-4 last:pb-0">
                  <div className="flex flex-col items-center">
                    <span className="h-2.5 w-2.5 shrink-0 rounded-full border-2 border-violet-400 bg-[#0a0d16]" />
                    {i < arr.length - 1 && <span className="w-px flex-1 bg-white/10" />}
                  </div>
                  <div className="-mt-0.5">
                    <p className="text-[12px] font-bold text-white">{row.label}</p>
                    <p className="text-[11.5px] text-slate-400">{row.value} <span className="text-slate-600">· {row.sub}</span></p>
                  </div>
                </div>
              ))}
            </div>
          </Card>

          {companies.length > 0 && (
            <Card title="Affected Companies">
              <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3">
                {a.companies_affected.map((c, i) => (
                  <Link key={i} href={`/companies/${c.symbol}`}
                    className="group flex items-center gap-2.5 rounded-[12px] border border-white/[0.07] bg-white/[0.02] p-2.5 transition hover:border-violet-500/25 hover:bg-white/[0.04]">
                    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-violet-500/20 to-sky-500/20 text-[11px] font-black text-white">
                      {c.symbol.slice(0, 2)}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block break-words text-[12.5px] font-bold leading-tight text-white">{c.symbol}</span>
                      <span className={`block text-[10px] font-semibold capitalize ${c.impact === "positive" ? "text-emerald-400" : c.impact === "negative" ? "text-rose-400" : "text-slate-500"}`}>
                        {c.impact ?? "neutral"}
                      </span>
                    </span>
                    <ArrowRight className="h-3.5 w-3.5 shrink-0 text-slate-600 opacity-0 transition group-hover:opacity-100" />
                  </Link>
                ))}
              </div>
            </Card>
          )}

          {/* Populated by the async enrichment pass (signal_publisher.py's
              run_signal_enrichment_cycle) — real content, not fabricated
              for the page: absent entirely on a signal not yet enriched,
              rather than showing an empty/placeholder section. */}
          {a.what_happened && (
            <Card title="What Happened" icon={<BookOpen className="h-3.5 w-3.5 text-sky-400" />}>
              <p className="text-[13px] leading-relaxed text-slate-300">{a.what_happened}</p>
            </Card>
          )}

          {a.why_it_matters && (
            <Card title="Why It Matters" icon={<Sparkles className="h-3.5 w-3.5 text-violet-400" />}>
              <p className="text-[13px] leading-relaxed text-slate-300">{a.why_it_matters}</p>
            </Card>
          )}

          {(a.opportunities?.length || a.risks?.length) ? (
            <div className="grid gap-4 sm:grid-cols-2">
              {a.opportunities && a.opportunities.length > 0 && (
                <Card title="Opportunities" icon={<TrendingUp className="h-3.5 w-3.5 text-emerald-400" />}>
                  <div className="space-y-2.5">
                    {a.opportunities.map((o, i) => (
                      <div key={i} className="rounded-xl border border-emerald-500/15 bg-emerald-500/[0.04] p-3">
                        <p className="text-[12.5px] font-bold text-white">{o.title}</p>
                        <p className="mt-1 text-[12px] leading-relaxed text-slate-400">{o.description}</p>
                      </div>
                    ))}
                  </div>
                </Card>
              )}
              {a.risks && a.risks.length > 0 && (
                <Card title="Risks" icon={<TrendingDown className="h-3.5 w-3.5 text-rose-400" />}>
                  <div className="space-y-2.5">
                    {a.risks.map((r, i) => (
                      <div key={i} className="rounded-xl border border-rose-500/15 bg-rose-500/[0.04] p-3">
                        <p className="text-[12.5px] font-bold text-white">{r.title}</p>
                        <p className="mt-1 text-[12px] leading-relaxed text-slate-400">{r.description}</p>
                      </div>
                    ))}
                  </div>
                </Card>
              )}
            </div>
          ) : null}

          {a.faqs && a.faqs.length > 0 && (
            <Card title="Frequently Asked" icon={<HelpCircle className="h-3.5 w-3.5 text-slate-400" />}>
              <div className="space-y-2">
                {a.faqs.map((f, i) => (
                  <details key={i} className="group rounded-xl border border-white/[0.06] bg-white/[0.02] p-3.5">
                    <summary className="cursor-pointer text-[12.5px] font-semibold text-white">{f.question}</summary>
                    <p className="mt-2 text-[12px] leading-relaxed text-slate-400">{f.answer}</p>
                  </details>
                ))}
              </div>
            </Card>
          )}

          {ctx.signal_type === "historical_match" && (p.winners?.length || p.losers?.length) && (
            <Card title="Historical Pattern" icon={<History className="h-3.5 w-3.5 text-amber-500" />}>
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <p className="mb-1 text-[10px] font-bold uppercase tracking-wider text-slate-500">Previous Similar Event</p>
                  <p className="text-[14px] font-bold text-white">{p.headline}</p>
                  {p.similarity != null && (
                    <p className="mt-1 text-[12px] text-slate-400">Similarity <span className="font-bold text-amber-300">{Math.round(p.similarity)}%</span></p>
                  )}
                </div>
                <div className="flex gap-4">
                  {p.winners?.[0] && (
                    <div>
                      <p className="text-[10px] font-bold uppercase tracking-wider text-emerald-500">Winner</p>
                      <Link href={`/companies/${p.winners[0]}`} className="text-[14px] font-bold text-emerald-300 hover:underline">{p.winners[0]}</Link>
                    </div>
                  )}
                  {p.losers?.[0] && (
                    <div>
                      <p className="text-[10px] font-bold uppercase tracking-wider text-rose-500">Loser</p>
                      <Link href={`/companies/${p.losers[0]}`} className="text-[14px] font-bold text-rose-300 hover:underline">{p.losers[0]}</Link>
                    </div>
                  )}
                </div>
              </div>
              {p.key_lesson && (
                <p className="mt-3 border-t border-white/[0.06] pt-3 text-[13px] leading-relaxed text-slate-400">{p.key_lesson}</p>
              )}
            </Card>
          )}

          {ctx.signal_type === "early_theme" && p.opportunity_id != null && (
            <Card title="Related Opportunity" icon={<Radar className="h-3.5 w-3.5 text-emerald-500" />}>
              <Link href={`/opportunity-radar/${p.opportunity_id}`}
                className="flex items-center justify-between rounded-[12px] border border-emerald-500/20 bg-emerald-500/[0.05] px-4 py-3 transition hover:border-emerald-500/35">
                <span>
                  <span className="block text-[13.5px] font-bold text-white">{a.headline}</span>
                  <span className="text-[11.5px] text-slate-400">Opportunity Score {p.opportunity_score}</span>
                </span>
                <ArrowRight className="h-4 w-4 shrink-0 text-emerald-400" />
              </Link>
            </Card>
          )}

          <Card title="Continue Your Research">
            <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
              <Link href={`/ai-search?q=${encodeURIComponent(a.headline)}`}
                className="flex items-center justify-between rounded-[12px] border border-violet-500/20 bg-violet-500/[0.05] px-4 py-3 transition hover:border-violet-500/35">
                <span className="text-[13px] font-semibold text-violet-200">Ask MarketRipple AI</span>
                <ArrowRight className="h-4 w-4 text-violet-400" />
              </Link>
              <Link href="/research/comparisons"
                className="flex items-center justify-between rounded-[12px] border border-white/10 bg-white/[0.02] px-4 py-3 transition hover:border-white/20">
                <span className="text-[13px] font-semibold text-slate-300">Browse Research Hub</span>
                <ArrowRight className="h-4 w-4 text-slate-500" />
              </Link>
            </div>
          </Card>
        </div>

        {/* RIGHT — sticky sidebar */}
        <div className="space-y-4 md:sticky md:top-20 md:self-start">
          <Card>
            <p className="mb-3 text-[10px] font-bold uppercase tracking-[0.14em] text-slate-500">Intelligence Score</p>
            {score != null ? (
              <div className="flex items-end gap-1.5">
                <span className="text-4xl font-black text-white">{Math.round(score)}</span>
                <span className="mb-1 text-[13px] font-bold text-slate-500">%</span>
              </div>
            ) : (
              <p className="text-[13px] font-semibold text-slate-500">Not applicable to this signal type</p>
            )}
            <p className="mt-0.5 text-[11px] text-slate-500">{scoreLabel}</p>

            <div className="mt-4 space-y-2.5 border-t border-white/[0.06] pt-3.5">
              <div className="flex items-center justify-between text-[12px]">
                <span className="text-slate-500">Occurrence</span>
                <span className="font-semibold text-white">Seen {ctx.occurrence_count ?? 1}×</span>
              </div>
              <div className="flex items-center justify-between text-[12px]">
                <span className="text-slate-500">First Detected</span>
                <span className="font-semibold text-white">{fmtDate(ctx.first_detected_at)}</span>
              </div>
              <div className="flex items-center justify-between text-[12px]">
                <span className="text-slate-500">Last Updated</span>
                <span className="font-semibold text-white">{timeAgo(ctx.last_seen_at)}</span>
              </div>
            </div>
          </Card>

          <SignalActions headline={a.headline} url={url} companies={companies} opportunityId={p.opportunity_id} />
        </div>
      </div>
    </main>
  );
}
