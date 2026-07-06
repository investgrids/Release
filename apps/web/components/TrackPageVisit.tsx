"use client";

import { useEffect } from "react";
import { HISTORY_KEYS } from "@/hooks/useRecentHistory";
import type { RecentItemType } from "@/types/history";

interface TrackPageVisitProps {
  type: RecentItemType;
  id: string;
  title: string;
  subtitle?: string;
  href: string;
}

const LIMITS: Record<RecentItemType, number> = {
  event: 10, company: 10, news: 10, story: 10, search: 20,
};

const KEY_FOR_TYPE: Record<RecentItemType, string> = {
  event:   HISTORY_KEYS.events,
  company: HISTORY_KEYS.companies,
  news:    HISTORY_KEYS.news,
  story:   HISTORY_KEYS.stories,
  search:  HISTORY_KEYS.searches,
};

/**
 * Invisible component — call once per detail page with the loaded item's data.
 * Renders null; only runs the tracking side-effect on mount.
 *
 * Example:
 *   {article && <TrackPageVisit type="news" id={article.id} title={article.headline} href={`/news/${article.id}`} />}
 */
export function TrackPageVisit({ type, id, title, subtitle, href }: TrackPageVisitProps) {
  useEffect(() => {
    if (!id || !title) return;
    const key = KEY_FOR_TYPE[type];
    const limit = LIMITS[type];
    try {
      const existing = JSON.parse(localStorage.getItem(key) ?? "[]");
      const filtered = existing.filter((i: { id: string }) => i.id !== id);
      const item = { id, title, subtitle, href, type, timestamp: Date.now() };
      localStorage.setItem(key, JSON.stringify([item, ...filtered].slice(0, limit)));
    } catch {}
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);  // only re-run when id changes (i.e., page navigates to a different item)

  return null;
}
