import { Suspense, cache } from "react";
import Link from "next/link";
import {
  ArrowRight, ChevronRight, Calendar, Building2, BarChart3,
  Landmark, Droplets, Shield, Cloud, DollarSign, FlameKindling, Cpu, Wheat,
  Sparkles, TrendingUp, Radar, GitBranch, Rocket, History,
} from "lucide-react";
import { HomepageRefresher } from "@/components/homepage/HomepageRefresher";
import { MarketSessionGate }  from "@/components/MarketSessionGate";
import { LiveIntelligenceFeed } from "@/components/market/LiveIntelligenceFeed";
import { API_BASE_URL as API } from "@/lib/api";
import { compareScoresDesc, impactToStyle } from "@/lib/scoring";
import { cleanText } from "@/lib/text";

export const dynamic = "force-dynamic";

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
const getPremarket    = cache(() => live(`${API}/api/market/premarket`));
const getTopMovers    = cache(() => live(`${API}/api/market/top-movers`));
const getCalendar     = cache(() => live(`${API}/api/calendar/`));
const getIndices      = cache(() => live<any[]>(`${API}/api/indices/`));
const getLive         = cache(() => live(`${API}/api/market/live`));
const getSession      = cache(() => live(`${API}/api/market/session`));
const getRadar        = cache(() => revalidate(`${API}/api/radar/?page=1&page_size=4`, 120));
const getRecentEvents = cache(() => revalidate(`${API}/api/events/?sort_by=impact_score&page_size=10`, 300));
// Recency-aware ranking (event_lifecycle.py) — used only by "Latest Biggest
// Events" below. CompaniesToWatchTable deliberately keeps using the plain
// impact_score pool above (unaffected by this change).
const getActiveEvents = cache(() => revalidate(`${API}/api/events/?sort_by=active&page_size=5`, 120));
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
  const t = (title + " " + (category ?? "")).toLowerCase();
  const base = "flex h-8 w-8 shrink-0 items-center justify-center rounded-xl";
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
  return <div className={`${base} bg-slate-500/20`}><Calendar className="h-4 w-4 text-slate-400"/></div>;
}

// Skeleton
function Sk({ h = 200, r = "rounded-2xl" }: { h?: number; r?: string }) {
  return (
    <div className={`animate-pulse border border-white/[0.05] bg-white/[0.02] ${r}`} style={{ height: h }} />
  );
}

// Shared compact card header — title + optional "View All →"
function CardHeader({ title, href, badge }: { title: string; href?: string; badge?: React.ReactNode }) {
  return (
    <div className="mb-3 flex items-center justify-between">
      <h3 className="text-[13px] font-black text-white">{title}</h3>
      {badge ?? (href && (
        <Link href={href as any} className="flex items-center gap-1 text-[11px] font-semibold text-violet-400 hover:text-violet-300 transition">
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
    <div className="flex items-stretch divide-x divide-white/[0.06] overflow-x-auto rounded-2xl border border-white/[0.07] bg-[#060e1e] scrollbar-hide">
      {cells.map((c: any) => {
        const chart = ((c.chart as any[] | undefined) ?? []).map((p: any) => p.value).filter((v: any) => typeof v === "number");
        return (
          <div key={c.label} className="flex min-w-[150px] flex-1 items-center justify-between gap-3 px-5 py-3.5">
            <div className="min-w-0">
              <p className="text-[9px] font-bold uppercase tracking-[0.1em] text-slate-600">{c.label}</p>
              <p className="text-[16px] font-black tabular-nums text-white leading-tight">{c.value}</p>
              <p className={`text-[10px] font-bold tabular-nums ${c.positive ? "text-emerald-400" : "text-rose-400"}`}>{c.change}</p>
            </div>
            {chart.length >= 2 && <MiniSparkline data={chart} positive={c.positive !== false} w={56} h={26} />}
          </div>
        );
      })}
      {usdinr && (
        <div className="flex min-w-[130px] flex-1 flex-col justify-center gap-0.5 px-5 py-3.5">
          <p className="text-[9px] font-bold uppercase tracking-[0.1em] text-slate-600">USD/INR</p>
          <p className="text-[16px] font-black tabular-nums text-white leading-tight">₹{usdinr.value}</p>
          <p className={`text-[10px] font-bold tabular-nums ${usdinr.positive ? "text-emerald-400" : "text-rose-400"}`}>{usdinr.change_str ?? usdinr.change}</p>
        </div>
      )}
      <div className="flex min-w-[150px] flex-1 flex-col justify-center gap-1 px-5 py-3.5">
        <p className="text-[9px] font-bold uppercase tracking-[0.1em] text-slate-600">Market Status</p>
        <p className={`text-[13px] font-black ${isOpen ? "text-emerald-400" : "text-slate-400"}`}>{statusLabel}</p>
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
      {"★".repeat(n)}<span className="text-white/15">{"★".repeat(5 - n)}</span>
    </span>
  );
}

/**
 * Homepage Intelligence (Phase 3, Priority 1) — the "Good Morning" daily
 * brief. Replaces the old AI Market Brief card as the homepage's hero:
 * same single source of truth (the real AIPE morning_intelligence
 * article — deliberately never blended with MIE or any other pipeline,
 * see homepage_intelligence.py's module docstring), just surfaced at the
 * scale this content deserves, plus two real additions the article alone
 * can't carry: a genuine day-over-day sector diff and a one-line AI
 * Prediction (both from GET /api/homepage/intelligence).
 */
async function HomepageIntelligenceHero() {
  const [brief, extras] = await Promise.all([getMorningBrief(), getHomepageExtras()]);
  if (!brief) return null;

  const ex = (extras as any) ?? {};
  const confPct = brief.confidence_score != null ? Math.round(brief.confidence_score * 100) : null;

  // Today's Biggest Story / Ripple / Companies Most Likely To Move /
  // Biggest Opportunity / Highest Risk all come from the Latest Biggest
  // Events Engine (event_lifecycle.py) — the SAME ranking that decides
  // what's on the Events page, not a second, independently-guessed
  // narrative. Falls back to the article's own fields only if the events
  // engine genuinely has nothing (e.g. empty dev DB) — never a blank hero.
  const ev = ex.event?.available ? ex.event.primary : null;
  const stars = ev
    ? Math.max(1, Math.min(5, Math.round((ev.impact_score ?? 60) / 20)))
    : Math.max(1, Math.min(5, Math.round((brief.impact_score ?? (confPct ?? 60)) / 20)));

  const sectors = (brief.sectors_affected ?? []) as any[];
  const positiveSectors = sectors.filter(s => s.impact === "positive")
    .sort((a, b) => _magRank(b.magnitude) - _magRank(a.magnitude));
  const negativeSectors = sectors.filter(s => s.impact === "negative")
    .sort((a, b) => _magRank(b.magnitude) - _magRank(a.magnitude));
  // Fall back to the article's own sector breakdown at the FIELD level, not
  // just when ev is entirely absent — the top event can be real and still
  // have no negative-impact sector of its own (e.g. a purely positive
  // Defence budget event), in which case the hero showed a bare "—" even
  // though the article's broader sectors_affected had a real risk sector.
  const biggestOpportunity = ev?.opportunity_sector ?? positiveSectors[0]?.name;
  const highestRisk = ev?.risk_sector ?? negativeSectors[0]?.name;

  const companies = ev
    ? ev.companies.slice(0, 3).map((c: any) => ({ symbol: c.symbol, name: c.name, impact: "positive" }))
    : ((brief.companies_affected ?? []) as any[]).filter(c => c.impact === "positive" || c.impact === "negative").slice(0, 3);

  const ripple = ev ? ev.ripple.slice(0, 3) : ((brief.ripple_effect ?? []) as any[]).slice(0, 3);
  const changes = (ex.yesterday_changes ?? []) as { name: string; delta: number; direction: string }[];
  const storyTitle = ev ? ev.title : brief.headline;
  const storySummary = ev ? ev.why_it_matters : brief.executive_summary;

  return (
    <div className="rounded-[24px] border border-white/[0.07] bg-gradient-to-br from-[#0b1220] to-[#060e1e] p-6 md:p-7">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="flex items-center gap-2 text-[11px] font-bold uppercase tracking-[0.16em] text-violet-400">
            <Sparkles className="h-3.5 w-3.5" /> {greeting()}
          </p>
          <h1 className="mt-1 text-[22px] font-black leading-tight text-white md:text-[26px]">Today&apos;s Market Intelligence</h1>
        </div>
        <div className="text-right">
          <p className="text-[9px] font-bold uppercase tracking-[0.14em] text-slate-500">Confidence</p>
          <p className="text-[28px] font-black tabular-nums text-white leading-none">{confPct != null ? `${confPct}%` : "—"}</p>
        </div>
      </div>

      <div className="mt-5 grid grid-cols-1 gap-5 lg:grid-cols-[1.3fr_1fr]">
        {/* Left: biggest story + opportunity/risk + companies */}
        <div className="space-y-4">
          <Link href={ev ? `/events/${ev.id}` as any : "/events"} className="block rounded-[16px] border border-white/[0.06] bg-white/[0.02] p-4 transition hover:border-violet-500/25">
            <div className="mb-1 flex items-center justify-between">
              <p className="text-[9px] font-bold uppercase tracking-[0.14em] text-slate-500">Today&apos;s Biggest Story</p>
              {ev?.lifecycle && _LIFECYCLE_BADGE[ev.lifecycle] && (
                <span className={`rounded-full px-1.5 py-0.5 text-[8px] font-black uppercase ${_LIFECYCLE_BADGE[ev.lifecycle]}`}>{ev.lifecycle}</span>
              )}
            </div>
            <p className="text-[16px] font-semibold leading-snug text-white">{cleanText(storyTitle)}</p>
            {storySummary && (
              <p className="mt-1.5 line-clamp-2 text-[12px] leading-5 text-slate-400">{cleanText(storySummary)}</p>
            )}
            <div className="mt-2 flex items-center gap-1.5 text-[11px] text-slate-500">
              <span>Expected Market Impact</span> <Stars n={stars} />
            </div>
          </Link>

          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-[14px] border border-emerald-500/15 bg-emerald-500/[0.05] p-3.5">
              <p className="text-[9px] font-bold uppercase tracking-[0.12em] text-emerald-400">Biggest Opportunity</p>
              <p className="mt-1 text-[14px] font-bold text-white">{biggestOpportunity ?? "—"}</p>
            </div>
            <div className="rounded-[14px] border border-rose-500/15 bg-rose-500/[0.05] p-3.5">
              <p className="text-[9px] font-bold uppercase tracking-[0.12em] text-rose-400">Highest Risk</p>
              <p className="mt-1 text-[14px] font-bold text-white">{highestRisk ?? "—"}</p>
            </div>
          </div>

          {companies.length > 0 && (
            <div>
              <p className="mb-1.5 text-[9px] font-bold uppercase tracking-[0.14em] text-slate-500">Companies Most Likely To Move</p>
              <div className="flex flex-wrap gap-1.5">
                {companies.map((c: any, i: number) => (
                  <Link key={i} href={`/companies/${c.symbol}` as any}
                    className={`flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-semibold transition hover:opacity-80 ${
                      c.impact === "positive" ? "border-emerald-500/25 bg-emerald-500/10 text-emerald-300" : "border-rose-500/25 bg-rose-500/10 text-rose-300"
                    }`}>
                    <ImpactDot impact={c.impact} /> {cleanText(c.name)}
                  </Link>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Right: what changed + ripple + prediction */}
        <div className="space-y-4">
          <div className="rounded-[16px] border border-white/[0.06] bg-white/[0.02] p-4">
            <p className="mb-2 text-[9px] font-bold uppercase tracking-[0.14em] text-slate-500">What Changed Since Yesterday</p>
            {changes.length === 0 ? (
              <p className="text-[11px] text-slate-600">Not enough history yet — check back tomorrow.</p>
            ) : (
              <ul className="space-y-1">
                {changes.map((c, i) => (
                  <li key={i} className={`flex items-center gap-1.5 text-[12px] font-medium ${c.direction === "up" ? "text-emerald-400" : "text-rose-400"}`}>
                    {c.direction === "up" ? "↑" : "↓"} {c.name} {c.direction === "up" ? "+" : ""}{c.delta}
                  </li>
                ))}
              </ul>
            )}
          </div>

          {ripple.length > 0 && (
            <div className="rounded-[16px] border border-white/[0.06] bg-white/[0.02] p-4">
              <p className="mb-2 text-[9px] font-bold uppercase tracking-[0.14em] text-slate-500">Today&apos;s Ripple</p>
              <div className="space-y-2">
                {ripple.map((r: any, i: number) => (
                  <div key={i} className="flex items-center gap-1.5 text-[11px] leading-snug text-slate-300">
                    <span className="font-medium text-white">{cleanText(r.from_entity)}</span>
                    <ArrowRight className="h-3 w-3 shrink-0 text-slate-600" />
                    <span>{cleanText(r.to_entity)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {ex.ai_prediction && (
            <div className="rounded-[16px] border border-violet-500/15 bg-violet-500/[0.06] p-4">
              <p className="mb-1 text-[9px] font-bold uppercase tracking-[0.14em] text-violet-300">AI Prediction</p>
              <p className="text-[13px] font-medium leading-snug text-slate-200">{ex.ai_prediction}</p>
            </div>
          )}
        </div>
      </div>

      <div className="mt-5 flex items-center justify-between border-t border-white/[0.06] pt-4">
        {brief.published_at && <span className="text-[10px] text-slate-600">{briefTimeLabel(brief.published_at)}</span>}
        <Link href="/newsroom/daily-brief"
          className="inline-flex items-center gap-1.5 rounded-full bg-white px-4 py-2 text-[11px] font-bold text-slate-900 transition hover:bg-slate-100">
          Read Full Brief <ArrowRight className="h-3 w-3" />
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
  anomaly:           { label: "Intelligence Detection", icon: <Radar className="h-3.5 w-3.5" />,     cls: "text-violet-300 border-violet-500/25 bg-violet-500/[0.08]" },
  policy_ripple:     { label: "Policy Intelligence",     icon: <GitBranch className="h-3.5 w-3.5" />, cls: "text-sky-300 border-sky-500/25 bg-sky-500/[0.08]" },
  early_theme:       { label: "Emerging Theme",          icon: <Rocket className="h-3.5 w-3.5" />,    cls: "text-emerald-300 border-emerald-500/25 bg-emerald-500/[0.08]" },
  historical_match:  { label: "Pattern Detected",        icon: <History className="h-3.5 w-3.5" />,   cls: "text-amber-300 border-amber-500/25 bg-amber-500/[0.08]" },
};

function LiveIntelligenceCard({ item }: { item: any }) {
  const meta = _LI_META[item.type];
  if (!meta) return null;

  return (
    <div className="flex h-full flex-col rounded-[18px] border border-white/[0.07] bg-white/[0.02] p-4">
      <span className={`inline-flex w-fit items-center gap-1.5 rounded-full border px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider ${meta.cls}`}>
        {meta.icon} {meta.label}
      </span>
      <p className="mt-2.5 text-[13.5px] font-semibold leading-snug text-white">{cleanText(item.headline)}</p>

      {item.type === "anomaly" && (
        <>
          {item.why_it_matters && <p className="mt-1.5 line-clamp-2 text-[11.5px] leading-5 text-slate-400">Why this matters: {cleanText(item.why_it_matters)}</p>}
          {item.similarity != null && <p className="mt-1.5 text-[10px] text-slate-500">Historical similarity <span className="font-bold text-white">{Math.round(item.similarity)}%</span></p>}
        </>
      )}

      {item.type === "policy_ripple" && item.path?.length > 0 && (
        <div className="mt-2 flex flex-wrap items-center gap-1 text-[11px] text-slate-300">
          {item.path.map((p: string, i: number) => (
            <span key={i} className="flex items-center gap-1">
              {i > 0 && <ArrowRight className="h-2.5 w-2.5 text-slate-600" />}
              <span className="rounded-full border border-white/10 bg-white/[0.03] px-2 py-0.5">{cleanText(p)}</span>
            </span>
          ))}
        </div>
      )}

      {item.type === "early_theme" && (
        <div className="mt-2 flex items-center gap-4 text-[11px]">
          <span className="text-slate-500">Stage <span className="font-bold text-emerald-400">Early</span></span>
          {item.opportunity_score != null && <span className="text-slate-500">Opportunity Score <span className="font-bold text-white">{item.opportunity_score}</span></span>}
        </div>
      )}

      {item.type === "historical_match" && (
        <>
          {item.similarity != null && <p className="mt-1.5 text-[10px] text-slate-500">Similarity <span className="font-bold text-white">{Math.round(item.similarity)}%</span></p>}
          {item.key_lesson && <p className="mt-1 line-clamp-2 text-[11px] leading-5 text-slate-400">{cleanText(item.key_lesson)}</p>}
          <div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-0.5 text-[10.5px]">
            {(item.winners ?? []).slice(0, 3).map((w: string, i: number) => <span key={i} className="text-emerald-400">▲ {w}</span>)}
            {(item.losers ?? []).slice(0, 2).map((l: string, i: number) => <span key={i} className="text-rose-400">▼ {l}</span>)}
          </div>
        </>
      )}

      {item.companies?.length > 0 && (
        <div className="mt-auto flex flex-wrap gap-1 pt-2.5">
          {item.companies.slice(0, 5).map((c: string, i: number) => (
            <Link key={i} href={`/companies/${c}` as any}
              className="rounded-full border border-white/10 bg-white/[0.03] px-2 py-0.5 text-[10px] font-semibold text-slate-300 transition hover:border-violet-500/30 hover:text-violet-300">
              {c}
            </Link>
          ))}
        </div>
      )}
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
        <h2 className="text-[15px] font-black text-white">Live Intelligence</h2>
        <span className="text-[11px] text-slate-500">— Ripple Signals</span>
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
    <div className="flex h-full flex-col rounded-2xl border border-white/[0.07] bg-[#060e1e] p-5">
      <CardHeader title="Other Major Events" href="/events" />
      {rest.length === 0 ? (
        <p className="flex-1 py-6 text-center text-[12px] text-slate-600">No other scored events available right now.</p>
      ) : (
        <div className="flex-1 space-y-3">
          {rest.map((e, idx) => {
            const style = impactToStyle(e.impact_score);
            const sectors = (e.sectors ?? []) as string[];
            const companies = (e.companies ?? []) as { symbol: string; name: string; impact: string }[];
            const reason = _rankReason(e.lifecycle, idx + 2);
            return (
              <div key={e.id} className="rounded-[16px] border border-white/[0.06] bg-white/[0.02] p-3.5">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-1.5">
                    <span className="rounded-full border border-white/10 bg-white/[0.03] px-1.5 py-0.5 text-[8px] font-black text-slate-300">
                      {reason.emoji} {reason.text}
                    </span>
                    <span className={`rounded-full border px-1.5 py-0.5 text-[8px] font-black uppercase tabular-nums ${style.circle}`}>
                      {style.label} Impact
                    </span>
                  </div>
                  <span className="shrink-0 text-[11px] font-black tabular-nums text-slate-400">
                    {e.impact_score != null ? Math.round(e.impact_score) : "—"}
                  </span>
                </div>
                <Link href={`/events/${e.id}` as any} className="group mt-1.5 block">
                  <p className="text-[13px] font-bold leading-snug text-white group-hover:text-violet-200 transition line-clamp-2">{cleanText(e.title)}</p>
                </Link>
                {sectors.length > 0 && (
                  <p className="mt-1.5 text-[10.5px] text-slate-500">{sectors.slice(0, 3).join(" • ")}</p>
                )}
                {companies.length > 0 && (
                  <div className="mt-1.5 flex flex-wrap gap-1">
                    {companies.slice(0, 5).map((c, i) => (
                      <Link key={i} href={`/companies/${c.symbol}` as any}
                        className={`rounded-full border px-1.5 py-0.5 text-[9.5px] font-semibold transition hover:opacity-80 ${
                          c.impact === "Positive" ? "border-emerald-500/25 bg-emerald-500/10 text-emerald-300"
                          : c.impact === "Negative" ? "border-rose-500/25 bg-rose-500/10 text-rose-300"
                          : "border-white/10 bg-white/[0.03] text-slate-400"
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
                <div className="mt-2.5 flex items-center gap-3 border-t border-white/[0.05] pt-2">
                  <Link href={`/ai-search?q=${encodeURIComponent(`What are the investment implications of: ${e.title}`)}` as any} className="text-[10px] font-semibold text-violet-400 hover:text-violet-300 transition">Analyze with AI →</Link>
                  <Link href={`/ripple?event=${e.id}` as any} className="text-[10px] font-semibold text-sky-400 hover:text-sky-300 transition">Ripple Analysis →</Link>
                  <Link href={`/events/${e.id}` as any} className="text-[10px] font-semibold text-slate-500 hover:text-slate-300 transition">Full Event Analysis →</Link>
                  {e.confidence != null && <span className="ml-auto text-[10px] text-slate-600">Confidence <span className="font-bold text-slate-400">{Math.round(e.confidence)}%</span></span>}
                </div>
              </div>
            );
          })}
        </div>
      )}
      <Link href="/events" className="mt-4 text-center text-[11px] font-semibold text-slate-500 hover:text-slate-300 transition">
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
    <div className="flex h-full flex-col rounded-2xl border border-white/[0.07] bg-[#060e1e] p-5">
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
        <p className="flex-1 py-6 text-center text-[12px] text-slate-600">Sector data unavailable.</p>
      ) : (
        <div className="grid flex-1 grid-cols-2 gap-2 content-start sm:grid-cols-3">
          {sectors.map((s: any) => (
            <div key={s.id ?? s.name} className={`flex flex-col justify-center rounded-xl p-3 ${s.positive ? "bg-emerald-500/15" : "bg-rose-500/15"}`}>
              <p className={`text-[9px] font-black uppercase tracking-wide leading-tight ${s.positive ? "text-emerald-300" : "text-rose-300"}`}>{s.name}</p>
              <p className={`mt-1 text-[13px] font-black tabular-nums ${s.positive ? "text-emerald-400" : "text-rose-400"}`}>{s.value}</p>
            </div>
          ))}
        </div>
      )}
      <div className="mt-4 flex items-center gap-4 text-[10px] text-slate-500">
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

async function CompaniesToWatchTable() {
  const recentRaw = await getRecentEvents();
  const events = ((recentRaw as any)?.results ?? (recentRaw as any) ?? []) as any[];
  const sorted = [...events].sort((a, b) => compareScoresDesc(a.impact_score, b.impact_score));

  const seen = new Set<string>();
  const rows: { ticker: string; name: string; reason: string; score: number | null }[] = [];
  outer:
  for (const e of sorted) {
    for (const c of (e.companies ?? [])) {
      if (!c.symbol || seen.has(c.symbol)) continue;
      seen.add(c.symbol);
      rows.push({ ticker: c.symbol, name: c.name ?? c.symbol, reason: e.title, score: e.impact_score ?? null });
      if (rows.length >= 5) break outer;
    }
  }

  return (
    <div className="flex h-full flex-col rounded-2xl border border-white/[0.07] bg-[#060e1e] p-5">
      <CardHeader title="Companies to Watch" href="/companies" />
      {rows.length === 0 ? (
        <p className="flex-1 py-6 text-center text-[12px] text-slate-600">Company data is loading.</p>
      ) : (
        <div className="flex-1">
          <div className="mb-1.5 grid grid-cols-[1fr_44px] gap-2 text-[8px] font-bold uppercase tracking-wider text-slate-700">
            <span>Company · Reason</span>
            <span className="text-right">Score</span>
          </div>
          <div className="space-y-2.5">
            {rows.map((r, i) => {
              const style = impactToStyle(r.score);
              return (
                <Link key={r.ticker} href={`/companies/${r.ticker}` as any} className="group grid grid-cols-[1fr_44px] items-center gap-2">
                  <div className="flex min-w-0 items-center gap-2">
                    <div className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br text-[8px] font-black text-white ${AVATAR_GRADIENT[i % 6]}`}>
                      {r.ticker.slice(0, 2)}
                    </div>
                    <div className="min-w-0">
                      <p className="truncate text-[11px] font-bold text-white group-hover:text-violet-200 transition">{cleanText(r.name)}</p>
                      <p className="truncate text-[9px] text-slate-500">{cleanText(r.reason)}</p>
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
    <div className="flex h-full flex-col rounded-2xl border border-white/[0.07] bg-[#060e1e] p-5">
      <CardHeader title="Top Opportunities" href="/opportunity-radar" />
      {items.length === 0 ? (
        <p className="flex-1 py-6 text-center text-[12px] text-slate-600">AI is scanning for opportunities.</p>
      ) : (
        <div className="flex-1 space-y-3">
          {items.map((r: any) => (
            <Link key={r.id} href="/opportunity-radar" className="group flex items-start gap-3">
              <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-emerald-500/15">
                <TrendingUp className="h-4 w-4 text-emerald-400" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-[12px] font-bold leading-snug text-white group-hover:text-emerald-200 transition line-clamp-1">{cleanText(r.title)}</p>
                <p className="mt-0.5 text-[10px] text-slate-500 line-clamp-1">{cleanText(r.summary)}</p>
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
    <div className="flex h-full flex-col rounded-2xl border border-white/[0.07] bg-[#060e1e] p-5">
      <CardHeader title="Key Risks" href="/newsroom/daily-brief" />
      {risks.length === 0 ? (
        <p className="flex-1 py-6 text-center text-[12px] text-slate-600">No elevated risks in today's brief.</p>
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
                  <p className="text-[12px] font-bold leading-snug text-white group-hover:text-rose-200 transition line-clamp-1">{cleanText(r.title)}</p>
                  <p className="mt-0.5 text-[10px] text-slate-500 line-clamp-1">{cleanText(r.description)}</p>
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
    <div className="flex h-full flex-col rounded-2xl border border-white/[0.07] bg-[#060e1e] p-5">
      <CardHeader title="Theme Strength" href="/newsroom/themes" />
      {themes.length === 0 ? (
        <p className="flex-1 py-6 text-center text-[12px] text-slate-600">Theme data is loading.</p>
      ) : (
        <div className="flex-1 space-y-3">
          {themes.map((t: any) => {
            const score = t.opportunity_score ?? 0;
            const barColor = score >= 75 ? "bg-emerald-500" : score >= 50 ? "bg-sky-500" : score >= 30 ? "bg-amber-500" : "bg-rose-500";
            return (
              <Link key={t.id} href={`/newsroom/themes/${t.slug}`} className="group block">
                <div className="mb-1 flex items-center justify-between">
                  <span className="line-clamp-1 text-[11px] font-semibold text-slate-300 group-hover:text-white transition">{cleanText(t.title)}</span>
                  <span className="shrink-0 text-[11px] font-black tabular-nums text-white">{Math.round(score)}</span>
                </div>
                <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/[0.06]">
                  <div className={`h-full rounded-full ${barColor}`} style={{ width: `${Math.min(100, Math.max(0, score))}%` }} />
                </div>
                <div className="mt-1 flex items-center gap-2 text-[9.5px] text-slate-600">
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
    <div className="flex h-full flex-col rounded-2xl border border-white/[0.07] bg-[#060e1e] p-5">
      <CardHeader title="Watch Tomorrow" href="/market-intelligence?tab=live-market" />
      {items.length === 0 ? (
        <p className="flex-1 py-6 text-center text-[12px] text-slate-600">No upcoming events in the next 7 days.</p>
      ) : (
        <div className="flex-1 space-y-3">
          {items.map((e: any) => (
            <div key={e.id} className="flex items-start gap-3">
              <EventIcon title={e.title} category={e.category} />
              <div className="min-w-0 flex-1">
                <p className="text-[12px] font-bold leading-snug text-white line-clamp-1">{e.title}</p>
                <p className="mt-0.5 text-[10px] text-slate-500">{e.category ?? "Event"}</p>
              </div>
              <span className="shrink-0 text-[10px] font-semibold text-slate-500">{e.date}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

async function LatestIntelligenceRow() {
  const insights = await getInsights();
  const items = (((insights as any)?.items ?? []) as any[]).slice(0, 4);
  if (items.length === 0) return null;

  return (
    <div className="rounded-2xl border border-white/[0.07] bg-[#060e1e] p-5">
      <CardHeader title="Latest Intelligence Articles" href="/newsroom" />
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {items.map((a: any) => {
          const publishedLabel = a.published_at
            ? new Date(a.published_at).toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit" })
            : null;
          return (
            <Link key={a.slug} href={`/newsroom/article/${a.slug}`} className="group flex flex-col rounded-xl border border-white/[0.06] bg-white/[0.02] p-3.5 transition-colors hover:border-white/20 hover:bg-white/[0.04]">
              <div className="flex items-center justify-between gap-2">
                <span className="w-fit rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider text-slate-500">
                  {(a.article_type ?? "intelligence").replace(/_/g, " ")}
                </span>
                {!a.views && (
                  <span className="rounded-full border border-violet-500/30 bg-violet-500/10 px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider text-violet-400">
                    New
                  </span>
                )}
              </div>
              <p className="mt-2 flex-1 text-[12px] font-bold leading-snug text-white group-hover:text-sky-200 transition line-clamp-3">
                {a.headline}
              </p>
              <div className="mt-3 flex flex-wrap items-center gap-x-2.5 gap-y-1 border-t border-white/[0.05] pt-2.5 text-[9px] text-slate-500">
                {publishedLabel && <span>Published {publishedLabel}</span>}
                <span>{a.read_time_minutes ?? 1} min read</span>
                {a.confidence_score != null && <span className="text-sky-400 font-semibold">{Math.round(a.confidence_score * 100)}% confidence</span>}
                {a.impact_score != null && <span className="text-violet-400 font-semibold">Impact {Math.round(a.impact_score)}</span>}
                {!!a.views && <span>{a.views.toLocaleString("en-IN")} {a.views === 1 ? "view" : "views"}</span>}
              </div>
              <span className="mt-2 flex items-center gap-1 text-[10px] font-bold text-violet-400 group-hover:text-violet-300 transition">
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
// ═══════════════════════════════════════════════════════════════════════════════
export default function HomePage() {
  return (
    <div className="mx-auto max-w-[1600px] space-y-5 px-5 py-6 pb-12 md:px-8">

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
