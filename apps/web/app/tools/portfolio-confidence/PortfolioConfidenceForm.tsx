"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  Loader2, Sparkles, ArrowRight, CheckCircle2, XCircle, HelpCircle,
  TrendingUp, TrendingDown, ExternalLink, RefreshCw, Download, Radio,
  Building2, MessageCircleQuestion,
} from "lucide-react";
import { API_BASE_URL as API } from "@/lib/api";

// ── Types — mirror the real API response exactly, no invented fields ────────
interface Suggestion { symbol: string; name: string; confidence: number }
interface HoldingResult {
  input: string;
  resolved: boolean;
  symbol: string | null;
  name: string | null;
  sector?: string | null;
  in_universe: boolean;
  event_count: number;
  news_count: number;
  level: "strong" | "light" | "thin" | "not_tracked";
  message: string;
  suggestions: Suggestion[];
  ai_search_query: string;
  price?: string | null;
  price_pct?: number | null;
}
interface BriefItem {
  symbol: string; name: string; price: string; pct: number; event_count: number; message: string;
}
interface RippleTheme {
  theme: string; momentum: string | null; score: number | null;
  holdings: { symbol: string; name: string }[];
}
interface Brief {
  needs_attention: BriefItem[];
  positive_developments: BriefItem[];
  ripples: RippleTheme[];
  prices_available: boolean;
  generated_at: string;
}
interface ConfidenceResponse {
  window_days: number;
  holdings: HoldingResult[];
  summary: { strong: number; light: number; thin: number; not_tracked: number };
  brief: Brief;
}

type TableFilter = "all" | "attention" | "positive" | "thin" | "not_tracked";

const LEVEL_META: Record<HoldingResult["level"], { label: string; badge: string; dot: string }> = {
  strong: {
    label: "Strong",
    badge: "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-500/10 dark:text-emerald-300 dark:border-emerald-500/20",
    dot: "bg-emerald-500",
  },
  light: {
    label: "Moderate",
    badge: "bg-sky-50 text-sky-700 border-sky-200 dark:bg-sky-500/10 dark:text-sky-300 dark:border-sky-500/20",
    dot: "bg-sky-500",
  },
  thin: {
    label: "Thin",
    badge: "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-500/10 dark:text-amber-300 dark:border-amber-500/20",
    dot: "bg-amber-500",
  },
  not_tracked: {
    label: "Unresolved",
    badge: "bg-slate-50 text-slate-600 border-slate-200 dark:bg-white/[0.04] dark:text-text-muted dark:border-surface-border/15",
    dot: "bg-slate-400",
  },
};

const TABLE_FILTERS: { id: TableFilter; label: string }[] = [
  { id: "all", label: "All" },
  { id: "attention", label: "Attention" },
  { id: "positive", label: "Positive" },
  { id: "thin", label: "Thin Coverage" },
  { id: "not_tracked", label: "Unresolved" },
];

const THEME_DOT_COLORS = ["bg-violet-500", "bg-sky-500", "bg-rose-500", "bg-amber-500", "bg-emerald-500", "bg-indigo-500"];

// Indicative only — the endpoint is one atomic request, not a real
// multi-stage stream. Cycled purely as a waiting affordance; no
// percentage is shown anywhere, so nothing claims false precision.
const LOADING_STAGES = [
  "Matching holdings",
  "Finding recent events",
  "Checking news",
  "Detecting shared themes",
  "Identifying attention signals",
  "Finding intelligence blind spots",
];

const SAMPLE_PORTFOLIO = "HAL, TCS, RELIANCE, MARUTI, INFY";
const PLACEHOLDER = "HAL, TCS, RELIANCE, MARUTI, INFY\nHDFCBANK, ITC, ASIANPAINT, LT";

function parseHoldings(raw: string): string[] {
  return raw.split(/[\n,]/).map(s => s.trim()).filter(Boolean).slice(0, 30);
}

function formatIST(iso: string): string {
  try {
    return new Date(iso).toLocaleString("en-IN", {
      timeZone: "Asia/Kolkata", day: "numeric", month: "short",
      hour: "numeric", minute: "2-digit", hour12: true,
    }) + " IST";
  } catch {
    return "just now";
  }
}

function matchLabel(h: HoldingResult): string {
  if (!h.resolved) return "Not in universe";
  return h.input.trim().toUpperCase() === h.symbol ? "Exact match" : "Matched";
}

function actionLabel(h: HoldingResult): string {
  if (h.level === "strong" || h.level === "light") return "View Intelligence";
  if (h.level === "thin") return "Ask AI Search";
  return "View Suggestions";
}

// ── Small building blocks ────────────────────────────────────────────────

function CoverageDonut({ pct }: { pct: number }) {
  const r = 52, c = 2 * Math.PI * r;
  const offset = c - (Math.min(100, Math.max(0, pct)) / 100) * c;
  return (
    <svg viewBox="0 0 120 120" className="h-[120px] w-[120px]">
      <circle cx="60" cy="60" r={r} fill="none" strokeWidth="10" className="stroke-surface-border/12" />
      <circle
        cx="60" cy="60" r={r} fill="none" strokeWidth="10" strokeLinecap="round"
        className="stroke-emerald-500 transition-all duration-700"
        strokeDasharray={c} strokeDashoffset={offset}
        transform="rotate(-90 60 60)"
      />
      <text x="60" y="56" textAnchor="middle" className="fill-text-primary text-[24px] font-bold">{pct}%</text>
      <text x="60" y="74" textAnchor="middle" className="fill-text-muted text-[9px] font-semibold uppercase tracking-wide">Coverage</text>
    </svg>
  );
}

function EmptyNote({ children }: { children: React.ReactNode }) {
  return <p className="rounded-xl border border-surface-border/10 bg-bg px-3.5 py-3 text-[12px] leading-relaxed text-text-muted">{children}</p>;
}

function AttentionCard({ item, tone }: { item: BriefItem; tone: "attention" | "positive" }) {
  const up = item.pct >= 0;
  return (
    <div className="rounded-xl border border-surface-border/10 bg-bg p-3.5">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-text-primary/[0.05] text-[10px] font-bold text-text-secondary">
            {item.symbol.slice(0, 3)}
          </span>
          <p className="truncate text-[13px] font-semibold text-text-primary">{item.name}</p>
        </div>
        <div className="shrink-0 text-right">
          <p className="text-[12.5px] font-semibold tabular-nums text-text-primary">₹{item.price}</p>
          <span className={`inline-flex items-center gap-1 text-[10.5px] font-bold tabular-nums ${
            tone === "positive" ? "text-emerald-600 dark:text-emerald-300" : "text-rose-500"
          }`}>
            {up ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
            {up ? "+" : ""}{item.pct.toFixed(2)}%
          </span>
        </div>
      </div>
      <p className="mt-2 text-[11.5px] leading-relaxed text-text-secondary">{item.message}</p>
      <Link href={`/companies/${item.symbol}`} className="mt-2 inline-flex items-center gap-1 text-[11.5px] font-semibold text-accent-violet hover:text-accent-violet/80">
        View Details <ArrowRight className="h-3 w-3" />
      </Link>
    </div>
  );
}

export function PortfolioConfidenceForm({
  universeTotal, heroLeft, howItWorks,
}: {
  universeTotal: number | null;
  heroLeft: React.ReactNode;
  howItWorks: { n: string; title: string; body: string }[];
}) {
  const [raw, setRaw] = useState("");
  const [data, setData] = useState<ConfidenceResponse | null>(null);
  const [lastHoldings, setLastHoldings] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [stageIdx, setStageIdx] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<TableFilter>("all");
  const stageTimer = useRef<ReturnType<typeof setInterval> | null>(null);
  const resultsRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    return () => { if (stageTimer.current) clearInterval(stageTimer.current); };
  }, []);

  async function runCheck(holdings: string[]) {
    if (holdings.length === 0) return;
    setLoading(true);
    setError(null);
    setStageIdx(0);
    setLastHoldings(holdings);
    stageTimer.current = setInterval(() => {
      setStageIdx(i => (i < LOADING_STAGES.length - 1 ? i + 1 : i));
    }, 800);

    try {
      const res = await fetch(`${API}/api/tools/portfolio-confidence`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ holdings }),
      });
      if (!res.ok) throw new Error(`Request failed: ${res.status}`);
      const json: ConfidenceResponse = await res.json();
      setData(json);
      setFilter("all");
    } catch {
      setError("Couldn't check your portfolio right now. Please try again in a moment.");
    } finally {
      if (stageTimer.current) clearInterval(stageTimer.current);
      setLoading(false);
    }
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const holdings = parseHoldings(raw);
    runCheck(holdings).then(() =>
      requestAnimationFrame(() => resultsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }))
    );
  }

  function handleSample() { setRaw(SAMPLE_PORTFOLIO); }

  function handleReset() {
    setData(null);
    setError(null);
    setRaw("");
    setFilter("all");
  }

  function scrollToMethodology() {
    document.getElementById("methodology")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function exportCSV() {
    if (!data) return;
    const rows = [
      ["Company", "Symbol", "Match", "Events (90D)", "News (90D)", "Coverage"],
      ...data.holdings.map(h => [h.name ?? h.input, h.symbol ?? "", matchLabel(h), String(h.event_count), String(h.news_count), LEVEL_META[h.level].label]),
    ];
    const csv = rows.map(r => r.map(c => `"${String(c).replace(/"/g, '""')}"`).join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "portfolio-intelligence-brief.csv";
    a.click();
    URL.revokeObjectURL(url);
  }

  const total = data?.holdings.length ?? 0;
  const strongOrModerate = (data?.summary.strong ?? 0) + (data?.summary.light ?? 0);
  const coveragePct = total > 0 ? Math.round((strongOrModerate / total) * 100) : 0;

  const attentionSymbols = new Set((data?.brief.needs_attention ?? []).map(i => i.symbol));
  const positiveSymbols = new Set((data?.brief.positive_developments ?? []).map(i => i.symbol));
  const thinHoldings = (data?.holdings ?? []).filter(h => h.level === "thin");

  const filtered = data ? data.holdings.filter(h => {
    if (filter === "all") return true;
    if (filter === "attention") return h.symbol ? attentionSymbols.has(h.symbol) : false;
    if (filter === "positive") return h.symbol ? positiveSymbols.has(h.symbol) : false;
    if (filter === "thin") return h.level === "thin";
    return h.level === "not_tracked";
  }) : [];

  return (
    <div>
      {/* ── Hero: static left copy + input card ──────────────────────── */}
      <div className="grid gap-6 lg:grid-cols-[1fr_440px] lg:items-start">
        {heroLeft}

        <div className="rounded-2xl border border-surface-border/10 bg-surface-card p-6 shadow-[0_1px_2px_rgba(15,23,42,0.04)]">
          <form onSubmit={handleSubmit}>
            <label htmlFor="holdings" className="block text-[14.5px] font-semibold text-text-primary">
              What stocks are you holding?
            </label>
            <p className="mt-1 text-[12px] text-text-muted">
              Enter company names or tickers. One per line, comma or space separated.
            </p>
            <textarea
              id="holdings"
              value={raw}
              onChange={e => setRaw(e.target.value)}
              placeholder={PLACEHOLDER}
              rows={5}
              disabled={loading}
              aria-describedby="holdings-help"
              className="mt-3 w-full resize-y rounded-xl border border-surface-border/15 bg-bg px-4 py-3 text-[13.5px] leading-relaxed text-text-primary placeholder:text-text-muted/70 transition focus:border-accent-violet/50 focus:outline-none focus:ring-2 focus:ring-accent-violet/15 disabled:opacity-60"
            />
            <p id="holdings-help" className="sr-only">Enter one holding per line, or separate with commas.</p>

            <div className="mt-4 flex flex-col-reverse items-stretch gap-3 sm:flex-row sm:items-center sm:justify-between">
              <button
                type="button"
                onClick={handleSample}
                disabled={loading}
                className="text-[12.5px] font-semibold text-accent-violet transition hover:text-accent-violet/80 disabled:opacity-50"
              >
                Try a sample portfolio →
              </button>
              <button
                type="submit"
                disabled={loading || raw.trim().length === 0}
                className="flex w-full items-center justify-center gap-2 rounded-xl bg-accent-violet px-5 py-3 text-[14px] font-semibold text-white transition hover:bg-accent-violet/90 disabled:cursor-not-allowed disabled:opacity-50 sm:w-auto"
              >
                {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                Analyze Portfolio <ArrowRight className="h-4 w-4" />
              </button>
            </div>
          </form>

          <p className="mt-3 text-[11px] text-text-muted">🔒 Your portfolio is analyzed on the fly and never stored.</p>

          {loading && (
            <div role="status" aria-live="polite" className="mt-5 rounded-xl border border-surface-border/10 bg-bg px-5 py-5 text-center">
              <Loader2 className="mx-auto h-5 w-5 animate-spin text-accent-violet" />
              <p className="mt-3 text-[13.5px] font-semibold text-text-primary">Analyzing your portfolio…</p>
              <p className="mt-1 text-[12.5px] text-text-secondary">{LOADING_STAGES[stageIdx]}</p>
            </div>
          )}

          {error && (
            <p role="alert" className="mt-4 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-[12.5px] text-rose-700 dark:border-rose-500/20 dark:bg-rose-500/[0.06] dark:text-rose-300">
              {error}
            </p>
          )}
        </div>
      </div>

      {/* ── Results ───────────────────────────────────────────────────── */}
      {data && (
        <div ref={resultsRef} className="mt-10 space-y-6 scroll-mt-6">
          {/* Your Portfolio Today */}
          <div className="rounded-2xl border border-surface-border/10 bg-surface-card p-6">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h2 className="text-[16px] font-semibold text-text-primary">Your Portfolio Today</h2>
                <p className="text-[12px] text-text-muted">Based on real intelligence from the last {data.window_days} days</p>
              </div>
              <div className="flex items-center gap-3 text-[12px] text-text-muted">
                <span>Analysis: {formatIST(data.brief.generated_at)}</span>
                <button
                  onClick={() => runCheck(lastHoldings)}
                  disabled={loading}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-surface-border/15 px-2.5 py-1.5 text-[11.5px] font-semibold text-text-secondary transition hover:text-text-primary disabled:opacity-50"
                >
                  <RefreshCw className={`h-3 w-3 ${loading ? "animate-spin" : ""}`} /> Refresh
                </button>
              </div>
            </div>

            <div className="mt-5 grid gap-5 lg:grid-cols-3">
              {/* Donut + legend */}
              <div className="rounded-xl border border-surface-border/10 bg-bg p-4">
                <div className="flex items-center gap-4">
                  <CoverageDonut pct={coveragePct} />
                  <div>
                    <p className="text-[12.5px] leading-relaxed text-text-secondary">
                      <span className="font-semibold text-text-primary">{strongOrModerate} of {total}</span> holdings have
                      strong or moderate intelligence coverage.
                    </p>
                    <button onClick={scrollToMethodology} className="mt-1.5 inline-flex items-center gap-1 text-[11.5px] font-semibold text-accent-violet hover:text-accent-violet/80">
                      <HelpCircle className="h-3 w-3" /> What is coverage?
                    </button>
                  </div>
                </div>
                <ul className="mt-4 space-y-1.5 border-t border-surface-border/8 pt-3">
                  {([
                    ["strong", data.summary.strong], ["light", data.summary.light],
                    ["thin", data.summary.thin], ["not_tracked", data.summary.not_tracked],
                  ] as const).map(([level, count]) => (
                    <li key={level} className="flex items-center justify-between text-[12px]">
                      <span className="flex items-center gap-2 text-text-secondary">
                        <span className={`h-1.5 w-1.5 rounded-full ${LEVEL_META[level].dot}`} /> {LEVEL_META[level].label} Coverage
                      </span>
                      <span className="font-semibold tabular-nums text-text-primary">{count}</span>
                    </li>
                  ))}
                </ul>
              </div>

              {/* Needs Attention */}
              <div className="rounded-xl border border-surface-border/10 bg-bg p-4">
                <div className="flex items-center gap-2">
                  <h3 className="text-[13px] font-semibold text-text-primary">Needs Attention</h3>
                  <span className="rounded-full bg-rose-500/10 px-1.5 py-0.5 text-[10.5px] font-bold text-rose-600 dark:text-rose-300">{data.brief.needs_attention.length}</span>
                </div>
                <p className="mt-0.5 text-[11px] text-text-muted">Notable downward price moves today</p>
                <div className="mt-3 space-y-2">
                  {!data.brief.prices_available ? (
                    <EmptyNote>Live price data is temporarily unavailable — check back soon.</EmptyNote>
                  ) : data.brief.needs_attention.length === 0 ? (
                    <EmptyNote>No notable downward moves detected today.</EmptyNote>
                  ) : (
                    data.brief.needs_attention.slice(0, 3).map(item => <AttentionCard key={item.symbol} item={item} tone="attention" />)
                  )}
                </div>
                {data.brief.needs_attention.length > 0 && (
                  <button onClick={() => { setFilter("attention"); document.getElementById("all-holdings")?.scrollIntoView({ behavior: "smooth", block: "start" }); }} className="mt-3 text-[11.5px] font-semibold text-accent-violet hover:text-accent-violet/80">
                    View all in holdings table →
                  </button>
                )}
              </div>

              {/* Positive Developments */}
              <div className="rounded-xl border border-surface-border/10 bg-bg p-4">
                <div className="flex items-center gap-2">
                  <h3 className="text-[13px] font-semibold text-text-primary">Positive Developments</h3>
                  <span className="rounded-full bg-emerald-500/10 px-1.5 py-0.5 text-[10.5px] font-bold text-emerald-600 dark:text-emerald-300">{data.brief.positive_developments.length}</span>
                </div>
                <p className="mt-0.5 text-[11px] text-text-muted">Notable upward price moves today</p>
                <div className="mt-3 space-y-2">
                  {!data.brief.prices_available ? (
                    <EmptyNote>Live price data is temporarily unavailable — check back soon.</EmptyNote>
                  ) : data.brief.positive_developments.length === 0 ? (
                    <EmptyNote>No notable upward moves detected today.</EmptyNote>
                  ) : (
                    data.brief.positive_developments.slice(0, 3).map(item => <AttentionCard key={item.symbol} item={item} tone="positive" />)
                  )}
                </div>
                {data.brief.positive_developments.length > 0 && (
                  <button onClick={() => { setFilter("positive"); document.getElementById("all-holdings")?.scrollIntoView({ behavior: "smooth", block: "start" }); }} className="mt-3 text-[11.5px] font-semibold text-accent-violet hover:text-accent-violet/80">
                    View all in holdings table →
                  </button>
                )}
              </div>
            </div>
          </div>

          {/* Ripples / Blind Spots / How It Works */}
          <div className="grid gap-5 lg:grid-cols-[1fr_1fr_300px]">
            <div className="rounded-2xl border border-surface-border/10 bg-surface-card p-5">
              <div className="flex items-center gap-2">
                <h3 className="text-[14px] font-semibold text-text-primary">Portfolio Ripples</h3>
                <span className="rounded-full bg-accent-violet/10 px-1.5 py-0.5 text-[10.5px] font-bold text-accent-violet">{data.brief.ripples.length}</span>
              </div>
              <p className="mt-0.5 text-[11px] text-text-muted">Themes and events impacting multiple holdings</p>
              <div className="mt-3 space-y-3">
                {data.brief.ripples.length === 0 ? (
                  <EmptyNote>No significant cross-holding signal detected yet.</EmptyNote>
                ) : (
                  data.brief.ripples.slice(0, 5).map((t, i) => (
                    <div key={t.theme} className="rounded-xl border border-surface-border/10 bg-bg p-3.5">
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex items-center gap-2">
                          <span className={`h-2 w-2 rounded-full ${THEME_DOT_COLORS[i % THEME_DOT_COLORS.length]}`} />
                          <p className="text-[13px] font-semibold text-text-primary">{t.theme}</p>
                        </div>
                        <span className="shrink-0 rounded-full border border-surface-border/12 px-2 py-0.5 text-[10.5px] font-semibold text-text-secondary">
                          {t.holdings.length} holding{t.holdings.length === 1 ? "" : "s"}
                        </span>
                      </div>
                      <p className="mt-1.5 text-[11.5px] text-text-secondary">
                        {t.momentum === "rising" ? "Rising momentum" : t.momentum === "falling" ? "Falling momentum" : "Stable momentum"} across this theme.
                      </p>
                      <p className="mt-1 text-[11px] text-text-muted">{t.holdings.map(h => h.symbol).join(" · ")}</p>
                    </div>
                  ))
                )}
              </div>
              <Link href="/newsroom/themes" className="mt-3 inline-flex items-center gap-1 text-[11.5px] font-semibold text-accent-violet hover:text-accent-violet/80">
                Explore All Themes <ArrowRight className="h-3 w-3" />
              </Link>
            </div>

            <div className="rounded-2xl border border-surface-border/10 bg-surface-card p-5">
              <div className="flex items-center gap-2">
                <h3 className="text-[14px] font-semibold text-text-primary">Intelligence Blind Spots</h3>
                <span className="rounded-full bg-amber-500/10 px-1.5 py-0.5 text-[10.5px] font-bold text-amber-600 dark:text-amber-300">{thinHoldings.length}</span>
              </div>
              <p className="mt-0.5 text-[11px] text-text-muted">Limited Market Ripple evidence</p>
              <div className="mt-3 space-y-3">
                {thinHoldings.length === 0 ? (
                  <EmptyNote>Every holding has at least moderate coverage — no blind spots detected.</EmptyNote>
                ) : (
                  thinHoldings.slice(0, 4).map(h => (
                    <div key={h.symbol} className="rounded-xl border border-surface-border/10 bg-bg p-3.5">
                      <div className="flex items-start justify-between gap-2">
                        <p className="text-[13px] font-semibold text-text-primary">{h.name}</p>
                        <span className="shrink-0 rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-[10px] font-bold uppercase text-amber-700 dark:border-amber-500/20 dark:bg-amber-500/10 dark:text-amber-300">
                          Thin Coverage
                        </span>
                      </div>
                      <p className="mt-1 text-[11.5px] leading-relaxed text-text-secondary">
                        Limited Market Ripple evidence does not mean the company is weak or inactive —
                        it means our current local evidence is limited.
                      </p>
                      <Link href={`/ai-search?q=${encodeURIComponent(h.ai_search_query)}`} className="mt-2 inline-flex items-center gap-1 rounded-lg border border-accent-violet/25 bg-accent-violet/[0.06] px-2.5 py-1.5 text-[11.5px] font-semibold text-accent-violet transition hover:bg-accent-violet/10">
                        <Sparkles className="h-3 w-3" /> Investigate with AI Search
                      </Link>
                    </div>
                  ))
                )}
              </div>
              <button onClick={scrollToMethodology} className="mt-3 inline-flex items-center gap-1 text-[11.5px] font-semibold text-accent-violet hover:text-accent-violet/80">
                See how coverage works <ArrowRight className="h-3 w-3" />
              </button>
            </div>

            {/* Sidebar */}
            <div className="space-y-5">
              <div className="rounded-2xl border border-surface-border/10 bg-surface-card p-5">
                <h3 className="text-[13.5px] font-semibold text-text-primary">How It Works</h3>
                <ol className="mt-3 space-y-3.5">
                  {howItWorks.map(s => (
                    <li key={s.n} className="flex gap-2.5">
                      <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-accent-violet/10 text-[10.5px] font-bold text-accent-violet">{s.n}</span>
                      <div>
                        <p className="text-[12.5px] font-semibold text-text-primary">{s.title}</p>
                        <p className="text-[11.5px] leading-relaxed text-text-secondary">{s.body}</p>
                      </div>
                    </li>
                  ))}
                </ol>
              </div>

              <div className="rounded-2xl border border-surface-border/10 bg-surface-card p-5 text-center">
                <Building2 className="mx-auto h-4 w-4 text-text-muted" />
                <p className="mt-2 text-[22px] font-bold tabular-nums text-text-primary">
                  {universeTotal != null ? universeTotal.toLocaleString() : "—"}
                </p>
                <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">Companies Tracked</p>
                <Link href="/companies" className="mt-2 inline-block text-[11.5px] font-semibold text-accent-violet hover:text-accent-violet/80">
                  Learn more about our universe →
                </Link>
              </div>

              <div className="rounded-2xl border border-accent-violet/15 bg-accent-violet/[0.05] p-5 text-center">
                <MessageCircleQuestion className="mx-auto h-4 w-4 text-accent-violet" />
                <p className="mt-2 text-[12.5px] font-semibold text-text-primary">Ready to investigate?</p>
                <p className="mt-0.5 text-[11.5px] text-text-secondary">Ask AI Search anything about your holdings.</p>
                <Link href="/ai-search" className="mt-3 flex items-center justify-center gap-1.5 rounded-xl bg-accent-violet px-3 py-2 text-[12.5px] font-semibold text-white transition hover:bg-accent-violet/90">
                  Open AI Search <ArrowRight className="h-3.5 w-3.5" />
                </Link>
              </div>
            </div>
          </div>

          {/* All Holdings */}
          <div id="all-holdings" className="scroll-mt-6">
            <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
              <div>
                <h2 className="text-[15px] font-semibold text-text-primary">All Holdings Overview</h2>
                <p className="text-[12px] text-text-muted">{total} holding{total === 1 ? "" : "s"} analyzed</p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <div className="flex flex-wrap gap-1.5" role="group" aria-label="Filter holdings">
                  {TABLE_FILTERS.map(f => (
                    <button
                      key={f.id}
                      onClick={() => setFilter(f.id)}
                      aria-pressed={filter === f.id}
                      className={`rounded-full border px-3 py-1.5 text-[11.5px] font-semibold transition ${
                        filter === f.id
                          ? "border-accent-violet/30 bg-accent-violet/10 text-accent-violet"
                          : "border-surface-border/12 bg-surface-card text-text-secondary hover:text-text-primary"
                      }`}
                    >
                      {f.label}
                    </button>
                  ))}
                </div>
                <button onClick={exportCSV} className="inline-flex items-center gap-1.5 rounded-full border border-surface-border/15 bg-surface-card px-3 py-1.5 text-[11.5px] font-semibold text-text-secondary transition hover:text-text-primary">
                  <Download className="h-3.5 w-3.5" /> Export
                </button>
              </div>
            </div>

            {/* Desktop table */}
            <div className="hidden overflow-x-auto rounded-2xl border border-surface-border/10 bg-surface-card sm:block">
              <table className="w-full text-left">
                <thead>
                  <tr className="border-b border-surface-border/10 text-[10.5px] uppercase tracking-wide text-text-muted">
                    <th className="px-4 py-3 font-semibold">Company</th>
                    <th className="px-4 py-3 font-semibold">Match</th>
                    <th className="px-4 py-3 font-semibold">Latest Signal</th>
                    <th className="px-4 py-3 font-semibold">Events</th>
                    <th className="px-4 py-3 font-semibold">News</th>
                    <th className="px-4 py-3 font-semibold">Coverage</th>
                    <th className="px-4 py-3 font-semibold text-right">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((h, i) => <HoldingRow key={i} h={h} />)}
                </tbody>
              </table>
              {filtered.length === 0 && <p className="px-4 py-8 text-center text-[12.5px] text-text-muted">No holdings match this filter.</p>}
            </div>

            {/* Mobile cards */}
            <div className="space-y-2.5 sm:hidden">
              {filtered.map((h, i) => <HoldingCard key={i} h={h} />)}
              {filtered.length === 0 && (
                <p className="rounded-xl border border-surface-border/10 bg-surface-card px-4 py-8 text-center text-[12.5px] text-text-muted">No holdings match this filter.</p>
              )}
            </div>
          </div>

          {/* Methodology */}
          <div id="methodology" className="scroll-mt-6 rounded-2xl border border-accent-violet/15 bg-accent-violet/[0.04] p-5">
            <div className="flex items-start gap-3">
              <HelpCircle className="mt-0.5 h-4 w-4 shrink-0 text-accent-violet" />
              <div>
                <p className="text-[13.5px] font-semibold text-text-primary">How coverage is calculated</p>
                <p className="mt-1 text-[12.5px] leading-relaxed text-text-secondary">
                  Each holding&apos;s coverage verdict (Strong, Moderate, Thin, or Unresolved) reflects how much
                  real event and news activity Market Ripple has tracked for it in the last {data.window_days} days —
                  it is a measure of our intelligence coverage, not the quality of the investment. Thin coverage
                  does not mean the company is weak, inactive, or a bad investment; it means our current local
                  evidence is limited. Price movement and theme signals are separate, live market data, not
                  AI-assessed impact scores.
                </p>
              </div>
            </div>
          </div>

          {/* Bottom */}
          <div className="rounded-2xl border border-surface-border/10 bg-surface-card p-6 text-center">
            <p className="text-[14px] font-semibold text-text-primary">Want to investigate something deeper?</p>
            <div className="mt-4 flex flex-col items-center justify-center gap-3 sm:flex-row">
              <Link href="/ai-search" className="flex w-full items-center justify-center gap-1.5 rounded-xl bg-accent-violet px-4 py-2.5 text-[13px] font-semibold text-white transition hover:bg-accent-violet/90 sm:w-auto">
                <Sparkles className="h-3.5 w-3.5" /> Explore Market Ripple AI Search
              </Link>
              <button onClick={handleReset} className="flex w-full items-center justify-center gap-1.5 rounded-xl border border-surface-border/15 px-4 py-2.5 text-[13px] font-semibold text-text-secondary transition hover:text-text-primary sm:w-auto">
                <RefreshCw className="h-3.5 w-3.5" /> Analyze Another Portfolio
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Row/card renderers ───────────────────────────────────────────────────

function HoldingRow({ h }: { h: HoldingResult }) {
  const meta = LEVEL_META[h.level];
  const hasPrice = h.price_pct != null;
  return (
    <tr className="border-b border-surface-border/6 last:border-0">
      <td className="px-4 py-3.5">
        <p className="text-[13px] font-semibold text-text-primary">{h.name ?? h.input}</p>
        {h.symbol && <p className="text-[11px] text-text-muted">{h.symbol}</p>}
        {h.level === "not_tracked" && (
          h.suggestions.length > 0 ? (
            <p className="mt-0.5 text-[11px] text-text-muted">
              Did you mean <span className="font-medium text-text-secondary">{h.suggestions[0].name} ({h.suggestions[0].symbol})</span>?
            </p>
          ) : (
            <p className="mt-0.5 text-[11px] text-text-muted">No matching company found.</p>
          )
        )}
      </td>
      <td className="px-4 py-3.5 text-[12px]">
        <span className={`inline-flex items-center gap-1 ${h.resolved ? "text-emerald-600 dark:text-emerald-300" : "text-rose-500"}`}>
          {h.resolved ? <CheckCircle2 className="h-3.5 w-3.5" /> : <XCircle className="h-3.5 w-3.5" />}
          {matchLabel(h)}
        </span>
      </td>
      <td className="px-4 py-3.5 text-[12.5px] tabular-nums">
        {hasPrice ? (
          <>
            <p className="font-semibold text-text-primary">₹{h.price}</p>
            <span className={`inline-flex items-center gap-1 font-medium ${h.price_pct! >= 0 ? "text-emerald-600 dark:text-emerald-300" : "text-rose-500"}`}>
              {h.price_pct! >= 0 ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
              {h.price_pct! >= 0 ? "+" : ""}{h.price_pct!.toFixed(2)}%
            </span>
          </>
        ) : (
          <span className="text-text-muted">—</span>
        )}
      </td>
      <td className="px-4 py-3.5 text-[13px] font-medium tabular-nums text-text-primary">{h.event_count}</td>
      <td className="px-4 py-3.5 text-[13px] font-medium tabular-nums text-text-primary">{h.news_count}</td>
      <td className="px-4 py-3.5">
        <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10.5px] font-bold uppercase tracking-wide ${meta.badge}`}>{meta.label}</span>
      </td>
      <td className="px-4 py-3.5 text-right">
        <HoldingAction h={h} compact />
      </td>
    </tr>
  );
}

function HoldingCard({ h }: { h: HoldingResult }) {
  const meta = LEVEL_META[h.level];
  const hasPrice = h.price_pct != null;
  return (
    <div className="rounded-xl border border-surface-border/10 bg-surface-card p-4">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate text-[13.5px] font-semibold text-text-primary">{h.name ?? h.input}</p>
          {h.symbol && <p className="text-[11px] text-text-muted">{h.symbol} · {matchLabel(h)}</p>}
        </div>
        <span className={`shrink-0 rounded-full border px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide ${meta.badge}`}>{meta.label}</span>
      </div>
      <div className="mt-3 flex items-center gap-4 text-[12px] text-text-secondary">
        <span><span className="font-semibold tabular-nums text-text-primary">{h.event_count}</span> events</span>
        <span><span className="font-semibold tabular-nums text-text-primary">{h.news_count}</span> news</span>
        {hasPrice && (
          <span className={`inline-flex items-center gap-1 font-semibold ${h.price_pct! >= 0 ? "text-emerald-600 dark:text-emerald-300" : "text-rose-500"}`}>
            ₹{h.price} ({h.price_pct! >= 0 ? "+" : ""}{h.price_pct!.toFixed(2)}%)
          </span>
        )}
      </div>
      <p className="mt-2 text-[11.5px] leading-relaxed text-text-muted">{h.message}</p>
      {h.level === "not_tracked" && h.suggestions.length > 0 && <SuggestionsList suggestions={h.suggestions} />}
      {h.level === "not_tracked" && h.suggestions.length === 0 && <p className="mt-2 text-[11.5px] text-text-muted">No matching company found.</p>}
      <div className="mt-3"><HoldingAction h={h} /></div>
    </div>
  );
}

function SuggestionsList({ suggestions }: { suggestions: Suggestion[] }) {
  return (
    <div className="mt-2">
      <p className="text-[11px] font-semibold text-text-muted">Possible matches</p>
      <ul className="mt-1 space-y-0.5">
        {suggestions.map(s => (
          <li key={s.symbol} className="text-[12px] text-text-secondary">{s.name} <span className="text-text-muted">({s.symbol})</span></li>
        ))}
      </ul>
    </div>
  );
}

function HoldingAction({ h, compact }: { h: HoldingResult; compact?: boolean }) {
  const size = compact ? "text-[11.5px]" : "text-[12.5px]";
  const label = actionLabel(h);
  if ((h.level === "strong" || h.level === "light") && h.symbol) {
    return (
      <Link href={`/companies/${h.symbol}`} className={`inline-flex items-center gap-1 font-semibold text-accent-violet transition hover:text-accent-violet/80 ${size}`}>
        <Radio className="h-3.5 w-3.5" /> {label}
      </Link>
    );
  }
  // thin or not_tracked — bridge into the existing AI Search deep link,
  // exact same construction (/ai-search?q=...) used elsewhere on this site.
  return (
    <Link href={`/ai-search?q=${encodeURIComponent(h.ai_search_query)}`} className={`inline-flex items-center gap-1 font-semibold text-accent-violet transition hover:text-accent-violet/80 ${size}`}>
      <Sparkles className="h-3.5 w-3.5" /> {label} <ExternalLink className="h-3 w-3" />
    </Link>
  );
}
