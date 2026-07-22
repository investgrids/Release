import type { Metadata } from "next";
import Link from "next/link";
import {
  Sunrise, Moon, Newspaper, CalendarClock, TrendingUp, ShieldAlert, Eye,
  BadgeCheck, ChevronRight,
} from "lucide-react";
import { API_BASE_URL as API } from "@/lib/api";
import { cleanText } from "@/lib/text";

export const metadata: Metadata = {
  title: "Daily Brief | AI Newsroom",
  description: "Today's AI market brief — overnight moves, market wrap, key events, opportunities, and risks in one place.",
  alternates: { canonical: "/newsroom/daily-brief" },
};

// ── Types (subset of the real /api/insights/{slug} detail shape) ────────────

interface CompanyAffected { name: string; symbol: string; impact: string; reason?: string }
interface OpportunityItem { title: string; description: string; timeframe?: string; risk?: string }
interface RiskItem { title: string; description: string; severity?: string; mitigation?: string }

interface ArticleDetail {
  slug: string;
  headline: string;
  key_takeaway?: string;
  executive_summary?: string;
  what_happened?: string;
  companies_affected: CompanyAffected[];
  opportunities: OpportunityItem[];
  risks: RiskItem[];
  what_to_watch_next: string[];
  sources: string[];
  confidence_score?: number;
  published_at?: string;
}

interface EventCard {
  id: string;
  title: string;
  category: string;
  impact_score: number;
}

async function fetchJSON<T>(path: string, fallback: T): Promise<T> {
  try {
    const res = await fetch(`${API}${path}`, { next: { revalidate: 300 } });
    if (!res.ok) return fallback;
    return res.json();
  } catch {
    return fallback;
  }
}

async function getBriefData() {
  const [morningList, wrapList, events] = await Promise.all([
    fetchJSON<{ items: { slug: string }[] }>("/api/insights/?article_type=morning_intelligence&limit=1", { items: [] }),
    fetchJSON<{ items: { slug: string; headline: string; key_takeaway?: string }[] }>("/api/insights/?article_type=market_wrap&limit=1", { items: [] }),
    fetchJSON<EventCard[]>("/api/events/?limit=5&sort_by=impact_score", []),
  ]);

  const morningSlug = morningList.items[0]?.slug;
  const morning = morningSlug
    ? await fetchJSON<ArticleDetail | null>(`/api/insights/${morningSlug}`, null)
    : null;

  return { morning, wrap: wrapList.items[0] ?? null, events };
}

function fmtTime(iso?: string) {
  if (!iso) return "";
  return new Date(iso).toLocaleString("en-IN", {
    day: "numeric", month: "short", hour: "2-digit", minute: "2-digit",
  });
}

const RISK_COLOR: Record<string, string> = {
  high: "text-rose-400 border-rose-500/30 bg-rose-500/10",
  medium: "text-amber-400 border-amber-500/30 bg-amber-500/10",
  low: "text-emerald-400 border-emerald-500/30 bg-emerald-500/10",
};

export default async function DailyBriefPage() {
  const { morning, wrap, events } = await getBriefData();

  if (!morning) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-16 sm:px-6">
        <p className="rounded-2xl border border-white/[0.07] bg-white/[0.03] p-8 text-center text-[13px] text-slate-500">
          No Daily Brief published yet today — check back soon.
        </p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl space-y-10 px-4 py-8 sm:px-6">

      {/* Morning Outlook */}
      <section>
        <p className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">
          <Sunrise className="h-3 w-3 text-amber-400" /> Morning Outlook
        </p>
        <h1 className="mt-3 text-[26px] font-black leading-tight text-white md:text-[30px]">
          {cleanText(morning.headline)}
        </h1>
        {morning.published_at && (
          <p className="mt-1.5 text-[12px] text-slate-500">Published {fmtTime(morning.published_at)}</p>
        )}
        {morning.key_takeaway && (
          <p className="mt-4 rounded-xl border border-amber-500/20 bg-amber-500/[0.06] p-4 text-[14px] leading-6 text-amber-100/90">
            {cleanText(morning.key_takeaway)}
          </p>
        )}
        {morning.executive_summary && (
          <p className="mt-4 text-[14.5px] leading-7 text-slate-300">{cleanText(morning.executive_summary)}</p>
        )}
      </section>

      {/* What Happened Overnight */}
      {morning.what_happened && (
        <section>
          <p className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">
            <Moon className="h-3 w-3 text-indigo-400" /> What Happened Overnight
          </p>
          <p className="mt-3 text-[14.5px] leading-7 text-slate-300">{cleanText(morning.what_happened)}</p>
        </section>
      )}

      {/* Market Wrap — embedded within Daily Brief, not a separate top-level
          section: users think in terms of "today's briefing," not "briefing
          plus a separate market wrap." */}
      {wrap && (
        <section>
          <p className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">
            <Newspaper className="h-3 w-3 text-sky-400" /> Market Wrap — Previous Session
          </p>
          <Link
            href={`/newsroom/article/${wrap.slug}`}
            className="group mt-3 block rounded-xl border border-white/[0.07] bg-white/[0.03] p-4 transition hover:border-white/20 hover:bg-white/[0.05]"
          >
            <p className="text-[14.5px] font-semibold text-white group-hover:text-sky-200">{cleanText(wrap.headline)}</p>
            {wrap.key_takeaway && (
              <p className="mt-1.5 line-clamp-2 text-[13px] leading-5 text-slate-400">{cleanText(wrap.key_takeaway)}</p>
            )}
            <span className="mt-2 inline-flex items-center gap-0.5 text-[12px] font-medium text-sky-400">
              Read the full wrap <ChevronRight className="h-3 w-3" />
            </span>
          </Link>
        </section>
      )}

      {/* Today's Key Events */}
      <section>
        <p className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">
          <CalendarClock className="h-3 w-3 text-violet-400" /> Today&apos;s Key Events
        </p>
        {events.length === 0 ? (
          <p className="mt-3 rounded-xl border border-white/[0.07] bg-white/[0.03] p-4 text-[12.5px] text-slate-500">
            No high-impact events right now.
          </p>
        ) : (
          <div className="mt-3 space-y-2">
            {events.map((e) => (
              <div key={e.id} className="flex items-center justify-between rounded-xl border border-white/[0.07] bg-white/[0.03] p-3.5">
                <p className="text-[13.5px] text-slate-200">{cleanText(e.title)}</p>
                <span className="shrink-0 text-[11px] text-slate-500">{e.category} · {Math.round(e.impact_score)}</span>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Opportunities */}
      {morning.opportunities?.length > 0 && (
        <section>
          <p className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">
            <TrendingUp className="h-3 w-3 text-emerald-400" /> Opportunities
          </p>
          <div className="mt-3 space-y-3">
            {morning.opportunities.map((o, i) => (
              <div key={i} className="rounded-xl border border-emerald-500/15 bg-emerald-500/[0.04] p-4">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-[13.5px] font-semibold text-emerald-200">{cleanText(o.title)}</p>
                  {o.risk && (
                    <span className={`shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase ${RISK_COLOR[o.risk] ?? RISK_COLOR.medium}`}>
                      {o.risk} risk
                    </span>
                  )}
                </div>
                <p className="mt-1.5 text-[13px] leading-5 text-slate-400">{cleanText(o.description)}</p>
                {o.timeframe && <p className="mt-1.5 text-[11px] text-slate-600">Timeframe: {o.timeframe}</p>}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Risks */}
      {morning.risks?.length > 0 && (
        <section>
          <p className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">
            <ShieldAlert className="h-3 w-3 text-rose-400" /> Risks
          </p>
          <div className="mt-3 space-y-3">
            {morning.risks.map((r, i) => (
              <div key={i} className="rounded-xl border border-rose-500/15 bg-rose-500/[0.04] p-4">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-[13.5px] font-semibold text-rose-200">{cleanText(r.title)}</p>
                  {r.severity && (
                    <span className={`shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase ${RISK_COLOR[r.severity] ?? RISK_COLOR.medium}`}>
                      {r.severity}
                    </span>
                  )}
                </div>
                <p className="mt-1.5 text-[13px] leading-5 text-slate-400">{cleanText(r.description)}</p>
                {r.mitigation && (
                  <p className="mt-1.5 text-[11.5px] leading-5 text-slate-500">
                    <span className="font-semibold text-slate-400">Mitigation:</span> {cleanText(r.mitigation)}
                  </p>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* What to Watch Next */}
      {morning.what_to_watch_next?.length > 0 && (
        <section>
          <p className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">
            <Eye className="h-3 w-3 text-sky-400" /> What to Watch Next
          </p>
          <ul className="mt-3 space-y-2">
            {morning.what_to_watch_next.map((w, i) => (
              <li key={i} className="flex gap-2 text-[13.5px] leading-6 text-slate-300">
                <span className="text-sky-500">•</span> {cleanText(w)}
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Supporting Evidence — real sources behind this brief, not the AI's own claim */}
      {morning.sources?.length > 0 && (
        <section className="border-t border-white/[0.07] pt-6">
          <p className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">
            <BadgeCheck className="h-3 w-3 text-slate-400" /> Supporting Evidence
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            {morning.sources.map((s, i) => (
              <span key={i} className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[11.5px] text-slate-400">
                ✓ {s}
              </span>
            ))}
          </div>
        </section>
      )}

    </div>
  );
}
