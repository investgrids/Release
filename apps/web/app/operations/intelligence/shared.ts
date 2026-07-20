export interface FeedArticle {
  id: string;
  slug: string;
  article_type: string;
  angle: string;
  angle_entity: string | null;
  is_evergreen: boolean;
  headline: string;
  key_takeaway: string | null;
  executive_summary: string | null;
  companies_affected: { name: string; symbol: string; impact: string; reason?: string }[];
  sectors_affected: { name: string; impact?: string }[] | string[];
  confidence_score: number | null;
  update_count: number;
  published_at: string | null;
  last_updated: string | null;
}

export const TYPE_LABEL: Record<string, string> = {
  breaking_intelligence:    "Breaking",
  morning_intelligence:     "Morning Brief",
  company_intelligence:     "Company",
  sector_intelligence:      "Sector",
  theme_intelligence:       "Theme",
  policy_intelligence:      "Policy",
  ripple_intelligence:      "Ripple",
  opportunity_intelligence: "Opportunity",
  market_wrap:              "Market Wrap",
  weekly_intelligence:      "Weekly",
  monthly_intelligence:     "Monthly",
  educational_intelligence: "Education",
  question_intelligence:    "Q&A",
  historical_intelligence:  "Historical",
};

export function fmtRelative(iso: string | null): string {
  if (!iso) return "";
  const hasOffset = /[zZ]|[+-]\d\d:\d\d$/.test(iso);
  const t = new Date(hasOffset ? iso : iso + "Z").getTime();
  if (Number.isNaN(t)) return "";
  const diffMin = Math.floor((Date.now() - t) / 60000);
  if (diffMin < 1) return "just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  const hr = Math.floor(diffMin / 60);
  if (hr < 24) return `${hr}h ago`;
  const day = Math.floor(hr / 24);
  if (day < 7) return `${day}d ago`;
  return new Date(t).toLocaleDateString("en-IN", { day: "numeric", month: "short" });
}

export function sectorName(s: { name?: string } | string): string {
  return typeof s === "string" ? s : (s.name ?? "");
}
