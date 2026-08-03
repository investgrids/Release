import { API_BASE_URL as API } from "@/lib/api";
import NewsDetailPage, { type NewsArticle } from "./NewsPageClient";

/**
 * Server wrapper (Phase 1 SEO fix — see the SEO/Growth audit's Critical
 * Finding #1). Fetches the same /api/news/{id} endpoint the client
 * component already calls, purely so crawlers and the first paint see a
 * real, indexable <h1> + summary instead of nothing.
 */

async function fetchArticle(id: string): Promise<NewsArticle | null> {
  try {
    const res = await fetch(`${API}/api/news/${id}`, { next: { revalidate: 300 } });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

function withPeriod(text: string) {
  const t = text.trim();
  return /[.!?]$/.test(t) ? t : `${t}.`;
}

export default async function NewsPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const article = await fetchArticle(id);

  return (
    <>
      {article && (
        <section className="mb-4 border-b border-surface-border/6 pb-4">
          {/* The single real <h1> for this page — the client component's
              own header renders the same headline as a <p>, not a second
              <h1>, when it detects this server data was already used. */}
          <h1 className="text-[13px] font-semibold uppercase tracking-wide text-text-muted">{article.headline}</h1>
          <p className="mt-1.5 max-w-3xl text-[13px] leading-relaxed text-text-secondary">
            {withPeriod(article.summary || `${article.headline} — ${article.source}, with MarketRipple's market-impact analysis.`)}
          </p>
        </section>
      )}
      <NewsDetailPage initialArticle={article} />
    </>
  );
}
