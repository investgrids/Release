"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { RefreshCw } from "lucide-react";

export function RefreshButton() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);

  return (
    <button
      onClick={() => {
        setLoading(true);
        router.refresh();
        setTimeout(() => setLoading(false), 1500);
      }}
      disabled={loading}
      className="inline-flex items-center gap-1.5 rounded-lg border border-surface-border/15 bg-surface-card px-3 py-1.5 text-[11.5px] font-semibold text-text-secondary transition hover:text-text-primary disabled:opacity-50"
    >
      <RefreshCw className={`h-3 w-3 ${loading ? "animate-spin" : ""}`} /> Refresh Analysis
    </button>
  );
}
