import type { Metadata } from "next";
import { notFound } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft, ArrowRight, TrendingUp, TrendingDown, AlertTriangle, Building2, Clock,
  BookOpen, HelpCircle, Eye, ListChecks, Activity, Shield,
  Brain, Layers, MessageCircleQuestion, GitCommit, RadioTower,
  Sparkles, Target, Radio, ChevronRight, Compass, Database,
} from "lucide-react";
import { API_BASE_URL as API } from "@/lib/api";

// ── Article type metadata ────────────────────────────────────────────────────

const TYPE_META: Record<string, { label: string; color: string }> = {
  breaking_intelligence:  { label: "Breaking Intelligence",  color: "text-rose-400 border-rose-500/30 bg-rose-500/10" },
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
  question_intelligence:   { label: "Investor Q&A",           color: "text-pink-400 border-pink-500/30 bg-pink-500/10" },
  historical_intelligence: { label: "Historical Intelligence", color: "text-amber-400 border-amber-500/30 bg-amber-500/10" },
};
const DEFAULT_TYPE_META = { label: "Market Intelligence", color: "text-slate-400 border-white/20 bg-white/5" };

// ── Types ─────────────────────────────────────────────────────────────────────

interface CompanyAffected { name: string; symbol: string; impact: "positive" | "negative" | "neutral"; reason?: string; timeframe?: string; }
interface SectorAffected { name: string; impact?: "positive" | "negative" | "neutral"; magnitude?: "high" | "medium" | "low"; reason?: string; }
interface Opportunity { title: string; description: string; timeframe?: string; risk?: string; }
interface Risk { title: string; description: string; severity?: string; mitigation?: string; }
interface RippleLink { from_entity: string; to_entity: string; mechanism: string; timeframe?: string; }
interface HistoricalEvent { event?: string; date?: string; category?: string; outcome?: number | null; sentiment?: string; }
interface Faq { question: string; answer: string; }
interface RelatedCompany { symbol: string; name: string; link: string; }
interface RelatedTheme { theme: string; link: string; }
interface RelatedArticle { slug: string; headline: string; angle: string; angle_entity?: string | null; article_type: string; }
interface UpdateEntry {
  at: string; version: number; reason: string; summary: string;
  previous_takeaway?: string | null; new_takeaway?: string | null; confidence?: number;
}

interface InsightDetail {
  id: string; slug: string; article_type: string;
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
  update_history?: UpdateEntry[];
  parent_event_group_id?: string | null;
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

const IMPACT_STYLE: Record<string, string> = {
  positive: "border-emerald-500/25 bg-emerald-500/10 text-emerald-400",
  negative: "border-rose-500/25 bg-rose-500/10 text-rose-400",
  neutral:  "border-white/10 bg-white/5 text-slate-400",
};
const MAGNITUDE_BARS: Record<string, number> = { high: 4, medium: 2, low: 1 };
const HORIZON_LABEL: Record<string, string> = {
  immediate: "Today", short: "1 Week", weeks: "1 Week", medium: "1 Month", months: "1 Month", long: "Long Term",
};

// Event Evolution — derived from real timestamps, not a stored field:
// Active = touched in the last 24h, Monitoring = within 7 days, Resolved =
// older than that but still a live event type, Historical = evergreen/
// historical content by nature (never "resolves", it's timeless by design).
function deriveEventStatus(article: { article_type: string; is_evergreen?: boolean; last_updated?: string; published_at?: string }): { label: string; color: string; icon: typeof Activity } {
  if (article.is_evergreen || article.article_type === "historical_intelligence" || article.article_type === "educational_intelligence") {
    return { label: "Historical", color: "text-slate-400 border-white/15 bg-white/5", icon: BookOpen };
  }
  const anchor = article.last_updated || article.published_at;
  const hoursSince = anchor ? (Date.now() - new Date(anchor).getTime()) / 3_600_000 : Infinity;
  if (hoursSince <= 24) return { label: "Active", color: "text-emerald-400 border-emerald-500/30 bg-emerald-500/10", icon: RadioTower };
  if (hoursSince <= 24 * 7) return { label: "Monitoring", color: "text-amber-400 border-amber-500/30 bg-amber-500/10", icon: Activity };
  return { label: "Resolved", color: "text-sky-400 border-sky-500/30 bg-sky-500/10", icon: GitCommit };
}

// AI Investment Verdict — derived entirely from the article's own real,
// AI-generated company/sector impact calls. Never a fabricated buy/sell
// rating: no numeric "score" or "Strong Buy" exists in the data model, so
// none is invented here — the verdict is a real aggregate of real signals.
function deriveVerdict(companies: CompanyAffected[], sectors: SectorAffected[]) {
  const pool = [...companies, ...sectors].filter(x => x.impact);
  const counts = { positive: 0, negative: 0, neutral: 0 };
  pool.forEach(x => { counts[x.impact as keyof typeof counts]++; });
  const total = pool.length;
  let stance: "Bullish" | "Bearish" | "Neutral" | "Mixed" = "Neutral";
  if (total > 0) {
    if (counts.positive >= total * 0.55 && counts.positive > counts.negative) stance = "Bullish";
    else if (counts.negative >= total * 0.55 && counts.negative > counts.positive) stance = "Bearish";
    else if (counts.positive > 0 && counts.negative > 0) stance = "Mixed";
  }
  const focus = companies.find(c => c.impact === (stance === "Bearish" ? "negative" : "positive"))?.name
    ?? sectors.find(s => s.impact === (stance === "Bearish" ? "negative" : "positive"))?.name
    ?? null;
  const horizons = new Set<string>();
  companies.forEach(c => c.timeframe && horizons.add(HORIZON_LABEL[c.timeframe] ?? c.timeframe));
  return { stance, focus, horizons: [...horizons] };
}

const STANCE_STYLE: Record<string, { color: string; icon: typeof TrendingUp; bg: string }> = {
  Bullish: { color: "text-emerald-400", icon: TrendingUp, bg: "from-emerald-500/15 to-transparent border-emerald-500/25" },
  Bearish: { color: "text-rose-400", icon: TrendingDown, bg: "from-rose-500/15 to-transparent border-rose-500/25" },
  Mixed:   { color: "text-amber-400", icon: Activity, bg: "from-amber-500/15 to-transparent border-amber-500/25" },
  Neutral: { color: "text-slate-400", icon: Activity, bg: "from-white/10 to-transparent border-white/15" },
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

// ── Small presentational helpers ────────────────────────────────────────────

function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <div className={`rounded-2xl border border-white/[0.08] bg-white/[0.03] backdrop-blur-xl ${className}`}>{children}</div>;
}
function Eyebrow({ icon: Icon, children }: { icon: typeof Activity; children: React.ReactNode }) {
  return (
    <h2 className="mb-4 flex items-center gap-2 text-[12px] font-bold uppercase tracking-widest text-slate-500">
      <Icon className="h-3.5 w-3.5" /> {children}
    </h2>
  );
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
  const sectors = article.sectors_affected ?? [];
  const opportunities = article.opportunities ?? [];
  const winners = companies.filter(c => c.impact === "positive");
  const losers = companies.filter(c => c.impact === "negative");
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
  const campaignCompanies = relatedArticles.filter(r => r.angle === "per_company").length;
  const campaignSectors = relatedArticles.filter(r => r.angle === "sector_rollup").length;
  const campaignThemes = relatedArticles.filter(r => r.angle === "theme").length;
  const status = deriveEventStatus(article);
  const StatusIcon = status.icon;
  const verdict = deriveVerdict(companies, sectors);
  const VerdictIcon = STANCE_STYLE[verdict.stance].icon;

  // Real, historically-verified base rate — only shown when the article
  // actually cites measured outcomes, never estimated.
  const measuredOutcomes = historical.filter(h => h.outcome != null);
  const positiveOutcomeRate = measuredOutcomes.length
    ? Math.round((measuredOutcomes.filter(h => (h.outcome ?? 0) >= 0).length / measuredOutcomes.length) * 100)
    : null;

  // "Ask AI" — real follow-up questions built from this article's own
  // real companies, not invented topics.
  const askPrompts = [
    ...companies.slice(0, 2).map(c => `How will this affect ${c.name}?`),
    companies[0] ? `Should I buy ${companies[0].symbol}?` : null,
    "Explain this for beginners",
  ].filter(Boolean) as string[];

  return (
    <main className="min-h-screen bg-[#040711] text-white">
      {article.json_ld && (
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(article.json_ld) }}
        />
      )}

      <div className="mx-auto max-w-4xl px-4 py-10 sm:px-6">

        {/* Breadcrumb */}
        <nav className="mb-6 flex items-center gap-2 text-[11px] text-slate-600">
          <Link href="/" className="hover:text-slate-400 transition">MarketRipple</Link>
          <span>/</span>
          <Link href="/insights" className="hover:text-slate-400 transition">Insights</Link>
          <span>/</span>
          <span className="truncate text-slate-400">{article.headline}</span>
        </nav>

        {/* ══════════ 1. HERO ══════════ */}
        <div className="mb-8">
          <div className="flex flex-wrap items-center gap-2">
            <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider ${meta.color}`}>
              <BookOpen className="h-2.5 w-2.5" /> {meta.label}
            </span>
            <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider ${status.color}`}>
              <StatusIcon className="h-2.5 w-2.5" /> {status.label}
            </span>
            {article.angle_entity && article.angle !== "primary" && (
              <span className="inline-flex items-center rounded-full border border-white/10 bg-white/5 px-2.5 py-0.5 text-[10px] font-medium text-slate-400">
                Focused on {article.angle_entity}
              </span>
            )}
          </div>
          <h1 className="mt-3 text-[28px] font-black leading-tight text-white sm:text-[34px]">
            {article.headline}
          </h1>
          <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1.5">
            {article.published_at && (
              <span className="flex items-center gap-1 text-[11px] text-slate-500">
                <Clock className="h-3 w-3" /> Published {fmtRelative(article.published_at)}
              </span>
            )}
            {(article.update_count ?? 0) > 0 && (
              <span className="flex items-center gap-1 text-[11px] font-semibold text-sky-400">
                <Eye className="h-3 w-3" /> Updated {article.update_count}× · last {fmtRelative(article.last_updated)}
              </span>
            )}
            {article.parent_event_group_id && (
              <span className="flex items-center gap-1 text-[11px] text-violet-400">
                <Layers className="h-3 w-3" /> Part of a {relatedArticles.length + 1}-article campaign
              </span>
            )}
          </div>
        </div>

        {/* ══════════ 2. AI INVESTMENT VERDICT ══════════ */}
        <Card className={`mb-8 overflow-hidden bg-gradient-to-br p-6 sm:p-8 ${STANCE_STYLE[verdict.stance].bg}`}>
          <div className="flex flex-wrap items-start justify-between gap-6">
            <div>
              <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500">AI Investment Verdict</p>
              <div className="mt-2 flex items-center gap-2.5">
                <VerdictIcon className={`h-7 w-7 ${STANCE_STYLE[verdict.stance].color}`} />
                <span className={`text-[28px] font-black ${STANCE_STYLE[verdict.stance].color}`}>{verdict.stance}</span>
              </div>
              {verdict.focus && (
                <p className="mt-1 text-[13px] text-slate-400">
                  Current view: <span className="font-semibold text-slate-200">{verdict.stance} on {verdict.focus}</span>
                </p>
              )}
            </div>
            {article.confidence_score != null && (
              <div className="text-right">
                <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500">Confidence</p>
                <p className="text-[28px] font-black text-white">{Math.round(article.confidence_score * 100)}%</p>
              </div>
            )}
          </div>

          {verdict.horizons.length > 0 && (
            <div className="mt-5 flex flex-wrap gap-2">
              {verdict.horizons.map(h => (
                <span key={h} className="rounded-full border border-white/15 bg-white/5 px-3 py-1 text-[11px] font-semibold text-slate-300">{h}</span>
              ))}
            </div>
          )}

          {opportunities.length > 0 && (
            <div className="mt-5 border-t border-white/10 pt-5">
              <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-2">Action</p>
              <p className="text-[15px] font-bold text-white">{opportunities[0].title}</p>
              <p className="mt-1 text-[13px] leading-6 text-slate-400">{opportunities[0].description}</p>
            </div>
          )}

          {(companies.length > 0 || sectors.length > 0) && (
            <div className="mt-5 border-t border-white/10 pt-5">
              <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-2">Reasons</p>
              <ul className="space-y-1.5">
                {[...companies, ...sectors].filter(x => x.reason).slice(0, 3).map((x, i) => (
                  <li key={i} className="flex items-start gap-2 text-[13px] leading-5 text-slate-300">
                    <ChevronRight className="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-600" /> {x.reason}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </Card>

        {/* ══════════ 3. TL;DR ══════════ */}
        {article.key_takeaway && (
          <div className="mb-8 rounded-2xl border border-violet-500/20 bg-violet-500/[0.06] p-5">
            <p className="text-[10px] font-bold uppercase tracking-widest text-violet-400 mb-1.5">TL;DR — 30 Seconds</p>
            <p className="text-[15px] font-semibold leading-snug text-white">{article.key_takeaway}</p>
          </div>
        )}

        {/* Why it matters / What happened (prose) */}
        {article.why_it_matters && (
          <section className="mb-8">
            <Eyebrow icon={Sparkles}>Why It Matters</Eyebrow>
            <p className="whitespace-pre-line text-[14px] leading-7 text-slate-300">{article.why_it_matters}</p>
          </section>
        )}
        {article.what_happened && (
          <section className="mb-8">
            <Eyebrow icon={Activity}>What Happened</Eyebrow>
            <p className="whitespace-pre-line text-[14px] leading-7 text-slate-300">{article.what_happened}</p>
          </section>
        )}

        {/* ══════════ 4. WHY THIS MATTERS TO EACH SECTOR ══════════ */}
        {sectors.length > 0 && (
          <section className="mb-8">
            <Eyebrow icon={Layers}>Sector Impact</Eyebrow>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              {sectors.map((s, i) => (
                <Card key={i} className="p-4">
                  <div className="flex items-center justify-between">
                    <span className="text-[13px] font-bold text-white">{s.name}</span>
                    <span className={`rounded-full border px-2 py-0.5 text-[9px] font-bold uppercase ${IMPACT_STYLE[s.impact ?? "neutral"]}`}>{s.impact ?? "neutral"}</span>
                  </div>
                  {s.magnitude && (
                    <div className="mt-2 flex items-center gap-1">
                      {[1, 2, 3, 4].map(n => (
                        <span key={n} className={`h-1.5 w-5 rounded-full ${n <= MAGNITUDE_BARS[s.magnitude!] ? (s.impact === "negative" ? "bg-rose-400" : "bg-emerald-400") : "bg-white/10"}`} />
                      ))}
                      <span className="ml-1.5 text-[10px] uppercase tracking-wide text-slate-600">{s.magnitude} magnitude</span>
                    </div>
                  )}
                  {s.reason && <p className="mt-2 text-[12px] leading-5 text-slate-400">{s.reason}</p>}
                </Card>
              ))}
            </div>
          </section>
        )}

        {/* ══════════ 5. RIPPLE EFFECT CHAIN ══════════ */}
        {rippleLinks.length > 0 && (
          <section className="mb-8">
            <Eyebrow icon={Compass}>Ripple Effect</Eyebrow>
            <Card className="p-5">
              <div className="space-y-4">
                {rippleLinks.map((r, i) => (
                  <div key={i} className="flex items-start gap-3">
                    <div className="flex flex-col items-center pt-1">
                      <span className="h-2.5 w-2.5 rounded-full bg-violet-400" />
                      {i < rippleLinks.length - 1 && <span className="mt-1 h-8 w-px bg-white/10" />}
                    </div>
                    <div className="flex-1">
                      <div className="flex flex-wrap items-center gap-1.5 text-[13px] font-bold text-white">
                        {r.from_entity} <ArrowRight className="h-3.5 w-3.5 text-violet-400" /> {r.to_entity}
                      </div>
                      <p className="mt-1 text-[12px] leading-5 text-slate-400">{r.mechanism}</p>
                      {r.timeframe && <span className="mt-1 inline-block text-[10px] uppercase tracking-wide text-slate-600">{r.timeframe}-term</span>}
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          </section>
        )}

        {/* ══════════ 6. COMPANY IMPACT TABLE ══════════ */}
        {companies.length > 0 && (
          <section className="mb-8">
            <Eyebrow icon={Building2}>Company Impact</Eyebrow>
            <Card className="overflow-hidden">
              <div className="grid grid-cols-[1fr_auto_auto] items-center gap-2 border-b border-white/[0.06] bg-white/[0.02] px-4 py-2.5 text-[9px] font-bold uppercase tracking-widest text-slate-600">
                <span>Company</span><span>Impact</span><span className="text-right">Horizon</span>
              </div>
              {companies.map((c, i) => (
                <div key={i} className={`grid grid-cols-[1fr_auto_auto] items-center gap-2 px-4 py-3 ${i < companies.length - 1 ? "border-b border-white/[0.04]" : ""}`}>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <Link href={`/companies/${c.symbol}`} className="text-[13px] font-bold text-sky-300 hover:text-sky-200 transition">{c.symbol}</Link>
                      <span className="truncate text-[11px] text-slate-500">{c.name}</span>
                    </div>
                    {c.reason && <p className="mt-0.5 line-clamp-1 text-[11px] text-slate-500">{c.reason}</p>}
                  </div>
                  <span className={`shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-bold capitalize ${IMPACT_STYLE[c.impact] ?? IMPACT_STYLE.neutral}`}>{c.impact}</span>
                  <span className="shrink-0 text-right text-[11px] text-slate-500">{c.timeframe ? (HORIZON_LABEL[c.timeframe] ?? c.timeframe) : "—"}</span>
                </div>
              ))}
            </Card>
          </section>
        )}

        {/* ══════════ 7. WINNERS & LOSERS ══════════ */}
        {(winners.length > 0 || losers.length > 0) && (
          <section className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-2">
            {winners.length > 0 && (
              <Card className="p-5">
                <h3 className="mb-3 flex items-center gap-1.5 text-[12px] font-bold uppercase tracking-widest text-emerald-400">
                  <TrendingUp className="h-3.5 w-3.5" /> Likely Winners
                </h3>
                <div className="flex flex-wrap gap-2">
                  {winners.map((c, i) => (
                    <Link key={i} href={`/companies/${c.symbol}`} className="rounded-full border border-emerald-500/25 bg-emerald-500/10 px-3 py-1.5 text-[12px] font-semibold text-emerald-300 hover:text-emerald-200 transition">
                      {c.name}
                    </Link>
                  ))}
                </div>
              </Card>
            )}
            {losers.length > 0 && (
              <Card className="p-5">
                <h3 className="mb-3 flex items-center gap-1.5 text-[12px] font-bold uppercase tracking-widest text-rose-400">
                  <TrendingDown className="h-3.5 w-3.5" /> Likely Losers
                </h3>
                <div className="flex flex-wrap gap-2">
                  {losers.map((c, i) => (
                    <Link key={i} href={`/companies/${c.symbol}`} className="rounded-full border border-rose-500/25 bg-rose-500/10 px-3 py-1.5 text-[12px] font-semibold text-rose-300 hover:text-rose-200 transition">
                      {c.name}
                    </Link>
                  ))}
                </div>
              </Card>
            )}
          </section>
        )}

        {/* ══════════ 8. INVESTMENT OPPORTUNITIES ══════════ */}
        {opportunities.length > 0 && (
          <section className="mb-8">
            <Eyebrow icon={Target}>Investment Opportunities</Eyebrow>
            <div className="space-y-3">
              {opportunities.map((o, i) => (
                <Card key={i} className="p-4">
                  <div className="flex items-start justify-between gap-3">
                    <h3 className="text-[13px] font-bold text-white">{o.title}</h3>
                    <div className="flex shrink-0 gap-1.5">
                      {o.timeframe && <span className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[9px] uppercase text-slate-500">{o.timeframe}</span>}
                      {o.risk && <span className="rounded-full border border-amber-500/20 bg-amber-500/10 px-2 py-0.5 text-[9px] uppercase text-amber-400">{o.risk} risk</span>}
                    </div>
                  </div>
                  <p className="mt-1.5 text-[12px] leading-5 text-slate-400">{o.description}</p>
                </Card>
              ))}
            </div>
          </section>
        )}

        {/* Risks */}
        {risks.length > 0 && (
          <section className="mb-8">
            <Eyebrow icon={AlertTriangle}>Risks</Eyebrow>
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

        {/* ══════════ 9. HISTORICAL INTELLIGENCE ══════════ */}
        {historical.length > 0 && (
          <section className="mb-8">
            <Eyebrow icon={Database}>Historical Intelligence</Eyebrow>
            <Card className="p-5">
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
              {positiveOutcomeRate != null && (
                <div className="mt-4 flex items-center gap-3 rounded-xl border border-white/[0.06] bg-white/[0.02] p-3.5">
                  <span className="text-[22px] font-black text-emerald-400">{positiveOutcomeRate}%</span>
                  <span className="text-[12px] leading-5 text-slate-400">
                    of {measuredOutcomes.length} similar historical events saw a positive outcome
                  </span>
                </div>
              )}
            </Card>
          </section>
        )}

        {/* ══════════ 10. INTELLIGENCE TIMELINE ══════════ */}
        {updateHistory.length > 0 && (
          <section className="mb-8">
            <Eyebrow icon={Activity}>Intelligence Timeline</Eyebrow>
            <div className="space-y-0">
              <div className="relative pl-6 pb-5">
                <span className="absolute left-0 top-1 h-3 w-3 rounded-full bg-sky-500" />
                <span className="absolute left-[5px] top-4 bottom-0 w-px bg-white/10" />
                <p className="text-[10px] font-bold uppercase tracking-wider text-sky-400">
                  {fmtDate(article.created_at || article.published_at)}
                </p>
                <p className="text-[13px] font-semibold text-white">Article Published</p>
                {article.key_takeaway && <p className="mt-0.5 text-[12px] text-slate-500 line-clamp-2">{article.key_takeaway}</p>}
              </div>
              {updateHistory.map((u, i) => {
                const prevConf = i === 0 ? article.confidence_score : updateHistory[i - 1].confidence;
                return (
                  <div key={i} className="relative pl-6 pb-5">
                    <span className="absolute left-0 top-1 h-3 w-3 rounded-full bg-emerald-500" />
                    {i < updateHistory.length - 1 && <span className="absolute left-[5px] top-4 bottom-0 w-px bg-white/10" />}
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="text-[10px] font-bold uppercase tracking-wider text-emerald-400">{fmtDate(u.at)} · v{u.version}</p>
                      {u.confidence != null && prevConf != null && u.confidence !== prevConf && (
                        <span className="text-[10px] font-bold text-slate-400">
                          Confidence {Math.round(prevConf * 100)}%→{Math.round(u.confidence * 100)}%
                        </span>
                      )}
                    </div>
                    <p className="text-[13px] font-semibold text-white">{u.reason}</p>
                    {u.new_takeaway && u.new_takeaway !== u.previous_takeaway && (
                      <p className="mt-0.5 text-[12px] text-slate-500 line-clamp-2">{u.new_takeaway}</p>
                    )}
                  </div>
                );
              })}
            </div>
          </section>
        )}

        {/* ══════════ 11. AI OPINION EVOLUTION ══════════ */}
        {updateHistory.length > 0 && (
          <section className="mb-8">
            <Eyebrow icon={Brain}>AI Opinion Evolution</Eyebrow>
            <Card className="p-5">
              <div className="space-y-3">
                <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3.5">
                  <p className="text-[9px] font-bold uppercase tracking-wider text-slate-600">Original — {fmtDate(article.created_at || article.published_at)}</p>
                  <p className="mt-1.5 text-[12px] leading-5 text-slate-400">{updateHistory[0].previous_takeaway ?? article.key_takeaway}</p>
                </div>
                {updateHistory.map((u, i) => (
                  <div key={i} className={`ml-4 rounded-xl border p-3.5 ${i === updateHistory.length - 1 ? "border-emerald-500/15 bg-emerald-500/[0.04]" : "border-white/[0.06] bg-white/[0.02]"}`}>
                    <p className={`text-[9px] font-bold uppercase tracking-wider ${i === updateHistory.length - 1 ? "text-emerald-500" : "text-slate-600"}`}>
                      {i === updateHistory.length - 1 ? "Current" : `v${u.version}`} — {fmtDate(u.at)}
                    </p>
                    <p className={`mt-1.5 text-[12px] leading-5 ${i === updateHistory.length - 1 ? "text-slate-300" : "text-slate-400"}`}>
                      {u.new_takeaway ?? u.summary}
                    </p>
                  </div>
                ))}
              </div>
            </Card>
          </section>
        )}

        {/* ══════════ 12. LIVE ARTICLE BADGE ══════════ */}
        {status.label === "Active" || status.label === "Monitoring" ? (
          <Card className="mb-8 flex flex-wrap items-center justify-between gap-4 border-sky-500/20 bg-sky-500/[0.04] p-5">
            <div className="flex items-center gap-3">
              <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-sky-500/15">
                <Radio className="h-4 w-4 animate-pulse text-sky-400" />
              </span>
              <div>
                <p className="text-[12px] font-bold uppercase tracking-widest text-sky-400">Live Article — Auto-Updating</p>
                <p className="text-[11px] text-slate-500">Last update {fmtRelative(article.last_updated || article.published_at)}</p>
              </div>
            </div>
            <div className="flex gap-5 text-right">
              <div>
                <p className="text-[18px] font-black text-white">{article.update_count ?? 0}</p>
                <p className="text-[9px] uppercase tracking-wide text-slate-600">Updates</p>
              </div>
              {watch.length > 0 && (
                <div>
                  <p className="text-[18px] font-black text-white">{watch.length}</p>
                  <p className="text-[9px] uppercase tracking-wide text-slate-600">Signals Tracked</p>
                </div>
              )}
            </div>
          </Card>
        ) : null}

        {/* What to watch next */}
        {watch.length > 0 && (
          <section className="mb-8">
            <Eyebrow icon={ListChecks}>What to Watch Next</Eyebrow>
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
          <section className="mb-8">
            <Eyebrow icon={HelpCircle}>Frequently Asked Questions</Eyebrow>
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

        {/* People Also Asked */}
        {questionSiblings.length > 0 && (
          <section className="mb-8">
            <Eyebrow icon={MessageCircleQuestion}>People Also Asked</Eyebrow>
            <div className="space-y-2">
              {questionSiblings.map((r, i) => (
                <Link key={i} href={`/insights/${r.slug}`}
                  className="flex items-center justify-between rounded-xl border border-pink-500/15 bg-pink-500/[0.03] px-4 py-3 hover:border-pink-500/30 transition">
                  <p className="text-[13px] font-medium text-slate-200">{r.headline}</p>
                  <ArrowLeft className="h-3.5 w-3.5 shrink-0 rotate-180 text-pink-400" />
                </Link>
              ))}
            </div>
          </section>
        )}

        {/* ══════════ ASK AI ABOUT THIS EVENT ══════════ */}
        {askPrompts.length > 0 && (
          <section className="mb-8">
            <Eyebrow icon={Sparkles}>Ask AI About This Event</Eyebrow>
            <div className="flex flex-wrap gap-2">
              {askPrompts.map((q, i) => (
                <Link key={i} href={`/ai-search?q=${encodeURIComponent(q)}`}
                  className="rounded-full border border-violet-500/25 bg-violet-500/[0.06] px-4 py-2 text-[12px] font-semibold text-violet-300 hover:bg-violet-500/15 hover:text-violet-200 transition">
                  {q}
                </Link>
              ))}
            </div>
          </section>
        )}

        {/* ══════════ 13. RELATED CAMPAIGN ══════════ */}
        {relatedArticles.length > 0 && (
          <section className="mb-8">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="flex items-center gap-2 text-[12px] font-bold uppercase tracking-widest text-slate-500">
                <Layers className="h-3.5 w-3.5 text-violet-400" /> Related Campaign
              </h2>
              <span className="text-[10px] text-slate-600">{relatedArticles.length + 1} articles</span>
            </div>
            <div className="mb-3 flex flex-wrap gap-1.5 text-[10px] text-slate-500">
              {campaignCompanies > 0 && <span className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5">{campaignCompanies} {campaignCompanies === 1 ? "company" : "companies"}</span>}
              {campaignSectors > 0 && <span className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5">{campaignSectors} sector</span>}
              {campaignThemes > 0 && <span className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5">{campaignThemes} theme</span>}
              {questionSiblings.length > 0 && <span className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5">{questionSiblings.length} Q&amp;A</span>}
            </div>
            <div className="space-y-2">
              {relatedArticles.map((r, i) => (
                <Link key={i} href={`/insights/${r.slug}`}
                  className="flex items-center justify-between rounded-xl border border-white/[0.07] bg-white/[0.03] px-4 py-3 hover:border-white/20 transition">
                  <div>
                    <span className="text-[10px] uppercase tracking-wider text-slate-600">
                      {r.angle === "per_company" ? r.angle_entity
                        : r.angle === "sector_rollup" ? `${r.angle_entity} Sector`
                        : r.angle === "theme" ? `${r.angle_entity} Theme`
                        : r.angle === "question" ? "Q&A"
                        : (TYPE_META[r.article_type] ?? DEFAULT_TYPE_META).label}
                    </span>
                    <p className="text-[12px] font-medium text-slate-300">{r.headline}</p>
                  </div>
                </Link>
              ))}
            </div>
          </section>
        )}

        {/* Related companies/themes */}
        {(relatedCompanies.length > 0 || relatedThemes.length > 0) && (
          <section className="mb-8">
            <Eyebrow icon={Building2}>Related Companies &amp; Themes</Eyebrow>
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

        {/* ══════════ EVIDENCE PANEL (collapsible) ══════════ */}
        <details className="group mb-8 rounded-2xl border border-white/[0.06] bg-white/[0.02] p-5 open:bg-white/[0.03]">
          <summary className="flex cursor-pointer list-none items-center justify-between marker:content-none">
            <span className="flex items-center gap-2 text-[12px] font-bold uppercase tracking-widest text-slate-500">
              <Shield className="h-3.5 w-3.5" /> Evidence Panel
            </span>
            <ChevronRight className="h-4 w-4 text-slate-600 transition group-open:rotate-90" />
          </summary>
          <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
            <div>
              <p className="text-[9px] font-bold uppercase tracking-wider text-slate-600">AI Confidence</p>
              <p className="mt-1 text-[16px] font-bold text-white">{article.confidence_score != null ? `${Math.round(article.confidence_score * 100)}%` : "—"}</p>
            </div>
            <div>
              <p className="text-[9px] font-bold uppercase tracking-wider text-slate-600">Sources</p>
              <p className="mt-1 text-[16px] font-bold text-white">{sources.length || "—"}</p>
            </div>
            <div>
              <p className="text-[9px] font-bold uppercase tracking-wider text-slate-600">Historical Data</p>
              <p className="mt-1 text-[16px] font-bold text-white">{historical.length} events</p>
            </div>
            <div>
              <p className="text-[9px] font-bold uppercase tracking-wider text-slate-600">Story Version</p>
              <p className="mt-1 text-[16px] font-bold text-white">v{article.story_version ?? 1}</p>
            </div>
          </div>
          {sources.length > 0 && (
            <p className="mt-4 text-[11px] text-slate-600">
              <span className="font-semibold text-slate-500">Sources: </span>{sources.join(", ")}
            </p>
          )}
        </details>

        <p className="mb-8 text-[10px] leading-5 text-slate-700">
          Generated by MarketRipple&apos;s AI Intelligence Engine from real market data and events.
          Not investment advice — always do your own research before making investment decisions.
        </p>

        {/* ══════════ FOOTER CTA ══════════ */}
        <div className="flex flex-col gap-3 rounded-2xl border border-white/[0.07] bg-white/[0.03] p-5 sm:flex-row sm:items-center sm:justify-between">
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
