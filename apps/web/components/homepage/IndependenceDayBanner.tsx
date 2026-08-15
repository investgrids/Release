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

const TRICOLOR = ["#FF9933", "#FFD700", "#138808", "#FF6B6B"];

function Firework({ x, delay }: { x: string; delay: string }) {
  const particles = Array.from({ length: 10 }, (_, i) => ({
    angle: (360 / 10) * i,
    color: TRICOLOR[i % TRICOLOR.length],
    pdelay: `${(i % 3) * 0.06}s`,
  }));
  return (
    <div className="absolute top-1/2 -translate-y-1/2" style={{ left: x }} aria-hidden>
      {particles.map((p, i) => (
        <span
          key={i}
          className="mr-id-particle"
          style={{
            // @ts-expect-error -- CSS custom properties
            "--pangle": `${p.angle}deg`,
            "--pcolor": p.color,
            "--pdelay": p.pdelay,
            animationDelay: `calc(${delay} + ${p.pdelay})`,
          }}
        />
      ))}
    </div>
  );
}

export function IndependenceDayBanner() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (isTodayIST(SHOW_DATE) && localStorage.getItem(DISMISS_KEY) !== "1") {
      setVisible(true);
    }
  }, []);

  if (!visible) return null;

  // Sparkle field — bigger and clearly inside the visible frame this time
  // (the first pass positioned them small and mostly off the top edge,
  // easy to miss entirely).
  const sparkles = [
    { Icon: Sparkles, top: "12%", left: "8%",  size: 20, delay: "0s"   },
    { Icon: Star,     top: "62%", left: "4%",  size: 14, delay: "0.5s" },
    { Icon: Star,     top: "18%", left: "93%", size: 16, delay: "0.8s" },
    { Icon: Sparkles, top: "60%", left: "97%", size: 18, delay: "0.2s" },
  ];

  return (
    <div className="relative">
      <style>{`
        @keyframes mr-id-twinkle {
          0%, 100% { opacity: 0.15; transform: scale(0.6) rotate(0deg); }
          50%      { opacity: 1;    transform: scale(1.15) rotate(15deg); }
        }
        .mr-id-sparkle { animation: mr-id-twinkle 2s ease-in-out infinite; }

        .mr-id-particle {
          position: absolute;
          top: 0; left: 0;
          width: 6px; height: 6px;
          margin: -3px 0 0 -3px;
          border-radius: 9999px;
          background: var(--pcolor);
          box-shadow: 0 0 4px 1px var(--pcolor);
          opacity: 0;
          animation: mr-id-pop 2.6s ease-out infinite;
          animation-delay: var(--pdelay);
        }
        @keyframes mr-id-pop {
          0%   { transform: rotate(var(--pangle)) translateX(0px) scale(1);   opacity: 0; }
          8%   { opacity: 1; }
          55%  { opacity: 0.9; }
          100% { transform: rotate(var(--pangle)) translateX(26px) scale(0.4); opacity: 0; }
        }

        @media (prefers-reduced-motion: reduce) {
          .mr-id-sparkle, .mr-id-particle { animation: none; opacity: 0.4; }
        }
      `}</style>

      {sparkles.map(({ Icon, top, left, size, delay }, i) => (
        <Icon
          key={i}
          aria-hidden
          className="mr-id-sparkle pointer-events-none absolute z-10 text-[#FF9933] drop-shadow-sm dark:text-amber-300"
          style={{ top, left, width: size, height: size, animationDelay: delay }}
        />
      ))}
      <Firework x="20%" delay="0s" />
      <Firework x="80%" delay="1.1s" />

      <div className="relative flex items-center gap-3 overflow-hidden rounded-2xl border border-surface-border/7 bg-surface-card px-5 py-3">
        <div className="absolute inset-y-0 left-0 w-1 bg-gradient-to-b from-[#FF9933] via-white to-[#138808]" />
        <p className="min-w-0 flex-1 pl-2 text-[13px] text-text-primary">
          <span className="font-bold">Happy 80th Independence Day.</span>{" "}
          <span className="text-text-secondary">Markets are closed today for the national holiday — regular live coverage resumes next trading session.</span>
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
