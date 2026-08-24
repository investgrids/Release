"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Sparkles, Zap, GitBranch, History, Lightbulb, ArrowRight } from "lucide-react";
import { API_BASE_URL as API } from "@/lib/api";
import { InvestmentWatchPanel, type WatchSubject } from "@/components/ai/InvestmentWatchPanel";
import { ConfidenceBreakdownPanel } from "@/components/ai/ConfidenceBreakdownPanel";

interface ActiveEvent { id: string; slug?: string; headline: string; urgency: number; sentiment: string; lifecycle: string; active_score: number; direct: boolean; }
interface RipplePosition { upstream: string[]; company: string; downstream: string[]; }
interface Historical { event_title: string; similarity: number; key_lesson: string | null; winners: string[]; losers: string[]; }
// Batch E consumer migration, 2026-08-24 — company_intelligence.py now
// resolves the full href server-side (V1 numeric id or V2 slug,
// depending on settings.opportunity_read_source) rather than exposing a
// raw id/slug pair. Supersedes the earlier V2-B fix that switched this
// to o.id — that was only correct for V1 mode; href is correct in both.
interface RelatedOpportunity { title: string; href: string; score: number | null; }
interface CompanyIntel {
  available: boolean;
  symbol?: string;
  why_matters?: { stars: number; verdict: string | null; last_change: any; reasons: string[]; confidence: number };
  active_events?: ActiveEvent[];
  ripple_position?: RipplePosition;
  confidence_breakdown?: any;
  historical?: Historical | null;
  related_opportunities?: RelatedOpportunity[];
}

const _LIFECYCLE_DOT: Record<string, string> = {
  LIVE: "bg-rose-400", Developing: "bg-amber-400", Active: "bg-sky-400", Historical: "bg-slate-500",
};

function Stars({ n }: { n: number }) {
  return <span className="text-amber-400 tracking-tight">{"★".repeat(n)}<span className="text-text-primary/15">{"★".repeat(5 - n)}</span></span>;
}

/**
 * Company Intelligence (Platform Integration Sprint) — "why does this
 * company matter today," reusing every engine already built this session
 * rather than recomputing anything (see company_intelligence.py's module
 * docstring): the Unified Event Intelligence Engine for Active
 * Intelligence, Investment Watch (Phase 2B, mounted directly — not
 * re-rendered), the same Confidence Explainability panel AI Search uses
 * (fed real company-context signals), and the same historical-precedent
 * engine used everywhere else.
 */
export function CompanyIntelligenceSection({ symbol, govScore, pricePositive }: { symbol: string; govScore?: number | null; pricePositive?: boolean | null }) {
  const [data, setData] = useState<CompanyIntel | null>(null);

  useEffect(() => {
    const params = new URLSearchParams();
    if (govScore != null) params.set("gov_score", String(govScore));
    if (pricePositive != null) params.set("price_positive", String(pricePositive));
    fetch(`${API}/api/company-intelligence/${symbol}?${params.toString()}`)
      .then(r => r.json()).then(setData).catch(() => setData({ available: false }));
  }, [symbol, govScore, pricePositive]);

  if (!data?.available) return null;
  const wm = data.why_matters;
  const ripple = data.ripple_position;

  return (
    <div className="space-y-5">
      {/* 1. Why This Company Matters Today */}
      {wm && (
        <div className="rounded-[20px] border border-violet-500/15 bg-gradient-to-br from-violet-500/[0.06] to-transparent p-5">
          <div className="flex items-center justify-between">
            <p className="flex items-center gap-1.5 text-[11px] font-black uppercase tracking-[0.14em] text-violet-600 dark:text-violet-300">
              <Sparkles className="h-3.5 w-3.5" /> Why {symbol} Matters Today
            </p>
            <Stars n={wm.stars} />
          </div>
          <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3">
            <div>
              <p className="text-[9px] uppercase tracking-wider text-text-muted">Current Verdict</p>
              <p className="mt-0.5 text-[14px] font-bold text-text-primary">{wm.verdict ?? "—"}</p>
            </div>
            <div>
              <p className="text-[9px] uppercase tracking-wider text-text-muted">Last Changed</p>
              <p className="mt-0.5 text-[14px] font-bold text-text-primary">
                {wm.last_change ? `${wm.last_change.from_date} → ${wm.last_change.to_date}` : "No change yet"}
              </p>
            </div>
            <div>
              <p className="text-[9px] uppercase tracking-wider text-text-muted">Confidence</p>
              <p className="mt-0.5 text-[14px] font-bold text-text-primary">{Math.round(wm.confidence)}%</p>
            </div>
          </div>
          {wm.reasons.length > 0 && (
            <ul className="mt-3 space-y-1">
              {wm.reasons.map((r, i) => (
                <li key={i} className="flex items-start gap-1.5 text-[11.5px] leading-5 text-text-secondary">
                  <span className="mt-1 h-1 w-1 shrink-0 rounded-full bg-emerald-400" /> {r}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        {/* 2. Active Intelligence */}
        {(data.active_events?.length ?? 0) > 0 && (
          <div className="rounded-[20px] border border-surface-border/7 bg-text-primary/[0.02] p-5">
            <p className="mb-3 flex items-center gap-1.5 text-[11px] font-black uppercase tracking-[0.14em] text-text-secondary">
              <Zap className="h-3.5 w-3.5 text-amber-400" /> Currently Affecting {symbol}
            </p>
            <div className="space-y-2">
              {data.active_events!.map(e => (
                <Link key={e.id} href={`/events/${e.slug || e.id}` as any}
                  className="group flex items-start gap-2 rounded-xl border border-surface-border/5 bg-text-primary/[0.02] p-2.5 transition hover:border-surface-border/[0.12]">
                  <span className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${_LIFECYCLE_DOT[e.lifecycle] ?? "bg-slate-500"}`} />
                  <p className="min-w-0 flex-1 text-[12px] leading-snug text-text-secondary line-clamp-2 group-hover:text-text-primary transition">{e.headline}</p>
                  <ArrowRight className="mt-0.5 h-3 w-3 shrink-0 text-text-muted opacity-0 group-hover:opacity-100 transition" />
                </Link>
              ))}
            </div>
          </div>
        )}

        {/* 3. Ripple Position */}
        {ripple && (ripple.upstream.length > 0 || ripple.downstream.length > 0) && (
          <div className="rounded-[20px] border border-surface-border/7 bg-text-primary/[0.02] p-5">
            <p className="mb-3 flex items-center gap-1.5 text-[11px] font-black uppercase tracking-[0.14em] text-text-secondary">
              <GitBranch className="h-3.5 w-3.5 text-sky-400" /> Ripple Position
            </p>
            <div className="flex flex-wrap items-center gap-1.5 text-[11px]">
              {ripple.upstream.map((u, i) => (
                <span key={`u${i}`} className="flex items-center gap-1.5">
                  <span className="rounded-full border border-surface-border/10 bg-text-primary/[0.03] px-2 py-1 text-text-secondary">{u}</span>
                  <ArrowRight className="h-3 w-3 text-text-muted" />
                </span>
              ))}
              <span className="rounded-full border border-violet-500/30 bg-violet-500/10 px-2.5 py-1 font-bold text-violet-600 dark:text-violet-300">{ripple.company}</span>
              {ripple.downstream.map((d, i) => (
                <span key={`d${i}`} className="flex items-center gap-1.5">
                  <ArrowRight className="h-3 w-3 text-text-muted" />
                  <Link href={`/companies/${d}` as any} className="rounded-full border border-surface-border/10 bg-text-primary/[0.03] px-2 py-1 text-text-secondary transition hover:border-violet-500/30 hover:text-violet-600 dark:text-violet-300">{d}</Link>
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        {/* 5. Why Confidence — reused verbatim, AI Search's own component */}
        {data.confidence_breakdown && <ConfidenceBreakdownPanel breakdown={data.confidence_breakdown} />}

        {/* 7. Investment Watch — reused verbatim, Phase 2B's own component */}
        <InvestmentWatchPanel subject={{ subject_key: `company:${symbol}`, subject_type: "company", subject_label: symbol } as WatchSubject} />
      </div>

      {/* 6. Historical Intelligence */}
      {data.historical && (
        <div className="rounded-[20px] border border-amber-500/15 bg-amber-500/[0.04] p-5">
          <p className="mb-2 flex items-center gap-1.5 text-[11px] font-black uppercase tracking-[0.14em] text-amber-600 dark:text-amber-300">
            <History className="h-3.5 w-3.5" /> Similar Situation
          </p>
          <div className="flex items-center justify-between">
            <p className="text-[13px] font-semibold text-text-primary">{data.historical.event_title}</p>
            <span className="shrink-0 rounded-full border border-amber-500/25 bg-amber-500/10 px-2 py-0.5 text-[11px] font-bold text-amber-600 dark:text-amber-300">
              {Math.round(data.historical.similarity)}% similar
            </span>
          </div>
          {data.historical.key_lesson && <p className="mt-1.5 text-[12px] leading-5 text-text-secondary">{data.historical.key_lesson}</p>}
          {(data.historical.winners.length > 0 || data.historical.losers.length > 0) && (
            <div className="mt-2.5 flex flex-wrap gap-x-4 gap-y-1 text-[11px]">
              {data.historical.winners.map((w, i) => <span key={`w${i}`} className="text-emerald-400">▲ {w}</span>)}
              {data.historical.losers.map((l, i) => <span key={`l${i}`} className="text-rose-400">▼ {l}</span>)}
            </div>
          )}
        </div>
      )}

      {/* 8. Related Opportunities */}
      {(data.related_opportunities?.length ?? 0) > 0 && (
        <div className="rounded-[20px] border border-surface-border/7 bg-text-primary/[0.02] p-5">
          <p className="mb-3 flex items-center gap-1.5 text-[11px] font-black uppercase tracking-[0.14em] text-text-secondary">
            <Lightbulb className="h-3.5 w-3.5 text-emerald-400" /> Related Opportunities
          </p>
          <div className="flex flex-wrap gap-2">
            {data.related_opportunities!.map(o => (
              <Link key={o.href} href={o.href as any}
                className="flex items-center gap-2 rounded-xl border border-emerald-500/20 bg-emerald-500/[0.06] px-3 py-2 text-[12px] font-medium text-emerald-600 dark:text-emerald-300 transition hover:bg-emerald-500/10">
                {o.title} {o.score != null && <span className="text-[10px] text-emerald-400/70">{Math.round(o.score)}</span>}
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
