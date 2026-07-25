"use client";

import { Bookmark } from "lucide-react";
import { useArticleBookmarks } from "@/hooks/useArticleBookmarks";

export function BookmarkButton({
  slug, headline, articleType, className = "",
}: {
  slug: string;
  headline: string;
  articleType: string;
  className?: string;
}) {
  const { isBookmarked, toggle } = useArticleBookmarks();
  const active = isBookmarked(slug);

  return (
    <button
      type="button"
      aria-label={active ? "Remove bookmark" : "Bookmark this article"}
      aria-pressed={active}
      onClick={(e) => {
        e.preventDefault();
        e.stopPropagation();
        toggle({ slug, headline, articleType });
      }}
      className={`rounded-lg p-1.5 transition ${active ? "text-violet-400" : "text-slate-500 hover:text-slate-300"} ${className}`}
    >
      <Bookmark className="h-4 w-4" fill={active ? "currentColor" : "none"} />
    </button>
  );
}
