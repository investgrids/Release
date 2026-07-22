import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import {
  TrendingUp, ShieldAlert, Gauge, Building2, CalendarClock, Newspaper, Sparkles,
} from "lucide-react";
import { API_BASE_URL as API } from "@/lib/api";
import { cleanText } from "@/lib/text";

interface OpportunityListItem { id: number; slug: string }
interface AISummary { matters: string; benefits: string; risks: string[]; why_bullets: string[] }
interface OppCompany { symbol: string; company_name: string; impact_score: number; trend: string; reason: string }
interface OppEvent { title: string; event_date: string; description: string }
interface OppNews { headline: string; source: string; url: string }
interface OpportunityDetail {
  id: number; slug: string; title: string; summary: string;
  opportunity_score: number; confidence: number; trend: string; risk_level: string;
  time_horizon: string; sectors: string[];
  ai_summary?: AISummary | null;
  companies: OppCompany[];
  events: OppEvent[];
  news: OppNews[];
}
interface ThemeArticle { slug: string; headline: string; key_takeaway?: string; executive_summary?: string; sectors_affected: { name: string }[] }

async function fetchJSON<T>(path: string, fallback: T): Promise<T> {
  try {
    const res = await fetch(`${API}${path}`, { next: { revalidate: 300 } });
    if (!res.ok) return fallback;
    return res.json();
  } catch {
    return fallback;
  }
}

// The opportunity detail endpoint (/api/radar/{id}) takes a numeric ID, not
// a slug — resolve the slug from the params against the list first, same
// approach as the list page uses to build these links.
async function resolveIdBySlug(slug: string): Promise<number | null> {
  const list = await fetchJSON<{ items: OpportunityListItem[] }>("/api/radar/?page=1&page_size=100", { items: [] });
  return list.items.find((o) => o.slug === slug)?.id ?? null;
}

// Best-effort match against a real AIPE theme_intelligence article covering
// the same theme — title/sector text overlap, since there's no direct FK
// between Opportunity rows and IntelligenceArticle rows.
async function findMatchingThemeArticle(title: string, sectors: string[]): Promise<ThemeArticle | null> {
  const list = await fetchJSON<{ items: ThemeArticle[] }>("/api/insights/?article_type=theme_intelligence&limit=20", { items: [] });
  const titleLower = title.toLowerCase();
  const sectorsLower = sectors.map((s) => s.toLowerCase());
  return (
    list.items.find((a) => {
      const headlineLower = a.headline.toLowerCase();
      const articleSectors = (a.sectors_affected ?? []).map((s) => s.name.toLowerCase());
      return (
        sectorsLower.some((s) => headlineLower.includes(s) || articleSectors.includes(s)) ||
        titleLower.split(" ").some((w) => w.length > 4 && headlineLower.includes(w))
      );
    }) ?? null
  );
}

export async function generateMetadata(
  { params }: { params: Promise<{ slug: string }> }
): Promise<Metadata> {
  const { slug } = await params;
  const id = await resolveIdBySlug(slug);
  if (id === null) return { title: "Not Found" };
  const detail = await fetchJSON<OpportunityDetail | null>(`/api/radar/${id}`, null);
  if (!detail) return { title: "Not Found" };

  const title = `${cleanText(detail.title)} | Theme Intelligence`;
  const description = detail.summary ? cleanText(detail.summary) : `Real opportunity score, confidence, and AI analysis for ${cleanText(detail.title)}.`;
  return {
    title,
    description,
    alternates: { canonical: `/newsroom/themes/${slug}` },
  };
}

export default async function ThemeDetailPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const id = await resolveIdBySlug(slug);
  if (id === null) notFound();

  const detail = await fetchJSON<OpportunityDetail | null>(`/api/radar/${id}`, null);
  if (!detail) notFound();

  const themeArticle = await findMatchingThemeArticle(detail.title, detail.sectors);

  return (
    <div className="mx-auto max-w-4xl px-4 py-8 sm:px-6">

      {/* Header */}
      <div className="mb-6">
        <p className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">
          <TrendingUp className="h-3 w-3 text-emerald-400" /> Theme Intelligence
        </p>
        <h1 className="mt-2 text-[26px] font-black leading-tight text-white md:text-[30px]">{cleanText(detail.title)}</h1>
        {detail.summary && <p className="mt-2 text-[14px] leading-6 text-slate-400">{cleanText(detail.summary)}</p>}
        {detail.sectors.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1.5">
            {detail.sectors.map((s, i) => (
              <span key={i} className="rounded-full border border-white/10 bg-white/5 px-2.5 py-1 text-[11px] text-slate-400">{s}</span>
            ))}
          </div>
        )}
      </div>

      {/* Theme Scores — real, computed, no AI inference */}
      <section className="mb-8 grid grid-cols-3 gap-3">
        <div className="rounded-xl border border-white/[0.07] bg-white/[0.03] p-4 text-center">
          <p className="text-[28px] font-black text-emerald-400">{Math.round(detail.opportunity_score)}</p>
          <p className="mt-0.5 text-[10px] uppercase tracking-wider text-slate-500">Opportunity Score</p>
        </div>
        <div className="rounded-xl border border-white/[0.07] bg-white/[0.03] p-4 text-center">
          <p className="text-[28px] font-black text-sky-400">{Math.round(detail.confidence * 100)}%</p>
          <p className="mt-0.5 text-[10px] uppercase tracking-wider text-slate-500">Confidence</p>
        </div>
        <div className="rounded-xl border border-white/[0.07] bg-white/[0.03] p-4 text-center">
          <p className="text-[18px] font-black text-amber-400">{detail.risk_level || "—"}</p>
          <p className="mt-0.5 text-[10px] uppercase tracking-wider text-slate-500">Risk · {detail.time_horizon || "n/a"}</p>
        </div>
      </section>

      {/* AI Theme Intelligence — prefer the real AIPE article; fall back to
          the radar engine's own real ai_summary if no article matches yet. */}
      <section className="mb-8">
        <p className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">
          <Sparkles className="h-3 w-3 text-violet-400" /> AI Theme Intelligence
        </p>
        {themeArticle ? (
          <Link
            href={`/newsroom/article/${themeArticle.slug}`}
            className="group mt-3 block rounded-xl border border-white/[0.07] bg-white/[0.03] p-4 transition hover:border-white/20 hover:bg-white/[0.05]"
          >
            <p className="text-[14.5px] font-semibold text-white group-hover:text-sky-200">{cleanText(themeArticle.headline)}</p>
            {(themeArticle.key_takeaway || themeArticle.executive_summary) && (
              <p className="mt-1.5 text-[13px] leading-5 text-slate-400">
                {cleanText(themeArticle.key_takeaway ?? themeArticle.executive_summary)}
              </p>
            )}
          </Link>
        ) : detail.ai_summary?.matters ? (
          <div className="mt-3 space-y-2 rounded-xl border border-white/[0.07] bg-white/[0.03] p-4">
            <p className="text-[13.5px] leading-6 text-slate-300">{cleanText(detail.ai_summary.matters)}</p>
            {detail.ai_summary.why_bullets?.length > 0 && (
              <ul className="mt-2 space-y-1">
                {detail.ai_summary.why_bullets.map((b, i) => (
                  <li key={i} className="flex gap-2 text-[12.5px] leading-5 text-slate-400">
                    <span className="text-violet-500">•</span> {cleanText(b)}
                  </li>
                ))}
              </ul>
            )}
          </div>
        ) : (
          <p className="mt-3 rounded-xl border border-white/[0.07] bg-white/[0.03] p-4 text-[12.5px] text-slate-500">
            No AI analysis available for this theme yet.
          </p>
        )}
      </section>

      {/* Companies */}
      {detail.companies?.length > 0 && (
        <section className="mb-8">
          <p className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">
            <Building2 className="h-3 w-3 text-sky-400" /> Related Companies
          </p>
          <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
            {detail.companies.map((c, i) => (
              <div key={i} className="rounded-xl border border-white/[0.07] bg-white/[0.03] p-3.5">
                <div className="flex items-center justify-between">
                  <span className="text-[13px] font-bold text-white">{c.symbol}</span>
                  <span className="text-[11px] text-slate-500">{Math.round(c.impact_score)}</span>
                </div>
                <p className="mt-0.5 text-[11.5px] text-slate-500">{cleanText(c.company_name)}</p>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Recent Events */}
      {detail.events?.length > 0 && (
        <section className="mb-8">
          <p className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">
            <CalendarClock className="h-3 w-3 text-indigo-400" /> Recent Events
          </p>
          <div className="mt-3 space-y-2">
            {detail.events.map((e, i) => (
              <div key={i} className="rounded-xl border border-white/[0.07] bg-white/[0.03] p-3.5">
                <p className="text-[13px] font-medium text-slate-200">{cleanText(e.title)}</p>
                {e.description && <p className="mt-1 line-clamp-1 text-[12px] text-slate-500">{cleanText(e.description)}</p>}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Live Sources */}
      {detail.news?.length > 0 && (
        <section className="border-t border-white/[0.07] pt-6">
          <p className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">
            <Newspaper className="h-3 w-3 text-slate-400" /> Live Sources
          </p>
          <ul className="mt-3 divide-y divide-white/[0.06] rounded-xl border border-white/[0.07] bg-white/[0.02]">
            {detail.news.map((n, i) => (
              <li key={i} className="px-4 py-2.5 text-[12.5px] text-slate-300">
                {cleanText(n.headline)} <span className="text-slate-600">· {n.source}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

    </div>
  );
}
