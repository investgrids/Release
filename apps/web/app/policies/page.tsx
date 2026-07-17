"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ClipboardList } from "lucide-react";
import { MarketContextStrip } from "@/components/MarketContextStrip";
import { NextSteps } from "@/components/NextSteps";
import { useIntelligence } from "@/hooks/useIntelligence";
import { IntelligenceBlock } from "@/components/intelligence/IntelligenceBlock";
import { API_BASE_URL as API } from "@/lib/api";


interface Event {
  id: string; title: string; summary: string;
  impact_score: number; confidence: number;
  sectors: string[]; companies: { symbol: string; name: string; impact: string }[];
  category: string; date: string;
}

const IMPACT_COLOR: Record<string, string> = {
  Positive: "text-emerald-300 bg-emerald-500/10 border-emerald-500/20",
  Negative: "text-rose-300 bg-rose-500/10 border-rose-500/20",
  Neutral:  "text-slate-300 bg-white/5 border-white/10",
};

const CATEGORY_PLAIN: Record<string, string> = {
  Government: "Government",
  Policy:     "Regulations",
  RBI:        "Central Bank",
  Macro:      "Economy",
  Global:     "Global",
};

const CAT_COLORS: Record<string, string> = {
  Government: "border-violet-500/20 bg-violet-500/10 text-violet-300",
  Policy:     "border-sky-500/20 bg-sky-500/10 text-sky-300",
  Macro:      "border-amber-500/20 bg-amber-500/10 text-amber-300",
  Global:     "border-slate-500/20 bg-slate-500/10 text-slate-300",
  RBI:        "border-indigo-500/20 bg-indigo-500/10 text-indigo-300",
};

const FILTER_CHIPS = [
  { label: "All",          value: "" },
  { label: "Government",   value: "Government" },
  { label: "Central Bank", value: "RBI" },
  { label: "Regulations",  value: "Policy" },
  { label: "Economy",      value: "Macro" },
];

function impactLabel(score: number) {
  const n = score <= 10 ? score * 10 : score;
  if (n >= 90) return "Very High Impact";
  if (n >= 75) return "High Impact";
  if (n >= 55) return "Medium Impact";
  return "Low Impact";
}

export default function PoliciesPage() {
  const [allEvents, setAllEvents] = useState<Event[]>([]);
  const [activeFilter, setActiveFilter] = useState("");

  const { data: intelligence } = useIntelligence("theme", "government-policy-rbi");

  useEffect(() => {
    fetch(`${API}/api/events/?limit=50`)
      .then(r => r.ok ? r.json() : [])
      .then(d => {
        if (Array.isArray(d) && d.length) {
          setAllEvents(d.filter((e: Event) => ["Government", "Policy", "RBI", "Macro"].includes(e.category)));
        }
      })
      .catch(() => {});
  }, []);

  const filtered = activeFilter ? allEvents.filter(e => e.category === activeFilter) : allEvents;

  return (
    <main className="min-w-0 space-y-6 pb-10">
      <MarketContextStrip />
      <div>
        <p className="text-sm uppercase tracking-[0.24em] text-sky-300">Intelligence</p>
        <h1 className="mt-2 text-4xl font-semibold tracking-tight text-white">Government Policies</h1>
        <p className="mt-1 text-sm text-slate-400">
          Policy and regulatory decisions often move entire sectors — not individual stocks. Watch these to understand the direction of the market.
        </p>
      </div>

      {/* Intelligence Block */}
      {intelligence && (
        <IntelligenceBlock data={intelligence} label="Policy & Regulatory Intelligence" compact={true} />
      )}

      {/* Filter chips — functional */}
      <div className="flex flex-wrap gap-2">
        {FILTER_CHIPS.map(chip => (
          <button key={chip.value}
            onClick={() => setActiveFilter(chip.value)}
            className={`rounded-full border px-3 py-1 text-xs font-medium transition ${
              activeFilter === chip.value
                ? "border-sky-500/40 bg-sky-500/15 text-sky-300"
                : (chip.value ? (CAT_COLORS[chip.value] ?? "border-white/10 bg-white/5 text-slate-400") : "border-white/10 bg-white/5 text-slate-300")
            } hover:border-white/20`}>
            {chip.label}
          </button>
        ))}
      </div>

      {/* Events list */}
      {filtered.length > 0 ? (
        <div className="space-y-4">
          {filtered.map((e) => (
            <article key={e.id}
              className="rounded-[20px] border border-white/10 bg-white/[0.03] p-5 transition hover:-translate-y-0.5 hover:border-white/20">
              {/* Top row */}
              <div className="flex flex-wrap items-center gap-2">
                <span className={`rounded-full border px-2.5 py-0.5 text-[11px] font-medium ${CAT_COLORS[e.category] ?? "border-white/10 bg-white/5 text-slate-300"}`}>
                  {CATEGORY_PLAIN[e.category] ?? e.category}
                </span>
                <span className="rounded-full border border-white/10 bg-white/5 px-2.5 py-0.5 text-[11px] text-slate-400">
                  {impactLabel(e.impact_score)}
                </span>
                <span className="text-[11px] text-slate-600">
                  {e.date ? new Date(e.date).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" }) : ""}
                </span>
              </div>

              <h3 className="mt-3 text-base font-semibold leading-snug text-white">{e.title}</h3>
              <p className="mt-2 text-sm leading-6 text-slate-400">{e.summary}</p>

              {/* Companies affected */}
              {e.companies?.length > 0 && (
                <div className="mt-4 flex flex-wrap gap-2">
                  <p className="w-full text-[10px] uppercase tracking-widest text-slate-500">Companies Affected</p>
                  {e.companies.map((c) => (
                    <Link key={c.symbol} href={`/companies/${c.symbol}`}
                      className={`rounded-full border px-2.5 py-1 text-[11px] transition hover:brightness-110 ${IMPACT_COLOR[c.impact] ?? IMPACT_COLOR["Neutral"]}`}>
                      {c.name} · {c.impact}
                    </Link>
                  ))}
                </div>
              )}

              {/* Sectors */}
              {e.sectors?.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {e.sectors.map((s) => (
                    <span key={s} className="rounded-full border border-white/8 bg-white/5 px-2 py-0.5 text-[10px] text-slate-500">{s}</span>
                  ))}
                </div>
              )}

              {/* Ask AI */}
              <div className="mt-3 pt-2.5 border-t border-white/[0.05]">
                <Link href={`/ai-search?q=${encodeURIComponent(e.title)}`}
                  className="text-[12px] font-medium text-violet-400 hover:text-violet-300 transition">
                  Ask AI about this →
                </Link>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <div className="flex items-center justify-center rounded-[20px] border border-white/10 bg-white/[0.03] py-20">
          <p className="text-slate-500">{allEvents.length === 0 ? "Start the backend to load policy events." : "No events match this filter."}</p>
        </div>
      )}

      {/* Intelligent guidance — derived from top policy event */}
      {filtered.length > 0 && (() => {
        const top       = [...filtered].sort((a, b) => (b.impact_score ?? 0) - (a.impact_score ?? 0))[0];
        const q         = (s: string) => encodeURIComponent(s);
        const firstCo   = top?.companies?.[0];
        const topSector = top?.sectors?.[0];
        const catLabel  = CATEGORY_PLAIN[top.category] ?? top.category;
        const shortTitle = top.title.length > 85 ? top.title.slice(0, 82) + "…" : top.title;
        return (
          <NextSteps config={{
            takeaway: `${shortTitle} — a ${catLabel} decision with ${top.sectors?.length || 0} sectors exposed.`,
            primary: firstCo ? {
              label: `Research ${firstCo.name}`,
              why:   `Because they face a direct ${firstCo.impact.toLowerCase()} impact — this policy changes their regulatory environment and growth trajectory.`,
              href:  `/companies/${firstCo.symbol}`,
            } : topSector ? {
              label: `Find companies most exposed to this policy`,
              why:   `Because understanding specific exposure in ${topSector} helps you separate the stocks that benefit from those that face headwinds.`,
              href:  `/ai-search?q=${q(`Which companies in ${topSector} are most affected by "${top.title}"?`)}`,
            } : {
              label: `Ask AI: What does this policy mean for investors?`,
              why:   `Because policy changes create structural shifts that persist long after the initial market reaction.`,
              href:  `/ai-search?q=${q(`What does "${top.title}" mean for Indian equity investors?`)}`,
            },
            groups: [
              {
                label: "Understand More",
                actions: [
                  {
                    label: `Ask AI: What does this policy mean for investors?`,
                    why:   `Because policy-driven themes can last years — understanding the structural shift helps you position ahead of the curve.`,
                    href:  `/ai-search?q=${q(`What does "${top.title}" mean for Indian equity investors? Which sectors and companies benefit or are at risk?`)}`,
                  },
                  {
                    label: "Trace the ripple across sectors",
                    why:   "Because policy changes propagate through supply chains, competitors, and adjacent sectors before reaching full market impact.",
                    href:  `/ripple`,
                  },
                ],
              },
              ...(topSector ? [{
                label: "Explore Further",
                actions: [{
                  label: `Long-term outlook for ${topSector}`,
                  why:   `Because sector-level policy impacts compound over 12–24 months — understanding the direction early creates a real edge.`,
                  href:  `/ai-search?q=${q(`What is the long-term impact of "${top.title}" on the ${topSector} sector over the next 12-24 months?`)}`,
                }],
              }] : []),
            ],
            path: [catLabel, topSector ?? "Sectors", firstCo?.name ?? "Companies", "Investment Thesis"].filter(Boolean) as string[],
          }} />
        );
      })()}

      <div className="rounded-[20px] border border-amber-500/20 bg-amber-500/[0.04] p-4">
        <p className="text-xs text-amber-300">
          <ClipboardList className="inline h-3.5 w-3.5 mr-1 align-text-bottom" /> <strong>Live Policy Feed:</strong> Real-time government notifications require{" "}
          <strong>SEBI Circular API</strong>, <strong>RBI Press Release RSS</strong>, and{" "}
          <strong>PIB (Press Information Bureau) API</strong>.
        </p>
      </div>
    </main>
  );
}
