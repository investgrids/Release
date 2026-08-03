"use client";

import { useState } from "react";
import Link from "next/link";
import { NextSteps } from "@/components/NextSteps";
import { compareScoresDesc } from "@/lib/scoring";

interface PolicyEvent {
  id: string; title: string; summary: string;
  impact_score: number | null; confidence: number | null;
  sectors: string[]; companies: { symbol: string; name: string; impact: string }[];
  category: string; date: string;
}

const IMPACT_COLOR: Record<string, string> = {
  Positive: "text-emerald-600 dark:text-emerald-300 bg-emerald-500/10 border-emerald-500/20",
  Negative: "text-rose-600 dark:text-rose-300 bg-rose-500/10 border-rose-500/20",
  Neutral:  "text-text-secondary bg-text-primary/5 border-surface-border/10",
};

const CATEGORY_PLAIN: Record<string, string> = {
  Government: "Government",
  Policy:     "Regulations",
  RBI:        "Central Bank",
  Macro:      "Economy",
  Global:     "Global",
};

const CAT_COLORS: Record<string, string> = {
  Government: "border-violet-500/20 bg-violet-500/10 text-violet-600 dark:text-violet-300",
  Policy:     "border-sky-500/20 bg-sky-500/10 text-sky-600 dark:text-sky-300",
  Macro:      "border-amber-500/20 bg-amber-500/10 text-amber-600 dark:text-amber-300",
  Global:     "border-surface-border/5 bg-slate-500/10 text-text-secondary",
  RBI:        "border-indigo-500/20 bg-indigo-500/10 text-indigo-600 dark:text-indigo-300",
};

const FILTER_CHIPS = [
  { label: "All",          value: "" },
  { label: "Government",   value: "Government" },
  { label: "Central Bank", value: "RBI" },
  { label: "Regulations",  value: "Policy" },
  { label: "Economy",      value: "Macro" },
];

// /api/events/ already normalizes every event to a 0-100 scale server-side
// (app/services/event_scale.py) — no client-side re-guessing needed.
function impactLabel(score: number | null | undefined) {
  if (score === null || score === undefined) return "Unscored";
  if (score >= 90) return "Very High Impact";
  if (score >= 75) return "High Impact";
  if (score >= 55) return "Medium Impact";
  return "Low Impact";
}

export function RecentPolicyEvents({ events: allEvents }: { events: PolicyEvent[] }) {
  const [activeFilter, setActiveFilter] = useState("");
  const filtered = activeFilter ? allEvents.filter(e => e.category === activeFilter) : allEvents;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap gap-2">
        {FILTER_CHIPS.map(chip => (
          <button key={chip.value}
            onClick={() => setActiveFilter(chip.value)}
            className={`rounded-full border px-3 py-1 text-xs font-medium transition ${
              activeFilter === chip.value
                ? "border-sky-500/40 bg-sky-500/15 text-sky-600 dark:text-sky-300"
                : (chip.value ? (CAT_COLORS[chip.value] ?? "border-surface-border/10 bg-text-primary/5 text-text-secondary") : "border-surface-border/10 bg-text-primary/5 text-text-secondary")
            } hover:border-surface-border/20`}>
            {chip.label}
          </button>
        ))}
      </div>

      {filtered.length > 0 ? (
        <div className="space-y-4">
          {filtered.map((e) => (
            <article key={e.id}
              className="rounded-[20px] border border-surface-border/10 bg-text-primary/[0.03] p-5 transition hover:-translate-y-0.5 hover:border-surface-border/20">
              <div className="flex flex-wrap items-center gap-2">
                <span className={`rounded-full border px-2.5 py-0.5 text-[11px] font-medium ${CAT_COLORS[e.category] ?? "border-surface-border/10 bg-text-primary/5 text-text-secondary"}`}>
                  {CATEGORY_PLAIN[e.category] ?? e.category}
                </span>
                <span className="rounded-full border border-surface-border/10 bg-text-primary/5 px-2.5 py-0.5 text-[11px] text-text-secondary">
                  {impactLabel(e.impact_score)}
                </span>
                <span className="text-[11px] text-text-muted">
                  {e.date ? new Date(e.date).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" }) : ""}
                </span>
              </div>

              <h3 className="mt-3 text-base font-semibold leading-snug text-text-primary">{e.title}</h3>
              <p className="mt-2 text-sm leading-6 text-text-secondary">{e.summary}</p>

              {e.companies?.length > 0 && (
                <div className="mt-4 flex flex-wrap gap-2">
                  <p className="w-full text-[10px] uppercase tracking-widest text-text-muted">Companies Affected</p>
                  {e.companies.map((c) => (
                    <Link key={c.symbol} href={`/companies/${c.symbol}`}
                      className={`rounded-full border px-2.5 py-1 text-[11px] transition hover:brightness-110 ${IMPACT_COLOR[c.impact] ?? IMPACT_COLOR["Neutral"]}`}>
                      {c.name} · {c.impact}
                    </Link>
                  ))}
                </div>
              )}

              {e.sectors?.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {e.sectors.map((s) => (
                    <span key={s} className="rounded-full border border-surface-border/8 bg-text-primary/5 px-2 py-0.5 text-[10px] text-text-muted">{s}</span>
                  ))}
                </div>
              )}

              <div className="mt-3 pt-2.5 border-t border-surface-border/5">
                <Link href={`/ai-search?q=${encodeURIComponent(e.title)}`}
                  className="text-[12px] font-medium text-violet-400 hover:text-violet-600 dark:text-violet-300 transition">
                  Ask AI about this →
                </Link>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <div className="flex items-center justify-center rounded-[20px] border border-surface-border/10 bg-text-primary/[0.03] py-16">
          <p className="text-text-muted">{allEvents.length === 0 ? "No recent policy events." : "No events match this filter."}</p>
        </div>
      )}

      {filtered.length > 0 && (() => {
        const top       = [...filtered].sort((a, b) => compareScoresDesc(a.impact_score, b.impact_score))[0];
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
    </div>
  );
}
