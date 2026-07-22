import { Suspense, cache } from "react";
import Link from "next/link";
import {
  ArrowRight, ChevronRight, Calendar, Building2, BarChart3,
  Landmark, Droplets, Shield, Cloud, DollarSign, FlameKindling, Cpu, Wheat,
  Sparkles, TrendingUp,
} from "lucide-react";
import { HomepageRefresher } from "@/components/homepage/HomepageRefresher";
import { MarketSessionGate }  from "@/components/MarketSessionGate";
import { LiveIntelligenceFeed } from "@/components/market/LiveIntelligenceFeed";
import { API_BASE_URL as API } from "@/lib/api";
import { compareScoresDesc, impactToStyle } from "@/lib/scoring";
import { cleanText } from "@/lib/text";
import { MarketSentimentGauge } from "@/components/MarketSentimentGauge";

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

// Same real market_health/market_bias score shown on the Newsroom sentiment
// gauge — one computed signal, reused here rather than a second, possibly
// disagreeing number.
const getMarketHealth = cache(async () => {
  return revalidate<{ market_bias?: string; market_health?: { score: number; label: string } }>(
    `${API}/api/mie/state`, 300,
  );
});

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
async function AIMarketBriefCard() {
  // Real AIPE morning_intelligence article — single source of truth for
  // "what does the AI say about today," replacing the old MIE-sourced
  // mie.story (a separate, competing narrative pipeline that could — and
  // did — disagree with what the AI Newsroom shows for the same day).
  const [brief, health] = await Promise.all([getMorningBrief(), getMarketHealth()]);
  if (!brief) return null;

  const summary = cleanText(brief.key_takeaway ?? brief.executive_summary ?? "");
  const confPct = brief.confidence_score != null ? Math.round(brief.confidence_score * 100) : null;

  return (
    <div className="flex h-full flex-col rounded-2xl border border-white/[0.07] bg-[#060e1e] p-5">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-violet-400" />
          <h3 className="text-[13px] font-black text-white">AI Market Brief</h3>
        </div>
        {brief.published_at && <span className="text-[10px] text-slate-600">{briefTimeLabel(brief.published_at)}</span>}
      </div>

      {confPct != null && (
        <div className="mb-3 flex items-center gap-2">
          <span className="text-[11px] font-bold text-slate-400">{confPct}% Confidence</span>
        </div>
      )}

      <p className="mb-2 text-[15px] font-semibold leading-snug text-white line-clamp-2">{cleanText(brief.headline)}</p>
      {summary && (
        <p className="mb-4 line-clamp-3 text-[12.5px] leading-5 text-slate-400">{summary}</p>
      )}

      {health?.market_bias && health.market_health && (
        <div className="mb-4 flex flex-1 flex-col items-center justify-center gap-1 rounded-xl border border-white/[0.06] bg-white/[0.02] py-3">
          <p className="text-[9px] font-bold uppercase tracking-[0.18em] text-slate-500">Today&apos;s Market Score</p>
          <MarketSentimentGauge
            score={health.market_health.score}
            bias={health.market_bias}
            label={health.market_health.label}
          />
        </div>
      )}

      <Link href="/newsroom/daily-brief"
        className="mt-auto inline-flex w-fit items-center gap-1.5 rounded-full bg-white px-4 py-2 text-[11px] font-bold text-slate-900 transition hover:bg-slate-100">
        Read Full Brief <ArrowRight className="h-3 w-3" />
      </Link>
    </div>
  );
}

async function TodaysBiggestEventsCard() {
  const recentRaw = await getRecentEvents();
  const events = ((recentRaw as any)?.results ?? (recentRaw as any) ?? []) as any[];
  const todayStr = todayDateStr();

  // impact_score === 0 means "not yet scored" (e.g. routine NSE compliance
  // filings that were enriched but genuinely carry no market signal), not a
  // real low score — same convention as Events/LiveMarketTab. Real news that
  // happened today can still be sitting unscored while a truly significant
  // event from a few days ago has a real score; showing nothing in that case
  // (the old "must be dated exactly today" rule) reads as "broken" when
  // there's genuinely nothing scored yet today. So: prefer today's own real
  // events, but fall back to the most recent scored events otherwise —
  // every item's own timestamp is shown, so it's never mislabeled as today's.
  const seen = new Set<string>();
  const scored: any[] = [];
  for (const e of events) {
    if (!e.id || seen.has(e.id) || e.impact_score === 0 || e.impact_score == null) continue;
    seen.add(e.id);
    scored.push(e);
  }
  scored.sort((a, b) => compareScoresDesc(a.impact_score, b.impact_score));
  const fromToday = scored.filter(e => e.date && new Date(e.date).toDateString() === todayStr);
  const items = (fromToday.length > 0 ? fromToday : scored).slice(0, 3);
  const allFromToday = items.length > 0 && items.every(e => e.date && new Date(e.date).toDateString() === todayStr);

  return (
    <div className="flex h-full flex-col rounded-2xl border border-white/[0.07] bg-[#060e1e] p-5">
      <CardHeader title={allFromToday ? "Today's Biggest Events" : "Latest Biggest Events"} href="/events" />
      {items.length === 0 ? (
        <p className="flex-1 py-6 text-center text-[12px] text-slate-600">No scored events available right now.</p>
      ) : (
        <div className="flex-1 space-y-3.5">
          {items.map((e, i) => {
            const style = impactToStyle(e.impact_score);
            const eventIsToday = e.date && new Date(e.date).toDateString() === todayStr;
            return (
              <Link key={e.id} href={`/events/${e.id}` as any} className="group flex items-start gap-3">
                <div className="mt-0.5 flex w-11 shrink-0 flex-col items-start gap-1">
                  <span className="text-[9px] font-bold tabular-nums text-slate-600">
                    {e.date
                      ? eventIsToday
                        ? new Date(e.date).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })
                        : new Date(e.date).toLocaleDateString("en-IN", { day: "2-digit", month: "short" })
                      : ""}
                  </span>
                  {i === 0 && eventIsToday && <span className="rounded-full bg-rose-500/15 px-1.5 py-0.5 text-[7px] font-black text-rose-400">LIVE</span>}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-[12px] font-bold leading-snug text-white group-hover:text-violet-200 transition line-clamp-2">{cleanText(e.title)}</p>
                  <p className="mt-0.5 text-[10px] text-slate-500">{e.category ?? "Market"} · {style.label} Impact</p>
                </div>
                <span className={`shrink-0 rounded-lg border px-2 py-1 text-[11px] font-black tabular-nums ${style.circle}`}>
                  {e.impact_score != null ? Math.round(e.impact_score) : "—"}
                </span>
              </Link>
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
              <span className="w-fit rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider text-slate-500">
                {(a.article_type ?? "intelligence").replace(/_/g, " ")}
              </span>
              <p className="mt-2 flex-1 text-[12px] font-bold leading-snug text-white group-hover:text-sky-200 transition line-clamp-3">
                {a.headline}
              </p>
              <div className="mt-3 flex flex-wrap items-center gap-x-2.5 gap-y-1 border-t border-white/[0.05] pt-2.5 text-[9px] text-slate-500">
                {publishedLabel && <span>Published {publishedLabel}</span>}
                <span>{a.read_time_minutes ?? 1} min read</span>
                {a.confidence_score != null && <span className="text-sky-400 font-semibold">{Math.round(a.confidence_score * 100)}% confidence</span>}
                {a.impact_score != null && <span className="text-violet-400 font-semibold">Impact {Math.round(a.impact_score)}</span>}
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

      {/* Row 1 — AI Market Brief (hero) · Today's Biggest Events · Live Intelligence */}
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[1.6fr_1fr_1fr]">
        <Suspense fallback={<Sk h={420} />}><AIMarketBriefCard /></Suspense>
        <Suspense fallback={<Sk h={420} />}><TodaysBiggestEventsCard /></Suspense>
        <LiveIntelligenceFeed compact limit={8} />
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
