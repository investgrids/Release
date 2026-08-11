import type { Metadata } from "next";
import Link from "next/link";
import { Clock, ChevronRight } from "lucide-react";
import { GUIDES, GUIDE_CATEGORIES } from "@/lib/guides-data";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "https://www.marketripple.in";

export const metadata: Metadata = {
  title: "Product Guides — How to Use MarketRipple",
  description:
    "Step-by-step guides to MarketRipple's real features — Market Intelligence, AI Search, Opportunity Radar, Ripple Maps, and Impact/Confidence scores.",
  alternates: { canonical: `${SITE_URL}/learn/guides` },
  openGraph: {
    title: "Product Guides — How to Use MarketRipple",
    description: "Step-by-step guides to MarketRipple's real features.",
    url: `${SITE_URL}/learn/guides`,
    images: [{ url: "/opengraph-image", width: 1200, height: 630, alt: "MarketRipple — AI-Powered Market Intelligence" }],
  },
};

export default function GuidesIndexPage() {
  return (
    <div className="space-y-8">
      <div>
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-text-muted">Knowledge Library</p>
        <h1 className="mt-3 text-[26px] font-black leading-tight text-text-primary md:text-[32px]">Product Guides</h1>
        <p className="mt-3 max-w-2xl text-[14px] leading-6 text-text-secondary">
          How to actually use MarketRipple's real, shipped features — not marketing copy, step-by-step
          walkthroughs. For the reasoning behind the features themselves, see{" "}
          <Link href="/how-it-works" className="text-violet-400 underline-offset-2 hover:underline">
            how MarketRipple's pipeline works
          </Link>{" "}
          end to end.
        </p>
      </div>

      {GUIDE_CATEGORIES.map(category => {
        const guides = GUIDES.filter(g => g.category === category);
        return (
          <section key={category}>
            <h2 className="mb-3 text-[11px] font-bold uppercase tracking-[0.14em] text-text-muted">{category}</h2>
            <div className="space-y-2.5">
              {guides.map(guide => (
                <Link
                  key={guide.slug}
                  href={`/learn/guides/${guide.slug}` as any}
                  className="flex items-center gap-4 rounded-xl border border-surface-border/7 bg-surface-card p-4 transition hover:border-violet-500/20 hover:bg-surface-card"
                >
                  <div className="min-w-0 flex-1">
                    <h3 className="text-[14px] font-bold text-text-primary">{guide.title}</h3>
                    <p className="mt-1 line-clamp-2 text-[12px] leading-5 text-text-muted">{guide.summary}</p>
                    <span className="mt-2 flex items-center gap-1 text-[10px] text-text-muted">
                      <Clock className="h-3 w-3" /> {guide.readTime} read · {guide.steps.length} steps
                    </span>
                  </div>
                  <ChevronRight className="h-4 w-4 shrink-0 text-text-muted" />
                </Link>
              ))}
            </div>
          </section>
        );
      })}
    </div>
  );
}
