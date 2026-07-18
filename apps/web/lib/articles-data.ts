/**
 * MarketRipple Learn Articles — longer-form investor education content.
 * Single source of truth for /learn/articles and /learn/articles/[slug].
 */

export interface Article {
  slug: string;
  title: string;
  category: "Market Mechanics" | "Macro & Policy" | "Investing Framework";
  summary: string;
  readTime: string;
  body: { heading?: string; paragraphs: string[] }[];
  relatedArticles?: string[];
  relatedGlossary?: string[];  // glossary slugs
}

export const ARTICLES: Article[] = [
  {
    slug: "how-ripple-effects-work",
    title: "How Ripple Effects Work: From a Single Event to the Whole Market",
    category: "Market Mechanics",
    summary: "Markets rarely move for one clean reason. Here's how a single event — a crude oil spike, a rate decision, an earnings surprise — spreads through sectors, companies, and macro indicators, and why tracing that chain matters more than reading the headline alone.",
    readTime: "6 min",
    body: [
      {
        paragraphs: [
          "Financial news tends to present events as isolated facts: 'Crude oil rises 3%.' 'RBI holds rates.' 'A large IT company beats earnings estimates.' Each headline reads like a complete story. But markets don't actually work that way — every event sits at the start of a chain of consequences, and the headline is only the first link.",
          "Understanding that chain — what MarketRipple calls a ripple effect — is often more useful than the headline itself, because the second- and third-order consequences are frequently where the real, tradeable insight lives.",
        ],
      },
      {
        heading: "A worked example: the crude oil chain",
        paragraphs: [
          "Take a Middle East supply disruption that pushes Brent crude up sharply in a single session. The first, most obvious layer of impact is direct: oil marketing companies (OMCs) face margin pressure since they can't always pass on higher input costs immediately, and airlines see fuel costs — one of their largest expenses — jump.",
          "The second layer is less obvious but often more important. Higher crude prices widen India's import bill (India imports roughly 85% of its crude oil needs), which pressures the rupee. A weaker rupee, in turn, raises the cost of all dollar-denominated imports, adding to inflation. That inflation risk feeds into a third layer: it can influence the RBI's rate-decision calculus at the next MPC meeting, since sustained above-target inflation limits the central bank's room to cut rates even if growth is slowing.",
          "None of this appears in the original headline. 'Crude oil rises 3%' says nothing about rupee pressure or RBI policy risk — but tracing the chain from event to sector to macro indicator is exactly how professional analysts translate a single data point into an investable view.",
        ],
      },
      {
        heading: "Why the chain matters more than the headline",
        paragraphs: [
          "The first-order impact of most events is usually already priced in almost instantly — professional traders react to headline news in seconds. The second- and third-order effects, by contrast, take longer to become obvious and are where genuine analytical edge tends to live, because fewer people are tracking them in real time.",
          "This is also why MarketRipple's Ripple Engine exists: to make that multi-layer chain visible and explicit, rather than requiring you to mentally reconstruct it from a scattered stream of headlines. Every ripple map traces real, evidenced relationships between an event and its downstream sectors, companies, and macro indicators — not a generic template of 'what usually happens.'",
        ],
      },
      {
        heading: "A caution: correlation isn't causation, and templates aren't analysis",
        paragraphs: [
          "Not every plausible-sounding chain is real. A genuinely rigorous ripple analysis requires real evidence connecting each link — not just 'these two things are often mentioned together.' This is why MarketRipple explicitly labels any ripple map that falls back to an illustrative pattern (used only when a genuine event-specific analysis hasn't been generated yet) rather than presenting a generic template as if it were bespoke analysis of that specific event.",
          "The discipline of asking 'is this a real, evidenced connection, or just a plausible-sounding story?' is the single most important habit in reading any ripple analysis — from MarketRipple or anywhere else.",
        ],
      },
    ],
    relatedArticles: ["understanding-sector-rotation"],
    relatedGlossary: ["ripple-effect", "impact-score", "sector-rotation"],
  },
  {
    slug: "understanding-sector-rotation",
    title: "Understanding Sector Rotation in Indian Markets",
    category: "Market Mechanics",
    summary: "Why different sectors take turns leading the market, what typically drives the handoff between them, and how to read sector-level strength as a signal in its own right — separate from the headline index move.",
    readTime: "5 min",
    body: [
      {
        paragraphs: [
          "On any given day, the Nifty 50's headline move can hide a lot. The index might be flat while banking stocks rally 2% and IT stocks fall 1.5% — two very different stories cancelling each other out at the index level. Sector rotation is the pattern of capital shifting between groups of stocks as the economic and market narrative changes, and learning to read it is often more informative than watching the index alone.",
        ],
      },
      {
        heading: "What typically drives a rotation",
        paragraphs: [
          "Interest-rate expectations are one of the most consistent drivers. Rate-sensitive sectors — banking, NBFCs, real estate, auto (largely bought on credit) — tend to respond directly and quickly to RBI policy signals. A dovish RBI tone (hinting at future cuts) often lifts these sectors even before an actual rate change happens, since markets price in expectations ahead of the event.",
          "Currency moves drive a different rotation. A weakening rupee tends to benefit export-oriented sectors like IT services and pharmaceuticals (their revenue is largely dollar-denominated, so a weaker rupee means more rupees per dollar earned), while it raises costs for import-dependent sectors.",
          "Commodity cycles rotate capital between upstream producers and downstream consumers of the same input — rising crude benefits upstream oil & gas producers (ONGC-type businesses) while hurting downstream users of crude derivatives (paints, tyres, aviation).",
          "And earnings season itself causes rotation — strong results from a bellwether company in a sector often pull the whole sector up in anticipation that peers will report similarly, while a disappointing result can drag the sector down even for companies that haven't reported yet.",
        ],
      },
      {
        heading: "Reading sector strength as its own signal",
        paragraphs: [
          "Rather than just tracking whether a sector is up or down today, the more useful question is whether its relative strength — momentum compared to the broader market — is rising or falling over a stretch of sessions. A sector consistently outperforming the index over several weeks, even by a small daily margin, is showing a real trend; a single strong day tells you much less.",
          "This is the idea behind tracking theme and sector strength scores over time rather than a single day's percentage move — persistence is usually more meaningful than magnitude.",
        ],
      },
      {
        heading: "The trap: chasing a rotation that's already priced in",
        paragraphs: [
          "By the time a sector rotation is obvious in the headlines — 'IT stocks rally as rupee weakens' — a meaningful part of the move has often already happened. The more useful skill is identifying the underlying driver (a rate decision, a currency trend, a commodity move) early and reasoning through which sectors it should logically affect, rather than reacting to the sector move itself after the fact.",
        ],
      },
    ],
    relatedArticles: ["how-ripple-effects-work", "reading-fii-dii-flows"],
    relatedGlossary: ["sector-rotation", "market-breadth", "theme-strength"],
  },
  {
    slug: "how-rbi-policy-moves-markets",
    title: "How RBI Policy Decisions Move Markets",
    category: "Macro & Policy",
    summary: "The repo rate decision itself is often the least interesting part of an RBI policy day. Here's what actually moves markets on MPC days, and why the tone matters as much as the number.",
    readTime: "5 min",
    body: [
      {
        paragraphs: [
          "Every two months, India's Monetary Policy Committee meets to decide the repo rate — and every time, financial media treats the decision like a binary event: rates up, down, or unchanged. In practice, markets often react less to the headline number (which is frequently well-anticipated in advance) and more to three other things: the vote split, the tone of forward guidance, and the inflation trajectory the RBI signals.",
        ],
      },
      {
        heading: "Why the rate number is often already priced in",
        paragraphs: [
          "Professional traders and economists build rate expectations well ahead of the actual MPC meeting, based on recent inflation prints, global central bank moves, and RBI Governor commentary in the weeks leading up to the decision. When the RBI delivers exactly what was expected — say, holding rates when a hold was already the consensus view — the market reaction is often muted, since there's no new information.",
          "The real market-moving surprises happen when the RBI does something the market didn't expect: an unscheduled rate move, a rate change larger or smaller than anticipated, or unexpectedly hawkish or dovish language.",
        ],
      },
      {
        heading: "The vote split matters",
        paragraphs: [
          "A unanimous MPC decision signals strong internal agreement on the policy path — markets read this as a clearer, more predictable signal about what comes next. A split vote (say, 4-2 instead of 6-0) signals genuine disagreement among committee members about the right path forward, which tends to increase uncertainty about future decisions and can add volatility even when the headline rate decision itself was as expected.",
        ],
      },
      {
        heading: "Forward guidance: the real signal",
        paragraphs: [
          "The RBI Governor's post-decision commentary — on inflation trajectory, growth outlook, and hints (or explicit statements) about the likely direction of future policy — is frequently more market-moving than the rate decision itself. Language shifts from 'withdrawal of accommodation' to 'neutral' stance, for example, signal a meaningfully different policy trajectory even without any change to the actual rate that day.",
          "This is why serious market participants read the full policy statement, not just the headline rate, and why the same 'RBI holds rates' headline can produce very different market reactions depending on what else was said alongside it.",
        ],
      },
      {
        heading: "How it transmits to specific sectors",
        paragraphs: [
          "Banking and NBFC stocks are the most directly sensitive — their net interest margins are a direct function of the rate environment. Real estate and auto, both largely credit-financed purchases for end consumers, respond to changes in effective borrowing costs. Government bond yields move in tandem with rate expectations, which in turn affects the relative attractiveness of debt versus equity for large institutional allocators — a factor that can influence overall market flows well beyond just rate-sensitive sectors.",
        ],
      },
    ],
    relatedArticles: ["reading-fii-dii-flows", "understanding-sector-rotation"],
    relatedGlossary: ["repo-rate", "mpc", "cpi-inflation", "bank-nifty"],
  },
  {
    slug: "reading-fii-dii-flows",
    title: "Reading FII/DII Flows: What They Really Tell You",
    category: "Macro & Policy",
    summary: "Foreign and domestic institutional flow data gets quoted every single trading day — but the daily number is far noisier than it looks. Here's how to actually use it.",
    readTime: "4 min",
    body: [
      {
        paragraphs: [
          "'FII net selling ₹1,200 Cr, DII net buying ₹1,018 Cr' is one of the most quoted data points in Indian financial media, appearing in some form on nearly every market-close summary. It's genuinely useful information — but only if you know what it does and doesn't tell you.",
        ],
      },
      {
        heading: "What a single day's number actually means",
        paragraphs: [
          "FII (Foreign Institutional Investor, officially FPI) flow data shows the net rupee value of Indian equities foreign institutions bought or sold that session. DII (Domestic Institutional Investor) data shows the same for India-based institutions — mainly mutual funds and insurers.",
          "A single day of FII selling is genuinely low-signal on its own. Large foreign funds rebalance portfolios, take profits, or adjust regional allocations for reasons that have nothing to do with a specific view on India — global risk sentiment, US bond yields, or a decision to rotate into a different emerging market can all show up as 'FII selling' in India with no India-specific cause at all.",
        ],
      },
      {
        heading: "What actually matters: the trend, not the day",
        paragraphs: [
          "Sustained FII selling or buying over multiple weeks is a much stronger signal than any single day. A consistent multi-week trend usually reflects a genuine shift in how global capital views India relative to other markets — often tied to relative valuations, currency expectations, or a broader emerging-market risk-on/risk-off cycle.",
          "It's also worth watching FII and DII flows relative to each other, not just in isolation. Since roughly 2020, sustained DII buying (increasingly funded by retail mutual fund SIP inflows) has repeatedly absorbed periods of heavy FII selling, keeping the market comparatively stable during episodes that, a decade earlier, would likely have caused a sharper fall. That structural shift — the market having a much larger domestic buyer base than before — is itself one of the more important stories in Indian markets over the past several years.",
        ],
      },
      {
        heading: "A common misreading to avoid",
        paragraphs: [
          "It's tempting to treat 'FII selling' as inherently bearish and 'FII buying' as inherently bullish for every individual session. In practice, the market can rise on a day of net FII selling if DII buying more than offsets it, and can fall on a day of FII buying if broader sentiment is weak enough. Flow data is one input into understanding market direction — not a standalone trading signal.",
        ],
      },
    ],
    relatedArticles: ["how-rbi-policy-moves-markets", "understanding-sector-rotation"],
    relatedGlossary: ["fii", "dii", "usd-inr"],
  },
  {
    slug: "beginners-guide-to-market-cycles",
    title: "A Beginner's Guide to Market Cycles",
    category: "Investing Framework",
    summary: "Markets move in recognizable phases — expansion, peak, contraction, trough — and different sectors, strategies, and risks matter at different points in that cycle. Here's a practical framework for orienting yourself.",
    readTime: "6 min",
    body: [
      {
        paragraphs: [
          "Markets don't move in a straight line, and they don't move randomly either — they tend to move through recognizable phases tied to the broader economic cycle: expansion, peak, contraction, and trough, followed by a new expansion. Understanding roughly where you are in that cycle doesn't let you predict the future with precision, but it does help you understand which risks and opportunities are most relevant right now.",
        ],
      },
      {
        heading: "Expansion: the recovery and growth phase",
        paragraphs: [
          "Coming out of a downturn, an expansion phase is typically marked by improving corporate earnings, accommodative monetary policy (lower rates to encourage borrowing and investment), rising employment, and generally improving investor sentiment. Cyclical sectors — those most sensitive to economic activity, like banking, industrials, real estate, and consumer discretionary — tend to lead during this phase, since they benefit most directly from an improving economy.",
        ],
      },
      {
        heading: "Peak: growth slows, inflation risk rises",
        paragraphs: [
          "As an expansion matures, growth rates start to slow from their fastest pace, inflation pressures often build (strong demand meeting capacity constraints), and central banks typically begin tightening policy (raising rates) to keep inflation in check. This phase is often the hardest to identify in real time — it's usually only clear in hindsight exactly when the peak occurred.",
        ],
      },
      {
        heading: "Contraction: the slowdown",
        paragraphs: [
          "Tighter monetary policy and slowing demand eventually show up as declining corporate earnings, rising unemployment, and falling investor confidence. Defensive sectors — those less sensitive to economic cycles, like FMCG, pharmaceuticals, and utilities, where demand holds up even in a weaker economy — tend to hold up better than cyclicals during this phase.",
        ],
      },
      {
        heading: "Trough: the bottom, and the hardest phase to act in",
        paragraphs: [
          "At the bottom of the cycle, sentiment is typically at its most pessimistic, and it's often genuinely difficult to distinguish 'the bottom' from 'still falling.' Historically, the strongest returns have often come from positions taken during this phase of maximum pessimism — but it's also the phase where the emotional and psychological difficulty of buying is highest, since the news flow and sentiment are almost uniformly negative.",
        ],
      },
      {
        heading: "Why this framework is useful — and its real limits",
        paragraphs: [
          "No two cycles play out identically, cycle phases don't have fixed durations, and it's genuinely difficult to identify turning points in real time rather than in hindsight. The value of this framework isn't precise timing — it's a mental model for asking better questions: which sectors typically lead at this stage, what would change if the cycle turned, and what's actually different about this cycle compared to historical patterns.",
          "Used this way — as a lens for interpreting what's happening, rather than a forecasting tool — a basic understanding of market cycles is one of the most durable frameworks in investing, precisely because it doesn't require being right about exact timing to be useful.",
        ],
      },
    ],
    relatedArticles: ["understanding-sector-rotation", "how-rbi-policy-moves-markets"],
    relatedGlossary: ["sector-rotation", "market-cap"],
  },
];

export function getArticle(slug: string): Article | undefined {
  return ARTICLES.find(a => a.slug === slug);
}

export function getRelatedArticles(article: Article): Article[] {
  return (article.relatedArticles ?? [])
    .map(slug => getArticle(slug))
    .filter((a): a is Article => !!a);
}

export const ARTICLE_CATEGORIES = Array.from(new Set(ARTICLES.map(a => a.category)));
