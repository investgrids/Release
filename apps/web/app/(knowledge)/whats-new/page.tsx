import type { Metadata } from "next";
import Link from "next/link";
import {
  Rocket,
  ArrowRight,
  HelpCircle,
  Wallet,
  Newspaper,
  ShieldCheck,
  TrendingUp,
  GitBranch,
  Radar,
  Search,
  Building2,
  Brain,
  Radio,
} from "lucide-react";
import { safeJsonLd } from "@/lib/text";
import { ReleaseAccordion, FaqAccordion, FeatureLinkTracker, RoadmapLinkTracker } from "./WhatsNewInteractive";

const SITE_URL = "https://www.marketripple.in";

export const metadata: Metadata = {
  title: "MarketRipple Features & Product Updates | AI Market Intelligence",
  description:
    "Explore MarketRipple's latest features, AI intelligence capabilities, product updates, release history, and roadmap for Indian investors.",
  alternates: { canonical: `${SITE_URL}/whats-new` },
  openGraph: {
    title: "MarketRipple Features & Product Updates | AI Market Intelligence",
    description:
      "Explore MarketRipple's latest features, AI intelligence capabilities, product updates, release history, and roadmap for Indian investors.",
    url: `${SITE_URL}/whats-new`,
    images: [{ url: "/opengraph-image", width: 1200, height: 630, alt: "MarketRipple — AI-Powered Market Intelligence" }],
  },
};

// ── Types ──────────────────────────────────────────────────────────────────

type ChangeType = "Feature" | "Improvement" | "Fix";
interface RawChange { type: ChangeType; text: string }
interface RawRelease { version: string; date: string; codename: string; headline: string; changes: RawChange[] }

// ── Data — the factual source of truth for this page. Every release below ──
// is preserved verbatim from the previous version of this page; nothing was
// added, removed, or reworded. Only the presentation changed.
const RELEASES: RawRelease[] = [
  {
    version: "1.5",
    date: "August 2026",
    codename: "Portfolio Intelligence & Newsroom",
    headline:
      "A major upgrade to how MarketRipple explains impact — a relaunched portfolio briefing tool, fact-grounded AI articles, and a redesigned AI Newsroom reading experience.",
    changes: [
      {
        type: "Feature",
        text: "Portfolio Intelligence Brief — relaunched from Portfolio Confidence into a fuller portfolio view. Paste your holdings (no login, no broker connection, nothing stored) and get a daily brief covering the real events and news touching each position, market-impact price signals, and themes shared across your holdings — plus an honest read on where MarketRipple's own coverage is thin for any given holding.",
      },
      {
        type: "Feature",
        text: "Redesigned AI Newsroom article experience — a new AI Investment Verdict surfaces the takeaway up front, the Evidence section is now clearly split into Fact vs AI Interpretation, and related companies, sectors, and events are linked more usefully throughout each article.",
      },
      {
        type: "Improvement",
        text: "Fact-grounding validators added to the AI article pipeline (shadow mode) — real per-company price-move data now grounds AI-generated company impact analysis, with automated checks catching inconsistencies before publish.",
      },
    ],
  },
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

// ── Internal linking: known feature names/phrases → the real product page ──
// they correspond to. Deliberately conservative — pattern match, and if
// nothing matches, no link is added rather than guessing.
const FEATURE_LINKS: Array<[RegExp, string]> = [
  [/Portfolio (Intelligence|Confidence)/i, "/tools/portfolio-confidence"],
  [/AI Newsroom|AI Investment Verdict/i, "/newsroom"],
  [/Fact-grounding/i, "/ai-methodology"],
  [/Opportunity Radar|Radar Detail/i, "/opportunity-radar"],
  [/Ripple Engine|Market Dependency Graph|Ripple (preview|pages)/i, "/ripple"],
  [/^Stories|Stories page/i, "/newsroom/themes"],
  [/Breaking News Alert/i, "/events"],
  [/AI Market Wrap/i, "/newsroom"],
  [/AI Search/i, "/ai-search"],
  [/Market Intelligence (dashboard|Command Centre)/i, "/market-intelligence"],
  [/Events Engine/i, "/events"],
  [/Company Intelligence/i, "/companies"],
  [/Sector Heatmap/i, "/sectors"],
  [/Economic Calendar/i, "/calendar"],
  [/Commodities/i, "/commodities"],
];

function linkFor(name: string | null): string | null {
  if (!name) return null;
  for (const [re, href] of FEATURE_LINKS) if (re.test(name)) return href;
  return null;
}

// Most change entries follow a "Name — description" pattern; split on the
// first em dash where present. Entries without one (a handful of single-
// sentence items) render as description-only, exactly as authored — no
// title is invented for them.
function splitChange(raw: RawChange) {
  const idx = raw.text.indexOf(" — ");
  if (idx === -1) return { type: raw.type, name: null, description: raw.text, href: null };
  const name = raw.text.slice(0, idx);
  const description = raw.text.slice(idx + 3);
  return { type: raw.type, name, description, href: linkFor(name) };
}

const RELEASES_FOR_UI = RELEASES.map((r) => ({ ...r, changes: r.changes.map(splitChange) }));

// ── Dynamic stats — computed from RELEASES itself so this never drifts out
// of sync with the actual release records (the previous hardcoded "26+
// Features" / "17+ Fixes & Improvements" undercounted vs. the real data on
// review, so those are now derived, not typed in).
const FEATURE_COUNT = RELEASES.reduce((sum, r) => sum + r.changes.filter((c) => c.type === "Feature").length, 0);
const OTHER_COUNT = RELEASES.reduce((sum, r) => sum + r.changes.filter((c) => c.type !== "Feature").length, 0);
const VERSION_COUNT = RELEASES.length;
const LATEST = RELEASES[0];
const LATEST_BULLETS = LATEST.changes.map(splitChange).map((c) => c.name ?? c.description);

// ── What's New (3 cards) — only claims already stated in the v1.5 record ───
const WHATS_NEW_CARDS = [
  {
    icon: Wallet,
    title: "Portfolio Intelligence",
    what: "Relaunched from Portfolio Confidence into a fuller daily briefing tool.",
    why: "See how real market events, price signals, and themes affect the companies in your portfolio — without login or broker integration.",
    href: "/tools/portfolio-confidence",
  },
  {
    icon: Newspaper,
    title: "AI Newsroom",
    what: "Redesigned article experience with an AI Investment Verdict up front.",
    why: "Read AI-generated market intelligence with a clear takeaway, evidence split into Fact vs AI Interpretation, and linked company/sector/event context.",
    href: "/newsroom",
  },
  {
    icon: ShieldCheck,
    title: "Fact-Grounded AI",
    what: "Fact-grounding validators added to the AI article pipeline (shadow mode).",
    why: "MarketRipple validates AI-generated company-impact analysis against real market and event data before publication.",
    href: "/ai-methodology",
  },
];

// ── Explore MarketRipple hub — only real, live routes ───────────────────────
const EXPLORE_LINKS = [
  { icon: TrendingUp, title: "Market Intelligence", desc: "Live market overview, sectors, and top movers.", href: "/market-intelligence" },
  { icon: Radio, title: "Events", desc: "AI-classified market events with impact scoring.", href: "/events" },
  { icon: Building2, title: "Companies", desc: "Per-company event exposure and AI impact analysis.", href: "/companies" },
  { icon: GitBranch, title: "Ripple Intelligence", desc: "Trace how one event cascades through the economy.", href: "/ripple" },
  { icon: Radar, title: "Opportunity Radar", desc: "AI-scored investment opportunities by sector and theme.", href: "/opportunity-radar" },
  { icon: Search, title: "AI Search", desc: "Ask market questions in plain English.", href: "/ai-search" },
  { icon: Newspaper, title: "AI Newsroom", desc: "AI-generated market intelligence articles.", href: "/newsroom" },
  { icon: Brain, title: "AI Methodology", desc: "How MarketRipple's AI actually works.", href: "/ai-methodology" },
];

// ── FAQ (7 questions, all answerable from the data on this page) ───────────
const FAQS = [
  {
    id: "latest-version",
    q: "What is the latest MarketRipple version?",
    a: `MarketRipple's latest release is v${LATEST.version} — "${LATEST.codename}" — shipped ${LATEST.date}. ${LATEST.headline}`,
  },
  {
    id: "newest-features",
    q: "What are the newest features in MarketRipple?",
    a: `The v${LATEST.version} release added the Portfolio Intelligence Brief, a redesigned AI Newsroom article experience with an AI Investment Verdict, and fact-grounding validators that check AI-generated company-impact analysis against real price data before publication.`,
  },
  {
    id: "ai-newsroom",
    q: "What is MarketRipple AI Newsroom?",
    a: "AI Newsroom is where MarketRipple publishes AI-generated market intelligence articles. Each article leads with an AI Investment Verdict, splits its Evidence section into Fact vs AI Interpretation, and links to the related companies, sectors, and events behind the analysis.",
  },
  {
    id: "opportunity-radar",
    q: "What is MarketRipple Opportunity Radar?",
    a: "Opportunity Radar is MarketRipple's AI-scored investment discovery engine, introduced in v1.3. It ranks opportunities 0–100 with sector and theme filters, and each opportunity has a deep-dive detail page with financial metrics, a company beneficiary list, and an event timeline.",
  },
  {
    id: "ai-analysis",
    q: "Does MarketRipple use AI for market analysis?",
    a: "Yes. AI Search, the Ripple Engine, Opportunity Radar, and AI Newsroom are all AI-driven — from natural-language search introduced in v1.1 to the fact-grounding validators added in v1.5. See the AI Methodology page for how each system actually works.",
  },
  {
    id: "evolution",
    q: "How has MarketRipple evolved?",
    a: `Across ${VERSION_COUNT} versions since February 2025, MarketRipple grew from a core market intelligence dashboard (v1.0) into a full AI intelligence platform — adding AI Search and Stories (v1.1), the Ripple Engine (v1.2), Opportunity Radar (v1.3), a performance and quality pass (v1.4), and Portfolio Intelligence with a redesigned AI Newsroom (v1.5).`,
  },
  {
    id: "coming-next",
    q: "What features are coming to MarketRipple?",
    a: "Planned items include FII/DII net flow cards, a custom alert builder, premium AI reports with PDF export, API access for professionals, and native mobile apps. These are roadmap items, not guaranteed release dates — see What's Coming Next below.",
  },
];

const FAQ_JSONLD = {
  "@context": "https://schema.org",
  "@type": "FAQPage",
  mainEntity: FAQS.map((item) => ({ "@type": "Question", name: item.q, acceptedAnswer: { "@type": "Answer", text: item.a } })),
};

const WEBPAGE_JSONLD = {
  "@context": "https://schema.org",
  "@type": "WebPage",
  name: "MarketRipple Features & Product Updates",
  url: `${SITE_URL}/whats-new`,
  description:
    "MarketRipple's latest features, AI intelligence capabilities, product updates, release history, and roadmap for Indian investors.",
  about: { "@type": "Organization", name: "MarketRipple", url: SITE_URL },
};

const RELEASES_JSONLD = {
  "@context": "https://schema.org",
  "@type": "ItemList",
  name: "MarketRipple Release History",
  description: "Every MarketRipple release, newest first, with the features, improvements, and fixes shipped in each version.",
  itemListOrder: "https://schema.org/ItemListOrderDescending",
  itemListElement: RELEASES.map((release, idx) => ({
    "@type": "ListItem",
    position: idx + 1,
    name: `Version ${release.version} — ${release.codename}`,
    description: release.headline,
  })),
};

// ── Page ───────────────────────────────────────────────────────────────────

export default function WhatsNewPage() {
  return (
    <main className="min-w-0 pb-14" aria-label="MarketRipple Product Updates">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: safeJsonLd(WEBPAGE_JSONLD) }} />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: safeJsonLd(RELEASES_JSONLD) }} />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: safeJsonLd(FAQ_JSONLD) }} />

      {/* ── HERO + LATEST RELEASE ──────────────────────────────────────── */}
      <section aria-labelledby="hero-heading" className="mb-10">
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-text-muted">Product Updates</p>
        <h1 id="hero-heading" className="mt-3 text-[26px] font-black leading-tight text-text-primary md:text-[34px]">
          MarketRipple Product Updates &amp; Feature History
        </h1>
        <p className="mt-3 max-w-2xl text-[14px] leading-6 text-text-secondary md:text-[15px]">
          Explore the latest MarketRipple features, AI intelligence capabilities, and product
          improvements — from the core market intelligence engine to Ripple Intelligence,
          Opportunity Radar, AI Search, Portfolio Intelligence, and the AI Newsroom.
        </p>

        {/* Dynamic stats */}
        <div className="mt-5 flex flex-wrap gap-3">
          {[
            { label: "Versions Shipped", value: String(VERSION_COUNT) },
            { label: "Features Launched", value: String(FEATURE_COUNT) },
            { label: "Improvements & Fixes", value: String(OTHER_COUNT) },
            { label: "Latest Version", value: LATEST.version },
          ].map((s) => (
            <div key={s.label} className="rounded-xl border border-surface-border/8 bg-surface-card px-4 py-2.5 text-center">
              <p className="text-[18px] font-black text-text-primary">{s.value}</p>
              <p className="text-[10px] font-bold uppercase tracking-[0.12em] text-text-muted">{s.label}</p>
            </div>
          ))}
        </div>

        {/* Latest release card */}
        <div className="mt-6 rounded-2xl border border-violet-200 bg-violet-50/60 p-5 dark:border-violet-500/25 dark:bg-violet-500/[0.06] md:p-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <span className="rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-[0.12em] text-emerald-700 dark:border-emerald-500/25 dark:bg-emerald-500/15 dark:text-emerald-400">
                Latest Release
              </span>
              <span className="text-[12px] text-text-muted">{LATEST.date}</span>
            </div>
          </div>
          <h2 className="mt-3 text-[20px] font-black text-text-primary">
            v{LATEST.version} — {LATEST.codename}
          </h2>
          <p className="mt-2 max-w-2xl text-[13px] leading-6 text-text-secondary">{LATEST.headline}</p>
          <ul className="mt-4 grid gap-1.5 sm:grid-cols-2">
            {LATEST_BULLETS.map((b) => (
              <li key={b} className="flex items-start gap-2 text-[12.5px] leading-5 text-text-secondary">
                <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-violet-500" aria-hidden="true" />
                {b}
              </li>
            ))}
          </ul>
          <div className="mt-5 flex flex-wrap gap-3">
            <Link
              href="#whats-new-heading"
              className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-violet-600 to-sky-500 px-4 py-2 text-[13px] font-semibold text-white transition hover:opacity-90"
            >
              Explore Latest Features
              <ArrowRight className="h-3.5 w-3.5" />
            </Link>
            <Link
              href="#release-history-heading"
              className="flex items-center gap-2 rounded-xl border border-surface-border/15 bg-text-primary/[0.03] px-4 py-2 text-[13px] font-semibold text-text-secondary transition hover:border-surface-border/25 hover:text-text-primary"
            >
              View Full Release History
            </Link>
          </div>
        </div>
      </section>

      {/* ── WHAT'S NEW ─────────────────────────────────────────────────── */}
      <section aria-labelledby="whats-new-heading" id="whats-new-heading" className="mb-10 scroll-mt-20">
        <h2 className="text-[20px] font-black text-text-primary md:text-[24px]">What&apos;s New in MarketRipple?</h2>
        <p className="mt-2 max-w-2xl text-[13.5px] leading-6 text-text-secondary">
          The three biggest changes in the latest MarketRipple update.
        </p>
        <div className="mt-5 grid gap-4 sm:grid-cols-3">
          {WHATS_NEW_CARDS.map((card) => (
            <div key={card.title} className="flex flex-col rounded-xl border border-surface-border/8 bg-surface-card p-5">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-violet-200 bg-violet-50 text-violet-600 dark:border-violet-500/20 dark:bg-violet-500/10 dark:text-violet-400">
                <card.icon className="h-4.5 w-4.5" aria-hidden="true" />
              </div>
              <h3 className="mt-3 text-[14px] font-bold text-text-primary">{card.title}</h3>
              <p className="mt-1.5 text-[12px] font-medium text-text-muted">{card.what}</p>
              <p className="mt-2 flex-1 text-[12.5px] leading-5 text-text-secondary">{card.why}</p>
              <FeatureLinkTracker
                feature={card.title}
                href={card.href}
                className="mt-3 inline-flex items-center gap-1 text-[12.5px] font-semibold text-violet-600 hover:text-violet-700 dark:text-violet-400 dark:hover:text-violet-300"
              >
                Explore <ArrowRight className="h-3 w-3" />
              </FeatureLinkTracker>
            </div>
          ))}
        </div>
      </section>

      {/* ── PRODUCT EVOLUTION ─────────────────────────────────────────── */}
      <section aria-labelledby="evolution-heading" className="mb-10">
        <h2 id="evolution-heading" className="text-[20px] font-black text-text-primary md:text-[24px]">
          Product Evolution
        </h2>
        <p className="mt-2 max-w-2xl text-[13.5px] leading-6 text-text-secondary">
          How MarketRipple has grown, version by version, since launch.
        </p>
        <div className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
          {[...RELEASES].reverse().map((r, i) => {
            const featureCount = r.changes.filter((c) => c.type === "Feature").length;
            const otherCount = r.changes.length - featureCount;
            return (
              <div key={r.version} className="rounded-xl border border-surface-border/8 bg-surface-card p-4">
                <div className="flex items-center gap-1.5">
                  <span className="text-[13px] font-black text-violet-600 dark:text-violet-400">v{r.version}</span>
                  {i === RELEASES.length - 1 && (
                    <span className="rounded-full border border-emerald-200 bg-emerald-50 px-1.5 py-0.5 text-[9px] font-bold text-emerald-700 dark:border-emerald-500/25 dark:bg-emerald-500/15 dark:text-emerald-400">
                      Latest
                    </span>
                  )}
                </div>
                <p className="mt-1 text-[12.5px] font-bold leading-snug text-text-primary">{r.codename}</p>
                <p className="text-[10.5px] text-text-muted">{r.date}</p>
                <p className="mt-2 text-[11px] leading-4 text-text-secondary line-clamp-3">{r.headline}</p>
                <p className="mt-2 text-[10px] font-medium text-text-muted">
                  {featureCount ? `${featureCount} feature${featureCount > 1 ? "s" : ""}` : ""}
                  {featureCount && otherCount ? " · " : ""}
                  {otherCount ? `${otherCount} more` : ""}
                </p>
              </div>
            );
          })}
        </div>
      </section>

      {/* ── RELEASE HISTORY (accordion) ───────────────────────────────── */}
      <section aria-labelledby="release-history-heading" id="release-history-heading" className="mb-10 scroll-mt-20">
        <h2 className="text-[20px] font-black text-text-primary md:text-[24px]">Release History</h2>
        <p className="mt-2 max-w-2xl text-[13.5px] leading-6 text-text-secondary">
          Every MarketRipple release, in full — features, improvements, and fixes. Select a
          version to expand it.
        </p>
        <div className="mt-5">
          <ReleaseAccordion releases={RELEASES_FOR_UI} defaultOpenVersion={LATEST.version} />
        </div>
      </section>

      {/* ── ROADMAP ────────────────────────────────────────────────────── */}
      <section aria-labelledby="roadmap-heading" className="mb-10">
        <div className="mb-5 flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-amber-200 bg-amber-50 dark:border-amber-500/20 dark:bg-amber-500/10">
            <Rocket className="h-4 w-4 text-amber-600 dark:text-amber-400" />
          </div>
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-text-muted">Roadmap</p>
            <h2 id="roadmap-heading" className="text-[18px] font-bold text-text-primary">What&apos;s Coming Next</h2>
          </div>
        </div>

        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {COMING_SOON.map((item) => (
            <div key={item.title} className="rounded-xl border border-dashed border-surface-border/[0.12] bg-text-primary/[0.02] p-4">
              <span className="inline-block rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-[9px] font-bold uppercase tracking-[0.1em] text-amber-700 dark:border-amber-500/25 dark:bg-amber-500/10 dark:text-amber-400">
                Planned
              </span>
              <p className="mt-2 text-[13px] font-semibold text-text-primary">{item.title}</p>
              <p className="mt-1 text-[12px] leading-5 text-text-muted">{item.desc}</p>
            </div>
          ))}
        </div>

        <p className="mt-4 text-[11.5px] italic text-text-muted">
          Roadmap items are subject to change as MarketRipple evolves — this list describes
          direction, not a committed release schedule.
        </p>
        <p className="mt-3 text-[12px] text-text-muted">
          Have a feature request?{" "}
          <RoadmapLinkTracker item="feature-request" className="font-medium text-sky-600 underline-offset-2 hover:underline dark:text-sky-400">
            Share your idea
          </RoadmapLinkTracker>{" "}
          — every suggestion is reviewed by the team.
        </p>
      </section>

      {/* ── EXPLORE MARKETRIPPLE ──────────────────────────────────────── */}
      <section aria-labelledby="explore-heading" className="mb-10">
        <h2 id="explore-heading" className="text-[20px] font-black text-text-primary md:text-[24px]">Explore MarketRipple</h2>
        <p className="mt-2 max-w-2xl text-[13.5px] leading-6 text-text-secondary">
          Where to experience these features today.
        </p>
        <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {EXPLORE_LINKS.map((l) => (
            <FeatureLinkTracker
              key={l.href}
              feature={l.title}
              href={l.href}
              className="group block rounded-xl border border-surface-border/8 bg-surface-card p-4 transition hover:border-surface-border/[0.16] hover:bg-text-primary/[0.02]"
            >
              <l.icon className="h-5 w-5 text-violet-600 dark:text-violet-400" aria-hidden="true" />
              <p className="mt-2.5 text-[13px] font-bold text-text-primary">{l.title}</p>
              <p className="mt-1 text-[11.5px] leading-5 text-text-muted">{l.desc}</p>
              <span className="mt-2 inline-flex items-center gap-1 text-[11.5px] font-semibold text-violet-600 group-hover:gap-1.5 dark:text-violet-400">
                Explore <ArrowRight className="h-3 w-3 transition-all" />
              </span>
            </FeatureLinkTracker>
          ))}
        </div>
      </section>

      {/* ── FAQ ────────────────────────────────────────────────────────── */}
      <section aria-labelledby="faq-heading" className="mb-10">
        <h2 id="faq-heading" className="flex items-center gap-2 text-[20px] font-black text-text-primary md:text-[24px]">
          <HelpCircle className="h-5 w-5 text-violet-600 dark:text-violet-400" aria-hidden="true" />
          MarketRipple Product Updates — Frequently Asked Questions
        </h2>
        <div className="mt-5">
          <FaqAccordion faqs={FAQS} />
        </div>
      </section>

      {/* ── FINAL CTA ──────────────────────────────────────────────────── */}
      <section aria-label="Explore MarketRipple" className="rounded-xl border border-surface-border/8 bg-surface-card p-6 text-center md:p-8">
        <h2 className="text-lg font-black text-text-primary">See it all in action</h2>
        <p className="mx-auto mt-2 max-w-md text-[13px] leading-6 text-text-secondary">
          MarketRipple is a free AI-powered market intelligence platform for Indian equity markets — no login required.
        </p>
        <Link
          href="/market-intelligence"
          className="mt-5 inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-violet-600 to-sky-500 px-6 py-2.5 text-sm font-semibold text-white transition hover:opacity-90"
        >
          Explore MarketRipple
          <ArrowRight className="h-3.5 w-3.5" />
        </Link>
      </section>
    </main>
  );
}
