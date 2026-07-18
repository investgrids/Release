/**
 * MarketRipple Product Guides — how-to content for using real, shipped
 * features. Single source of truth for /learn/guides and /learn/guides/[slug].
 */

export interface Guide {
  slug: string;
  title: string;
  category: "Getting Started" | "Intelligence Features" | "Research Tools";
  summary: string;
  readTime: string;
  steps: { title: string; body: string }[];
  tips?: string[];
  relatedGuides?: string[];  // slugs
}

export const GUIDES: Guide[] = [
  {
    slug: "reading-the-market-intelligence-dashboard",
    title: "Reading the Market Intelligence Dashboard",
    category: "Getting Started",
    summary: "How to read the AI Market Brief, ticker strip, and session tabs (Overview, Pre-Market, Live Market, After Market, Global Markets) so you know exactly what MarketRipple is telling you before the market opens.",
    readTime: "4 min",
    steps: [
      {
        title: "Start with the AI Market Brief",
        body: "The Market Brief at the top of the Intelligence page is the single most important thing on the page — a plain-language summary of the day's mood (Bullish / Bearish / Neutral), the confidence behind that read, and the day's biggest driving event. Everything else on the dashboard supports or expands on this headline.",
      },
      {
        title: "Check the session tab you actually need",
        body: "The dashboard is split into five tabs matched to the trading day: Overview (a general snapshot), Pre-Market (before 9:15 AM IST — Gift Nifty, global cues, FII/DII flows), Live Market (during trading hours — real-time drivers, sector rotation, live feed), After Market (post-close wrap and tomorrow's setup), and Global Markets (US, European, and Asian indices). Pick the tab that matches where you are in the trading day, rather than reading the Overview tab all day.",
      },
      {
        title: "Use the ticker strip as your pulse check",
        body: "The top ticker strip (Nifty 50, Sensex, Bank Nifty, India VIX, plus USD/INR) updates continuously and is designed to be glanced at, not read in detail — it's there so you always know the market's current state without leaving whatever page you're on.",
      },
      {
        title: "Watch Market Status, not the clock",
        body: "Rather than mentally tracking Indian market hours, check the Market Status indicator in the page header — it tells you directly whether the market is in pre-market, open, closed, or it's a weekend, and adjusts which tab's data is most current.",
      },
    ],
    tips: [
      "The AI Market Brief refreshes as new events break — if the mood or confidence number changes mid-session, that's a signal something material just happened.",
      "On the Live Market tab, 'Data Status' badges (Preliminary / Verified / Live) next to any score tell you how much evidence backs that specific number — treat a Preliminary score as a first draft, not a final answer.",
    ],
    relatedGuides: ["understanding-impact-and-confidence-scores", "using-the-live-intelligence-feed"],
  },
  {
    slug: "how-ai-search-works",
    title: "How AI Search Works",
    category: "Intelligence Features",
    summary: "Ask MarketRipple's AI Search a plain-language question about markets, companies, or events, and get a sourced, evidence-linked answer instead of a list of blue links.",
    readTime: "3 min",
    steps: [
      {
        title: "Ask a real question, not keywords",
        body: "AI Search is built to answer questions the way you'd ask a knowledgeable analyst — 'What's driving IT stocks this week?' or 'How does a repo rate hold affect banking stocks?' — rather than requiring exact search terms.",
      },
      {
        title: "Read the answer, then check the evidence",
        body: "Every AI Search answer is grounded in specific events, scores, and data points MarketRipple actually tracked — not generated from general knowledge alone. The sources behind an answer are shown alongside it, so you can verify the reasoning rather than taking the summary on faith.",
      },
      {
        title: "Use the Methodology drawer for transparency",
        body: "Where AI Search or a score is shown, look for the 'Why am I seeing this?' or methodology option — it explains what evidence and reasoning chain produced that specific answer, not just a generic description of how AI Search works in general.",
      },
    ],
    tips: [
      "AI Search draws on the same real-time event and scoring data that powers the rest of MarketRipple — it's not a separate, disconnected chatbot.",
      "If AI Search doesn't have enough real evidence to answer confidently, it will say so rather than filling the gap with a plausible-sounding guess.",
    ],
    relatedGuides: ["understanding-impact-and-confidence-scores"],
  },
  {
    slug: "reading-the-opportunity-radar",
    title: "Reading the Opportunity Radar",
    category: "Research Tools",
    summary: "How Opportunity Radar surfaces and scores potential investment themes — and how to use the score, confidence, risk level, and time horizon together instead of looking at the score alone.",
    readTime: "4 min",
    steps: [
      {
        title: "Understand what an 'opportunity' is here",
        body: "Each entry on the Opportunity Radar represents a theme or cluster of companies that MarketRipple's analysis has flagged as being driven by current, real events — a policy change, a sector-wide earnings trend, or a structural shift. It is a research starting point, not a buy recommendation.",
      },
      {
        title: "Read the Opportunity Score alongside confidence",
        body: "The 0–100 Opportunity Score reflects the underlying event impact, sector momentum, and historical precedent. Always check the confidence percentage next to it — a high score with lower confidence means the upside case is real but the evidence is still developing.",
      },
      {
        title: "Check risk level and time horizon before anything else",
        body: "Every opportunity is tagged with a risk level (Low / Medium / High) and a time horizon (e.g. '3–5 Years'). These aren't decorative — they tell you the kind of position this is (a quick tactical trade vs. a multi-year structural thesis) and should shape how you size or research it.",
      },
      {
        title: "Drill into the underlying events and companies",
        body: "Every opportunity links back to the specific events and companies driving it. Open an opportunity's detail page to see exactly which events fed into the score, rather than treating the score as a black box.",
      },
    ],
    tips: [
      "Sort or filter by sector if you're researching a specific area rather than browsing the full radar.",
      "An opportunity with a high company count and event count usually reflects a broader, more structurally-driven theme than one backed by a single event.",
    ],
    relatedGuides: ["understanding-impact-and-confidence-scores", "understanding-the-ripple-map"],
  },
  {
    slug: "understanding-the-ripple-map",
    title: "Understanding the Ripple Effects Map",
    category: "Intelligence Features",
    summary: "How to read MarketRipple's AI Ripple Map — the visual trace of how a single event's effects flow through sectors, companies, and macro indicators.",
    readTime: "3 min",
    steps: [
      {
        title: "Start at the source event",
        body: "The Ripple Map always begins with the originating event at the top or center — a policy decision, a commodity price move, a corporate result — and branches outward to show what it's expected to affect next.",
      },
      {
        title: "Follow the branches, not just the first layer",
        body: "The first layer of a ripple map (direct sector or index impacts) is usually the least interesting part — the more useful insight is often two or three layers deep, where indirect, less obvious connections show up (for example, a crude oil spike eventually showing up as an inflation-risk flag that could influence RBI policy).",
      },
      {
        title: "Check whether it's a real analysis or a template",
        body: "Every ripple map either reflects a genuine, event-specific AI analysis or, when one hasn't been generated yet for that specific event, a clearly-labeled illustrative template. Look for the 'Illustrative Template' badge — if you see it, treat the map as a general pattern example rather than a specific claim about that event.",
      },
    ],
    tips: [
      "Ripple maps are most useful for building intuition about second-order effects — the connections that aren't obvious from the headline alone.",
    ],
    relatedGuides: ["reading-the-opportunity-radar"],
  },
  {
    slug: "understanding-impact-and-confidence-scores",
    title: "Understanding Impact & Confidence Scores",
    category: "Intelligence Features",
    summary: "Why MarketRipple always shows a score and a confidence level together — and what to do when a score shows as 'Unscored' instead of a number.",
    readTime: "3 min",
    steps: [
      {
        title: "Know what each number means",
        body: "Impact Score (0–100) measures how significant an event or opportunity is expected to be. Confidence (a separate percentage) measures how much real evidence backs that specific score. These are deliberately never combined into one number.",
      },
      {
        title: "Read them together, not separately",
        body: "A 90 Impact Score at 90% confidence is a strong, well-evidenced signal. A 90 Impact Score at 40% confidence means: if this plays out, it matters a great deal — but the evidence behind that expectation is still thin. Treat the second case as worth watching, not acting on.",
      },
      {
        title: "Trust 'Unscored' as an honest answer",
        body: "When you see 'Unscored' or 'Collecting Evidence' instead of a number, that's not a bug or a loading state — it means MarketRipple genuinely doesn't have enough evidence yet to responsibly assign a score. We treat 'we don't know yet' as a legitimate answer rather than filling the gap with a fabricated number.",
      },
      {
        title: "Check the Data Status badge",
        body: "Preliminary, Verified, or Live badges next to a score tell you how mature the underlying evidence is. A Preliminary score was generated the moment an event broke, from limited information — expect it to firm up (or change) as Verified and Live data comes in.",
      },
    ],
    relatedGuides: ["reading-the-market-intelligence-dashboard", "reading-the-opportunity-radar"],
  },
  {
    slug: "using-the-live-intelligence-feed",
    title: "Using the Live Intelligence Feed",
    category: "Intelligence Features",
    summary: "The Live Intelligence Feed streams every new event, score update, and alert in real time — here's how to read it and why it's never simulated.",
    readTime: "2 min",
    steps: [
      {
        title: "Find it on the Live Market tab",
        body: "The Live Intelligence Feed sits on the Live Market tab of the Market Intelligence dashboard and updates continuously over a live connection — no need to refresh the page.",
      },
      {
        title: "Distinguish alerts, updates, and score changes",
        body: "Entries are badged by type: ALERT for high-urgency breaking events, UPDATE for lower-urgency events, and score-change entries (badged Preliminary / Verified / Live) that show when a specific score moved and in which direction.",
      },
      {
        title: "Treat an empty feed as accurate, not broken",
        body: "Outside trading hours, or during genuinely quiet stretches, the feed will show 'Watching for the next real-time signal…' rather than manufacturing activity to look busy. An empty feed means nothing new has genuinely happened yet — that's the feed working correctly.",
      },
    ],
    relatedGuides: ["reading-the-market-intelligence-dashboard"],
  },
];

export function getGuide(slug: string): Guide | undefined {
  return GUIDES.find(g => g.slug === slug);
}

export function getRelatedGuides(guide: Guide): Guide[] {
  return (guide.relatedGuides ?? [])
    .map(slug => getGuide(slug))
    .filter((g): g is Guide => !!g);
}

export const GUIDE_CATEGORIES = Array.from(new Set(GUIDES.map(g => g.category)));
