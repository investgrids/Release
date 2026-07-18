import type { Metadata } from "next";
import Link from "next/link";
import { Clock, ChevronRight } from "lucide-react";
import { ARTICLES, ARTICLE_CATEGORIES } from "@/lib/articles-data";

export const metadata: Metadata = {
  title: "Investor Education Articles",
  description:
    "Longer-form articles on how markets actually work — ripple effects, sector rotation, RBI policy transmission, FII/DII flows, and market cycles.",
  openGraph: {
    title: "Investor Education Articles — MarketRipple Learn",
    description: "Longer-form articles on how Indian markets actually work.",
  },
};

export default function ArticlesIndexPage() {
  return (
    <div className="space-y-8">
      <div>
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">Knowledge Library</p>
        <h1 className="mt-3 text-[26px] font-black leading-tight text-white md:text-[32px]">Investor Education</h1>
        <p className="mt-3 max-w-2xl text-[14px] leading-6 text-slate-400">
          Longer-form articles that go past the headline — how ripple effects actually propagate,
          why sectors rotate, and how policy decisions transmit through markets.
        </p>
      </div>

      {ARTICLE_CATEGORIES.map(category => {
        const articles = ARTICLES.filter(a => a.category === category);
        return (
          <section key={category}>
            <h2 className="mb-3 text-[11px] font-bold uppercase tracking-[0.14em] text-slate-500">{category}</h2>
            <div className="space-y-2.5">
              {articles.map(article => (
                <Link
                  key={article.slug}
                  href={`/learn/articles/${article.slug}` as any}
                  className="flex items-center gap-4 rounded-xl border border-white/[0.07] bg-[#080c14] p-4 transition hover:border-emerald-500/20 hover:bg-[#0a102c]"
                >
                  <div className="min-w-0 flex-1">
                    <h3 className="text-[14px] font-bold text-white">{article.title}</h3>
                    <p className="mt-1 line-clamp-2 text-[12px] leading-5 text-slate-500">{article.summary}</p>
                    <span className="mt-2 flex items-center gap-1 text-[10px] text-slate-600">
                      <Clock className="h-3 w-3" /> {article.readTime} read
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
