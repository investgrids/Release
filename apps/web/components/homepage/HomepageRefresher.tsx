"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { API_BASE_URL as API } from "@/lib/api";

const INTERVAL = 5 * 60 * 1000; // 5 minutes

export function HomepageRefresher() {
  const router    = useRouter();
  const hashRef   = useRef<string | null>(null);
  const [toast, setToast] = useState(false);

  useEffect(() => {
    let toastTimer: ReturnType<typeof setTimeout>;

    const check = async () => {
      try {
        const r = await fetch(`${API}/api/intelligence/market/story`, { cache: "no-store" });
        if (!r.ok) return;
        const data = await r.json();
        const hash = data?.story?.story_hash as string | undefined;
        if (!hash) return;

        if (hashRef.current === null) {
          hashRef.current = hash;
          return;
        }
        if (hash !== hashRef.current) {
          hashRef.current = hash;
          router.refresh();
          setToast(true);
          clearTimeout(toastTimer);
          toastTimer = setTimeout(() => setToast(false), 4_000);
        }
      } catch { /* backend offline */ }
    };

    check();
    const id = setInterval(check, INTERVAL);
    return () => { clearInterval(id); clearTimeout(toastTimer); };
  }, [router]);

  if (!toast) return null;

  return (
    <div className="fixed left-1/2 top-20 z-50 -translate-x-1/2">
      <div className="flex items-center gap-2 rounded-full border border-violet-500/35 bg-[#0d0820]/95 px-4 py-2 text-[12px] font-semibold text-violet-300 shadow-xl backdrop-blur">
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-violet-400" />
        Market intelligence updated
      </div>
    </div>
  );
}
