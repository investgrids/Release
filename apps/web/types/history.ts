export type RecentItemType = "event" | "company" | "news" | "story" | "search";

export interface RecentItem {
  id: string;
  title: string;
  subtitle?: string;
  href: string;
  timestamp: number;
  type: RecentItemType;
}

export interface RecentHistory {
  events: RecentItem[];
  companies: RecentItem[];
  news: RecentItem[];
  stories: RecentItem[];
  searches: RecentItem[];
}

// Future: replace with DB-backed user profile
export interface UserPreferences {
  themes: string[];
}
