import { Suspense, cache } from "react";
import Link from "next/link";
import {
  ArrowRight, ChevronRight, TrendingUp, TrendingDown, Minus,
  Calendar, Building2, BarChart3, Zap, BookOpen, MessageSquare,
  AlertCircle, Globe, Shield, Droplets, Cloud, Landmark,
  DollarSign, FlameKindling, Cpu, Wheat,
} from "lucide-react";
import { HomepageRefresher } from "@/components/homepage/HomepageRefresher";
import { MarketSessionGate }  from "@/components/MarketSessionGate";
import { API_BASE_URL as API } from "@/lib/api";
import { compareScoresDesc } from "@/lib/scoring";

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
const getRadar        = cache(() => revalidate(`${API}/api/radar/?page=1&page_size=4`, 120));
const getRecentEvents = cache(() => revalidate(`${API}/api/events/?sort_by=impact_score&page_size=10`, 300));

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

// ── Mini sparkline ────────────────────────────────────────────────────────────
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

// Generates 12 synthetic intraday points from a seed + direction
function syntheticChart(seed: string, positive: boolean): number[] {
  let v = 100, h2 = 0;
  for (let i = 0; i < seed.length; i++) h2 = (h2 * 31 + seed.charCodeAt(i)) & 0x7fffffff;
  const pts: number[] = [v];
  for (let i = 1; i < 12; i++) {
    h2 = (h2 * 1664525 + 1013904223) & 0x7fffffff;
    v += (h2 / 0x7fffffff - 0.47) * 1.4 + (positive ? 0.14 : -0.14);
    pts.push(Math.max(95, Math.min(105, v)));
  }
  return pts;
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
  if (/tech|it |software|digital|ai |chip/.test(t))
    return <div className={`${base} bg-cyan-500/20`}><Cpu className="h-4 w-4 text-cyan-400"/></div>;
  if (/wheat|grain|food|fmcg|fertiliz/.test(t))
    return <div className={`${base} bg-green-500/20`}><Wheat className="h-4 w-4 text-green-400"/></div>;
  if (/dollar|rupee|forex|currency|exchange/.test(t))
    return <div className={`${base} bg-teal-500/20`}><DollarSign className="h-4 w-4 text-teal-400"/></div>;
  if (/infra|power|energy|coal|gas/.test(t))
    return <div className={`${base} bg-amber-500/20`}><FlameKindling className="h-4 w-4 text-amber-400"/></div>;
  return <div className={`${base} bg-slate-500/20`}><Calendar className="h-4 w-4 text-slate-400"/></div>;
}

// Product illustration — candlestick chart with AI trend overlay
function ProductGlyphSVG() {
  return (
    <svg viewBox="0 0 500 360" fill="none" xmlns="http://www.w3.org/2000/svg" className="w-full h-full" preserveAspectRatio="xMidYMid meet">
      <defs>
        <linearGradient id="pG" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#a5b4fc" stopOpacity="0.95"/>
          <stop offset="100%" stopColor="#3b82f6" stopOpacity="0.80"/>
        </linearGradient>
        <linearGradient id="areaG" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor="#6366f1" stopOpacity="0.55"/>
          <stop offset="100%" stopColor="#6366f1" stopOpacity="0.0"/>
        </linearGradient>
      </defs>

      {/* Grid lines */}
      <line x1="52" y1="74" x2="458" y2="74" stroke="#818cf8" strokeOpacity="0.10" strokeWidth="1"/>
      <line x1="52" y1="134" x2="458" y2="134" stroke="#818cf8" strokeOpacity="0.10" strokeWidth="1"/>
      <line x1="52" y1="194" x2="458" y2="194" stroke="#818cf8" strokeOpacity="0.10" strokeWidth="1"/>
      <line x1="52" y1="254" x2="458" y2="254" stroke="#818cf8" strokeOpacity="0.08" strokeWidth="1"/>
      <line x1="52" y1="60" x2="52" y2="310" stroke="#818cf8" strokeOpacity="0.12" strokeWidth="1"/>

      {/* Candlesticks — 12 candles on a bullish trend */}
      {/* c1 bear */ }<line x1="76" y1="186" x2="76" y2="208" stroke="#fb7185" strokeOpacity="0.75" strokeWidth="1.5"/><rect x="70" y="190" width="12" height="10" rx="2" fill="#f43f5e" fillOpacity="0.75"/>
      {/* c2 bull */ }<line x1="106" y1="170" x2="106" y2="195" stroke="#34d399" strokeOpacity="0.75" strokeWidth="1.5"/><rect x="100" y="172" width="12" height="18" rx="2" fill="#10b981" fillOpacity="0.80"/>
      {/* c3 bear */ }<line x1="136" y1="162" x2="136" y2="186" stroke="#fb7185" strokeOpacity="0.75" strokeWidth="1.5"/><rect x="130" y="165" width="12" height="14" rx="2" fill="#f43f5e" fillOpacity="0.75"/>
      {/* c4 bull */ }<line x1="166" y1="148" x2="166" y2="178" stroke="#34d399" strokeOpacity="0.75" strokeWidth="1.5"/><rect x="160" y="150" width="12" height="22" rx="2" fill="#10b981" fillOpacity="0.85"/>
      {/* c5 bull */ }<line x1="196" y1="132" x2="196" y2="162" stroke="#34d399" strokeOpacity="0.75" strokeWidth="1.5"/><rect x="190" y="134" width="12" height="20" rx="2" fill="#10b981" fillOpacity="0.85"/>
      {/* c6 bear */ }<line x1="226" y1="128" x2="226" y2="152" stroke="#fb7185" strokeOpacity="0.75" strokeWidth="1.5"/><rect x="220" y="130" width="12" height="14" rx="2" fill="#f43f5e" fillOpacity="0.75"/>
      {/* c7 bull */ }<line x1="256" y1="112" x2="256" y2="144" stroke="#34d399" strokeOpacity="0.75" strokeWidth="1.5"/><rect x="250" y="114" width="12" height="22" rx="2" fill="#10b981" fillOpacity="0.88"/>
      {/* c8 bull */ }<line x1="286" y1="94" x2="286" y2="132" stroke="#34d399" strokeOpacity="0.75" strokeWidth="1.5"/><rect x="280" y="96" width="12" height="28" rx="2" fill="#10b981" fillOpacity="0.90"/>
      {/* c9 bear */ }<line x1="316" y1="88" x2="316" y2="118" stroke="#fb7185" strokeOpacity="0.75" strokeWidth="1.5"/><rect x="310" y="90" width="12" height="20" rx="2" fill="#f43f5e" fillOpacity="0.78"/>
      {/* c10 bull*/ }<line x1="346" y1="76" x2="346" y2="112" stroke="#34d399" strokeOpacity="0.75" strokeWidth="1.5"/><rect x="340" y="78" width="12" height="26" rx="2" fill="#10b981" fillOpacity="0.92"/>
      {/* c11 bull*/ }<line x1="376" y1="68" x2="376" y2="102" stroke="#34d399" strokeOpacity="0.75" strokeWidth="1.5"/><rect x="370" y="70" width="12" height="22" rx="2" fill="#10b981" fillOpacity="0.90"/>
      {/* c12 bull*/ }<line x1="406" y1="62" x2="406" y2="94" stroke="#34d399" strokeOpacity="0.75" strokeWidth="1.5"/><rect x="400" y="64" width="12" height="20" rx="2" fill="#10b981" fillOpacity="0.92"/>

      {/* AI trend line — area fill */}
      <path d="M 70,198 C 100,186 126,172 166,162 C 202,153 224,138 258,124 C 288,112 318,98 350,86 C 375,78 395,70 430,64 L 430,310 L 70,310 Z"
        fill="url(#areaG)" opacity="0.22"/>

      {/* AI trend line — stroke */}
      <path d="M 70,198 C 100,186 126,172 166,162 C 202,153 224,138 258,124 C 288,112 318,98 350,86 C 375,78 395,70 430,64"
        stroke="#818cf8" strokeWidth="8" fill="none" strokeLinecap="round" opacity="0.28"/>
      <path d="M 70,198 C 100,186 126,172 166,162 C 202,153 224,138 258,124 C 288,112 318,98 350,86 C 375,78 395,70 430,64"
        stroke="url(#pG)" strokeWidth="2.5" fill="none" strokeLinecap="round"/>

      {/* Live price dot */}
      <circle cx="430" cy="64" r="5" fill="#818cf8"/>
      <circle cx="430" cy="64" r="10" fill="none" stroke="#818cf8" strokeWidth="1.5" strokeOpacity="0.4"/>
      <circle cx="430" cy="64" r="16" fill="none" stroke="#818cf8" strokeWidth="1" strokeOpacity="0.18"/>

      {/* Volume bars */}
      <rect x="70"  y="284" width="12" height="20" rx="2" fill="#f43f5e" fillOpacity="0.38"/>
      <rect x="100" y="272" width="12" height="32" rx="2" fill="#10b981" fillOpacity="0.38"/>
      <rect x="130" y="278" width="12" height="26" rx="2" fill="#f43f5e" fillOpacity="0.38"/>
      <rect x="160" y="264" width="12" height="40" rx="2" fill="#10b981" fillOpacity="0.38"/>
      <rect x="190" y="268" width="12" height="36" rx="2" fill="#10b981" fillOpacity="0.38"/>
      <rect x="220" y="280" width="12" height="24" rx="2" fill="#f43f5e" fillOpacity="0.38"/>
      <rect x="250" y="258" width="12" height="46" rx="2" fill="#10b981" fillOpacity="0.38"/>
      <rect x="280" y="248" width="12" height="56" rx="2" fill="#10b981" fillOpacity="0.40"/>
      <rect x="310" y="272" width="12" height="32" rx="2" fill="#f43f5e" fillOpacity="0.38"/>
      <rect x="340" y="240" width="12" height="64" rx="2" fill="#10b981" fillOpacity="0.40"/>
      <rect x="370" y="244" width="12" height="60" rx="2" fill="#10b981" fillOpacity="0.40"/>
      <rect x="400" y="252" width="12" height="52" rx="2" fill="#10b981" fillOpacity="0.42"/>

      {/* Divider */}
      <line x1="60" y1="310" x2="450" y2="310" stroke="#818cf8" strokeOpacity="0.08" strokeWidth="1"/>

      {/* Floating label badges */}
      <rect x="52" y="28" width="94" height="22" rx="6" fill="#1e1b4b" fillOpacity="0.90"/>
      <rect x="52" y="28" width="94" height="22" rx="6" fill="none" stroke="#6366f1" strokeOpacity="0.35" strokeWidth="1"/>
      <text x="99" y="43" textAnchor="middle" fill="#a5b4fc" fontSize="8.5" fontFamily="monospace" fontWeight="700" letterSpacing="0.5">NIFTY 50</text>

      <rect x="154" y="28" width="58" height="22" rx="6" fill="#052e16" fillOpacity="0.90"/>
      <rect x="154" y="28" width="58" height="22" rx="6" fill="none" stroke="#34d399" strokeOpacity="0.35" strokeWidth="1"/>
      <text x="183" y="43" textAnchor="middle" fill="#34d399" fontSize="9" fontFamily="monospace" fontWeight="700">+2.41%</text>

      <rect x="326" y="28" width="120" height="22" rx="6" fill="#1c0535" fillOpacity="0.90"/>
      <rect x="326" y="28" width="120" height="22" rx="6" fill="none" stroke="#a855f7" strokeOpacity="0.40" strokeWidth="1"/>
      <circle cx="342" cy="39" r="3.5" fill="#a855f7" fillOpacity="0.90"/>
      <text x="356" y="43" fill="#c084fc" fontSize="8.5" fontFamily="monospace" fontWeight="700" letterSpacing="0.3">AI SIGNAL: BUY</text>

      {/* Subtle network dots (AI intelligence concept) */}
      <circle cx="140" cy="220" r="3.5" fill="#6366f1" fillOpacity="0.55"/>
      <circle cx="218" cy="238" r="3" fill="#818cf8" fillOpacity="0.50"/>
      <circle cx="302" cy="228" r="3.5" fill="#6366f1" fillOpacity="0.50"/>
      <circle cx="388" cy="216" r="3" fill="#818cf8" fillOpacity="0.45"/>
      <line x1="140" y1="220" x2="218" y2="238" stroke="#818cf8" strokeOpacity="0.18" strokeWidth="1"/>
      <line x1="218" y1="238" x2="302" y2="228" stroke="#818cf8" strokeOpacity="0.18" strokeWidth="1"/>
      <line x1="302" y1="228" x2="388" y2="216" stroke="#818cf8" strokeOpacity="0.15" strokeWidth="1"/>

      {/* Peak signal ring */}
      <circle cx="286" cy="104" r="18" fill="none" stroke="#34d399" strokeOpacity="0.18" strokeWidth="1.5" strokeDasharray="4 3"/>
      <circle cx="286" cy="104" r="26" fill="none" stroke="#34d399" strokeOpacity="0.09" strokeWidth="1" strokeDasharray="3 5"/>
    </svg>
  );
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

  // Watch items (max 3): today's events → upcoming events → MIE fallback
  const todayStr = todayDateStr();
  const nowMs = Date.now();
  const calList = (cal ?? []) as any[];

  const toWatchItem = (e: any, label?: string) => ({
    title: e.title ?? e.event ?? "Market Event",
    impact: label ?? e.impact ?? (
      e.impact_score === null || e.impact_score === undefined ? "UNSCORED" :
      e.impact_score >= 7 ? "HIGH IMPACT" : e.impact_score >= 4 ? "MEDIUM" : "LOW"
    ),
    sub: e.category ?? e.description?.split(/[.!?]/)[0]?.trim() ?? "",
  });

  const watchItems = calList
    .filter(e => { try { return new Date(e.date ?? e.event_date ?? e.datetime).toDateString() === todayStr; } catch { return false; } })
    .sort((a: any, b: any) => compareScoresDesc(a.impact_score, b.impact_score))
    .slice(0, 3)
    .map((e: any) => toWatchItem(e));

  // Upcoming calendar events (next 7 days) as secondary source
  const upcomingItems = calList
    .filter(e => {
      try {
        const d = new Date(e.date ?? e.event_date ?? e.datetime).getTime();
        return d > nowMs && d <= nowMs + 7 * 86400_000;
      } catch { return false; }
    })
    .sort((a: any, b: any) => new Date(a.date ?? a.event_date ?? a.datetime).getTime() - new Date(b.date ?? b.event_date ?? b.datetime).getTime())
    .slice(0, 3)
    .map((e: any) => toWatchItem(e, "UPCOMING"));

  const fallbackWatch = ((mie?.top_events ?? []) as any[])
    .slice(0, 3)
    .map((e: any) => ({
      title: (e.headline ?? "").split(" ").slice(0, 6).join(" "),
      impact: e.urgency >= 7 ? "HIGH IMPACT" : "MEDIUM",
      sub: e.one_liner ?? "",
    }));

  const watch = watchItems.length ? watchItems : upcomingItems.length ? upcomingItems : fallbackWatch;

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
          style={{ background: "radial-gradient(circle, rgba(99,102,241,0.4) 0%, transparent 70%)" }} />
        <div className="absolute -bottom-16 left-12 h-72 w-72 rounded-full opacity-20"
          style={{ background: "radial-gradient(circle, rgba(139,92,246,0.5) 0%, transparent 70%)" }} />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 h-64 w-64 rounded-full opacity-10"
          style={{ background: "radial-gradient(circle, rgba(59,130,246,0.6) 0%, transparent 70%)" }} />
      </div>

      {/* Product chart glyph — center of hero */}
      <div className="pointer-events-none absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-[480px] h-[340px] hidden lg:block"
        style={{ filter: "drop-shadow(0 0 28px rgba(99,102,241,0.7)) drop-shadow(0 0 60px rgba(59,130,246,0.35))", opacity: 0.42 }}>
        <ProductGlyphSVG />
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
              <span className="text-[13px] font-black text-white">{conf !== null && conf !== undefined ? `${conf}%` : "—"}</span>
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
            <div className="space-y-2.5">
              {watch.map((w, i) => {
                const ic = impactColor(w.impact);
                return (
                  <div key={i} className="flex items-center gap-3 rounded-2xl border border-white/[0.07] bg-white/[0.03] p-3 hover:bg-white/[0.05] transition">
                    <EventIcon title={w.title} category={w.sub} />
                    <div className="min-w-0 flex-1">
                      <p className="text-[12px] font-bold text-white leading-snug line-clamp-1">{w.title}</p>
                      {w.sub && <p className="mt-0.5 text-[10px] text-slate-500 line-clamp-1">{w.sub}</p>}
                    </div>
                    <span className={`shrink-0 rounded-full border px-2 py-0.5 text-[8px] font-black uppercase tracking-wider whitespace-nowrap ${ic.bg} ${ic.text}`}>
                      {w.impact}
                    </span>
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
            const chart = syntheticChart(c.label, isVix ? !pos : pos);
            return (
              <div key={c.key} className="p-5">
                <div className="mb-2 flex items-start justify-between gap-2">
                  <p className="text-[9px] font-bold uppercase tracking-[0.12em] text-slate-600">{c.label}</p>
                  <MiniSparkline data={chart} positive={isVix ? !pos : pos} w={64} h={28} />
                </div>
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
            <p className="mb-3 text-[9px] font-bold uppercase tracking-[0.12em] text-slate-600">Market Breadth</p>
            {breadth && tot > 0 ? (
              <>
                <div className="flex items-end gap-4 mb-3">
                  <div className="text-center">
                    <p className="text-[26px] font-black text-emerald-400 tabular-nums leading-none">{breadth.advances.toLocaleString()}</p>
                    <p className="mt-0.5 text-[9px] font-bold uppercase tracking-wider text-emerald-600">Advances</p>
                  </div>
                  <div className="mb-1 text-slate-700 text-[16px] font-light">/</div>
                  <div className="text-center">
                    <p className="text-[26px] font-black text-rose-400 tabular-nums leading-none">{breadth.declines.toLocaleString()}</p>
                    <p className="mt-0.5 text-[9px] font-bold uppercase tracking-wider text-rose-700">Declines</p>
                  </div>
                </div>
                <div className="h-2 w-full overflow-hidden rounded-full bg-white/[0.05] flex gap-px">
                  <div className="h-full rounded-l-full bg-emerald-500" style={{ width: `${(advPct * 100).toFixed(0)}%` }} />
                  <div className="h-full bg-slate-600" style={{ width: `${((breadth.unchanged / tot) * 100).toFixed(0)}%` }} />
                  <div className="h-full flex-1 rounded-r-full bg-rose-500" />
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
    chart?: number[];
  };

  const cards: Card[] = [];

  // Gift Nifty
  const gn = premarket?.gift_nifty;
  if (gn) {
    const up = (gn.change_pct ?? gn.premium_pct ?? 0) >= 0;
    const gnChart = (gn.chart as any[] | undefined)?.map((p: any) => p.value ?? p) as number[] | undefined;
    cards.push({
      icon: <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-amber-500/20"><TrendingUp className="h-4 w-4 text-amber-400"/></div>,
      label: "GIFT NIFTY",
      value: gn.value ? String(gn.value) : "—",
      change: gn.pct ?? (gn.premium_pct != null ? `${gn.premium_pct >= 0 ? "+" : ""}${Number(gn.premium_pct).toFixed(2)}% premium` : (gn.change_str ?? "")),
      up,
      why: up ? "Positive opening indicated for Nifty. Expect early strength." : "Cautious opening. Watch 9:15 AM gap.",
      chart: gnChart?.length ? gnChart : syntheticChart("GIFTNIFTY", up),
    });
  }

  // Global Markets
  const usArr = (premarket?.us ?? []) as any[];
  const sp = usArr.find((u: any) => /S&P|SPX/i.test(u.name ?? "")) ?? usArr[0];
  if (sp) {
    const up = sp.positive !== false;
    cards.push({
      icon: <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-sky-500/20"><Globe className="h-4 w-4 text-sky-400"/></div>,
      label: "GLOBAL MARKETS",
      value: up ? "Positive" : "Negative",
      change: sp.change_str ?? "",
      up,
      why: `US markets ${up ? "ended higher." : "declined."} ${up ? "Positive cues for Asian session." : "Cautious tone in Asian open."}`,
      chart: syntheticChart("GLOBAL", up),
    });
  }

  // Crude Oil
  const oil = ((premarket?.commodities ?? []) as any[]).find((c: any) => /brent|crude/i.test(c.name ?? ""));
  if (oil) {
    const up = oil.positive !== false;
    cards.push({
      icon: <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-orange-500/20"><Droplets className="h-4 w-4 text-orange-400"/></div>,
      label: "CRUDE OIL",
      value: oil.value ? `$${oil.value}` : "—",
      change: oil.change_str ?? String(oil.change ?? ""),
      up,
      why: up ? "Rising oil pressures Auto, Airlines. Monitor input-cost inflation." : "Falling oil benefits Auto, Airlines, Paint sectors.",
      chart: syntheticChart("BRENTOIL", up),
    });
  }

  // USD/INR
  const usdinr = ((premarket?.currencies ?? []) as any[]).find((c: any) => /USD.?INR/i.test(c.name ?? ""));
  if (usdinr) {
    cards.push({
      icon: <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-teal-500/20"><DollarSign className="h-4 w-4 text-teal-400"/></div>,
      label: "USD / INR",
      value: usdinr.value ? `₹${usdinr.value}` : "—",
      change: usdinr.change_str ?? String(usdinr.change ?? ""),
      up: null,
      why: "Stable rupee supports FII flows and reduces import-cost pressure.",
      chart: syntheticChart("USDINR", true),
    });
  }

  // Today's Biggest Event
  const todayStr = todayDateStr();
  const topEvt = ((cal ?? []) as any[])
    .filter(e => { try { return new Date(e.date ?? e.event_date ?? e.datetime).toDateString() === todayStr; } catch { return false; } })
    .sort((a: any, b: any) => compareScoresDesc(a.impact_score, b.impact_score))[0];
  if (topEvt) {
    const title = topEvt.title ?? topEvt.event ?? "";
    cards.push({
      icon: <EventIcon title={title} />,
      label: "TODAY'S BIGGEST EVENT",
      value: title.split(" ").slice(0, 5).join(" "),
      change: topEvt.impact ?? (
        topEvt.impact_score === null || topEvt.impact_score === undefined ? "UNSCORED" :
        topEvt.impact_score >= 7 ? "HIGH IMPACT" : "MEDIUM"
      ),
      up: null,
      why: topEvt.description?.split(/[.!?]/)[0]?.trim() ?? "This event may trigger significant market moves. Track closely.",
      chart: syntheticChart(title.slice(0, 8), true),
    });
  }

  // Fallback from MIE top_events if cards are short
  if (cards.length < 2 && mie?.top_events?.length) {
    const ev = (mie.top_events as any[])[0];
    if (ev) {
      cards.push({
        icon: <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-rose-500/20"><AlertCircle className="h-4 w-4 text-rose-400"/></div>,
        label: "TOP EVENT",
        value: (ev.headline ?? "").split(" ").slice(0, 4).join(" "),
        change: `Urgency ${ev.urgency ?? "—"}/10`,
        up: ev.sentiment === "bullish" ? true : ev.sentiment === "bearish" ? false : null,
        why: ev.one_liner ?? ev.headline ?? "",
        chart: syntheticChart(ev.headline?.slice(0, 8) ?? "event", ev.sentiment !== "bearish"),
      });
    }
  }

  if (!cards.length) return null;

  return (
    <section>
      <SectionHeader label="Why Today Matters" sub="The five drivers every investor must understand today" href="/market-intelligence" linkLabel="Full Market" />
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-5">
        {cards.slice(0, 5).map((c, i) => (
          <div key={i} className="flex flex-col rounded-2xl border border-white/[0.07] bg-[#060e1e] p-5 transition hover:border-white/[0.12] hover:bg-[#081224]">
            <div className="mb-3 flex items-center justify-between">
              {c.icon}
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
            <p className="mt-2 flex-1 text-[11px] leading-[1.6] text-slate-500">{c.why}</p>
            {c.chart && (
              <div className="mt-3 pt-3 border-t border-white/[0.05]">
                <MiniSparkline data={c.chart} positive={c.up !== false} w={100} h={28} />
              </div>
            )}
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
  const [cal, mie, recentRaw] = await Promise.all([getCalendar(), getMIE(), getRecentEvents()]);

  type Ev = { id: string; title: string; time: string; impact: string; sectors: string[]; companies: string[]; href: string; tag?: string };

  const todayStr = todayDateStr();
  const nowMs = Date.now();

  const toEv = (e: any, tag?: string): Ev => {
    // impact_score is the Scoring Engine's field and may legitimately be
    // null; urgency is a triage field that always has a real value. Only
    // fall through to urgency when impact_score is genuinely absent —
    // never invent a shared "60" baseline when both are missing.
    const gradeSource = e.impact_score !== null && e.impact_score !== undefined ? e.impact_score
      : e.urgency !== null && e.urgency !== undefined ? e.urgency
      : null;
    return {
      id: e.id ?? String(Math.random()),
      title: e.title ?? e.headline ?? e.event ?? "Market Event",
      time: e.time ? `${e.time} IST` : tag ?? "Today",
      impact: e.impact ?? (
        gradeSource === null ? "UNSCORED" :
        gradeSource >= 80 ? "HIGH IMPACT" :
        gradeSource >= 60 ? "MEDIUM IMPACT" : "LOW"
      ),
      sectors: (e.sectors ?? e.affected_sectors ?? []).slice(0, 3),
      companies: (e.companies ?? e.affected_companies ?? e.tickers ?? []).slice(0, 3),
      href: e.id ? `/events/${e.id}` : "/events",
      tag,
    };
  };

  // Tier 1 — today's calendar events
  const todayCalEvents: Ev[] = ((cal ?? []) as any[])
    .filter(e => { try { return new Date(e.date ?? e.event_date ?? e.datetime).toDateString() === todayStr; } catch { return false; } })
    .sort((a: any, b: any) => compareScoresDesc(a.impact_score, b.impact_score))
    .map(e => toEv(e, "Today"));

  // Tier 2 — MIE top_events (any urgency)
  const mieEvs: Ev[] = ((mie?.top_events ?? []) as any[])
    .sort((a: any, b: any) => (b.urgency ?? 0) - (a.urgency ?? 0))
    .map(e => toEv(e, "Live Signal"));

  // Tier 3 — Upcoming calendar events (next 30 days), closest first
  const upcomingCalEvents: Ev[] = ((cal ?? []) as any[])
    .filter(e => { try { const d = new Date(e.date ?? e.event_date ?? e.datetime); return d.getTime() > nowMs; } catch { return false; } })
    .sort((a: any, b: any) => new Date(a.date ?? a.event_date ?? a.datetime).getTime() - new Date(b.date ?? b.event_date ?? b.datetime).getTime())
    .map(e => {
      const d = new Date(e.date ?? e.event_date ?? e.datetime);
      const diffDays = Math.ceil((d.getTime() - nowMs) / 86400000);
      const tag = diffDays === 0 ? "Today" : diffDays === 1 ? "Tomorrow" : `In ${diffDays}d`;
      return toEv(e, tag);
    });

  // Tier 4 — recent events from API, English only, meaningful titles
  const recentEvents: Ev[] = ((recentRaw as any)?.results ?? (recentRaw as any) ?? [])
    .filter((e: any) => {
      const title = e.title ?? "";
      // Skip non-English (Hindi/other) and low-signal corporate filings
      if (/[ऀ-ॿ]/.test(title)) return false;
      const skipWords = ["allotment", "dividend", "cessation", "appointment", "surety", "record date", "auditor", "insolvency"];
      if (skipWords.some(w => title.toLowerCase().includes(w))) return false;
      return true;
    })
    .sort((a: any, b: any) => compareScoresDesc(a.impact_score, b.impact_score))
    .map((e: any) => {
      const d = new Date(e.date ?? e.datetime);
      const diffDays = Math.floor((nowMs - d.getTime()) / 86400000);
      const tag = diffDays === 0 ? "Today" : diffDays === 1 ? "Yesterday" : `${diffDays}d ago`;
      return toEv(e, tag);
    });

  // Merge in priority order, deduplicate by id
  const seen = new Set<string>();
  const events: Ev[] = [];
  for (const ev of [...todayCalEvents, ...mieEvs, ...upcomingCalEvents, ...recentEvents]) {
    if (seen.has(ev.id)) continue;
    seen.add(ev.id);
    events.push(ev);
    if (events.length >= 5) break;
  }

  // Section subtitle changes based on source
  const hasTodayEvents = todayCalEvents.length > 0 || mieEvs.length > 0;
  const sub = hasTodayEvents ? "Events that move markets today" : "Upcoming events and recent market signals";

  if (!events.length) return (
    <section>
      <SectionHeader label="High Impact Events" sub={sub} href="/events" linkLabel="All Events" />
      <div className="rounded-2xl border border-white/[0.06] bg-[#060e1e] p-8 text-center">
        <Calendar className="mx-auto h-8 w-8 text-slate-700 mb-3" />
        <p className="text-[13px] text-slate-600">No events found. <Link href="/events" className="text-violet-400 hover:underline">Browse all events →</Link></p>
      </div>
    </section>
  );

  return (
    <section>
      <SectionHeader label="High Impact Events" sub={sub} href="/events" linkLabel="View All" />
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-5">
        {events.map((ev) => {
          const ic = impactColor(ev.impact);
          return (
            <Link key={ev.id} href={ev.href as any}
              className="group flex flex-col rounded-2xl border border-white/[0.07] bg-[#060e1e] p-4 transition hover:border-white/[0.14] hover:bg-[#081224]">

              {/* Top row: icon + impact badge */}
              <div className="mb-3 flex items-start justify-between gap-2">
                <EventIcon title={ev.title} />
                <div className={`self-start rounded-full border px-2.5 py-1 text-[8px] font-black uppercase tracking-wider ${ic.bg} ${ic.text}`}>
                  {ev.impact}
                </div>
              </div>

              <h3 className="mb-1 text-[13px] font-bold leading-snug text-white group-hover:text-violet-200 transition line-clamp-2">{ev.title}</h3>

              {/* Time tag */}
              {ev.tag && (
                <p className="mb-1 text-[10px] text-slate-600">{ev.tag}</p>
              )}

              {/* Sectors */}
              {ev.sectors.length > 0 && (
                <div className="mt-auto mb-1 flex flex-wrap gap-1 pt-2">
                  <p className="w-full text-[8px] font-bold uppercase tracking-wider text-slate-700 mb-1">Affected Sectors</p>
                  {ev.sectors.map((s: string, j: number) => (
                    <span key={j} className="rounded-full bg-white/[0.04] border border-white/[0.06] px-2 py-0.5 text-[9px] text-slate-500">{s}</span>
                  ))}
                </div>
              )}

              <div className="mt-auto flex items-center gap-1 pt-3 text-[10px] font-semibold text-violet-400 group-hover:text-violet-300 transition">
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
  const [movers, mie] = await Promise.all([getTopMovers(), getMIE()]);

  // Prefer gainers (have meaningful % change), then losers, then active
  const gainers = ((movers?.gainers ?? []) as any[]);
  const losers  = ((movers?.losers  ?? []) as any[]);
  const active  = ((movers?.active  ?? []) as any[]);

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

                {conf !== null && conf !== undefined && (
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

  type OppRow = { name: string; why: string; conf: number | null; sectors: string[] };
  type RiskRow = { name: string; why: string; level: string; sectors: string[] };

  const opps: OppRow[] = [];
  const risks: RiskRow[] = [];

  if (story?.opportunity)
    opps.push({ name: "AI Market Signal", why: story.opportunity.split(/[.!?]/)[0]?.trim() ?? story.opportunity, conf: story.confidence ?? null, sectors: [] });
  radarItems.forEach((r: any) =>
    opps.push({
      name: r.title ?? r.theme,
      why: (r.summary ?? r.reason ?? "").split(/[.!?]/)[0]?.trim() || "",
      conf: r.opportunity_score !== null && r.opportunity_score !== undefined ? Math.round(r.opportunity_score) : null,
      sectors: (r.sectors ?? []).slice(0, 2),
    }));

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
            {(opps.length ? opps : [{ name: "Scanning markets…", why: "AI is identifying today's opportunities.", conf: null, sectors: [] }]).slice(0, 4).map((o, i) => (
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
                {o.conf !== null && o.conf !== undefined && o.conf > 0 && (
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
