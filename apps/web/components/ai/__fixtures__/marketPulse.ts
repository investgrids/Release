// Representative fixtures for market_pulse (2026-09-22, canonical-core
// audit), mirroring exactly what aev2/market_pulse.py's
// assemble_market_pulse() produces server-side — see that module's own
// docstring and test_market_pulse_assembly.py for the real backend
// behavior these mirror. Unlike every other AEV2 fixture file, there is
// no baseAev2Response() here to extend — AEV2MarketPulse is a fully
// separate top-level shape, never nested inside AEV2Response.
import type { SearchResult } from "@/app/ai-search/AISearchClient";
import type { AEV2MarketPulse } from "../aev2Types";
import { baseSearchResult } from "./directCompanyResearch";

export function baseMarketPulseSearchResult(overrides: Record<string, unknown> = {}): SearchResult {
  return baseSearchResult({
    query: "top gainers and losers today",
    ui_mode: "market_pulse",
    intent: "market_pulse",
    ...overrides,
  });
}

export function baseMarketPulse(overrides: Partial<AEV2MarketPulse> = {}): AEV2MarketPulse {
  return {
    kind: "market_pulse",
    as_of: "2026-09-22T10:06:08+00:00",
    market_session: "live",
    market_status: "open",
    indices: [{
      name: "NIFTY 50", ticker: "^NSEI",
      price: { value: "23,329.00", as_of: "2026-09-22T10:06:08+00:00", source: "yfinance_nse_index", session: "live" },
      change: { value: "-0.43%", as_of: "2026-09-22T10:06:08+00:00", source: "yfinance_nse_index", session: "live" },
      chart: [
        { label: "2026-09-18", value: 23346.4 },
        { label: "2026-09-19", value: 23390.1 },
        { label: "2026-09-21", value: 23414.3 },
        { label: "2026-09-22", value: 23329.0 },
      ],
    }],
    sector_movement: {
      leading: [{
        id: "realty", name: "Realty",
        change: { value: "+0.5%", as_of: "2026-09-22T10:06:08+00:00", source: "yfinance_sector_etf", session: "live" },
        momentum_score: 57.5,
      }],
      lagging: [{
        id: "it", name: "IT",
        change: { value: "-0.9%", as_of: "2026-09-22T10:06:08+00:00", source: "yfinance_sector_etf", session: "live" },
        momentum_score: 20.0,
      }],
    },
    movers: {
      gainers: [{
        company: "Coal India", ticker: "COALINDIA",
        price: { value: "428.00", as_of: "2026-09-22T10:06:08+00:00", source: "yfinance_top_movers", session: "live" },
        change: { value: "+3.21%", as_of: "2026-09-22T10:06:08+00:00", source: "yfinance_top_movers", session: "live" },
        verified_drivers: [],
        narrative: "No verified driver identified for this move — likely broad-market or idiosyncratic trading.",
      }],
      losers: [{
        company: "Reliance Industries", ticker: "RELIANCE",
        price: { value: "1,257.50", as_of: "2026-09-22T10:06:08+00:00", source: "yfinance_top_movers", session: "live" },
        change: { value: "-1.20%", as_of: "2026-09-22T10:06:08+00:00", source: "yfinance_top_movers", session: "live" },
        verified_drivers: [{
          driver: "Weak Results", driver_type: "corporate_results", confidence_tier: "High",
          driver_strength: 80.0, evidence_refs: ["event:evt-reliance-1"],
        }],
        narrative: "Reliance declined after weaker-than-expected quarterly results.",
      }],
      most_active: [],
    },
    theme_momentum: [
      { theme: "Banking", score: 61.0, momentum: "rising", price_signal: 0.8, news_signal: 40.0 },
    ],
    biggest_opportunity: { title: "IPO rush: 9 companies to launch issues this week", href: "/opportunity-radar/36", opportunity_score: 98.0 },
    risk_context: {
      source: "tracked_event", event_id: "evt-risk-1", title: "FII outflows accelerate on global risk-off sentiment",
      published_at: "2026-09-22T09:00:00+00:00", evidence_refs: ["event:evt-risk-1"],
    },
    upcoming_events: [
      { id: "cal-1", title: "RBI Policy Meeting", date: "Sep 28, 2026", category: "rbi", description: "High importance. Source: RBI." },
    ],
    generated_summary: {
      text: "Markets traded mixed today, with Coal India leading gainers and Reliance Industries among the top losers.",
      evidence_refs: [], validation_status: "validated",
    },
    generated_conclusion: {
      text: "Today's move looks narrow, concentrated in a handful of names rather than broad-based across sectors.",
      evidence_refs: [], validation_status: "validated",
    },
    synthesis_status: "complete",
    evidence_coverage: { movers_with_driver: 1, movers_total: 2, tracked_event_count: 1, calendar_event_count: 1 },
    ...overrides,
  };
}

// 1. Complete, fully synthesized market pulse.
export const completeMarketPulseAnswer = {
  result: baseMarketPulseSearchResult(),
  aev2: baseMarketPulse(),
};

// 2. Structured-complete, synthesis unavailable (advisory-language
// violation or failed citation validation upstream) — every real field
// still present, only the generated prose is missing.
export const synthesisUnavailableMarketPulseAnswer = {
  result: baseMarketPulseSearchResult(),
  aev2: baseMarketPulse({
    generated_summary: null,
    generated_conclusion: null,
    synthesis_status: "unavailable",
    movers: {
      ...baseMarketPulse().movers,
      gainers: [{ ...baseMarketPulse().movers.gainers[0], narrative: null }],
      losers: [{ ...baseMarketPulse().movers.losers[0], narrative: null }],
    },
  }),
};

// 3. AI-synthesized risk consideration — currently unreachable from the
// real backend (aev2/market_pulse.py never emits this branch, since it
// has no real evidence_refs to back it — see that module's own
// docstring), kept here only to exercise the type/label rendering path
// itself in isolation.
export const aiSynthesisRiskMarketPulseAnswer = {
  result: baseMarketPulseSearchResult(),
  aev2: baseMarketPulse({
    risk_context: {
      source: "ai_synthesis",
      text: "Renewed FII outflows could pressure markets in the near term.",
      validation_status: "validated",
      evidence_refs: [],
    },
  }),
};

// 4. No tracked risk and no AI synthesis — honestly null.
export const noRiskMarketPulseAnswer = {
  result: baseMarketPulseSearchResult(),
  aev2: baseMarketPulse({ risk_context: null }),
};

// 5. No public Opportunity resolves.
export const noOpportunityMarketPulseAnswer = {
  result: baseMarketPulseSearchResult(),
  aev2: baseMarketPulse({ biggest_opportunity: null }),
};

// 6. Degraded response — never reaches the successful layout.
export const marketPulseSynthesisIncompleteAnswer = {
  result: baseMarketPulseSearchResult({ synthesis_incomplete: true }),
  aev2: baseMarketPulse(),
};

// 7. No verified drivers on any mover — honest, not fabricated.
export const noDriversMarketPulseAnswer = {
  result: baseMarketPulseSearchResult(),
  aev2: baseMarketPulse({
    movers: {
      gainers: [{ ...baseMarketPulse().movers.gainers[0], verified_drivers: [] }],
      losers: [{ ...baseMarketPulse().movers.losers[0], verified_drivers: [] }],
      most_active: [],
    },
    evidence_coverage: { movers_with_driver: 0, movers_total: 2, tracked_event_count: 0, calendar_event_count: 1 },
  }),
};
