"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Grid3x3, Target, Sparkles, Calendar, Rocket } from "lucide-react";
import { API_BASE_URL as API } from "@/lib/api";
import { HubHero, type HubStat } from "@/components/HubHero";
import { HubTabBar, type HubTab } from "@/components/HubTabBar";
import { calendarCategoryLabel } from "@/lib/economicCalendarCategory";


// ── Types ─────────────────────────────────────────────────────────────────────

interface RadarItem {
  id: string | number;
  theme: string;
  score: number | null;
  reason: string;
  confidence: number | null;
  beneficiaries: string[];
  sectors?: string[];
  trend?: string | null;
}

// ── Filter option lists (UI chrome, not market data) ───────────────────────────

const SECTORS_FILTER = ["All Sectors", "Infrastructure", "Energy", "Technology", "Banking", "Manufacturing", "Healthcare", "FMCG"];
const THEMES_FILTER  = ["All Themes", "AI & Automation", "Green Energy", "Infrastructure", "Defence", "EV", "Pharma"];
const HORIZONS       = ["All", "Short Term", "Medium Term", "Long Term"];

const SECTOR_BAR_COLORS = [
  "from-violet-500 to-indigo-500", "from-sky-500 to-blue-500", "from-blue-500 to-cyan-500",
  "from-emerald-500 to-teal-500", "from-amber-500 to-orange-500",
];

const CHIP_COLORS = [
  "bg-violet-500/25 text-violet-700 dark:text-violet-200",
  "bg-sky-500/25 text-sky-700 dark:text-sky-200",
  "bg-emerald-500/25 text-emerald-700 dark:text-emerald-200",
  "bg-amber-500/25 text-amber-700 dark:text-amber-200",
  "bg-rose-500/25 text-rose-700 dark:text-rose-200",
  "bg-teal-500/25 text-teal-700 dark:text-teal-200",
];

// ── Sub-components ────────────────────────────────────────────────────────────

function confidenceColor(c: number | null | undefined) {
  if (c === null || c === undefined) return { ring: "ring-surface-border/9", text: "text-text-muted", fill: "stroke-slate-600" };
  if (c >= 0.9) return { ring: "ring-emerald-500/40", text: "text-emerald-400", fill: "stroke-emerald-500" };
  if (c >= 0.8) return { ring: "ring-sky-500/40",     text: "text-sky-400",     fill: "stroke-sky-500"     };
  return               { ring: "ring-amber-500/40",   text: "text-amber-400",   fill: "stroke-amber-500"   };
}

function ConfidenceCircle({ value, size = 64 }: { value: number | null | undefined; size?: number }) {
  const unscored = value === null || value === undefined;
  const pct = unscored ? 0 : Math.round(value * 100);
  const r   = (size - 8) / 2;
  const circ = 2 * Math.PI * r;
  const dash = (pct / 100) * circ;
  const cc   = confidenceColor(value);
  return (
    <div className="relative flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }}>
        <circle cx={size/2} cy={size/2} r={r} stroke="rgb(var(--text-primary) / 0.06)" strokeWidth={4} fill="none"/>
        {!unscored && (
          <circle cx={size/2} cy={size/2} r={r} stroke="currentColor" className={cc.fill} strokeWidth={4} fill="none" strokeLinecap="round" strokeDasharray={`${dash} ${circ}`}/>
        )}
      </svg>
      <div className="absolute text-center">
        <div className={`text-[11px] font-bold ${cc.text}`}>{unscored ? "N/A" : `${pct}%`}</div>
      </div>
    </div>
  );
}

function ScoreBadge({ score }: { score: number | null | undefined }) {
  const unscored = score === null || score === undefined;
  const bg = unscored ? "from-slate-700 to-slate-600"
           : score >= 90 ? "from-emerald-500 to-teal-400"
           : score >= 80 ? "from-sky-500 to-blue-400"
           : "from-amber-500 to-yellow-400";
  return (
    <div className={`flex h-14 w-14 items-center justify-center rounded-full bg-gradient-to-br ${bg} shadow-lg`}>
      <span className={`font-black text-text-primary ${unscored ? "text-[9px]" : "text-xl"}`}>{unscored ? "N/A" : score}</span>
    </div>
  );
}

function OpportunityCardGrid({ displayed }: { displayed: RadarItem[] }) {
  if (displayed.length === 0) {
    return (
      <div className="col-span-full flex flex-col items-center justify-center rounded-[20px] border border-surface-border/10 bg-text-primary/[0.03] py-20 text-center">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-8 w-8 text-text-muted"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
        <p className="mt-3 text-sm font-semibold text-text-primary">No opportunities match right now</p>
      </div>
    );
  }
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
      {displayed.map((item) => {
        const conf = item.confidence;
        const unscoredConf = conf === null || conf === undefined;
        const cc   = confidenceColor(conf);
        const beneficiaries = Array.isArray(item.beneficiaries) ? item.beneficiaries : [];
        const sectors = Array.isArray(item.sectors) ? item.sectors : [];
        return (
          <div key={item.id} className="flex flex-col rounded-[20px] border border-surface-border/10 bg-text-primary/[0.03] p-4 hover:border-surface-border/20 hover:-translate-y-0.5 transition">
            <div className="mb-3 flex items-start justify-between gap-3">
              <ScoreBadge score={item.score}/>
              <div className="min-w-0 flex-1">
                <h3 className="text-[13px] font-bold leading-snug text-text-primary">{item.theme}</h3>
                {sectors.length > 0 && <p className="mt-0.5 text-[11px] text-text-muted">{sectors.join(" • ")}</p>}
              </div>
            </div>
            <div className="mb-3 flex items-center gap-3">
              <ConfidenceCircle value={conf} size={52}/>
              <div className="min-w-0">
                <p className="text-[10px] text-text-muted">Confidence</p>
                <p className={`text-base font-bold ${cc.text}`}>{unscoredConf ? "Unscored" : `${Math.round(conf * 100)}%`}</p>
              </div>
              <div className="flex-1">
                <div className="h-1.5 overflow-hidden rounded-full bg-text-primary/[0.06]">
                  {!unscoredConf && (
                    <div className={`h-full rounded-full ${cc.ring.replace("ring-","bg-").replace("/40","")}`} style={{ width: `${Math.round(conf * 100)}%` }}/>
                  )}
                </div>
              </div>
            </div>
            <p className="mb-3 text-[12px] leading-4 text-text-secondary line-clamp-2">{item.reason}</p>
            {beneficiaries.length > 0 && (
              <div className="mb-3">
                <p className="mb-1.5 text-[9px] uppercase tracking-widest text-text-muted">Top Beneficiaries</p>
                <div className="flex items-center gap-1">
                  {beneficiaries.slice(0, 5).map((b, bi) => (
                    <Link key={bi} href={`/companies/${b.replace(/[&\s]/g, "")}`} title={b}
                      className={`flex h-7 w-7 items-center justify-center rounded-full border border-surface-border/10 text-[9px] font-bold hover:scale-110 transition ${CHIP_COLORS[bi % CHIP_COLORS.length]}`}>
                      {b.slice(0, 2).toUpperCase()}
                    </Link>
                  ))}
                </div>
              </div>
            )}
            <div className="mt-auto pt-2 border-t border-surface-border/5">
              <Link href={`/opportunity-radar/${item.id}`} className="flex items-center gap-1 text-[12px] font-medium text-sky-400 hover:text-sky-600 dark:text-sky-300 transition">
                View Details
                <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7"/></svg>
              </Link>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── All Opportunities tab (the former whole page) ──────────────────────────────

function AllOpportunitiesTab({ items, loading }: { items: RadarItem[]; loading: boolean }) {
  const [sectorFilter, setSectorFilter] = useState("All Sectors");
  const [themeFilter, setThemeFilter]   = useState("All Themes");
  const [horizon, setHorizon]           = useState("All");
  const [minScore, setMinScore]         = useState(0);

  // Real, derived from the actual items on screen — not a fabricated fixed
  // list. Averages each sector's opportunity_score across every item that
  // names it, so it moves with real data instead of being hardcoded.
  const topSectors = useMemo(() => {
    const bySector = new Map<string, { total: number; count: number }>();
    for (const item of items) {
      if (item.score === null) continue;
      for (const s of item.sectors ?? []) {
        const cur = bySector.get(s) ?? { total: 0, count: 0 };
        cur.total += item.score;
        cur.count += 1;
        bySector.set(s, cur);
      }
    }
    return Array.from(bySector.entries())
      .map(([name, { total, count }]) => ({ name, score: Math.round(total / count) }))
      .sort((a, b) => b.score - a.score)
      .slice(0, 5);
  }, [items]);

  const displayed = items.filter(i => {
    if (minScore > 0 && (i.score === null || i.score === undefined || i.score < minScore)) return false;
    if (sectorFilter !== "All Sectors" && !(i.sectors ?? []).some(s => s.toLowerCase().includes(sectorFilter.toLowerCase()))) return false;
    if (themeFilter !== "All Themes" && !i.theme.toLowerCase().includes(themeFilter.toLowerCase().replace("ai & automation", "ai").replace("green energy", "energy"))) return false;
    return true;
  });

  return (
    <>
      <div className="mb-6 flex flex-wrap gap-2">
        <select value={sectorFilter} onChange={e => setSectorFilter(e.target.value)} className="rounded-xl border border-surface-border/10 bg-text-primary/[0.03] px-3 py-2 text-[13px] text-text-secondary outline-none hover:border-surface-border/20">
          {SECTORS_FILTER.map(s => <option key={s} value={s} className="bg-surface-card">{s}</option>)}
        </select>
        <select value={themeFilter} onChange={e => setThemeFilter(e.target.value)} className="rounded-xl border border-surface-border/10 bg-text-primary/[0.03] px-3 py-2 text-[13px] text-text-secondary outline-none hover:border-surface-border/20">
          {THEMES_FILTER.map(t => <option key={t} value={t} className="bg-surface-card">{t}</option>)}
        </select>
        <select value={horizon} onChange={e => setHorizon(e.target.value)} className="rounded-xl border border-surface-border/10 bg-text-primary/[0.03] px-3 py-2 text-[13px] text-text-secondary outline-none hover:border-surface-border/20">
          {HORIZONS.map(h => <option key={h} value={h} className="bg-surface-card">{h}</option>)}
        </select>
        <select onChange={e => setMinScore(Number(e.target.value))} className="rounded-xl border border-surface-border/10 bg-text-primary/[0.03] px-3 py-2 text-[13px] text-text-secondary outline-none hover:border-surface-border/20">
          <option value={0} className="bg-surface-card">Min Score</option>
          <option value={80} className="bg-surface-card">80+</option>
          <option value={85} className="bg-surface-card">85+</option>
          <option value={90} className="bg-surface-card">90+</option>
        </select>
      </div>

      <div className="grid grid-cols-1 items-start gap-5 lg:grid-cols-[1fr_220px]">
        {loading ? (
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {[1,2,3,4,5,6].map(i => <div key={i} className="h-[280px] animate-pulse rounded-[20px] border border-surface-border/6 bg-text-primary/[0.02]" />)}
          </div>
        ) : (
          <OpportunityCardGrid displayed={displayed} />
        )}

        <aside className="rounded-[20px] border border-surface-border/10 bg-text-primary/[0.03] p-4 lg:sticky lg:top-[84px]">
          <h3 className="mb-4 text-[11px] font-semibold uppercase tracking-wider text-text-secondary">Top Sectors</h3>
          {topSectors.length === 0 ? (
            <p className="text-[11px] text-text-muted">Not enough scored opportunities yet to rank sectors.</p>
          ) : (
            <div className="space-y-3.5">
              {topSectors.map((s, i) => (
                <div key={s.name}>
                  <div className="mb-1.5 flex items-center justify-between">
                    <span className="text-[13px] font-medium text-text-primary">{s.name}</span>
                    <span className="text-[13px] font-bold text-text-primary">{s.score}</span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-text-primary/[0.06]">
                    <div className={`h-full rounded-full bg-gradient-to-r ${SECTOR_BAR_COLORS[i % SECTOR_BAR_COLORS.length]}`} style={{ width: `${s.score}%` }}/>
                  </div>
                </div>
              ))}
            </div>
          )}
          <div className="mt-6 border-t border-surface-border/5 pt-4">
            <Link href="/ai-search?q=top investment opportunities India"
              className="block w-full rounded-xl bg-gradient-to-r from-violet-600/80 to-sky-500/80 py-2 text-center text-[12px] font-semibold text-text-primary hover:opacity-90 transition">
              Ask AI for Analysis
            </Link>
          </div>
        </aside>
      </div>
    </>
  );
}

// ── Upcoming Events tab (real forward-looking economic calendar data) ─────────

interface CalendarEvent { id: string; category: string; title: string; date: string; description: string }

function UpcomingEventsTab() {
  const [events, setEvents] = useState<CalendarEvent[] | null>(null);
  useEffect(() => {
    fetch(`${API}/api/market/calendar`).then(r => r.ok ? r.json() : null).then(d => setEvents(d?.events ?? [])).catch(() => setEvents([]));
  }, []);

  if (events === null) {
    return <div className="grid gap-3 sm:grid-cols-2">{[1,2,3,4].map(i => <div key={i} className="h-24 animate-pulse rounded-2xl border border-surface-border/6 bg-text-primary/[0.02]" />)}</div>;
  }
  if (events.length === 0) {
    return <p className="rounded-2xl border border-surface-border/10 bg-text-primary/[0.03] py-16 text-center text-[13px] text-text-muted">No upcoming calendar events right now.</p>;
  }
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {events.map(ev => (
        <div key={ev.id} className="rounded-2xl border border-surface-border/10 bg-text-primary/[0.03] p-4">
          <div className="mb-1.5 flex items-center justify-between">
            <span className="rounded-full border border-sky-500/25 bg-sky-500/10 px-2 py-0.5 text-[10px] font-bold text-sky-500">{calendarCategoryLabel(ev.category)}</span>
            <span className="text-[11px] text-text-muted">{ev.date}</span>
          </div>
          <h3 className="text-[13px] font-bold text-text-primary">{ev.title}</h3>
          <p className="mt-1 text-[12px] leading-5 text-text-secondary line-clamp-2">{ev.description}</p>
        </div>
      ))}
    </div>
  );
}

// ── IPO Watch tab (real, reuses the IPO Hub's own endpoint) ───────────────────

interface IpoSummary { id: string; name: string; sector: string; status: string; priceMin: number; priceMax: number; gmpPct: number; listingDate: string }

function IpoWatchTab() {
  const [ipos, setIpos] = useState<IpoSummary[] | null>(null);
  useEffect(() => {
    fetch(`${API}/api/ipo/`).then(r => r.ok ? r.json() : null).then(d => setIpos((d?.ipos ?? []).filter((i: any) => i.status === "Upcoming"))).catch(() => setIpos([]));
  }, []);

  if (ipos === null) {
    return <div className="grid gap-3 sm:grid-cols-2">{[1,2,3,4].map(i => <div key={i} className="h-24 animate-pulse rounded-2xl border border-surface-border/6 bg-text-primary/[0.02]" />)}</div>;
  }
  if (ipos.length === 0) {
    return (
      <div className="rounded-2xl border border-surface-border/10 bg-text-primary/[0.03] py-16 text-center">
        <p className="text-[13px] text-text-muted">No upcoming IPOs tracked right now.</p>
        <Link href="/companies?tab=ipo-hub" className="mt-3 inline-block text-[12px] font-semibold text-sky-500 hover:text-sky-600">View full IPO Hub →</Link>
      </div>
    );
  }
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {ipos.map(ipo => {
        // The listingDate field on some IPO records is itself placeholder
        // text ("Example date — placeholder"), not a real date — a
        // pre-existing data-quality gap in the underlying IPO data source
        // (the standalone IPO Hub page displays the same raw field
        // unfiltered). Surfacing it prominently in a new compact card
        // would read as a fabricated real date, so it's only shown when it
        // actually looks like one.
        const hasRealDate = /\d/.test(ipo.listingDate) && !/placeholder|example/i.test(ipo.listingDate);
        return (
          <Link key={ipo.id} href="/companies?tab=ipo-hub" className="rounded-2xl border border-surface-border/10 bg-text-primary/[0.03] p-4 transition hover:border-violet-500/25">
            <div className="mb-1.5 flex items-center justify-between">
              <span className="rounded-full border border-violet-500/25 bg-violet-500/10 px-2 py-0.5 text-[10px] font-bold text-violet-500">{ipo.sector}</span>
              {hasRealDate && <span className="text-[11px] text-text-muted">Lists {ipo.listingDate}</span>}
            </div>
            <h3 className="text-[13px] font-bold text-text-primary">{ipo.name}</h3>
            <p className="mt-1 text-[12px] text-text-secondary">₹{ipo.priceMin}–₹{ipo.priceMax} · GMP {ipo.gmpPct >= 0 ? "+" : ""}{ipo.gmpPct}%</p>
          </Link>
        );
      })}
    </div>
  );
}

// ── Page (hub shell) ────────────────────────────────────────────────────────────

const TABS: HubTab[] = [
  { id: "all",           label: "All Opportunities", icon: <Grid3x3 className="h-3.5 w-3.5" /> },
  { id: "high-conviction", label: "High Conviction", icon: <Target className="h-3.5 w-3.5" /> },
  { id: "emerging",      label: "Emerging",          icon: <Sparkles className="h-3.5 w-3.5" /> },
  { id: "events",        label: "Upcoming Events",   icon: <Calendar className="h-3.5 w-3.5" /> },
  { id: "ipo",           label: "IPO Watch",         icon: <Rocket className="h-3.5 w-3.5" /> },
];

export default function OpportunityRadarPage() {
  const [activeTab, setActiveTab] = useState("all");
  const [items, setItems]     = useState<RadarItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API}/api/radar/?page=1&page_size=20`)
      .then(r => r.ok ? r.json() : null)
      .then(d => {
        const raw = Array.isArray(d) ? d : (d?.items ?? []);
        const mapped: RadarItem[] = raw.map((o: any) => {
          const rawScore = o.opportunity_score ?? o.score;
          const rawConf = o.confidence;
          return {
            id:           o.id,
            theme:        o.title,
            score:        rawScore === null || rawScore === undefined ? null : Math.round(rawScore),
            reason:       o.summary ?? o.reason ?? "",
            confidence:   typeof rawConf === "number" ? (rawConf > 1 ? rawConf / 100 : rawConf) : null,
            beneficiaries: (o.companies ?? []).map((c: any) => typeof c === "string" ? c : c.symbol),
            sectors:      o.sectors ?? [],
            trend:        o.trend ?? null,
          };
        });
        setItems(mapped);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  // High Conviction / Emerging are real, derivable from the same score +
  // confidence + trend fields the API already returns — never a fabricated
  // "Today's Opportunities" style bucket. There's no date field on this
  // endpoint (confirmed live), so a real date-based tab isn't buildable
  // without a backend change — that tab is held back entirely rather than
  // faked, per the same principle already applied elsewhere in this pass.
  const highConviction = useMemo(
    () => items.filter(i => (i.score ?? 0) >= 90 && (i.confidence ?? 0) >= 0.85),
    [items],
  );
  const emerging = useMemo(
    () => items.filter(i => {
      const trendPositive = (i.trend ?? "").toLowerCase() === "positive";
      const midScore = (i.score ?? 0) >= 55 && (i.score ?? 0) < 90;
      return trendPositive && midScore;
    }),
    [items],
  );

  const scored = items.filter(i => i.score !== null);
  const avgScore = scored.length > 0 ? Math.round(scored.reduce((a, b) => a + (b.score ?? 0), 0) / scored.length) : null;
  const stats: HubStat[] = [
    { label: "Opportunities", value: String(items.length) },
    { label: "High Conviction", value: String(highConviction.length) },
    ...(avgScore != null ? [{ label: "Avg Score", value: String(avgScore) }] : []),
    { label: "Signal", value: "Live" },
  ];

  return (
    <main className="min-w-0 pb-10">
      <HubHero
        hub="Opportunity Radar"
        eyebrow="AI-Powered"
        title="Today's investment ideas, ranked"
        pitch="Themes and market opportunities ranked by AI signal strength — the actionable end of the MarketRipple pipeline."
        stats={stats}
        quickActions={[
          { label: "IPO Hub", href: "/companies?tab=ipo-hub" },
          { label: "Ask AI for Analysis", href: "/ai-search?q=top investment opportunities India" },
        ]}
      />
      <div className="mb-6">
        <HubTabBar hub="Opportunity Radar" tabs={TABS} active={activeTab} onChange={setActiveTab} />
      </div>

      {activeTab === "all"             && <AllOpportunitiesTab items={items} loading={loading} />}
      {activeTab === "high-conviction" && <OpportunityCardGrid displayed={highConviction} />}
      {activeTab === "emerging"        && <OpportunityCardGrid displayed={emerging} />}
      {activeTab === "events"          && <UpcomingEventsTab />}
      {activeTab === "ipo"             && <IpoWatchTab />}
    </main>
  );
}
