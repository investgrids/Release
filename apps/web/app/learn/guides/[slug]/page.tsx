import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ChevronRight, ArrowLeft, Clock, Lightbulb } from "lucide-react";
import { GUIDES, getGuide, getRelatedGuides } from "@/lib/guides-data";

export function generateStaticParams() {
  return GUIDES.map(g => ({ slug: g.slug }));
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  const guide = getGuide(slug);
  if (!guide) return { title: "Guide Not Found" };
  return {
    title: guide.title,
    description: guide.summary,
    openGraph: { title: `${guide.title} | MarketRipple Guide`, description: guide.summary },
  };
}

export default async function GuideDetailPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const guide = getGuide(slug);
  if (!guide) notFound();

  const related = getRelatedGuides(guide);

  return (
    <div className="space-y-8">
      <nav className="flex items-center gap-1.5 text-[11px] text-slate-600">
        <Link href="/learn/guides" className="hover:text-slate-400">Guides</Link>
        <ChevronRight className="h-3 w-3" />
        <span className="text-slate-400">{guide.title}</span>
      </nav>

      <div>
        <span className="rounded-full border border-violet-500/20 bg-violet-500/10 px-2.5 py-0.5 text-[9px] font-bold uppercase tracking-wider text-violet-400">
          {guide.category}
        </span>
        <h1 className="mt-3 text-[26px] font-black leading-tight text-white md:text-[32px]">{guide.title}</h1>
        <p className="mt-2 max-w-2xl text-[14px] leading-6 text-slate-400">{guide.summary}</p>
        <span className="mt-3 flex items-center gap-1 text-[11px] text-slate-600">
          <Clock className="h-3 w-3" /> {guide.readTime} read
        </span>
      </div>

      <ol className="space-y-4">
        {guide.steps.map((step, i) => (
          <li key={i} className="flex gap-4 rounded-2xl border border-white/[0.07] bg-[#080c14] p-5">
            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-violet-500/15 text-[12px] font-black text-violet-400">
              {i + 1}
            </span>
            <div>
              <h2 className="text-[14px] font-bold text-white">{step.title}</h2>
              <p className="mt-1.5 text-[13px] leading-6 text-slate-400">{step.body}</p>
            </div>
          </li>
        ))}
      </ol>

      {guide.tips && guide.tips.length > 0 && (
        <div className="rounded-2xl border border-amber-500/15 bg-amber-500/[0.04] p-5">
          <div className="mb-2 flex items-center gap-2">
            <Lightbulb className="h-4 w-4 text-amber-400" />
            <h2 className="text-[12px] font-bold uppercase tracking-wider text-amber-400">Tips</h2>
          </div>
          <ul className="space-y-1.5">
            {guide.tips.map((tip, i) => (
              <li key={i} className="flex items-start gap-2 text-[13px] leading-6 text-slate-300">
                <span className="mt-2 h-1 w-1 shrink-0 rounded-full bg-amber-400" />
                {tip}
              </li>
            ))}
          </ul>
        </div>
      )}

      {related.length > 0 && (
        <div>
          <h2 className="mb-3 text-[11px] font-bold uppercase tracking-[0.14em] text-slate-500">Related Guides</h2>
          <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
            {related.map(r => (
              <Link
                key={r.slug}
                href={`/learn/guides/${r.slug}` as any}
                className="rounded-xl border border-white/[0.07] bg-[#080c14] p-4 transition hover:border-violet-500/20"
              >
                <h3 className="text-[13px] font-bold text-white">{r.title}</h3>
                <p className="mt-1 line-clamp-2 text-[11px] leading-5 text-slate-500">{r.summary}</p>
              </Link>
            ))}
          </div>
        </div>
      )}

      <Link href="/learn/guides" className="inline-flex items-center gap-1.5 text-[12px] font-semibold text-slate-500 hover:text-slate-300 transition">
        <ArrowLeft className="h-3.5 w-3.5" /> Back to Guides
      </Link>
    </div>
  );
}
