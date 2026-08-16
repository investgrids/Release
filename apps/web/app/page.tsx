import { Suspense, cache } from "react";
import type { Metadata } from "next";
import Link from "next/link";
import {
  ArrowRight, ChevronRight, Calendar, Building2, BarChart3,
  Landmark, Droplets, Shield, Cloud, DollarSign, FlameKindling, Cpu, Wheat,
  Sparkles, TrendingUp, Radar, GitBranch, Rocket, History,
} from "lucide-react";
import { HomepageRefresher } from "@/components/homepage/HomepageRefresher";
import { IndependenceDayBanner } from "@/components/homepage/IndependenceDayBanner";
import { MarketSessionGate }  from "@/components/MarketSessionGate";
import { LiveIntelligenceFeed } from "@/components/market/LiveIntelligenceFeed";
import { WeekendHomePage } from "@/components/weekend/WeekendHomePage";
import { API_BASE_URL as API } from "@/lib/api";
import { isWeekendSession } from "@/lib/weekendSession";
import { compareScoresDesc, impactToStyle } from "@/lib/scoring";
import { cleanText, truncateForQuery } from "@/lib/text";
import { calendarCategoryLabel } from "@/lib/economicCalendarCategory";

export const dynamic = "force-dynamic";

// SEO fix: the root layout previously set a blanket alternates.canonical
// pointing here (the homepage) for EVERY page site-wide — any page that
// didn't define its own canonical silently inherited this one, telling
// search engines the homepage was the canonical version of pages like
// /companies, /faq, /ripple, /about (confirmed live: <link rel="canonical"
// href=".../"> on all of them). The homepage itself needs the exact same
// tag it was implicitly relying on the root default for — this makes that
// explicit and local, so the root default could be removed without the
// homepage losing its own canonical.
export const metadata: Metadata = {
  alternates: { canonical: process.env.NEXT_PUBLIC_SITE_URL ?? "https://www.marketripple.in" },
};

// The AI-generated morning brief (and, less often, real event data) lists
// market indices and macro instruments in the same companies_affected /
// event.companies shape a real company uses ("Sensex" / SENSEX, "Nifty
// 50" / NIFTY) — found live in production ("Stocks to Watch" showing
// SENSEX and NIFTY as if they were tickers). Same root cause the backend
// itself already guards against in live_intelligence.py's anomaly
// detector (indices/macro symbols mixed into real event ticker lists) —
// applied here too since the frontend doesn't have that backend's real
// company-universe lookup to check against, only a blocklist of the
// known non-company symbols this pipeline actually produces.
const _NON_COMPANY_SYMBOLS = new Set([
  "SENSEX", "NIFTY", "NIFTY50", "BANKNIFTY", "NIFTYBANK", "INDIAVIX", "VIX",
  "INR", "USDINR", "GOLD", "SILVER", "CRUDE", "BRENT",
]);
function isRealCompanySymbol(symbol?: string | null): boolean {
  return !!symbol && !_NON_COMPANY_SYMBOLS.has(symbol.trim().toUpperCase());
}

// ── Fetch helpers — single cached call per render ─────────────────────────────
async function live<T = any>(url: string, ms = 7000): Promise<T | null> {
  const ac = new AbortController();
  const t  = setTimeout(() => ac.abort(), ms);
  try {
    const r = await fetch(url, { cache: "no-store", signal: ac.signal });
    clearTimeout(t);
    return r.ok ? r.json() : null;
  } catch { clearTimeout(t); return null; }
}
async function revalidate<T = any>(url: string, sec = 60, ms = 5000): Promise<T | null> {
  const ac = new AbortController();
  const t  = setTimeout(() => ac.abort(), ms);
  try {
    const r = await fetch(url, { next: { revalidate: sec }, signal: ac.signal });
    clearTimeout(t);
    return r.ok ? r.json() : null;
  } catch { clearTimeout(t); return null; }
}

// One call each — deduplicated within a render via cache()
// (getMIE removed — no homepage card reads MIE directly anymore; the
// three cards that used to now read the real AIPE/Opportunity Engine
// sources instead. MIE itself is untouched and still powers other pages.)
// Re-added specifically for the hero's top-level market-direction verdict —
// see the comment at HomepageIntelligenceHero's `outlook` derivation for
// why. Every other homepage card still reads AIPE/Opportunity Engine
// sources as before; this one call is scoped to fixing a single confirmed
// bug, not a wholesale revert of the "MIE removed" decision above.
const getMieState     = cache(() => live(`${API}/api/mie/state`));
const getPremarket    = cache(() => live(`${API}/api/market/premarket`));
const getTopMovers    = cache(() => live(`${API}/api/market/top-movers`));
const getCalendar     = cache(() => live(`${API}/api/calendar/`));
const getIndices      = cache(() => live<any[]>(`${API}/api/indices/`));
const getLive         = cache(() => live(`${API}/api/market/live`));
const getSession      = cache(() => live(`${API}/api/market/session`));
const getRadar        = cache(() => revalidate(`${API}/api/radar/?page=1&page_size=4`, 120));
// Recency-aware ranking (event_lifecycle.py) — used by "Latest Biggest
// Events" below.
const getActiveEvents = cache(() => revalidate(`${API}/api/events/?sort_by=active&page_size=5`, 120));
// CompaniesToWatchTable's own pull from the SAME recency-aware endpoint —
// a larger page than getActiveEvents' own page_size=5 because extracting
// up to 5 DISTINCT companies (not events) needs a bigger real pool to
// draw from. Previously used the plain impact_score-sorted pool above,
// which only returns the top-10 BY SCORE before any recency filtering
// ever runs — so a real, currently-relevant company past rank 10 was
// invisible no matter how good a decay formula ran on top of it. Found
// live: switching sources was the actual fix, not a better decay curve.
const getActiveEventsForWatch = cache(() => revalidate(`${API}/api/events/?sort_by=active&page_size=25`, 300));
const getInsights     = cache(() => revalidate(`${API}/api/insights/?limit=4`, 300));

// Real AIPE Daily Brief — single source of truth for "what does the AI say
// about today," replacing the old MIE-sourced mie.story. Two calls (list
// then detail) because the list row doesn't carry the structured risks[]
// field Key Risks needs; cache() dedupes this across AIMarketBriefCard and
// KeyRisksCard so it only actually fetches once per render.
const getMorningBrief = cache(async () => {
  const list = await revalidate<{ items: { slug: string }[] }>(
    `${API}/api/insights/?article_type=morning_intelligence&limit=1`, 300,
  );
  const slug = list?.items?.[0]?.slug;
  if (!slug) return null;
  return revalidate<any>(`${API}/api/insights/${slug}`, 300);
});

// Phase 3 — the two things the morning_intelligence article itself can't
// carry (a real day-over-day diff, and the article-derived AI Prediction
// line) — see homepage_intelligence.py's module docstring for why this
// is deliberately NOT a second, competing narrative source.
const getHomepageExtras = cache(() => live(`${API}/api/homepage/intelligence`, 6000));

// Phase 3, Priority 2 — see live_intelligence.py's module docstring for
// exactly what backs each of the 4 real card types.
const getLiveIntelligenceItems = cache(() => live<{ items: any[] }>(`${API}/api/live-intelligence/feed`, 8000));

// ── Pure helpers ──────────────────────────────────────────────────────────────
function todayDateStr() {
  // Add IST offset, then read components via getUTC* to avoid double-applying
  // local timezone offset on systems already in IST (which would push evening → tomorrow)
  const ist = new Date(Date.now() + 5.5 * 3600_000);
  return new Date(ist.getUTCFullYear(), ist.getUTCMonth(), ist.getUTCDate()).toDateString();
}

function timeAgo(iso: string | null | undefined): string {
  if (!iso) return "";
  const mins = Math.floor((Date.now() - new Date(iso).getTime()) / 60000);
  return mins < 1 ? "just now" : mins < 60 ? `${mins}m ago` : `${Math.floor(mins / 60)}h ago`;
}

// The backend only ever creates a morning_intelligence article in one of two
// windows: the normal 06:00-11:59 IST run, or the noon+ one-time late
// backfill (see publisher.py's _scheduled_article_due). published_at's IST
// hour is therefore a reliable signal for which one happened — no separate
// "generated_late" field needs to round-trip through the API for this.
function briefTimeLabel(iso: string | null | undefined): string {
  if (!iso) return "";
  const ist = new Date(new Date(iso).getTime() + 5.5 * 3600_000);
  const hour = ist.getUTCHours();
  if (hour < 12) return `Updated ${timeAgo(iso)}`;
  const h12 = hour % 12 === 0 ? 12 : hour % 12;
  const mins = ist.getUTCMinutes().toString().padStart(2, "0");
  return `Generated at ${h12}:${mins} ${hour >= 12 ? "PM" : "AM"}`;
}

// ── Mini sparkline (fed real index chart points — never synthetic) ────────────
function MiniSparkline({ data, positive, w = 64, h = 28 }: { data: number[]; positive: boolean; w?: number; h?: number }) {
  if (!data || data.length < 2) return null;
  const min = Math.min(...data), max = Math.max(...data);
  const range = max - min || 1;
  const pad = 2;
  const pts = data.map((v, i) =>
    `${pad + (i / (data.length - 1)) * (w - pad * 2)},${pad + (h - pad * 2) - ((v - min) / range) * (h - pad * 2)}`
  ).join(" ");
  const fill = `${pad},${pad + h - pad * 2} ` + pts + ` ${pad + (w - pad * 2)},${pad + h - pad * 2}`;
  const color = positive ? "#22c55e" : "#f43f5e";
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`}>
      <polygon points={fill} fill={positive ? "rgba(34,197,94,0.12)" : "rgba(244,63,94,0.12)"}/>
      <polyline points={pts} stroke={color} strokeWidth="1.5" fill="none" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

// Category icon for events
function EventIcon({ title, category }: { title: string; category?: string }) {
  const base = "flex h-8 w-8 shrink-0 items-center justify-center rounded-xl";
  // Phase 5A.12 — exact category lookup first, for the real Economic
  // Calendar categories (rbi_mpc/india_cpi/india_iip/fomc/us_cpi/
  // us_jobs). The text-regex fallback below misfired on these: "India
  // CPI" matched the US-flag pattern via the substring "cpi", and
  // "FOMC Interest Rate Decision" matched the RBI/Landmark pattern via
  // "rate" — both silently wrong. An exact category can't misfire.
  if (category === "rbi_mpc")
    return <div className={`${base} bg-violet-500/20`}><Landmark className="h-4 w-4 text-violet-400"/></div>;
  if (category === "india_cpi" || category === "india_iip")
    return <div className={`${base} bg-teal-500/20`}><BarChart3 className="h-4 w-4 text-teal-400"/></div>;
  if (category === "fomc" || category === "us_cpi" || category === "us_jobs")
    return <div className={`${base} bg-sky-500/20`}><span className="text-[13px]">🇺🇸</span></div>;

  const t = (title + " " + (category ?? "")).toLowerCase();
  if (/rbi|reserve bank|monetary|rate|repo/.test(t))
    return <div className={`${base} bg-violet-500/20`}><Landmark className="h-4 w-4 text-violet-400"/></div>;
  if (/us |cpi|fed |federal|dollar|nasdaq|s&p/.test(t))
    return <div className={`${base} bg-sky-500/20`}><span className="text-[13px]">🇺🇸</span></div>;
  if (/crude|oil|brent|opec|petroleum/.test(t))
    return <div className={`${base} bg-orange-500/20`}><Droplets className="h-4 w-4 text-orange-400"/></div>;
  if (/defence|defense|military|army|order flow/.test(t))
    return <div className={`${base} bg-emerald-500/20`}><Shield className="h-4 w-4 text-emerald-400"/></div>;
  if (/monsoon|rain|weather|climate|agri/.test(t))
    return <div className={`${base} bg-sky-500/20`}><Cloud className="h-4 w-4 text-sky-400"/></div>;
  if (/budget|finance|ministry|gst|tax/.test(t))
    return <div className={`${base} bg-amber-500/20`}><Building2 className="h-4 w-4 text-amber-400"/></div>;
  if (/result|earning|q[1-4]|revenue|profit/.test(t))
    return <div className={`${base} bg-indigo-500/20`}><BarChart3 className="h-4 w-4 text-indigo-400"/></div>;
  if (/tech|it |software|digital|ai |chip|semiconductor/.test(t))
    return <div className={`${base} bg-cyan-500/20`}><Cpu className="h-4 w-4 text-cyan-400"/></div>;
  if (/wheat|grain|food|fmcg|fertiliz/.test(t))
    return <div className={`${base} bg-green-500/20`}><Wheat className="h-4 w-4 text-green-400"/></div>;
  if (/dollar|rupee|forex|currency|exchange/.test(t))
    return <div className={`${base} bg-teal-500/20`}><DollarSign className="h-4 w-4 text-teal-400"/></div>;
  if (/infra|power|energy|coal|gas/.test(t))
    return <div className={`${base} bg-amber-500/20`}><FlameKindling className="h-4 w-4 text-amber-400"/></div>;
  return <div className={`${base} bg-slate-500/20`}><Calendar className="h-4 w-4 text-text-secondary"/></div>;
}

// Skeleton
function Sk({ h = 200, r = "rounded-2xl" }: { h?: number; r?: string }) {
  return (
    <div className={`animate-pulse border border-surface-border/5 bg-text-primary/[0.02] ${r}`} style={{ height: h }} />
  );
}

// Shared compact card header — title + optional "View All →"
function CardHeader({ title, href, badge }: { title: string; href?: string; badge?: React.ReactNode }) {
  return (
    <div className="mb-3 flex items-center justify-between">
      <h3 className="text-[13px] font-black text-text-primary">{title}</h3>
      {badge ?? (href && (
        <Link href={href as any} className="flex items-center gap-1 text-[11px] font-semibold text-violet-400 hover:text-violet-600 dark:text-violet-300 transition">
          View All <ChevronRight className="h-3 w-3" />
        </Link>
      ))}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// TICKER STRIP (top) — real index sparklines, real USD/INR, real session status
// ═══════════════════════════════════════════════════════════════════════════════
async function TickerStrip() {
  const [indices, premarket, session] = await Promise.all([getIndices(), getPremarket(), getSession()]);
  const all = (indices ?? []) as any[];

  const WANT = [
    { match: "NIFTY 50",   label: "NIFTY 50" },
    { match: "SENSEX",     label: "SENSEX" },
    { match: "BANK NIFTY", label: "NIFTY BANK" },
    { match: "INDIA VIX",  label: "INDIA VIX" },
  ];
  const cells = WANT.map(w => {
    const m = all.find((i: any) => (i.name ?? "").toUpperCase() === w.match);
    return m ? { ...m, label: w.label } : null;
  }).filter(Boolean) as any[];

  const usdinr = ((premarket?.currencies ?? []) as any[]).find((c: any) => /USD.?INR/i.test(c.name ?? ""));
  const isOpen = session?.is_open;
  const statusLabel = isOpen ? "Market Open" : session?.session === "weekend" ? "Weekend" : "Market Closed";

  return (
    <div className="flex items-stretch divide-x divide-surface-border/6 overflow-x-auto rounded-2xl border border-surface-border/7 bg-surface-card scrollbar-hide">
      {cells.map((c: any) => {
        const chart = ((c.chart as any[] | undefined) ?? []).map((p: any) => p.value).filter((v: any) => typeof v === "number");
        return (
          <div key={c.label} className="flex min-w-[150px] flex-1 items-center justify-between gap-3 px-5 py-3.5">
            <div className="min-w-0">
              <p className="text-[9px] font-bold uppercase tracking-[0.1em] text-text-muted">{c.label}</p>
              <p className="text-[16px] font-black tabular-nums text-text-primary leading-tight">{c.value}</p>
              <p className={`text-[10px] font-bold tabular-nums ${c.positive ? "text-emerald-400" : "text-rose-400"}`}>{c.change}</p>
            </div>
            {chart.length >= 2 && <MiniSparkline data={chart} positive={c.positive !== false} w={56} h={26} />}
          </div>
        );
      })}
      {usdinr && (
        <div className="flex min-w-[130px] flex-1 flex-col justify-center gap-0.5 px-5 py-3.5">
          <p className="text-[9px] font-bold uppercase tracking-[0.1em] text-text-muted">USD/INR</p>
          <p className="text-[16px] font-black tabular-nums text-text-primary leading-tight">₹{usdinr.value}</p>
          <p className={`text-[10px] font-bold tabular-nums ${usdinr.positive ? "text-emerald-400" : "text-rose-400"}`}>{usdinr.change_str ?? usdinr.change}</p>
        </div>
      )}
      <div className="flex min-w-[150px] flex-1 flex-col justify-center gap-1 px-5 py-3.5">
        <p className="text-[9px] font-bold uppercase tracking-[0.1em] text-text-muted">Market Status</p>
        <p className={`text-[13px] font-black ${isOpen ? "text-emerald-400" : "text-text-secondary"}`}>{statusLabel}</p>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// ROW 1 — AI Market Brief · Today's Biggest Events · Market Snapshot
// ═══════════════════════════════════════════════════════════════════════════════
function ImpactDot({ impact }: { impact?: string }) {
  const i = (impact ?? "").toLowerCase();
  const color = i === "positive" ? "bg-emerald-400" : i === "negative" ? "bg-rose-400" : "bg-amber-400";
  return <span className={`inline-block h-1.5 w-1.5 shrink-0 rounded-full ${color}`} />;
}

function greeting(): string {
  const ist = new Date(Date.now() + 5.5 * 3600_000);
  const h = ist.getUTCHours();
  return h < 12 ? "Good Morning" : h < 17 ? "Good Afternoon" : "Good Evening";
}

function Stars({ n }: { n: number }) {
  return (
    <span className="text-amber-400 tracking-tight" aria-label={`${n} of 5`}>
      {"★".repeat(n)}<span className="text-text-muted/40">{"★".repeat(5 - n)}</span>
    </span>
  );
}

// Real sector-count → coarse outlook label. Not a stored field anywhere
// in the pipeline — this app has no discrete "Bullish/Bearish" classifier
// — but it's an honest, deterministic transform of already-real data
// (positive vs negative sector counts), the same kind of derivation the
// existing `stars` rating already does from impact_score. Never invented
// from nothing; always traceable back to the same sectors_affected array
// rendered elsewhere on this same hero.
function deriveOutlook(posCount: number, negCount: number): { label: string; cls: string; dot: string } {
  if (posCount === 0 && negCount === 0) return { label: "Neutral", cls: "text-text-secondary bg-slate-500/10 border-surface-border/5", dot: "bg-slate-400" };
  if (posCount >= negCount * 2 && posCount >= 2) return { label: "Bullish", cls: "text-emerald-600 dark:text-emerald-300 bg-emerald-500/10 border-emerald-500/20", dot: "bg-emerald-400" };
  if (posCount > negCount) return { label: "Cautiously Bullish", cls: "text-emerald-600 dark:text-emerald-300 bg-emerald-500/10 border-emerald-500/20", dot: "bg-emerald-400" };
  if (negCount >= posCount * 2 && negCount >= 2) return { label: "Bearish", cls: "text-rose-600 dark:text-rose-300 bg-rose-500/10 border-rose-500/20", dot: "bg-rose-400" };
  if (negCount > posCount) return { label: "Cautious", cls: "text-amber-600 dark:text-amber-300 bg-amber-500/10 border-amber-500/20", dot: "bg-amber-400" };
  return { label: "Neutral", cls: "text-text-secondary bg-slate-500/10 border-surface-border/5", dot: "bg-slate-400" };
}

// Same label/style vocabulary as deriveOutlook above, driven by MIE's real
// pulse ("+"/"-"/neutral) + confidence — the identical fields
// LiveMarketTab.tsx's AI Market Intelligence hero already renders via
// pulseDisplay(). Returns null (never a guess) when MIE has no story yet,
// so the caller can fall back to the sector-count derivation rather than
// showing a fabricated direction.
function deriveOutlookFromMie(pulse: string | undefined, confidence: number | null | undefined): { label: string; cls: string; dot: string } | null {
  if (!pulse) return null;
  const conf = confidence ?? 50;
  if (pulse === "+") {
    return conf >= 65
      ? { label: "Bullish", cls: "text-emerald-600 dark:text-emerald-300 bg-emerald-500/10 border-emerald-500/20", dot: "bg-emerald-400" }
      : { label: "Cautiously Bullish", cls: "text-emerald-600 dark:text-emerald-300 bg-emerald-500/10 border-emerald-500/20", dot: "bg-emerald-400" };
  }
  if (pulse === "-") {
    return conf >= 65
      ? { label: "Bearish", cls: "text-rose-600 dark:text-rose-300 bg-rose-500/10 border-rose-500/20", dot: "bg-rose-400" }
      : { label: "Cautious", cls: "text-amber-600 dark:text-amber-300 bg-amber-500/10 border-amber-500/20", dot: "bg-amber-400" };
  }
  return { label: "Neutral", cls: "text-text-secondary bg-slate-500/10 border-surface-border/5", dot: "bg-slate-400" };
}

// Real delta magnitude → 1-4 dot strength, same honest-derivation
// reasoning as deriveOutlook above — never a stored rating, always a
// transform of the same `delta` number rendered as text beside it.
function deltaStrength(delta: number): number {
  const n = Math.abs(delta);
  return n >= 4 ? 4 : n >= 3 ? 3 : n >= 1 ? 2 : 1;
}

// Real event titles (NSE compliance filings, mostly) frequently carry
// regulatory acronyms retail investors won't recognize — expands a small,
// well-known set in the DISPLAYED title only. Not new information: "PIT"
// genuinely stands for exactly this in every SEBI filing that uses it
// (confirmed by the same event data's own summary text), so this clarifies
// an existing real acronym rather than inventing anything.
const _ACRONYM_EXPANSIONS: Record<string, string> = {
  "PIT": "PIT (Prohibition of Insider Trading)",
  "SAST": "SAST (Substantial Acquisition of Shares & Takeovers)",
  "LODR": "LODR (Listing Obligations & Disclosure Requirements)",
};
function expandAcronyms(text: string): string {
  let out = text;
  for (const [k, v] of Object.entries(_ACRONYM_EXPANSIONS)) {
    out = out.replace(new RegExp(`\\b${k}\\b`), v);
  }
  return out;
}

/**
 * Homepage Intelligence (Phase 3, Priority 1) — the "Good Morning" daily
 * brief. Same single source of truth as before (the real AIPE
 * morning_intelligence article, never blended with MIE — see
 * homepage_intelligence.py's module docstring), reorganized into a
 * Decision (left) / Evidence (right) layout per the hero-layout audit.
 *
 * Two new real sources added, both already fetched elsewhere on this same
 * homepage render via cache()-deduped calls, so this adds zero new
 * network requests: getPremarket() (US futures / commodities / currencies
 * / FII-DII — backs "Today's Drivers") and getRadar() (backs the live
 * opportunity count in the status strip).
 *
 * Deliberately NOT built, because no real data backs them without
 * inventing something: an RBI stance driver (no discrete "surprise/no
 * surprise" field exists anywhere in the pipeline), per-company
 * confidence tiers (only a directional impact — positive/negative/
 * neutral — exists per company, never a numeric confidence), and a
 * "best time horizon" line (not a field on the morning brief).
 */
async function HomepageIntelligenceHero() {
  const [brief, extras, premarket, radar, activeForWatch, mie] = await Promise.all([
    getMorningBrief(), getHomepageExtras(), getPremarket(), getRadar(), getActiveEventsForWatch(), getMieState(),
  ]);
  if (!brief) return null;

  const ex = (extras as any) ?? {};
  const pm = (premarket as any) ?? {};
  const confPct = brief.confidence_score != null ? Math.round(brief.confidence_score * 100) : null;
  // The morning brief's own confidence (above) is how confident the AI was
  // WRITING that narrative — not a market-direction confidence. Confirmed
  // live: homepage showed "Bearish 92%" while Nifty/Sensex/BankNifty were
  // all solidly green and the Live Market tab's AI Market Intelligence
  // hero — reading the same MIE state every other page already trusts —
  // correctly said "Bullish 70%". Two flagship pages contradicting each
  // other on market direction is a real trust problem, so the top-level
  // verdict specifically (not the rest of this hero's sector-level
  // analysis) now reads the identical MIE story object Live Market uses.
  const mieStory = (mie as any)?.story ?? null;
  const marketConfPct = mieStory?.confidence != null ? Math.round(mieStory.confidence) : confPct;

  const ev = ex.event?.available ? ex.event.primary : null;
  const stars = ev
    ? Math.max(1, Math.min(5, Math.round((ev.impact_score ?? 60) / 20)))
    : Math.max(1, Math.min(5, Math.round((brief.impact_score ?? (confPct ?? 60)) / 20)));

  // "Economy" / "Macro" aren't things a user can invest in — real event
  // sector-tagging sometimes includes them alongside genuinely investable
  // sectors (e.g. a routine compliance-filing event tagged
  // ["Economy","Macro","Financials"]), so they're excluded from ever
  // becoming Focus / Biggest Opportunity / Biggest Risk.
  const NON_INVESTABLE = new Set(["economy", "macro", "market"]);
  const sectors = (brief.sectors_affected ?? []) as any[];
  const positiveSectors = sectors.filter(s => s.impact === "positive" && !NON_INVESTABLE.has((s.name ?? "").toLowerCase()))
    .sort((a, b) => _magRank(b.magnitude) - _magRank(a.magnitude));
  const negativeSectors = sectors.filter(s => s.impact === "negative" && !NON_INVESTABLE.has((s.name ?? "").toLowerCase()))
    .sort((a, b) => _magRank(b.magnitude) - _magRank(a.magnitude));

  // The article's own sectors_affected is the SAME source ai_prediction is
  // generated from — preferred over the event engine's opportunity_sector/
  // risk_sector, which named a non-investable macro bucket from a routine
  // event often enough to contradict ai_prediction's own stated sector
  // (found live: Focus said "Economy" while ai_prediction said "led by
  // IT" — both should trace back to the same signal). Event-engine fields
  // are now only a fallback, and only when they're not themselves a
  // non-investable bucket.
  const evOpportunity = ev?.opportunity_sector && !NON_INVESTABLE.has(ev.opportunity_sector.toLowerCase()) ? ev.opportunity_sector : null;
  const evRisk = ev?.risk_sector && !NON_INVESTABLE.has(ev.risk_sector.toLowerCase()) ? ev.risk_sector : null;
  const focusSector = positiveSectors[0]?.name ?? evOpportunity;
  // Deliberately NOT the same value as focusSector — the second real
  // positive sector when one exists, so this card adds information
  // instead of repeating "Focus" above it.
  const secondaryOpportunity = positiveSectors[1]?.name ?? (evOpportunity && evOpportunity !== focusSector ? evOpportunity : null);
  const highestRisk = negativeSectors[0]?.name ?? evRisk;
  // Only reachable when NOTHING investable exists anywhere — the honest
  // "this is a macro condition, not a stock opportunity" case instead of
  // mislabeling it.
  const macroTheme = !focusSector && ev?.opportunity_sector ? ev.opportunity_sector : null;
  // MIE's live pulse first — it's the same real-time signal Live Market's
  // hero already shows, refreshed every 5 minutes from actual index
  // movement. Falls back to the sector-count derivation only when MIE has
  // no story yet (e.g. very early pre-market), never a fabricated guess.
  const outlook = deriveOutlookFromMie(mieStory?.pulse, mieStory?.confidence)
    ?? deriveOutlook(positiveSectors.length, negativeSectors.length);

  // Three real sources merged, not one — the top event alone often names
  // only 1-2 companies. Deduped by symbol, capped at 4, never padded with
  // anything not backed by a real company record. The third source is the
  // SAME recency-aware engine (event_lifecycle.py via sort_by=active) that
  // now also powers "Companies to Watch" below on this same homepage —
  // added specifically because the first two sources alone regularly
  // produced just a single real company on a quiet day, and hardcoding
  // extras was never the right fix for that.
  const evCompanies = ev ? ev.companies.map((c: any) => ({ symbol: c.symbol, name: c.name, impact: "positive" as const })) : [];
  const briefCompanies = ((brief.companies_affected ?? []) as any[])
    .filter(c => c.impact === "positive" || c.impact === "negative")
    .map(c => ({ symbol: c.symbol, name: c.name, impact: c.impact as "positive" | "negative" }));
  const activeEventsList = ((activeForWatch as any)?.results ?? (activeForWatch as any) ?? []) as any[];
  const activeCompanies = activeEventsList.flatMap(e =>
    (e.companies ?? []).map((c: any) => ({ symbol: c.symbol, name: c.name, impact: (c.impact ?? "").toLowerCase() === "negative" ? "negative" as const : "positive" as const }))
  );
  const seenSymbols = new Set<string>();
  const companies = [...evCompanies, ...briefCompanies, ...activeCompanies].filter(c => {
    if (!isRealCompanySymbol(c.symbol) || seenSymbols.has(c.symbol)) return false;
    seenSymbols.add(c.symbol);
    return true;
  }).slice(0, 4);

  const changes = (ex.yesterday_changes ?? []) as { name: string; delta: number; direction: string; is_new?: boolean }[];
  const storyTitle = ev ? ev.title : brief.headline;
  // ev.why_it_matters is frequently empty for routine compliance-filing
  // events; the SAME api/homepage/intelligence response also carries a
  // real summary for that exact event in top_events (which the events
  // engine's own /events page already surfaces) — matched by id here
  // rather than left unused, so a real explanation shows instead of a
  // blank subtitle. Never fabricated text, just a different real field
  // from the same response.
  const matchedEvent = ev ? (ex.event?.top_events ?? []).find((e: any) => e.id === ev.id) : null;
  const storySummary = ev ? (ev.why_it_matters || matchedEvent?.summary) : brief.executive_summary;

  // Today's Drivers — real market_data_service fields, same endpoint the
  // homepage ticker strip already fetches. find() returns undefined (not
  // a crash) if a given instrument is missing from a given day's feed —
  // each driver row is skipped individually rather than showing a fake one.
  // Ordered FII → US Futures → Crude → USD/INR (importance to Indian
  // equity flows first, per feedback).
  const usFut = (pm.us_futures ?? [])[0];
  const crude = (pm.commodities ?? []).find((c: any) => (c.name ?? "").toLowerCase().includes("crude"));
  const usdInr = (pm.currencies ?? []).find((c: any) => (c.name ?? "").toUpperCase() === "USD/INR");
  const fiiDii = pm.fii_dii;
  const drivers = [
    fiiDii?.available && { label: "FII", value: fiiDii.fii_net >= 0 ? "Buying" : "Selling", positive: fiiDii.fii_net >= 0 },
    usFut && { label: "US Futures", value: usFut.positive ? "Positive" : "Negative", positive: usFut.positive },
    crude && { label: "Crude", value: crude.positive ? "Rising" : "Falling", positive: !crude.positive },
    usdInr && { label: "USD/INR", value: usdInr.positive ? "INR Weaker" : "INR Stronger", positive: !usdInr.positive },
  ].filter(Boolean) as { label: string; value: string; positive: boolean }[];

  // High/Medium/Low — an honest bucketing of the real confidence score,
  // not a second independent metric. Shown inside "Today's AI Action"
  // alongside the same directional outlook rendered at the top.
  const convictionStrength = marketConfPct == null ? null : marketConfPct >= 75 ? "High" : marketConfPct >= 50 ? "Medium" : "Low";

  const liveEventCount = ex.event?.top_events?.length ?? 0;
  const opportunityCount = (radar as any)?.total ?? 0;

  // A risk card that just says "—" tells the user nothing — an explicit,
  // honest statement that no negative-impact sector cleared the bar today
  // is real information, not a gap. Never invents a specific risk that
  // isn't backed by a real negative sector.
  const highestRiskDisplay = highestRisk ?? "No major verified market risk detected today";

  // Weekend Intelligence Phase 0 (see audit doc): whether the morning brief
  // is actually from today's IST calendar date, and — when it isn't — what
  // to honestly call the day it's from ("Friday's Close" over a weekend,
  // same idea as engine.py's session_label_for on the backend). This never
  // hides brief/mieStory content; Friday's read is real, useful data. It
  // only changes whether the UI is allowed to call it "Today's".
  const WEEKDAY_NAMES = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
  const briefSession = (() => {
    if (!brief.published_at) return { isCurrent: true, weekday: null as string | null };
    const nowIst = new Date(Date.now() + 5.5 * 3600_000);
    const dIst = new Date(new Date(brief.published_at).getTime() + 5.5 * 3600_000);
    const sameDay = nowIst.getUTCFullYear() === dIst.getUTCFullYear()
      && nowIst.getUTCMonth() === dIst.getUTCMonth()
      && nowIst.getUTCDate() === dIst.getUTCDate();
    return { isCurrent: sameDay, weekday: WEEKDAY_NAMES[dIst.getUTCDay()] };
  })();
  // mieStory now carries its own is_current/session_label from
  // engine.py::read_story() — the top verdict badge should defer to that
  // when it disagrees with the brief (MIE refreshes every 5 min and is the
  // more current of the two signals), falling back to the brief's own
  // staleness when MIE has no story yet.
  const heroIsCurrent = mieStory?.is_current ?? briefSession.isCurrent;
  const heroDayLabel = !heroIsCurrent ? (mieStory?.session_label?.replace(/'s Close$/, "") ?? briefSession.weekday) : null;

  // "Updated 17h ago" reads as stale for a page titled "Today's Market
  // Outlook" even when the underlying content genuinely hasn't changed —
  // shows the real IST time when the brief is from today, falls back to
  // an honest "{Weekday}'s Close" label (not a vague relative age) when
  // it's from an earlier trading session.
  const heroFreshnessLabel = (() => {
    if (!brief.published_at) return null;
    if (briefSession.isCurrent) {
      const dIst = new Date(new Date(brief.published_at).getTime() + 5.5 * 3600_000);
      const h = dIst.getUTCHours(), h12 = h % 12 === 0 ? 12 : h % 12, m = dIst.getUTCMinutes().toString().padStart(2, "0");
      return `Updated today at ${h12}:${m} ${h >= 12 ? "PM" : "AM"} IST`;
    }
    return `${briefSession.weekday}'s Close — ${timeAgo(brief.published_at)}`;
  })();

  // Today's Summary — a template composed entirely from real fields
  // already derived above (outlook, focusSector/macroTheme, the same
  // honest risk fallback, ai_prediction) — not a new LLM call, not
  // invented. Each clause is only included when its underlying field is
  // real; capped at 50 words per the explicit ask. "today" only appears
  // when the underlying data actually is from today — otherwise it names
  // the real day the data reflects, same principle as the heading above.
  const todaysSummary = (() => {
    const parts: string[] = heroIsCurrent
      ? [`Markets look ${outlook.label.toLowerCase()} today${marketConfPct != null ? ` with ${marketConfPct}% confidence` : ""}.`]
      : [`As of ${heroDayLabel}'s close, markets looked ${outlook.label.toLowerCase()}${marketConfPct != null ? ` with ${marketConfPct}% confidence` : ""}.`];
    if (focusSector) parts.push(heroIsCurrent ? `${focusSector} stands out as the biggest opportunity.` : `${focusSector} stood out as the biggest opportunity.`);
    else if (macroTheme) parts.push(heroIsCurrent ? `${macroTheme} is the dominant macro theme today.` : `${macroTheme} was the dominant macro theme.`);
    parts.push(highestRisk
      ? `Watch ${highestRisk} as the key risk area.`
      : (heroIsCurrent ? `No major verified risk stands out today.` : `No major verified risk stood out.`));
    if (ex.ai_prediction) parts.push(ex.ai_prediction);
    const words = parts.join(" ").split(/\s+/);
    return words.length > 50 ? words.slice(0, 50).join(" ") + "…" : words.join(" ");
  })();

  return (
    <div className="rounded-[24px] border border-surface-border/7 bg-gradient-to-br from-surface-card to-surface-bg p-6 md:p-7">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="flex items-center gap-2 text-[11px] font-bold uppercase tracking-[0.16em] text-violet-400">
            <Sparkles className="h-3.5 w-3.5" /> {greeting()}
          </p>
          <h1 className="mt-1 text-[22px] font-black leading-tight text-text-primary md:text-[26px]">
            {heroIsCurrent ? "Today's Market Outlook" : `${heroDayLabel}'s Market Outlook`}
          </h1>
          {/* Status strip — real counts only, no "N min ago" copy of what's
              already in the footer timestamp; this is the "feels alive" row. */}
          <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[10.5px] text-text-muted">
            {heroFreshnessLabel && <span>{heroFreshnessLabel}</span>}
            {liveEventCount > 0 && <span>· {liveEventCount} live events</span>}
            {opportunityCount > 0 && <span>· {opportunityCount} active opportunities</span>}
            {positiveSectors.length > 0 && <span>· {positiveSectors.length} sectors strengthening</span>}
          </div>
        </div>
        <div className="text-right">
          <p className="text-[9px] font-bold uppercase tracking-[0.14em] text-text-muted">Market Conviction</p>
          <span className={`mt-1 inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[13px] font-bold ${outlook.cls}`}>
            <span className={`h-1.5 w-1.5 rounded-full ${outlook.dot}`} /> {outlook.label}
          </span>
          {marketConfPct != null && (
            <div className="mt-1.5 flex items-center justify-end gap-1.5">
              <div className="h-1.5 w-16 overflow-hidden rounded-full bg-text-primary/[0.08]">
                <div className="h-full rounded-full bg-accent-violet" style={{ width: `${marketConfPct}%` }} />
              </div>
              <span className="text-[11px] font-bold tabular-nums text-text-primary">{marketConfPct}%</span>
            </div>
          )}
          {/* Evidence behind the conviction label, not just the label
              itself — real counts already computed above. */}
          <p className="mt-1 text-[10px] text-text-muted">{positiveSectors.length} positive · {negativeSectors.length} negative signals</p>
        </div>
      </div>

      <div className="mt-5 grid grid-cols-1 gap-5 lg:grid-cols-2">
        {/* LEFT — Decision. AI Action leads: users care more about "what
            should I do" than "what happened" — the story/evidence moved
            to the right column entirely. */}
        <div className="space-y-4">
          {(focusSector || macroTheme || highestRisk) && (
            <div className="rounded-[18px] border border-surface-border/10 bg-gradient-to-br from-text-primary/[0.05] to-transparent p-5">
              <p className="mb-3 text-[10px] font-bold uppercase tracking-[0.16em] text-text-secondary">Today&apos;s AI Action</p>
              <div className="grid grid-cols-2 gap-4 text-[13px]">
                {focusSector ? (
                  <div><span className="text-[10px] uppercase tracking-wide text-text-muted">Focus</span><p className="mt-0.5 text-[19px] font-black text-emerald-600 dark:text-emerald-300">{focusSector}</p></div>
                ) : macroTheme ? (
                  <div><span className="text-[10px] uppercase tracking-wide text-text-muted">Macro Theme</span><p className="mt-0.5 text-[19px] font-black text-emerald-600 dark:text-emerald-300">{macroTheme}</p></div>
                ) : null}
                <div><span className="text-[10px] uppercase tracking-wide text-text-muted">Avoid</span><p className="mt-0.5 text-[15px] font-black leading-snug text-rose-600 dark:text-rose-300">{highestRiskDisplay}</p></div>
                <div className="col-span-2 flex items-center justify-between border-t border-surface-border/8 pt-3">
                  <span className="text-[10px] uppercase tracking-wide text-text-muted">Market Conviction</span>
                  <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[12px] font-bold ${outlook.cls}`}>
                    <span className={`h-1.5 w-1.5 rounded-full ${outlook.dot}`} /> {convictionStrength ?? outlook.label}
                  </span>
                </div>
              </div>
            </div>
          )}

          {ex.ai_prediction && focusSector && (
            <div className="rounded-[16px] border border-violet-500/15 bg-violet-500/[0.06] p-4">
              <p className="mb-1 text-[9px] font-bold uppercase tracking-[0.14em] text-violet-600 dark:text-violet-300">AI Market Call</p>
              <p className="text-[16px] font-black leading-snug text-text-primary">Overweight {focusSector}</p>
              <p className="mt-1.5 text-[12px] leading-5 text-text-secondary"><span className="text-text-muted">Driven by —</span> {ex.ai_prediction}</p>
              {/* Today's Summary — same underlying signal as the call
                  above (outlook / focus / risk / ai_prediction), composed
                  into one retail-readable paragraph, capped at 50 words. */}
              <p className="mt-2.5 border-t border-surface-border/8 pt-2.5 text-[11.5px] leading-relaxed text-text-secondary">{todaysSummary}</p>
            </div>
          )}

          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-[14px] border border-emerald-500/15 bg-emerald-500/[0.05] p-3.5">
              <p className="text-[9px] font-bold uppercase tracking-[0.12em] text-emerald-400">🔥 Biggest Opportunity</p>
              <p className="mt-1 text-[14px] font-bold text-text-primary">{secondaryOpportunity ?? "No second opportunity signal today"}</p>
            </div>
            <div className="rounded-[14px] border border-rose-500/15 bg-rose-500/[0.05] p-3.5">
              <p className="text-[9px] font-bold uppercase tracking-[0.12em] text-rose-400">⚠ Biggest Risk</p>
              <p className="mt-1 text-[13px] font-bold leading-snug text-text-primary">{highestRiskDisplay}</p>
            </div>
          </div>
        </div>

        {/* RIGHT — Evidence */}
        <div className="space-y-4">
          <Link href={ev ? `/events/${ev.slug || ev.id}` as any : "/events"} className="block rounded-[16px] border border-surface-border/6 bg-text-primary/[0.02] p-4 transition hover:border-violet-500/25">
            <div className="mb-1 flex items-center justify-between">
              <p className="text-[9px] font-bold uppercase tracking-[0.14em] text-text-muted">Why Today Matters</p>
              {ev?.lifecycle && _LIFECYCLE_BADGE[ev.lifecycle] && (
                <span className={`rounded-full px-1.5 py-0.5 text-[8px] font-black uppercase ${_LIFECYCLE_BADGE[ev.lifecycle]}`}>{ev.lifecycle}</span>
              )}
            </div>
            <p className="text-[15px] font-semibold leading-snug text-text-primary">{expandAcronyms(cleanText(storyTitle))}</p>
            {storySummary && (
              <p className="mt-1.5 line-clamp-2 text-[12px] leading-5 text-text-secondary">{cleanText(storySummary)}</p>
            )}
            <div className="mt-2 flex items-center gap-1.5 text-[11px] text-text-muted">
              <span>Expected Market Impact</span> <Stars n={stars} />
            </div>
          </Link>

          {drivers.length > 0 && (
            <div className="rounded-[16px] border border-surface-border/6 bg-text-primary/[0.02] p-4">
              <p className="mb-2 text-[9px] font-bold uppercase tracking-[0.14em] text-text-muted">Today&apos;s Drivers</p>
              <div className="flex flex-wrap gap-1.5">
                {drivers.map((d, i) => (
                  <span key={i} className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-semibold ${
                    d.positive ? "border-emerald-500/20 bg-emerald-500/[0.06] text-emerald-600 dark:text-emerald-300" : "border-rose-500/20 bg-rose-500/[0.06] text-rose-600 dark:text-rose-300"
                  }`}>
                    {d.positive ? "🟢" : "🔴"} {d.label} <span className="text-text-secondary font-normal">{d.value}</span>
                  </span>
                ))}
              </div>
            </div>
          )}

          {companies.length > 0 && (
            <div className="rounded-[16px] border border-surface-border/6 bg-text-primary/[0.02] p-4">
              <p className="mb-2 text-[9px] font-bold uppercase tracking-[0.14em] text-text-muted">Stocks To Watch</p>
              {/* impact is an AI event-impact call ("this catalyst helps/hurts
                  this company"), not a live price quote — found live: it can
                  read "positive" while the stock is actually trading down for
                  unrelated reasons, and a bare ▲/▼ arrow reads exactly like a
                  price-ticker direction to anyone market-literate, creating a
                  false "the site contradicts itself" impression. Labeled
                  "Bullish/Bearish Catalyst" instead of an arrow so it's
                  unambiguous this is an assessment, not today's price move. */}
              <div className="grid grid-cols-2 gap-2">
                {companies.map((c: any, i: number) => (
                  <Link key={i} href={`/companies/${c.symbol}` as any}
                    title={c.impact === "positive" ? "AI-assessed positive catalyst — not today's live price" : "AI-assessed negative catalyst — not today's live price"}
                    className={`flex flex-col justify-between rounded-[10px] border px-2.5 py-1.5 text-[11.5px] font-semibold transition hover:opacity-80 ${
                      c.impact === "positive" ? "border-emerald-500/25 bg-emerald-500/10 text-emerald-600 dark:text-emerald-300" : "border-rose-500/25 bg-rose-500/10 text-rose-600 dark:text-rose-300"
                    }`}>
                    <span>{cleanText(c.symbol || c.name)}</span>
                    <span className="text-[9px] font-bold uppercase tracking-wide opacity-80">{c.impact === "positive" ? "Bullish Catalyst" : "Bearish Catalyst"}</span>
                  </Link>
                ))}
              </div>
            </div>
          )}

          <div className="rounded-[16px] border border-surface-border/6 bg-text-primary/[0.02] p-4">
            <p className="mb-2 text-[9px] font-bold uppercase tracking-[0.14em] text-text-muted">What Changed Since Yesterday</p>
            {changes.length === 0 ? (
              <p className="text-[11px] text-text-muted">Not enough history yet — check back tomorrow.</p>
            ) : (
              <ul className="space-y-1.5">
                {changes.map((c, i) => (
                  <li key={i} className="flex items-center gap-2 text-[12px] font-medium">
                    <span className={c.direction === "up" ? "text-emerald-400" : "text-rose-400"}>{c.direction === "up" ? "↑" : "↓"}</span>
                    <span className="text-text-primary">{c.name}</span>
                    {c.is_new ? (
                      <span className="text-[10px] font-normal text-text-muted">newly in focus today</span>
                    ) : (
                      <>
                        <span className={c.direction === "up" ? "text-emerald-400" : "text-rose-400"}>{c.direction === "up" ? "+" : ""}{c.delta}</span>
                        <span className="ml-auto flex gap-0.5">
                          {Array.from({ length: 4 }).map((_, di) => (
                            <span key={di} className={`h-1.5 w-1.5 rounded-full ${di < deltaStrength(c.delta) ? (c.direction === "up" ? "bg-emerald-400" : "bg-rose-400") : "bg-text-primary/10"}`} />
                          ))}
                        </span>
                      </>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>

      <div className="mt-5 flex items-center justify-between border-t border-surface-border/6 pt-4">
        {brief.published_at && <span className="text-[10px] text-text-muted">{briefTimeLabel(brief.published_at)}</span>}
        <Link href="/newsroom/daily-brief"
          className="inline-flex items-center gap-1.5 rounded-full bg-accent-violet px-4 py-2 text-[11px] font-bold text-text-primary transition hover:opacity-90">
          Read Today&apos;s Market Brief <ArrowRight className="h-3 w-3" />
        </Link>
      </div>
    </div>
  );
}

function _magRank(m: string): number {
  return m === "high" ? 3 : m === "medium" ? 2 : m === "low" ? 1 : 0;
}

// ═══════════════════════════════════════════════════════════════════════════════
// LIVE INTELLIGENCE (Phase 3, Priority 2) — the "why this matters" stream,
// not a news feed. See live_intelligence.py's module docstring for exactly
// which real signal backs each of these 4 card types.
// ═══════════════════════════════════════════════════════════════════════════════
const _LI_META: Record<string, { label: string; icon: React.ReactNode; cls: string }> = {
  anomaly:           { label: "Intelligence Detection", icon: <Radar className="h-3.5 w-3.5" />,     cls: "text-violet-600 dark:text-violet-300 border-violet-500/25 bg-violet-500/[0.08]" },
  policy_ripple:     { label: "Policy Intelligence",     icon: <GitBranch className="h-3.5 w-3.5" />, cls: "text-sky-600 dark:text-sky-300 border-sky-500/25 bg-sky-500/[0.08]" },
  early_theme:       { label: "Emerging Theme",          icon: <Rocket className="h-3.5 w-3.5" />,    cls: "text-emerald-600 dark:text-emerald-300 border-emerald-500/25 bg-emerald-500/[0.08]" },
  historical_match:  { label: "Pattern Detected",        icon: <History className="h-3.5 w-3.5" />,   cls: "text-amber-600 dark:text-amber-300 border-amber-500/25 bg-amber-500/[0.08]" },
};

// Every card links to its own permanent /intelligence/signal/{slug} page
// (homepage audit, Priority 1 — signal_publisher.py persists one on every
// cache-miss feed rebuild). The card itself stays a plain div with a full-
// cover overlay <Link> (the "stretched link" pattern) rather than wrapping
// everything in one <a>, so the company chips below can remain their own
// real, separately-navigable links — nesting an <a> inside an <a> is
// invalid HTML and would swallow those clicks.
function LiveIntelligenceCard({ item }: { item: any }) {
  const meta = _LI_META[item.type];
  if (!meta) return null;
  const href = item.slug ? `/intelligence/signal/${item.slug}` : null;

  return (
    <div className="group relative flex h-full flex-col rounded-[18px] border border-surface-border/7 bg-text-primary/[0.02] p-4 transition hover:border-violet-500/25">
      {href && (
        // SEO fix: this stretched-link pattern (see comment above) previously
        // shipped as a self-closing <a> with only an aria-label — accessible
        // to screen readers, but crawlers weight visible anchor text far more
        // than aria-label, and this <a> had none. An sr-only span gives it
        // real text content without touching the visual "invisible overlay"
        // behavior or aria-label (which still controls the announced name).
        <Link href={href as any} className="absolute inset-0 z-0 rounded-[18px]" aria-label={`View full intelligence: ${cleanText(item.headline)}`}>
          <span className="sr-only">{cleanText(item.headline)}</span>
        </Link>
      )}
      <div className="pointer-events-none relative z-10 flex h-full flex-col">
        <div className="flex flex-wrap items-center gap-1.5">
          <span className={`inline-flex w-fit items-center gap-1.5 rounded-full border px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider ${meta.cls}`}>
            {meta.icon} {meta.label}
          </span>
          {item.is_fallback ? (
            <span className="inline-flex items-center rounded-full border border-surface-border/10 bg-text-primary/[0.03] px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider text-text-muted">
              Recurring, not today
            </span>
          ) : item.detected_at ? (
            <span className="text-[9.5px] text-text-muted">{timeAgo(item.detected_at)}</span>
          ) : null}
        </div>
        <p className="mt-2.5 text-[13.5px] font-semibold leading-snug text-text-primary transition group-hover:text-violet-700 dark:text-violet-200">{cleanText(item.headline)}</p>

        {item.type === "anomaly" && (
          <>
            {item.why_it_matters && <p className="mt-1.5 line-clamp-2 text-[11.5px] leading-5 text-text-secondary">Why this matters: {cleanText(item.why_it_matters)}</p>}
            {item.similarity != null && <p className="mt-1.5 text-[10px] text-text-muted">Historical similarity <span className="font-bold text-text-primary">{Math.round(item.similarity)}%</span></p>}
          </>
        )}

        {item.type === "policy_ripple" && item.path?.length > 0 && (
          <div className="mt-2 flex flex-wrap items-center gap-1 text-[11px] text-text-secondary">
            {item.path.map((p: string, i: number) => (
              <span key={i} className="flex items-center gap-1">
                {i > 0 && <ArrowRight className="h-2.5 w-2.5 text-text-muted" />}
                <span className="rounded-full border border-surface-border/10 bg-text-primary/[0.03] px-2 py-0.5">{cleanText(p)}</span>
              </span>
            ))}
          </div>
        )}

        {item.type === "early_theme" && (
          <div className="mt-2 flex items-center gap-4 text-[11px]">
            <span className="text-text-muted">Stage <span className="font-bold text-emerald-400">Early</span></span>
            {item.opportunity_score != null && <span className="text-text-muted">Opportunity Score <span className="font-bold text-text-primary">{item.opportunity_score}</span></span>}
          </div>
        )}

        {item.type === "historical_match" && (
          <>
            {item.similarity != null && <p className="mt-1.5 text-[10px] text-text-muted">Similarity <span className="font-bold text-text-primary">{Math.round(item.similarity)}%</span></p>}
            {item.key_lesson && <p className="mt-1 line-clamp-2 text-[11px] leading-5 text-text-secondary">{cleanText(item.key_lesson)}</p>}
            <div className="pointer-events-auto mt-1.5 flex flex-wrap gap-x-2 gap-y-1 text-[10.5px]">
              {(item.winners ?? []).slice(0, 3).map((w: string, i: number) => (
                <Link key={`w${i}`} href={`/companies/${w}` as any} className="text-emerald-400 hover:text-emerald-600 dark:text-emerald-300 hover:underline">▲ {w}</Link>
              ))}
              {(item.losers ?? []).slice(0, 2).map((l: string, i: number) => (
                <Link key={`l${i}`} href={`/companies/${l}` as any} className="text-rose-400 hover:text-rose-600 dark:text-rose-300 hover:underline">▼ {l}</Link>
              ))}
            </div>
          </>
        )}

        {item.companies?.length > 0 && (
          <div className="pointer-events-auto mt-auto flex flex-wrap gap-1 pt-2.5">
            {item.companies.slice(0, 5).map((c: string | { symbol: string; impact?: string | null }, i: number) => {
              // anomaly/early_theme/policy_ripple items carry a real
              // per-company impact (EventTriage direction or a theme's
              // live change_pct — see live_intelligence.py) when one
              // genuinely exists; grey is the honest default otherwise,
              // never a guessed color. Plain-string entries (older cached
              // shape) fall back to the same grey.
              const symbol = typeof c === "string" ? c : c.symbol;
              const impact = typeof c === "string" ? null : c.impact;
              const cls = impact === "positive"
                ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-600 dark:text-emerald-300 hover:border-emerald-500/50"
                : impact === "negative"
                ? "border-rose-500/30 bg-rose-500/10 text-rose-600 dark:text-rose-300 hover:border-rose-500/50"
                : "border-surface-border/10 bg-text-primary/[0.03] text-text-secondary hover:border-violet-500/30 hover:text-violet-600 dark:hover:text-violet-300";
              return (
                <Link key={i} href={`/companies/${symbol}` as any}
                  className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold transition ${cls}`}>
                  {impact === "positive" ? "▲ " : impact === "negative" ? "▼ " : ""}{symbol}
                </Link>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

async function LiveIntelligenceSection() {
  const data = await getLiveIntelligenceItems();
  const items = (data as any)?.items ?? [];
  if (items.length === 0) return null;

  return (
    <div>
      <div className="mb-3 flex items-center gap-2">
        <Sparkles className="h-4 w-4 text-violet-400" />
        <h2 className="text-[15px] font-black text-text-primary">Live Intelligence</h2>
        <span className="text-[11px] text-text-muted">— Ripple Signals</span>
      </div>
      <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-2 lg:grid-cols-4">
        {items.map((item: any, i: number) => <LiveIntelligenceCard key={i} item={item} />)}
      </div>
    </div>
  );
}

const _LIFECYCLE_BADGE: Record<string, string> = {
  LIVE: "bg-rose-500/15 text-rose-400",
  Developing: "bg-amber-500/15 text-amber-400",
  Active: "bg-sky-500/15 text-sky-400",
};

// Why a card is ranked where it is — the Latest Biggest Events Engine's
// own lifecycle + position, translated into one glanceable line, per the
// user's explicit ask: "users instantly understand why they're seeing
// that event." Historical items (most common in this dev dataset — see
// event_lifecycle.py) fall back to their real rank number rather than a
// fabricated "trending" claim.
function _rankReason(lifecycle: string | undefined, rank: number): { emoji: string; text: string } {
  if (lifecycle === "LIVE") return { emoji: "🔴", text: "Live Now" };
  if (lifecycle === "Developing") return { emoji: "📈", text: "Developing" };
  if (lifecycle === "Active") return { emoji: "🟡", text: "Active" };
  return { emoji: "📌", text: `#${rank} Today` };
}

async function TodaysBiggestEventsCard() {
  // Recency-aware ranking (event_lifecycle.py) — see its module docstring
  // for the bug this replaced: pure impact_score sorting let month-old
  // events (e.g. a June RBI meeting) permanently outrank genuinely current
  // ones. The backend already applies the 7→14→30-day progressive window
  // and only falls back to real Historical events as an explicit last
  // resort, so this component just renders what it's given.
  //
  // #1 is deliberately skipped here — it's already the homepage hero's
  // "Today's Biggest Story" (same engine, same event), so repeating it
  // in this list would just be the same story twice.
  const recentRaw = await getActiveEvents();
  const events = ((recentRaw as any)?.results ?? (recentRaw as any) ?? []) as any[];

  const seen = new Set<string>();
  const items: any[] = [];
  for (const e of events) {
    if (!e.id || seen.has(e.id)) continue;
    seen.add(e.id);
    items.push(e);
  }
  const rest = items.slice(1, 4);

  return (
    <div className="flex h-full flex-col rounded-2xl border border-surface-border/7 bg-surface-card p-5">
      <CardHeader title="Other Major Events" href="/events" />
      {rest.length === 0 ? (
        <p className="flex-1 py-6 text-center text-[12px] text-text-muted">No other scored events available right now.</p>
      ) : (
        <div className="flex-1 space-y-3">
          {rest.map((e, idx) => {
            const style = impactToStyle(e.impact_score);
            const sectors = (e.sectors ?? []) as string[];
            const companies = (e.companies ?? []) as { symbol: string; name: string; impact: string }[];
            const reason = _rankReason(e.lifecycle, idx + 2);
            return (
              <div key={e.id} className="rounded-[16px] border border-surface-border/6 bg-text-primary/[0.02] p-3.5">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-1.5">
                    <span className="rounded-full border border-surface-border/10 bg-text-primary/[0.03] px-1.5 py-0.5 text-[8px] font-black text-text-secondary">
                      {reason.emoji} {reason.text}
                    </span>
                    <span className={`rounded-full border px-1.5 py-0.5 text-[8px] font-black uppercase tabular-nums ${style.circle}`}>
                      {style.label} Impact
                    </span>
                  </div>
                  <span className="shrink-0 text-[11px] font-black tabular-nums text-text-secondary">
                    {e.impact_score != null ? Math.round(e.impact_score) : "—"}
                  </span>
                </div>
                <Link href={`/events/${e.slug || e.id}` as any} className="group mt-1.5 block">
                  <p className="text-[13px] font-bold leading-snug text-text-primary group-hover:text-violet-700 dark:text-violet-200 transition line-clamp-2">{cleanText(e.title)}</p>
                </Link>
                {sectors.length > 0 && (
                  <p className="mt-1.5 text-[10.5px] text-text-muted">{sectors.slice(0, 3).join(" • ")}</p>
                )}
                {companies.length > 0 && (
                  <div className="mt-1.5 flex flex-wrap gap-1">
                    {companies.slice(0, 5).map((c, i) => (
                      <Link key={i} href={`/companies/${c.symbol}` as any}
                        className={`rounded-full border px-1.5 py-0.5 text-[9.5px] font-semibold transition hover:opacity-80 ${
                          c.impact === "Positive" ? "border-emerald-500/25 bg-emerald-500/10 text-emerald-600 dark:text-emerald-300"
                          : c.impact === "Negative" ? "border-rose-500/25 bg-rose-500/10 text-rose-600 dark:text-rose-300"
                          : "border-surface-border/10 bg-text-primary/[0.03] text-text-secondary"
                        }`}>
                        {c.symbol || c.name}
                      </Link>
                    ))}
                  </div>
                )}
                {/* Only 3 quick actions — dedicated destinations for
                    "Impacted Companies" / "Opportunities" / "Historical
                    Similar Events" as separate views don't exist yet, and
                    a broken/placeholder link is worse than not having it. */}
                <div className="mt-2.5 flex items-center gap-3 border-t border-surface-border/5 pt-2">
                  <Link href={`/ai-search?q=${encodeURIComponent(`What are the investment implications of: ${truncateForQuery(e.title)}`)}` as any} className="text-[10px] font-semibold text-violet-400 hover:text-violet-600 dark:text-violet-300 transition">Analyze with AI →</Link>
                  <Link href={`/ripple?event=${e.id}` as any} className="text-[10px] font-semibold text-sky-400 hover:text-sky-600 dark:text-sky-300 transition">Ripple Analysis →</Link>
                  <Link href={`/events/${e.slug || e.id}` as any} className="text-[10px] font-semibold text-text-muted hover:text-text-secondary transition">Full Event Analysis →</Link>
                  {e.confidence != null && <span className="ml-auto text-[10px] text-text-muted">Confidence <span className="font-bold text-text-secondary">{Math.round(e.confidence)}%</span></span>}
                </div>
              </div>
            );
          })}
        </div>
      )}
      <Link href="/events" className="mt-4 text-center text-[11px] font-semibold text-text-muted hover:text-text-secondary transition">
        View All Events →
      </Link>
    </div>
  );
}

async function MarketSnapshotCard() {
  const [liveData, session] = await Promise.all([getLive(), getSession()]);
  const sectors = ((liveData as any)?.sectors ?? []) as any[];
  const isOpen = session?.is_open;

  return (
    <div className="flex h-full flex-col rounded-2xl border border-surface-border/7 bg-surface-card p-5">
      <CardHeader
        title="Market Snapshot"
        badge={
          <span className="flex items-center gap-1.5 text-[10px] font-bold text-emerald-400">
            <span className={`h-1.5 w-1.5 rounded-full ${isOpen ? "bg-emerald-400 animate-pulse" : "bg-slate-600"}`} />
            {isOpen ? "Live" : "Closed"}
          </span>
        }
      />
      {sectors.length === 0 ? (
        <p className="flex-1 py-6 text-center text-[12px] text-text-muted">Sector data unavailable.</p>
      ) : (
        <div className="grid flex-1 grid-cols-2 gap-2 content-start sm:grid-cols-3">
          {sectors.map((s: any) => (
            <div key={s.id ?? s.name} className={`flex flex-col justify-center rounded-xl p-3 ${s.positive ? "bg-emerald-500/15" : "bg-rose-500/15"}`}>
              <p className={`text-[9px] font-black uppercase tracking-wide leading-tight ${s.positive ? "text-emerald-600 dark:text-emerald-300" : "text-rose-600 dark:text-rose-300"}`}>{s.name}</p>
              <p className={`mt-1 text-[13px] font-black tabular-nums ${s.positive ? "text-emerald-400" : "text-rose-400"}`}>{s.value}</p>
            </div>
          ))}
        </div>
      )}
      <div className="mt-4 flex items-center gap-4 text-[10px] text-text-muted">
        <span className="flex items-center gap-1"><span className="h-1.5 w-1.5 rounded-full bg-emerald-400" /> Top Gainers</span>
        <span className="flex items-center gap-1"><span className="h-1.5 w-1.5 rounded-full bg-rose-400" /> Top Losers</span>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// ROW 2 — Companies to Watch · Top Opportunities · Key Risks · Theme Strength
// ═══════════════════════════════════════════════════════════════════════════════
const AVATAR_GRADIENT = [
  "from-indigo-600 to-indigo-800", "from-sky-600 to-sky-800", "from-emerald-600 to-emerald-800",
  "from-violet-600 to-violet-800", "from-rose-600 to-rose-800", "from-amber-600 to-amber-800",
];

// Today's Watch Score — companies extracted from event_lifecycle.py's own
// recency-aware ranking (the sort_by=active pool, real active_score
// already applying its own progressive 7→14→30-day decay window), not the
// plain impact_score pool. Previously sorted by raw impact_score with no
// recency factor at all, so a handful of weeks-old high-score seed events
// (94/91/87/83, dated back to June) permanently outranked anything
// current — the same company names (Dixon, Kaynes, BEL, HAL, Bharat
// Forge) showed up unchanged for days. A second, independent decay
// formula layered on top of that same stale pool doesn't fix it — the
// pool itself was wrong; the real recency-ranked engine already exists
// and is used two cards over on this same page.
function _watchFreshness(dateStr: string | null | undefined, lifecycle: string | undefined): string {
  if (lifecycle === "LIVE") return "New today";
  if (!dateStr) return "Still relevant";
  const hoursAgo = (Date.now() - new Date(dateStr).getTime()) / 3_600_000;
  if (hoursAgo >= 0 && hoursAgo <= 24) return `Updated ${Math.max(1, Math.round(hoursAgo))}h ago`;
  return "Still relevant";
}

async function CompaniesToWatchTable() {
  const activeRaw = await getActiveEventsForWatch();
  const events = ((activeRaw as any)?.results ?? (activeRaw as any) ?? []) as any[];

  const seen = new Set<string>();
  const rows: { ticker: string; name: string; reason: string; score: number | null; freshness: string }[] = [];
  outer:
  for (const e of events) {
    for (const c of (e.companies ?? [])) {
      if (!isRealCompanySymbol(c.symbol) || seen.has(c.symbol)) continue;
      seen.add(c.symbol);
      rows.push({ ticker: c.symbol, name: c.name ?? c.symbol, reason: e.title, score: e.impact_score ?? null, freshness: _watchFreshness(e.date, e.lifecycle) });
      if (rows.length >= 5) break outer;
    }
  }

  return (
    <div className="flex h-full flex-col rounded-2xl border border-surface-border/7 bg-surface-card p-5">
      <CardHeader title="Companies to Watch" href="/companies" />
      {rows.length === 0 ? (
        <p className="flex-1 py-6 text-center text-[12px] text-text-muted">No high-relevance company signals right now.</p>
      ) : (
        <div className="flex-1">
          <div className="mb-1.5 grid grid-cols-[1fr_44px] gap-2 text-[8px] font-bold uppercase tracking-wider text-text-muted">
            <span>Company · Reason</span>
            <span className="text-right">Score</span>
          </div>
          <div className="space-y-2.5">
            {rows.map((r, i) => {
              const style = impactToStyle(r.score);
              return (
                <Link key={r.ticker} href={`/companies/${r.ticker}` as any} className="group grid grid-cols-[1fr_44px] items-center gap-2">
                  <div className="flex min-w-0 items-center gap-2">
                    <div className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br text-[8px] font-black text-text-primary ${AVATAR_GRADIENT[i % 6]}`}>
                      {r.ticker.slice(0, 2)}
                    </div>
                    <div className="min-w-0">
                      <p className="truncate text-[11px] font-bold text-text-primary group-hover:text-violet-700 dark:text-violet-200 transition">{cleanText(r.name)}</p>
                      <p className="truncate text-[9px] text-text-muted">{cleanText(r.reason)} <span className="text-text-muted">· {r.freshness}</span></p>
                    </div>
                  </div>
                  <span className={`text-right text-[12px] font-black tabular-nums ${style.text}`}>
                    {r.score != null ? Math.round(r.score) : "—"}
                  </span>
                </Link>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

async function TopOpportunitiesCard() {
  const radar = await getRadar();
  const items = (((radar as any)?.items ?? []) as any[]).slice(0, 3);

  return (
    <div className="flex h-full flex-col rounded-2xl border border-surface-border/7 bg-surface-card p-5">
      <CardHeader title="Top Opportunities" href="/opportunity-radar" />
      {items.length === 0 ? (
        <p className="flex-1 py-6 text-center text-[12px] text-text-muted">AI is scanning for opportunities.</p>
      ) : (
        <div className="flex-1 space-y-3">
          {items.map((r: any) => (
            <Link key={r.id} href="/opportunity-radar" className="group flex items-start gap-3">
              <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-emerald-500/15">
                <TrendingUp className="h-4 w-4 text-emerald-400" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-[12px] font-bold leading-snug text-text-primary group-hover:text-emerald-700 dark:text-emerald-200 transition line-clamp-1">{cleanText(r.title)}</p>
                <p className="mt-0.5 text-[10px] text-text-muted line-clamp-1">{cleanText(r.summary)}</p>
              </div>
              <span className="shrink-0 rounded-lg border border-emerald-500/25 bg-emerald-500/10 px-2 py-1 text-[11px] font-black tabular-nums text-emerald-400">
                {r.opportunity_score != null ? Math.round(r.opportunity_score) : "—"}
              </span>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

async function KeyRisksCard() {
  // Real structured risks[] from the AIPE Daily Brief — not a second,
  // independently-generated risk narrative from MIE. Same article
  // AIMarketBriefCard uses; cache() means this doesn't double-fetch.
  const brief = await getMorningBrief();
  const risks = (brief?.risks ?? []) as { title: string; description: string; severity?: string }[];

  return (
    <div className="flex h-full flex-col rounded-2xl border border-surface-border/7 bg-surface-card p-5">
      <CardHeader title="Key Risks" href="/newsroom/daily-brief" />
      {risks.length === 0 ? (
        <p className="flex-1 py-6 text-center text-[12px] text-text-muted">No elevated risks in today's brief.</p>
      ) : (
        <div className="flex-1 space-y-3">
          {risks.slice(0, 3).map((r, i) => {
            const level = (r.severity ?? "medium").toLowerCase();
            return (
              <Link key={i} href="/newsroom/daily-brief" className="group flex items-start gap-3">
                <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-rose-500/15">
                  <Building2 className="h-4 w-4 text-rose-400" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-[12px] font-bold leading-snug text-text-primary group-hover:text-rose-700 dark:text-rose-200 transition line-clamp-1">{cleanText(r.title)}</p>
                  <p className="mt-0.5 text-[10px] text-text-muted line-clamp-1">{cleanText(r.description)}</p>
                </div>
                <span className={`shrink-0 text-[11px] font-black ${level === "high" ? "text-rose-400" : "text-amber-400"}`}>
                  {level === "high" ? "High" : level === "low" ? "Low" : "Medium"}
                </span>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}

async function ThemeStrengthCard() {
  // Real Opportunity Engine (/api/radar) — same source and same numbers as
  // Top Opportunities and the AI Newsroom's Theme Intelligence, not MIE's
  // separate sector_themes scoring (which could, and did, disagree).
  const radar = await getRadar();
  const themes = (((radar as any)?.items ?? []) as any[]).slice(0, 5);

  return (
    <div className="flex h-full flex-col rounded-2xl border border-surface-border/7 bg-surface-card p-5">
      <CardHeader title="Theme Strength" href="/newsroom/themes" />
      {themes.length === 0 ? (
        <p className="flex-1 py-6 text-center text-[12px] text-text-muted">Theme data is loading.</p>
      ) : (
        <div className="flex-1 space-y-3">
          {themes.map((t: any) => {
            const score = t.opportunity_score ?? 0;
            const barColor = score >= 75 ? "bg-emerald-500" : score >= 50 ? "bg-sky-500" : score >= 30 ? "bg-amber-500" : "bg-rose-500";
            return (
              <Link key={t.id} href={`/newsroom/themes/${t.slug}`} className="group block">
                <div className="mb-1 flex items-center justify-between">
                  <span className="line-clamp-1 text-[11px] font-semibold text-text-secondary group-hover:text-text-primary transition">{cleanText(t.title)}</span>
                  <span className="shrink-0 text-[11px] font-black tabular-nums text-text-primary">{Math.round(score)}</span>
                </div>
                <div className="h-1.5 w-full overflow-hidden rounded-full bg-text-primary/[0.06]">
                  <div className={`h-full rounded-full ${barColor}`} style={{ width: `${Math.min(100, Math.max(0, score))}%` }} />
                </div>
                <div className="mt-1 flex items-center gap-2 text-[9.5px] text-text-muted">
                  <span>{Math.round((t.confidence ?? 0) * 100)}% confidence</span>
                  {t.risk_level && <span>· {t.risk_level} risk</span>}
                </div>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// SUPPORTING ROW — Key Risks · Market Snapshot · Watch Tomorrow
// ═══════════════════════════════════════════════════════════════════════════════
async function WatchTomorrowCard() {
  const cal = await getCalendar();
  // Calendar dates are day-only ("Jul 21, 2026"), which parse to midnight —
  // comparing against the exact current instant would wrongly exclude
  // today's own events every time. Compare against start-of-day instead.
  const startOfToday = new Date();
  startOfToday.setHours(0, 0, 0, 0);
  const startMs = startOfToday.getTime();
  const items = ((cal ?? []) as any[])
    .filter(e => { try { const d = new Date(e.date ?? e.event_date ?? e.datetime).getTime(); return d >= startMs && d <= startMs + 7 * 86400_000; } catch { return false; } })
    .sort((a: any, b: any) => new Date(a.date ?? a.event_date ?? a.datetime).getTime() - new Date(b.date ?? b.event_date ?? b.datetime).getTime())
    .slice(0, 3);

  return (
    <div className="flex h-full flex-col rounded-2xl border border-surface-border/7 bg-surface-card p-5">
      <CardHeader title="Watch Tomorrow" href="/market-intelligence?tab=live-market" />
      {items.length === 0 ? (
        <p className="flex-1 py-6 text-center text-[12px] text-text-muted">No upcoming events in the next 7 days.</p>
      ) : (
        <div className="flex-1 space-y-3">
          {items.map((e: any) => (
            <div key={e.id} className="flex items-start gap-3">
              <EventIcon title={e.title} category={e.category} />
              <div className="min-w-0 flex-1">
                <p className="text-[12px] font-bold leading-snug text-text-primary line-clamp-1">{e.title}</p>
                <p className="mt-0.5 text-[10px] text-text-muted">{calendarCategoryLabel(e.category)}</p>
              </div>
              <span className="shrink-0 text-[10px] font-semibold text-text-muted">{e.date}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// Same per-type color coding as the article page's TYPE_META (newsroom/
// article/[slug]/page.tsx) — this card grid mixes several article types in
// one row (LIVE SIGNAL, COMPANY INTELLIGENCE, RIPPLE INTELLIGENCE, ...) and
// was rendering all of them as the same flat neutral-gray pill, so the type
// wasn't scannable at a glance the way it is everywhere else this badge
// appears.
const ARTICLE_TYPE_COLOR: Record<string, string> = {
  breaking_intelligence:     "text-rose-600 dark:text-rose-400 border-rose-500/30 bg-rose-500/10",
  live_signal:               "text-rose-600 dark:text-rose-400 border-rose-500/30 bg-rose-500/10",
  morning_intelligence:      "text-amber-600 dark:text-amber-400 border-amber-500/30 bg-amber-500/10",
  market_wrap:               "text-amber-600 dark:text-amber-400 border-amber-500/30 bg-amber-500/10",
  historical_intelligence:   "text-amber-600 dark:text-amber-400 border-amber-500/30 bg-amber-500/10",
  company_intelligence:      "text-sky-600 dark:text-sky-400 border-sky-500/30 bg-sky-500/10",
  weekly_intelligence:       "text-sky-600 dark:text-sky-400 border-sky-500/30 bg-sky-500/10",
  monthly_intelligence:      "text-sky-600 dark:text-sky-400 border-sky-500/30 bg-sky-500/10",
  news_intelligence:         "text-sky-600 dark:text-sky-400 border-sky-500/30 bg-sky-500/10",
  sector_intelligence:       "text-violet-600 dark:text-violet-400 border-violet-500/30 bg-violet-500/10",
  theme_intelligence:        "text-violet-600 dark:text-violet-400 border-violet-500/30 bg-violet-500/10",
  comparison_intelligence:   "text-violet-600 dark:text-violet-400 border-violet-500/30 bg-violet-500/10",
  decision_intelligence:     "text-violet-600 dark:text-violet-400 border-violet-500/30 bg-violet-500/10",
  policy_intelligence:       "text-indigo-600 dark:text-indigo-400 border-indigo-500/30 bg-indigo-500/10",
  ripple_intelligence:       "text-cyan-600 dark:text-cyan-400 border-cyan-500/30 bg-cyan-500/10",
  timeline_intelligence:     "text-cyan-600 dark:text-cyan-400 border-cyan-500/30 bg-cyan-500/10",
  opportunity_intelligence:  "text-emerald-600 dark:text-emerald-400 border-emerald-500/30 bg-emerald-500/10",
  educational_intelligence:  "text-emerald-600 dark:text-emerald-400 border-emerald-500/30 bg-emerald-500/10",
  question_intelligence:     "text-pink-600 dark:text-pink-400 border-pink-500/30 bg-pink-500/10",
  default:                   "text-text-secondary border-surface-border/10 bg-text-primary/5",
};

async function LatestIntelligenceRow() {
  const insights = await getInsights();
  const items = (((insights as any)?.items ?? []) as any[]).slice(0, 4);
  if (items.length === 0) return null;

  return (
    <div className="rounded-2xl border border-surface-border/7 bg-surface-card p-5">
      <CardHeader title="Latest Intelligence Articles" href="/newsroom" />
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {items.map((a: any) => {
          const publishedLabel = a.published_at
            ? new Date(a.published_at).toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit" })
            : null;
          const typeCls = ARTICLE_TYPE_COLOR[a.article_type as string] ?? ARTICLE_TYPE_COLOR.default;
          return (
            <Link key={a.slug} href={`/newsroom/article/${a.slug}`} className="group flex flex-col rounded-xl border border-surface-border/6 bg-text-primary/[0.02] p-3.5 transition-colors hover:border-surface-border/20 hover:bg-text-primary/[0.04]">
              <div className="flex items-center justify-between gap-2">
                <span className={`w-fit rounded-full border px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider ${typeCls}`}>
                  {(a.article_type ?? "intelligence").replace(/_/g, " ")}
                </span>
                {!a.views && (
                  <span className="rounded-full border border-violet-500/30 bg-violet-500/10 px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider text-violet-400">
                    New
                  </span>
                )}
              </div>
              <p className="mt-2 flex-1 text-[12px] font-bold leading-snug text-text-primary group-hover:text-sky-700 dark:text-sky-200 transition line-clamp-3">
                {a.headline}
              </p>
              <div className="mt-3 flex flex-wrap items-center gap-x-2.5 gap-y-1 border-t border-surface-border/5 pt-2.5 text-[9px] text-text-muted">
                {publishedLabel && <span>Published {publishedLabel}</span>}
                <span>{a.read_time_minutes ?? 1} min read</span>
                {a.confidence_score != null && <span className="text-sky-400 font-semibold">{Math.round(a.confidence_score * 100)}% confidence</span>}
                {a.impact_score != null && <span className="text-violet-400 font-semibold">Impact {Math.round(a.impact_score)}</span>}
                {!!a.views && <span>{a.views.toLocaleString("en-IN")} {a.views === 1 ? "view" : "views"}</span>}
              </div>
              <span className="mt-2 flex items-center gap-1 text-[10px] font-bold text-violet-400 group-hover:text-violet-600 dark:text-violet-300 transition">
                Read <ArrowRight className="h-2.5 w-2.5" />
              </span>
            </Link>
          );
        })}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// ROOT PAGE
//
// Weekend switch (brief §3/§4): a single branch here, not `if weekend`
// scattered through the sections below — the existing weekday homepage
// (WeekdayHomePage) is completely untouched, just wrapped. Reuses the
// SAME `/api/market/session` call TickerStrip/MarketSnapshotCard already
// make (cache()-deduped, so this adds zero extra requests on a weekday;
// on a weekend it's the only session call made, since the rest of this
// file's weekday components never render). `session === "weekend"` is
// this endpoint's own existing real value — not a new session detector
// (MarketSessionGate.tsx's client-side getSession() is dead code, not
// used here; see final report for why /api/market/session was chosen
// over /api/mie/state's equivalent field).
// ═══════════════════════════════════════════════════════════════════════════════
export default async function HomePage() {
  const session = await getSession();
  if (isWeekendSession(session as any)) {
    return <WeekendHomePage />;
  }
  return <WeekdayHomePage />;
}

function WeekdayHomePage() {
  return (
    <div className="space-y-5 py-6 pb-12">

      {/* Independence Day banner — scoped to 2026-08-15, see component. */}
      <IndependenceDayBanner />

      {/* Ticker strip */}
      <Suspense fallback={<Sk h={80} />}>
        <TickerStrip />
      </Suspense>

      {/* Homepage Intelligence hero (Phase 3, Priority 1) — "Good Morning",
          replaces the old AI Market Brief card as the primary read-this-first
          surface; see HomepageIntelligenceHero's own docstring. */}
      <Suspense fallback={<Sk h={420} />}>
        <HomepageIntelligenceHero />
      </Suspense>

      {/* Live Intelligence (Phase 3, Priority 2) — the "why this matters"
          stream right beneath the hero, per the user's own reasoning:
          "the next thing every user naturally asks is 'show me the
          intelligence behind it.'" */}
      <Suspense fallback={<Sk h={220} />}>
        <LiveIntelligenceSection />
      </Suspense>

      {/* Row 1 — Today's Biggest Events · Live Activity */}
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <Suspense fallback={<Sk h={340} />}><TodaysBiggestEventsCard /></Suspense>
        <LiveIntelligenceFeed compact limit={5} />
      </div>

      {/* Row 2 — Today's Opportunities · Companies to Watch · Theme Strength */}
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        <Suspense fallback={<Sk h={340} />}><TopOpportunitiesCard /></Suspense>
        <Suspense fallback={<Sk h={340} />}><CompaniesToWatchTable /></Suspense>
        <Suspense fallback={<Sk h={340} />}><ThemeStrengthCard /></Suspense>
      </div>

      {/* Row 3 — Latest Intelligence Articles (AIPE published articles, incl.
          the morning wrap — as a real article, not a duplicate homepage card) */}
      <Suspense fallback={<Sk h={180} />}>
        <LatestIntelligenceRow />
      </Suspense>

      {/* Supporting row — Key Risks · Market Snapshot · Watch Tomorrow.
          Real data, just not part of the primary read-this-first flow above. */}
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        <Suspense fallback={<Sk h={280} />}><KeyRisksCard /></Suspense>
        <Suspense fallback={<Sk h={280} />}><MarketSnapshotCard /></Suspense>
        <Suspense fallback={<Sk h={280} />}><WatchTomorrowCard /></Suspense>
      </div>

      {/* Background: 5-min story-hash poller + SSE session gate */}
      <HomepageRefresher />
      <MarketSessionGate />
    </div>
  );
}
