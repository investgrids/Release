import { Suspense, cache } from "react";
import Link from "next/link";
import {
  ArrowRight, ChevronRight, TrendingUp, TrendingDown, Minus,
  Calendar, Building2, BarChart3, Zap, BookOpen, MessageSquare,
  AlertCircle, Target, Activity, Globe,
} from "lucide-react";
import { HomepageRefresher } from "@/components/homepage/HomepageRefresher";
import { MarketSessionGate }  from "@/components/MarketSessionGate";

export const dynamic = "force-dynamic";
const API = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

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
const getMIE       = cache(() => live(`${API}/api/mie/state`));
const getPremarket = cache(() => live(`${API}/api/market/premarket`));
const getDashboard = cache(() => live(`${API}/api/dashboard/`));
const getCalendar  = cache(() => revalidate(`${API}/api/calendar/`, 3600));
const getIndices   = cache(() => live<any[]>(`${API}/api/indices/`));
const getLive      = cache(() => live(`${API}/api/market/live`));
const getRadar     = cache(() => revalidate(`${API}/api/radar/?page=1&page_size=4`, 120));

// ── Pure helpers ──────────────────────────────────────────────────────────────
function getIST() {
  const ms  = Date.now() + (5 * 60 + 30) * 60_000;
  const ist = new Date(ms);
  const h   = ist.getUTCHours(), m = ist.getUTCMinutes(), dow = ist.getUTCDay();
  const mins = h * 60 + m, isWd = dow >= 1 && dow <= 5;
  const greeting = h < 12 ? "Good Morning" : h < 17 ? "Good Afternoon" : "Good Evening";
  type S = "pre-market" | "live" | "after-market" | "weekend";
  const session: S = !isWd ? "weekend"
    : mins < 9 * 60 + 15  ? "pre-market"
    : mins <= 15 * 60 + 30 ? "live"
    : "after-market";
  return { session, greeting, h, m, dow, isWd };
}

function todayDateStr() {
  return new Date(Date.now() + 5.5 * 3600_000).toDateString();
}

function timeAgo(iso: string | null | undefined): string {
  if (!iso) return "";
  const mins = Math.floor((Date.now() - new Date(iso).getTime()) / 60000);
  return mins < 1 ? "just now" : mins < 60 ? `${mins}m ago` : `${Math.floor(mins / 60)}h ago`;
}

function pct(n: number | undefined | null) {
  if (n == null) return "—";
  return `${n >= 0 ? "+" : ""}${n.toFixed(2)}%`;
}

function moodColor(mood: string) {
  const m = (mood ?? "").toLowerCase();
  if (/bull|positive|strong|optimis/.test(m)) return "text-emerald-400";
  if (/bear|negative|weak|pessim/.test(m))   return "text-rose-400";
  return "text-amber-400";
}

function impactColor(imp: string | undefined) {
  const i = (imp ?? "").toLowerCase();
  if (/high/.test(i)) return { text: "text-rose-400", bg: "bg-rose-500/10 border-rose-500/20", dot: "bg-rose-400" };
  if (/medium/.test(i)) return { text: "text-amber-400", bg: "bg-amber-500/10 border-amber-500/20", dot: "bg-amber-400" };
  return { text: "text-sky-400", bg: "bg-sky-500/10 border-sky-500/20", dot: "bg-sky-400" };
}

// Skeleton
function Sk({ h = 200, r = "rounded-2xl" }: { h?: number; r?: string }) {
  return (
    <div className={`animate-pulse border border-white/[0.05] bg-white/[0.02] ${r}`} style={{ height: h }} />
  );
}

// Section label
function SectionHeader({ label, sub, href, linkLabel }: { label: string; sub?: string; href?: string; linkLabel?: string }) {
  return (
    <div className="mb-5 flex items-end justify-between">
      <div>
        <h2 className="text-[18px] font-black tracking-tight text-white">{label}</h2>
        {sub && <p className="mt-0.5 text-[12px] text-slate-500">{sub}</p>}
      </div>
      {href && linkLabel && (
        <Link href={href as any} className="flex items-center gap-1 text-[12px] font-semibold text-violet-400 hover:text-violet-300 transition">
          {linkLabel} <ChevronRight className="h-3.5 w-3.5" />
        </Link>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// SECTION 1 — AI Executive Brief
// ═══════════════════════════════════════════════════════════════════════════════
async function AIExecutiveBrief({ session, greeting }: { session: string; greeting: string }) {
  const [mie, cal, premarket] = await Promise.all([getMIE(), getCalendar(), getPremarket()]);
  const story   = mie?.story;
  const signals = mie?.signals;
  const isWeekend = session === "weekend";

  // 3-line narrative
  const sentences = (story?.text ?? "").split(/(?<=[.!?])\s+/).filter(Boolean);
  const line1 = sentences[0] ?? (session === "live" ? "Markets are open — AI is monitoring live conditions." : session === "pre-market" ? "Markets are preparing for today's open." : "Today's session has closed.");
  const line2 = sentences.slice(1, 3).join(" ") || "";

  // Watch items (max 3): top calendar events or top_events from MIE
  const todayStr = todayDateStr();
  const watchItems = ((cal ?? []) as any[])
    .filter(e => { try { return new Date(e.date ?? e.event_date ?? e.datetime).toDateString() === todayStr; } catch { return false; } })
    .sort((a: any, b: any) => (b.impact_score ?? 0) - (a.impact_score ?? 0))
    .slice(0, 3)
    .map((e: any) => ({
      title: e.title ?? e.event ?? "Market Event",
      impact: e.impact ?? (e.impact_score >= 7 ? "HIGH IMPACT" : e.impact_score >= 4 ? "MEDIUM" : "LOW"),
      sub: e.category ?? e.description?.split(/[.!?]/)[0]?.trim() ?? "",
    }));

  // If no calendar, fall back to MIE top_events
  const fallbackWatch = ((mie?.top_events ?? []) as any[])
    .slice(0, 3)
    .map((e: any) => ({
      title: (e.headline ?? "").split(" ").slice(0, 6).join(" "),
      impact: e.urgency >= 7 ? "HIGH IMPACT" : "MEDIUM",
      sub: e.one_liner ?? "",
    }));

  const watch = watchItems.length ? watchItems : fallbackWatch;

  const mood = story?.mood ?? "Neutral";
  const conf = story?.confidence;
  const riskLevel = signals?.risk_level ?? "MODERATE";
  const riskCls = riskLevel === "LOW" ? "text-emerald-400" : riskLevel === "HIGH" ? "text-rose-400" : "text-amber-400";

  const sessionBadge = session === "live"         ? { label: "LIVE", cls: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30" }
    : session === "pre-market"  ? { label: "PRE-MARKET", cls: "bg-sky-500/20 text-sky-400 border-sky-500/30" }
    : session === "weekend"     ? { label: "WEEKEND", cls: "bg-violet-500/20 text-violet-400 border-violet-500/30" }
    : { label: "AFTER MARKET", cls: "bg-slate-500/20 text-slate-400 border-slate-600/30" };

  const briefLabel = isWeekend ? "WEEKEND INTELLIGENCE" : "AI EXECUTIVE BRIEF";

  return (
    <section
      className="relative overflow-hidden rounded-3xl border border-white/[0.08]"
      style={{ background: "linear-gradient(135deg, #040d1e 0%, #08142a 60%, #050e1e 100%)", minHeight: 300 }}
    >
      {/* Ambient glows */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute -right-24 -top-24 h-96 w-96 rounded-full opacity-20"
          style={{ background: "radial-gradient(circle, rgba(251,191,36,0.3) 0%, transparent 70%)" }} />
        <div className="absolute -bottom-16 left-12 h-72 w-72 rounded-full opacity-15"
          style={{ background: "radial-gradient(circle, rgba(139,92,246,0.5) 0%, transparent 70%)" }} />
        {/* Subtle chart line */}
        <svg className="absolute right-0 bottom-0 w-[360px] opacity-40 hidden lg:block" viewBox="0 0 360 120" fill="none" preserveAspectRatio="none">
          <polyline points="0,100 60,88 120,92 180,62 240,48 300,30 360,18"
            stroke="url(#lgold)" strokeWidth="1.5" strokeLinecap="round" fill="none" />
          <linearGradient id="lgold" x1="0" x2="1" y1="0" y2="0">
            <stop offset="0%" stopColor="#f59e0b" stopOpacity="0" />
            <stop offset="100%" stopColor="#f59e0b" stopOpacity="0.9" />
          </linearGradient>
        </svg>
      </div>

      <div className="relative grid grid-cols-1 gap-0 lg:grid-cols-[1fr_320px]">
        {/* ── Left: Brief ──────────────────────────────────────── */}
        <div className="px-8 py-9 md:px-10">
          {/* Top meta row */}
          <div className="mb-5 flex items-center gap-3">
            <span className={`rounded-full border px-3 py-1 text-[9px] font-black uppercase tracking-widest ${sessionBadge.cls}`}>
              {sessionBadge.label}
            </span>
            <span className="rounded-full bg-amber-500/15 px-2.5 py-0.5 text-[9px] font-black uppercase tracking-widest text-amber-400">
              {briefLabel}
            </span>
            {story?.generated_at && (
              <span className="text-[10px] text-slate-600">Updated {timeAgo(story.generated_at)}</span>
            )}
          </div>

          {/* Greeting + headline */}
          <h1 className="mb-3 text-[28px] font-black leading-tight tracking-tight text-white md:text-[34px]">
            {greeting},&nbsp;<span className="text-amber-400">Investor</span>
          </h1>

          <p className="mb-1.5 max-w-[560px] text-[15px] font-medium leading-7 text-slate-200">{line1}</p>
          {line2 && (
            <p className="mb-6 max-w-[540px] text-[13px] leading-[1.7] text-slate-400">{line2}</p>
          )}
          {!line2 && <div className="mb-6" />}

          {/* 3 metric pills */}
          <div className="mb-7 flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2 rounded-full border border-white/[0.1] bg-white/[0.04] px-4 py-2 backdrop-blur-sm">
              <span className="h-2 w-2 rounded-full bg-violet-400" />
              <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">AI Confidence</span>
              <span className="text-[13px] font-black text-white">{conf ? `${conf}%` : "—"}</span>
            </div>
            <div className="flex items-center gap-2 rounded-full border border-white/[0.1] bg-white/[0.04] px-4 py-2 backdrop-blur-sm">
              <span className="h-2 w-2 rounded-full bg-emerald-400" />
              <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">Market Mood</span>
              <span className={`text-[13px] font-black ${moodColor(mood)}`}>{mood}</span>
            </div>
            <div className="flex items-center gap-2 rounded-full border border-white/[0.1] bg-white/[0.04] px-4 py-2 backdrop-blur-sm">
              <span className="h-2 w-2 rounded-full bg-amber-400" />
              <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">Risk Level</span>
              <span className={`text-[13px] font-black ${riskCls}`}>{riskLevel}</span>
            </div>
          </div>

          {/* CTAs */}
          <div className="flex flex-wrap items-center gap-3">
            <Link href="/market-intelligence"
              className="flex items-center gap-2 rounded-full bg-white px-5 py-2.5 text-[13px] font-bold text-slate-900 shadow-lg shadow-white/10 transition hover:bg-slate-100">
              Read Full Intelligence <ArrowRight className="h-3.5 w-3.5" />
            </Link>
            <Link
              href={`/ai-search?q=${encodeURIComponent("What should I focus on in the Indian market today?")}`}
              className="flex items-center gap-2 rounded-full border border-white/[0.15] bg-white/[0.05] px-5 py-2.5 text-[13px] font-semibold text-white transition hover:bg-white/[0.09]">
              <Zap className="h-3.5 w-3.5 text-violet-400" />
              Ask AI about today
            </Link>
          </div>
        </div>

        {/* ── Right: Watch Today ────────────────────────────────── */}
        <div className="border-l border-white/[0.06] px-6 py-9">
          <p className="mb-4 text-[10px] font-black uppercase tracking-[0.18em] text-slate-500">Watch Today</p>
          {watch.length === 0 ? (
            <p className="text-[12px] text-slate-600">No scheduled events found for today.</p>
          ) : (
            <div className="space-y-3">
              {watch.map((w, i) => {
                const ic = impactColor(w.impact);
                return (
                  <div key={i} className={`flex items-start gap-3 rounded-2xl border p-3.5 ${ic.bg}`}>
                    <div className={`mt-1 h-2 w-2 shrink-0 rounded-full ${ic.dot}`} />
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-[12px] font-bold text-white leading-snug line-clamp-1">{w.title}</span>
                      </div>
                      {w.sub && <p className="mt-0.5 text-[11px] text-slate-500 line-clamp-1">{w.sub}</p>}
                      <span className={`mt-1 inline-block text-[9px] font-black uppercase tracking-wider ${ic.text}`}>{w.impact}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
          <Link href="/events"
            className="mt-4 flex items-center gap-1 text-[11px] font-semibold text-slate-500 hover:text-slate-300 transition">
            View all events <ChevronRight className="h-3 w-3" />
          </Link>
        </div>
      </div>
    </section>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// SECTION 2 — Today's Market Overview
// ═══════════════════════════════════════════════════════════════════════════════
async function MarketOverview() {
  const [indices, live, mie, premarket] = await Promise.all([getIndices(), getLive(), getMIE(), getPremarket()]);

  const all     = (indices ?? live?.indices ?? []) as any[];
  const story   = mie?.story;
  const signals = mie?.signals;
  const breadth = live?.breadth;
  const sectorThemes = (mie?.sector_themes ?? []) as any[];
  const eventSectors = (mie?.event_sectors ?? []) as any[];

  // Resolve index cards
  const want = [
    { key: "nifty 50",   label: "NIFTY 50",   ctx: (v: number) => v > 24000 ? "Above key support levels." : "Testing major support." },
    { key: "sensex",     label: "SENSEX",     ctx: () => "Leading blue-chip index." },
    { key: "nifty bank", label: "BANK NIFTY", ctx: (v: number) => v > 50000 ? "Banking sector showing strength." : "Watching banking sector pressure." },
    { key: "india vix",  label: "INDIA VIX",  ctx: (v: number) => v < 12 ? "Low volatility. Calm conditions." : v < 18 ? "Moderate volatility. Normal conditions." : "Elevated volatility. Expect swings." },
  ];
  const indexCards = want.map(w => {
    const m = all.find((i: any) => (i.title ?? i.name ?? "").toLowerCase().includes(w.key.split(" ").at(-1)!));
    return m ? { ...w, value: m.value, change: m.change, positive: m.positive } : null;
  }).filter(Boolean) as any[];

  // Breadth bar data
  const tot = breadth ? (breadth.advances + breadth.declines + breadth.unchanged) || 1 : 0;
  const advPct = tot ? breadth!.advances / tot : 0.5;

  // Top / Weak sectors from MIE
  const topSec  = sectorThemes[0]?.name ?? eventSectors[0]?.name ?? "—";
  const weakSec = (sectorThemes.at(-1)?.name !== topSec ? sectorThemes.at(-1)?.name : sectorThemes.at(-2)?.name) ?? "—";

  // FII/DII — try premarket.fii_dii or MIE signals
  const fiiNet = (premarket as any)?.fii_dii?.fii_net;
  const diiNet = (premarket as any)?.fii_dii?.dii_net;
  const fiiStr = fiiNet != null
    ? `${fiiNet >= 0 ? "+" : ""}₹${Math.abs(fiiNet / 100).toFixed(0)}Cr`
    : signals?.mood === "Bullish" ? "Net buyers" : "Net sellers";

  const mood = story?.mood ?? signals?.mood ?? "Neutral";
  const isOpen = mie?.is_market_open;

  return (
    <section>
      <div className="mb-5 flex items-end justify-between">
        <div>
          <h2 className="text-[18px] font-black tracking-tight text-white">Today's Market Overview</h2>
          <p className="mt-0.5 text-[12px] text-slate-500">Every number explained — not just quoted</p>
        </div>
        <div className="flex items-center gap-2">
          {isOpen ? (
            <span className="flex items-center gap-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 px-3 py-1 text-[10px] font-bold text-emerald-400">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" /> Market is Open
            </span>
          ) : (
            <span className="rounded-full bg-slate-700/30 border border-slate-600/30 px-3 py-1 text-[10px] font-bold text-slate-500">Closed</span>
          )}
          <Link href="/market-intelligence" className="text-[12px] font-semibold text-violet-400 hover:text-violet-300 transition flex items-center gap-1">
            Full market <ChevronRight className="h-3.5 w-3.5" />
          </Link>
        </div>
      </div>

      <div className="rounded-2xl border border-white/[0.07] bg-[#060e1e] overflow-hidden">
        {/* Index cards */}
        <div className="grid grid-cols-2 divide-x divide-y divide-white/[0.05] xl:grid-cols-4">
          {(indexCards.length ? indexCards : want.map(w => ({ ...w, value: "—", change: "—", positive: true }))).slice(0, 4).map((c: any) => {
            const isVix = c.key?.includes("vix");
            const pos   = c.positive !== false;
            const val   = parseFloat(String(c.value).replace(/,/g, "")) || 0;
            return (
              <div key={c.key} className="p-5">
                <p className="mb-1 text-[9px] font-bold uppercase tracking-[0.12em] text-slate-600">{c.label}</p>
                <p className="text-[24px] font-black tabular-nums text-white leading-none">{c.value}</p>
                <p className={`mt-1 text-[12px] font-bold tabular-nums ${isVix ? "text-amber-400" : pos ? "text-emerald-400" : "text-rose-400"}`}>
                  {pos && !isVix ? "▲" : "▼"} {c.change}
                </p>
                <p className="mt-2.5 text-[11px] leading-[1.5] text-slate-500">{c.ctx(val)}</p>
              </div>
            );
          })}
        </div>

        {/* Second row: breadth + supplementary signals */}
        <div className="grid grid-cols-1 divide-y divide-white/[0.05] border-t border-white/[0.05] sm:grid-cols-2 xl:grid-cols-5 sm:divide-x sm:divide-y-0">

          {/* Market Breadth */}
          <div className="col-span-1 xl:col-span-2 p-5">
            <p className="mb-2 text-[9px] font-bold uppercase tracking-[0.12em] text-slate-600">Market Breadth</p>
            {breadth && tot > 0 ? (
              <>
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-[20px] font-black text-emerald-400 tabular-nums">{breadth.advances.toLocaleString()}</span>
                  <span className="text-slate-600 text-[14px]">vs</span>
                  <span className="text-[20px] font-black text-rose-400 tabular-nums">{breadth.declines.toLocaleString()}</span>
                </div>
                <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/[0.05] flex">
                  <div className="h-full bg-emerald-500" style={{ width: `${(advPct * 100).toFixed(0)}%` }} />
                  <div className="h-full bg-slate-600" style={{ width: `${((breadth.unchanged / tot) * 100).toFixed(0)}%` }} />
                  <div className="h-full flex-1 bg-rose-500" />
                </div>
                <p className="mt-2 text-[11px] text-slate-500">
                  {advPct > 0.65 ? "Advances outnumber declines 2:1. Strong breadth, broad participation."
                    : advPct > 0.55 ? "Majority advancing. Moderate conviction."
                    : advPct > 0.45 ? "Roughly balanced. Mixed conviction."
                    : "Declines dominating. Weak breadth."}
                </p>
              </>
            ) : (
              <p className="text-[13px] text-slate-600">—</p>
            )}
          </div>

          {/* Top Sector */}
          <div className="p-5">
            <p className="mb-2 text-[9px] font-bold uppercase tracking-[0.12em] text-slate-600">Top Sector</p>
            <p className="text-[16px] font-black text-emerald-400">{topSec}</p>
            <p className="mt-1.5 text-[11px] text-slate-500">Leading in event frequency and theme momentum today.</p>
          </div>

          {/* Weak Sector */}
          <div className="p-5">
            <p className="mb-2 text-[9px] font-bold uppercase tracking-[0.12em] text-slate-600">Weak Sector</p>
            <p className="text-[16px] font-black text-rose-400">{weakSec}</p>
            <p className="mt-1.5 text-[11px] text-slate-500">Lowest theme momentum — approach with caution.</p>
          </div>

          {/* FII/DII + Mood */}
          <div className="p-5">
            <p className="mb-2 text-[9px] font-bold uppercase tracking-[0.12em] text-slate-600">FII / DII · Market Mood</p>
            <p className="text-[16px] font-black text-sky-400">{fiiStr}</p>
            <p className={`mt-1 text-[13px] font-bold ${moodColor(mood)}`}>{mood}</p>
            <p className="mt-1.5 text-[11px] text-slate-500">Institutional flows shape the broader trend.</p>
          </div>
        </div>
      </div>
    </section>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// SECTION 3 — Why Today Matters
// ═══════════════════════════════════════════════════════════════════════════════
async function WhyTodayMatters() {
  const [premarket, cal, mie] = await Promise.all([getPremarket(), getCalendar(), getMIE()]);

  type Card = {
    icon: React.ReactNode;
    label: string;
    value: string;
    change: string;
    up: boolean | null;
    why: string;
  };

  const cards: Card[] = [];

  // Gift Nifty
  const gn = premarket?.gift_nifty;
  if (gn) {
    const up = (gn.change_pct ?? gn.premium_pct ?? 0) >= 0;
    cards.push({
      icon: <TrendingUp className="h-4 w-4 text-amber-400" />,
      label: "GIFT NIFTY",
      value: gn.value ? String(gn.value) : "—",
      change: gn.premium_pct != null ? `${gn.premium_pct >= 0 ? "+" : ""}${gn.premium_pct.toFixed(2)}% premium` : (gn.change_str ?? ""),
      up,
      why: up ? "Positive opening indicated for Nifty. Expect early strength." : "Cautious opening. Watch 9:15 AM gap.",
    });
  }

  // Global Markets
  const usArr = (premarket?.us ?? []) as any[];
  const sp = usArr.find((u: any) => /S&P|SPX/i.test(u.name ?? "")) ?? usArr[0];
  if (sp) {
    const up = sp.positive !== false;
    cards.push({
      icon: <Globe className="h-4 w-4 text-sky-400" />,
      label: "GLOBAL MARKETS",
      value: up ? "Positive" : "Negative",
      change: sp.change_str ?? "",
      up,
      why: `US markets ${up ? "ended higher." : "declined."} ${up ? "Positive cues for Asian session." : "Cautious tone in Asian open."}`,
    });
  }

  // Crude Oil
  const oil = ((premarket?.commodities ?? []) as any[]).find((c: any) => /brent|crude/i.test(c.name ?? ""));
  if (oil) {
    const up = oil.positive !== false;
    cards.push({
      icon: <Activity className="h-4 w-4 text-orange-400" />,
      label: "CRUDE OIL",
      value: oil.value ? `$${oil.value}` : "—",
      change: oil.change_str ?? String(oil.change ?? ""),
      up,
      why: up ? "Rising oil pressures Auto, Airlines. Monitor input-cost inflation." : "Falling oil benefits Auto, Airlines, Paint sectors.",
    });
  }

  // USD/INR
  const usdinr = ((premarket?.currencies ?? []) as any[]).find((c: any) => /USD.?INR/i.test(c.name ?? ""));
  if (usdinr) {
    cards.push({
      icon: <BarChart3 className="h-4 w-4 text-green-400" />,
      label: "USD / INR",
      value: usdinr.value ? `₹${usdinr.value}` : "—",
      change: usdinr.change_str ?? String(usdinr.change ?? ""),
      up: null,
      why: "Rupee stability supports FII flows and reduces import-cost pressure.",
    });
  }

  // Today's Biggest Event
  const todayStr = todayDateStr();
  const topEvt = ((cal ?? []) as any[])
    .filter(e => { try { return new Date(e.date ?? e.event_date ?? e.datetime).toDateString() === todayStr; } catch { return false; } })
    .sort((a: any, b: any) => (b.impact_score ?? 0) - (a.impact_score ?? 0))[0];
  if (topEvt) {
    const ic = impactColor(topEvt.impact ?? (topEvt.impact_score >= 7 ? "high" : "medium"));
    cards.push({
      icon: <Calendar className="h-4 w-4" />,
      label: "TODAY'S BIGGEST EVENT",
      value: (topEvt.title ?? topEvt.event ?? "").split(" ").slice(0, 5).join(" "),
      change: topEvt.impact ?? (topEvt.impact_score >= 7 ? "HIGH IMPACT" : "MEDIUM"),
      up: null,
      why: topEvt.description?.split(/[.!?]/)[0]?.trim() ?? "This event may trigger significant market moves. Track closely.",
    });
  }

  // Fallback from MIE top_events if cards are short
  if (cards.length < 2 && mie?.top_events?.length) {
    const ev = (mie.top_events as any[])[0];
    if (ev) {
      cards.push({
        icon: <AlertCircle className="h-4 w-4 text-rose-400" />,
        label: "TOP EVENT",
        value: (ev.headline ?? "").split(" ").slice(0, 4).join(" "),
        change: `Urgency ${ev.urgency ?? "—"}/10`,
        up: ev.sentiment === "bullish" ? true : ev.sentiment === "bearish" ? false : null,
        why: ev.one_liner ?? ev.headline ?? "",
      });
    }
  }

  if (!cards.length) return null;

  return (
    <section>
      <SectionHeader label="Why Today Matters" sub="The five drivers every investor must understand today" href="/market-intelligence" linkLabel="Full Market" />
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-5">
        {cards.slice(0, 5).map((c, i) => (
          <div key={i} className="rounded-2xl border border-white/[0.07] bg-[#060e1e] p-5 transition hover:border-white/[0.12] hover:bg-[#081224]">
            <div className="mb-4 flex items-center justify-between">
              <div className="flex h-8 w-8 items-center justify-center rounded-xl border border-white/[0.08] bg-white/[0.04]">
                {c.icon}
              </div>
              {c.up === true  && <TrendingUp   className="h-3.5 w-3.5 text-emerald-400" />}
              {c.up === false && <TrendingDown  className="h-3.5 w-3.5 text-rose-400" />}
              {c.up === null  && <Minus         className="h-3.5 w-3.5 text-slate-600" />}
            </div>
            <p className="mb-0.5 text-[9px] font-bold uppercase tracking-[0.12em] text-slate-500">{c.label}</p>
            <p className="text-[17px] font-black leading-tight text-white">{c.value}</p>
            {c.change && (
              <p className={`mt-0.5 text-[11px] font-semibold tabular-nums ${c.up === true ? "text-emerald-400" : c.up === false ? "text-rose-400" : "text-slate-500"}`}>
                {c.change}
              </p>
            )}
            <p className="mt-3 text-[11px] leading-[1.6] text-slate-500">{c.why}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// SECTION 4 — High Impact Events
// ═══════════════════════════════════════════════════════════════════════════════
async function HighImpactEvents() {
  const [cal, mie] = await Promise.all([getCalendar(), getMIE()]);
  const todayStr = todayDateStr();

  type Ev = { id: string; title: string; time: string; impact: string; sectors: string[]; companies: string[]; href: string };

  // Today's calendar events
  const calEvents: Ev[] = ((cal ?? []) as any[])
    .filter(e => { try { return new Date(e.date ?? e.event_date ?? e.datetime).toDateString() === todayStr; } catch { return false; } })
    .sort((a: any, b: any) => (b.impact_score ?? 0) - (a.impact_score ?? 0))
    .slice(0, 5)
    .map((e: any) => ({
      id: e.id ?? String(Math.random()),
      title: e.title ?? e.event ?? "Market Event",
      time: e.time ? `${e.time} IST` : "Today",
      impact: e.impact ?? (e.impact_score >= 7 ? "HIGH IMPACT" : e.impact_score >= 4 ? "MEDIUM IMPACT" : "LOW"),
      sectors: (e.sectors ?? e.affected_sectors ?? []).slice(0, 3),
      companies: (e.companies ?? e.affected_companies ?? []).slice(0, 3),
      href: e.id ? `/events/${e.id}` : "/events",
    }));

  // Fill from MIE top_events if we don't have enough
  const mieEvents: Ev[] = (calEvents.length < 3)
    ? ((mie?.top_events ?? []) as any[])
        .filter((e: any) => e.urgency >= 5)
        .slice(0, 5 - calEvents.length)
        .map((e: any) => ({
          id: e.id ?? String(Math.random()),
          title: (e.headline ?? "Market Event").split(" ").slice(0, 8).join(" "),
          time: "Today",
          impact: e.urgency >= 7 ? "HIGH IMPACT" : "MEDIUM IMPACT",
          sectors: (e.sectors ?? []).slice(0, 3),
          companies: (e.tickers ?? []).slice(0, 3),
          href: `/events/${e.event_id ?? ""}`,
        }))
    : [];

  const events = [...calEvents, ...mieEvents].slice(0, 5);

  if (!events.length) return (
    <section>
      <SectionHeader label="High Impact Events" sub="Events that move markets today" href="/events" linkLabel="All Events" />
      <div className="rounded-2xl border border-white/[0.06] bg-[#060e1e] p-8 text-center">
        <Calendar className="mx-auto h-8 w-8 text-slate-700 mb-3" />
        <p className="text-[13px] text-slate-600">No high-impact events scheduled. Check back at market open.</p>
      </div>
    </section>
  );

  return (
    <section>
      <SectionHeader label="High Impact Events" sub="Events that deserve your attention today" href="/events" linkLabel="View All" />
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-5">
        {events.map((ev, i) => {
          const ic = impactColor(ev.impact);
          return (
            <Link key={ev.id} href={ev.href as any}
              className="group flex flex-col rounded-2xl border border-white/[0.07] bg-[#060e1e] p-4 transition hover:border-white/[0.14] hover:bg-[#081224]">

              {/* Impact badge */}
              <div className={`mb-3 self-start rounded-full border px-2.5 py-1 text-[9px] font-black uppercase tracking-wider ${ic.bg} ${ic.text}`}>
                {ev.impact}
              </div>

              <h3 className="mb-1 text-[13px] font-bold leading-snug text-white group-hover:text-violet-200 transition line-clamp-2">{ev.title}</h3>
              <p className="mb-3 text-[11px] text-slate-500">{ev.time}</p>

              {/* Sectors */}
              {ev.sectors.length > 0 && (
                <div className="mb-2 flex flex-wrap gap-1">
                  {ev.sectors.map((s: string, j: number) => (
                    <span key={j} className="rounded-full bg-white/[0.04] border border-white/[0.06] px-2 py-0.5 text-[9px] text-slate-500">{s}</span>
                  ))}
                </div>
              )}

              <div className="mt-auto flex items-center gap-1 pt-2 text-[10px] font-semibold text-violet-400 group-hover:text-violet-300 transition">
                Open Event <ChevronRight className="h-3 w-3" />
              </div>
            </Link>
          );
        })}
      </div>
    </section>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// SECTION 5 — Companies to Watch
// ═══════════════════════════════════════════════════════════════════════════════
const AVATAR_GRADIENT = [
  "from-indigo-600 to-indigo-800",
  "from-sky-600 to-sky-800",
  "from-emerald-600 to-emerald-800",
  "from-violet-600 to-violet-800",
  "from-rose-600 to-rose-800",
  "from-amber-600 to-amber-800",
];

async function CompaniesToWatch() {
  const [dashboard, mie] = await Promise.all([getDashboard(), getMIE()]);

  // Prefer gainers (have meaningful % change), then losers, then active
  const gainers = ((dashboard?.top_movers?.gainers ?? []) as any[]);
  const losers  = ((dashboard?.top_movers?.losers  ?? []) as any[]);
  const active  = ((dashboard?.top_movers?.active  ?? []) as any[]);

  // Build a deduped merged list: gainers first, then losers, then active (by volume)
  const seen = new Set<string>();
  const merged: any[] = [];
  for (const c of [...gainers, ...losers, ...active]) {
    if (c.ticker && !seen.has(c.ticker)) { seen.add(c.ticker); merged.push(c); }
  }

  const topEvents = (mie?.top_events ?? []) as any[];

  // MIE-derived fallback companies from top_events tickers
  const mieCompanies: any[] = [];
  if (merged.length < 3) {
    for (const ev of topEvents) {
      for (const t of (ev.tickers ?? []).slice(0, 2)) {
        if (!seen.has(t)) {
          seen.add(t);
          mieCompanies.push({
            ticker: t,
            company: t,
            value: "—",
            subtitle: ev.one_liner?.split(/[.!?]/)[0]?.trim() ?? "MIE signal",
            positive: ev.sentiment !== "bearish",
            _mie_event: ev,
          });
        }
      }
      if (mieCompanies.length >= 4) break;
    }
  }

  const companies = [...merged, ...mieCompanies].slice(0, 6);

  const getWhy = (ticker: string, existing_event?: any) => {
    if (existing_event) return existing_event.one_liner ?? "";
    return topEvents.find((e: any) =>
      (e.tickers ?? []).map((t: string) => t.toUpperCase()).includes(ticker.toUpperCase())
    );
  };

  return (
    <section>
      <SectionHeader
        label="Companies to Watch"
        sub="Companies that matter to investors today"
        href="/companies"
        linkLabel="View All"
      />

      {companies.length === 0 ? (
        <div className="rounded-2xl border border-white/[0.06] bg-[#060e1e] p-8 text-center">
          <Building2 className="mx-auto h-8 w-8 text-slate-700 mb-3" />
          <p className="text-[13px] text-slate-600">Market data is loading. Companies will appear once the market opens.</p>
          <Link href="/companies" className="mt-3 inline-flex items-center gap-1 text-[12px] font-semibold text-violet-400 hover:text-violet-300 transition">
            Browse all companies <ChevronRight className="h-3.5 w-3.5" />
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-6">
          {companies.map((c: any, i: number) => {
            const pos    = c.positive !== false;
            const match  = getWhy(c.ticker, c._mie_event);
            const why    = (typeof match === "object" && match !== null)
              ? (match.one_liner ?? "High institutional interest. Monitor for sector-driven momentum.")
              : (typeof match === "string" ? match : "High institutional interest. Monitor for sector-driven momentum.");
            const sector  = (typeof match === "object" && match !== null) ? (match.sectors?.[0] ?? "") : "";
            const conf    = (typeof match === "object" && match !== null && match.confidence)
              ? `${match.confidence}%` : null;
            // value = change% for gainers/losers; for active it's volume; for MIE it's "—"
            const displayVal  = c.value ?? "—";
            const displaySub  = c.subtitle ?? "";

            return (
              <Link key={c.ticker ?? i} href={`/companies/${c.ticker}` as any}
                className="group flex flex-col rounded-2xl border border-white/[0.07] bg-[#060e1e] p-4 transition hover:border-violet-500/20 hover:bg-[#0a102c]">

                {/* Avatar + ticker */}
                <div className="mb-3 flex items-center gap-2.5">
                  <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br text-[11px] font-black text-white ${AVATAR_GRADIENT[i % 6]}`}>
                    {(c.ticker ?? "??").slice(0, 2)}
                  </div>
                  <div className="min-w-0">
                    <p className="truncate text-[12px] font-bold text-white group-hover:text-violet-200 transition">{c.ticker}</p>
                    {sector && <p className="text-[9px] text-slate-600 uppercase tracking-wide">{sector}</p>}
                  </div>
                </div>

                {/* Value */}
                <p className={`text-[17px] font-black tabular-nums leading-none ${pos ? "text-emerald-400" : "text-rose-400"}`}>{displayVal}</p>
                {displaySub && <p className={`mt-0.5 mb-3 text-[11px] font-semibold tabular-nums ${pos ? "text-emerald-500/80" : "text-rose-500/80"}`}>{displaySub}</p>}
                {!displaySub && <div className="mb-3" />}

                {/* Why */}
                <p className="line-clamp-3 text-[10px] leading-[1.5] text-slate-500">
                  <span className="font-bold text-slate-400">Why: </span>{why}
                </p>

                {conf && (
                  <p className="mt-2 text-[10px] text-slate-600">Confidence <span className="font-bold text-violet-400">{conf}</span></p>
                )}

                <div className="mt-auto pt-3 flex items-center gap-1 text-[10px] font-semibold text-violet-400 group-hover:text-violet-300 transition">
                  Open Analysis <ChevronRight className="h-3 w-3" />
                </div>
              </Link>
            );
          })}
        </div>
      )}
    </section>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// SECTION 6 — Opportunities & Risks
// ═══════════════════════════════════════════════════════════════════════════════
async function OpportunitiesAndRisks() {
  const [mie, radar] = await Promise.all([getMIE(), getRadar()]);
  const story    = mie?.story;
  const feed     = (mie?.top_events ?? []) as any[];
  const radarItems = ((radar as any)?.items ?? []) as any[];

  type OppRow = { name: string; why: string; conf: number; sectors: string[] };
  type RiskRow = { name: string; why: string; level: string; sectors: string[] };

  const opps: OppRow[] = [];
  const risks: RiskRow[] = [];

  if (story?.opportunity)
    opps.push({ name: "AI Market Signal", why: story.opportunity.split(/[.!?]/)[0]?.trim() ?? story.opportunity, conf: story.confidence ?? 78, sectors: [] });
  radarItems.forEach((r: any) =>
    opps.push({ name: r.title ?? r.theme, why: (r.summary ?? r.reason ?? "").split(/[.!?]/)[0]?.trim() || "", conf: Math.round(r.opportunity_score ?? 75), sectors: (r.sectors ?? []).slice(0, 2) }));

  if (story?.risk)
    risks.push({ name: "Market Risk", why: story.risk.split(/[.!?]/)[0]?.trim() ?? story.risk, level: "High", sectors: [] });
  feed.filter((f: any) => f.urgency >= 5).slice(0, 4).forEach((f: any) =>
    risks.push({ name: f.headline.split(" ").slice(0, 6).join(" "), why: f.one_liner || f.headline, level: f.urgency >= 7 ? "High" : "Medium", sectors: (f.sectors ?? []).slice(0, 2) }));

  return (
    <section>
      <SectionHeader label="Opportunities & Risks" sub="Where to look — and what to avoid" />
      <div className="grid gap-4 lg:grid-cols-2">

        {/* Opportunities */}
        <div className="rounded-2xl border border-emerald-500/[0.12] bg-[#060e1e] p-5">
          <div className="mb-4 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-emerald-400" />
              <h3 className="text-[12px] font-black uppercase tracking-[0.1em] text-white">Top Opportunities</h3>
            </div>
            <Link href="/opportunity-radar" className="text-[11px] font-semibold text-emerald-400 hover:text-emerald-300 transition flex items-center gap-0.5">
              View All <ChevronRight className="h-3 w-3" />
            </Link>
          </div>
          <div className="space-y-2">
            {(opps.length ? opps : [{ name: "Scanning markets…", why: "AI is identifying today's opportunities.", conf: 0, sectors: [] }]).slice(0, 4).map((o, i) => (
              <Link key={i} href="/opportunity-radar"
                className="flex items-start justify-between gap-3 rounded-xl border border-white/[0.05] bg-white/[0.02] px-4 py-3 transition hover:border-emerald-500/20 hover:bg-emerald-500/[0.03]">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <span className="text-[12px] font-bold text-emerald-400">{`${i + 1}. ${o.name}`}</span>
                    {o.sectors.map((s: string) => (
                      <span key={s} className="rounded-full bg-emerald-500/10 px-1.5 py-0.5 text-[8px] text-emerald-400">{s}</span>
                    ))}
                  </div>
                  <p className="mt-0.5 line-clamp-1 text-[11px] text-slate-500">{o.why}</p>
                </div>
                {o.conf > 0 && (
                  <span className="shrink-0 text-[11px] tabular-nums">
                    <span className="text-slate-600">Conf. </span>
                    <span className="font-black text-emerald-400">{o.conf}%</span>
                  </span>
                )}
              </Link>
            ))}
          </div>
        </div>

        {/* Risks */}
        <div className="rounded-2xl border border-rose-500/[0.12] bg-[#060e1e] p-5">
          <div className="mb-4 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-rose-400" />
              <h3 className="text-[12px] font-black uppercase tracking-[0.1em] text-white">Key Risks</h3>
            </div>
            <Link href="/market-intelligence" className="text-[11px] font-semibold text-rose-400 hover:text-rose-300 transition flex items-center gap-0.5">
              Monitor <ChevronRight className="h-3 w-3" />
            </Link>
          </div>
          <div className="space-y-2">
            {(risks.length ? risks : [{ name: "Monitoring…", why: "AI is watching for risk signals.", level: "Low", sectors: [] }]).slice(0, 4).map((r, i) => (
              <Link key={i} href="/market-intelligence"
                className="flex items-start justify-between gap-3 rounded-xl border border-white/[0.05] bg-white/[0.02] px-4 py-3 transition hover:border-rose-500/20 hover:bg-rose-500/[0.03]">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <span className="text-[12px] font-bold text-rose-400">{`${i + 1}. ${r.name}`}</span>
                    {r.sectors.map((s: string) => (
                      <span key={s} className="rounded-full bg-rose-500/10 px-1.5 py-0.5 text-[8px] text-rose-400">{s}</span>
                    ))}
                  </div>
                  <p className="mt-0.5 line-clamp-1 text-[11px] text-slate-500">{r.why}</p>
                </div>
                <span className={`shrink-0 text-[11px] font-black ${r.level === "High" ? "text-rose-400" : r.level === "Medium" ? "text-amber-400" : "text-slate-500"}`}>
                  {r.level}
                </span>
              </Link>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// SECTION 7 — Continue Research (3 cards)
// ═══════════════════════════════════════════════════════════════════════════════
function ContinueResearch() {
  const items = [
    {
      icon: <Calendar className="h-6 w-6" />,
      color: "text-sky-400",
      border: "hover:border-sky-500/30",
      glow: "hover:bg-sky-500/[0.03]",
      title: "Explore Today's Events",
      desc: "See all high-impact events and their potential market impact.",
      cta: "Explore Events",
      href: "/events",
    },
    {
      icon: <BookOpen className="h-6 w-6" />,
      color: "text-violet-400",
      border: "hover:border-violet-500/30",
      glow: "hover:bg-violet-500/[0.03]",
      title: "Read Today's Intelligence",
      desc: "Deep dive into today's market story, opportunities, risks and more.",
      cta: "Read Intelligence",
      href: "/market-intelligence",
    },
    {
      icon: <MessageSquare className="h-6 w-6" />,
      color: "text-emerald-400",
      border: "hover:border-emerald-500/30",
      glow: "hover:bg-emerald-500/[0.03]",
      title: "Ask AI Anything",
      desc: "Get instant, intelligent answers to any market question.",
      cta: "Ask AI",
      href: "/ai-search",
    },
  ];

  return (
    <section className="pb-4">
      <SectionHeader label="Continue Your Research" sub="Go deeper into any part of today's market story" />
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        {items.map((item, i) => (
          <Link key={i} href={item.href as any}
            className={`group flex flex-col rounded-2xl border border-white/[0.07] bg-[#060e1e] p-6 transition ${item.border} ${item.glow}`}>
            <div className={`mb-4 flex h-11 w-11 items-center justify-center rounded-2xl border border-white/[0.08] bg-white/[0.04] ${item.color}`}>
              {item.icon}
            </div>
            <h3 className="mb-1.5 text-[15px] font-bold text-white group-hover:text-white transition">{item.title}</h3>
            <p className="flex-1 text-[12px] leading-[1.6] text-slate-500">{item.desc}</p>
            <div className={`mt-4 flex items-center gap-1.5 text-[12px] font-semibold ${item.color} transition`}>
              {item.cta} <ArrowRight className="h-3.5 w-3.5" />
            </div>
          </Link>
        ))}
      </div>
    </section>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// TICKER BAR (fixed bottom)
// ═══════════════════════════════════════════════════════════════════════════════
async function TickerBar() {
  const raw = ((await getIndices()) ?? []) as any[];
  const items = raw.length ? raw : [
    { title: "NIFTY 50",   value: "—", change: "—", positive: true },
    { title: "SENSEX",     value: "—", change: "—", positive: true },
    { title: "BANK NIFTY", value: "—", change: "—", positive: true },
    { title: "INDIA VIX",  value: "—", change: "—", positive: false },
  ];
  return (
    <div className="fixed bottom-0 left-0 right-0 z-40 border-t border-white/[0.05] bg-[#020617]/95 backdrop-blur-xl">
      <div className="mx-auto flex max-w-[1600px] items-center gap-8 overflow-x-auto px-6 py-2 scrollbar-hide">
        <span className="shrink-0 text-[8px] font-black uppercase tracking-[0.18em] text-slate-700">LIVE</span>
        {items.map((idx: any, i: number) => (
          <div key={i} className="flex shrink-0 items-center gap-2">
            <span className="text-[9px] font-semibold uppercase tracking-wider text-slate-600">{idx.title ?? idx.name}</span>
            <span className="text-[11px] font-bold tabular-nums text-slate-300">{idx.value}</span>
            <span className={`text-[10px] font-semibold tabular-nums ${idx.positive ? "text-emerald-400" : "text-rose-400"}`}>{idx.change}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// ROOT PAGE
// ═══════════════════════════════════════════════════════════════════════════════
export default function HomePage() {
  const { session, greeting } = getIST();

  return (
    <div className="mx-auto max-w-[1600px] space-y-10 px-5 py-7 pb-20 md:px-8">

      {/* §1 — AI Executive Brief */}
      <Suspense fallback={<Sk h={320} />}>
        <AIExecutiveBrief session={session} greeting={greeting} />
      </Suspense>

      {/* §2 — Today's Market Overview */}
      <Suspense fallback={<Sk h={260} />}>
        <MarketOverview />
      </Suspense>

      {/* §3 — Why Today Matters */}
      <Suspense fallback={<Sk h={200} />}>
        <WhyTodayMatters />
      </Suspense>

      {/* §4 — High Impact Events */}
      <Suspense fallback={<Sk h={220} />}>
        <HighImpactEvents />
      </Suspense>

      {/* §5 — Companies to Watch */}
      <Suspense fallback={<Sk h={240} />}>
        <CompaniesToWatch />
      </Suspense>

      {/* §6 — Opportunities & Risks */}
      <Suspense fallback={<Sk h={240} />}>
        <OpportunitiesAndRisks />
      </Suspense>

      {/* §7 — Continue Research */}
      <ContinueResearch />

      {/* Fixed: ticker bar */}
      <Suspense fallback={null}>
        <TickerBar />
      </Suspense>

      {/* Background: 5-min story-hash poller + SSE session gate */}
      <HomepageRefresher />
      <MarketSessionGate />
    </div>
  );
}
