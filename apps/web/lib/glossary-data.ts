/**
 * MarketRipple Glossary — real, written definitions covering both general
 * Indian-market terminology and MarketRipple's own scoring concepts.
 * Single source of truth for /learn/glossary and /learn/glossary/[slug].
 */

export interface GlossaryTerm {
  slug: string;
  term: string;
  category: "Indices" | "Market Mechanics" | "Institutional Flows & Policy" | "Fundamental Analysis" | "Corporate Actions" | "MarketRipple Concepts";
  shortDef: string;
  definition: string[];     // paragraphs
  example?: string;
  related?: string[];       // slugs
}

export const GLOSSARY: GlossaryTerm[] = [
  // ── Indices ────────────────────────────────────────────────────────────
  {
    slug: "nifty-50",
    term: "Nifty 50",
    category: "Indices",
    shortDef: "NSE's benchmark index tracking the 50 largest, most liquid Indian companies by free-float market capitalization.",
    definition: [
      "The Nifty 50 is the National Stock Exchange of India's flagship index, made up of 50 of the largest and most actively traded companies across sectors — weighted by free-float market capitalization, meaning shares actually available for public trading rather than promoter or government holdings.",
      "Because it's diversified across roughly 13 sectors (financials, IT, energy, FMCG, and more), the Nifty 50 is the most commonly quoted proxy for 'how the Indian stock market is doing,' and is the underlying for the country's most liquid index futures and options.",
    ],
    example: "When you hear 'the market fell 1%' on Indian financial news, it almost always means the Nifty 50 fell 1%.",
    related: ["sensex", "bank-nifty", "market-breadth"],
  },
  {
    slug: "sensex",
    term: "Sensex (BSE Sensex)",
    category: "Indices",
    shortDef: "BSE's benchmark index of 30 large, established companies — India's oldest stock market index, running since 1986.",
    definition: [
      "The S&P BSE Sensex tracks 30 financially sound, well-established companies listed on the Bombay Stock Exchange, chosen to represent a cross-section of India's economy. It's narrower than the Nifty 50 (30 stocks vs 50) but moves in close lockstep with it, since most large-cap companies are listed on both exchanges.",
      "The Sensex predates the Nifty by roughly a decade and remains the more recognized name internationally, even though the Nifty 50 now carries more derivatives trading volume.",
    ],
    related: ["nifty-50", "market-cap"],
  },
  {
    slug: "bank-nifty",
    term: "Bank Nifty (Nifty Bank)",
    category: "Indices",
    shortDef: "A sectoral index tracking the most liquid, large-cap banking stocks listed on the NSE.",
    definition: [
      "Nifty Bank tracks the most liquid and large-capitalized Indian banking stocks — a mix of private banks (HDFC Bank, ICICI Bank, Axis Bank, Kotak Mahindra Bank) and public-sector banks (SBI). Because banks sit at the center of credit growth, interest-rate transmission, and NPA (bad loan) cycles, Bank Nifty is often treated as a leading indicator for the broader economy.",
      "It's also one of the most actively traded derivatives contracts in India, meaning its intraday moves tend to be sharper and faster than the Nifty 50's.",
    ],
    related: ["nifty-50", "repo-rate"],
  },
  {
    slug: "india-vix",
    term: "India VIX",
    category: "Indices",
    shortDef: "India's 'fear gauge' — measures the market's expectation of Nifty volatility over the next 30 days.",
    definition: [
      "India VIX is computed from the order book of Nifty options and expresses expected volatility as an annualized percentage. It doesn't predict direction — only how much movement (up or down) the market is pricing in.",
      "As a rough guide: below 12–13 typically signals a calm, low-volatility market; 15–20 is a normal working range; above 20–25 usually coincides with genuine stress (elections, geopolitical shocks, global sell-offs) and wider, faster intraday swings.",
    ],
    example: "India VIX spiking from 13 to 22 in a single session — even with the Nifty flat — tells you options traders suddenly expect much bigger moves soon, often ahead of a known event like a budget or a central bank decision.",
    related: ["nifty-50", "put-call-ratio"],
  },

  // ── Market Mechanics ───────────────────────────────────────────────────
  {
    slug: "market-breadth",
    term: "Market Breadth",
    category: "Market Mechanics",
    shortDef: "The ratio of advancing stocks to declining stocks — a check on whether an index move is broad-based or narrow.",
    definition: [
      "Market breadth (advances vs. declines) tells you how many individual stocks actually participated in a day's index move, not just whether the index itself went up or down. A Nifty 50 index can rise 1% on the back of just 3–4 heavyweight stocks while hundreds of other listed stocks fall — that's narrow, fragile breadth.",
      "Broad breadth (a large majority of stocks advancing alongside the index) is generally read as healthier and more sustainable than a rally concentrated in a handful of names.",
    ],
    example: "1,124 advancing vs. 387 declining stocks is broad, healthy breadth. 600 advancing vs. 900 declining while the index is still up is a warning sign — the index gain is being carried by a few large stocks.",
    related: ["nifty-50", "sector-rotation"],
  },
  {
    slug: "circuit-filter",
    term: "Circuit Filter (Circuit Breaker)",
    category: "Market Mechanics",
    shortDef: "A price band that automatically halts trading in a stock or index if it moves too far, too fast.",
    definition: [
      "Exchanges apply circuit filters — typically 2%, 5%, 10%, or 20% — to individual stocks to stop trading temporarily once a stock hits that move in either direction, giving the market time to absorb information and preventing panic-driven price spirals.",
      "Index-wide circuit breakers exist too (triggered by a sharp Nifty/Sensex move), and can halt trading across the entire exchange for a fixed cooling-off period.",
    ],
    related: ["india-vix"],
  },
  {
    slug: "52-week-high-low",
    term: "52-Week High / Low",
    category: "Market Mechanics",
    shortDef: "The highest and lowest price a stock has traded at over the trailing 12 months.",
    definition: [
      "A stock hitting a new 52-week high means it's trading above every closing price from the past year — often read as a sign of strong momentum or improving fundamentals, though it can also signal a stock has run ahead of its valuation. A new 52-week low is the inverse, and can reflect either a genuine deterioration in the business or a temporary, overdone sell-off.",
      "Neither on its own is a buy or sell signal — the more useful question is always why the stock is at that level.",
    ],
    related: ["market-breadth"],
  },
  {
    slug: "put-call-ratio",
    term: "Put-Call Ratio (PCR)",
    category: "Market Mechanics",
    shortDef: "The ratio of put option to call option trading volume (or open interest) — a sentiment gauge for options traders.",
    definition: [
      "PCR divides the volume (or open interest) of put options by call options for a given underlying, usually the Nifty. A PCR meaningfully above 1 means traders are buying more puts (bearish bets / hedges) than calls; a PCR well below 1 suggests more bullish positioning via calls.",
      "PCR is a sentiment and positioning indicator, not a price predictor — extremely high or low readings are sometimes read as contrarian signals (excessive bearishness can precede a bounce, and vice versa), but it's most useful alongside other signals, not alone.",
    ],
    related: ["india-vix"],
  },
  {
    slug: "market-cap",
    term: "Market Capitalization (Large / Mid / Small Cap)",
    category: "Market Mechanics",
    shortDef: "A company's total market value (share price × shares outstanding), used to bucket stocks into large-, mid-, and small-cap.",
    definition: [
      "Market cap is simply current share price multiplied by the total number of outstanding shares. SEBI's official classification ranks all listed companies by market cap and buckets them: the top 100 are large-cap, the next 150 are mid-cap, and everything ranked below 250 is small-cap.",
      "Large-caps are generally more liquid and stable; mid- and small-caps carry higher growth potential alongside higher volatility and liquidity risk — they can be harder to buy or sell in size without moving the price.",
    ],
    related: ["sensex", "nifty-50"],
  },
  {
    slug: "sector-rotation",
    term: "Sector Rotation",
    category: "Market Mechanics",
    shortDef: "The shifting of investor capital from one sector to another as the economic cycle or market narrative changes.",
    definition: [
      "Different sectors tend to lead at different points in an economic or market cycle — for example, IT and export-oriented sectors often benefit from a weaker rupee and strong global demand, while rate-sensitive sectors like banking, real estate, and auto tend to respond directly to RBI policy moves. Sector rotation is the observable pattern of institutional money moving between these groups as the macro backdrop shifts.",
      "Tracking which sectors are gaining relative strength (and which are losing it) is often a more useful signal than the headline index move alone, since it tells you what story the market is actually pricing in.",
    ],
    related: ["market-breadth", "theme-strength"],
  },

  // ── Institutional Flows & Policy ───────────────────────────────────────
  {
    slug: "fii",
    term: "FII (Foreign Institutional Investor)",
    category: "Institutional Flows & Policy",
    shortDef: "Overseas institutions — funds, pension funds, insurers — that invest in Indian equities and debt from abroad.",
    definition: [
      "FIIs (also called FPIs, Foreign Portfolio Investors, in current SEBI terminology) are large foreign entities that buy and sell Indian securities. Because they move large sums relative to daily trading volumes, sustained FII buying or selling can meaningfully move the Nifty and the rupee, and FII flow data is watched closely as a sentiment indicator for how global capital views India relative to other emerging markets.",
      "FII flows are sensitive to global factors well beyond India-specific news — US interest rates, dollar strength, and risk appetite across all emerging markets all influence whether foreign money is flowing in or out.",
    ],
    example: "'FII net selling ₹1,200 Cr' means foreign institutions sold roughly ₹1,200 crore more Indian equity than they bought that session — a headwind for the market, all else equal.",
    related: ["dii", "usd-inr"],
  },
  {
    slug: "dii",
    term: "DII (Domestic Institutional Investor)",
    category: "Institutional Flows & Policy",
    shortDef: "Indian institutions — mutual funds, insurance companies, banks — investing domestic capital in Indian markets.",
    definition: [
      "DIIs are India-based institutions, most visibly mutual funds (increasingly funded by retail SIP inflows) and insurance companies like LIC. Over the past decade, sustained DII buying — largely powered by rising domestic retail participation via mutual fund SIPs — has become a structural counterweight to FII selling, something that wasn't true a decade ago.",
      "When FIIs sell and DIIs absorb that selling (buy roughly the same amount), the market often stays range-bound rather than falling sharply — a dynamic increasingly common in Indian markets since 2020.",
    ],
    related: ["fii"],
  },
  {
    slug: "repo-rate",
    term: "Repo Rate",
    category: "Institutional Flows & Policy",
    shortDef: "The interest rate at which the RBI lends short-term funds to commercial banks — India's key policy interest rate.",
    definition: [
      "The repo rate is the RBI's primary tool for controlling inflation and growth. Raising the repo rate makes borrowing costlier across the economy — banks pass higher rates on to loans — which tends to cool inflation but also growth and rate-sensitive sectors (banking margins, real estate, auto financing). Cutting it does the reverse, aiming to stimulate borrowing and spending.",
      "The Monetary Policy Committee (MPC) reviews the repo rate roughly every two months; the decision, and even more so the RBI Governor's forward guidance on future moves, is one of the most closely watched events in the Indian market calendar.",
    ],
    example: "'RBI holds repo rate at 6.50% for the seventh consecutive meeting' signals policy stability — markets generally read an unchanged, well-telegraphed rate as neutral-to-mildly-positive, since it removes uncertainty.",
    related: ["mpc", "cpi-inflation", "bank-nifty"],
  },
  {
    slug: "mpc",
    term: "MPC (Monetary Policy Committee)",
    category: "Institutional Flows & Policy",
    shortDef: "The six-member RBI committee that sets India's repo rate through a majority vote at scheduled policy meetings.",
    definition: [
      "The MPC — three RBI members plus three external economists appointed by the government — meets roughly every two months to review growth and inflation data and vote on the repo rate. Its primary mandate is keeping CPI inflation within a target band (currently 2–6%, with 4% as the medium-term target).",
      "Markets watch not just the rate decision itself but the vote split (unanimous vs. split decisions signal how much internal disagreement exists) and the accompanying policy statement, which shapes expectations for the next several meetings.",
    ],
    related: ["repo-rate", "cpi-inflation"],
  },
  {
    slug: "cpi-inflation",
    term: "CPI Inflation",
    category: "Institutional Flows & Policy",
    shortDef: "The Consumer Price Index — India's headline inflation measure, tracking the price change of a representative basket of goods and services.",
    definition: [
      "CPI inflation measures how much the average consumer's cost of living rose year-over-year, based on a fixed basket that includes food, fuel, housing, and other everyday categories. It's the RBI's primary inflation target and the single most-watched monthly economic data release in India, since it directly informs the MPC's rate decisions.",
      "Food and fuel prices are typically the most volatile components; 'core CPI' (inflation excluding food and fuel) is watched separately as a cleaner read on underlying, stickier price pressure.",
    ],
    related: ["mpc", "wpi-inflation", "repo-rate"],
  },
  {
    slug: "wpi-inflation",
    term: "WPI Inflation",
    category: "Institutional Flows & Policy",
    shortDef: "The Wholesale Price Index — tracks price changes at the wholesale/producer level, ahead of consumer prices.",
    definition: [
      "WPI measures inflation at the wholesale level — prices producers and traders pay each other — rather than what consumers pay at the till (that's CPI). Because wholesale price changes often feed through to consumer prices with a lag, WPI is watched as an early, leading signal for where CPI inflation may be headed, though the RBI's actual policy target is CPI, not WPI.",
    ],
    related: ["cpi-inflation", "repo-rate"],
  },
  {
    slug: "fiscal-deficit",
    term: "Fiscal Deficit",
    category: "Institutional Flows & Policy",
    shortDef: "The gap between the government's total spending and its total revenue (excluding borrowings), usually expressed as a % of GDP.",
    definition: [
      "A fiscal deficit means the government is spending more than it collects in revenue and must borrow to cover the gap. Markets watch the fiscal deficit target closely around Union Budget time — a wider-than-expected deficit can pressure bond yields (the government needs to borrow more, competing with corporate borrowers for funds) and is sometimes read as inflationary if the extra spending isn't productive.",
      "A credible, narrowing fiscal deficit path is generally viewed positively by rating agencies and foreign investors as a sign of fiscal discipline.",
    ],
    related: ["mpc"],
  },
  {
    slug: "usd-inr",
    term: "USD/INR (Rupee Exchange Rate)",
    category: "Institutional Flows & Policy",
    shortDef: "How many rupees it takes to buy one US dollar — India's most-watched currency pair.",
    definition: [
      "A rising USD/INR number means the rupee is weakening (it takes more rupees to buy a dollar); a falling number means the rupee is strengthening. Rupee moves are driven by FII flows, the trade balance, crude oil prices (India imports most of its oil in dollars), and relative interest-rate differences with the US.",
      "A weaker rupee raises import costs (especially oil, which feeds into inflation) but benefits export-heavy sectors like IT services, since their dollar revenue converts into more rupees.",
    ],
    related: ["fii", "repo-rate"],
  },

  // ── Fundamental Analysis ───────────────────────────────────────────────
  {
    slug: "pe-ratio",
    term: "P/E Ratio (Price-to-Earnings)",
    category: "Fundamental Analysis",
    shortDef: "A stock's share price divided by its earnings per share — the most common shorthand for whether a stock looks 'expensive' or 'cheap'.",
    definition: [
      "The P/E ratio tells you how many rupees investors are willing to pay for every one rupee of a company's current annual profit. A P/E of 25 means the market is valuing the stock at 25 times its earnings. Higher P/E generally reflects higher expected future growth (or, sometimes, overvaluation); lower P/E can mean the stock is undervalued, or that the market expects earnings to decline.",
      "P/E is only meaningful when compared — against the company's own historical average, against direct sector peers, or against the broader index. A P/E of 40 might be cheap for a fast-growing tech company and expensive for a slow-growing utility.",
    ],
    related: ["pb-ratio", "market-cap"],
  },
  {
    slug: "pb-ratio",
    term: "P/B Ratio (Price-to-Book)",
    category: "Fundamental Analysis",
    shortDef: "A stock's share price divided by its book value per share — compares market value to accounting net worth.",
    definition: [
      "Book value is a company's total assets minus total liabilities — its accounting net worth. P/B compares the market's valuation to that net worth: a P/B of 1 means the market values the company exactly at its book value; well above 1 means the market is pricing in intangible value (brand, growth prospects, market position) beyond the balance sheet.",
      "P/B is used most often for asset-heavy businesses like banks and financials, where book value (largely loans and capital) is a more meaningful anchor than for asset-light businesses like software companies.",
    ],
    related: ["pe-ratio"],
  },
  {
    slug: "dividend-yield",
    term: "Dividend Yield",
    category: "Fundamental Analysis",
    shortDef: "Annual dividend per share divided by share price — the cash-return percentage a stock pays out, independent of price appreciation.",
    definition: [
      "Dividend yield expresses how much cash income a stock generates relative to its price, similar to a bond's coupon rate. A stock priced at ₹1,000 paying ₹20 in annual dividends has a 2% yield. High yields can signal a generous, mature, cash-generative business — or can be a warning sign if the price has fallen sharply and the market doubts the dividend is sustainable.",
    ],
    related: ["pe-ratio"],
  },
  {
    slug: "roe",
    term: "ROE (Return on Equity)",
    category: "Fundamental Analysis",
    shortDef: "Net profit divided by shareholders' equity — how efficiently a company turns shareholder capital into profit.",
    definition: [
      "ROE measures how much profit a company generates for every rupee of shareholder equity invested in the business. A consistently high ROE (relative to sector peers) generally signals an efficient, well-run, competitively advantaged business. It's one of the most-cited quality metrics for long-term investors, though it can be artificially inflated by high debt (leverage boosts ROE without necessarily improving underlying business quality), so it's best read alongside debt levels.",
    ],
    related: ["pe-ratio", "pb-ratio"],
  },
  {
    slug: "ebitda",
    term: "EBITDA",
    category: "Fundamental Analysis",
    shortDef: "Earnings Before Interest, Taxes, Depreciation, and Amortization — a measure of core operating profitability.",
    definition: [
      "EBITDA strips out financing decisions (interest), tax jurisdiction effects, and non-cash accounting charges (depreciation and amortization) to isolate how profitable the core operating business is. It's widely used to compare operating performance across companies with different capital structures or tax situations, and to calculate leverage ratios like Net Debt/EBITDA.",
      "EBITDA is not the same as cash flow or net profit — it deliberately ignores real costs like interest payments and capital expenditure, so it shouldn't be read as 'the money the company actually has.'",
    ],
    related: ["roe"],
  },

  // ── Corporate Actions ──────────────────────────────────────────────────
  {
    slug: "ipo",
    term: "IPO (Initial Public Offering)",
    category: "Corporate Actions",
    shortDef: "The first time a private company sells shares to the public and lists on a stock exchange.",
    definition: [
      "An IPO is how a company transitions from privately held to publicly traded, raising capital by selling new shares (or existing shareholders selling their stake) to public investors for the first time. Retail investors apply for shares during a fixed subscription window at a price band set by the company and its bankers; allotment is then done via lottery or pro-rata basis if the issue is oversubscribed.",
      "The Grey Market Premium (GMP) — the unofficial, informal premium at which IPO shares trade before listing — is widely tracked as an (unreliable but popular) gauge of expected listing-day demand.",
    ],
    related: ["market-cap"],
  },
  {
    slug: "bonus-shares",
    term: "Bonus Shares",
    category: "Corporate Actions",
    shortDef: "Additional free shares issued to existing shareholders in a fixed ratio, funded from the company's reserves.",
    definition: [
      "A bonus issue gives existing shareholders extra shares — for example, a 1:1 bonus means you get one additional free share for every share you already hold — funded out of the company's accumulated reserves rather than fresh capital. The total value of your holding doesn't change immediately (the share price adjusts down proportionally), but bonus issues improve liquidity by increasing the number of shares in circulation and are often read as a signal of management confidence.",
    ],
    related: ["stock-split"],
  },
  {
    slug: "stock-split",
    term: "Stock Split",
    category: "Corporate Actions",
    shortDef: "Dividing each existing share into multiple shares, reducing the price per share without changing total holding value.",
    definition: [
      "A stock split (e.g., 1:5, where each share becomes five) reduces the share price proportionally while increasing the number of shares outstanding — your total holding value is unchanged. Companies typically split shares to bring a high per-share price back into a range that's more accessible to retail investors, improving liquidity.",
    ],
    related: ["bonus-shares"],
  },

  // ── MarketRipple Concepts ──────────────────────────────────────────────
  {
    slug: "impact-score",
    term: "Impact Score",
    category: "MarketRipple Concepts",
    shortDef: "MarketRipple's 0–100 measure of how significant a market event is likely to be, based on real evidence — never fabricated when evidence is insufficient.",
    definition: [
      "Every event MarketRipple tracks is scored 0–100 for market impact by our Scoring Engine, weighing factors like the size and reach of the event, sector and company linkages, and historical precedent for similar events. Higher scores mean broader, more significant expected market consequences.",
      "Crucially, an Impact Score is only shown when there's enough real evidence to compute one. If evidence is genuinely insufficient, MarketRipple shows 'Unscored' rather than guessing — we never display a fabricated number where the honest answer is 'we don't know yet.'",
    ],
    related: ["confidence-score", "data-status"],
  },
  {
    slug: "confidence-score",
    term: "Confidence Score",
    category: "MarketRipple Concepts",
    shortDef: "How certain MarketRipple's AI is in a given score or prediction — shown separately from the score itself, never blended into it.",
    definition: [
      "Confidence is reported alongside — not folded into — every score MarketRipple produces. A high Impact Score with low confidence means: 'if this plays out as expected, it matters a lot, but the evidence behind that expectation is still thin.' A high Impact Score with high confidence means the evidence is both strong and consistent.",
      "Keeping confidence separate from the underlying score is a deliberate design choice: collapsing the two into one number would hide exactly the information — how sure should you be? — that matters most when deciding how much weight to give any single signal.",
    ],
    related: ["impact-score", "data-status"],
  },
  {
    slug: "ripple-effect",
    term: "Ripple Effect",
    category: "MarketRipple Concepts",
    shortDef: "The chain of downstream consequences a single market event triggers — from the originating event through sectors, companies, and related asset classes.",
    definition: [
      "Markets rarely move in isolation — a crude oil price spike doesn't just affect oil companies; it raises input costs for paints, tyres, and airlines, adds to inflation risk, and can influence RBI policy expectations. A 'ripple effect' is this traced chain of cause and consequence, mapped from the original event outward.",
      "MarketRipple's Ripple Engine generates these maps using real event data and modeled relationships between sectors, companies, and macro indicators — helping you see not just what happened, but what it's likely to touch next.",
    ],
    related: ["impact-score", "sector-rotation"],
  },
  {
    slug: "opportunity-score",
    term: "Opportunity Score",
    category: "MarketRipple Concepts",
    shortDef: "MarketRipple's 0–100 ranking of investment opportunities, combining event impact, sector momentum, and historical precedent.",
    definition: [
      "The Opportunity Radar scores potential investment opportunities — themes, sectors, or company clusters — on a 0–100 scale, built from the underlying events driving the opportunity, their Impact Scores, current sector momentum, and how similar historical setups have played out. It's a starting point for research, not a recommendation to buy or sell.",
    ],
    related: ["impact-score", "theme-strength"],
  },
  {
    slug: "data-status",
    term: "Data Status (Preliminary / Verified / Live)",
    category: "MarketRipple Concepts",
    shortDef: "A label showing how mature the evidence behind a score is — not how big the number is, but how much you should trust it right now.",
    definition: [
      "MarketRipple scores evolve as evidence accumulates. 'Preliminary' means a score was generated immediately from the information available when an event first broke — useful for speed, but based on limited evidence. 'Verified' means the score has been cross-checked against additional market data. 'Live' means it's backed by current, actively-updating market data.",
      "This status is shown explicitly wherever a score appears, so you always know whether you're looking at a first-draft read or a well-evidenced one — instead of every number looking equally authoritative regardless of how much evidence actually backs it.",
    ],
    related: ["confidence-score", "impact-score"],
  },
  {
    slug: "sentiment-score",
    term: "Sentiment Score",
    category: "MarketRipple Concepts",
    shortDef: "A 0–100 read of overall market mood, derived from real breadth data (how many stocks/indices are advancing vs. declining) — not a survey or guess.",
    definition: [
      "MarketRipple's sentiment score is computed from actual market breadth — the proportion of tracked indices and stocks currently advancing versus declining — rather than being a subjective 'vibe' estimate. It's presented on a Fear & Greed-style scale (Extreme Fear to Extreme Greed) as a fast, at-a-glance summary of real market conditions.",
    ],
    related: ["market-breadth"],
  },
  {
    slug: "theme-strength",
    term: "Theme Strength",
    category: "MarketRipple Concepts",
    shortDef: "A 0–100 score measuring how strong the momentum and news-driven attention behind an investment theme currently is.",
    definition: [
      "MarketRipple tracks investment themes (like Defence, IT & Technology, or Banking) as living entities, scoring each on price momentum among its constituent stocks and the volume of relevant news activity. Rising theme strength suggests a theme is gaining real market attention and momentum; falling strength suggests it's cooling off.",
    ],
    related: ["opportunity-score", "sector-rotation"],
  },
];

export function getGlossaryTerm(slug: string): GlossaryTerm | undefined {
  return GLOSSARY.find(t => t.slug === slug);
}

export function getRelatedTerms(term: GlossaryTerm): GlossaryTerm[] {
  return (term.related ?? [])
    .map(slug => getGlossaryTerm(slug))
    .filter((t): t is GlossaryTerm => !!t);
}

export const GLOSSARY_CATEGORIES = Array.from(new Set(GLOSSARY.map(t => t.category)));
