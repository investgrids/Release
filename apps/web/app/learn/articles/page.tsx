import type { Metadata } from "next";
import Link from "next/link";
import { Clock, ChevronRight } from "lucide-react";
import { ARTICLES, ARTICLE_CATEGORIES } from "@/lib/articles-data";
import { safeJsonLd } from "@/lib/text";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "https://www.marketripple.in";

export const metadata: Metadata = {
  title: "Investor Education Articles",
  description:
    "Longer-form articles on how markets actually work — ripple effects, sector rotation, RBI policy transmission, FII/DII flows, and market cycles.",
  alternates: { canonical: `${SITE_URL}/learn/articles` },
  openGraph: {
    title: "Investor Education Articles — MarketRipple Learn",
    description: "Longer-form articles on how Indian markets actually work.",
    url: `${SITE_URL}/learn/articles`,
    images: [{ url: "/opengraph-image", width: 1200, height: 630, alt: "MarketRipple — AI-Powered Market Intelligence" }],
  },
};

// Built directly from ARTICLES — the same real, written articles rendered
// on the page — so this can never drift into fabricated entries.
const ARTICLES_JSONLD = {
  "@context": "https://schema.org",
  "@type": "CollectionPage",
  name: "Investor Education Articles",
  url: `${SITE_URL}/learn/articles`,
  mainEntity: {
    "@type": "ItemList",
    itemListElement: ARTICLES.map((a, i) => ({
      "@type": "ListItem",
      position: i + 1,
      name: a.title,
      url: `${SITE_URL}/learn/articles/${a.slug}`,
    })),
  },
};

export default function ArticlesIndexPage() {
  return (
    <div className="space-y-8">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: safeJsonLd(ARTICLES_JSONLD) }} />
      <div>
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-text-muted">Knowledge Library</p>
        <h1 className="mt-3 text-[26px] font-black leading-tight text-text-primary md:text-[32px]">Investor Education</h1>
        <p className="mt-3 max-w-2xl text-[14px] leading-6 text-text-secondary">
          Longer-form articles that go past the headline — how ripple effects actually propagate,
          why sectors rotate, and how policy decisions transmit through markets.
        </p>
      </div>

      {ARTICLE_CATEGORIES.map(category => {
        const articles = ARTICLES.filter(a => a.category === category);
        return (
          <section key={category}>
            <h2 className="mb-3 text-[11px] font-bold uppercase tracking-[0.14em] text-text-muted">{category}</h2>
            <div className="space-y-2.5">
              {articles.map(article => (
                <Link
                  key={article.slug}
                  href={`/learn/articles/${article.slug}` as any}
                  className="flex items-center gap-4 rounded-xl border border-surface-border/7 bg-surface-card p-4 transition hover:border-emerald-500/20 hover:bg-surface-card"
                >
                  <div className="min-w-0 flex-1">
                    <h3 className="text-[14px] font-bold text-text-primary">{article.title}</h3>
                    <p className="mt-1 line-clamp-2 text-[12px] leading-5 text-text-muted">{article.summary}</p>
                    <span className="mt-2 flex items-center gap-1 text-[10px] text-text-muted">
                      <Clock className="h-3 w-3" /> {article.readTime} read
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
