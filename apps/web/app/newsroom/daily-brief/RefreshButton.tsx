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
      className="inline-flex items-center gap-1.5 rounded-lg border border-[#6366F1]/25 bg-[#6366F1]/[0.07] px-3.5 py-2 text-[12px] font-semibold text-[#4f46e5] transition hover:bg-[#6366F1]/[0.12] disabled:opacity-50 dark:text-indigo-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#6366F1]"
    >
      <RefreshCw className={`h-3 w-3 ${loading ? "animate-spin" : ""}`} /> Refresh Analysis
    </button>
  );
}
