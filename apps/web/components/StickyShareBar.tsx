"use client";

import { useEffect, useState } from "react";
import { ShareInsightCard, type ShareInsightType } from "@/components/ShareInsightCard";

/** Floating share affordance that appears once the reader has scrolled past
 * the hero (where the primary Share button already lives) — so sharing stays
 * reachable through a long article without pinning a whole bar to the
 * viewport for the entire read. */
export function StickyShareBar({
  title, summary, entityType, entityId, shareCount,
}: {
  title: string;
  summary?: string;
  entityType: ShareInsightType;
  entityId: string;
  shareCount?: number;
}) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const onScroll = () => setVisible(window.scrollY > 480);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <div
      className={`fixed bottom-6 right-6 z-50 transition-all duration-300 ${
        visible ? "translate-y-0 opacity-100" : "pointer-events-none translate-y-3 opacity-0"
      }`}
    >
      <ShareInsightCard
        entityType={entityType}
        entityId={entityId}
        title={title}
        summary={summary}
        shareCount={shareCount}
        className="shadow-2xl shadow-black/60"
      />
    </div>
  );
}
