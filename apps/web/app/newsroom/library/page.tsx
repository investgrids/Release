import type { Metadata } from "next";
import Link from "next/link";
import {
  Search, Clock, ChevronLeft, ChevronRight, Flame, Sparkles, Eye,
  FileText, CalendarDays, TrendingUp, Building2, Radio as RadioIcon,
  Tag, type LucideIcon,
} from "lucide-react";
import { API_BASE_URL as API } from "@/lib/api";
import { cleanText, isRealSymbol } from "@/lib/text";
import { HeroImage } from "@/components/HeroImage";
import { BookmarkButton } from "@/components/BookmarkButton";
import { MEASUREMENT_LABEL } from "@/lib/measurementSemantics";

export const metadata: Metadata = {
  title: "AI Intelligence Library",
  description: "The complete, searchable archive of every AI-generated market intelligence article — no raw feeds, no external content, just MarketRipple's own analysis.",
  alternates: { canonical: "/newsroom/library" },
};

// ── Types ─────────────────────────────────────────────────────────────────

interface InsightCard {
  slug: string;
  article_type: string;
  headline: string;
  key_takeaway?: string;
  executive_summary?: string;
  confidence_score?: number;
  read_time_minutes?: number;
  views?: number;
  published_at?: string;
  companies_affected: { name: string; symbol: string; impact: string }[];
  sectors_affected: { name: string }[];
  hero_image_url?: string | null;
}

interface LibraryStats {
  total_articles?: number;
  today_articles?: number;
  this_week_articles?: number;
  companies_covered?: number;
  events_covered?: number;
  themes_covered?: number;
  avg_confidence?: number | null;
  last_updated?: string | null;
}

const TYPE_LABEL: Record<string, string> = {
  breaking_intelligence: "Breaking",
  morning_intelligence:  "Morning Brief",
  market_wrap:           "Market Wrap",
  company_intelligence:  "Company",
  sector_intelligence:   "Sector",
  theme_intelligence:    "Theme",
  policy_intelligence:   "Policy",
  ripple_intelligence:   "Ripple",
  opportunity_intelligence: "Opportunity",
  question_intelligence: "Q&A",
  historical_intelligence: "Historical",
  educational_intelligence: "Explainer",
};

const CATEGORIES = [
  { id: "",             label: "All" },
  { id: "market",        label: "Market" },
  { id: "companies",     label: "Companies" },
  { id: "events",        label: "Events" },
  { id: "themes",        label: "Themes" },
  { id: "opportunities", label: "Opportunities" },
] as const;

const SORTS = [
  { id: "newest",     label: "Newest" },
  { id: "views",      label: "Most Viewed" },
  { id: "confidence", label: "Highest Confidence" },
] as const;

const SECTIONS = [
  { title: "Market Intelligence",      category: "market",        href: "/newsroom/daily-brief" },
  { title: "Company Intelligence",     category: "companies",     href: "/newsroom/companies" },
  { title: "Event Intelligence",       category: "events",        href: "/newsroom/events" },
  { title: "Theme Intelligence",       category: "themes",        href: "/newsroom/themes" },
  { title: "Opportunity Intelligence", category: "opportunities", href: "/opportunity-radar" },
] as const;

const PAGE_SIZE = 20;

// ── Fetching ──────────────────────────────────────────────────────────────

async function fetchJSON<T>(path: string, fallback: T): Promise<T> {
  try {
    const res = await fetch(`${API}${path}`, { next: { revalidate: 120 } });
    if (!res.ok) return fallback;
    return res.json();
  } catch {
    return fallback;
  }
}

function fmtRelative(iso?: string): string {
  if (!iso) return "";
  const mins = Math.floor((Date.now() - new Date(iso).getTime()) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  if (mins < 1440) return `${Math.floor(mins / 60)}h ago`;
  return `${Math.floor(mins / 1440)}d ago`;
}

// ── Page ──────────────────────────────────────────────────────────────────

export default async function LibraryPage(
  { searchParams }: { searchParams: Promise<{ page?: string; category?: string; sort?: string }> }
) {
  const { page: pageParam, category = "", sort = "newest" } = await searchParams;
  const page = Math.max(1, parseInt(pageParam ?? "1", 10) || 1);
  const offset = (page - 1) * PAGE_SIZE;
  const catQS = category ? `&category=${category}` : "";
  const isFiltered = !!category || sort !== "newest" || page > 1;

  const [stats, list, trending, ...sectionLists] = await Promise.all([
    fetchJSON<LibraryStats>("/api/insights/stats", {}),
    fetchJSON<{ items: InsightCard[]; total: number }>(
      `/api/insights/?limit=${PAGE_SIZE}&offset=${offset}&sort_by=${sort}${catQS}`, { items: [], total: 0 }
    ),
    // Trending Today: real view-based ranking among TODAY's articles only
    // (a dedicated endpoint — sort_by=views on the generic list ranks
    // across all time and was surfacing weeks-old articles here).
    fetchJSON<{ items: InsightCard[] }>(`/api/insights/trending?limit=4`, { items: [] }),
    ...SECTIONS.map(s => fetchJSON<{ items: InsightCard[] }>(`/api/insights/?category=${s.category}&limit=4`, { items: [] })),
  ]);

  const totalPages = Math.max(1, Math.ceil(list.total / PAGE_SIZE));
  const featured = !isFiltered ? list.items[0] : null;
  const gridItems = featured ? list.items.slice(1) : list.items;

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6">

      {/* ══════════ Header ══════════ */}
      <div className="mb-6">
        <h1 className="text-[30px] font-black leading-tight text-text-primary md:text-[36px]">
          AI Intelligence Library
        </h1>
        <p className="mt-2 max-w-2xl text-[14px] leading-6 text-text-secondary">
          Discover AI-generated market intelligence, investment research and daily analysis —
          every article written by MarketRipple&apos;s AI Publishing Engine from real market data.
        </p>
        <form action="/search" method="get" className="mt-5 max-w-xl">
          <div className="flex items-center gap-3 rounded-2xl border border-surface-border/10 bg-text-primary/[0.04] px-4 py-3 focus-within:border-violet-500/40">
            <Search className="h-4.5 w-4.5 shrink-0 text-text-muted" />
            <input
              type="text"
              name="q"
              placeholder="Search articles, companies, events, themes…"
              className="flex-1 bg-transparent text-[14px] text-text-primary outline-none placeholder:text-text-muted"
            />
          </div>
        </form>
      </div>

      {/* ══════════ Stats ══════════ */}
      <div className="mb-8 grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-8">
        <StatTile icon={FileText}     label="Total AI Articles"  value={stats.total_articles}   sub="Across all categories" />
        <StatTile icon={CalendarDays} label="Today's Articles"   value={stats.today_articles}   sub="Published today" />
        <StatTile icon={TrendingUp}   label="This Week"          value={stats.this_week_articles} sub="Last 7 days" />
        <StatTile icon={Building2}    label="Companies Covered"  value={stats.companies_covered} sub="Active companies" />
        <StatTile icon={RadioIcon}    label="Events Covered"     value={stats.events_covered}    sub="Key events tracked" />
        <StatTile icon={Tag}          label="Themes Covered"     value={stats.themes_covered}    sub="Investment themes" />
        {/* Avg AI Confidence removed per CD3-C: avg_confidence is a plain SQL
            avg() across confidence_score, whose per-article inputs are 4
            genuinely incompatible producers (LLM self-report, 0.0 DB
            default, 0.7 soft-fill, 0.7 hard publish-gate floor) -- a
            DERIVED_TRANSFORM average of incompatible inputs authorizes
            nothing, same rule that removed IntelligenceGraph's average-
            edge-confidence stat. */}
        <StatTile icon={Clock}        label="Last Updated"       value={stats.last_updated ? fmtRelative(stats.last_updated) : undefined} sub="Real-time updates" />
      </div>

      {/* ══════════ Filters (sticky) ══════════ */}
      <div className="sticky top-0 z-20 -mx-4 mb-8 border-y border-surface-border/7 bg-surface-card/95 px-4 py-3 backdrop-blur sm:-mx-6 sm:px-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap gap-2">
            {CATEGORIES.map((c) => (
              <Link
                key={c.id}
                href={c.id ? `/newsroom/library?category=${c.id}` : "/newsroom/library"}
                className={`rounded-full border px-3.5 py-1.5 text-[12px] font-semibold transition ${
                  category === c.id
                    ? "border-violet-500/40 bg-violet-500/15 text-violet-600 dark:text-violet-300"
                    : "border-surface-border/10 bg-text-primary/[0.03] text-text-secondary hover:text-text-primary"
                }`}
              >
                {c.label}
              </Link>
            ))}
          </div>
          <div className="flex gap-2">
            {SORTS.map((s) => (
              <Link
                key={s.id}
                href={`/newsroom/library?sort=${s.id}${category ? `&category=${category}` : ""}`}
                className={`rounded-full border px-3 py-1.5 text-[11px] font-medium transition ${
                  sort === s.id
                    ? "border-surface-border/20 bg-text-primary/10 text-text-primary"
                    : "border-surface-border/10 bg-text-primary/[0.02] text-text-muted hover:text-text-secondary"
                }`}
              >
                {s.label}
              </Link>
            ))}
          </div>
        </div>
      </div>

      {list.items.length === 0 ? (
        <p className="rounded-xl border border-surface-border/7 bg-text-primary/[0.03] p-10 text-center text-[13px] text-text-muted">
          No AI Intelligence Available — check back soon.
        </p>
      ) : (
        <>
          {/* ══════════ Featured Intelligence ══════════ */}
          {featured && (
            <section className="mb-10">
              <p className="mb-3 flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-[0.16em] text-amber-400">
                <Sparkles className="h-3.5 w-3.5" /> Featured Intelligence
              </p>
              <Link
                href={`/newsroom/article/${featured.slug}`}
                className="group grid grid-cols-1 overflow-hidden rounded-2xl border border-surface-border/8 bg-text-primary/[0.02] transition hover:border-surface-border/20 md:grid-cols-2"
              >
                <HeroImage
                  heroImageUrl={featured.hero_image_url}
                  headline={featured.headline}
                  articleType={featured.article_type}
                  sectors={(featured.sectors_affected ?? []).map(s => s.name)}
                  className="h-56 md:h-full"
                />
                <div className="flex flex-col justify-center p-6 md:p-8">
                  <span className="w-fit rounded-full border border-surface-border/10 bg-text-primary/5 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider text-text-secondary">
                    {TYPE_LABEL[featured.article_type] ?? "Intelligence"}
                  </span>
                  <h2 className="mt-3 text-[22px] font-black leading-tight text-text-primary group-hover:text-sky-700 dark:text-sky-200 transition md:text-[26px]">
                    {cleanText(featured.headline)}
                  </h2>
                  {(featured.key_takeaway || featured.executive_summary) && (
                    <p className="mt-2 line-clamp-3 text-[13.5px] leading-6 text-text-secondary">
                      {cleanText(featured.key_takeaway ?? featured.executive_summary ?? "")}
                    </p>
                  )}
                  {featured.companies_affected?.some(c => isRealSymbol(c.symbol)) && (
                    <div className="mt-4 flex flex-wrap gap-1.5">
                      {featured.companies_affected.filter(c => isRealSymbol(c.symbol)).slice(0, 4).map((c, i) => (
                        <span key={i} className="rounded-full border border-surface-border/10 bg-text-primary/5 px-2 py-0.5 text-[10px] text-text-secondary">{c.symbol}</span>
                      ))}
                    </div>
                  )}
                  <div className="mt-5 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-text-muted">
                    {featured.confidence_score != null && (
                      <span
                        className="font-semibold text-sky-400"
                        title="The model's own self-reported certainty at generation time -- not a verified or computed score"
                      >
                        {MEASUREMENT_LABEL.self_reported_certainty}: {Math.round(featured.confidence_score * 100)}%
                      </span>
                    )}
                    {featured.read_time_minutes && <span>{featured.read_time_minutes} min read</span>}
                    {featured.published_at && <span>{fmtRelative(featured.published_at)}</span>}
                  </div>
                  <span className="mt-5 inline-flex w-fit items-center gap-1.5 rounded-full bg-accent-violet px-4 py-2 text-[12px] font-bold text-white transition group-hover:opacity-90">
                    Read Article <ChevronRight className="h-3.5 w-3.5" />
                  </span>
                </div>
              </Link>
            </section>
          )}

          {/* ══════════ Trending Today ══════════ */}
          {trending.items.some(a => (a.views ?? 0) > 0) && (
            <section className="mb-10">
              <p className="mb-3 flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-[0.16em] text-rose-400">
                <Flame className="h-3.5 w-3.5" /> Trending Today
              </p>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {trending.items.filter(a => (a.views ?? 0) > 0).map((a) => <GridCard key={a.slug} a={a} />)}
              </div>
            </section>
          )}

          {/* ══════════ Latest Intelligence (filtered/paginated grid) ══════════ */}
          <section className="mb-10">
            <p className="mb-3 text-[11px] font-bold uppercase tracking-[0.16em] text-text-muted">
              {category ? CATEGORIES.find(c => c.id === category)?.label : "Latest Intelligence"}
            </p>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {gridItems.map((a) => <GridCard key={a.slug} a={a} large />)}
            </div>
          </section>

          {/* ══════════ Pagination ══════════ */}
          {totalPages > 1 && (
            <div className="mb-12 flex items-center justify-between">
              <PageLink page={page - 1} disabled={page <= 1} category={category} sort={sort}>
                <ChevronLeft className="h-3.5 w-3.5" /> Previous
              </PageLink>
              <div className="flex items-center gap-1.5">
                {paginationRange(page, totalPages).map((p, i) =>
                  p === "…" ? (
                    <span key={`e${i}`} className="px-1.5 text-[12px] text-text-muted">…</span>
                  ) : (
                    <Link
                      key={p}
                      href={`/newsroom/library?page=${p}${category ? `&category=${category}` : ""}${sort !== "newest" ? `&sort=${sort}` : ""}`}
                      className={`flex h-8 w-8 items-center justify-center rounded-full text-[12px] font-semibold transition ${
                        p === page ? "bg-violet-500 text-text-primary" : "text-text-secondary hover:bg-text-primary/5 hover:text-text-primary"
                      }`}
                    >
                      {p}
                    </Link>
                  )
                )}
              </div>
              <PageLink page={page + 1} disabled={page >= totalPages} category={category} sort={sort}>
                Next <ChevronRight className="h-3.5 w-3.5" />
              </PageLink>
            </div>
          )}

          {/* ══════════ Dedicated category sections (only on the unfiltered default view) ══════════ */}
          {!isFiltered && sectionLists.map((sl, i) => {
            const s = SECTIONS[i];
            if (sl.items.length === 0) return null;
            return (
              <section key={s.category} className="mb-10">
                <div className="mb-3 flex items-center justify-between">
                  <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-text-muted">{s.title}</p>
                  <Link href={`/newsroom/library?category=${s.category}`} className="flex items-center gap-0.5 text-[11.5px] font-medium text-text-muted hover:text-text-primary">
                    View all <ChevronRight className="h-3 w-3" />
                  </Link>
                </div>
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
                  {sl.items.map((a) => <GridCard key={a.slug} a={a} />)}
                </div>
              </section>
            );
          })}
        </>
      )}
    </div>
  );
}

// ── Building blocks ──────────────────────────────────────────────────────────

function paginationRange(page: number, total: number): (number | "…")[] {
  const out: (number | "…")[] = [];
  const add = (n: number | "…") => out.push(n);
  add(1);
  if (page > 3) add("…");
  for (let p = Math.max(2, page - 1); p <= Math.min(total - 1, page + 1); p++) add(p);
  if (page < total - 2) add("…");
  if (total > 1) add(total);
  return out;
}

function PageLink({ page, disabled, category, sort, children }: { page: number; disabled: boolean; category: string; sort: string; children: React.ReactNode }) {
  return (
    <Link
      href={`/newsroom/library?page=${page}${category ? `&category=${category}` : ""}${sort !== "newest" ? `&sort=${sort}` : ""}`}
      aria-disabled={disabled}
      className={`flex items-center gap-1 rounded-full border px-4 py-2 text-[12px] font-medium transition ${
        disabled ? "pointer-events-none border-surface-border/5 text-text-muted" : "border-surface-border/10 bg-text-primary/5 text-text-secondary hover:text-text-primary"
      }`}
    >
      {children}
    </Link>
  );
}

function StatTile({ icon: Icon, label, value, sub }: { icon: LucideIcon; label: string; value?: number | string; sub?: string }) {
  return (
    <div className="flex h-full flex-col rounded-xl border border-surface-border/7 bg-text-primary/[0.02] p-3.5">
      {/* Fixed-height label row — some labels wrap to 2 lines ("Total AI
          Articles") and some fit on 1 ("This Week"), which otherwise pushes
          the value below to a different Y per tile and breaks the row's
          alignment. */}
      <div className="flex min-h-[28px] items-start gap-1.5 text-text-muted">
        <Icon className="mt-0.5 h-3 w-3 shrink-0" />
        <p className="text-[9.5px] font-semibold uppercase leading-tight tracking-wider">{label}</p>
      </div>
      <p className="mt-1.5 text-[20px] font-black leading-none text-text-primary">
        {typeof value === "number" ? value.toLocaleString("en-IN") : (value ?? "—")}
      </p>
      <p className="mt-1 min-h-[13px] text-[10px] text-text-muted">{sub ?? ""}</p>
    </div>
  );
}

function GridCard({ a, large = false }: { a: InsightCard; large?: boolean }) {
  return (
    <Link
      href={`/newsroom/article/${a.slug}`}
      className="group flex flex-col overflow-hidden rounded-xl border border-surface-border/7 bg-text-primary/[0.02] transition hover:border-surface-border/20 hover:bg-text-primary/[0.04]"
    >
      <div className="relative">
        <HeroImage
          heroImageUrl={a.hero_image_url}
          headline={a.headline}
          articleType={a.article_type}
          sectors={(a.sectors_affected ?? []).map(s => s.name)}
          className={large ? "h-36" : "h-28"}
        />
        <span className="absolute left-2.5 top-2.5 rounded-full border border-surface-border/10 bg-black/50 px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider text-text-primary backdrop-blur">
          {TYPE_LABEL[a.article_type] ?? "Intelligence"}
        </span>
        <div className="absolute right-2 top-2">
          <BookmarkButton slug={a.slug} headline={a.headline} articleType={a.article_type} className="bg-black/40 backdrop-blur" />
        </div>
      </div>
      <div className="flex flex-1 flex-col p-3.5">
        <p className={`line-clamp-2 font-semibold leading-snug text-text-primary group-hover:text-sky-700 dark:text-sky-200 transition ${large ? "text-[14px]" : "text-[12.5px]"}`}>
          {cleanText(a.headline)}
        </p>
        {(a.key_takeaway || a.executive_summary) && large && (
          <p className="mt-1.5 line-clamp-2 text-[12px] leading-5 text-text-muted">
            {cleanText(a.key_takeaway ?? a.executive_summary ?? "")}
          </p>
        )}
        <div className="mt-auto flex flex-wrap items-center gap-x-2.5 gap-y-1 pt-2.5 text-[10px] text-text-muted">
          {a.confidence_score != null && (
            <span
              className="font-semibold text-sky-400"
              title="Model Self-Rating -- the article's own self-reported certainty, not a verified score"
            >
              {Math.round(a.confidence_score * 100)}%
            </span>
          )}
          {a.read_time_minutes && <span>{a.read_time_minutes} min</span>}
          {a.published_at && <span className="flex items-center gap-1"><Clock className="h-2.5 w-2.5" />{fmtRelative(a.published_at)}</span>}
          {!!a.views && <span className="ml-auto flex items-center gap-1"><Eye className="h-2.5 w-2.5" />{a.views}</span>}
        </div>
      </div>
    </Link>
  );
}
