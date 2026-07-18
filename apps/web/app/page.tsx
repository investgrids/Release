import { Suspense, cache } from "react";
import Link from "next/link";
import {
  ArrowRight, ChevronRight, Calendar, Building2, BarChart3,
  Landmark, Droplets, Shield, Cloud, DollarSign, FlameKindling, Cpu, Wheat,
  Sparkles, TrendingUp, TrendingDown, Minus,
} from "lucide-react";
import { HomepageRefresher } from "@/components/homepage/HomepageRefresher";
import { MarketSessionGate }  from "@/components/MarketSessionGate";
import { LiveIntelligenceFeed } from "@/components/market/LiveIntelligenceFeed";
import { API_BASE_URL as API } from "@/lib/api";
import { compareScoresDesc, impactToStyle } from "@/lib/scoring";

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
const getMIE          = cache(() => live(`${API}/api/mie/state`));
const getPremarket    = cache(() => live(`${API}/api/market/premarket`));
const getTopMovers    = cache(() => live(`${API}/api/market/top-movers`));
const getCalendar     = cache(() => live(`${API}/api/calendar/`));
const getIndices      = cache(() => live<any[]>(`${API}/api/indices/`));
const getLive         = cache(() => live(`${API}/api/market/live`));
const getSession      = cache(() => live(`${API}/api/market/session`));
const getRadar        = cache(() => revalidate(`${API}/api/radar/?page=1&page_size=4`, 120));
const getRecentEvents = cache(() => revalidate(`${API}/api/events/?sort_by=impact_score&page_size=10`, 300));

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

function moodColor(mood: string) {
  const m = (mood ?? "").toLowerCase();
  if (/bull|positive|strong|optimis/.test(m)) return "text-emerald-400";
  if (/bear|negative|weak|pessim/.test(m))   return "text-rose-400";
  return "text-amber-400";
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
  const [recentRaw, mie] = await Promise.all([getRecentEvents(), getMIE()]);
  const events = ((recentRaw as any)?.results ?? (recentRaw as any) ?? []) as any[];
  const top = [...events].sort((a, b) => compareScoresDesc(a.impact_score, b.impact_score))[0];
  const story = mie?.story;

  if (!top && !story) return null;

  const headline    = top?.title ?? story?.text?.split(/(?<=[.!?])\s+/)[0] ?? "AI is monitoring the market.";
  const description = top?.summary ?? story?.text ?? "";
  const style        = impactToStyle(top?.impact_score ?? null);
  const confPct = top?.confidence !== null && top?.confidence !== undefined
    ? Math.round(top.confidence * 100)
    : (story?.confidence ?? null);
  const mood     = story?.mood ?? "Neutral";
  const category = top?.category ?? "Market";

  return (
    <div className="flex h-full flex-col rounded-2xl border border-white/[0.07] bg-[#060e1e] p-5">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-violet-400" />
          <h3 className="text-[13px] font-black text-white">AI Market Brief</h3>
        </div>
        {story?.generated_at && <span className="text-[10px] text-slate-600">Updated {timeAgo(story.generated_at)}</span>}
      </div>

      <div className="mb-3 flex items-start gap-4">
        <div className="min-w-0 flex-1">
          <h4 className="text-[17px] font-black leading-snug text-white">{headline}</h4>
          {top && (
            <span className={`mt-1.5 inline-block rounded-full border px-2 py-0.5 text-[8px] font-black uppercase tracking-wider ${style.pill}`}>
              {style.label} Impact
            </span>
          )}
        </div>
        <EventIcon title={headline} category={category} />
      </div>

      {description && <p className="mb-4 text-[12px] leading-[1.6] text-slate-400 line-clamp-3">{description}</p>}

      <Link href="/market-intelligence"
        className="mb-4 inline-flex w-fit items-center gap-1.5 rounded-full bg-white px-4 py-2 text-[11px] font-bold text-slate-900 transition hover:bg-slate-100">
        View Full Intelligence <ArrowRight className="h-3 w-3" />
      </Link>

      <div className="mt-auto grid grid-cols-2 gap-3 border-t border-white/[0.06] pt-4 sm:grid-cols-4">
        <div>
          <p className="text-[9px] font-bold uppercase tracking-wider text-slate-600">Impact Score</p>
          <p className="text-[15px] font-black text-white">{top?.impact_score != null ? `${Math.round(top.impact_score)}/100` : "—"}</p>
          <p className={`text-[10px] font-semibold ${style.text}`}>{style.label}</p>
        </div>
        <div>
          <p className="text-[9px] font-bold uppercase tracking-wider text-slate-600">Confidence</p>
          <p className="text-[15px] font-black text-white">{confPct != null ? `${confPct}%` : "—"}</p>
          <p className="text-[10px] font-semibold text-sky-400">{confPct != null ? (confPct >= 75 ? "High" : confPct >= 50 ? "Moderate" : "Low") : "—"}</p>
        </div>
        <div>
          <p className="text-[9px] font-bold uppercase tracking-wider text-slate-600">Market Sentiment</p>
          <p className={`text-[15px] font-black ${moodColor(mood)}`}>{mood}</p>
          <p className="text-[10px] font-semibold text-slate-500">{story?.direction === "up" ? "Improving" : story?.direction === "down" ? "Weakening" : "Steady"}</p>
        </div>
        <div>
          <p className="text-[9px] font-bold uppercase tracking-wider text-slate-600">Category</p>
          <p className="text-[15px] font-black text-white truncate">{category}</p>
          <p className="text-[10px] font-semibold text-slate-500 truncate">{top?.event_type ?? "—"}</p>
        </div>
      </div>
    </div>
  );
}

async function TodaysBiggestEventsCard() {
  const recentRaw = await getRecentEvents();
  const events = ((recentRaw as any)?.results ?? (recentRaw as any) ?? []) as any[];

  const seen = new Set<string>();
  const merged: any[] = [];
  for (const e of events) {
    if (!e.id || seen.has(e.id)) continue;
    seen.add(e.id);
    merged.push(e);
  }
  merged.sort((a, b) => compareScoresDesc(a.impact_score, b.impact_score));
  const items = merged.slice(0, 3);

  return (
    <div className="flex h-full flex-col rounded-2xl border border-white/[0.07] bg-[#060e1e] p-5">
      <CardHeader title="Today's Biggest Events" href="/events" />
      {items.length === 0 ? (
        <p className="flex-1 py-6 text-center text-[12px] text-slate-600">No high-impact events yet today.</p>
      ) : (
        <div className="flex-1 space-y-3.5">
          {items.map((e, i) => {
            const style = impactToStyle(e.impact_score);
            return (
              <Link key={e.id} href={`/events/${e.id}` as any} className="group flex items-start gap-3">
                <div className="mt-0.5 flex w-11 shrink-0 flex-col items-start gap-1">
                  <span className="text-[9px] font-bold tabular-nums text-slate-600">
                    {e.date ? new Date(e.date).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" }) : ""}
                  </span>
                  {i === 0 && <span className="rounded-full bg-rose-500/15 px-1.5 py-0.5 text-[7px] font-black text-rose-400">LIVE</span>}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-[12px] font-bold leading-snug text-white group-hover:text-violet-200 transition line-clamp-2">{e.title}</p>
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
                      <p className="truncate text-[11px] font-bold text-white group-hover:text-violet-200 transition">{r.name}</p>
                      <p className="truncate text-[9px] text-slate-500">{r.reason}</p>
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
                <p className="text-[12px] font-bold leading-snug text-white group-hover:text-emerald-200 transition line-clamp-1">{r.title}</p>
                <p className="mt-0.5 text-[10px] text-slate-500 line-clamp-1">{r.summary}</p>
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
  const mie = await getMIE();
  const story = mie?.story;
  const feed  = (mie?.top_events ?? []) as any[];

  type RiskRow = { name: string; why: string; level: string };
  const risks: RiskRow[] = [];
  if (story?.risk) risks.push({ name: "Market Risk", why: story.risk.split(/[.!?]/)[0]?.trim() ?? story.risk, level: "High" });
  feed.filter((f: any) => f.urgency >= 5).slice(0, 2).forEach((f: any) =>
    risks.push({ name: f.headline.split(" ").slice(0, 6).join(" "), why: f.one_liner || f.headline, level: f.urgency >= 7 ? "High" : "Medium" }));

  return (
    <div className="flex h-full flex-col rounded-2xl border border-white/[0.07] bg-[#060e1e] p-5">
      <CardHeader title="Key Risks" href="/market-intelligence" />
      {risks.length === 0 ? (
        <p className="flex-1 py-6 text-center text-[12px] text-slate-600">No elevated risks detected.</p>
      ) : (
        <div className="flex-1 space-y-3">
          {risks.slice(0, 3).map((r, i) => (
            <Link key={i} href="/market-intelligence" className="group flex items-start gap-3">
              <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-rose-500/15">
                <Building2 className="h-4 w-4 text-rose-400" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-[12px] font-bold leading-snug text-white group-hover:text-rose-200 transition line-clamp-1">{r.name}</p>
                <p className="mt-0.5 text-[10px] text-slate-500 line-clamp-1">{r.why}</p>
              </div>
              <span className={`shrink-0 text-[11px] font-black ${r.level === "High" ? "text-rose-400" : "text-amber-400"}`}>{r.level}</span>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

async function ThemeStrengthCard() {
  const mie = await getMIE();
  const themes = ((mie?.sector_themes ?? []) as any[])
    .filter((t: any) => t.score !== null && t.score !== undefined)
    .sort((a: any, b: any) => b.score - a.score)
    .slice(0, 5);

  return (
    <div className="flex h-full flex-col rounded-2xl border border-white/[0.07] bg-[#060e1e] p-5">
      <CardHeader title="Theme Strength" href="/themes" />
      {themes.length === 0 ? (
        <p className="flex-1 py-6 text-center text-[12px] text-slate-600">Theme data is loading.</p>
      ) : (
        <div className="flex-1 space-y-3">
          {themes.map((t: any) => {
            const MomentumIcon = t.momentum === "rising" ? TrendingUp : t.momentum === "falling" ? TrendingDown : Minus;
            const momentumCls  = t.momentum === "rising" ? "text-emerald-400" : t.momentum === "falling" ? "text-rose-400" : "text-slate-500";
            const barColor     = t.score >= 75 ? "bg-emerald-500" : t.score >= 50 ? "bg-sky-500" : t.score >= 30 ? "bg-amber-500" : "bg-rose-500";
            return (
              <div key={t.name}>
                <div className="mb-1 flex items-center justify-between">
                  <span className="flex items-center gap-1 text-[11px] font-semibold text-slate-300">
                    <MomentumIcon className={`h-3 w-3 ${momentumCls}`} />
                    {t.name}
                  </span>
                  <span className="text-[11px] font-black tabular-nums text-white">{Math.round(t.score)}</span>
                </div>
                <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/[0.06]">
                  <div className={`h-full rounded-full ${barColor}`} style={{ width: `${Math.min(100, Math.max(0, t.score))}%` }} />
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// ROW 3 — Live Feed · AI Market Wrap (Morning) · Watch Tomorrow
// ═══════════════════════════════════════════════════════════════════════════════
async function AIMarketWrapCard() {
  const mie = await getMIE();
  const story = mie?.story;
  if (!story?.text) {
    return (
      <div className="flex h-full flex-col rounded-2xl border border-white/[0.07] bg-[#060e1e] p-5">
        <CardHeader title="AI Market Wrap" />
        <p className="flex-1 py-6 text-center text-[12px] text-slate-600">AI is preparing today's wrap.</p>
      </div>
    );
  }
  const isMorning = new Date(Date.now() + 5.5 * 3600_000).getUTCHours() < 12;

  return (
    <div className="flex h-full flex-col rounded-2xl border border-white/[0.07] bg-[#060e1e] p-5">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-violet-400" />
          <h3 className="text-[13px] font-black text-white">AI Market Wrap {isMorning ? "(Morning)" : ""}</h3>
        </div>
        {story.generated_at && <span className="text-[10px] text-slate-600">Updated {timeAgo(story.generated_at)}</span>}
      </div>
      <p className="flex-1 text-[12px] leading-[1.7] text-slate-400 line-clamp-6">{story.text}</p>
      <Link href="/market-intelligence"
        className="mt-4 inline-flex w-fit items-center gap-1.5 rounded-full border border-white/[0.1] bg-white/[0.04] px-4 py-2 text-[11px] font-bold text-white transition hover:bg-white/[0.08]">
        Read Full Wrap <ArrowRight className="h-3 w-3" />
      </Link>
    </div>
  );
}

async function WatchTomorrowCard() {
  const cal = await getCalendar();
  const nowMs = Date.now();
  const items = ((cal ?? []) as any[])
    .filter(e => { try { const d = new Date(e.date ?? e.event_date ?? e.datetime).getTime(); return d > nowMs && d <= nowMs + 7 * 86400_000; } catch { return false; } })
    .sort((a: any, b: any) => new Date(a.date ?? a.event_date ?? a.datetime).getTime() - new Date(b.date ?? b.event_date ?? b.datetime).getTime())
    .slice(0, 3);

  return (
    <div className="flex h-full flex-col rounded-2xl border border-white/[0.07] bg-[#060e1e] p-5">
      <CardHeader title="Watch Tomorrow" href="/market-intelligence?tab=economic-calendar" />
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

      {/* Row 1 — AI Market Brief · Today's Biggest Events · Market Snapshot */}
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[1.6fr_1fr_1fr]">
        <Suspense fallback={<Sk h={420} />}><AIMarketBriefCard /></Suspense>
        <Suspense fallback={<Sk h={420} />}><TodaysBiggestEventsCard /></Suspense>
        <Suspense fallback={<Sk h={420} />}><MarketSnapshotCard /></Suspense>
      </div>

      {/* Row 2 — Companies to Watch · Top Opportunities · Key Risks · Theme Strength */}
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
        <Suspense fallback={<Sk h={340} />}><CompaniesToWatchTable /></Suspense>
        <Suspense fallback={<Sk h={340} />}><TopOpportunitiesCard /></Suspense>
        <Suspense fallback={<Sk h={340} />}><KeyRisksCard /></Suspense>
        <Suspense fallback={<Sk h={340} />}><ThemeStrengthCard /></Suspense>
      </div>

      {/* Row 3 — Live Feed · AI Market Wrap (Morning) · Watch Tomorrow */}
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        <LiveIntelligenceFeed compact limit={4} />
        <Suspense fallback={<Sk h={280} />}><AIMarketWrapCard /></Suspense>
        <Suspense fallback={<Sk h={280} />}><WatchTomorrowCard /></Suspense>
      </div>

      {/* Background: 5-min story-hash poller + SSE session gate */}
      <HomepageRefresher />
      <MarketSessionGate />
    </div>
  );
}
