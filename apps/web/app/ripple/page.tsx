import type { ReactNode } from "react";
import Link from "next/link";
import type { Metadata } from "next";
import { Flame, Landmark, Building2, Repeat2, Telescope, Zap, Link2, BarChart2, Plane, Factory } from "lucide-react";
import { MarketContextStrip } from "@/components/MarketContextStrip";
import { NextSteps } from "@/components/NextSteps";
import { API_BASE_URL as API } from "@/lib/api";

export const metadata: Metadata = {
  title: "Ripple Engine — Market Dependency Graph | MarketRipple",
  description: "Discover how one market event creates cascading effects across sectors, commodities, companies, and the broader Indian economy.",
};

export const dynamic = "force-dynamic";


const TYPE_BADGE: Record<string, { label: string; cls: string }> = {
  geopolitical: { label: "Global Event",       cls: "border-rose-500/30 bg-rose-500/10 text-rose-400" },
  macro:        { label: "Economy",            cls: "border-amber-500/30 bg-amber-500/10 text-amber-400" },
  monetary:     { label: "Central Bank",       cls: "border-sky-500/30 bg-sky-500/10 text-sky-400" },
  fiscal:       { label: "Government Budget",  cls: "border-violet-500/30 bg-violet-500/10 text-violet-400" },
  earnings:     { label: "Company Earnings",   cls: "border-emerald-500/30 bg-emerald-500/10 text-emerald-400" },
  commodity:    { label: "Raw Materials",      cls: "border-amber-500/30 bg-amber-500/10 text-amber-400" },
};

function impactColor(score: number) {
  if (score >= 8) return "text-rose-400";
  if (score >= 6) return "text-amber-400";
  return "text-emerald-400";
}

function impactLabel(score: number) {
  if (score >= 8) return "Very High";
  if (score >= 6) return "High";
  if (score >= 4) return "Medium";
  return "Low";
}

async function fetchFeatured() {
  try {
    const r = await fetch(`${API}/api/ripple/featured?limit=9`, { cache: "no-store" });
    if (r.ok) return r.json();
  } catch {}
  return [];
}

// Static examples shown when no events are in DB
const STATIC_EXAMPLES = [
  { id: 1,  title: "India-Pakistan Military Tensions",   summary: "Cross-border conflict escalation triggers defence sector rally and risk-off sentiment in Indian markets.", event_type: "geopolitical", impact_score: 9.2, categories: ["Defence", "Energy", "Aviation"] },
  { id: 2,  title: "RBI Emergency Rate Cut — 50 bps",   summary: "Surprise rate cut to stimulate growth sends banking sector NIM lower and real estate stocks surging.", event_type: "monetary",     impact_score: 8.7, categories: ["Banking", "Real Estate", "NBFCs"] },
  { id: 3,  title: "Union Budget 2026 — Capex Surge",   summary: "Government announces ₹15 lakh crore infrastructure capex, largest ever allocation for railways and defence.", event_type: "fiscal",       impact_score: 8.1, categories: ["Infrastructure", "Defence", "Cement"] },
  { id: 4,  title: "OPEC+ Cuts Production by 2M bbl/d", summary: "Saudi-led supply cut drives Brent crude above $90, triggering aviation and logistics sector sell-off.", event_type: "commodity",     impact_score: 8.5, categories: ["Energy", "Aviation", "Chemicals"] },
  { id: 5,  title: "FII Record Inflows — ₹45,000Cr",    summary: "Largest ever single-month FII inflow into Indian equities triggers broad-based mid-cap rally.", event_type: "macro",        impact_score: 7.8, categories: ["Banking", "IT", "Mid-caps"] },
  { id: 6,  title: "India GDP Growth Hits 8.4% Q2",     summary: "Strong Q2 GDP print above estimates triggers rate expectation reset and broad market re-rating.", event_type: "macro",        impact_score: 7.3, categories: ["Consumer", "Banking", "Infra"] },
];

export default async function RipplePage() {
  const events: any[] = await fetchFeatured();
  const displayEvents = events.length > 0 ? events : STATIC_EXAMPLES;

  return (
    <div className="min-h-screen space-y-8 pb-16">
      <MarketContextStrip />

      {/* ── Hero ─────────────────────────────────────────────────────────── */}
      <div className="rounded-xl border border-indigo-500/15 bg-[#080c18] p-8">
        <div className="flex items-start justify-between gap-6">
          <div className="max-w-2xl">
            <div className="mb-3 flex items-center gap-2">
              <span className="flex items-center gap-1.5 rounded-full border border-indigo-500/30 bg-indigo-500/10 px-3 py-1 text-[11px] font-bold text-indigo-400">
                <svg viewBox="0 0 24 24" fill="currentColor" className="h-3 w-3"><path d="M12 2 L14.4 9.6 L22 9.6 L15.8 14.1 L18.2 21.7 L12 17 L5.8 21.7 L8.2 14.1 L2 9.6 L9.6 9.6 Z"/></svg> FLAGSHIP FEATURE
              </span>
              <span className="text-[11px] text-slate-600">Powered by Ripple Engine AI</span>
            </div>
            <h1 className="text-[32px] font-black text-white leading-tight mb-3">
              Market Dependency Graph™
              <br />
              <span className="text-[22px] font-semibold text-slate-400">Powered by Ripple Engine AI</span>
            </h1>
            <p className="text-[14px] text-slate-400 leading-7 max-w-xl">
              When one thing changes in the economy, it triggers a chain of effects. An interest rate cut makes loans cheaper, which helps real estate, which affects cement companies. This tool maps that entire chain — so you can see what to watch before the market reacts.
            </p>
            <div className="mt-5 flex flex-wrap gap-3">
              {([
                { icon: <Flame className="h-3.5 w-3.5" />,     text: "Commodity chains" },
                { icon: <Landmark className="h-3.5 w-3.5" />,  text: "Sector impacts" },
                { icon: <Building2 className="h-3.5 w-3.5" />, text: "Company P&L effects" },
                { icon: <Landmark className="h-3.5 w-3.5" />,  text: "Policy responses" },
                { icon: <Repeat2 className="h-3.5 w-3.5" />,   text: "Currency dynamics" },
                { icon: <Telescope className="h-3.5 w-3.5" />, text: "What-if scenarios" },
              ] as { icon: ReactNode; text: string }[]).map(f => (
                <span key={f.text} className="flex items-center gap-1.5 rounded-full border border-white/[0.07] bg-white/[0.03] px-3 py-1.5 text-[11px] text-slate-400">
                  {f.icon}{f.text}
                </span>
              ))}
            </div>
          </div>
          {/* Mini graph teaser */}
          <div className="hidden lg:flex flex-col items-center gap-2 shrink-0">
            <div className="relative w-[200px] h-[180px]">
              {/* Concentric rings */}
              {[180, 140, 100, 60].map((s, i) => (
                <div key={i} className="absolute inset-0 flex items-center justify-center">
                  <div className="rounded-full border border-white/[0.05]" style={{ width: s, height: s }} />
                </div>
              ))}
              {/* Center node */}
              <div className="absolute inset-0 flex items-center justify-center">
                <div className="h-12 w-12 rounded-full border-2 border-indigo-500 bg-[#120833] flex items-center justify-center text-indigo-400"><Zap className="h-5 w-5" /></div>
              </div>
              {/* Surrounding mini nodes */}
              {([
                { angle: -90,  color: "border-amber-500/60 bg-[#1a1200]",   icon: <Flame className="h-3 w-3 text-amber-400" />,    x: 100, y: 10 },
                { angle: -30,  color: "border-rose-500/60 bg-[#1a0008]",    icon: <Plane className="h-3 w-3 text-rose-400" />,     x: 160, y: 60 },
                { angle:  30,  color: "border-emerald-500/60 bg-[#001a10]", icon: <Factory className="h-3 w-3 text-emerald-400" />,x: 150, y: 120 },
                { angle:  90,  color: "border-sky-500/60 bg-[#001a2a]",     icon: <Landmark className="h-3 w-3 text-sky-400" />,   x: 100, y: 160 },
                { angle: 150,  color: "border-violet-500/60 bg-[#14001a]",  icon: <Building2 className="h-3 w-3 text-violet-400" />,x: 40, y: 120 },
                { angle: 210,  color: "border-teal-500/60 bg-[#001a1a]",    icon: <Repeat2 className="h-3 w-3 text-teal-400" />,   x: 30, y: 60 },
              ] as { angle: number; color: string; icon: ReactNode; x: number; y: number }[]).map((n, i) => (
                <div key={i} className="absolute" style={{ left: n.x - 12, top: n.y - 12 }}>
                  <div className={`w-6 h-6 rounded-lg border ${n.color} flex items-center justify-center`}>{n.icon}</div>
                </div>
              ))}
            </div>
            <p className="text-[10px] text-slate-600 text-center">Interactive force-directed graph</p>
          </div>
        </div>
      </div>

      {/* ── How it works ─────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {([
          { step: "1", icon: <Zap className="h-4 w-4 text-indigo-400" />,       title: "Select Event",       desc: "Choose any market event — geopolitical, macro, monetary, or earnings." },
          { step: "2", icon: <Link2 className="h-4 w-4 text-indigo-400" />,     title: "AI Ripple Analysis", desc: "Ripple Engine AI traces 4 levels of cascading effects across the market." },
          { step: "3", icon: <BarChart2 className="h-4 w-4 text-indigo-400" />, title: "Explore Graph",      desc: "Interactive force-directed graph with clickable nodes and animated edges." },
          { step: "4", icon: <Telescope className="h-4 w-4 text-indigo-400" />, title: "Run Scenarios",      desc: "Ask 'What if crude hits $100?' and get an instant AI-generated graph." },
        ] as { step: string; icon: ReactNode; title: string; desc: string }[]).map(s => (
          <div key={s.step} className="rounded-xl border border-white/[0.06] bg-[#0a0d16] p-4">
            <div className="flex items-center gap-2 mb-2">
              <span className="flex h-6 w-6 items-center justify-center rounded-full bg-indigo-500/15 text-[11px] font-black text-indigo-400">{s.step}</span>
              {s.icon}
            </div>
            <p className="text-[12px] font-bold text-white mb-1">{s.title}</p>
            <p className="text-[11px] text-slate-500 leading-5">{s.desc}</p>
          </div>
        ))}
      </div>

      {/* ── Event grid ───────────────────────────────────────────────────── */}
      <div>
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h2 className="text-[18px] font-bold text-white">Today's Biggest Ripples</h2>
            <p className="text-[12px] text-slate-500 mt-0.5">Click any event to launch the full Ripple Engine analysis</p>
          </div>
          <Link href="/events" className="text-[12px] text-sky-400 hover:text-sky-300 transition">
            All Events →
          </Link>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {displayEvents.map((ev: any) => {
            const badge = TYPE_BADGE[ev.event_type] || TYPE_BADGE.macro;
            const score = ev.impact_score ?? 7;
            const cats = ev.categories || [];
            return (
              <Link
                key={ev.id}
                href={`/ripple/${ev.id}`}
                className="group rounded-xl border border-white/[0.07] bg-[#0a0d16] p-5 hover:border-indigo-500/25 hover:bg-[#0d1028] transition-all"
              >
                {/* Header */}
                <div className="flex items-start justify-between gap-3 mb-3">
                  <span className={`rounded-full border px-2.5 py-0.5 text-[9px] font-bold uppercase tracking-wide ${badge.cls}`}>
                    {badge.label}
                  </span>
                  <div className="flex items-center gap-1 shrink-0">
                    <span className={`text-[18px] font-black leading-none tabular-nums ${impactColor(score)}`}>{score.toFixed(1)}</span>
                    <span className="text-[9px] text-slate-600">/10</span>
                  </div>
                </div>
                {/* Title */}
                <h3 className="text-[13px] font-bold text-white leading-snug mb-2 group-hover:text-indigo-300 transition-colors line-clamp-2">
                  {ev.title}
                </h3>
                {/* Summary */}
                <p className="text-[11px] text-slate-500 leading-5 line-clamp-2 mb-3">
                  {ev.summary || "Click to view ripple analysis →"}
                </p>
                {/* Categories */}
                {cats.length > 0 && (
                  <div className="flex flex-wrap gap-1.5">
                    {cats.slice(0, 3).map((c: string) => (
                      <span key={c} className="rounded border border-white/[0.06] bg-white/[0.03] px-2 py-0.5 text-[9px] text-slate-500">
                        {c}
                      </span>
                    ))}
                  </div>
                )}
                {/* Impact indicator */}
                <div className="mt-3 flex items-center justify-between">
                  <span className={`text-[10px] font-semibold ${impactColor(score)}`}>
                    {impactLabel(score)} Impact
                  </span>
                  <span className="text-[10px] text-slate-600 group-hover:text-indigo-400 transition-colors">
                    View Ripple Engine →
                  </span>
                </div>
              </Link>
            );
          })}
        </div>
      </div>

      {/* ── Stat strip ───────────────────────────────────────────────────── */}
      <div className="rounded-xl border border-white/[0.06] bg-[#0a0d16] p-5">
        <div className="grid grid-cols-2 sm:grid-cols-4 divide-x divide-white/[0.05]">
          {[
            { label: "Node Types Tracked", value: "7", sub: "Event → Company chain" },
            { label: "Ripple Depth Levels", value: "4", sub: "Direct to Long-term" },
            { label: "Edge Relationship Types", value: "7", sub: "Causes, Hurts, Benefits…" },
            { label: "AI Confidence Scoring", value: "Per Edge", sub: "0-100% on every link" },
          ].map(s => (
            <div key={s.label} className="px-6 first:pl-0 last:pr-0">
              <p className="text-[22px] font-black text-white tabular-nums">{s.value}</p>
              <p className="text-[11px] font-semibold text-slate-400 mt-0.5">{s.label}</p>
              <p className="text-[10px] text-slate-600 mt-0.5">{s.sub}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Intelligent guidance — derived from top ripple event */}
      {(() => {
        const top = displayEvents[0];
        if (!top) return null;
        const q    = (s: string) => encodeURIComponent(s);
        const cats = (top.categories ?? []).slice(0, 2).join(" and ");
        const shortTitle = top.title.length > 85 ? top.title.slice(0, 82) + "…" : top.title;
        return (
          <NextSteps config={{
            takeaway: `${shortTitle} is creating ripple effects${cats ? ` across ${cats}` : ""} — map the full chain to find where the real opportunity lies.`,
            primary: {
              label: "Read the full event analysis",
              why:   "Because understanding the origin of the ripple changes how you interpret downstream effects — start with the cause, not the symptoms.",
              href:  `/events/${top.id}`,
            },
            groups: [
              {
                label: "Understand More",
                actions: [
                  {
                    label: "Ask AI: What are the second-order effects?",
                    why:   "Because ripple effects compound — the real opportunity is often in companies two steps removed from the headline event.",
                    href:  `/ai-search?q=${q(`What are the second-order market effects of "${top.title}"? Which companies benefit indirectly?`)}`,
                  },
                ],
              },
              ...(cats ? [{
                label: "Monitor",
                actions: [{
                  label: `Track ${cats} sector news`,
                  why:   `Because monitoring sector news flow tells you when the ripple has peaked and when the opportunity window is closing.`,
                  href:  `/events?category=${top.event_type ?? ""}`,
                }],
              }] : []),
            ],
            path: ([top.event_type ?? "Event", ...(top.categories ?? []).slice(0, 2), "Investment Chain"] as string[]).filter(Boolean),
          }} />
        );
      })()}

    </div>
  );
}
