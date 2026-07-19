"use client";

import Link from "next/link";
import { useMarketIntelligence } from "@/hooks/useMarketIntelligence";

function moodIcon(mood: string) {
  const m = (mood ?? "").toLowerCase();
  if (/bull|strong|positive/.test(m)) return "↗";
  if (/bear|weak|negative/.test(m)) return "↘";
  return "→";
}

function moodTheme(mood: string) {
  const m = (mood ?? "").toLowerCase();
  if (/bull|strong|positive/.test(m))
    return { wrap: "border-emerald-500/20 bg-emerald-500/[0.05]", icon: "text-emerald-400", label: "text-emerald-500", text: "text-emerald-200/80", link: "text-emerald-400 hover:text-emerald-300" };
  if (/bear|weak|negative/.test(m))
    return { wrap: "border-rose-500/20 bg-rose-500/[0.05]", icon: "text-rose-400", label: "text-rose-500", text: "text-rose-200/80", link: "text-rose-400 hover:text-rose-300" };
  return { wrap: "border-amber-500/20 bg-amber-500/[0.05]", icon: "text-amber-400", label: "text-amber-500", text: "text-amber-200/80", link: "text-amber-400 hover:text-amber-300" };
}

export function MarketContextStrip() {
  const { state } = useMarketIntelligence();
  const story = state?.story;

  if (!story) return null;

  const sentences = story.text?.split(/(?<=[.!?])\s+/) ?? [];
  const first  = sentences[0]?.trim() ?? "";
  const second = sentences[1]?.trim() ?? story.pulse ?? "";
  const t = moodTheme(story.mood);

  return (
    <div className={`mb-5 flex items-start gap-3 rounded-2xl border px-4 py-3 ${t.wrap}`}>
      <span className={`mt-0.5 shrink-0 text-[16px] font-black leading-none ${t.icon}`}>
        {moodIcon(story.mood)}
      </span>
      <div className="min-w-0 flex-1">
        <p className={`text-[10px] font-black uppercase tracking-[0.18em] mb-0.5 ${t.label}`}>
          Market Strategist · Now
        </p>
        <p className={`text-[12px] leading-5 font-medium ${t.text}`}>
          {first}{second ? ` ${second}` : ""}
        </p>
      </div>
      <Link
        href="/market-intelligence"
        className={`mt-0.5 shrink-0 whitespace-nowrap text-[11px] font-bold transition ${t.link}`}
      >
        Full Brief →
      </Link>
    </div>
  );
}
