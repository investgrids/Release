"use client";

import { useRouter } from "next/navigation";

interface Props {
  label: string;
  currentSort: string;
  baseParamsString: string;
  // "ticker" sorts A-Z only (single direction, per spec). "score" toggles
  // score_desc <-> score_asc on each double-click.
  kind: "ticker" | "score";
}

// Double-click to sort (owner instruction, 2026-09-27) -- Ticker sorts
// A-Z; Score alternates high-to-low / low-to-high on each double-click,
// defaulting to high-to-low the first time. A client component because
// the rest of this table is server-rendered; this is the one interactive
// affordance in the header row.
export function SortableHeaderCell({ label, currentSort, baseParamsString, kind }: Props) {
  const router = useRouter();

  function nextSort(): string {
    if (kind === "ticker") return "ticker";
    return currentSort === "score_desc" ? "score_asc" : "score_desc";
  }

  function handleDoubleClick() {
    const sp = new URLSearchParams(baseParamsString);
    sp.set("tab", "all-companies");
    sp.set("sort", nextSort());
    sp.set("page", "1");
    router.push(`/companies?${sp.toString()}`);
  }

  const isActive = kind === "ticker" ? currentSort === "ticker" : currentSort === "score_desc" || currentSort === "score_asc";
  const arrow = kind === "score" ? (currentSort === "score_asc" ? " ↑" : currentSort === "score_desc" ? " ↓" : "") : "";

  return (
    <span
      onDoubleClick={handleDoubleClick}
      title={`Double-click to sort by ${label.toLowerCase()}`}
      className={`cursor-pointer select-none transition ${isActive ? "text-text-primary" : "hover:text-text-secondary"}`}
    >
      {label}{arrow}
    </span>
  );
}
