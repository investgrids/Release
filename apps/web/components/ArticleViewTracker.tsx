"use client";

import { useEffect } from "react";
import { API_BASE_URL as API } from "@/lib/api";

/**
 * Records one "engaged read" per visitor per article per day — fires after
 * the reader has actually spent time on the page, not on mount, so a bounce
 * (tab closed in the first second) doesn't count as a view. The backend
 * still dedupes server-side (Redis, 24h), so a remount/rerender here can't
 * inflate the count either.
 */
const ENGAGED_READ_DELAY_MS = 8000;

export function ArticleViewTracker({ slug }: { slug: string }) {
  useEffect(() => {
    if (document.visibilityState !== "visible") return;

    const timer = setTimeout(() => {
      if (document.visibilityState !== "visible") return;
      fetch(`${API}/api/insights/${slug}/view`, { method: "POST", keepalive: true }).catch(() => {});
    }, ENGAGED_READ_DELAY_MS);

    return () => clearTimeout(timer);
  }, [slug]);

  return null;
}
