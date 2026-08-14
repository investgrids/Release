export interface FeedbackOption {
  key: string;
  label: string;
}

export const REASON_OPTIONS: FeedbackOption[] = [
  { key: "research_company", label: "Research a company" },
  { key: "check_market", label: "Check what's happening in the market" },
  { key: "find_events", label: "Find important events or opportunities" },
  { key: "ask_ai_search", label: "Ask AI Search a question" },
  { key: "explore_intelligence", label: "Explore Market Ripple intelligence" },
  { key: "check_last_visit", label: "Check something from my last visit" },
  { key: "other", label: "Something else" },
];

export const IMPROVEMENT_OPTIONS: FeedbackOption[] = [
  { key: "actionable_conclusions", label: "More actionable investment conclusions" },
  { key: "faster_alerts", label: "Faster market-moving alerts" },
  { key: "deeper_company_intel", label: "Deeper company intelligence" },
  { key: "event_news_coverage", label: "Better event and news coverage" },
  { key: "portfolio_intelligence", label: "Portfolio intelligence" },
  { key: "more_opportunities", label: "More opportunities and emerging themes" },
  { key: "other", label: "Something else" },
];

export interface ReturningUserFeedbackPayload {
  name?: string;
  email?: string;
  reasons: string[];
  improvements: string[];
  other_reason?: string;
  other_improvement?: string;
  additional_feedback?: string;
  visit_count: number;
  page: string;
  device_category?: string;
  referrer?: string;
  timestamp: string;
}
