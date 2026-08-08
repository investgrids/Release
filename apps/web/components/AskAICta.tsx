"use client";

import Link from "next/link";
import { trackEvent } from "@/lib/analytics";
import { truncateForQuery } from "@/lib/text";

/**
 * Small client island for the "Ask MarketRipple AI" CTA used on server-
 * rendered pages (sector, research) — the page itself stays a Server
 * Component; only this one interactive link needs to be a client boundary.
 * Fires a real GA4 event (ai_search_cta_click) so "AI Search conversion
 * from a landing page" — one of the audit's own §10 metrics — is actually
 * measurable, not just recommended.
 */
export function AskAICta({ query, source }: { query: string; source: string }) {
  return (
    <Link
      href={`/ai-search?q=${encodeURIComponent(truncateForQuery(query))}` as any}
      onClick={() => trackEvent("ai_search_cta_click", { source })}
      className="font-semibold text-violet-600 dark:text-violet-300 hover:text-violet-700 dark:text-violet-200 transition"
    >
      Ask MarketRipple AI →
    </Link>
  );
}
