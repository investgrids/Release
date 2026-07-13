"use client";

import { Bookmark } from "lucide-react";
import { useWatchlist, type WatchlistItem } from "@/hooks/useWatchlist";

interface Props {
  item: Omit<WatchlistItem, "addedAt">;
  size?: "sm" | "md";
  className?: string;
}

export function WatchlistButton({ item, size = "md", className = "" }: Props) {
  const { toggle, isWatched } = useWatchlist();
  const watched = isWatched(item.id);
  const dim = size === "sm" ? 13 : 15;

  return (
    <button
      onClick={e => { e.preventDefault(); e.stopPropagation(); toggle(item); }}
      title={watched ? "Remove from watchlist" : "Add to watchlist"}
      className={className}
      style={{
        display: "inline-flex", alignItems: "center", justifyContent: "center",
        width: size === "sm" ? 26 : 30, height: size === "sm" ? 26 : 30,
        borderRadius: 8, border: "none", cursor: "pointer", transition: "all 0.15s",
        background: watched ? "rgba(124,58,237,0.18)" : "rgba(255,255,255,0.06)",
        color: watched ? "#a78bfa" : "#475569",
        flexShrink: 0,
      }}
    >
      <Bookmark
        width={dim} height={dim}
        fill={watched ? "currentColor" : "none"}
        style={{ transition: "fill 0.15s" }}
      />
    </button>
  );
}
