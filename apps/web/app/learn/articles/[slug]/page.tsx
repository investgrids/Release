import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ChevronRight, ArrowLeft, Clock } from "lucide-react";
import { ARTICLES, getArticle, getRelatedArticles } from "@/lib/articles-data";
import { getGlossaryTerm } from "@/lib/glossary-data";

export function generateStaticParams() {
  return ARTICLES.map(a => ({ slug: a.slug }));
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  const article = getArticle(slug);
  if (!article) return { title: "Article Not Found" };
  return {
    title: article.title,
    description: article.summary,
    openGraph: { title: article.title, description: article.summary, type: "article" },
  };
}

export default async function ArticleDetailPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const article = getArticle(slug);
  if (!article) notFound();

  const related = getRelatedArticles(article);
  const glossaryLinks = (article.relatedGlossary ?? [])
    .map(s => getGlossaryTerm(s))
    .filter((t): t is NonNullable<typeof t> => !!t);

  return (
    <div className="space-y-8">
      <nav className="flex items-center gap-1.5 text-[11px] text-text-muted">
        <Link href="/learn/articles" className="hover:text-text-secondary">Articles</Link>
        <ChevronRight className="h-3 w-3" />
        <span className="text-text-secondary">{article.title}</span>
      </nav>

      <div>
        <span className="rounded-full border border-emerald-500/20 bg-emerald-500/10 px-2.5 py-0.5 text-[9px] font-bold uppercase tracking-wider text-emerald-400">
          {article.category}
        </span>
        <h1 className="mt-3 text-[26px] font-black leading-tight text-text-primary md:text-[34px]">{article.title}</h1>
        <p className="mt-3 max-w-2xl text-[14px] leading-6 text-text-secondary">{article.summary}</p>
        <span className="mt-3 flex items-center gap-1 text-[11px] text-text-muted">
          <Clock className="h-3 w-3" /> {article.readTime} read
        </span>
      </div>

      <article className="space-y-6 rounded-2xl border border-surface-border/7 bg-surface-card p-6 md:p-8">
        {article.body.map((section, i) => (
          <div key={i}>
            {section.heading && <h2 className="mb-3 text-[16px] font-bold text-text-primary">{section.heading}</h2>}
            <div className="space-y-3">
              {section.paragraphs.map((p, j) => (
                <p key={j} className="text-[14px] leading-7 text-text-secondary">{p}</p>
              ))}
            </div>
          </div>
        ))}
      </article>

      {glossaryLinks.length > 0 && (
        <div>
          <h2 className="mb-3 text-[11px] font-bold uppercase tracking-[0.14em] text-text-muted">Terms Used In This Article</h2>
          <div className="flex flex-wrap gap-2">
            {glossaryLinks.map(t => (
              <Link
                key={t.slug}
                href={`/learn/glossary/${t.slug}` as any}
                className="rounded-full border border-surface-border/8 bg-text-primary/[0.03] px-3.5 py-1.5 text-[12px] font-semibold text-text-secondary transition hover:border-sky-500/25 hover:text-text-primary"
              >
                {t.term}
              </Link>
            ))}
          </div>
        </div>
      )}

      {related.length > 0 && (
        <div>
          <h2 className="mb-3 text-[11px] font-bold uppercase tracking-[0.14em] text-text-muted">Related Articles</h2>
          <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
            {related.map(r => (
              <Link
                key={r.slug}
                href={`/learn/articles/${r.slug}` as any}
                className="rounded-xl border border-surface-border/7 bg-surface-card p-4 transition hover:border-emerald-500/20"
              >
                <h3 className="text-[13px] font-bold text-text-primary">{r.title}</h3>
                <p className="mt-1 line-clamp-2 text-[11px] leading-5 text-text-muted">{r.summary}</p>
              </Link>
            ))}
          </div>
        </div>
      )}

      <Link href="/learn/articles" className="inline-flex items-center gap-1.5 text-[12px] font-semibold text-text-muted hover:text-text-secondary transition">
        <ArrowLeft className="h-3.5 w-3.5" /> Back to Articles
      </Link>
    </div>
  );
}
