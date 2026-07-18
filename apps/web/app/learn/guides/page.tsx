import type { Metadata } from "next";
import Link from "next/link";
import { Clock, ChevronRight } from "lucide-react";
import { GUIDES, GUIDE_CATEGORIES } from "@/lib/guides-data";

export const metadata: Metadata = {
  title: "Product Guides — How to Use MarketRipple",
  description:
    "Step-by-step guides to MarketRipple's real features — the Market Intelligence dashboard, AI Search, Opportunity Radar, Ripple Maps, and Impact/Confidence scores.",
  openGraph: {
    title: "Product Guides — How to Use MarketRipple",
    description: "Step-by-step guides to MarketRipple's real features.",
  },
};

export default function GuidesIndexPage() {
  return (
    <div className="space-y-8">
      <div>
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">Knowledge Library</p>
        <h1 className="mt-3 text-[26px] font-black leading-tight text-white md:text-[32px]">Product Guides</h1>
        <p className="mt-3 max-w-2xl text-[14px] leading-6 text-slate-400">
          How to actually use MarketRipple's real, shipped features — not marketing copy, step-by-step walkthroughs.
        </p>
      </div>

      {GUIDE_CATEGORIES.map(category => {
        const guides = GUIDES.filter(g => g.category === category);
        return (
          <section key={category}>
            <h2 className="mb-3 text-[11px] font-bold uppercase tracking-[0.14em] text-slate-500">{category}</h2>
            <div className="space-y-2.5">
              {guides.map(guide => (
                <Link
                  key={guide.slug}
                  href={`/learn/guides/${guide.slug}` as any}
                  className="flex items-center gap-4 rounded-xl border border-white/[0.07] bg-[#080c14] p-4 transition hover:border-violet-500/20 hover:bg-[#0a102c]"
                >
                  <div className="min-w-0 flex-1">
                    <h3 className="text-[14px] font-bold text-white">{guide.title}</h3>
                    <p className="mt-1 line-clamp-2 text-[12px] leading-5 text-slate-500">{guide.summary}</p>
                    <span className="mt-2 flex items-center gap-1 text-[10px] text-slate-600">
                      <Clock className="h-3 w-3" /> {guide.readTime} read · {guide.steps.length} steps
                    </span>
                  </div>
                  <ChevronRight className="h-4 w-4 shrink-0 text-slate-700" />
                </Link>
              ))}
            </div>
          </section>
        );
      })}
    </div>
  );
}
