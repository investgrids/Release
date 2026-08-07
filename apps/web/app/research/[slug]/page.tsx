import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { API_BASE_URL as API } from "@/lib/api";
import { AskAICta } from "@/components/AskAICta";
import { RelatedContent } from "@/components/RelatedContent";
import { safeJsonLd } from "@/lib/text";

/**
 * Comparison research pages (SEO Phase 2, §2.2 — the permanent-page half
 * of "AI Search answer becomes an indexable page"). Server Component from
 * the start. Reuses the existing GET /api/insights/{slug} endpoint (no
 * new API surface) — comparison_intelligence articles live in the same
 * IntelligenceArticle table as every other AIPE article, with the real
 * decision comparison stashed in market_context (see comparison_publisher.py
 * and insights.py's _detail_row for exactly why).
 */

const SITE = process.env.NEXT_PUBLIC_SITE_URL ?? "https://www.marketripple.in";

interface EntityAnalysis {
  entity: string; symbol: string; sector: string; thesis: string;
  strengths: string[]; risks: string[]; catalysts: string[];
  near_term_outlook: string; confidence: number;
}
interface ComparisonRow { dimension: string; holding: string; target: string; advantage: string }
interface Tradeoff {
  reasons_to_switch: string[]; reasons_to_hold: string[];
  risks_of_switching: string[]; risks_of_holding: string[]; when_to_wait: string;
}
interface DecisionFramework { supports_switch: string[]; argues_against: string[]; key_unknowns: string[]; ai_stance: string }
interface DecisionIntelligence {
  decision_summary: string;
  holding_analysis: EntityAnalysis; target_analysis: EntityAnalysis;
  comparison: ComparisonRow[]; tradeoff: Tradeoff; decision_framework: DecisionFramework;
}
interface ResearchArticle {
  slug: string; headline: string; seo_title?: string; meta_description?: string;
  executive_summary?: string; companies_affected: { name: string; symbol: string }[];
  published_at?: string; last_updated?: string;
  market_context?: { kind: string; decision_intelligence: DecisionIntelligence; investment_verdict: Record<string, unknown> } | null;
}

async function fetchArticle(slug: string): Promise<ResearchArticle | null> {
  try {
    const res = await fetch(`${API}/api/insights/${slug}`, { next: { revalidate: 1800 } });
    if (!res.ok) return null;
    const data = await res.json();
    if (data.market_context?.kind !== "comparison") return null;
    return data;
  } catch {
    return null;
  }
}

// This page previously had NO related-content section at all — a genuine
// orphan-content-graph gap (SEO audit's Part 8 / roadmap Stage 4 "no
// orphan pages" finding). Server-fetched so the links exist in the
// initial HTML, same reasoning as the companies page's own fetchRelated.
async function fetchRelated(slug: string, sector?: string) {
  try {
    const params = new URLSearchParams(sector ? { sector } : {});
    const res = await fetch(`${API}/api/related/comparison/${encodeURIComponent(slug)}?${params}`, { next: { revalidate: 600 } });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

function outlookColor(o: string) {
  const l = (o || "").toLowerCase();
  if (l === "positive") return "text-emerald-400";
  if (l === "negative") return "text-rose-400";
  return "text-amber-400";
}
function advantageColor(a: string, side: "holding" | "target") {
  if (a === side) return "text-emerald-400 font-semibold";
  return "text-text-secondary";
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  const url = `${SITE}/research/${slug}`;
  const a = await fetchArticle(slug);
  if (!a) return { title: "Comparison Not Found", alternates: { canonical: url } };
  const desc = (a.meta_description || a.executive_summary || a.headline).slice(0, 160);
  return {
    title: a.seo_title || a.headline,
    description: desc,
    openGraph: { type: "article", title: a.headline, description: desc, url, siteName: "MarketRipple" },
    twitter: { card: "summary_large_image", title: a.headline, description: desc },
    alternates: { canonical: url },
  };
}

export default async function ResearchPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const article = await fetchArticle(slug);
  if (!article || !article.market_context) notFound();

  const di = article.market_context.decision_intelligence;
  const url = `${SITE}/research/${slug}`;
  const [a, b] = [di.holding_analysis, di.target_analysis];
  const related = await fetchRelated(slug, a.sector || b.sector);

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "Article",
    headline: article.headline,
    description: article.meta_description || article.executive_summary,
    url,
    publisher: { "@type": "Organization", name: "MarketRipple" },
    breadcrumb: {
      "@type": "BreadcrumbList",
      itemListElement: [
        { "@type": "ListItem", position: 1, name: "MarketRipple", item: SITE },
        { "@type": "ListItem", position: 2, name: "Research", item: `${SITE}/research` },
        { "@type": "ListItem", position: 3, name: article.headline, item: url },
      ],
    },
  };

  return (
    <main className="mx-auto max-w-[1100px] space-y-6 px-6 py-6 pb-16">
      {/* JSON.stringify (not safeJsonLd) previously left "<" unescaped —
          same stored-XSS class already fixed on the article/signal pages;
          a literal "</script>" inside any AI-generated field here
          (headline, thesis, etc.) could close this tag early. */}
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: safeJsonLd(jsonLd) }} />

      <nav className="flex items-center gap-2 text-[12px] text-text-muted">
        <Link href="/research/comparisons" className="hover:text-text-secondary transition">Research</Link>
        <span>/</span>
        <span className="text-text-secondary">{a.entity} vs {b.entity}</span>
      </nav>

      <div>
        <p className="text-[11px] font-bold uppercase tracking-[0.2em] text-sky-400">AI Comparison Research</p>
        <h1 className="mt-2 text-3xl font-black tracking-tight text-text-primary">{article.headline}</h1>
        {article.executive_summary && (
          <p className="mt-3 max-w-3xl text-[14px] leading-relaxed text-text-secondary">{article.executive_summary}</p>
        )}
        <p className="mt-2 text-[11px] text-text-muted">Not investment advice — research framing only.</p>
      </div>

      {/* Side-by-side entity analysis */}
      <div className="grid gap-4 sm:grid-cols-2">
        {[a, b].map((e, i) => (
          <div key={i} className="rounded-[20px] border border-surface-border/8 bg-surface-card p-5">
            <div className="flex items-center justify-between">
              <Link href={`/companies/${e.symbol}`} className="text-[17px] font-bold text-text-primary hover:text-sky-600 dark:text-sky-300 transition">{e.entity}</Link>
              <span className={`text-[12px] font-semibold uppercase ${outlookColor(e.near_term_outlook)}`}>{e.near_term_outlook}</span>
            </div>
            {e.sector && <p className="mt-0.5 text-[11px] text-text-muted">{e.sector}</p>}
            {e.thesis && <p className="mt-3 text-[13px] leading-relaxed text-text-secondary">{e.thesis}</p>}
            {e.strengths?.length > 0 && (
              <div className="mt-3">
                <p className="text-[10px] uppercase tracking-wider text-emerald-400 font-semibold mb-1">Strengths</p>
                <ul className="space-y-1">
                  {e.strengths.filter(Boolean).map((s, j) => <li key={j} className="text-[12px] text-text-secondary">• {s}</li>)}
                </ul>
              </div>
            )}
            {e.risks?.length > 0 && (
              <div className="mt-3">
                <p className="text-[10px] uppercase tracking-wider text-rose-400 font-semibold mb-1">Risks</p>
                <ul className="space-y-1">
                  {e.risks.filter(Boolean).map((s, j) => <li key={j} className="text-[12px] text-text-secondary">• {s}</li>)}
                </ul>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Dimension-by-dimension comparison table */}
      {di.comparison?.length > 0 && (
        <section>
          <h2 className="mb-3 text-[15px] font-semibold text-text-primary">Dimension-by-Dimension Comparison</h2>
          <div className="overflow-x-auto rounded-[16px] border border-surface-border/8">
            <table className="w-full min-w-[560px] text-[13px]">
              <thead>
                <tr className="border-b border-surface-border/8 bg-text-primary/[0.02]">
                  <th className="px-4 py-2.5 text-left text-[10px] uppercase tracking-wider text-text-muted">Dimension</th>
                  <th className="px-4 py-2.5 text-left text-[10px] uppercase tracking-wider text-text-muted">{a.entity}</th>
                  <th className="px-4 py-2.5 text-left text-[10px] uppercase tracking-wider text-text-muted">{b.entity}</th>
                </tr>
              </thead>
              <tbody>
                {di.comparison.filter(r => r.dimension).map((r, i) => (
                  <tr key={i} className="border-b border-surface-border/5 last:border-0">
                    <td className="px-4 py-2.5 text-text-secondary">{r.dimension}</td>
                    <td className={`px-4 py-2.5 ${advantageColor(r.advantage, "holding")}`}>{r.holding}</td>
                    <td className={`px-4 py-2.5 ${advantageColor(r.advantage, "target")}`}>{r.target}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* Tradeoff */}
      {di.tradeoff && (
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="rounded-[16px] border border-emerald-500/15 bg-emerald-500/[0.04] p-4">
            <p className="mb-2 text-[11px] uppercase tracking-wider text-emerald-400 font-semibold">Case For {b.entity}</p>
            <ul className="space-y-1.5">
              {(di.tradeoff.reasons_to_switch || []).filter(Boolean).map((s, i) => <li key={i} className="text-[12.5px] text-text-secondary">• {s}</li>)}
            </ul>
          </div>
          <div className="rounded-[16px] border border-sky-500/15 bg-sky-500/[0.04] p-4">
            <p className="mb-2 text-[11px] uppercase tracking-wider text-sky-400 font-semibold">Case For {a.entity}</p>
            <ul className="space-y-1.5">
              {(di.tradeoff.reasons_to_hold || []).filter(Boolean).map((s, i) => <li key={i} className="text-[12.5px] text-text-secondary">• {s}</li>)}
            </ul>
          </div>
        </div>
      )}

      {/* Decision framework / AI stance */}
      {di.decision_framework?.ai_stance && (
        <div className="rounded-[16px] border border-violet-500/20 bg-violet-500/[0.04] px-5 py-4">
          <p className="text-[11px] uppercase tracking-wider text-violet-400 font-semibold mb-1.5">Research Framing</p>
          <p className="text-[13.5px] leading-relaxed text-text-primary">{di.decision_framework.ai_stance}</p>
          {di.decision_framework.key_unknowns?.filter(Boolean).length > 0 && (
            <p className="mt-2 text-[11.5px] text-text-muted">
              Key unknowns: {di.decision_framework.key_unknowns.filter(Boolean).join(" · ")}
            </p>
          )}
        </div>
      )}

      <div className="rounded-[16px] border border-surface-border/7 bg-text-primary/[0.02] px-5 py-4">
        <p className="text-[13px] text-text-secondary">
          Want a personalized read?{" "}
          <AskAICta query={`${a.entity} vs ${b.entity}, which is better for 12 months?`} source="research_page" />
        </p>
      </div>

      {related && (
        <RelatedContent
          entityType="comparison"
          entityId={slug}
          sector={a.sector || b.sector}
          initialData={related}
        />
      )}
    </main>
  );
}
