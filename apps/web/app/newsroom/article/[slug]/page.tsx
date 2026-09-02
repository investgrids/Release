import type { Metadata } from "next";
import { notFound } from "next/navigation";
import Link from "next/link";
import {
  AlertTriangle, Building2, Clock,
  BookOpen, HelpCircle, Eye, ListChecks, Activity,
  Brain, Layers, GitCommit, RadioTower,
  Sparkles, ArrowRight, Compass, Database,
} from "lucide-react";
import { API_BASE_URL as API } from "@/lib/api";
import { cleanText, isRealSymbol, safeJsonLd } from "@/lib/text";
import { containsRecommendationLanguage } from "@/lib/recommendationLanguage";
import { ShareInsightCard } from "@/components/ShareInsightCard";
import { ArticleViewTracker } from "@/components/ArticleViewTracker";
import { ReadingProgressBar } from "@/components/ReadingProgressBar";
import { StickyShareBar } from "@/components/StickyShareBar";
import { HeroImage } from "@/components/HeroImage";
import { EvidenceList, type EvidenceFact } from "@/components/article/EvidenceList";
import { CompanyImpactTable } from "@/components/article/CompanyImpactTable";
import { ExploreNext } from "@/components/article/ExploreNext";
import { type CompanyAffected, type SectorAffected } from "./deriveVerdict";

// ── P0-CD1 — Public Claim Containment (2026-09-01) ─────────────────────────
// The P0-D audit (recommendation provenance) found that every one of this
// page's directional/actionable claims — AI Investment Verdict, Bullish/
// Bearish, "Current view: X on Y", Likely Winners/Losers, opportunities[0]
// as "Action", and public confidence percentages (P0-C: 4 incoherent
// producers, bimodal) — render unconditionally regardless of article type,
// with no field anywhere that lets this page tell a grounded claim apart
// from an ungrounded one. Per owner authorization, this page fails closed:
// those elements are suppressed at the presentation layer only. Nothing is
// deleted — companies_affected[].impact, sectors_affected[].impact,
// opportunities[], and confidence_score are all still fetched and still
// exist in the API response; this page simply stops rendering them as a
// public claim until P0-D's semantic-typing repair (impact.basis/
// evidence_ids) makes it safe to. See project_market_wrap_integrity_incident
// memory for the full audit trail. Reference implementations explicitly
// NOT touched by this change: /ripple's dated historical outcomes, and AI
// Search's InvestmentVerdictHero (refuses Buy/Sell wording already).

// ── Article type metadata — light-first, matching Daily Brief's own
// color-token convention (text-{c}-700 dark:text-{c}-300, border-{c}-200
// dark:border-{c}-500/30, bg-{c}-50 dark:bg-{c}-500/10) instead of the
// dark-only literals this page used before the redesign. ─────────────────

const TYPE_META: Record<string, { label: string; color: string }> = {
  breaking_intelligence:    { label: "Breaking Intelligence",   color: "text-rose-700 dark:text-rose-300 border-rose-200 dark:border-rose-500/30 bg-rose-50 dark:bg-rose-500/10" },
  morning_intelligence:     { label: "Morning Intelligence",    color: "text-amber-700 dark:text-amber-300 border-amber-200 dark:border-amber-500/30 bg-amber-50 dark:bg-amber-500/10" },
  company_intelligence:     { label: "Company Intelligence",    color: "text-sky-700 dark:text-sky-300 border-sky-200 dark:border-sky-500/30 bg-sky-50 dark:bg-sky-500/10" },
  sector_intelligence:      { label: "Sector Intelligence",     color: "text-violet-700 dark:text-violet-300 border-violet-200 dark:border-violet-500/30 bg-violet-50 dark:bg-violet-500/10" },
  theme_intelligence:       { label: "Theme Intelligence",      color: "text-violet-700 dark:text-violet-300 border-violet-200 dark:border-violet-500/30 bg-violet-50 dark:bg-violet-500/10" },
  policy_intelligence:      { label: "Policy Intelligence",     color: "text-indigo-700 dark:text-indigo-300 border-indigo-200 dark:border-indigo-500/30 bg-indigo-50 dark:bg-indigo-500/10" },
  ripple_intelligence:      { label: "Ripple Intelligence",     color: "text-cyan-700 dark:text-cyan-300 border-cyan-200 dark:border-cyan-500/30 bg-cyan-50 dark:bg-cyan-500/10" },
  opportunity_intelligence: { label: "Opportunity Intelligence", color: "text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-500/30 bg-emerald-50 dark:bg-emerald-500/10" },
  market_wrap:               { label: "Market Wrap",            color: "text-amber-700 dark:text-amber-300 border-amber-200 dark:border-amber-500/30 bg-amber-50 dark:bg-amber-500/10" },
  weekly_intelligence:       { label: "Weekly Intelligence",    color: "text-sky-700 dark:text-sky-300 border-sky-200 dark:border-sky-500/30 bg-sky-50 dark:bg-sky-500/10" },
  monthly_intelligence:      { label: "Monthly Intelligence",   color: "text-sky-700 dark:text-sky-300 border-sky-200 dark:border-sky-500/30 bg-sky-50 dark:bg-sky-500/10" },
  educational_intelligence:  { label: "Investor Education",     color: "text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-500/30 bg-emerald-50 dark:bg-emerald-500/10" },
  question_intelligence:     { label: "Investor Q&A",           color: "text-pink-700 dark:text-pink-300 border-pink-200 dark:border-pink-500/30 bg-pink-50 dark:bg-pink-500/10" },
  historical_intelligence:   { label: "Historical Intelligence", color: "text-amber-700 dark:text-amber-300 border-amber-200 dark:border-amber-500/30 bg-amber-50 dark:bg-amber-500/10" },
};
const DEFAULT_TYPE_META = { label: "Market Intelligence", color: "text-text-secondary border-surface-border/20 bg-text-primary/5" };

// ── Types ─────────────────────────────────────────────────────────────────────
// CompanyAffected/SectorAffected live in ./deriveVerdict.ts (imported above)
// — page.tsx can't export arbitrary names past Next's route type-checker,
// and deriveVerdict needs them importable from its own test file.

interface Opportunity { title: string; description: string; timeframe?: string; risk?: string; }
interface Risk { title: string; description: string; severity?: string; mitigation?: string; }
interface RippleLink { from_entity: string; to_entity: string; mechanism: string; timeframe?: string; }
interface HistoricalEvent { event?: string; date?: string; category?: string; outcome?: number | null; sentiment?: string; }
interface Faq { question: string; answer: string; }
interface RelatedCompany { symbol: string; name: string; link: string; }
interface RelatedTheme { theme: string; link: string; }
interface RelatedArticle { slug: string; headline: string; angle: string; angle_entity?: string | null; article_type: string; }
interface LinkCandidate { label: string; href: string; type: string; }
interface UpdateEntry {
  at: string; version: number; reason: string; summary: string;
  previous_takeaway?: string | null; new_takeaway?: string | null; confidence?: number;
}

interface InsightDetail {
  id: string; slug: string; article_type: string;
  hero_image_url?: string | null;
  headline: string; key_takeaway?: string; executive_summary?: string;
  seo_title?: string; meta_description?: string;
  why_it_matters?: string; what_happened?: string;
  companies_affected: CompanyAffected[];
  sectors_affected: SectorAffected[];
  opportunities: Opportunity[];
  risks: Risk[];
  historical_events: HistoricalEvent[];
  ripple_effect: RippleLink[];
  what_to_watch_next: string[];
  faqs: Faq[];
  sources: string[];
  related_companies: RelatedCompany[];
  related_themes: RelatedTheme[];
  related_articles: RelatedArticle[];
  angle: string;
  angle_entity?: string | null;
  is_evergreen?: boolean;
  confidence_score?: number;
  canonical_url?: string;
  json_ld?: Record<string, unknown>;
  published_at?: string;
  last_updated?: string;
  created_at?: string;
  story_version?: number;
  update_count?: number;
  views?: number;
  share_count?: number;
  update_history?: UpdateEntry[];
  parent_event_group_id?: string | null;
  // SEO Intelligence (Phase 3, wired into the article surface as part of
  // the AI Newsroom redesign, 2026-08-10) — deterministic, computed at
  // publish time from this article's own real companies/sectors, never a
  // second LLM call. See apps/backend/app/services/seo_intelligence.py.
  headline_angle?: string | null;
  primary_keyword?: string | null;
  secondary_keywords?: string[];
  entity_keywords?: string[];
  question_keywords?: string[];
  internal_link_candidates?: LinkCandidate[];
}

// ── Fetch ─────────────────────────────────────────────────────────────────────

// Cleans every real AIPE-authored text field once, at the data layer,
// rather than sprinkling cleanText() through the JSX below — the
// mojibake/HTML-entity issue (see lib/text.ts) can appear in any of these
// fields since they're all real ingested/generated text.
function cleanArticle(a: InsightDetail): InsightDetail {
  return {
    ...a,
    headline: cleanText(a.headline),
    key_takeaway: a.key_takeaway ? cleanText(a.key_takeaway) : a.key_takeaway,
    executive_summary: a.executive_summary ? cleanText(a.executive_summary) : a.executive_summary,
    why_it_matters: a.why_it_matters ? cleanText(a.why_it_matters) : a.why_it_matters,
    what_happened: a.what_happened ? cleanText(a.what_happened) : a.what_happened,
    // Drop entries where the symbol couldn't be resolved to a real ticker
    // (the backend's normalize_symbol already returns null for these — see
    // app/services/symbol_normalization.py — rather than a fabricated or
    // malformed one) — these would otherwise render as broken
    // /companies/{symbol} links elsewhere on this page, not just odd text.
    companies_affected: (a.companies_affected ?? []).filter(c => isRealSymbol(c.symbol)).map(c => ({ ...c, name: cleanText(c.name), reason: c.reason ? cleanText(c.reason) : c.reason })),
    sectors_affected: (a.sectors_affected ?? []).map(s => ({ ...s, name: cleanText(s.name), reason: s.reason ? cleanText(s.reason) : s.reason })),
    opportunities: (a.opportunities ?? []).map(o => ({ ...o, title: cleanText(o.title), description: cleanText(o.description) })),
    risks: (a.risks ?? []).map(r => ({ ...r, title: cleanText(r.title), description: cleanText(r.description), mitigation: r.mitigation ? cleanText(r.mitigation) : r.mitigation })),
    historical_events: (a.historical_events ?? []).map(h => ({ ...h, event: h.event ? cleanText(h.event) : h.event })),
    ripple_effect: (a.ripple_effect ?? []).map(r => ({ ...r, from_entity: cleanText(r.from_entity), to_entity: cleanText(r.to_entity), mechanism: cleanText(r.mechanism) })),
    what_to_watch_next: (a.what_to_watch_next ?? []).map(cleanText),
    faqs: (a.faqs ?? []).map(f => ({ question: cleanText(f.question), answer: cleanText(f.answer) })),
    related_companies: (a.related_companies ?? []).map(c => ({ ...c, name: cleanText(c.name) })),
    related_themes: (a.related_themes ?? []).map(t => ({ ...t, theme: cleanText(t.theme) })),
    related_articles: (a.related_articles ?? []).map(r => ({ ...r, headline: cleanText(r.headline) })),
    update_history: (a.update_history ?? []).map(u => ({
      ...u, reason: cleanText(u.reason),
      previous_takeaway: u.previous_takeaway ? cleanText(u.previous_takeaway) : u.previous_takeaway,
      new_takeaway: u.new_takeaway ? cleanText(u.new_takeaway) : u.new_takeaway,
    })),
  };
}

async function fetchInsight(slug: string): Promise<InsightDetail | null> {
  try {
    const res = await fetch(`${API}/api/insights/${slug}`, { next: { revalidate: 1800 } });
    if (!res.ok) return null;
    const raw: InsightDetail = await res.json();
    return cleanArticle(raw);
  } catch {
    return null;
  }
}

interface Quote { price_str: string; change_pct_str: string; positive: boolean }

// Short revalidate (unlike the article's own 30-min cache) — this is the
// one genuinely time-sensitive number on the page, and the "Live Article"
// framing only means anything if the price actually is close to live.
async function fetchQuotes(symbols: string[]): Promise<Record<string, Quote>> {
  if (!symbols.length) return {};
  try {
    const res = await fetch(`${API}/api/data/quotes?symbols=${encodeURIComponent(symbols.join(","))}`, { next: { revalidate: 60 } });
    if (!res.ok) return {};
    const data = await res.json();
    const out: Record<string, Quote> = {};
    for (const q of data.quotes ?? []) {
      out[q.symbol] = { price_str: q.price_str, change_pct_str: q.change_pct_str, positive: q.positive };
    }
    return out;
  } catch {
    return {};
  }
}

// Legacy-history containment patch (2026-09-01): u.reason was assumed
// safe (a meta-description of why an update happened, e.g. "Market
// narrative updated: Bullish"), but a real pre-CD2 article proved that
// assumption wrong — its stored reason was literally "Auto moved -2.2%
// today | Market narrative updated: Cautious ...", the exact unrelated-
// sector-contamination shape continuous_updater.py's CD2 fix addresses
// going forward, just already persisted. Gated the same way as
// key_takeaway: omit the unsafe text, fall back to a generic label,
// never rewrite it into something that merely sounds safer.
function safeReason(reason: string): string {
  return containsRecommendationLanguage(reason) ? "Article updated" : reason;
}

function fmtDate(iso?: string) {
  if (!iso) return null;
  return new Date(iso).toLocaleString("en-IN", {
    day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit",
  });
}
function fmtRelative(iso?: string): string {
  if (!iso) return "";
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return "";
  const diffMin = Math.floor((Date.now() - t) / 60000);
  if (diffMin < 1) return "just now";
  if (diffMin < 60) return `${diffMin} min ago`;
  const hr = Math.floor(diffMin / 60);
  if (hr < 24) return `${hr}h ago`;
  return `${Math.floor(hr / 24)}d ago`;
}

// Plain CSS dots, not emoji — emoji glyphs render inconsistently across
// platforms (Windows in particular renders "⚪"/"🟡" as shaded/glossy
// spheres, clashing with this flat design system).
const RISK_DOT: Record<string, string> = { low: "bg-emerald-500", medium: "bg-amber-500", high: "bg-rose-500" };
const MAGNITUDE_BARS: Record<string, number> = { high: 4, medium: 2, low: 1 };

// Event Evolution — derived from real timestamps, not a stored field:
// Active = touched in the last 24h, Monitoring = within 7 days, Resolved =
// older than that but still a live event type, Historical = evergreen/
// historical content by nature (never "resolves", it's timeless by design).
function deriveEventStatus(article: { article_type: string; is_evergreen?: boolean; last_updated?: string; published_at?: string }): { label: string; color: string; icon: typeof Activity } {
  if (article.is_evergreen || article.article_type === "historical_intelligence" || article.article_type === "educational_intelligence") {
    return { label: "Historical", color: "text-text-secondary border-surface-border/15 bg-text-primary/5", icon: BookOpen };
  }
  const anchor = article.last_updated || article.published_at;
  const hoursSince = anchor ? (Date.now() - new Date(anchor).getTime()) / 3_600_000 : Infinity;
  if (hoursSince <= 24) return { label: "Active", color: "text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-500/30 bg-emerald-50 dark:bg-emerald-500/10", icon: RadioTower };
  if (hoursSince <= 24 * 7) return { label: "Monitoring", color: "text-amber-700 dark:text-amber-300 border-amber-200 dark:border-amber-500/30 bg-amber-50 dark:bg-amber-500/10", icon: Activity };
  return { label: "Resolved", color: "text-sky-700 dark:text-sky-300 border-sky-200 dark:border-sky-500/30 bg-sky-50 dark:bg-sky-500/10", icon: GitCommit };
}

// ── Metadata ──────────────────────────────────────────────────────────────────

export async function generateMetadata(
  { params }: { params: Promise<{ slug: string }> }
): Promise<Metadata> {
  const { slug } = await params;
  const article = await fetchInsight(slug);
  if (!article) return { title: "Not Found" };

  const title = article.seo_title || article.headline;
  // Legacy-history containment patch (2026-09-01): the key_takeaway
  // fallback here feeds <meta name="description">, og:description, and
  // twitter:description directly — a real leak path this patch's original
  // pass missed (it only gated the visible 30-Second Answer/Intelligence
  // Timeline renderings of the same field, not this metadata fallback).
  const safeKeyTakeaway = article.key_takeaway && !containsRecommendationLanguage(article.key_takeaway) ? article.key_takeaway : "";
  // Same gate applied to executive_summary — a real live example (this
  // exact article) proved it can carry the identical unsafe language
  // ("...consider shorting over-valued circuit-climbed stocks.") and was
  // the actual source of the leak here, since it's the first fallback,
  // ahead of key_takeaway, when meta_description is empty.
  const safeExecutiveSummary = article.executive_summary && !containsRecommendationLanguage(article.executive_summary) ? article.executive_summary : "";
  const description = article.meta_description || safeExecutiveSummary || safeKeyTakeaway || "";
  // Real per-article AI-generated hero images exist for a real subset of
  // articles (served from the backend at /api/media/{id}.jpg) but were
  // never read here — og:image/twitter:image were silently absent even
  // when a real image existed, hurting social-share CTR and Article
  // rich-result eligibility. Omitted entirely (not a placeholder) when
  // the article has none, consistent with this app's "never fabricate"
  // rule — no article, no image, no invented stock photo.
  const image = article.hero_image_url ? `${API}${article.hero_image_url}` : null;
  // entity_keywords are real (every term traceable to this article's own
  // companies/sectors/themes — see seo_intelligence.py's module docstring),
  // so surfacing them as a <meta name="keywords"> tag doesn't fabricate
  // anything; it's a plain-text restatement of entities already on the page.
  const keywords = (article.entity_keywords ?? []).length > 0 ? article.entity_keywords : undefined;

  return {
    title,
    description,
    keywords,
    openGraph: {
      title,
      description,
      type: "article",
      siteName: "MarketRipple",
      ...(image ? { images: [{ url: image }] } : {}),
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
      ...(image ? { images: [image] } : {}),
    },
    alternates: {
      canonical: article.canonical_url || `/newsroom/article/${slug}`,
    },
  };
}

// ── Small presentational helpers ────────────────────────────────────────────

// Light-first card, matching Daily Brief's own token pattern (rounded-2xl
// border-surface-border/7 bg-text-primary/[0.02]) rather than the article
// page's old dark-only bg-surface-card/90 fill.
function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <div className={`rounded-2xl border border-surface-border/7 bg-text-primary/[0.02] ${className}`}>{children}</div>;
}
function Eyebrow({ icon: Icon, children }: { icon: typeof Activity; children: React.ReactNode }) {
  return (
    <h2 className="mb-4 flex items-center gap-2 text-[11px] font-bold uppercase tracking-wide text-text-muted">
      <Icon className="h-3.5 w-3.5" /> {children}
    </h2>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default async function ArticlePage(
  { params }: { params: Promise<{ slug: string }> }
) {
  const { slug } = await params;
  const article = await fetchInsight(slug);
  if (!article || !article.headline) notFound();

  const meta = TYPE_META[article.article_type] ?? DEFAULT_TYPE_META;
  // Legacy-history containment patch (2026-09-01): single source of truth
  // for every place on this page that used to read article.key_takeaway
  // directly — the 30-Second Answer box, Intelligence Timeline's "Article
  // Published" entry, and the share-card summaries below all now go
  // through this instead of their own separate (and, first time round,
  // incomplete) inline check.
  const safeKeyTakeaway = article.key_takeaway && !containsRecommendationLanguage(article.key_takeaway) ? article.key_takeaway : null;
  // Same gate on executive_summary — real live example (this exact
  // article, via the share-card summary fallback) proved it can carry the
  // identical unsafe language independently of key_takeaway.
  const safeExecutiveSummary = article.executive_summary && !containsRecommendationLanguage(article.executive_summary) ? article.executive_summary : null;
  const companies = article.companies_affected ?? [];
  const quotes = await fetchQuotes(companies.filter(c => isRealSymbol(c.symbol)).map(c => c.symbol as string));
  const sectors = article.sectors_affected ?? [];
  const risks = article.risks ?? [];
  const historical = article.historical_events ?? [];
  const rippleLinks = article.ripple_effect ?? [];
  const watch = article.what_to_watch_next ?? [];
  const faqs = article.faqs ?? [];
  const relatedCompanies = article.related_companies ?? [];
  const relatedThemes = article.related_themes ?? [];
  const relatedArticles = article.related_articles ?? [];
  const sources = article.sources ?? [];
  const questionSiblings = relatedArticles.filter(r => r.angle === "question");
  const updateHistory = article.update_history ?? [];
  const status = deriveEventStatus(article);
  const StatusIcon = status.icon;

  // Real, historically-verified base rate — only shown when the article
  // actually cites measured outcomes, never estimated.
  const measuredOutcomes = historical.filter(h => h.outcome != null);
  const positiveOutcomeRate = measuredOutcomes.length
    ? Math.round((measuredOutcomes.filter(h => (h.outcome ?? 0) >= 0).length / measuredOutcomes.length) * 100)
    : null;


  // Article-level Evidence (Decision 3) — built entirely from fields already
  // on this article, split into what happened (Fact) vs the AI's own read
  // of it (Interpretation). No new engine, no Fact Registry extension.
  const evidenceFacts: EvidenceFact[] = [
    ...(article.published_at ? [{ label: "Published", detail: fmtDate(article.published_at) ?? undefined }] : []),
    ...((article.update_count ?? 0) > 0 && article.last_updated
      ? [{ label: `Updated ${article.update_count}×`, detail: fmtDate(article.last_updated) ?? undefined }] : []),
    ...historical.slice(0, 6).map(h => ({
      label: h.event ?? "Historical precedent",
      detail: [h.date, h.outcome != null ? `${h.outcome >= 0 ? "+" : ""}${h.outcome}%` : null].filter(Boolean).join(" — ") || undefined,
    })),
  ];
  // opportunities[] deliberately excluded here (P0-CD1) — their titles are
  // actionable Buy/Sell/Wait-style recommendations (P0-D), and this list
  // renders as "AI Interpretation" evidence, not flagged as a suppressed
  // section, so it was a real leak path for the exact claims Phase 1
  // suppresses everywhere else on this page.
  const evidenceInterpretations: EvidenceFact[] = [
    ...[...companies, ...sectors].filter(x => x.reason).slice(0, 5).map(x => ({
      label: x.name, detail: x.reason,
    })),
    ...risks.slice(0, 3).map(r => ({ label: r.title, detail: r.description })),
    ...watch.slice(0, 3).map(w => ({ label: "What to watch", detail: w })),
  ];

  // Hero images are generated asynchronously by a worker some time after
  // publish (see image_worker.py) — json_ld is built once at publish time
  // and never touched again for this field, so it can never carry an image
  // the backend didn't have yet. Overlaying it here, at render time, means
  // the very next page load after the image lands gets a correct Article
  // schema — no backend job needs to remember to go back and patch it.
  // entity_keywords/secondary_keywords are appended the same way — real,
  // already-computed SEO fields the backend didn't have when json_ld was
  // first built for older articles.
  const jsonLd = article.json_ld ? {
    ...article.json_ld,
    ...(article.hero_image_url ? { image: `${API}${article.hero_image_url}` } : {}),
    ...(article.secondary_keywords?.length ? { keywords: article.secondary_keywords.join(", ") } : {}),
    ...(article.entity_keywords?.length ? { about: article.entity_keywords.map(name => ({ "@type": "Thing", name })) } : {}),
  } : article.json_ld;

  return (
    <main className="min-h-screen bg-bg text-text-primary">
      {jsonLd && (
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: safeJsonLd(jsonLd) }}
        />
      )}

      <ReadingProgressBar />
      <StickyShareBar
        entityType="article"
        entityId={article.slug}
        title={article.headline}
        summary={safeKeyTakeaway ?? safeExecutiveSummary ?? undefined}
        shareCount={article.share_count}
      />

      <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6">

        <ArticleViewTracker slug={article.slug} />

        {/* Breadcrumb */}
        <div className="mb-6 flex items-center justify-between gap-3">
          <nav className="flex min-w-0 items-center gap-2 text-[11px] text-text-muted">
            <Link href="/" className="hover:text-text-secondary transition">MarketRipple</Link>
            <span>/</span>
            <Link href="/newsroom" className="hover:text-text-secondary transition">AI Newsroom</Link>
            <span>/</span>
            <span className="truncate text-text-secondary">{article.headline}</span>
          </nav>
          <ShareInsightCard
            entityType="article"
            entityId={article.slug}
            title={article.headline}
            summary={safeKeyTakeaway ?? safeExecutiveSummary ?? undefined}
            shareCount={article.share_count}
            className="shrink-0"
          />
        </div>

        {/* ══════════════════════ TIER 1 — ABOVE THE FOLD ══════════════════════ */}

        <div className="mb-8">
          <HeroImage
            heroImageUrl={article.hero_image_url}
            headline={article.headline}
            articleType={article.article_type}
            sectors={(article.sectors_affected ?? []).map(s => s.name)}
            className="mb-5 h-56 w-full rounded-2xl sm:h-72"
          />
          <div className="flex flex-wrap items-center gap-2">
            <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider ${meta.color}`}>
              <BookOpen className="h-2.5 w-2.5" /> {meta.label}
            </span>
            <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider ${status.color}`}>
              <StatusIcon className="h-2.5 w-2.5" /> {status.label}
            </span>
            {article.angle_entity && article.angle !== "primary" && (
              <span className="inline-flex items-center rounded-full border border-surface-border/10 bg-text-primary/5 px-2.5 py-0.5 text-[10px] font-medium text-text-secondary">
                Focused on {article.angle_entity}
              </span>
            )}
          </div>
          <h1 className="mt-3 text-[26px] font-black leading-tight text-text-primary sm:text-[32px]">
            {article.headline}
          </h1>
          {/* Visible author/publisher disclosure — the JSON-LD schema above
              already declares this to crawlers, but a human reader saw
              nothing on the page itself. */}
          <p className="mt-2 flex items-center gap-1.5 text-[12px] text-text-muted">
            <Brain className="h-3.5 w-3.5 text-accent-violet" />
            By <span className="font-semibold text-text-secondary">MarketRipple AI Intelligence Engine</span> — AI-generated from real market data, not written by a human reporter.
          </p>
          <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1.5">
            {article.published_at && (
              <span className="flex items-center gap-1 text-[11px] text-text-muted">
                <Clock className="h-3 w-3" /> Published {fmtRelative(article.published_at)}
              </span>
            )}
            {(article.update_count ?? 0) > 0 && (
              <span className="flex items-center gap-1 text-[11px] font-semibold text-sky-600 dark:text-sky-300">
                <Eye className="h-3 w-3" /> Updated {article.update_count}× · last {fmtRelative(article.last_updated)}
              </span>
            )}
            <span className="flex items-center gap-1 text-[11px] text-text-muted">
              <Eye className="h-3 w-3" /> {(article.views ?? 0).toLocaleString("en-IN")} read this
            </span>
            {article.parent_event_group_id && (
              <span className="flex items-center gap-1 text-[11px] text-accent-violet">
                <Layers className="h-3 w-3" /> Part of a {relatedArticles.length + 1}-article campaign
              </span>
            )}
          </div>
        </div>

        {/* Above-the-fold: 30-second answer + quick facts (the "prove it").
            P0-CD1 (2026-09-01): the AI Investment Verdict card that used to
            sit alongside this — Bullish/Bearish stance, "Current view: X on
            Y", top opportunity as "Action", confidence % — is suppressed
            here. See the header comment for why. */}
        <div className="mb-8 space-y-4">
          {/* Legacy-history containment patch (2026-09-01): key_takeaway is
              a free-text field that predates CD2's generation-side fix —
              real live example, this exact article: "Consider shorting
              over-valued circuit-climbed names like Hy-Tech Engineers and
              TBZ..." was still surfacing here as the "30-Second Answer"
              despite the dedicated verdict/opportunities UI already being
              suppressed elsewhere on the page. Same fail-closed rule as the
              rest of CD1 — omit rather than show, never rewrite the text
              into something that merely sounds safer. */}
          {safeKeyTakeaway && (
            <div className="rounded-2xl border border-accent-violet/20 bg-accent-violet/[0.05] p-5">
              <p className="mb-2 text-[11px] font-bold uppercase tracking-wide text-accent-violet">30-Second Answer</p>
              <p className="text-[13.5px] leading-relaxed text-text-primary">{safeKeyTakeaway}</p>
            </div>
          )}
          <div className="grid grid-cols-3 gap-3 rounded-2xl border border-surface-border/7 bg-text-primary/[0.02] p-4">
            <div>
              <p className="text-[9.5px] font-bold uppercase tracking-wide text-text-muted">Companies</p>
              <p className="mt-0.5 text-[15px] font-bold tabular-nums text-text-primary">{companies.length}</p>
            </div>
            <div>
              <p className="text-[9.5px] font-bold uppercase tracking-wide text-text-muted">Sectors</p>
              <p className="mt-0.5 text-[15px] font-bold tabular-nums text-text-primary">{sectors.length}</p>
            </div>
            <div>
              <p className="text-[9.5px] font-bold uppercase tracking-wide text-text-muted">Sources</p>
              <p className="mt-0.5 text-[15px] font-bold tabular-nums text-text-primary">{sources.length}</p>
            </div>
          </div>
        </div>

        {/* ══════════════════════ TIER 2 — CORE INTELLIGENCE ══════════════════════ */}

        {article.why_it_matters && (
          <section className="mb-8">
            <Eyebrow icon={Sparkles}>Why It Matters</Eyebrow>
            <p className="whitespace-pre-line text-[14px] leading-7 text-text-secondary">{article.why_it_matters}</p>
          </section>
        )}
        {article.what_happened && (
          <section className="mb-8">
            <Eyebrow icon={Activity}>What Happened</Eyebrow>
            <p className="whitespace-pre-line text-[14px] leading-7 text-text-secondary">{article.what_happened}</p>
          </section>
        )}

        {(sectors.length > 0 || rippleLinks.length > 0) && (
          <div className="mb-8 grid grid-cols-1 gap-4 lg:grid-cols-2">
            {sectors.length > 0 && (
              <section>
                <Eyebrow icon={Layers}>Sector Impact</Eyebrow>
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  {/* P0-CD1: the positive/negative/neutral pill and the
                      sign-colored magnitude bars are dropped — same
                      unprovenanced `impact` field as companies_affected,
                      same suppression. Magnitude (how much this sector was
                      discussed) still renders, just direction-neutral. */}
                  {sectors.map((s, i) => (
                    <Card key={i} className="p-4">
                      <span className="text-[13px] font-bold text-text-primary">{s.name}</span>
                      {s.magnitude && (
                        <div className="mt-2 flex items-center gap-1">
                          {[1, 2, 3, 4].map(n => (
                            <span key={n} className={`h-1.5 w-5 rounded-full ${n <= MAGNITUDE_BARS[s.magnitude!] ? "bg-sky-400" : "bg-text-primary/10"}`} />
                          ))}
                          <span className="ml-1.5 text-[10px] uppercase tracking-wide text-text-muted">{s.magnitude} magnitude</span>
                        </div>
                      )}
                      {s.reason && <p className="mt-2 text-[12px] leading-5 text-text-secondary">{s.reason}</p>}
                    </Card>
                  ))}
                </div>
              </section>
            )}

            {rippleLinks.length > 0 && (
              <section>
                <Eyebrow icon={Compass}>Ripple Effect</Eyebrow>
                <Card className="p-5">
                  <div className="space-y-4">
                    {rippleLinks.map((r, i) => (
                      <div key={i} className="flex items-start gap-3">
                        <div className="flex flex-col items-center pt-1">
                          <span className="h-2.5 w-2.5 rounded-full bg-accent-violet" />
                          {i < rippleLinks.length - 1 && <span className="mt-1 h-8 w-px bg-text-primary/10" />}
                        </div>
                        <div className="flex-1">
                          <div className="flex flex-wrap items-center gap-1.5 text-[13px] font-bold text-text-primary">
                            {r.from_entity} <ArrowRight className="h-3.5 w-3.5 text-accent-violet" /> {r.to_entity}
                          </div>
                          <p className="mt-1 text-[12px] leading-5 text-text-secondary">{r.mechanism}</p>
                          {r.timeframe && <span className="mt-1 inline-block text-[10px] uppercase tracking-wide text-text-muted">{r.timeframe}-term</span>}
                        </div>
                      </div>
                    ))}
                  </div>
                </Card>
              </section>
            )}
          </div>
        )}

        {companies.length > 0 && (
          <section className="mb-8">
            <Eyebrow icon={Building2}>Company Impact</Eyebrow>
            <CompanyImpactTable companies={companies as { symbol: string; name: string; impact: "positive" | "negative" | "neutral"; reason?: string; timeframe?: string }[]} quotes={quotes} showImpact={false} />
          </section>
        )}

        {/* P0-CD1 (2026-09-01): "Likely Winners"/"Likely Losers" (grouping
            companies by the same unprovenanced `impact` field as the
            verdict card) and "Investment Opportunities" (opportunities[]
            rendered as Buy/Sell/Wait-style recommendations — P0-D found
            this is prompt-intended across every article type, not drift)
            are both suppressed. opportunities[] is still fetched and still
            in the API response; it just doesn't render publicly as advice
            here. Risks stays — descriptive, not a directional claim. */}
        {risks.length > 0 && (
          <section className="mb-8">
            <Eyebrow icon={AlertTriangle}>Risks</Eyebrow>
            <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
              {risks.map((r, i) => (
                <div key={i} className={`rounded-xl border p-4 ${
                  r.severity === "high" ? "border-rose-200 dark:border-rose-500/20 bg-rose-50 dark:bg-rose-500/[0.04]" : "border-amber-200 dark:border-amber-500/15 bg-amber-50 dark:bg-amber-500/[0.04]"
                }`}>
                  <div className="flex items-start justify-between gap-3">
                    <h3 className={`text-[13px] font-semibold ${r.severity === "high" ? "text-rose-700 dark:text-rose-300" : "text-amber-700 dark:text-amber-300"}`}>
                      {r.title}
                    </h3>
                    {r.severity && (
                      <span className={`shrink-0 rounded-full border px-2 py-0.5 text-[10px] capitalize ${
                        r.severity === "high"
                          ? "border-rose-200 dark:border-rose-500/20 bg-rose-50 dark:bg-rose-500/10 text-rose-700 dark:text-rose-300"
                          : "border-amber-200 dark:border-amber-500/20 bg-amber-50 dark:bg-amber-500/10 text-amber-700 dark:text-amber-300"
                      }`}>{r.severity}</span>
                    )}
                  </div>
                  <p className="mt-1.5 text-[12px] leading-5 text-text-secondary">{r.description}</p>
                  {r.mitigation && (
                    <p className="mt-1.5 text-[11px] leading-5 text-text-muted">
                      <span className="font-semibold text-text-muted">How to manage: </span>{r.mitigation}
                    </p>
                  )}
                </div>
              ))}
            </div>
          </section>
        )}

        {/* ══════════════════════ TIER 3 — DEEPER INTELLIGENCE ══════════════════════ */}

        {(historical.length > 0 || updateHistory.length > 0) && (
          <div className="mb-8 grid grid-cols-1 gap-4 lg:grid-cols-2">
            {historical.length > 0 && (
              <section>
                <Eyebrow icon={Database}>Historical Intelligence</Eyebrow>
                <Card className="p-5">
                  <div className="space-y-2.5">
                    {historical.map((h, i) => (
                      <div key={i} className="flex items-start justify-between gap-3 text-[13px]">
                        <div>
                          <span className="text-text-secondary">{h.event}</span>
                          {h.category && <span className="ml-2 text-[10px] uppercase tracking-wider text-text-muted">{h.category}</span>}
                        </div>
                        <div className="flex shrink-0 items-center gap-2 text-text-muted">
                          <span>{h.date}</span>
                          {h.outcome != null && (
                            <span className={h.outcome >= 0 ? "text-emerald-600 dark:text-emerald-400" : "text-rose-600 dark:text-rose-400"}>
                              {h.outcome >= 0 ? "+" : ""}{h.outcome}%
                            </span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                  {positiveOutcomeRate != null && (
                    <div className="mt-4 flex items-center gap-3 rounded-xl border border-surface-border/6 bg-text-primary/[0.02] p-3.5">
                      <span className="text-[22px] font-black text-emerald-600 dark:text-emerald-400">{positiveOutcomeRate}%</span>
                      <span className="text-[12px] leading-5 text-text-secondary">
                        of {measuredOutcomes.length} similar historical events saw a positive outcome
                      </span>
                    </div>
                  )}
                </Card>
              </section>
            )}

            {updateHistory.length > 0 && (
              <section>
                <Eyebrow icon={Activity}>Intelligence Timeline</Eyebrow>
                <div className="space-y-0">
                  <div className="relative pl-6 pb-5">
                    <span className="absolute left-0 top-1 h-3 w-3 rounded-full bg-sky-500" />
                    <span className="absolute left-[5px] top-4 bottom-0 w-px bg-text-primary/10" />
                    <p className="text-[10px] font-bold uppercase tracking-wider text-sky-600 dark:text-sky-300">
                      {fmtDate(article.created_at || article.published_at)}
                    </p>
                    <p className="text-[13px] font-semibold text-text-primary">Article Published</p>
                    {/* Legacy-history containment patch (2026-09-01): same
                        gate as the 30-Second Answer above — this is the
                        same field, just re-displayed here. */}
                    {safeKeyTakeaway && (
                      <p className="mt-0.5 text-[12px] text-text-muted line-clamp-2">{safeKeyTakeaway}</p>
                    )}
                  </div>
                  {/* P0-CD1: the version-over-version confidence % delta is
                      suppressed along with every other public confidence
                      percentage on this page — same P0-C provenance gap.
                      Legacy-history patch: new_takeaway free text dropped
                      entirely (metadata only — date/version/reason); u.reason
                      itself also gated (see safeReason) — proven live that
                      it can carry the same unrelated-sector-contamination
                      shape CD2's continuous_updater.py fix addresses going
                      forward, just already persisted for this article. */}
                  {updateHistory.map((u, i) => {
                    return (
                      <div key={i} className="relative pl-6 pb-5">
                        <span className="absolute left-0 top-1 h-3 w-3 rounded-full bg-emerald-500" />
                        {i < updateHistory.length - 1 && <span className="absolute left-[5px] top-4 bottom-0 w-px bg-text-primary/10" />}
                        <p className="text-[10px] font-bold uppercase tracking-wider text-emerald-600 dark:text-emerald-300">{fmtDate(u.at)} · v{u.version}</p>
                        <p className="text-[13px] font-semibold text-text-primary">{safeReason(u.reason)}</p>
                      </div>
                    );
                  })}
                </div>
              </section>
            )}
          </div>
        )}

        {updateHistory.length > 0 && (
          <section className="mb-8">
            <Eyebrow icon={Brain}>AI Opinion Evolution</Eyebrow>
            {/* Legacy-history containment patch (2026-09-01): this section
                used to replay the article's own stored opinion-evolution
                free text (previous_takeaway/new_takeaway/summary) verbatim
                — a real, confirmed leak path for pre-CD2 recommendation
                language that CD1's structural suppression elsewhere on
                this page never touched (this exact article's "Consider
                shorting over-valued circuit-climbed names..." was still
                visible here across multiple versions). Simplified to
                metadata only, per owner instruction — timestamps and the
                same safe update_reason used in Intelligence Timeline above,
                never the generated conclusion text. */}
            <Card className="p-5">
              <div className="space-y-2">
                <div className="flex items-center justify-between rounded-xl border border-surface-border/6 bg-text-primary/[0.02] p-3.5">
                  <p className="text-[12px] font-semibold text-text-primary">Original</p>
                  <p className="text-[11px] text-text-muted">{fmtDate(article.created_at || article.published_at)}</p>
                </div>
                {updateHistory.map((u, i) => (
                  <div key={i} className={`ml-4 flex items-center justify-between rounded-xl border p-3.5 ${i === updateHistory.length - 1 ? "border-emerald-200 dark:border-emerald-500/15 bg-emerald-50 dark:bg-emerald-500/[0.04]" : "border-surface-border/6 bg-text-primary/[0.02]"}`}>
                    <div className="min-w-0">
                      <p className={`text-[12px] font-semibold ${i === updateHistory.length - 1 ? "text-emerald-700 dark:text-emerald-400" : "text-text-primary"}`}>
                        {i === updateHistory.length - 1 ? "Current" : `Updated (v${u.version})`}
                      </p>
                      <p className="mt-0.5 text-[11px] text-text-muted line-clamp-1">{safeReason(u.reason)}</p>
                    </div>
                    <p className="shrink-0 pl-3 text-[11px] text-text-muted">{fmtDate(u.at)}</p>
                  </div>
                ))}
              </div>
            </Card>
          </section>
        )}

        {watch.length > 0 && (
          <section className="mb-8">
            <Eyebrow icon={ListChecks}>What to Watch Next</Eyebrow>
            <ul className="space-y-2">
              {watch.map((pt, i) => (
                <li key={i} className="flex items-start gap-2.5 text-[13px] text-text-secondary">
                  <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-sky-500" />
                  {pt}
                </li>
              ))}
            </ul>
          </section>
        )}

        <div className="mb-8">
          <EvidenceList
            sources={sources}
            facts={evidenceFacts}
            interpretations={evidenceInterpretations}
            confidenceScore={article.confidence_score}
            historicalCount={historical.length}
            storyVersion={article.story_version}
            showConfidence={false}
          />
        </div>

        {/* ══════════════════════ TIER 4 — SEARCH & DISCOVERY ══════════════════════ */}

        {faqs.length > 0 && (
          <section className="mb-8">
            <Eyebrow icon={HelpCircle}>Frequently Asked Questions</Eyebrow>
            <div className="space-y-2">
              {faqs.map((f, i) => (
                <details key={i} className="group rounded-xl border border-surface-border/7 bg-text-primary/[0.02] px-4 py-3 open:bg-text-primary/[0.035]">
                  <summary className="cursor-pointer list-none text-[13px] font-semibold text-text-primary marker:content-none">
                    {f.question}
                  </summary>
                  <p className="mt-2 text-[12px] leading-6 text-text-secondary">{f.answer}</p>
                </details>
              ))}
            </div>
          </section>
        )}

        <section className="mb-8">
          <ExploreNext
            headline={article.headline}
            companiesAffected={companies}
            sectorsAffected={sectors}
            relatedCompanies={relatedCompanies}
            relatedThemes={relatedThemes}
            relatedArticles={relatedArticles}
            rippleEffect={rippleLinks}
            historicalCount={historical.length}
          />
        </section>

        {sources.length > 0 && (
          <div className="mb-8">
            <p className="mb-2.5 flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.18em] text-text-muted">
              <Database className="h-3 w-3 text-text-muted" /> Sources Used
            </p>
            <div className="flex flex-wrap gap-1.5">
              {sources.map((s, i) => (
                <span key={i} className="rounded-full border border-surface-border/10 bg-text-primary/[0.02] px-2.5 py-1 text-[11px] text-text-secondary">
                  {s}
                </span>
              ))}
            </div>
          </div>
        )}

        <p className="mb-8 text-[10px] leading-5 text-text-muted">
          Generated by MarketRipple&apos;s AI Intelligence Engine from real market data and events.
          Not investment advice — always do your own research before making investment decisions.
        </p>

      </div>
    </main>
  );
}
