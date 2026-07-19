/**
 * TypeScript types for the Market Intelligence Engine (MIE).
 *
 * The MIE is the single source of truth for all intelligence in the app.
 * Every page and component must consume from /api/mie/* — never compute
 * intelligence independently.
 */

// ── Story (StoryEngineWorker output) ──────────────────────────────────────────

export interface MIEStory {
  text:            string;
  mood:            string;   // "Bullish" | "Bearish" | "Cautious" | "Neutral"
  pulse:           string;
  direction:       string;   // "up" | "down" | "sideways"
  opportunity:     string;
  risk:            string;
  trader_watch:    string;
  investor_watch:  string;
  confidence:      number;   // 0-100
  sector_rotation: string | null;
  generated_at:    string | null;
}

// ── Theme (ThemeWorker output) ─────────────────────────────────────────────────

export interface MIETheme {
  theme:        string;
  score:        number;
  momentum:     string;    // "rising" | "falling" | "stable"
  top_stocks:   string[];
  price_signal: string | null;
  news_signal:  string | null;
  news_count:   number;
  updated_at:   string | null;
}

// ── Event (TriageWorker output) ────────────────────────────────────────────────

export interface MIEEvent {
  id:            string;
  headline:      string;
  one_liner:     string | null;
  urgency:       number;   // 1-10
  importance:    number;
  confidence:    number;
  sentiment:     string;   // "bullish" | "bearish" | "neutral"
  horizon:       string;   // "short" | "medium" | "long"
  market_impact: string;
  direction:     string;
  is_structural: boolean;
  sectors:       string[];
  themes:        string[];
  tickers:       string[];
  broadcast:     boolean;
  source:        string;
  triaged_at:    string | null;
  // Intelligence Priority Queue — see app.services.intelligence.engine._compute_priority.
  priority_score: number;   // 0-100
  priority_tier:  "Critical" | "High" | "Medium" | "Low";
}

// ── Signals (synthesised by engine) ───────────────────────────────────────────

export interface MIESignals {
  mood:              string;
  direction:         string;
  risk_level:        string;   // "HIGH" | "MODERATE" | "LOW"
  confidence:        number;
  top_theme:         string | null;
  top_theme_score:   number;
  breadth:           string;   // "advancing" | "declining" | "mixed"
  bullish_events:    number;
  bearish_events:    number;
  total_events:      number;
  critical_alerts:   number;
  structural_shifts: number;
}

// ── Newsroom-style summary fields ──────────────────────────────────────────────

export interface MIEOpportunity {
  id:                string;
  slug:              string;
  title:             string;
  summary:           string;
  opportunity_score: number | null;
  confidence:        number | null;
  trend:             string | null;
  risk_level:        string | null;
  sectors:           string[];
}

export interface MIERisk {
  headline:   string | null;
  reason:     string;
  sectors:    string[];
  tickers:    string[];
  confidence: number | null;
}

export interface MIECompanyToWatch {
  ticker:     string;
  why:        string;
  impact:     number | null;   // priority_score of the driving event
  confidence: number | null;
}

export interface MIEMarketDriver {
  headline: string;
  urgency:  number;
}

export interface MIEMarketHealth {
  score: number;   // 0-100
  label: "Healthy" | "Mixed" | "Weak" | "Stressed";
}

export interface MIECalendarEvent {
  id:          string;
  category:    string;
  title:       string;
  date:        string;
  description: string;
}

// ── Full intelligence state ────────────────────────────────────────────────────

export interface MarketIntelligenceState {
  version:        string;
  generated_at:   string;
  market_session: "pre_market" | "live" | "post_market" | "weekend";
  is_market_open: boolean;
  story:          MIEStory | null;
  themes:         MIETheme[];
  top_events:     MIEEvent[];
  signals:        MIESignals;
  sector_themes:  { name: string; score: number; momentum: string }[];
  event_sectors:  { name: string; event_count: number }[];

  market_bias:         string;
  market_health:       MIEMarketHealth;
  ai_summary:           string | null;
  biggest_opportunity: MIEOpportunity | null;
  biggest_risk:        MIERisk | null;
  companies_to_watch:  MIECompanyToWatch[];
  market_drivers:      MIEMarketDriver[];
  strongest_themes:    MIETheme[];
  weakest_themes:      MIETheme[];
  tomorrow_watch:      MIECalendarEvent[];
}

// ── Symbol context ─────────────────────────────────────────────────────────────

export interface SymbolIntelligenceContext {
  symbol:           string;
  generated_at:     string;
  market_session:   string;
  story:            MIEStory | null;
  signals:          MIESignals | null;
  related_events:   MIEEvent[];
  related_themes:   MIETheme[];
  market_mood:      string;
  market_direction: string;
}

// ── Feed item ─────────────────────────────────────────────────────────────────

// The feed is now backed by the same reader as MIEEvent (engine.read_top_events)
// — both /api/mie/feed and /api/intelligence/market/feed return this shape.
export type MIEFeedItem = MIEEvent;

export interface MIEFeed {
  feed:           MIEFeedItem[];
  count:          number;
  min_urgency:    number;
  hours:          number;
  market_session: string;
}

// ── Engine status ─────────────────────────────────────────────────────────────

export interface MIEStatus {
  engine:            string;
  version:           string | null;
  market_session:    string;
  redis_connected:   boolean;
  state_cached:      boolean;
  state_age_seconds: number | null;
  events_processed:  number;
  state_session:     string | null;
  is_fresh:          boolean;
}
