import type { Metadata } from "next";
import Link from "next/link";
import { Library, BookOpen, GraduationCap, ArrowRight } from "lucide-react";
import { GLOSSARY } from "@/lib/glossary-data";
import { GUIDES } from "@/lib/guides-data";
import { ARTICLES } from "@/lib/articles-data";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "https://www.marketripple.in";

// The parent layout (learn/layout.tsx) sets a title *template*
// ("%s | MarketRipple Learn"), so this only needs to supply the
// page-specific half — Next.js composes the two automatically.
export const metadata: Metadata = {
  title: "Learn Hub — Glossary, Guides & Investor Education",
  description:
    "MarketRipple's Knowledge Library: a plain-language glossary of Indian market terms, step-by-step product guides, and investor education articles.",
  alternates: { canonical: `${SITE_URL}/learn` },
};

export default function LearnHubPage() {
  const sections = [
    {
      href: "/learn/glossary",
      icon: Library,
      title: "Glossary",
      count: `${GLOSSARY.length} terms`,
      desc: "Plain-language definitions for Indian market terminology — from Nifty 50 to Put-Call Ratio to MarketRipple's own scoring concepts.",
      color: "text-sky-400",
      bg: "bg-sky-500/10 border-sky-500/20",
      sample: GLOSSARY.slice(0, 4),
    },
    {
      href: "/learn/guides",
      icon: BookOpen,
      title: "Guides",
      count: `${GUIDES.length} guides`,
      desc: "How to actually use MarketRipple — reading the dashboard, AI Search, the Opportunity Radar, Ripple Maps, and Impact/Confidence scores.",
      color: "text-violet-400",
      bg: "bg-violet-500/10 border-violet-500/20",
      sample: GUIDES.slice(0, 4),
    },
    {
      href: "/learn/articles",
      icon: GraduationCap,
      title: "Articles",
      count: `${ARTICLES.length} articles`,
      desc: "Longer-form investor education — how ripple effects work, sector rotation, RBI policy transmission, FII/DII flows, and market cycles.",
      color: "text-emerald-400",
      bg: "bg-emerald-500/10 border-emerald-500/20",
      sample: ARTICLES.slice(0, 4),
    },
  ];

  return (
    <div className="space-y-10">
      <div>
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-text-muted">Knowledge Library</p>
        <h1 className="mt-3 text-[28px] font-black leading-tight text-text-primary md:text-[36px]">
          Understand Markets. Not Just Watch Them.
        </h1>
        <p className="mt-3 max-w-2xl text-[15px] leading-7 text-text-secondary">
          A glossary of real market terminology, guides to MarketRipple's own features, and
          investor education articles — all in one place, all written to be actually useful,
          not filler.
        </p>
      </div>

      <div className="space-y-6">
        {sections.map(s => {
          const Icon = s.icon;
          return (
            <section key={s.href} className={`rounded-2xl border p-6 ${s.bg}`}>
              <div className="mb-4 flex items-start justify-between gap-4">
                <div className="flex items-start gap-4">
                  <div className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border ${s.bg}`}>
                    <Icon className={`h-5 w-5 ${s.color}`} />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h2 className="text-[18px] font-bold text-text-primary">{s.title}</h2>
                      <span className={`text-[10px] font-bold uppercase tracking-wider ${s.color}`}>{s.count}</span>
                    </div>
                    <p className="mt-1 max-w-xl text-[13px] leading-6 text-text-secondary">{s.desc}</p>
                  </div>
                </div>
                <Link href={s.href as any} className={`shrink-0 flex items-center gap-1 text-[12px] font-semibold ${s.color} hover:underline`}>
                  Browse all <ArrowRight className="h-3.5 w-3.5" />
                </Link>
              </div>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                {s.sample.map((item: any) => (
                  <Link
                    key={item.slug}
                    href={`${s.href}/${item.slug}` as any}
                    className="rounded-lg border border-surface-border/6 bg-text-primary/[0.03] px-3 py-2.5 text-[11px] font-semibold text-text-secondary transition hover:border-surface-border/[0.12] hover:text-text-primary"
                  >
                    {item.term ?? item.title}
                  </Link>
                ))}
              </div>
            </section>
          );
        })}
      </div>

      {/* Cross-link into the Knowledge Center — the glossary/guide entries
          above describe MarketRipple concepts (scores, ripple effects, data
          sourcing) that are explained in full depth on these pages. */}
      <div className="rounded-2xl border border-surface-border/8 bg-surface-card p-6">
        <h2 className="text-[10px] font-bold uppercase tracking-[0.18em] text-text-muted">
          Go Deeper
        </h2>
        <p className="mt-3 max-w-2xl text-[13px] leading-6 text-text-secondary">
          These pages explain what MarketRipple's terms and features mean. For the
          mechanics behind them, see how{" "}
          <Link href="/ai-methodology" className="font-medium text-violet-400 underline-offset-2 hover:underline">
            Impact and Confidence scores are actually calculated
          </Link>
          , walk through{" "}
          <Link href="/how-marketripple-thinks" className="font-medium text-violet-400 underline-offset-2 hover:underline">
            how the AI reasons through ripple effects
          </Link>
          , browse the{" "}
          <Link href="/data-sources" className="font-medium text-violet-400 underline-offset-2 hover:underline">
            data sources
          </Link>{" "}
          behind every number, or read{" "}
          <Link href="/how-it-works" className="font-medium text-violet-400 underline-offset-2 hover:underline">
            the full pipeline
          </Link>{" "}
          from breaking news to opportunity score.
        </p>
      </div>
    </div>
  );
}
