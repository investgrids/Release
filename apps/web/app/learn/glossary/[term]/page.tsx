import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ChevronRight, ArrowLeft } from "lucide-react";
import { GLOSSARY, getGlossaryTerm, getRelatedTerms } from "@/lib/glossary-data";
import { safeJsonLd } from "@/lib/text";

const SITE = process.env.NEXT_PUBLIC_SITE_URL ?? "https://www.marketripple.in";

export function generateStaticParams() {
  return GLOSSARY.map(t => ({ term: t.slug }));
}

export async function generateMetadata({ params }: { params: Promise<{ term: string }> }): Promise<Metadata> {
  const { term: slug } = await params;
  const term = getGlossaryTerm(slug);
  if (!term) return { title: "Term Not Found" };
  return {
    title: `${term.term} — Meaning & Definition`,
    description: term.shortDef,
    openGraph: { title: `${term.term} — MarketRipple Glossary`, description: term.shortDef },
    alternates: { canonical: `${SITE}/learn/glossary/${slug}` },
  };
}

export default async function GlossaryTermPage({ params }: { params: Promise<{ term: string }> }) {
  const { term: slug } = await params;
  const term = getGlossaryTerm(slug);
  if (!term) notFound();

  const related = getRelatedTerms(term);
  const url = `${SITE}/learn/glossary/${slug}`;
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "DefinedTerm",
    name: term.term,
    description: term.shortDef,
    url,
    inDefinedTermSet: `${SITE}/learn/glossary`,
  };

  return (
    <div className="space-y-8">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: safeJsonLd(jsonLd) }} />
      <nav className="flex items-center gap-1.5 text-[11px] text-text-muted">
        <Link href="/learn/glossary" className="hover:text-text-secondary">Glossary</Link>
        <ChevronRight className="h-3 w-3" />
        <span className="text-text-secondary">{term.term}</span>
      </nav>

      <div>
        <span className="rounded-full border border-surface-border/8 bg-text-primary/[0.04] px-2.5 py-0.5 text-[9px] font-bold uppercase tracking-wider text-text-muted">
          {term.category}
        </span>
        <h1 className="mt-3 text-[26px] font-black leading-tight text-text-primary md:text-[32px]">{term.term}</h1>
        <p className="mt-2 text-[14px] leading-6 text-text-secondary">{term.shortDef}</p>
      </div>

      <div className="space-y-4 rounded-2xl border border-surface-border/7 bg-surface-card p-6">
        {term.definition.map((p, i) => (
          <p key={i} className="text-[14px] leading-7 text-text-secondary">{p}</p>
        ))}
        {term.example && (
          <div className="rounded-xl border border-violet-500/15 bg-violet-500/[0.05] p-4">
            <p className="mb-1 text-[10px] font-bold uppercase tracking-wider text-violet-400">Example</p>
            <p className="text-[13px] leading-6 text-text-secondary">{term.example}</p>
          </div>
        )}
      </div>

      {related.length > 0 && (
        <div>
          <h2 className="mb-3 text-[11px] font-bold uppercase tracking-[0.14em] text-text-muted">Related Terms</h2>
          <div className="flex flex-wrap gap-2">
            {related.map(r => (
              <Link
                key={r.slug}
                href={`/learn/glossary/${r.slug}` as any}
                className="rounded-full border border-surface-border/8 bg-text-primary/[0.03] px-3.5 py-1.5 text-[12px] font-semibold text-text-secondary transition hover:border-violet-500/25 hover:text-text-primary"
              >
                {r.term}
              </Link>
            ))}
          </div>
        </div>
      )}

      <Link href="/learn/glossary" className="inline-flex items-center gap-1.5 text-[12px] font-semibold text-text-muted hover:text-text-secondary transition">
        <ArrowLeft className="h-3.5 w-3.5" /> Back to Glossary
      </Link>
    </div>
  );
}
