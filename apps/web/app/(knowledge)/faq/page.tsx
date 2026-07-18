"use client";

import { useState } from "react";
import {
  ChevronDown,
  HelpCircle,
  Cpu,
  Database,
  Layers,
  Lock,
} from "lucide-react";

// Metadata cannot be exported from a client component in Next.js 15.
// Declare it in a separate file or move to a parent layout if needed.
// For now, we define it here as a reference:
// export const metadata: Metadata = { ... } — not valid in "use client"

const SECTIONS = [
  {
    id: "getting-started",
    label: "Getting Started",
    icon: HelpCircle,
    color: "text-sky-400",
    accent: "border-sky-500/30 bg-sky-500/[0.06]",
    iconBg: "bg-sky-500/15",
    questions: [
      {
        q: "What is MarketRipple?",
        a: "MarketRipple is an AI-powered market intelligence platform focused on Indian equity markets. It continuously monitors market-moving events — from government policy announcements and RBI decisions to global macro developments — and uses artificial intelligence to analyse their impact on sectors, companies, and broader market themes. The platform synthesises raw information into structured intelligence: impact scores, confidence ratings, ripple-effect cascades, investment opportunity rankings, and AI-curated narratives. MarketRipple is designed to compress hours of research into minutes, giving investors and analysts a real-time edge.",
      },
      {
        q: "Who is MarketRipple designed for?",
        a: "MarketRipple serves a wide range of market participants: retail investors who want to understand how news events affect their holdings; research analysts who need rapid sector-level impact assessments; portfolio managers looking for early signals on macro and policy developments; financial journalists who require structured data about market events; and traders who monitor high-impact catalysts. Whether you are managing a large portfolio or making your first investment decision, MarketRipple provides the intelligence layer to help you research more efficiently.",
      },
      {
        q: "Is MarketRipple free to use?",
        a: "Yes — the current version of MarketRipple is completely free to use. All core features including the Events Engine, AI Search, Market Intelligence dashboard, Opportunity Radar, Stories, Sector Heatmap, Economic Calendar, Ripple Engine, and Company Intelligence pages are available at no cost. Premium plans are planned for a future release and will include advanced portfolio analysis, custom alert builders, deeper AI research reports, and API access for professional users. The What's New page has the latest roadmap information.",
      },
      {
        q: "Does MarketRipple require login or account creation?",
        a: "No — MarketRipple currently requires no login or account creation. You can access all features immediately without registering. This is intentional: we want to remove all friction between you and the intelligence you need. Account features — including saved watchlists, custom alerts, personal preferences, and portfolio tracking — are planned for future releases. When those features launch, they will remain optional and the core platform will stay accessible without an account.",
      },
      {
        q: "What markets does MarketRipple cover?",
        a: "MarketRipple's primary focus is Indian equity markets — specifically stocks listed on the BSE (Bombay Stock Exchange) and NSE (National Stock Exchange). Coverage includes Nifty 50, Sensex, Nifty Bank, Nifty IT, mid-cap and small-cap segments, and sector-level indices. The platform also tracks global market context that influences Indian markets: US equity futures, Gift Nifty, Asian market performance, crude oil, gold, the US Dollar Index, and major macro data releases from the US Federal Reserve, ECB, and other central banks. India VIX is monitored live as a volatility gauge.",
      },
    ],
  },
  {
    id: "ai-features",
    label: "AI Features",
    icon: Cpu,
    color: "text-violet-400",
    accent: "border-violet-500/30 bg-violet-500/[0.06]",
    iconBg: "bg-violet-500/15",
    questions: [
      {
        q: "How does AI Search work?",
        a: "AI Search accepts queries in natural language — for example, 'Which sectors benefit most from a falling rupee?' or 'What is the market impact of the RBI rate hold?' The system processes your query in several stages: (1) Entity extraction identifies companies, sectors, events, and concepts mentioned; (2) The knowledge graph is searched for relevant event, company, and sector nodes matching those entities; (3) AI models synthesise the retrieved information into a structured, sourced answer with confidence indicators; (4) Related events, companies, and opportunities are surfaced as contextual links. The result is a researched answer grounded in MarketRipple's data, not a generic language model response.",
      },
      {
        q: "What is the Ripple Engine?",
        a: "The Ripple Engine is MarketRipple's proprietary cascade analysis system. When a significant market event occurs — a rate cut, a major policy announcement, or a global shock — its effects do not stop at the most obvious sector. The Ripple Engine traces how that event propagates through the economy in four levels of depth: Level 1 (Direct) shows the immediate, most obvious sector and company impacts; Level 2 (Intermediate) captures second-order effects on related industries; Level 3 (Indirect) surfaces distant but statistically linked beneficiaries or losers; Level 4 (Long-term) analyses structural shifts that may take quarters or years to materialise. The engine renders these cascades as an interactive Market Dependency Graph.",
      },
      {
        q: "What is the Market Dependency Graph?",
        a: "The Market Dependency Graph is a force-directed interactive visualisation — the graphical output of the Ripple Engine. Nodes represent events, sectors, and companies. Edges represent causal or correlation-based relationships. Node size encodes impact magnitude; edge colour encodes relationship type (causal, correlated, structural). You can drag nodes, zoom, filter by ripple level, and click any node to see detailed analysis. The graph lets you visually trace how a single event — say, a 100 bps US Fed rate hike — affects Indian IT exporters, bond yields, the rupee, import-heavy sectors, and eventually consumer demand, all in a single interactive view.",
      },
      {
        q: "How are confidence scores calculated?",
        a: "Confidence scores are a weighted composite of several signals: source quality (government/regulatory announcements score higher than unverified social feeds); corroboration (how many independent sources confirm the same fact); historical precedent (how reliably similar events produced the predicted outcome in the past); specificity (a precise policy announcement scores higher than a rumour); and time decay (recent data is weighted more heavily). Scores are expressed as a percentage (0–100%). A score above 85% means high conviction; 60–85% means moderate confidence with some uncertainty; below 60% means the signal should be treated with caution.",
      },
      {
        q: "How often is AI analysis updated?",
        a: "MarketRipple runs continuous background processing on incoming data streams. For newly published events, initial AI classification and impact scoring occurs within minutes of ingestion. Market prices and India VIX are updated in near real-time (subject to data provider delays). News ingestion runs every 5 minutes. Full re-analysis of an event — including ripple cascade recalculation and story reassignment — is triggered when significant new corroborating or contradicting data arrives, or when price action materially diverges from the AI's initial prediction. Economic data (GDP, CPI, RBI decisions) is processed immediately on official release.",
      },
    ],
  },
  {
    id: "data-accuracy",
    label: "Data & Accuracy",
    icon: Database,
    color: "text-emerald-400",
    accent: "border-emerald-500/30 bg-emerald-500/[0.06]",
    iconBg: "bg-emerald-500/15",
    questions: [
      {
        q: "Where does MarketRipple get its data?",
        a: "MarketRipple aggregates data from multiple source categories: (1) Market data — equity prices, index levels, derivatives, and volumes sourced via yfinance and financial data APIs with BSE/NSE as the underlying exchanges; (2) News — aggregated from financial news publishers, wire services, and official press releases; (3) Government announcements — budget documents, PIB press releases, ministry notifications, and parliamentary proceedings; (4) Regulatory filings — RBI circulars, SEBI orders, and stock exchange announcements; (5) Macro data — economic indicators from MoSPI, RBI data warehouse, and global statistics agencies. All sources are attributed in the platform's event cards.",
      },
      {
        q: "How current is the data?",
        a: "Data freshness varies by type: Market prices have a 15-minute delay, which is standard for free-tier financial data. News and event data is ingested within 5 minutes of publication. RBI and SEBI regulatory announcements are processed immediately upon official release. Economic data (CPI, GDP, PMI, IIP) is ingested and analysed as soon as the official statistical authority publishes it. India VIX and index data follow the 15-minute delay standard. For real-time pricing, you should supplement MarketRipple with a live trading terminal — MarketRipple is designed for research intelligence, not tick-by-tick execution.",
      },
      {
        q: "How reliable are the confidence scores?",
        a: "Confidence scores are probability estimates, not guarantees. A score of 90% means our models assign a 90% probability that the stated impact will materialise based on historical patterns and current data — not that it is certain. Markets are inherently uncertain and subject to events that no model can anticipate. Confidence scores should be used as one input among many in your research process, not as the sole basis for investment decisions. See the AI & Methodology page for a full explanation of how scores are constructed and their known limitations.",
      },
      {
        q: "Does MarketRipple replace a financial advisor?",
        a: "No. MarketRipple is a market research and intelligence tool — it aggregates, analyses, and presents publicly available market information in a structured way. It does not replace the personalised advice of a SEBI-registered investment advisor, who takes into account your individual financial situation, risk tolerance, tax status, and long-term goals. MarketRipple can help you arrive at better-researched questions to ask your advisor, understand the market context behind events that affect your portfolio, and discover opportunities worth investigating further. It is a research tool, not an advisory service.",
      },
      {
        q: "Can I rely on MarketRipple for investment decisions?",
        a: "MarketRipple is designed to assist your research process, not to make decisions for you. All investment decisions remain solely the responsibility of the user. The platform's AI analysis, confidence scores, opportunity rankings, and market intelligence are based on publicly available information and algorithmic models that can and do make errors. Before acting on any information from MarketRipple, you should independently verify facts, consult qualified financial professionals, and assess whether any investment is appropriate for your specific situation and risk tolerance. Please read the Disclaimer on our Legal page.",
      },
    ],
  },
  {
    id: "features",
    label: "Features",
    icon: Layers,
    color: "text-amber-400",
    accent: "border-amber-500/30 bg-amber-500/[0.06]",
    iconBg: "bg-amber-500/15",
    questions: [
      {
        q: "What is Opportunity Radar?",
        a: "Opportunity Radar is MarketRipple's AI-scored investment opportunity discovery engine. It continuously evaluates market events, sector momentum, policy developments, and company-specific catalysts to generate a ranked list of investment opportunities, each scored 0–100. The score combines event impact strength, AI confidence, sector trend direction, and company exposure quality. Opportunities are filterable by sector (Banking, Energy, Technology, Defence, etc.) and theme (AI Infrastructure, Railways, Renewable Energy, EVs, Semiconductors). Each opportunity has a dedicated detail page with financial metrics, event timeline, AI analysis, and related companies.",
      },
      {
        q: "What are Stories?",
        a: "Stories are AI-synthesised investment themes that connect multiple related events into a coherent, multi-layered narrative. Where an individual event is a single data point, a Story is a pattern: 'India Infrastructure Supercycle' synthesises dozens of events — budget allocations, project announcements, tender awards, company results — into a unified investment thesis with a time horizon, risk assessment, and list of key beneficiaries. Stories help you see the forest rather than the trees: they are investment narratives that persist and evolve over months or years as new evidence accumulates.",
      },
      {
        q: "What is the difference between Events and Stories?",
        a: "Events are individual, time-stamped market occurrences: a rate decision, a government order, a quarterly result, a global macro release. Each event is discrete, has its own impact score, and affects specific sectors and companies. Stories, by contrast, are multi-event investment narratives curated by AI over time. A Story aggregates many related events and synthesises them into a thematic investment case with a long-term outlook. Think of events as individual puzzle pieces and stories as the assembled picture. You might monitor events daily, but stories inform your medium-to-long-term positioning.",
      },
      {
        q: "How does the breaking news alert system work?",
        a: "MarketRipple's alert system runs continuous monitoring across all ingested data sources. When an event is classified by the AI with an impact score of 8 or above (on a 10-point scale), a breaking news alert is triggered and displayed at the top of the platform. Alert categories include: policy shocks (emergency RBI decisions, surprise budget items), major corporate events (large merger announcements, significant earnings misses), and global catalysts (Fed emergency action, geopolitical escalation). Alerts are timestamped and linked to the full event analysis so you can immediately understand the context and cascade implications.",
      },
      {
        q: "Can I track specific companies?",
        a: "Yes. Each listed company on MarketRipple has its own Company Intelligence page, accessible by searching the company name or symbol. A company page shows: all events that directly or indirectly affect the company, with impact direction (positive/negative/neutral); AI analysis of the company's exposure to each major market theme; sector context showing how peers are being affected; opportunity radar entries featuring the company; and related stories in which the company plays a beneficiary or risk role. Company pages are updated continuously as new events are classified that involve that ticker.",
      },
    ],
  },
  {
    id: "privacy-technical",
    label: "Privacy & Technical",
    icon: Lock,
    color: "text-rose-400",
    accent: "border-rose-500/30 bg-rose-500/[0.06]",
    iconBg: "bg-rose-500/15",
    questions: [
      {
        q: "Does MarketRipple store my personal data?",
        a: "No. Because MarketRipple currently requires no login or account creation, we do not collect any personally identifiable information. Usage analytics are collected in anonymous, aggregated form only — for example, which pages are visited most frequently or which search queries are most common — and cannot be linked back to any individual. No names, email addresses, phone numbers, device fingerprints, or tracking cookies that identify individuals are stored. If account features are introduced in future, a clear and explicit privacy policy update will accompany them.",
      },
      {
        q: "What technology powers MarketRipple?",
        a: "MarketRipple is built on a modern, open-source-friendly technology stack. The frontend is built with Next.js 15 (App Router), TypeScript, and Tailwind CSS, delivering a fast, responsive web experience. The backend uses Python with FastAPI, providing high-performance API endpoints. Market data is sourced via yfinance and specialised financial data APIs. AI analysis is powered by models accessed through OpenRouter (currently using free-tier models). Data storage uses PostgreSQL with Redis for caching and real-time data handling. The infrastructure is containerised with Docker for reliable deployment.",
      },
      {
        q: "Will MarketRipple have mobile apps?",
        a: "MarketRipple's web platform is already fully mobile-optimised and responsive, providing a near-native experience on iOS and Android browsers. All features — including the interactive Ripple graph, Opportunity Radar, AI Search, and Stories — work on mobile devices. Dedicated native apps for iOS and Android are on the development roadmap. When available, native apps will offer push notifications for breaking news alerts, offline access to saved intelligence, and biometric authentication. Check the What's New page for the latest status on mobile app development.",
      },
      {
        q: "How do I report a bug or request a feature?",
        a: "Use the Contact page to get in touch. For bugs, select 'Bug Reports' and describe what you were doing, what you expected to happen, and what actually happened — screenshots are very helpful. For feature requests, write to support@marketripple.in with 'Feature Request' in the subject line and describe the problem you want solved and how you imagine a solution might work. All bug reports and feature requests are reviewed by the team. Critical bugs affecting core functionality are addressed within 24 hours on business days.",
      },
      {
        q: "What are the upcoming premium features?",
        a: "The MarketRipple premium tier (planned, not yet live) will include: Advanced Portfolio Analysis — connect your holdings to see personalised event impact assessments across your specific portfolio; Custom Alert Builder — define precise conditions (sector + impact score + confidence threshold) to trigger personalised alerts; Deeper AI Reports — downloadable PDF research reports with extended analysis, sector comparisons, and multi-scenario projections; API Access — programmatic access to MarketRipple's event classification, company data, and opportunity scores for professional and institutional users; and Priority Data Refresh — near-zero latency data for high-frequency research workflows.",
      },
    ],
  },
];

function AccordionItem({
  q,
  a,
  isOpen,
  onToggle,
}: {
  q: string;
  a: string;
  isOpen: boolean;
  onToggle: () => void;
}) {
  return (
    <div
      className={`rounded-xl border transition-colors duration-200 ${
        isOpen
          ? "border-white/[0.12] bg-white/[0.04]"
          : "border-white/[0.06] bg-transparent hover:border-white/[0.10] hover:bg-white/[0.02]"
      }`}
    >
      <button
        onClick={onToggle}
        className="flex w-full items-start justify-between gap-4 px-5 py-4 text-left"
        aria-expanded={isOpen}
      >
        <span className="text-[14px] font-medium leading-snug text-slate-200">
          {q}
        </span>
        <ChevronDown
          className={`mt-0.5 h-4 w-4 shrink-0 text-slate-500 transition-transform duration-200 ${
            isOpen ? "rotate-180 text-slate-300" : ""
          }`}
        />
      </button>
      <div
        className={`overflow-hidden transition-all duration-200 ${
          isOpen ? "max-h-[600px] opacity-100" : "max-h-0 opacity-0"
        }`}
      >
        <p className="px-5 pb-5 text-[13px] leading-6 text-slate-400">{a}</p>
      </div>
    </div>
  );
}

export default function FAQPage() {
  const [openItems, setOpenItems] = useState<Record<string, boolean>>({});

  function toggle(key: string) {
    setOpenItems((prev) => ({ ...prev, [key]: !prev[key] }));
  }

  return (
    <main className="min-w-0 pb-10">
      {/* Hero */}
      <div className="mb-10">
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">
          Knowledge Centre
        </p>
        <h1 className="mt-3 text-[28px] font-black leading-tight text-white md:text-[36px]">
          Frequently Asked Questions
        </h1>
        <p className="mt-3 max-w-2xl text-[15px] leading-7 text-slate-400">
          Everything you need to know about MarketRipple — how it works, what powers
          the AI, how data is sourced, and what to expect next.
        </p>

        {/* Section jump links */}
        <div className="mt-6 flex flex-wrap gap-2">
          {SECTIONS.map((s) => {
            const Icon = s.icon;
            return (
              <a
                key={s.id}
                href={`#${s.id}`}
                className="flex items-center gap-1.5 rounded-full border border-white/[0.08] bg-white/[0.03] px-3 py-1.5 text-[12px] text-slate-400 transition hover:border-white/[0.14] hover:text-slate-200"
              >
                <Icon className="h-3.5 w-3.5" />
                {s.label}
              </a>
            );
          })}
        </div>
      </div>

      {/* Sections */}
      <div className="space-y-10">
        {SECTIONS.map((section, si) => {
          const Icon = section.icon;
          return (
            <section key={section.id} id={section.id}>
              {/* Section header */}
              <div className={`mb-4 flex items-center gap-3 rounded-xl border px-4 py-3 ${section.accent}`}>
                <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${section.iconBg}`}>
                  <Icon className={`h-4 w-4 ${section.color}`} />
                </div>
                <div>
                  <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">
                    Section {si + 1} of {SECTIONS.length}
                  </p>
                  <p className={`text-[15px] font-semibold ${section.color}`}>
                    {section.label}
                  </p>
                </div>
                <span className="ml-auto text-[12px] text-slate-500">
                  {section.questions.length} questions
                </span>
              </div>

              {/* Questions */}
              <div className="space-y-2">
                {section.questions.map((item, qi) => {
                  const key = `${si}-${qi}`;
                  return (
                    <AccordionItem
                      key={key}
                      q={item.q}
                      a={item.a}
                      isOpen={!!openItems[key]}
                      onToggle={() => toggle(key)}
                    />
                  );
                })}
              </div>
            </section>
          );
        })}
      </div>

      {/* Footer note */}
      <div className="mt-12 rounded-xl border border-white/[0.08] bg-[#080c14] p-5 text-center">
        <p className="text-[13px] text-slate-400">
          Didn&apos;t find what you were looking for?{" "}
          <a
            href="/contact"
            className="font-medium text-sky-400 underline-offset-2 hover:underline"
          >
            Contact us
          </a>{" "}
          and we&apos;ll get back to you.
        </p>
      </div>
    </main>
  );
}
