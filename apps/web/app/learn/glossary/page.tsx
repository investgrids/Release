import type { Metadata } from "next";
import Link from "next/link";
import { GLOSSARY, GLOSSARY_CATEGORIES } from "@/lib/glossary-data";

export const metadata: Metadata = {
  title: "Market Glossary — Indian Stock Market Terms Explained",
  description:
    "Plain-language definitions of Indian stock market terminology — Nifty 50, Sensex, FII/DII, repo rate, P/E ratio, and more — plus MarketRipple's own scoring concepts.",
  openGraph: {
    title: "Market Glossary — Indian Stock Market Terms Explained",
    description: "Plain-language definitions of Indian stock market terminology and MarketRipple's scoring concepts.",
    images: [{ url: "/opengraph-image", width: 1200, height: 630, alt: "MarketRipple — AI-Powered Market Intelligence" }],
  },
};

export default function GlossaryIndexPage() {
  return (
    <div className="space-y-8">
      <div>
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-text-muted">Knowledge Library</p>
        <h1 className="mt-3 text-[26px] font-black leading-tight text-text-primary md:text-[32px]">Market Glossary</h1>
        <p className="mt-3 max-w-2xl text-[14px] leading-6 text-text-secondary">
          {GLOSSARY.length} terms — from index basics to MarketRipple's own scoring language. Each entry
          is a real, written definition, not a one-line dictionary snippet.
        </p>
      </div>

      {GLOSSARY_CATEGORIES.map(category => {
        const terms = GLOSSARY.filter(t => t.category === category);
        return (
          <section key={category}>
            <h2 className="mb-3 text-[11px] font-bold uppercase tracking-[0.14em] text-text-muted">{category}</h2>
            <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
              {terms.map(term => (
                <Link
                  key={term.slug}
                  href={`/learn/glossary/${term.slug}` as any}
                  className="rounded-xl border border-surface-border/7 bg-surface-card p-4 transition hover:border-violet-500/20 hover:bg-surface-card"
                >
                  <h3 className="text-[13px] font-bold text-text-primary">{term.term}</h3>
                  <p className="mt-1 line-clamp-2 text-[12px] leading-5 text-text-muted">{term.shortDef}</p>
                </Link>
              ))}
            </div>
          </section>
        );
      })}
    </div>
  );
}
