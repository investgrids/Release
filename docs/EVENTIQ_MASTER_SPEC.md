# MARKETRIPPLE MASTER SPECIFICATION
### Version 1.0 · July 2026 · The Product Constitution

> This document is the single source of truth for the MarketRipple platform. Every feature, every component, every API endpoint, every design decision must conform to this specification. If a feature is not covered here, it must be proposed as an amendment before implementation begins. No exceptions.

---

## TABLE OF CONTENTS

1. [Product Vision](#1-product-vision)
2. [Product Principles](#2-product-principles)
3. [Target Users](#3-target-users)
4. [Information Architecture](#4-information-architecture)
5. [Module Specifications](#5-module-specifications)
6. [Intelligence Layer Framework](#6-intelligence-layer-framework)
7. [AI Transparency Framework](#7-ai-transparency-framework)
8. [Knowledge & Trust Center](#8-knowledge--trust-center)
9. [Design System](#9-design-system)
10. [Component Library](#10-component-library)
11. [Backend Standards](#11-backend-standards)
12. [Frontend Standards](#12-frontend-standards)
13. [Performance Standards](#13-performance-standards)
14. [Security](#14-security)
15. [Accessibility](#15-accessibility)
16. [SEO](#16-seo)
17. [QA Checklist](#17-qa-checklist)
18. [Product Roadmap](#18-product-roadmap)
19. [Coding Standards](#19-coding-standards)
20. [Product Review Checklist](#20-product-review-checklist)

---

# 1 PRODUCT VISION

## 1.1 What MarketRipple Is

MarketRipple is an AI-powered market intelligence platform built specifically for Indian equity markets. It transforms raw financial events — RBI policy decisions, geopolitical shocks, quarterly earnings, regulatory changes, global macro shifts — into structured, explainable investment intelligence.

MarketRipple is not a stock screener. It is not a trading terminal. It is not a news aggregator. It is a reasoning engine that answers the question every investor actually needs answered: **not what happened, but what it means, who is affected, what chain reactions will follow, and where opportunity or risk lies**.

The platform ingests thousands of market signals daily, classifies them using AI, traces their ripple effects across sectors and companies using a proprietary dependency graph, synthesizes multi-event investment themes, and surfaces scored opportunities — all with full transparency about how every conclusion was reached.

## 1.2 The Problem MarketRipple Solves

Indian retail investors face three compounding problems that no existing platform adequately addresses:

**Problem 1: Information Overload Without Context**
Financial news volume has increased 400% in the last decade. The average investor sees 200+ market headlines daily. None of these headlines explain the chain of effects. "RBI raises rates by 50 bps" is a fact. What it means for banking NIM compression, real estate demand, NBFC funding costs, IT sector currency exposure, and automotive loan affordability is the intelligence — and no platform provides it automatically.

**Problem 2: Data Without Relationships**
Traditional platforms show isolated data: a stock price, an earnings figure, a news headline. Markets are fundamentally relational systems. Crude oil prices affect aviation, which affects tourism, which affects hospitality, which affects real estate in certain geographies. No traditional platform maps these relationships dynamically, in real time, with confidence scores on every connection.

**Problem 3: AI Without Explainability**
A new generation of AI-powered financial tools exists, but they function as black boxes. They surface recommendations without evidence, predictions without reasoning, scores without methodology. When the AI is wrong — and it will be — users have no basis to evaluate the error or adjust their thinking. Unexplained AI in finance is not intelligence; it is noise with a confidence interval.

MarketRipple solves all three problems simultaneously: it explains news in context, maps relationships across the market, and makes its AI reasoning fully visible and auditable.

## 1.3 Who It Serves

MarketRipple serves the full spectrum of Indian equity market participants, from first-time retail investors learning how markets work to professional research analysts who need structured intelligence faster than their existing workflows provide. See Section 3 for complete persona definitions.

## 1.4 How It Differs From Traditional Platforms

| Dimension | Traditional Platforms | MarketRipple |
|---|---|---|
| Primary output | Price data + news | Explained events + ripple chains |
| AI role | Screening / alerts | Reasoning + transparency |
| Market view | Isolated instruments | Relational dependency graph |
| Investment thesis | User-constructed | AI-synthesized with evidence |
| Confidence | Absent | Explicit, scored, explained |
| Explainability | None | Full methodology visible |
| Indian market depth | Generic | BSE/NSE/RBI/SEBI/FII-DII native |
| Navigation model | Data tables | Intelligence stories |

Moneycontrol shows you that RBI raised rates. MarketRipple shows you which 47 companies are affected, in which direction, with what confidence, and why — with links to the evidence that supports each claim.

## 1.5 Long-Term Vision

MarketRipple's five-year vision is to become the definitive AI reasoning layer for Indian equity markets — the platform that professional investors, research analysts, financial journalists, and serious retail investors consult before making any significant portfolio decision.

In concrete terms, this means:

- **The standard reference**: When a major event occurs — a Union Budget, a geopolitical shock, an RBI surprise — MarketRipple's ripple analysis is cited and referenced by financial media within hours.
- **The intelligent interface**: Investors can ask MarketRipple any market intelligence question in natural language and receive a sourced, reasoned, auditable answer within seconds.
- **The opportunity discovery layer**: MarketRipple surfaces investment opportunities that a solo analyst would take days to identify manually, available to every investor regardless of resources.
- **The trust standard**: MarketRipple's AI Transparency Framework becomes the industry benchmark for how financial AI should explain itself.

## 1.6 Product Philosophy

MarketRipple is built on five philosophical commitments that are non-negotiable:

**Explain, don't just show.** Every data point has context. Every event has consequences. Every consequence has a chain. Our job is not to display information — it is to explain it.

**Evidence before conclusions.** No AI output is published without supporting evidence. Confidence scores must be justified. Every claim must link to a source, a historical analogue, or a reasoning chain that users can inspect.

**Transparency is a feature, not a footnote.** The methodology behind every AI analysis is always one click away. We do not hide how we think. We show our work because investors who understand our reasoning can improve it — and can catch us when we are wrong.

**Relationships over isolated data.** Markets are systems, not collections of independent instruments. MarketRipple always presents data in relationship to other data. A stock price without its event context is half the picture. An event without its ripple chain is an incomplete story.

**Education through intelligence.** MarketRipple does not just tell investors what to think. It shows them how to think about markets — through real examples, live data, and transparent reasoning. Over time, investors who use MarketRipple should become better investors, not more dependent on the platform.

---

# 2 PRODUCT PRINCIPLES

These principles govern every product decision. When two approaches are in conflict, these principles determine which to choose. They are ordered by priority.

## 2.1 Explain Before Recommending

MarketRipple never makes a recommendation without first explaining the underlying situation. If a user sees "Buy Signal" without understanding why, we have failed. Every recommendation, every scored opportunity, every flagged risk must be preceded by a clear explanation of the event, the relationship chain, the evidence, and the confidence level. A user must be able to say "I understand why MarketRipple thinks this" before they see a score.

**Implementation rule:** No AI output component may render a conclusion before rendering a reasoning section. `AITransparencyPanel` must always appear at or near the top of any AI-generated content block, not below it.

## 2.2 Evidence Before Conclusions

Every AI conclusion must be accompanied by its supporting evidence. Evidence types include: government announcements, regulatory filings, earnings reports, economic indicators, breaking news, historical patterns, company reports, and global events. Each piece of evidence must be typed, labeled, dated, and linked where possible.

**Implementation rule:** The `EvidenceCard` component must appear on every page that contains AI-generated analysis. Minimum one evidence item required to publish any AI conclusion. If evidence is unavailable, the analysis must be withheld or clearly marked as speculative with a Low confidence score.

## 2.3 AI Must Be Explainable

Every AI inference — whether it is a confidence score, a ripple chain connection, a story synthesis, or an opportunity score — must have a visible explanation. Users must be able to access: what the AI concluded, why it reached that conclusion, what evidence it used, what assumptions it made, what limitations apply, and what alternative outcomes are possible.

**Implementation rule:** The `MethodologyDrawer` must be accessible from every AI-generated content block via a "View Methodology" button. The drawer must contain reasoning, confidence calculation, relationship chain, events analyzed, companies analyzed, assumptions, and known limitations.

## 2.4 Relationships Over Isolated Data

Market events do not exist in isolation. Every event has antecedents, contemporaries, and consequences. MarketRipple always surfaces events in their relational context. A company page must show the events affecting that company. An event page must show the companies affected. A sector view must show its relationship to macro events. Data without relationships is raw material, not intelligence.

**Implementation rule:** No entity page (event, company, sector, story, opportunity) may exist without links to related entities. Orphan pages — pages with no outbound or inbound connections to other MarketRipple entities — must not be shipped.

## 2.5 Quality Over Quantity

MarketRipple does not compete on the number of data points it shows. It competes on the quality of insight derived from those data points. Ten well-explained, well-evidenced connections are more valuable than a hundred unexplained data rows. Prefer fewer, richer insights over exhaustive but shallow data tables.

**Implementation rule:** When displaying lists of events, companies, opportunities, or stories, cap display at 10-15 items with a clear "See More" path. Do not paginate endlessly. Curate aggressively. An empty state with a clear explanation is preferable to 50 low-quality items.

## 2.6 Increase Intelligence, Not Navigation

Every new feature must increase the intelligence of the platform — the depth of insight available to the user — rather than adding navigation complexity. The goal is not to have more pages; it is to make every existing page more intelligent, more connected, and more explanatory.

**Implementation rule:** Before adding a new top-level navigation item, teams must demonstrate that the feature cannot be a sub-section of an existing module. The 7-module navigation structure is final. See Section 4.4 for the rationale.

## 2.7 Every Page Tells a Complete Story

A user landing on any MarketRipple page — whether it is a specific event, a company analysis, a ripple chain, or an opportunity radar item — should be able to understand the full picture from that page alone. They should not need to navigate to five other pages to construct context. Each page must be self-contained: it surfaces the event, the why, the who is affected, the evidence, the opportunity or risk, and the path forward.

**Implementation rule:** Every entity detail page must include: entity description, AI summary, confidence score, related entities (events/companies/sectors), evidence cards, and a clear call to action (view ripple chain, explore companies, find related stories). See Section 20 for the complete Product Review Checklist.

## 2.8 Transparency Is Mandatory

AI transparency is not optional, not a "nice to have," and not something applied inconsistently across features. Every AI-generated output — every summary, score, chain, story, opportunity, or recommendation — must carry its transparency layer. This is an unconditional product requirement.

**Implementation rule:** Before any AI-generated feature is merged to production, the QA checklist must confirm: (1) AITransparencyPanel is rendered, (2) MethodologyDrawer opens correctly, (3) ConfidenceBadge is visible, (4) EvidenceCards are present, (5) WhyAmISeeingThis is accessible, (6) AIDisclaimer is rendered. See Section 17 for the full QA checklist.

---

# 3 TARGET USERS

## 3.1 Persona: Retail Investor — The Informed Beginner

**Profile:** Ages 25-40. Salaried professional with ₹5,000–₹50,000/month investable surplus. Invests in direct equity, mutual funds, or both. Reads financial news daily but struggles to connect events to portfolio implications. Uses Zerodha or Groww for execution but finds their research tools insufficient. Has experienced at least one significant loss from acting on incomplete information.

**Core need:** "I read that RBI raised rates. What does this mean for my banking stocks? Should I be worried about my real estate holdings?"

**What MarketRipple provides:** The event is explained in plain language. The ripple chain shows which sectors and companies are affected, with what magnitude, and with what confidence. The user can see whether their specific holdings are in the affected companies list. They can read the evidence supporting each claim. They can check the AI's confidence level and decide whether to act.

**Success metric:** User can answer "I understand exactly what this event means for my investments" after 3 minutes on MarketRipple.

**Design considerations:** Language must be jargon-free. Financial terms must be explained on first use. The platform should not assume knowledge of option chains, derivative strategies, or advanced technical analysis. Charts must be simple and labeled. AI explanations must be in plain Indian English, not financial textbook prose.

## 3.2 Persona: Swing Trader — The Active Short-Term Investor

**Profile:** Ages 28-45. Invests 5-15 hours per week on market research. Holds positions for days to weeks. Uses technical analysis but increasingly relies on event-driven catalysts for entries and exits. Needs to understand which events create short-term price movements and why.

**Core need:** "A major policy announcement just dropped. Which stocks will move in the next 3-5 days? What's the catalyst and how strong is it? What are the risks to the thesis?"

**What MarketRipple provides:** The Breaking News alert surfaces high-impact events in real time. The event detail page shows immediate vs. long-term impact classification. The beneficiary and risk company lists are ranked by impact score. The Market Reaction tab shows bull/base/bear cases. The AI confidence score indicates how certain the analysis is. The risk factors section identifies what could invalidate the trade thesis.

**Success metric:** User identifies a catalyst-driven opportunity within 5 minutes of a major event, with sufficient evidence to evaluate the trade.

**Design considerations:** Speed matters. Information hierarchy must be optimized for scanning, not reading. Impact scores, company names, and direction (up/down) must be visible without scrolling. Mobile experience must be near-parity with desktop.

## 3.3 Persona: Long-Term Investor — The Thematic Allocator

**Profile:** Ages 30-55. Builds concentrated portfolios around multi-year investment themes. Invests ₹1L–₹10L+ in single thematic positions. Thinks in terms of structural trends: defense indigenization, infrastructure supercycle, EV transition, AI adoption. Needs to understand which themes are strengthening and which companies are best positioned within each theme.

**Core need:** "I believe in the India defense manufacturing story. Which events are strengthening or weakening this thesis? Which companies are the purest plays? What's the 5-year opportunity size?"

**What MarketRipple provides:** The Stories module surfaces multi-event investment themes with supporting evidence from 5-10 related events. The Opportunity Radar scores themes by AI confidence, event momentum, sector strength, and historical precedent. The How MarketRipple Thinks page helps users understand the reasoning behind thematic scores. Company intelligence pages show exposure to specific themes.

**Success metric:** User can construct a complete investment thesis — theme, catalyst, evidence, company selection, risk factors, time horizon — using MarketRipple data alone in under 20 minutes.

**Design considerations:** Depth over speed. Long-form content is appropriate. Timeline visualizations showing theme development over time are essential. Historical context and precedent are critical. Users want to see 3-5 year roadmaps, not just today's events.

## 3.4 Persona: Research Analyst — The Professional

**Profile:** Ages 25-35. Works at a mutual fund, PMS, wealth management firm, or independent research house. Produces formal research reports. Needs structured, evidence-backed market intelligence that reduces their data gathering time by 60-70% while maintaining research quality.

**Core need:** "I need to publish a sector note on Indian banking in 4 hours. I need every relevant policy event, regulatory development, earnings surprise, and macro data point from the last 6 months organized and explained."

**What MarketRipple provides:** Structured event timelines by sector. Filtered event lists by category, sector, and date range. AI-synthesized summaries with source attribution. Company-level impact analysis with quantitative scores. Historical analogue events with similarity scores. All content is citable and traceable to primary sources.

**Success metric:** Analyst reduces data-gathering phase of a sector note from 3 hours to 45 minutes.

**Design considerations:** Export/share functionality is important. Dense information display is acceptable — this persona is comfortable with data. Source attribution and primary source links are critical for professional use. API access will be a premium feature.

## 3.5 Persona: Student — The Learning Investor

**Profile:** Ages 18-25. Student of finance, economics, MBA, or CA. Learning how Indian capital markets work. Needs educational context alongside data. Wants to understand not just what is happening but why markets respond the way they do.

**Core need:** "I'm studying for my CFA/MBA. How does a currency depreciation actually affect different sectors? Can I see a real example?"

**What MarketRipple provides:** How MarketRipple Thinks page with real case studies (Israel-Iran conflict chain, RBI rate cut chain). Confidence level explanations that teach the concept of analytical uncertainty. Story pages that synthesize complex multi-event narratives into coherent themes. The FAQ knowledge center explains fundamental concepts without condescension.

**Success metric:** Student can explain a market event's second and third-order effects after reading MarketRipple's analysis of that event.

**Design considerations:** Educational framing for technical concepts. No financial jargon without explanation. The platform's transparent AI methodology actually serves as a teaching tool — students can see how professional-grade market reasoning works.

## 3.6 Persona: Financial Journalist — The Researcher

**Profile:** Ages 25-40. Writes for financial publications, business news channels, or independent newsletters. Needs to verify claims, find supporting data, and identify non-obvious angles on breaking market events.

**Core need:** "A major event just happened. What's the non-obvious second-order effect that other journalists haven't covered? Give me three data points I can verify independently."

**What MarketRipple provides:** Ripple chain analysis reveals second and third-order effects that are not obvious from the primary event. Historical similarity engine identifies analogous past events with outcomes. Confidence scores help journalists calibrate how strongly to state claims. Evidence cards provide verifiable source links.

**Success metric:** Journalist finds a unique market angle — one not covered by other outlets — using MarketRipple's ripple analysis within 10 minutes of a major event.

**Design considerations:** Source transparency is paramount. Every claim must be traceable. Export/share should include source attributions. The AI Disclaimer must be prominent so journalists understand the platform's limitations.

---

# 4 INFORMATION ARCHITECTURE

## 4.1 Navigation Structure

MarketRipple has exactly **7 top-level navigation modules** plus a **Knowledge & Trust Center** accessible via the footer. This structure is final and must not be modified without a formal product amendment.

```
MarketRipple Navigation
├── Market Intelligence        (/) — The command center
├── Events                     (/events) — Event explorer
├── Companies                  (/companies) — Company intelligence
├── Stories                    (/stories) — Investment themes
├── Opportunity Radar          (/radar) — Scored opportunities
├── Ripple Intelligence        (/ripple) — Dependency graph
└── AI Search                  (/ai-search) — Natural language queries

Footer — Knowledge & Trust Center
├── About MarketRipple              (/about)
├── Why MarketRipple                (/why-marketripple)
├── How MarketRipple Works          (/how-it-works)
├── How MarketRipple Thinks         (/how-marketripple-thinks)
├── AI & Methodology           (/ai-methodology)
├── Data Sources               (/data-sources)
├── FAQ                        (/faq)
├── What's New                 (/whats-new)
├── Contact                    (/contact)
├── Privacy Policy             (/legal#privacy)
├── Terms of Service           (/legal#terms)
└── Disclaimer                 (/legal#disclaimer)
```

## 4.2 URL Structure

| Pattern | Example | Notes |
|---|---|---|
| `/` | `/` | Market Intelligence dashboard |
| `/{module}` | `/events` | Module index pages |
| `/{module}/{id}` | `/events/rbi-rate-hike-june-2025` | Entity detail pages; use slug when available, fall back to numeric ID |
| `/{module}/{id}/{sub}` | `/ripple/crude-oil-spike/graph` | Deep-link to specific tab within detail page |
| `/(knowledge)/{page}` | `/about`, `/faq` | Route group; no sidebar in layout |

**Slug rules:** Slugs are hyphen-separated, lowercase, ASCII only, max 80 characters. Generated from title by removing stop words, special characters, and collapsing spaces to hyphens. Numeric IDs are permanent fallbacks when slugs change.

## 4.3 Layout Model

```
┌─ SiteHeader (60px) ──────────────────────────────────────────┐
│ Logo | Nav tabs (7) | AI Search | Alerts | Theme toggle      │
└──────────────────────────────────────────────────────────────┘
┌─ Grid: max-w-[1600px] ───────────────────────────────────────┐
│ ┌─ Sidebar (240px) ─┐ ┌─ Main Content (flex-1) ─────────────┐│
│ │ - Quick links     │ │ - Page content                      ││
│ │ - Recent visits   │ │ - Tabs where applicable              ││
│ │ - Market pulse    │ │ - AI panels                          ││
│ │ - AI tip          │ └─────────────────────────────────────┘│
│ └───────────────────┘                                        │
└──────────────────────────────────────────────────────────────┘
┌─ Footer ─────────────────────────────────────────────────────┐
│ Brand | Product links | Company/Trust Center links           │
└──────────────────────────────────────────────────────────────┘
```

On Knowledge & Trust Center pages (`/(knowledge)/*`), the sidebar is not rendered. The main content area spans the full column width.

**Breakpoints:**
- `sm`: 640px — mobile landscape
- `md`: 768px — tablet
- `lg`: 1024px — small desktop
- `xl`: 1280px — full layout (sidebar + main + optional right panel)
- `2xl`: 1536px — wide screens (additional whitespace only, no new columns)

## 4.4 Why No More Top-Level Modules

The 7-module structure maps directly to the 7 stages of the MarketRipple intelligence pipeline:

1. **Market Intelligence** — aggregates the full picture
2. **Events** — the raw intelligence inputs
3. **Companies** — the entities most directly affected
4. **Stories** — the synthesized themes across multiple events
5. **Opportunity Radar** — the scored output of the intelligence process
6. **Ripple Intelligence** — the relationship visualization layer
7. **AI Search** — the query interface for the entire intelligence graph

Every conceivable feature can be expressed as a sub-component of one of these seven stages. Adding an eighth top-level module would either duplicate an existing stage or fragment the user's mental model without adding clarity. The navigation system should have the fewest possible top-level items needed to cover the full intelligence workflow — and seven achieves that.

**Procedure for proposing a new module:** A written proposal must demonstrate (a) the feature cannot be implemented within any existing module, (b) the feature serves a different stage of the intelligence pipeline than the existing seven, and (c) adding it improves the average user's task completion time rather than increasing navigation burden.

## 4.5 Entity Relationships

```
Market Event
  ├── belongs to: Event Category (Monetary, Fiscal, Geopolitical, Earnings, Regulatory, Global)
  ├── affects: Companies (direct, indirect, thematic)
  ├── affects: Sectors
  ├── relates to: Other Events (historical similarity, concurrent, causal)
  ├── part of: Stories (thematic narratives)
  ├── source of: Ripple Chains
  └── evidence for: Opportunities

Company
  ├── exposed to: Events (beneficiary, risk, neutral)
  ├── member of: Sectors
  ├── appears in: Stories
  ├── listed in: Opportunity Radar
  └── node in: Ripple Dependency Graph

Story (Investment Theme)
  ├── composed of: 3-15 Events
  ├── features: Companies
  ├── contains: Opportunity Radar items
  └── has: Time Horizon, Risk Level, AI Confidence

Opportunity
  ├── driven by: 1+ Events
  ├── benefits: Companies
  ├── belongs to: Theme/Sector
  └── scored by: Opportunity Score algorithm

Ripple Chain
  ├── triggered by: Event
  ├── propagates through: Sectors, Commodities, Currencies
  ├── reaches: Companies
  └── has: Confidence weights on every edge
```

---

# 5 MODULE SPECIFICATIONS

## 5.1 Module: Market Intelligence (/)

### Purpose
The Market Intelligence dashboard is MarketRipple's command center. It provides an at-a-glance view of everything that matters in Indian markets right now, with AI-synthesized context explaining the significance of each data point. It is the page users land on first and return to daily.

### Goals
- Surface today's most important market signals in under 30 seconds of reading
- Provide AI context for each signal, not just raw data
- Enable one-click navigation to any module from a single, information-dense view
- Give users a complete picture of market health without requiring navigation

### Navigation & Tabs
The dashboard uses a tabbed navigation system with the following tabs:

**Pre-Market Tab** (visible before 9:15 AM IST)
- Gift Nifty futures (with premium vs. spot and expected opening range)
- Bank Nifty futures
- India VIX with interpretation badge
- US Futures (S&P 500, Nasdaq 100, Dow Jones) with 12-point sparklines
- Asian Markets (Nikkei, Hang Seng, Shanghai, KOSPI) with country flags
- European Markets (FTSE 100, DAX, CAC 40)
- Indian ADRs on NYSE/NASDAQ (Infosys, Wipro, HDFC Bank, ICICI Bank) with premium/discount
- Currency pairs (USD/INR, EUR/INR, GBP/INR)
- Commodities (Brent Crude, Gold, Silver, DXY)
- FII/DII net flows (previous session, ₹Cr)
- Put-Call Ratio with interpretation
- AI Opening Prediction (bull/neutral/bear % with reasoning)
- Market Opening Countdown Timer (live, client-side)
- Today's Scheduled Events (from Economic Calendar)

**Overview Tab** (primary tab during market hours)
- Market session header with Nifty 50 live, India VIX, market status
- AI Market Wrap (daily AI-synthesized market summary)
- Top Movers (5 gainers, 5 losers from Nifty 500)
- Sector Heatmap (11 NSE sectors, color-coded by performance)
- Trending Events (3-5 highest impact events of the day)
- Opportunity Radar preview (top 3 opportunities)

**After-Market Tab** (visible after 3:30 PM IST)
- Session recap: Nifty 50 final, advance/decline ratio, total volume
- Today's biggest events and their market reactions
- AI Day Wrap summary
- What to watch tomorrow

### Features
- Real-time data refresh every 15 minutes during market hours
- Breaking News Alert system (overlay banner for impact score ≥ 8.0 events)
- Navigation Progress bar on all page transitions
- All data degraded gracefully when APIs fail (cached data with timestamp)

### Backend Requirements
- `GET /api/market/overview` — Nifty50, India VIX, sector performance, top movers
- `GET /api/market/premarket` — full pre-market data bundle
- `GET /api/market/ai-wrap` — AI market summary (cached 6h, regenerated on high-impact events)
- All market data endpoints: 15-minute cache during market hours, 1-hour cache outside
- FII/DII from NSE India API with 6-hour cache; graceful fallback to previous session data
- PCR from NSE option chain API with 15-minute cache

### Frontend Components
- `DashboardHero` — session header with live Nifty and VIX
- `AIMarketWrapCard` — AI summary with transparency panel
- `TopMoversSection` — gainers/losers with sparklines
- `SectorHeatmap` — 11-sector color grid
- `TrendingEvents` — event cards with impact scores
- `PreMarketPanel` — pre-market widget in sidebar
- `OpportunityRadar` — radar preview widget
- `market/tabs/PreMarketTab` — full pre-market view
- `market/tabs/OverviewTab` — main market tab
- `market/tabs/AfterMarketTab` — post-session tab

### Success Metrics
- Time to first meaningful insight: < 15 seconds on page load
- Bounce rate from dashboard < 40% (users navigate to at least one module)
- Pre-market section used by > 30% of daily active users

---

## 5.2 Module: Events (/events)

### Purpose
Events is the intelligence input layer. Every significant market development — RBI announcements, earnings releases, geopolitical shocks, regulatory changes, government policies, global macro events — enters MarketRipple as an event. The Events module allows users to explore, filter, search, and deep-dive into individual events with full AI analysis.

### Goals
- Make every significant market event discoverable and understandable
- Provide AI analysis that explains context, impact, affected entities, and evidence
- Enable historical comparison between current and past events
- Surface the chain of effects from each event through the ripple system

### Navigation
- `/events` — Event list with filters (category, sector, date, impact score)
- `/events/{id}` — Event detail page with 8 tabs

### Event Categories
Events are classified into exactly these categories:
- **Monetary** — RBI rate decisions, liquidity operations, forex interventions
- **Fiscal** — Union Budget, tax policy, government spending, disinvestments
- **Geopolitical** — International conflicts, trade relations, sanctions, diplomatic events
- **Earnings** — Quarterly results, guidance changes, management commentary
- **Regulatory** — SEBI circulars, sector regulations, compliance requirements
- **Global** — International economic data, central bank decisions (Fed, ECB), commodity shocks
- **Corporate** — M&A, leadership changes, capacity expansions, product launches

### Event Detail Page Tabs

**Overview Tab**
- AI Summary with key bullets
- AITransparencyPanel (confidence, evidence, reasoning)
- Beneficiary companies (ranked by impact score, max 5 preview)
- Negatively affected companies (ranked by impact score, max 5 preview)
- Affected sectors with impact direction
- Timeline preview (4 most recent entries)
- Historical similar events (3 most similar)

**Companies Tab**
- Full list of beneficiaries with impact scores, reasons
- Full list of risk-exposed companies with impact scores, reasons
- Neutral/monitoring companies

**Sectors Tab**
- All affected sectors with impact direction and score
- Horizontal bar chart of impact magnitude per sector

**Timeline Tab**
- Complete event timeline from announcement to most recent development
- Each entry: date, title, description

**Historical Tab**
- Similar historical events ranked by similarity score
- Similarity score = AI-computed vector similarity on event embedding
- Each card: event title, date, impact score, similarity %, reason for similarity

**Related News Tab**
- News articles linked to this event
- Source, headline, date, summary

**Market Tab**
- Bull/Base/Bear case analysis (AI-generated)
- Market reaction outlook (short-term, medium-term, volatility, sentiment)
- Key risks and growth catalysts

**Graph Tab**
- ReactFlow force-directed graph showing event → sector → company relationships
- Interactive: zoom, pan, click nodes to navigate

### Backend Requirements
- `GET /api/events/` — paginated list with filters
- `GET /api/events/{id}` — full event detail with all analysis
- `GET /api/events/{id}/market-data` — live market context
- `GET /api/events/{id}/market-chart?period=1D|5D|1M|3M|6M` — Nifty chart data
- Event enrichment is asynchronous; page shows enrichment-in-progress state while AI completes
- Enrichment status: `pending` → `processing` → `done` → `failed`

### Frontend Components
- Event list page with filter sidebar
- `EventCard` — preview card with category badge, impact score ring, AI summary excerpt
- `OverviewTab`, `CompaniesTab`, `SectorsTab`, `TimelineTab`, `HistoricalTab`, `NewsTab`, `MarketTab`, `GraphTab`
- `ScoreRing` — SVG ring chart for impact/confidence scores
- `KpiCard` — metric card for Impact Score, Companies Affected, Sectors, Confidence
- `AITransparencyPanel` — mandatory on Overview tab

### Success Metrics
- Events enriched within 5 minutes of ingestion: > 90%
- Average time on event detail page: > 3 minutes (indicates comprehension, not bounce)
- Users clicking through to at least one related company or event: > 50%

---

## 5.3 Module: Companies (/companies)

### Purpose
Company Intelligence pages aggregate all MarketRipple intelligence around a single listed company — the events affecting it, the sectors it operates in, its AI-analyzed exposure to themes and risks, and its position within the market dependency graph.

### Goals
- Give users a complete event-driven view of any company in the Nifty 500 universe
- Show not just the company's fundamentals but its intelligence exposure: which events are affecting it and why
- Surface the investment thesis for or against the company based on current event intelligence
- Connect company data to the full MarketRipple intelligence ecosystem

### Navigation
- `/companies` — searchable company list
- `/companies/{symbol}` — individual company intelligence page

### Company Detail Sections

**Header**
- Company name, NSE symbol, sector, market cap category (Large/Mid/Small Cap)
- Current price, daily change, 52-week high/low
- AI intelligence score (how much active intelligence MarketRipple has on this company)

**Event Exposure Panel**
- Events where this company is a beneficiary (with impact scores)
- Events where this company is at risk (with impact scores)
- Timeline of event exposure over the past 90 days

**AI Analysis Section**
- Investment thesis: why this company is positioned as a buy/hold/watch
- Key risks: AI-identified risks specific to this company
- Sector context: how the company's sector is positioned
- AITransparencyPanel with confidence, evidence, methodology

**Sector & Theme Exposure**
- Primary sector and sub-sector
- Themes the company is exposed to (from Stories module)
- Opportunity Radar items featuring this company

**Fundamentals Context**
- Revenue, PAT, EPS (most recent quarter)
- Analyst target price range
- Note: MarketRipple does not provide buy/sell recommendations; fundamental data is context only

### Backend Requirements
- `GET /api/companies/` — searchable, filterable company list
- `GET /api/companies/{symbol}` — company detail with all intelligence
- `GET /api/companies/{symbol}/events` — events affecting this company
- `GET /api/companies/{symbol}/price-history` — price chart data

### Success Metrics
- Company pages covering > 95% of Nifty 500 universe
- Event exposure data available for > 80% of company pages
- Users navigating from company to related event: > 40%

---

## 5.4 Module: Stories (/stories)

### Purpose
Stories synthesizes multiple related events into coherent investment themes — the AI-powered editorial layer of MarketRipple. Where the Events module shows individual data points, Stories shows the narrative arc: five to fifteen related events that together constitute an investment case.

### Goals
- Surface multi-event investment themes that individual event analysis cannot reveal
- Provide 6-18 month investment narratives with supporting evidence
- Help users understand structural market shifts, not just short-term catalysts
- Connect thematic analysis to specific companies and opportunities

### Story Structure
Each story contains:
- **Theme headline** — one sentence investment thesis
- **Summary** — 2-3 paragraph overview of the theme, drivers, and timeline
- **Evidence events** — 5-15 related events that support the theme
- **Beneficiary companies** — companies most exposed to the opportunity
- **Risk companies** — companies at risk from the theme's progression
- **Opportunity Score** — 0-100 score based on theme momentum and AI confidence
- **Time Horizon** — short-term (0-6 months), medium-term (6-24 months), long-term (2+ years)
- **Risk Level** — Low / Medium / High / Very High
- **AI Confidence** — 0-100% with full methodology
- **Scenarios** — Bull/Base/Bear outcomes for the theme

### Active Themes (as of July 2026)
- India Infrastructure Supercycle
- Defence Manufacturing & Export Boom
- Green Energy & EV Transition
- AI Infrastructure Buildout
- PLI Scheme Manufacturing Renaissance
- Financial Inclusion & NBFC Growth
- Healthcare & Pharma Expansion
- Railways Modernization
- Agricultural Technology Transformation
- Semiconductor Design & Packaging

### Backend Requirements
- `GET /api/stories/` — list of all active stories
- `GET /api/stories/{slug}` — story detail with full intelligence
- Stories are generated by AI weekly, or when 3+ new supporting events are detected
- Each story has a `last_updated` timestamp indicating when AI re-evaluated the theme

### Success Metrics
- Users spending > 5 minutes on a story page: > 35%
- Stories connected to at least 5 supporting events: 100%
- Story-to-company navigation rate: > 45%

---

## 5.5 Module: Opportunity Radar (/radar)

### Purpose
Opportunity Radar is the scored output layer of MarketRipple's intelligence pipeline. It surfaces the most compelling current investment opportunities, ranked by a multi-factor AI score. Every opportunity is driven by real market events, supported by evidence, and carries a full AI transparency breakdown.

### Opportunity Score Algorithm
The Opportunity Score (0-100) is a weighted combination of:

| Factor | Weight | Description |
|---|---|---|
| Event Impact Score | 30% | Magnitude and breadth of the driving market event |
| AI Confidence Score | 25% | Quality of evidence and analytical certainty |
| Sector Momentum | 20% | Current trend direction and strength in the opportunity's sector |
| Historical Precedent | 15% | How similar past events played out |
| Time Sensitivity | 10% | Urgency and reversibility of the opportunity |

Score bands:
- **90-100**: Excellent — rare, high-conviction opportunities
- **80-89**: Strong — well-evidenced, clear catalyst
- **70-79**: Good — solid evidence, some uncertainty
- **60-69**: Watch — emerging, needs confirmation
- **< 60**: Monitor — too early or insufficient evidence

### Navigation
- `/radar` — full opportunity list with filters (sector, theme, score range, time horizon)
- `/radar/{slug}` — individual opportunity detail page

### Opportunity Detail Sections
- Opportunity score (large, prominent)
- Driving event summary
- Why this opportunity exists (AI-generated bullets)
- Beneficiary companies (ranked by impact score)
- AI Analysis: matters, benefits, risks, invalidating factors
- Opportunity Score chart (simulated history)
- Scenario analysis (Bull/Base/Bear)
- AITransparencyPanel (mandatory)

### Filters Available
- Sector (all 11 NSE sectors)
- Theme (aligned with Stories themes)
- Score range slider
- Time horizon (short/medium/long)
- Risk level

### Backend Requirements
- `GET /api/radar/` — scored opportunity list with filters
- `GET /api/radar/{slug}` — opportunity detail
- Scores recalculated every 15 minutes during market hours, hourly otherwise
- New opportunities created automatically when event impact + company exposure crosses threshold

---

## 5.6 Module: Ripple Intelligence (/ripple)

### Purpose
Ripple Intelligence visualizes the cascade of effects from a single market event through the dependency graph — showing how one event propagates across sectors, commodities, currencies, and companies at multiple levels of depth.

### Goals
- Make visible the hidden relationships between market entities that traditional analysis misses
- Show investors not just first-order effects but second, third, and fourth-order consequences
- Enable scenario analysis: "What if crude hits $130?" generating a new dependency cascade

### Ripple Visualization
MarketRipple uses ReactFlow (force-directed graph) to render the dependency network:

**Node types:**
- Event nodes (violet) — the triggering event
- Sector nodes (sky blue) — affected sectors
- Commodity nodes (amber) — affected commodities
- Currency nodes (emerald) — affected currency pairs
- Company nodes (rose/emerald for negative/positive impact)

**Edge properties:**
- Direction (cause → effect)
- Confidence weight (0-100%)
- Relationship type (commodity chain, currency effect, sector contagion, policy response, earnings impact, sentiment shift, global flow)
- Magnitude (percentage impact estimate)

**Depth levels:**
- Level 1 — Direct effects (highest confidence, 80%+)
- Level 2 — Indirect effects (high confidence, 65-80%)
- Level 3 — Secondary cascade (medium confidence, 50-65%)
- Level 4 — Long-term structural (lower confidence, 35-50%)

### Scenario Analysis
Users can modify event parameters (e.g., crude oil price assumption) and see the dependency graph recalculate. This is an AI-powered feature that requires the backend to re-run the cascade simulation with the modified input.

### Backend Requirements
- `GET /api/ripple/{event_id}` — full ripple chain with all nodes and edges
- `POST /api/ripple/scenario` — run scenario with modified parameters
- `GET /api/ripple/graph` — global market dependency graph (all relationships)
- Graph stored as adjacency list in Redis for fast traversal

### Success Metrics
- Ripple chains generated for > 80% of high-impact events (score ≥ 7.0)
- Graph rendering in < 2 seconds for chains up to 50 nodes
- Scenario analysis response time < 5 seconds

---

## 5.7 Module: AI Search (/ai-search)

### Purpose
AI Search is the natural language query interface for the entire MarketRipple intelligence graph. Users can ask any market intelligence question in plain language and receive a sourced, reasoned, auditable answer.

### Goals
- Make the full depth of MarketRipple's intelligence accessible without knowing what to navigate to
- Answer complex multi-entity questions that would require minutes of manual navigation
- Provide sourced, evidence-backed answers — not black box outputs
- Surface related opportunities, events, and companies alongside every answer

### Query Capabilities
AI Search can answer:
- Entity questions: "What events are affecting HDFC Bank?"
- Sector questions: "How is the IT sector positioned given current USD/INR movements?"
- Causal questions: "Why did Nifty Pharma fall last week?"
- Opportunity questions: "Which sectors benefit from rising crude oil prices?"
- Comparative questions: "Compare the impact of this RBI decision to the June 2022 hike"
- Scenario questions: "What happens to Indian markets if the Fed cuts rates?"

### Answer Structure
Each AI Search response contains:
- **Direct answer** — 2-4 sentences directly answering the query
- **Reasoning chain** — step-by-step reasoning trace showing how the AI reached the answer
- **Supporting events** — MarketRipple events that provide evidence for the answer
- **Affected companies** — companies relevant to the query
- **Related stories** — thematic narratives connected to the answer
- **Confidence score** — how confident the AI is in the answer
- **AITransparencyPanel** — full methodology and evidence for the response

### Technical Architecture
1. Query preprocessing: entity extraction, intent classification, ambiguity resolution
2. Semantic search: vector similarity across MarketRipple event embeddings
3. Graph traversal: BFS through dependency graph to find related entities
4. Evidence assembly: gather supporting events, companies, data points
5. Response generation: LLM synthesis with retrieved context (RAG pattern)
6. Confidence calculation: based on evidence quality and graph depth

**AI Model:** Free-tier models via OpenRouter only (see Section 11.8). No paid models.

### Backend Requirements
- `POST /api/search/query` — accepts natural language query, returns structured response
- Response streaming for perceived performance (stream answer tokens as they generate)
- Query history stored in session (no user accounts currently)
- Rate limiting: 10 queries per minute per IP
- Timeout: 30 seconds maximum; partial response returned on timeout

---

# 6 INTELLIGENCE LAYER FRAMEWORK

The Intelligence Layer Framework defines the reusable intelligence components that appear across multiple MarketRipple modules. Every module must implement the applicable layers. These are not optional enhancements — they are the core intelligence vocabulary of the platform.

## 6.1 Investment Thesis

**What it is:** A 2-4 sentence AI-generated statement of the investment case for or against a position. Explains why the current event or trend constitutes an investable opportunity or risk.

**Format:**
```
[Entity] is [positioned/exposed] to [opportunity/risk] because [cause chain].
The primary catalyst is [event/trend]. The thesis strengthens if [condition] and
weakens if [counter-condition]. Time horizon: [duration].
```

**Where it appears:** Stories, Opportunity Radar, Company detail pages, Ripple Intelligence

**Data requirements:** Minimum 2 supporting events + 1 historical analogue

## 6.2 Market Catalysts

**What it is:** A ranked list of events or conditions that are driving the opportunity or risk. Each catalyst is typed (Monetary, Fiscal, Geopolitical, Earnings, Regulatory, Global, Corporate), scored by impact, and linked to the originating event.

**Display:** Numbered list, max 5 catalysts, each with type badge and impact score

**Where it appears:** All detail pages, AI Search results

## 6.3 Growth Drivers

**What it is:** Structural factors (beyond individual events) that provide multi-year tailwind for an opportunity. Distinguished from Market Catalysts by time horizon (catalysts = weeks/months; drivers = years).

**Examples:** India's demographic dividend, government capital expenditure cycle, global supply chain diversification away from China, increasing formalization of the economy

**Display:** Card grid, max 4 drivers per entity, each with icon and 2-sentence explanation

**Where it appears:** Stories, Opportunity Radar detail pages, Company pages

## 6.4 Opportunity Lifecycle

**What it is:** A 5-stage model describing where an opportunity is in its development arc:
1. **Emerging** — first signals detected, low confidence, early positioning possible
2. **Building** — multiple confirming signals, confidence rising, opportunity strengthening
3. **Peak** — maximum catalyst intensity, highest opportunity score, widest coverage
4. **Maturing** — opportunity well-known, consensus forming, alpha potential declining
5. **Resolving** — catalysts fading, outcome becoming clear, exit timing relevant

**Display:** Horizontal stage indicator with current position highlighted

**Where it appears:** Opportunity Radar detail pages, Stories

## 6.5 Ripple Timeline

**What it is:** A chronological visualization of how an event's effects propagate over time. Short-term effects (days) are distinguished from medium-term (weeks/months) and long-term (quarters/years) effects.

**Display:** Horizontal timeline with event at origin; branching effects plotted left to right by time horizon

**Where it appears:** Event detail pages, Ripple Intelligence module, Story pages

## 6.6 Historical Similarity

**What it is:** AI identification of past events that are structurally similar to a current event, with their outcomes used to inform current confidence calculations.

**Similarity score:** Computed via vector embedding cosine similarity on event descriptions enriched with entity and category metadata.

**Display:** Cards showing: past event title, date, similarity %, what happened, key outcome, relevance to current situation

**Where it appears:** Event detail History tab, Opportunity Radar, AI Search responses

## 6.7 Monitoring Checklist

**What it is:** A set of specific, observable conditions users should monitor to track whether the investment thesis is playing out or breaking down. Each item is a verifiable statement, not a vague concern.

**Format:** Checklist items in two categories:
- **Confirmation signals** (green) — evidence the thesis is working as expected
- **Warning signals** (amber/rose) — evidence the thesis is at risk

**Where it appears:** Opportunity Radar detail pages, Company pages, Story pages

## 6.8 Risk Framework

**What it is:** A structured enumeration of risks with three attributes per risk:
- **Risk type** — Market, Regulatory, Geopolitical, Execution, Valuation, Sector
- **Probability** — Low / Medium / High (qualitative)
- **Impact** — Low / Medium / High / Very High

**Display:** Risk matrix grid or ranked list with type badge, probability indicator, impact indicator, and 1-sentence description

**Where it appears:** All AI analysis sections, Opportunity Radar, Stories, Event detail Market tab

## 6.9 Scenario Analysis

**What it is:** Three explicitly modeled outcomes for any situation:
- **Bull scenario** — conditions that cause the best outcome, probability estimate, target outcome
- **Base scenario** — most likely outcome given current evidence, probability estimate, expected outcome
- **Bear scenario** — conditions that cause the worst outcome, probability estimate, downside outcome

**Display:** Three-column card layout with probability badges (%, not ranges), trigger conditions, and market impact summary

**Where it appears:** Event detail Market tab, Opportunity Radar, Stories, Ripple Intelligence

## 6.10 Expected Evolution

**What it is:** A forward-looking narrative of how the current situation is expected to develop over the next 3, 6, and 12 months. Distinct from Scenario Analysis in that it presents the base case timeline, not alternative scenarios.

**Display:** Horizontal timeline with three waypoints; each waypoint has: timeframe, expected development, key indicator to watch

**Where it appears:** Stories, Opportunity Radar detail pages

## 6.11 Supporting Evidence

**What it is:** The collection of evidence cards that support the AI analysis. Evidence types:
- **Government** — official government announcements
- **Filing** — SEBI/BSE/NSE corporate filings
- **Earnings** — quarterly results and guidance
- **Indicator** — economic data releases (CPI, GDP, IIP, PMI)
- **News** — breaking news from verified financial sources
- **Historical** — historical market data or past event records
- **Company** — company-specific reports or announcements
- **Global** — international events and data with Indian market impact

**Display:** `EvidenceCard` component (see Section 10); clickable when URL available

**Where it appears:** Everywhere AI analysis appears

## 6.12 Confidence Score

**What it is:** A numeric score (0-100) representing the AI's confidence in its analysis. Calculated as:

```
Confidence = (Source Credibility × 0.30) 
           + (Corroboration Score × 0.25) 
           + (Historical Accuracy × 0.20) 
           + (Recency Score × 0.15) 
           + (Domain Expertise Score × 0.10)
```

**Levels:**
- **Very High (90-100):** Emerald — multiple corroborating official sources, strong historical precedent, high analytical consensus
- **High (75-89):** Sky — strong evidence, some historical precedent, minor uncertainty factors
- **Medium (50-74):** Amber — reasonable evidence, moderate uncertainty, possible conflicting signals
- **Low (<50):** Rose — limited evidence, high uncertainty, early-stage hypothesis

**Display:** `ConfidenceBadge` component with optional progress bar

**Mandatory rule:** Every AI-generated output must display a confidence score. An AI output without a confidence score is a product defect.

## 6.13 AI Transparency

See Section 7 for the complete AI Transparency Framework specification.

---

# 7 AI TRANSPARENCY FRAMEWORK

## 7.1 Purpose

The AI Transparency Framework is MarketRipple's commitment to never deploying AI that users cannot understand, question, or verify. It consists of seven components that together make every AI inference auditable.

## 7.2 Components

### 7.2.1 AI Badge
A visual indicator that content is AI-generated. Appears on every AI output block.

**Specification:**
- Icon: `Bot` (lucide-react)
- Label: "AI Generated"
- Container: small rounded pill, violet-500/15 background
- Always appears at the top-left of any AI content block

### 7.2.2 Confidence Badge
See Section 6.12. The confidence badge appears adjacent to the AI badge in the same header row.

### 7.2.3 Reasoning Section
A plain-language explanation of how the AI reached its conclusion. Must be the first content item after the header row.

**Requirements:**
- Written in the first person on behalf of MarketRipple ("MarketRipple analyzed...")
- Maximum 4 sentences for the primary reasoning
- Additional "Full Reasoning" expandable section for longer explanations
- No jargon without explanation

### 7.2.4 Evidence Cards
Supporting evidence items presented in a consistent format. See `EvidenceCard` specification in Section 10.

**Requirements:**
- Minimum 1 evidence card per AI conclusion
- Maximum 6 evidence cards visible without "Show More" interaction
- Evidence must be dated
- Evidence must link to primary source when URL is available

### 7.2.5 Why Am I Seeing This (WhyAmISeeingThis)
An interactive modal explaining why this specific result was surfaced to the user.

**Required fields:**
- Reason: why this analysis was generated
- Influences: what factors contributed to the analysis
- Relationship Chain: the causal path from event to conclusion
- Historical Examples: past precedents for this type of analysis
- Alternative Scenarios: what could make this analysis wrong

### 7.2.6 View Methodology (MethodologyDrawer)
A right-side slide-in drawer with the complete technical methodology for the analysis.

**Required sections:**
- Confidence Score: numeric score with bar and explanation
- Why AI Reached This Conclusion: detailed reasoning
- Relationship Chain: step-by-step causal chain with confidence per step
- Market Events Considered: list of events used in the analysis
- Companies Analyzed: companies considered
- Assumptions: explicit assumptions made
- Known Limitations: what this analysis cannot account for
- Learn More Links: links to How MarketRipple Thinks, AI & Methodology, Data Sources

### 7.2.7 AI Disclaimer
A standard disclaimer that AI-generated content is for research and educational purposes only and does not constitute investment advice.

**Two modes:**
- **Compact:** Single line with link to `/legal#disclaimer`
- **Full:** AlertTriangle icon + full disclaimer text + link

**Placement:** Always at the bottom of any AI content block. Never omitted.

## 7.3 AITransparencyPanel (Composite Component)

The `AITransparencyPanel` is the primary delivery vehicle for the AI Transparency Framework. It composes all seven components into a single cohesive UI block.

**Props:**
```typescript
interface AITransparencyProps {
  confidence: number;           // 0-100
  reasoning: string;            // AI reasoning text
  summary?: string;             // Optional shorter summary
  events?: LinkedItem[];        // Related events
  companies?: CompanyItem[];    // Affected companies
  stories?: LinkedItem[];       // Related stories
  evidence?: EvidenceCardProps[]; // Supporting evidence
  relationshipChain?: RelationshipStep[]; // Causal chain
  assumptions?: string[];       // Analytical assumptions
  limitations?: string[];       // Known limitations
  updatedAt?: string;           // When analysis was generated
  title?: string;               // Panel title
  whyReason?: string;           // Why Am I Seeing This reason
  whyInfluences?: string[];     // Influencing factors
  whyChain?: string[];          // Relationship chain steps
  whyHistorical?: string[];     // Historical examples
  whyAlternatives?: string[];   // Alternative scenarios
  compact?: boolean;            // Collapsed by default
  className?: string;           // Additional CSS classes
}
```

**Mandatory use:** `AITransparencyPanel` must appear on every page that contains AI-generated content. It may not be omitted, hidden behind a feature flag, or replaced with a custom implementation.

## 7.4 AI Model Policy

**Permanent constraint: MarketRipple uses only free-tier AI models via OpenRouter.**

This constraint is non-negotiable and applies to all AI calls across all features, both current and future. No paid AI models may be used. The reason: MarketRipple must remain economically sustainable as a free platform. AI costs that scale with usage would compromise that sustainability.

**Approved providers:** OpenRouter free tier only.
**Approved models:** Any model available on OpenRouter's free tier at time of implementation. Models change; the constraint (free tier only) does not.
**Implementation:** All AI calls must route through the `apps/backend/app/services/ai_service.py` module, which enforces the free model constraint.

---

# 8 KNOWLEDGE & TRUST CENTER

The Knowledge & Trust Center is the educational and transparency backbone of MarketRipple. It exists in the `app/(knowledge)/` Next.js route group, rendering without the sidebar navigation. Links are in the site footer, not the main navigation.

## 8.1 About MarketRipple (/about)

**Purpose:** Introduce MarketRipple to users who are encountering it for the first time, or who want to understand its full scope.

**Required sections:**
- Hero with mission statement
- The Problem (3 cards: information overload, no context, no connections)
- Our Mission (blockquote-style statement)
- Our Solution (3-column: explain news, connect events, surface opportunities)
- Core Features (6-card grid)
- Product Philosophy (3 principles with icons)
- Product Roadmap (4 phases: Live, Q3 2025, Q4 2025, 2026)
- CTA linking to dashboard and How It Works

## 8.2 Why MarketRipple (/why-marketripple)

**Purpose:** Address the "why switch" question for users who currently use Moneycontrol, Zerodha Kite, ET Markets, or similar platforms.

**Required sections:**
- Traditional Platform vs. MarketRipple feature comparison (side-by-side)
- Philosophy Gap (3 cards: Data→Intelligence, Events→Opportunities, AI→Explainable AI)
- Real Example (RBI rate hike showing traditional vs. MarketRipple analysis depth)
- Why India (6 cards explaining India-specific market intelligence)
- CTAs to How It Works and How MarketRipple Thinks

## 8.3 How MarketRipple Works (/how-it-works)

**Purpose:** Explain the 9-stage intelligence pipeline from event ingestion to AI Search query response.

**Required sections:**
- Hero: "From Breaking News to Investment Opportunity in Seconds"
- 9-step pipeline timeline (each step: icon, number, latency/stat, tagline, description, checklist)
  1. Breaking News ingestion
  2. AI Analysis
  3. Market Event classification
  4. Ripple Engine cascade
  5. Market Dependency Graph
  6. Companies analysis
  7. Stories synthesis
  8. Opportunity Radar scoring
  9. AI Search query
- Technology section (3 cards: AI Models, Data Pipeline, Graph Engine)
- Pipeline summary (all 9 steps as connected pills)

## 8.4 How MarketRipple Thinks (/how-marketripple-thinks)

**Purpose:** The most important trust page. Demonstrates AI reasoning through real-world examples. Shows users that MarketRipple's AI is not a black box.

**Required sections:**
- Hero: "AI That Shows Its Work"
- 4-step Thinking Framework (Observe, Classify, Connect, Conclude)
- Case Study: Israel-Iran Conflict (full cascading dependency visualization, 8 levels deep)
- Confidence System explanation (4 levels with visual indicators)
- 6 Relationship Types (commodity chain, currency effect, sector contagion, policy response, earnings impact, sentiment shift)
- 3 Alternative Scenarios (Bull/Base/Bear with probabilities)
- Case Study 2: RBI Rate Cut (sector-by-sector P&L impact)
- CTAs to AI & Methodology and Data Sources

**Design note:** The Israel-Iran case study must show the full cascade: Conflict → Strait of Hormuz risk → Crude oil spike → India ATF price → Airlines cost pressure → Consumer inflation → RBI policy response → Real estate / Auto impact, with confidence % at each link.

## 8.5 AI & Methodology (/ai-methodology)

**Purpose:** Technical explanation of how each AI system within MarketRipple works.

**Required sections:**
- Hero: "Transparent AI. Explainable Decisions."
- AI Search: 5-step pipeline + query walkthrough example
- Ripple Engine: graph construction, relationship detection, Bayesian confidence, cascade simulation
- Opportunity Radar: weighted scoring formula with factor breakdown
- Stories Generation: 5-stage pipeline (clustering → themes → evidence → narrative → QC)
- Confidence Score Calculation: 5 factors with weights
- AI Limitations: 6 named limitations with severity coding
- Human Judgment: section emphasizing AI augments, not replaces

## 8.6 Data Sources (/data-sources)

**Purpose:** Complete transparency about where MarketRipple's data comes from.

**Required sections:**
- Hero: "Intelligence Is Only as Good as Its Sources"
- Market Data: BSE, NSE, MCX, COMEX, NYMEX, yfinance, global indices
- Corporate Data: quarterly filings, annual reports, corporate actions, shareholding patterns
- Economic & Government Data: RBI, Ministry of Finance, Ministry of Commerce, SEBI, NSO
- News & Media: aggregation sources, AI filtering methodology
- Refresh Frequency: table with 8 data types and their update cadence
- Processing Pipeline: 4-step ingestion process
- Disclaimer: MarketRipple aggregates public information; verify against primary sources

## 8.7 FAQ (/faq)

**Purpose:** Answer the 25 most common questions. Client component with accordion UI.

**Question groups:**
1. Getting Started (5 questions)
2. AI Features (5 questions)
3. Data & Accuracy (5 questions)
4. Features (5 questions)
5. Privacy & Technical (5 questions)

**Note:** Because FAQ is a client component (`"use client"`), metadata must be exported from a co-located `layout.tsx` file, not from the page itself.

## 8.8 What's New (/whats-new)

**Purpose:** Changelog of product releases. Shows users the platform is actively maintained and improving.

**Format:** Version cards in reverse chronological order, each with:
- Version badge (e.g., v1.4)
- Codename
- Release date
- Category badges: Feature (violet) / Improvement (sky) / Fix (emerald)
- Bulleted change list
- Type count summary row

**Versions to maintain:** v1.0 through current, with new entries added on each release.

## 8.9 Contact (/contact)

**Purpose:** Communication channels for support, feedback, business inquiries, partnerships, media, and bug reports.

**Required sections:**
- 6 contact category cards (Support, Feedback, Business, Partnerships, Media, Bug Reports)
- Feature Requests callout
- Response Times table
- Community section (Discord/forum roadmap note)

## 8.10 Legal (/legal)

**Purpose:** Privacy Policy, Terms of Service, Disclaimer, Risk Disclosure, Cookie Information.

**Anchor IDs required:** `#privacy`, `#terms`, `#disclaimer`, `#risk`, `#cookies`

**Critical legal content:**
- MarketRipple is NOT a registered investment advisor, stock broker, or financial planner
- Nothing on MarketRipple constitutes investment advice
- AI-generated analysis is based on publicly available information and may contain errors
- Users are solely responsible for all investment decisions
- Always consult a SEBI-registered investment advisor for personalized advice
- Indian jurisdiction specified throughout

---

# 9 DESIGN SYSTEM

## 9.1 Color Palette

### Background Colors
```
bg-slate-950      #020617   — Page backgrounds, deepest layer
bg-[#030608]      #030608   — Footer background
bg-[#080c14]      #080c14   — Card backgrounds (primary)
bg-[#0a0d16]      #0a0d16   — Card backgrounds (secondary)
bg-[#0d1028]      #0d1028   — Hero section gradient start
bg-white/[0.025]  rgba(255,255,255,0.025) — Elevated card surface
bg-white/[0.04]   rgba(255,255,255,0.04)  — Interactive hover state
```

### Text Colors
```
text-white        — Primary headings, key values
text-slate-100    — Primary body text on dark backgrounds
text-slate-300    — Secondary body text, descriptions
text-slate-400    — Tertiary text, labels
text-slate-500    — Section labels, metadata, captions
text-slate-600    — Disabled states, copyright notices
```

### Accent Colors (semantic)
```
violet-400/500/600  — Primary AI/intelligence accent; brand color
sky-400/500         — Data, links, informational elements
emerald-400/500     — Positive indicators, success states, buy signals
amber-400/500       — Warnings, neutral indicators, caution
rose-400/500        — Negative indicators, risk signals, sell pressure
teal-400            — Secondary positive accent
indigo-400          — Thematic/story accent
slate-400           — Neutral/unchanged indicators
```

### Border Colors
```
border-white/[0.06]   — Default card borders (very subtle)
border-white/[0.08]   — Slightly more visible card borders
border-white/10       — Interactive element borders
border-white/20       — Hover state borders
border-violet-500/20  — AI content borders
border-violet-500/30  — AI content hover borders
```

### Gradient Patterns
```
— Hero sections: from-[#0d1028] to-[#080c14]
— AI content: violet-500/[0.04] background with violet-500/20 border
— Score rings: sky-500 to violet-500 (gradient arc)
— Brand logo: from-violet-500 to-sky-400
```

## 9.2 Typography

### Type Scale
```
text-[10px]  — Section labels, badges, metadata (UPPERCASE + tracking)
text-[11px]  — Secondary body text, list items, small descriptions
text-[12px]  — Primary body text, button labels, card content
text-[13px]  — Article body, description text
text-[14px]  — Large body, card titles, tab labels
text-xl      — Component headings
text-2xl     — Section headings
text-[28px]  — Page headings (mobile)
text-[36px]  — Page headings (desktop)
text-7xl     — Hero display text (decorative only, opacity reduced)
```

### Font Weights
```
font-normal    (400) — Body text
font-medium    (500) — Labels, navigation items
font-semibold  (600) — Card titles, important labels
font-bold      (700) — Section headings
font-black     (900) — Score numbers, hero headlines, KPI values
```

### Letter Spacing
```
tracking-[0.10em]   — Standard uppercase labels
tracking-[0.12em]   — Section divider labels
tracking-[0.14em]   — Drawer/modal labels
tracking-[0.16em]   — Footer section labels
tracking-[0.18em]   — Primary section labels
tracking-[0.22em]   — Page-level superlabels
```

### Line Height
```
leading-4    — Compact list items (1rem)
leading-5    — Small descriptions (1.25rem)
leading-6    — Body text (1.5rem)
leading-snug — Headings
leading-tight — Display text
```

## 9.3 Spacing

MarketRipple uses Tailwind's default spacing scale. Key conventions:

```
p-3 / p-4 / p-5 / p-6  — Card padding (increase with card prominence)
gap-3 / gap-4 / gap-5 / gap-6  — Grid/flex gaps
space-y-3 / space-y-4 / space-y-5  — Vertical spacing in sections
mb-2 / mb-3 / mb-4 / mb-5  — Section margins within cards
```

**Page-level spacing:**
- `space-y-16` between major page sections (knowledge pages)
- `space-y-5` or `space-y-6` between content blocks within a page
- `pb-20` page bottom padding (ensures footer clearance)

## 9.4 Border Radius

```
rounded-lg       — Small elements (badges, inputs)
rounded-xl       — Medium elements (inner cards, pills, icons)
rounded-[12px]   — Brand logo/icon containers
rounded-[14px]   — Learn More section containers
rounded-[16px]   — AI Transparency Panel
rounded-[20px]   — Primary cards
rounded-[24px]   — Prominent feature cards, hero sections
rounded-full     — Pills, badges, circular elements
```

## 9.5 Card Specifications

### Primary Card
```css
rounded-[20px] border border-white/[0.08] bg-[#080c14] p-5
```

### Elevated Card (hover target)
```css
rounded-[20px] border border-white/[0.06] bg-white/[0.025] p-4
transition hover:-translate-y-0.5 hover:shadow-lg
```

### AI Content Card
```css
rounded-[16px] border border-violet-500/20 bg-violet-500/[0.04]
```

### Hero Section Card
```css
rounded-2xl border border-white/[0.08] bg-gradient-to-br from-[#0d1028] to-[#080c14] p-8 md:p-12
```

### KPI Card
```css
rounded-[20px] border bg-white/[0.025] p-4 transition hover:-translate-y-0.5 hover:shadow-lg
```

## 9.6 Buttons

### Primary Button
```css
rounded-xl bg-violet-600 px-4 py-2 text-[13px] font-semibold text-white 
hover:bg-violet-500 transition
```

### Secondary Button
```css
rounded-xl border border-white/10 bg-white/[0.04] px-3 py-1.5 
text-[12px] text-slate-300 hover:bg-white/[0.08] hover:text-white transition
```

### Ghost Button
```css
text-[12px] text-slate-400 hover:text-white transition
```

### Methodology Button (AI-specific)
```css
rounded-full border border-violet-500/20 bg-violet-500/10 px-2.5 py-1 
text-[10px] font-medium text-violet-400 hover:bg-violet-500/20 transition
```

### Tab Button (active)
```css
-mb-px border-b-2 border-violet-500 text-white px-4 py-2.5 text-[13px] font-medium
```

### Tab Button (inactive)
```css
-mb-px border-b-2 border-transparent text-slate-500 hover:text-slate-300 
px-4 py-2.5 text-[13px] font-medium transition
```

## 9.7 Animations

All animations must respect `prefers-reduced-motion`. Animations serve to indicate state changes and hierarchy; they must not be decorative noise.

**Standard transitions:**
```css
transition           — 150ms ease (Tailwind default, for color changes)
transition-all       — For multi-property changes
duration-200         — Button hover states
duration-300         — Card elevations
duration-700         — Progress bars, confidence meters
```

**Modal entrance:**
```css
@keyframes scaleIn {
  from { opacity: 0; transform: translate(-50%, -48%) scale(0.96); }
  to   { opacity: 1; transform: translate(-50%, -50%) scale(1); }
}
animation: scaleIn 0.18s cubic-bezier(0.16,1,0.3,1)
```

**Drawer entrance:**
```css
@keyframes slideInRight {
  from { transform: translateX(100%); opacity: 0; }
  to   { transform: translateX(0); opacity: 1; }
}
animation: slideInRight 0.22s cubic-bezier(0.16,1,0.3,1)
```

**Loading states:** `animate-pulse` on skeleton elements; `animate-spin` on single circular loaders.

## 9.8 Glassmorphism Policy

MarketRipple uses **false glassmorphism** — the visual appearance without the GPU cost of `backdrop-filter: blur()`. This means:

- Card backgrounds use low-opacity solid colors (`bg-white/[0.025]`, `bg-[#080c14]`) rather than backdrop blur
- `backdrop-blur-sm` is acceptable only for full-screen overlays (modal/drawer backdrops) where performance is acceptable
- Never apply `backdrop-filter` or `backdrop-blur` to cards, panels, or elements that appear in lists
- The visual effect of depth is achieved through border opacity and background lightness, not blur

## 9.9 Dark Mode

MarketRipple is exclusively dark-themed. There is no light mode. Color choices are optimized for dark backgrounds.

- All colors are specified as dark-first
- If future light mode is added, `@media (prefers-color-scheme: dark)` and `[data-theme="dark"]` selectors handle the primary theme; light mode is the override
- No white backgrounds in the main application UI
- Use `text-white` for maximum contrast elements; `text-slate-300` for comfortable reading

## 9.10 Responsive Layout

**Grid system:** CSS Grid via Tailwind. No third-party grid library.

**Main layout grid:**
```css
xl:grid-cols-[240px_1fr_260px]   — With sidebar and right panel
xl:grid-cols-[240px_1fr]         — With sidebar, no right panel
grid-cols-1                       — Mobile stack
```

**Content grids (common patterns):**
```css
grid-cols-2               — Two equal columns (tablet+)
grid-cols-3               — Three columns (desktop+)
grid-cols-4               — Four columns (desktop+, compact)
grid-cols-[1fr_280px]     — Main + narrow panel
grid-cols-[1fr_1.3fr]     — Two asymmetric columns
sm:grid-cols-2 lg:grid-cols-3   — Responsive card grids
```

**Mobile-first rule:** All components must be functional and readable on 375px viewport. Tablet and desktop enhance the experience but are never required for core functionality.

## 9.11 Icons

**Icon library:** `lucide-react` exclusively. Emoji are prohibited throughout the codebase.

**Icon sizes:**
```
h-3 w-3     — Inline icons within text, very small UI elements
h-3.5 w-3.5 — Badge icons, small button icons
h-4 w-4     — Standard button icons, card meta icons
h-5 w-5     — Section icons, feature icons
h-6 w-6     — Header icons
h-8 w-8     — Empty state icons (with container)
h-10 w-10   — Large theme icons
h-12 w-12   — Illustration-scale icons
h-20 w-20   — Hero decorative icons
```

**Color convention:**
- Violet icons — AI, intelligence, methodology elements
- Sky icons — informational, data, links
- Emerald icons — positive, success, growth
- Amber icons — warning, neutral, caution
- Rose icons — risk, negative, danger
- Slate icons — neutral, disabled, decorative

---

# 10 COMPONENT LIBRARY

## 10.1 AI Components

### ConfidenceBadge (`components/ai/ConfidenceBadge.tsx`)
**Props:** `score: number`, `showBar?: boolean`, `showLabel?: boolean`, `size?: "sm"|"md"|"lg"`, `className?: string`

**Exported types:** `ConfidenceLevel` ("very-high"|"high"|"medium"|"low"), `getConfidenceLevel(score: number): ConfidenceLevel`

**Behavior:** Renders a rounded badge with level label and optional progress bar. Colors mapped to confidence level (emerald/sky/amber/rose).

**ConfidenceMeter:** A larger display showing the confidence bar with percentage label. Used inside MethodologyDrawer and AITransparencyPanel.

---

### EvidenceCard (`components/ai/EvidenceCard.tsx`)
**Props:** `type: EvidenceType`, `title: string`, `summary?: string`, `href?: string`, `date?: string`

**Exported types:** `EvidenceType` (8 values), `EvidenceCardProps`

**EvidenceGrid:** Wrapper that accepts `items: EvidenceCardProps[]` and `maxVisible?: number`. Shows items in 2-column grid.

---

### AIDisclaimer (`components/ai/AIDisclaimer.tsx`)
**Props:** `compact?: boolean`, `className?: string`

**Behavior:** Compact mode = one line with link. Full mode = AlertTriangle icon + full disclaimer text.

---

### MethodologyDrawer (`components/ai/MethodologyDrawer.tsx`)
**Client component.** Right-side slide-in drawer.

**Props:** `open: boolean`, `onClose: () => void`, `title: string`, `reasoning: string`, `confidence: number`, `events?`, `companies?`, `relationshipChain?`, `assumptions?`, `limitations?`

**Behavior:** Closes on Escape key and backdrop click. Locks body scroll when open. Focuses drawer on open.

---

### WhyAmISeeingThis (`components/ai/WhyAmISeeingThis.tsx`)
**Client component.** Centered modal with trigger button.

**Props:** `reason: string`, `influences?: string[]`, `relationshipChain?: string[]`, `historicalExamples?: string[]`, `alternativeScenarios?: string[]`, `confidenceExplanation?: string`

---

### AITransparencyPanel (`components/ai/AITransparencyPanel.tsx`)
**Client component.** Primary AI transparency container.

**See Section 7.3 for complete prop interface.**

**Usage rule:** Import as `import { AITransparencyPanel } from "@/components/ai/AITransparencyPanel"`. Never inline the panel content directly.

---

## 10.2 Layout Components

### SiteHeader (`components/SiteHeader.tsx`)
Fixed top header. Contains: brand logo + name, 7 navigation tabs, AI Search link, alert bell, theme toggle.

### Sidebar (`components/Sidebar.tsx`)
Left rail navigation. Contains: module quick links, recent page history, pre-market pulse widget, AI tip of the day.

### Footer (`components/Footer.tsx`)
Full-width footer. Contains: brand column (logo + tagline + disclaimer), Product links (7 items), Company links (12 items in 2-column grid), copyright + investment disclaimer.

### NavigationProgress (`components/NavigationProgress.tsx`)
Thin progress bar at top of page during navigation transitions.

---

## 10.3 Card Components

### AIMarketWrapCard (`components/AIMarketWrapCard.tsx`)
Dashboard widget showing AI-synthesized market summary. Includes Sparkles icon, AI badge, summary text, and key bullets.

### SectorHeatmap (`components/SectorHeatmap.tsx`)
11-sector color grid. Each cell shows sector name and % change. Color-coded from deep red (heavy loss) through grey (unchanged) to deep green (strong gain).

### TopMoversSection (`components/TopMoversSection.tsx`)
Split view: top 5 gainers (emerald) and top 5 losers (rose) from Nifty 500. Each row: rank, ticker, name, change%.

### TrendingEvents (`components/TrendingEvents.tsx`)
List of 3-5 high-impact events with category badge, impact score, and 1-line AI summary.

### OpportunityRadar (`components/OpportunityRadar.tsx`)
Sidebar widget or full-page component. Shows opportunity cards with score circle, title, sector badge.

### DashboardHero (`components/DashboardHero.tsx`)
Session header with live Nifty 50 price, change, and India VIX. Market status indicator.

---

## 10.4 UI Primitives

### ScoreRing
SVG ring chart. Props: `score: number` (0-100), `size?: number` (default 80). Color determined by score band.

### KpiCard
Metric display card. Props: `label`, `value`, `sub`, `icon`, `color`, `border`.

### ConfidenceMeter
Horizontal bar showing confidence score with percentage label and level descriptor.

### Empty
Empty state component. Props: `msg: string`. Shows icon + message centered in container.

### Card
Generic content card wrapper. Props: `title?`, `action?`, `children`, `className?`. Renders standard card border + background.

---

## 10.5 Market Components

### PreMarketTab (`components/market/tabs/PreMarketTab.tsx`)
Complete pre-market data view. See Section 5.1 for full feature list.

### OverviewTab (`components/market/tabs/OverviewTab.tsx`)
Main market tab with session summary, AI wrap, movers, and sector heat.

### AfterMarketTab (`components/market/tabs/AfterMarketTab.tsx`)
Post-session summary tab.

---

## 10.6 Alert Components

### AlertProvider (`components/AlertProvider.tsx`)
Context provider for the global alert system.

### BreakingNewsAlert (`components/BreakingNewsAlert.tsx`)
Overlay banner for high-impact events (score ≥ 8.0). Shows for 10 seconds then auto-dismisses. Maximum one alert visible at a time.

---

## 10.7 Timeline Components

### Ripple Timeline
Horizontal timeline component showing event effects propagating over time. Renders using CSS flexbox; no canvas required.

### Event Timeline
Vertical timeline with dot/line connectors. Each entry: date (text-slate-500), title (text-white), description (text-slate-400). First entry uses violet dot; subsequent entries use slate dots.

---

# 11 BACKEND STANDARDS

## 11.1 Technology Stack

- **Framework:** FastAPI (Python 3.11+)
- **ASGI Server:** Uvicorn
- **Database:** PostgreSQL (via SQLAlchemy async)
- **Cache:** Redis (via aioredis)
- **Task Queue:** APScheduler for periodic tasks; Celery for heavy async tasks (optional)
- **AI:** OpenRouter API (free models only — see Section 7.4)
- **Market Data:** yfinance, NSE India API, custom scrapers
- **Package Manager:** uv (pyproject.toml)

## 11.2 API Naming Conventions

```
GET  /api/{resource}/              — List resources
GET  /api/{resource}/{id}          — Get single resource
POST /api/{resource}/              — Create resource
PUT  /api/{resource}/{id}          — Full update
PATCH /api/{resource}/{id}         — Partial update
DELETE /api/{resource}/{id}        — Delete resource
GET  /api/{resource}/{id}/{sub}    — Sub-resource
POST /api/{resource}/{id}/{action} — Action on resource
```

**Resource naming:** Plural nouns, hyphen-separated for multi-word resources (`/api/market-events/`, not `/api/marketEvents/`).

**ID convention:** Slugs preferred in URLs; numeric IDs accepted as fallback. Backend must accept both.

## 11.3 Folder Structure

```
apps/backend/
├── app/
│   ├── api/               — Route handlers (one file per resource)
│   │   ├── market.py
│   │   ├── events.py
│   │   ├── companies.py
│   │   ├── stories.py
│   │   ├── radar.py
│   │   ├── ripple.py
│   │   ├── search.py
│   │   ├── news.py
│   │   ├── sectors.py
│   │   ├── indices.py
│   │   ├── calendar.py
│   │   ├── dashboard.py
│   │   └── alerts.py
│   ├── core/
│   │   ├── config.py      — Environment configuration
│   │   ├── redis.py       — Redis client singleton
│   │   └── database.py    — Database connection
│   ├── db/
│   │   ├── base.py        — SQLAlchemy base + session
│   │   └── models/        — ORM models
│   ├── schemas/           — Pydantic response/request schemas
│   ├── services/
│   │   ├── ai_service.py  — All AI calls (OpenRouter, free models only)
│   │   ├── market_data.py — Market data fetching (yfinance, NSE)
│   │   ├── news_fetcher.py — News aggregation
│   │   └── ripple_engine.py — Dependency graph computation
│   ├── tasks/
│   │   └── daily_tasks.py — Scheduled background jobs
│   ├── scheduler/
│   │   └── scheduler.py   — APScheduler configuration
│   └── main.py            — FastAPI app, middleware, router registration
├── Dockerfile
├── pyproject.toml
└── .env.example
```

## 11.4 Caching Strategy

All external API calls must be cached. Cache keys are deterministic and documented per endpoint.

```python
# Cache duration conventions:
MARKET_HOURS_CACHE = 900      # 15 minutes (during market hours)
STANDARD_CACHE = 3600         # 1 hour
FII_DII_CACHE = 21600         # 6 hours
AI_WRAP_CACHE = 21600         # 6 hours (regenerated on high-impact events)
PREMARKET_CACHE = 900         # 15 minutes
EVENT_LIST_CACHE = 300        # 5 minutes
COMPANY_PROFILE_CACHE = 86400 # 24 hours
```

Cache pattern:
```python
cache_key = f"marketripple:{resource}:{identifier}:{params_hash}"
cached = await redis.get(cache_key)
if cached:
    return json.loads(cached)
data = await fetch_from_source()
await redis.setex(cache_key, TTL, json.dumps(data))
return data
```

**Graceful fallback:** When a cache miss occurs AND the source API fails, return the last cached value with a `data_stale: true` flag and `cached_at` timestamp. Never return an error when stale data is available.

## 11.5 Error Handling

All API endpoints must return consistent error shapes:

```python
# Success
{"data": {...}, "status": "ok", "cached_at": "2026-07-04T09:15:00Z"}

# Error
{"error": "Resource not found", "code": "NOT_FOUND", "status": "error"}

# Partial success (data with warnings)
{"data": {...}, "warnings": ["FII data unavailable"], "data_stale": true, 
 "cached_at": "...", "status": "partial"}
```

HTTP status codes:
- `200` — Success
- `400` — Client error (bad request, invalid params)
- `404` — Resource not found
- `422` — Validation error (Pydantic)
- `429` — Rate limited
- `500` — Server error (never expose stack traces in production)
- `503` — Upstream API unavailable (use when source data is completely unavailable)

## 11.6 Rate Limiting

Apply at the FastAPI middleware level using `slowapi` or equivalent:

```
AI Search queries: 10 per minute per IP
Market data endpoints: 60 per minute per IP
Event/company lookups: 120 per minute per IP
Static data endpoints: 300 per minute per IP
```

Rate limit headers must be included in all responses:
- `X-RateLimit-Limit`
- `X-RateLimit-Remaining`
- `X-RateLimit-Reset`

## 11.7 Validation

All request parameters must be validated with Pydantic:

```python
class EventListParams(BaseModel):
    category: Optional[EventCategory] = None
    sector: Optional[str] = None
    min_score: float = Field(0.0, ge=0.0, le=10.0)
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    page: int = Field(1, ge=1)
    per_page: int = Field(20, ge=1, le=100)
```

Validators must reject: SQL injection patterns, excessively long strings (> 500 chars for query params), invalid date ranges (future dates where not applicable).

## 11.8 OpenRouter Integration (Free AI Only)

**Location:** `apps/backend/app/services/ai_service.py`

**Permanent constraint:** Only free-tier models may be used. This is enforced at the service layer, not the API layer.

```python
class AIService:
    FREE_MODELS = [
        "meta-llama/llama-3.1-8b-instruct:free",
        "google/gemma-2-9b-it:free",
        "mistralai/mistral-7b-instruct:free",
        # Update list as OpenRouter free offerings change
    ]
    
    def _get_model(self) -> str:
        # Always use first available free model
        # Never use a model not in FREE_MODELS list
        return self.FREE_MODELS[0]
```

All AI calls must:
- Use the `ai_service.py` singleton — never call OpenRouter directly from route handlers
- Handle model unavailability gracefully (fallback to next model in list)
- Log token usage for monitoring
- Implement exponential backoff on rate limit responses
- Set maximum token limits appropriate to each task type

## 11.9 Logging

Log structure (JSON):
```json
{
  "timestamp": "2026-07-04T09:15:00.000Z",
  "level": "INFO|WARN|ERROR",
  "service": "marketripple-backend",
  "endpoint": "/api/events/rbi-rate-hike",
  "method": "GET",
  "status_code": 200,
  "duration_ms": 45,
  "cache_hit": true,
  "user_ip": "hashed",
  "event_id": "evt_12345"
}
```

Never log: raw IP addresses (hash them), API keys, user queries verbatim (hash or truncate to 50 chars).

---

# 12 FRONTEND STANDARDS

## 12.1 Technology Stack

- **Framework:** Next.js 15 (App Router)
- **Language:** TypeScript (strict mode, no `any` without explicit justification)
- **Styling:** Tailwind CSS v3 (no CSS modules, no styled-components)
- **Icons:** lucide-react exclusively (no emoji, no custom SVG except brand mark)
- **Charts:** Recharts
- **Graphs:** ReactFlow (for dependency graph visualization)
- **Animation:** Framer Motion (for complex animations); CSS transitions (for simple state changes)
- **Package Manager:** npm (package-lock.json committed)

## 12.2 Component Organization

```
apps/web/
├── app/                     — Next.js App Router pages
│   ├── (knowledge)/         — Route group: knowledge center pages
│   ├── events/
│   ├── companies/
│   ├── stories/
│   ├── radar/
│   ├── ripple/
│   ├── ai-search/
│   ├── globals.css
│   ├── layout.tsx            — Root layout with Sidebar, Footer
│   ├── page.tsx              — Market Intelligence dashboard
│   └── loading.tsx           — Global loading skeleton
├── components/
│   ├── ai/                  — AI Transparency Framework components
│   │   ├── AIDisclaimer.tsx
│   │   ├── AITransparencyPanel.tsx
│   │   ├── ConfidenceBadge.tsx
│   │   ├── EvidenceCard.tsx
│   │   ├── MethodologyDrawer.tsx
│   │   └── WhyAmISeeingThis.tsx
│   ├── market/
│   │   └── tabs/            — Dashboard tab components
│   ├── ui/                  — Generic UI primitives (future)
│   ├── AlertProvider.tsx
│   ├── BreakingNewsAlert.tsx
│   ├── DashboardHero.tsx
│   ├── FloatingAISearch.tsx
│   ├── Footer.tsx
│   ├── NavLoadingProvider.tsx
│   ├── NavigationProgress.tsx
│   ├── OpportunityRadar.tsx
│   ├── SectorHeatmap.tsx
│   ├── Sidebar.tsx
│   ├── SiteHeader.tsx
│   ├── TopMoversSection.tsx
│   ├── TrackPageVisit.tsx
│   └── TrendingEvents.tsx
└── public/
    └── (static assets)
```

## 12.3 Server vs. Client Components

**Default to Server Components.** Only use `"use client"` when:
- The component uses React state (`useState`, `useReducer`)
- The component uses React effects (`useEffect`)
- The component uses browser APIs (`window`, `document`, `localStorage`)
- The component uses event listeners
- The component uses third-party libraries that require client context

**Client component rule:** When a page is primarily a server component but needs one interactive section, extract the interactive section into a `ClientXxx` component and import it. Do not mark the entire page as `"use client"` for one interactive element.

**Metadata rule:** Pages marked `"use client"` cannot export `metadata`. Create a co-located `layout.tsx` that exports the metadata instead.

## 12.4 Reusable Hooks

Document custom hooks here as they are created:

```typescript
// useCountdown — returns seconds remaining until target time (IST)
function useCountdown(targetHour: number, targetMinute: number): number

// useMarketStatus — returns current market session status
function useMarketStatus(): { isOpen: boolean; status: string; timeIST: string }

// useBreakingAlert — subscribes to breaking news SSE stream
function useBreakingAlert(): { alert: Alert | null; dismiss: () => void }
```

All hooks must:
- Be named `use{Purpose}` (React convention)
- Live in `apps/web/hooks/` directory
- Export TypeScript types for their return values
- Handle cleanup in useEffect return functions

## 12.5 State Management

MarketRipple does not use a global state management library (no Redux, Zustand, Jotai). State is managed at:

- **URL state:** Search filters, active tabs, selected items — use URL params via `useSearchParams`
- **Local state:** Component-specific UI state — use `useState`
- **Server state:** Data fetched from backend — use Next.js server components + `fetch`; for client-side data, use `useState` + `useEffect` with manual loading states
- **Context:** Cross-cutting app concerns (alert system, navigation loading) — use React Context via `Provider` components

When the same data is needed in multiple sibling components, lift state to the nearest common ancestor. Do not create global stores for data that can be re-fetched.

## 12.6 Loading States

Every data-fetching component must implement loading states:

**Skeleton approach (preferred):**
```tsx
if (loading) return <SkeletonCard />;
```

**Skeleton implementation:** Use `animate-pulse` on placeholder divs that match the rough shape of the content they will replace. Skeleton shapes should have the same height/width as the content.

**Suspense boundaries:** Use Next.js Suspense with `loading.tsx` files for route-level loading states. Component-level loading uses local state.

**Never:** Show a spinning loader in the center of a full page without a skeleton. The layout shift when content loads is jarring.

## 12.7 Error States

Every data-fetching operation must handle errors:

```tsx
if (error) return (
  <div className="flex flex-col items-center justify-center py-20">
    <AlertCircle className="h-8 w-8 text-rose-500 mb-3" />
    <p className="text-sm font-medium text-slate-400">{error}</p>
    <button onClick={retry} className="mt-4 text-sm text-sky-400 hover:text-sky-300">
      Try again
    </button>
  </div>
);
```

Error messages must:
- Be human-readable (no HTTP status codes visible to users)
- Suggest a recovery action
- Not expose technical details (stack traces, internal error messages)

---

# 13 PERFORMANCE STANDARDS

## 13.1 Core Web Vitals Targets

```
LCP (Largest Contentful Paint): < 2.5s
FID (First Input Delay):         < 100ms
CLS (Cumulative Layout Shift):   < 0.1
TTFB (Time to First Byte):       < 800ms
```

These targets are measured on a simulated 4G connection (10Mbps, 40ms RTT) for mobile.

## 13.2 Image Optimization

- Use Next.js `<Image>` component for all images (automatic WebP conversion, lazy loading, size optimization)
- Specify `width` and `height` on all `<Image>` components to prevent CLS
- Use `priority` prop on above-the-fold images (hero images, first viewport content)
- Serve images from Next.js public folder or CDN; never hotlink external images
- Maximum image size: 200KB for content images, 50KB for icons/logos

## 13.3 Code Splitting

- Next.js App Router handles route-level code splitting automatically
- Use `dynamic()` import for: large chart libraries (Recharts, ReactFlow), heavy modals/drawers, components used only in specific tab content
- Never import chart libraries at the page level if they are only used in one tab; defer with `dynamic()`

```typescript
const ReactFlow = dynamic(() => import("reactflow").then(m => m.default), { ssr: false });
```

## 13.4 Caching Strategy (Frontend)

```typescript
// Next.js fetch cache (server components)
fetch(url, { next: { revalidate: 300 } })   // 5-minute revalidation
fetch(url, { cache: "no-store" })            // No cache (real-time data)
fetch(url, { next: { revalidate: 3600 } })  // 1-hour revalidation (semi-static)
```

Static data (company lists, sector definitions) should be statically generated at build time using `generateStaticParams`.

## 13.5 Bundle Optimization

- Monitor bundle size on every merge to main
- Target: < 250KB JavaScript (gzipped) for the initial route bundle
- Use `@next/bundle-analyzer` to identify large dependencies
- Prefer tree-shakeable imports: `import { Bot } from "lucide-react"`, not `import * as Icons from "lucide-react"`

## 13.6 Streaming

Use Next.js streaming for pages with multiple independent data sources:

```tsx
// Page component
export default async function EventPage({ params }) {
  return (
    <>
      <EventHeader params={params} />   {/* loads first */}
      <Suspense fallback={<AnalysisSkeleton />}>
        <EventAnalysis id={params.id} />  {/* streams in */}
      </Suspense>
      <Suspense fallback={<CompaniesSkeleton />}>
        <EventCompanies id={params.id} />  {/* streams in */}
      </Suspense>
    </>
  );
}
```

---

# 14 SECURITY

## 14.1 Authentication

MarketRipple currently operates without user authentication. All pages are publicly accessible. When authentication is added (Phase 3 roadmap), it must use:

- **Provider:** NextAuth.js (App Router compatible)
- **Strategy:** OAuth 2.0 (Google, GitHub) + magic link email
- **Session:** JWT stored in httpOnly cookie, 7-day expiry
- **No passwords stored** — passwordless only

## 14.2 API Protection

Even without user authentication, all API endpoints must be protected against abuse:

- **Rate limiting:** See Section 11.6
- **CORS:** Only allow requests from the MarketRipple frontend domain and localhost (development)
- **Input validation:** All parameters validated via Pydantic (see Section 11.7)
- **SQL injection:** Use SQLAlchemy ORM exclusively; never construct raw SQL strings
- **XSS:** Never render user input as HTML. Use React's default text rendering which escapes content
- **SSRF:** Never make HTTP requests to user-supplied URLs from the backend; only fetch from approved domains

## 14.3 Secrets Management

**Allowed:** Environment variables via `.env` files. Never commit `.env` files.

**Required `.env.example` format:**
```
OPENROUTER_API_KEY=your-key-here
DATABASE_URL=postgresql://user:pass@localhost/marketripple
REDIS_URL=redis://localhost:6379
NSE_BASE_URL=https://www.nseindia.com
NEXT_PUBLIC_API_URL=http://localhost:8000
```

**Never in code:** API keys, connection strings, passwords, tokens. If a secret is found in code, it must be rotated immediately.

## 14.4 Content Security Policy

For Artifact/embedded views:
- Block all external CDN scripts
- Block all external stylesheets
- Block all remote image sources (use data URIs)
- Block fetch/XHR to external domains

For main application:
- Allow scripts from Next.js origin
- Allow styles from Next.js origin + Tailwind CDN (if used)
- Allow images from configured CDN origins

---

# 15 ACCESSIBILITY

## 15.1 WCAG AA Compliance

MarketRipple targets WCAG 2.1 Level AA. Every new feature must pass the following checks before merging:

- Color contrast ratio ≥ 4.5:1 for normal text
- Color contrast ratio ≥ 3:1 for large text and UI components
- All interactive elements are keyboard accessible
- No color as the sole means of conveying information
- All non-text content has text alternatives

## 15.2 ARIA Labels

Rules:
- All icon-only buttons must have `aria-label` describing the action
- All icon decorations must have `aria-hidden="true"`
- Modals and drawers must have `role="dialog"`, `aria-modal="true"`, `aria-label`
- Tabs must use `role="tab"`, `aria-selected`, `aria-controls`
- Tab panels must use `role="tabpanel"`, `aria-labelledby`
- Lists of navigation items must use `role="list"` on `<ul>` and `role="listitem"` on `<li>`
- Form inputs must have visible labels or `aria-label`

## 15.3 Keyboard Navigation

- All interactive elements must be reachable via Tab key
- Tab order must follow visual reading order (top-to-bottom, left-to-right)
- Modal/drawer: focus must be trapped inside while open; restored to trigger on close
- Escape key must close all modals, drawers, and dropdowns
- Enter/Space must activate buttons and links
- Arrow keys must navigate within tab bars and menu lists

## 15.4 Screen Readers

- Page must have a single `<h1>` per route
- Heading hierarchy must be logical: h1 → h2 → h3 (never skip levels)
- Use semantic HTML: `<main>`, `<nav>`, `<aside>`, `<section>`, `<article>`, `<header>`, `<footer>`
- `<main>` must have `id="main-content"` for skip links
- Dynamic content updates must use `aria-live="polite"` for non-urgent updates, `aria-live="assertive"` for alerts

## 15.5 Motion and Animation

- All animations must be suppressible via `prefers-reduced-motion`
- Implementation pattern:
```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
```

---

# 16 SEO

## 16.1 Metadata Requirements

Every page must export a `Metadata` object:

```typescript
export const metadata: Metadata = {
  title: "Page Title — MarketRipple",
  description: "Specific, accurate description of this page's content. 150-160 characters.",
  openGraph: {
    type: "website",
    siteName: "MarketRipple",
    title: "Page Title — MarketRipple",
    description: "Open Graph description. Can be same as meta description.",
    images: [{ url: "/og-image.png", width: 1200, height: 630 }],
  },
  twitter: {
    card: "summary_large_image",
    title: "Page Title — MarketRipple",
    description: "Twitter card description.",
  },
};
```

**Title formula:** `[Page-specific title] — MarketRipple`

**Prohibited:** Generic titles ("Home", "Page 1"), duplicate titles across pages, titles over 60 characters.

## 16.2 Canonical URLs

Every page must have a canonical URL to prevent duplicate content:

```typescript
export const metadata: Metadata = {
  alternates: {
    canonical: "https://marketripple.in/events/rbi-rate-hike-june-2025",
  },
};
```

Event and company pages accessible via both slug and numeric ID must canonicalize to the slug URL.

## 16.3 Structured Data

For event pages, use JSON-LD `NewsArticle` schema:
```json
{
  "@context": "https://schema.org",
  "@type": "NewsArticle",
  "headline": "RBI Raises Repo Rate by 50 bps",
  "datePublished": "2025-06-04",
  "author": { "@type": "Organization", "name": "MarketRipple" },
  "publisher": { "@type": "Organization", "name": "MarketRipple" }
}
```

For FAQ page, use `FAQPage` schema. For breadcrumbs, use `BreadcrumbList` schema.

## 16.4 Sitemap

Generate `sitemap.xml` dynamically via Next.js:
- Static routes: all 7 module index pages + all 10 knowledge pages
- Dynamic routes: all event slugs, company symbols, story slugs, opportunity slugs
- Update frequency: daily for static, on-change for dynamic
- Priority: dashboard (1.0), module indexes (0.8), entity pages (0.6), knowledge pages (0.5)

## 16.5 robots.txt

```
User-agent: *
Allow: /

Sitemap: https://marketripple.in/sitemap.xml
```

Only disallow: `/api/*` (backend API routes), `/_next/*` (Next.js internal).

---

# 17 QA CHECKLIST

## 17.1 Visual QA

For every new component or page:
- [ ] Renders correctly at 375px (iPhone SE)
- [ ] Renders correctly at 768px (tablet)
- [ ] Renders correctly at 1280px (desktop)
- [ ] Renders correctly at 1600px (wide desktop)
- [ ] No horizontal scroll on any viewport
- [ ] Dark theme colors are consistent with design system
- [ ] No emoji visible anywhere (lucide-react icons only)
- [ ] Loading skeleton matches content shape
- [ ] Empty state renders with appropriate icon and message
- [ ] Error state renders with recovery action

## 17.2 Functional QA

- [ ] All API calls succeed with real data
- [ ] All API calls degrade gracefully when backend is unavailable
- [ ] Loading states show during data fetch
- [ ] Tab navigation works correctly
- [ ] All internal links navigate to correct destinations
- [ ] All external links open in new tab
- [ ] Filters/search update results correctly
- [ ] Pagination or "Load More" works correctly
- [ ] Real-time data refreshes without full page reload

## 17.3 Accessibility QA

- [ ] All icon-only buttons have aria-label
- [ ] All images have alt text or aria-hidden
- [ ] Modals trap focus correctly
- [ ] Escape key closes modals and drawers
- [ ] Tab order is logical and complete
- [ ] No color-only information conveyance
- [ ] Screen reader announces dynamic content changes
- [ ] Keyboard-navigable without mouse

## 17.4 Performance QA

- [ ] LCP < 2.5s on simulated 4G
- [ ] No layout shift from async data loading
- [ ] Chart libraries loaded lazily (not in initial bundle)
- [ ] Images use Next.js `<Image>` component
- [ ] No unnecessary re-renders visible in React DevTools

## 17.5 AI QA

For every feature with AI-generated content:
- [ ] `AITransparencyPanel` is rendered
- [ ] `MethodologyDrawer` opens when "View Methodology" is clicked
- [ ] `ConfidenceBadge` is visible on the AI content header
- [ ] At least one `EvidenceCard` is present
- [ ] `WhyAmISeeingThis` modal opens correctly
- [ ] `AIDisclaimer` is rendered at the bottom of AI content
- [ ] Confidence score is a real value (not hardcoded)
- [ ] Reasoning text is specific to the entity, not generic

## 17.6 TypeScript QA

- [ ] `npx tsc --noEmit --skipLibCheck` exits with code 0
- [ ] No `any` types without `// eslint-disable-next-line` justification comment
- [ ] All exported components have complete prop interfaces
- [ ] No type assertions (`as Type`) without justification

---

# 18 PRODUCT ROADMAP

## 18.1 Phase 1 — Core Platform (Complete)

**Status:** Live

**Features delivered:**
- Market Intelligence dashboard with Pre-Market, Overview, After-Market tabs
- Events module with full AI enrichment pipeline
- Company Intelligence pages
- Stories module with AI-synthesized themes
- Opportunity Radar with scored opportunities
- Ripple Intelligence with dependency graph visualization
- AI Search with natural language query interface
- Breaking News Alert system
- Economic Calendar
- Commodities & Energy page
- Knowledge & Trust Center (10 pages)
- AI Transparency Framework (6 components)
- Footer with complete company links

## 18.2 Phase 2 — Intelligence Enhancement (Q3-Q4 2026)

**Target:** September–December 2026

**Pre-Market Enhancements:**
- FII/DII Net Flow Card (real data from NSE India API)
- Bank Nifty Futures alongside Nifty Futures
- Market Opening Countdown Timer
- Expected Opening Range (computed from Gift Nifty premium + VIX)
- Put-Call Ratio with interpretation
- Indian ADRs (Infosys, Wipro, HDFC Bank, ICICI Bank) with premium/discount
- Silver commodity addition
- Real Market Breadth (Advances/Declines from actual data)
- Today's Scheduled Events card
- Global Sentiment Score

**AI Transparency Integration:**
- `AITransparencyPanel` on Dashboard AI Brief
- `AITransparencyPanel` on Stories pages
- `AITransparencyPanel` on AI Search responses
- `AITransparencyPanel` on Company Intelligence pages

**Events Enhancement:**
- Improved historical similarity with better embedding models
- Event clustering: surface related events automatically
- Sector-level event aggregation view

**Data Quality:**
- Real advance/decline data from BSE/NSE
- Improved FII/DII data freshness
- Automated data quality monitoring and alerts

## 18.3 Phase 3 — Premium Intelligence (2027 H1)

**Personalization:**
- User accounts (OAuth, no passwords)
- Watchlist: track specific companies and events
- Custom Alerts: trigger on specific event categories, impact scores, companies
- Portfolio Exposure: upload portfolio holdings, see event exposure automatically

**Advanced AI:**
- Portfolio-level ripple analysis: how a specific portfolio is exposed to current events
- Personalized AI Wrap: morning brief tailored to watchlist and portfolio
- Historical backtesting: how would a thesis have performed in 2019-2025?

**Professional Tools:**
- API access (authenticated, rate-limited, documented)
- PDF report export (event analysis, opportunity summary, portfolio exposure)
- Multi-entity comparison: compare event exposure across 3-5 companies side by side

## 18.4 Phase 4 — Market Intelligence Platform (2027 H2 and beyond)

**Mobile Applications:**
- Native iOS app
- Native Android app
- Near-parity with web experience
- Push notifications for breaking alerts and custom triggers

**Premium Intelligence Tier:**
- Deeper quantitative models
- Options market intelligence (PCR trends, max pain, open interest analysis)
- Sector rotation signals
- Intraday ripple tracking

**Partnerships:**
- Integration with major Indian brokers (Zerodha, Angel One, HDFC Securities)
- Data partnerships for proprietary datasets
- Research firm collaborations for professional content

**Future Ideas (Not Yet Scoped):**
- Voice interface ("Hey MarketRipple, what happened in markets today?")
- WhatsApp integration for daily briefings
- Community features: investment thesis sharing, user-generated event commentary
- Global expansion: similar intelligence for US, UK, Southeast Asian markets

---

# 19 CODING STANDARDS

## 19.1 TypeScript

**Strict mode is mandatory.** `tsconfig.json` must include:
```json
{
  "compilerOptions": {
    "strict": true,
    "noImplicitAny": true,
    "strictNullChecks": true,
    "noUncheckedIndexedAccess": true
  }
}
```

**No `any` policy:**
- Never use `any` in a type annotation
- `as any` is only acceptable for legacy third-party library workarounds; must have a comment explaining why
- When a type cannot be determined, use `unknown` and narrow it with type guards

**Type naming:**
- Interfaces: PascalCase, no `I` prefix (`EventDetail`, not `IEventDetail`)
- Types: PascalCase (`ConfidenceLevel`)
- Enums: PascalCase for enum name, PascalCase for values
- Generics: single uppercase letter for simple (`T`, `K`, `V`) or descriptive PascalCase (`TItem`)

## 19.2 Naming Conventions

**Files:**
```
components/SectorHeatmap.tsx   — PascalCase for components
hooks/useMarketStatus.ts       — camelCase with use prefix for hooks
app/events/[id]/page.tsx       — Next.js App Router convention (lowercase)
services/ai_service.py         — snake_case for Python
```

**Variables and functions:**
```typescript
const marketData = ...          // camelCase for variables
function getConfidenceLevel()   // camelCase for functions
const API_BASE_URL = ...        // SCREAMING_SNAKE_CASE for constants
interface EventDetailProps      // PascalCase for interfaces
```

**CSS classes:** Tailwind utility classes only. No custom CSS class names in component files. Custom CSS only in `globals.css` for animations.

## 19.3 Component Structure

Every React component file must follow this order:
1. Imports (third-party libraries, then internal imports)
2. Type/interface declarations
3. Constants (module-level data, lookup tables)
4. Helper functions (pure functions, no side effects)
5. Sub-components (if needed, defined before the primary component)
6. Primary exported component
7. No default exports — use named exports only

```typescript
// ── Imports ────────────────────────────────────────────────────────────────
import { useState } from "react";
import { Bot } from "lucide-react";
import type { Metadata } from "next";

// ── Types ──────────────────────────────────────────────────────────────────
interface ConfidenceBadgeProps {
  score: number;
  size?: "sm" | "md" | "lg";
}

// ── Constants ──────────────────────────────────────────────────────────────
const LEVEL_CONFIG = { ... };

// ── Helpers ────────────────────────────────────────────────────────────────
function getConfidenceLevel(score: number): ConfidenceLevel { ... }

// ── Component ──────────────────────────────────────────────────────────────
export function ConfidenceBadge({ score, size = "md" }: ConfidenceBadgeProps) {
  ...
}
```

## 19.4 Comments Policy

Write zero comments by default. Add a comment only when the **why** is non-obvious:
- A hidden constraint that would surprise a reader
- A workaround for a specific external API bug
- An invariant that must hold for correctness but isn't visible from the code

**Never write:**
- Comments explaining what code does (the code should be self-documenting)
- Comments referencing tasks, PRs, or ticket numbers
- Section divider comments except at the top-level component section boundaries (where they aid navigation in long files)

**Permitted section separators** (in long files only):
```typescript
// ── Types ──────────────────────────────────────────────────────────────────
// ── Constants ──────────────────────────────────────────────────────────────
// ── Helpers ────────────────────────────────────────────────────────────────
```

## 19.5 Import Organization

Order imports:
1. React/Next.js core
2. Third-party libraries (alphabetical)
3. Internal `@/components/...` imports (alphabetical)
4. Internal `@/hooks/...` imports
5. Internal `@/lib/...` imports
6. Relative imports
7. Type-only imports (`import type { ... }`)

Blank line between each group.

## 19.6 Folder Organization Rules

- Feature components live in `components/` with a flat or one-level-deep structure
- AI transparency components are the only components with their own subdirectory (`components/ai/`)
- Market tab components have their own subdirectory (`components/market/tabs/`)
- App Router pages live in `app/` following Next.js conventions
- Shared utilities live in `lib/` (not yet created; create when 3+ utilities exist)
- Custom hooks live in `hooks/` (not yet created; create when 3+ hooks exist)

## 19.7 Git Conventions

**Branch naming:** `feat/description-of-feature`, `fix/description-of-bug`, `docs/description-of-change`

**Commit messages:**
```
feat: add FII/DII card to PreMarketTab
fix: correct confidence score calculation for low-evidence events
docs: update MARKETRIPPLE_MASTER_SPEC with Phase 2 features
refactor: extract ScoreRing from EventExplorerPage to shared component
```

**PR requirements before merge:**
- Zero TypeScript errors
- Visual QA completed on 375px + 1280px
- AI QA checklist completed if AI content is involved
- At least one reviewer approval

---

# 20 PRODUCT REVIEW CHECKLIST

Every new feature, before it is considered complete, must answer all 11 questions in this checklist. If any answer is "No" or "Not applicable" without a documented justification, the feature must be revised before shipping.

This checklist applies to every entity detail page, every AI-generated content block, and every intelligence output surface.

---

## Question 1: What Happened?

**The requirement:** The page must clearly state the primary fact. What is the event, opportunity, company situation, or story?

**Evaluation criteria:**
- Is there a clear, specific headline or title?
- Is there a 1-3 sentence plain-language description of what happened?
- Is the date/timing of the event or analysis clear?
- Is the source or origin of the information shown?

**If missing:** The feature is incomplete. Add a clear event description or entity summary before anything else on the page.

---

## Question 2: Why?

**The requirement:** The page must explain the causal context. Why did this happen? What caused this event, trend, or opportunity?

**Evaluation criteria:**
- Does the page explain the antecedents (what led to this)?
- Is the causal chain visible (event A caused B, which caused C)?
- For AI-generated content: is the AI reasoning section present and specific?

**If missing:** Add a "Why it happened" or "Context" section with 2-4 sentences of causal explanation before the impact analysis.

---

## Question 3: Who Is Affected?

**The requirement:** Every page must show who is affected by the event or situation — which companies, which sectors, which investor types.

**Evaluation criteria:**
- Is there a list of beneficiary companies with reasons?
- Is there a list of risk-exposed companies with reasons?
- Is there a list of affected sectors?
- Are the lists ranked by impact score (not alphabetical)?

**If missing:** The Companies and Sectors sections are mandatory on event and opportunity pages. If data is not yet available (enrichment in progress), show the enrichment-in-progress state.

---

## Question 4: Evidence?

**The requirement:** Every AI conclusion must be backed by visible, dated, typed evidence.

**Evaluation criteria:**
- Are at least one `EvidenceCard` components present?
- Is each evidence item dated?
- Does each evidence item link to the primary source where available?
- Are evidence types correctly classified (government, filing, earnings, indicator, news, historical, company, global)?

**If missing:** The feature violates Principle 2.2 (Evidence Before Conclusions). Do not ship without evidence cards.

---

## Question 5: Risks?

**The requirement:** Every opportunity or investment thesis must explicitly enumerate the risks that could invalidate it.

**Evaluation criteria:**
- Is there a risk section with at least 2 specific risks?
- Are risks categorized by type and severity?
- Is there an explicit statement of what would invalidate the analysis (the "What could prove this wrong?" question)?

**If missing:** Add a Risk Framework section (see Section 6.8). Generic risks ("markets are volatile") are not acceptable — risks must be specific to the entity and situation.

---

## Question 6: Growth Drivers?

**The requirement:** For opportunity and company intelligence pages, the structural drivers of the opportunity must be visible.

**Evaluation criteria:**
- Are multi-year structural tailwinds identified (not just short-term catalysts)?
- Are growth drivers distinguished from market catalysts by time horizon?
- Are 2-4 growth drivers shown?

**Applicability:** Required on Stories, Opportunity Radar, Company pages. Not required on individual event pages (where Market Catalysts suffice).

---

## Question 7: Opportunity Lifecycle?

**The requirement:** The user must be able to understand where in the opportunity's development arc the situation currently sits.

**Evaluation criteria:**
- Is the lifecycle stage (Emerging, Building, Peak, Maturing, Resolving) shown?
- Is the stage justified by the current evidence?
- Has the stage changed recently, and is that change reflected?

**Applicability:** Required on Opportunity Radar and Stories. Optional on other pages.

---

## Question 8: Monitoring Checklist?

**The requirement:** Users must know what to watch to track whether the thesis is playing out or breaking down.

**Evaluation criteria:**
- Are there specific, observable confirmation signals?
- Are there specific, observable warning signals?
- Are signals verifiable (not vague "watch markets")?

**Applicability:** Required on Opportunity Radar and Stories. Recommended on Company pages.

---

## Question 9: Expected Evolution?

**The requirement:** Users must understand how the situation is expected to develop over the next 3, 6, and 12 months.

**Evaluation criteria:**
- Are there forward-looking waypoints at 3 months, 6 months, and 12 months?
- Does each waypoint include a key indicator to watch?
- Is the expected evolution distinguished from the three-scenario analysis?

**Applicability:** Required on Stories and Opportunity Radar. Recommended on Events.

---

## Question 10: Confidence?

**The requirement:** Every AI output must carry a confidence score that is specific, justified, and visible.

**Evaluation criteria:**
- Is the `ConfidenceBadge` component rendered?
- Is the score a real computed value (not hardcoded)?
- Does the `MethodologyDrawer` explain how the confidence was calculated?
- Does the confidence score change when evidence changes?

**If missing:** This is a mandatory requirement. No AI output ships without a confidence score.

---

## Question 11: Transparency?

**The requirement:** The complete AI Transparency Framework must be deployed on every AI-generated content surface.

**Evaluation criteria:**
- [ ] `AITransparencyPanel` is rendered with real data
- [ ] `ConfidenceBadge` is visible on the AI content header
- [ ] `MethodologyDrawer` opens when "View Methodology" is clicked
- [ ] Reasoning section is specific to the entity (not generic)
- [ ] At least one `EvidenceCard` is present
- [ ] `WhyAmISeeingThis` modal opens and contains relevant content
- [ ] `AIDisclaimer` is rendered at the bottom of the AI content block
- [ ] The disclaimer links to `/legal#disclaimer`

**If any item is unchecked:** The feature must not be merged. Incomplete AI transparency is not a "nice to have" — it is a product requirement and a trust commitment.

---

## Checklist Summary Table

| Question | Event Pages | Company Pages | Stories | Opp. Radar | AI Search | Dashboard |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| What Happened? | ✅ Required | ✅ Required | ✅ Required | ✅ Required | ✅ Required | ✅ Required |
| Why? | ✅ Required | ✅ Required | ✅ Required | ✅ Required | ✅ Required | ✅ Required |
| Who Is Affected? | ✅ Required | ✅ Required | ✅ Required | ✅ Required | ✅ Required | — |
| Evidence? | ✅ Required | ✅ Required | ✅ Required | ✅ Required | ✅ Required | ✅ Required |
| Risks? | ✅ Required | ✅ Required | ✅ Required | ✅ Required | ✅ Recommended | — |
| Growth Drivers? | — | ✅ Recommended | ✅ Required | ✅ Required | — | — |
| Opportunity Lifecycle? | — | — | ✅ Required | ✅ Required | — | — |
| Monitoring Checklist? | — | ✅ Recommended | ✅ Required | ✅ Required | — | — |
| Expected Evolution? | ✅ Recommended | ✅ Recommended | ✅ Required | ✅ Required | — | — |
| Confidence? | ✅ Required | ✅ Required | ✅ Required | ✅ Required | ✅ Required | ✅ Required |
| Transparency? | ✅ Required | ✅ Required | ✅ Required | ✅ Required | ✅ Required | ✅ Required |

---

*End of MARKETRIPPLE MASTER SPECIFICATION v1.0*

*This document is maintained by the MarketRipple product team. Amendments require written proposal, team review, and version increment. All implementation work must cite the relevant section of this spec.*

*Last updated: July 2026*
