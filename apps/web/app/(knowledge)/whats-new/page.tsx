import type { Metadata } from "next";
import {
  Sparkles,
  Wrench,
  Bug,
  Rocket,
  Clock,
  CheckCircle2,
  CircleDot,
} from "lucide-react";

export const metadata: Metadata = {
  title: "What's New — MarketRipple Release Notes & Changelog",
  description:
    "Explore the latest features, improvements, and fixes shipped in every version of MarketRipple — the AI-powered Indian stock market intelligence platform.",
  openGraph: {
    title: "What's New — MarketRipple Release Notes & Changelog",
    description:
      "Follow MarketRipple's continuous evolution: new AI features, data improvements, and platform updates released every month.",
  },
};

// ── Types ──────────────────────────────────────────────────────────────────────

type ChangeType = "Feature" | "Improvement" | "Fix";

interface ChangeEntry {
  type: ChangeType;
  text: string;
}

interface Release {
  version: string;
  date: string;
  codename: string;
  headline: string;
  changes: ChangeEntry[];
}

// ── Data ───────────────────────────────────────────────────────────────────────

const RELEASES: Release[] = [
  {
    version: "1.4",
    date: "June 2025",
    codename: "Performance & Polish",
    headline:
      "A focused quality release eliminating technical debt and improving platform consistency across all 40+ components.",
    changes: [
      {
        type: "Improvement",
        text: "Eliminated all emoji icons throughout the platform — replaced with professional lucide-react icons for a consistent, accessible experience across all pages and components.",
      },
      {
        type: "Improvement",
        text: "TypeScript strict compliance achieved — zero type errors across all 40+ components, ensuring a more maintainable and reliable codebase.",
      },
      {
        type: "Improvement",
        text: "Fake glassmorphism optimisation — removed GPU compositing cost on all card elements while preserving the visual depth of the design.",
      },
      {
        type: "Fix",
        text: "AI Search suggestion panel layout fixed on mobile — panel now correctly anchors within the viewport on small screens.",
      },
      {
        type: "Fix",
        text: "Ripple Engine force-directed graph rendering on Safari improved — resolved WebKit-specific SVG transform issues causing node misalignment.",
      },
    ],
  },
  {
    version: "1.3",
    date: "May 2025",
    codename: "Opportunity Radar",
    headline:
      "Introduced the Opportunity Radar — MarketRipple's AI-scored investment discovery engine — along with deep-dive detail pages and theme-based browsing.",
    changes: [
      {
        type: "Feature",
        text: "Opportunity Radar — AI-scored investment opportunities ranked 0–100 with sector and theme filters for targeted discovery.",
      },
      {
        type: "Feature",
        text: "Radar Detail pages — deep-dive analysis for each opportunity with financial metrics, company beneficiary list, event timeline, and full AI insights.",
      },
      {
        type: "Feature",
        text: "Theme-based opportunity discovery — browse opportunities by AI Infrastructure, Defence, Renewable Energy, Railways, Electric Vehicles, and Semiconductors.",
      },
      {
        type: "Improvement",
        text: "Dashboard redesigned with a quick-access Opportunity Radar widget on the home view, surfacing top-scored opportunities without navigating away.",
      },
      {
        type: "Improvement",
        text: "Stories page enhanced with theme categorisation — filter stories by investment theme for faster navigation.",
      },
    ],
  },
  {
    version: "1.2",
    date: "April 2025",
    codename: "Ripple Intelligence",
    headline:
      "Launched the Ripple Engine — MarketRipple's proprietary cascade analysis system — with an interactive Market Dependency Graph and 4-level ripple tracing.",
    changes: [
      {
        type: "Feature",
        text: "Ripple Engine — proprietary market cascade analysis system that traces how a single event propagates through the economy across four levels of impact depth.",
      },
      {
        type: "Feature",
        text: "Interactive force-directed graph visualisation — the Market Dependency Graph renders event–sector–company relationships as a fully interactive node-edge diagram.",
      },
      {
        type: "Feature",
        text: "4-level ripple effect tracing — Direct (immediate sector impact), Intermediate (second-order effects), Indirect (distant correlations), and Long-term (structural shifts).",
      },
      {
        type: "Feature",
        text: "Scenario Analysis — 'What if crude hits $100?' — AI-generated scenario graphs showing predicted cascade effects across sectors and companies under specified conditions.",
      },
      {
        type: "Feature",
        text: "Event-specific Ripple pages showing the full dependency chain for each high-impact market event.",
      },
      {
        type: "Improvement",
        text: "Event detail pages enhanced with a Ripple preview panel — view the first two cascade levels without navigating to the full Ripple page.",
      },
    ],
  },
  {
    version: "1.1",
    date: "March 2025",
    codename: "AI Search & Stories",
    headline:
      "Introduced natural language AI Search, AI-curated Stories, breaking news alerts, and the daily AI Market Wrap.",
    changes: [
      {
        type: "Feature",
        text: "AI Search — natural language query interface for market intelligence: ask questions in plain English and receive sourced, structured answers from MarketRipple's knowledge graph.",
      },
      {
        type: "Feature",
        text: "Stories — AI-curated multi-event investment narratives connecting related market events into thematic, long-horizon investment cases.",
      },
      {
        type: "Feature",
        text: "Breaking News Alert system — continuous monitoring with real-time notifications when events exceed impact score 8, with full event context linked from the alert.",
      },
      {
        type: "Feature",
        text: "AI Market Wrap — daily AI-synthesised market summary covering the day's most impactful events, sector movers, and key intelligence highlights.",
      },
      {
        type: "Improvement",
        text: "Market Intelligence Command Centre upgraded to 6-tab navigation: Overview, Events, Opportunities, Stories, Calendar, and Signals.",
      },
      {
        type: "Improvement",
        text: "Pre-market section expanded with Gift Nifty live, US Equity Futures, Asian market performance, and USD/INR live feed.",
      },
    ],
  },
  {
    version: "1.0",
    date: "February 2025",
    codename: "Core Platform",
    headline:
      "The initial public release of MarketRipple — the AI-powered market intelligence platform built for Indian equity markets.",
    changes: [
      {
        type: "Feature",
        text: "Market Intelligence dashboard — real-time overview with session tracking, Nifty/Sensex live levels, breadth indicators, and top movers.",
      },
      {
        type: "Feature",
        text: "Events Engine — AI-classified market events with impact scoring (0–10), confidence ratings, sector tagging, and company attribution.",
      },
      {
        type: "Feature",
        text: "Company Intelligence pages — per-company event exposure analysis, AI impact summary, sector context, and linked opportunity discoveries.",
      },
      {
        type: "Feature",
        text: "Sector Heatmap — real-time sector performance visualisation across all NSE sector indices with colour-coded strength/weakness mapping.",
      },
      {
        type: "Feature",
        text: "Economic Calendar — macro data releases, RBI policy meeting schedule, government budget dates, and corporate results calendar.",
      },
      {
        type: "Feature",
        text: "India VIX live monitoring — fear gauge dashboard with trend analysis and historical context.",
      },
      {
        type: "Feature",
        text: "Commodities & Energy markets page — crude oil (Brent/WTI), gold, silver, natural gas, and related Indian company impact analysis.",
      },
    ],
  },
];

const COMING_SOON = [
  {
    title: "FII / DII Net Flow Cards",
    desc: "Daily foreign and domestic institutional investor flow data with trend analysis and market impact correlation.",
  },
  {
    title: "Portfolio Tracker Integration",
    desc: "Connect your holdings to see personalised event impact assessments and opportunity scores specific to your portfolio.",
  },
  {
    title: "Custom Alert Builder",
    desc: "Define precise alert conditions — sector, impact score threshold, company, confidence level — for tailored notifications.",
  },
  {
    title: "Premium AI Reports (PDF Export)",
    desc: "Downloadable research reports with extended AI analysis, multi-scenario projections, and sector comparison tables.",
  },
  {
    title: "API Access for Professionals",
    desc: "Programmatic access to MarketRipple's event classification, company exposure data, and opportunity scores for institutional users.",
  },
  {
    title: "Mobile App (iOS & Android)",
    desc: "Native mobile experience with push notifications for breaking alerts, offline access, and biometric authentication.",
  },
];

// ── Badge ──────────────────────────────────────────────────────────────────────

const BADGE_STYLES: Record<ChangeType, string> = {
  Feature:
    "bg-violet-500/15 text-violet-300 border border-violet-500/30",
  Improvement:
    "bg-sky-500/15 text-sky-300 border border-sky-500/30",
  Fix: "bg-amber-500/15 text-amber-300 border border-amber-500/30",
};

const BADGE_ICONS: Record<ChangeType, typeof Sparkles> = {
  Feature: Sparkles,
  Improvement: Wrench,
  Fix: Bug,
};

function ChangeBadge({ type }: { type: ChangeType }) {
  const Icon = BADGE_ICONS[type];
  return (
    <span
      className={`inline-flex shrink-0 items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold ${BADGE_STYLES[type]}`}
    >
      <Icon className="h-2.5 w-2.5" />
      {type}
    </span>
  );
}

// ── Page ───────────────────────────────────────────────────────────────────────

export default function WhatsNewPage() {
  return (
    <main className="min-w-0 pb-10">
      {/* Hero */}
      <div className="mb-10">
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">
          Release Notes
        </p>
        <h1 className="mt-3 text-[28px] font-black leading-tight text-white md:text-[36px]">
          What&apos;s New in MarketRipple
        </h1>
        <p className="mt-3 max-w-2xl text-[15px] leading-7 text-slate-400">
          MarketRipple ships continuous improvements — new AI capabilities, richer
          data, and refined experiences delivered regularly. Here is a full
          record of every release.
        </p>

        {/* Stats row */}
        <div className="mt-6 flex flex-wrap gap-3">
          {[
            { label: "Versions Shipped", value: "5" },
            { label: "Features Launched", value: "24+" },
            { label: "Fixes & Improvements", value: "16+" },
            { label: "Latest Version", value: "1.4" },
          ].map((s) => (
            <div
              key={s.label}
              className="rounded-xl border border-white/[0.08] bg-[#080c14] px-4 py-3 text-center"
            >
              <p className="text-[22px] font-black text-white">{s.value}</p>
              <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-slate-500">
                {s.label}
              </p>
            </div>
          ))}
        </div>
      </div>

      {/* Timeline */}
      <div className="relative space-y-0">
        {/* Vertical line */}
        <div className="absolute left-[19px] top-6 bottom-6 hidden w-px bg-white/[0.06] md:block" />

        {RELEASES.map((release, idx) => (
          <div key={release.version} className="relative mb-10 md:pl-12">
            {/* Timeline dot */}
            <div
              className={`absolute left-0 top-5 hidden h-10 w-10 items-center justify-center rounded-full border md:flex ${
                idx === 0
                  ? "border-violet-500/50 bg-violet-500/20"
                  : "border-white/[0.10] bg-[#080c14]"
              }`}
            >
              {idx === 0 ? (
                <CircleDot className="h-4 w-4 text-violet-400" />
              ) : (
                <CheckCircle2 className="h-4 w-4 text-slate-500" />
              )}
            </div>

            {/* Card */}
            <article className="rounded-xl border border-white/[0.08] bg-[#080c14] p-5">
              {/* Header */}
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <span
                      className={`rounded-full px-3 py-1 text-[11px] font-black tracking-wide ${
                        idx === 0
                          ? "bg-violet-500/20 text-violet-300 border border-violet-500/30"
                          : "bg-white/[0.06] text-slate-300 border border-white/[0.08]"
                      }`}
                    >
                      v{release.version}
                    </span>
                    <span className="rounded-full border border-white/[0.06] bg-white/[0.03] px-2.5 py-0.5 text-[11px] text-slate-400">
                      {release.codename}
                    </span>
                    {idx === 0 && (
                      <span className="rounded-full bg-emerald-500/15 px-2.5 py-0.5 text-[10px] font-semibold text-emerald-400 border border-emerald-500/25">
                        Latest
                      </span>
                    )}
                  </div>
                  <h2 className="mt-2 text-[18px] font-bold text-white">
                    Version {release.version} — {release.codename}
                  </h2>
                </div>
                <div className="flex items-center gap-1.5 text-slate-500">
                  <Clock className="h-3.5 w-3.5" />
                  <span className="text-[12px]">{release.date}</span>
                </div>
              </div>

              {/* Headline */}
              <p className="mt-3 text-[13px] leading-6 text-slate-400">
                {release.headline}
              </p>

              {/* Changes */}
              <div className="mt-4 space-y-2.5">
                {release.changes.map((change, ci) => (
                  <div key={ci} className="flex items-start gap-3">
                    <ChangeBadge type={change.type} />
                    <p className="text-[13px] leading-5 text-slate-300">
                      {change.text}
                    </p>
                  </div>
                ))}
              </div>

              {/* Change count badges */}
              <div className="mt-4 flex flex-wrap gap-2 border-t border-white/[0.06] pt-4">
                {(["Feature", "Improvement", "Fix"] as ChangeType[]).map((type) => {
                  const count = release.changes.filter(
                    (c) => c.type === type
                  ).length;
                  if (!count) return null;
                  return (
                    <span
                      key={type}
                      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[11px] font-medium ${BADGE_STYLES[type]}`}
                    >
                      {count} {type}{count > 1 ? "s" : ""}
                    </span>
                  );
                })}
              </div>
            </article>
          </div>
        ))}
      </div>

      {/* Coming Soon */}
      <section className="mt-4">
        <div className="mb-5 flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-amber-500/15">
            <Rocket className="h-4 w-4 text-amber-400" />
          </div>
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">
              Roadmap
            </p>
            <h2 className="text-[18px] font-bold text-white">Coming Soon</h2>
          </div>
        </div>

        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {COMING_SOON.map((item) => (
            <div
              key={item.title}
              className="rounded-xl border border-dashed border-white/[0.10] bg-white/[0.02] p-4"
            >
              <div className="mb-1.5 flex items-center gap-2">
                <div className="h-1.5 w-1.5 rounded-full bg-amber-400/60" />
                <p className="text-[13px] font-semibold text-slate-200">
                  {item.title}
                </p>
              </div>
              <p className="text-[12px] leading-5 text-slate-500">{item.desc}</p>
            </div>
          ))}
        </div>

        <p className="mt-5 text-[12px] text-slate-500">
          Have a feature request?{" "}
          <a
            href="/contact"
            className="text-sky-400 underline-offset-2 hover:underline"
          >
            Share your idea
          </a>{" "}
          — every suggestion is reviewed by the team.
        </p>
      </section>
    </main>
  );
}
