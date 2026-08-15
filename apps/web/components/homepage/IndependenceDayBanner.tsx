"use client";

import { useEffect, useState } from "react";
import { X, Sparkles, Star } from "lucide-react";

// One-day banner for India's 80th Independence Day (Aug 15, 2026). Scoped to
// this exact date rather than "any Aug 15" so it doesn't silently resurface
// next year with a stale "80th" count — bump the date/copy by hand if this
// is wanted again for the 81st.
const SHOW_DATE = "2026-08-15";
const DISMISS_KEY = "mr-independence-day-2026-dismissed";

function isTodayIST(dateStr: string): boolean {
  const ist = new Date(Date.now() + 5.5 * 60 * 60 * 1000);
  return ist.toISOString().slice(0, 10) === dateStr;
}

export function IndependenceDayBanner() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (isTodayIST(SHOW_DATE) && localStorage.getItem(DISMISS_KEY) !== "1") {
      setVisible(true);
    }
  }, []);

  if (!visible) return null;

  // Sparkle field: a handful of small icons twinkling around the banner's
  // edges. Purely decorative for the one day this renders — kept out of
  // Tailwind config since it doesn't need to exist tomorrow.
  const sparkles = [
    { Icon: Sparkles, top: "-10%", left: "6%",  size: 14, delay: "0s"    },
    { Icon: Star,     top: "70%",  left: "3%",  size: 9,  delay: "0.6s"  },
    { Icon: Sparkles, top: "10%",  left: "97%", size: 11, delay: "0.3s"  },
    { Icon: Star,     top: "80%",  left: "94%", size: 13, delay: "0.9s"  },
    { Icon: Sparkles, top: "-15%", left: "50%", size: 10, delay: "1.2s"  },
  ];

  return (
    <div className="relative">
      <style>{`
        @keyframes mr-id-twinkle {
          0%, 100% { opacity: 0; transform: scale(0.4) rotate(0deg); }
          50%      { opacity: 1; transform: scale(1) rotate(12deg); }
        }
        .mr-id-sparkle { animation: mr-id-twinkle 2.4s ease-in-out infinite; }
        @media (prefers-reduced-motion: reduce) {
          .mr-id-sparkle { animation: none; opacity: 0.5; }
        }
      `}</style>

      {sparkles.map(({ Icon, top, left, size, delay }, i) => (
        <Icon
          key={i}
          aria-hidden
          className="mr-id-sparkle pointer-events-none absolute text-[#FF9933] dark:text-amber-300"
          style={{ top, left, width: size, height: size, animationDelay: delay }}
        />
      ))}

      <div className="relative flex items-center gap-3 overflow-hidden rounded-2xl border border-surface-border/7 bg-surface-card px-5 py-3">
        <div className="absolute inset-y-0 left-0 w-1 bg-gradient-to-b from-[#FF9933] via-white to-[#138808]" />
        <p className="min-w-0 flex-1 pl-2 text-[13px] text-text-primary">
          <span className="font-bold">Happy 80th Independence Day.</span>{" "}
          <span className="text-text-secondary">Markets are closed today for the national holiday — live coverage resumes tomorrow.</span>
        </p>
        <button
          onClick={() => { localStorage.setItem(DISMISS_KEY, "1"); setVisible(false); }}
          aria-label="Dismiss"
          className="shrink-0 rounded-full p-1 text-text-muted transition hover:bg-text-primary/[0.06] hover:text-text-secondary"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}
