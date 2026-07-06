"use client";
import { useState, useEffect, useCallback } from "react";
import type { RecentItem, RecentHistory } from "@/types/history";

export const HISTORY_KEYS = {
  events:    "recent_events",
  companies: "recent_companies",
  news:      "recent_news",
  stories:   "recent_stories",
  searches:  "recent_ai_searches",
} as const;

const LIMITS = { events: 10, companies: 10, news: 10, stories: 10, searches: 20 };

function safeRead(key: string): RecentItem[] {
  try {
    const s = localStorage.getItem(key);
    return s ? JSON.parse(s) : [];
  } catch {
    return [];
  }
}

function pushItem(
  key: string,
  item: Omit<RecentItem, "timestamp">,
  limit: number
): RecentItem[] {
  const list = safeRead(key).filter(i => i.id !== item.id);
  const next: RecentItem[] = [{ ...item, timestamp: Date.now() }, ...list].slice(0, limit);
  try { localStorage.setItem(key, JSON.stringify(next)); } catch {}
  return next;
}

const EMPTY: RecentHistory = {
  events: [], companies: [], news: [], stories: [], searches: [],
};

/**
 * Manages all recent-history lists.
 * Each tracker (trackEvent, trackCompany, …) writes to localStorage and
 * updates React state, so the UI stays in sync without a full reload.
 *
 * Future: replace safeRead / pushItem with API calls once auth is added.
 */
export function useRecentHistory() {
  const [history, setHistory] = useState<RecentHistory>(EMPTY);

  useEffect(() => {
    setHistory({
      events:    safeRead(HISTORY_KEYS.events),
      companies: safeRead(HISTORY_KEYS.companies),
      news:      safeRead(HISTORY_KEYS.news),
      stories:   safeRead(HISTORY_KEYS.stories),
      searches:  safeRead(HISTORY_KEYS.searches),
    });
  }, []);

  const trackEvent = useCallback((item: Omit<RecentItem, "type" | "timestamp">) => {
    const next = pushItem(HISTORY_KEYS.events, { ...item, type: "event" }, LIMITS.events);
    setHistory(h => ({ ...h, events: next }));
  }, []);

  const trackCompany = useCallback((item: Omit<RecentItem, "type" | "timestamp">) => {
    const next = pushItem(HISTORY_KEYS.companies, { ...item, type: "company" }, LIMITS.companies);
    setHistory(h => ({ ...h, companies: next }));
  }, []);

  const trackNews = useCallback((item: Omit<RecentItem, "type" | "timestamp">) => {
    const next = pushItem(HISTORY_KEYS.news, { ...item, type: "news" }, LIMITS.news);
    setHistory(h => ({ ...h, news: next }));
  }, []);

  const trackStory = useCallback((item: Omit<RecentItem, "type" | "timestamp">) => {
    const next = pushItem(HISTORY_KEYS.stories, { ...item, type: "story" }, LIMITS.stories);
    setHistory(h => ({ ...h, stories: next }));
  }, []);

  const trackSearch = useCallback((query: string) => {
    if (!query.trim()) return;
    const item: Omit<RecentItem, "timestamp"> = {
      id: `s-${query.slice(0, 40)}`,
      title: query.trim(),
      href: `/ai-search?q=${encodeURIComponent(query.trim())}`,
      type: "search",
    };
    const next = pushItem(HISTORY_KEYS.searches, item, LIMITS.searches);
    setHistory(h => ({ ...h, searches: next }));
  }, []);

  // The single most recent item across all types
  const lastViewed: RecentItem | null = [
    ...history.events,
    ...history.companies,
    ...history.news,
    ...history.stories,
  ].sort((a, b) => b.timestamp - a.timestamp)[0] ?? null;

  return {
    history,
    trackEvent, trackCompany, trackNews, trackStory, trackSearch,
    lastViewed,
  };
}
