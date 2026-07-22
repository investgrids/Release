import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { API_BASE_URL as API } from "@/lib/api";
import {
  ArrowRight, Zap, Building2, BookOpen,
  Target, Activity, Search, ExternalLink,
  TrendingUp, Brain, Shield,
} from "lucide-react";

const SITE = process.env.NEXT_PUBLIC_SITE_URL     ?? "https://marketripple.in";

type EntityType = "event" | "company" | "story" | "opportunity" | "ripple" | "search" | "article";

const VALID_TYPES = new Set<EntityType>(["event", "company", "story", "opportunity", "ripple", "search", "article"]);

function isValid(t: string): t is EntityType { return VALID_TYPES.has(t as EntityType); }

interface EntityData {
  title:       string;
  description: string;
  summary?:    string;
  sector?:     string;
  score?:      number;
  confidence?: number;
  href:        string;
  type:        EntityType;
}

async function fetchEntity(type: EntityType, id: string): Promise<EntityData | null> {
  try {
    switch (type) {
      case "event": {
        const r = await fetch(`${API}/api/events/${id}`, { next: { revalidate: 3600 } });
        if (!r.ok) return null;
        const d = await r.json();
        const ev = d.event ?? d;
        return {
          title:       ev.title ?? "Market Event",
          description: d.summary?.text ?? ev.description ?? "",
          summary:     d.summary?.why_it_matters,
          sector:      d.affectedSectors?.[0]?.sector,
          score:       d.impactScore,
          confidence:  d.confidence,
          href:        `/events/${id}`,
          type,
        };
      }
      case "company": {
        const r = await fetch(`${API}/api/stocks/${id.toUpperCase()}`, { next: { revalidate: 300 } });
        if (!r.ok) return null;
        const d = await r.json();
        return {
          title:       `${d.name ?? id} (${id.toUpperCase()})`,
          description: d.description ?? `AI-powered market analysis for ${d.name ?? id}.`,
          sector:      d.sector,
          href:        `/companies/${id.toUpperCase()}`,
          type,
        };
      }
      case "story": {
        const r = await fetch(`${API}/api/stories/${id}`, { next: { revalidate: 3600 } });
        if (!r.ok) return null;
        const d = await r.json();
        return {
          title:       d.title ?? "Investment Story",
          description: d.description ?? d.summary ?? "",
          sector:      d.sectors?.[0],
          score:       d.opportunity_score,
          confidence:  d.confidence,
          href:        `/stories/${id}`,
          type,
        };
      }
      case "opportunity": {
        const r = await fetch(`${API}/api/radar/${id}`, { next: { revalidate: 3600 } });
        if (!r.ok) return null;
        const d = await r.json();
        return {
          title:       d.title ?? "Investment Opportunity",
          description: d.summary ?? "",
          sector:      d.sector,
          score:       d.opportunity_score,
          confidence:  d.confidence,
          href:        `/radar/${id}`,
          type,
        };
      }
      case "ripple": {
        const r = await fetch(`${API}/api/ripple/${id}`, { next: { revalidate: 3600 } });
        if (!r.ok) return null;
        const d = await r.json();
        return {
          title:       d.event_title ?? d.title ?? "Ripple Intelligence",
          description: d.insights?.summary ?? d.summary ?? "",
          sector:      d.insights?.impacted_sectors?.[0]?.name,
          href:        `/ripple/${id}`,
          type,
        };
      }
      case "search": {
        const query = decodeURIComponent(id);
        return {
          title:       `AI Answer: ${query}`,
          description: `MarketRipple's AI has analyzed "${query}" with sourced, evidence-backed market intelligence.`,
          href:        `/ai-search?q=${encodeURIComponent(query)}`,
          type,
        };
      }
      case "article": {
        const r = await fetch(`${API}/api/insights/${id}`, { next: { revalidate: 1800 } });
        if (!r.ok) return null;
        const d = await r.json();
        return {
          title:       d.headline ?? "Market Intelligence",
          description: d.key_takeaway ?? d.executive_summary ?? "",
          sector:      d.sectors_affected?.[0]?.name,
          confidence:  d.confidence_score,
          href:        `/newsroom/article/${id}`,
          type,
        };
      }
    }
  } catch { return null; }
}

const TYPE_ICON: Record<EntityType, React.ReactNode> = {
  event:       <Zap className="h-5 w-5" />,
  company:     <Building2 className="h-5 w-5" />,
  story:       <BookOpen className="h-5 w-5" />,
  opportunity: <Target className="h-5 w-5" />,
  ripple:      <Activity className="h-5 w-5" />,
  search:      <Search className="h-5 w-5" />,
  article:     <Brain className="h-5 w-5" />,
};

const TYPE_COLOR: Record<EntityType, string> = {
  event:       "from-violet-600 to-violet-800",
  company:     "from-sky-600 to-sky-800",
  story:       "from-amber-600 to-orange-700",
  opportunity: "from-emerald-600 to-teal-700",
  ripple:      "from-rose-600 to-rose-800",
  search:      "from-indigo-600 to-indigo-800",
  article:     "from-fuchsia-600 to-purple-800",
};

const TYPE_LABEL: Record<EntityType, string> = {
  event:       "Market Event",
  company:     "Company Intelligence",
  story:       "Investment Story",
  opportunity: "Investment Opportunity",
  ripple:      "Ripple Intelligence",
  search:      "AI Market Search",
  article:     "AI Newsroom",
};

// ── generateMetadata ──────────────────────────────────────────────────────────

export async function generateMetadata({
  params,
}: {
  params: Promise<{ type: string; id: string }>;
}): Promise<Metadata> {
  const { type, id } = await params;
  if (!isValid(type)) return { title: "MarketRipple" };
  const entity = await fetchEntity(type, id);
  if (!entity) return { title: "MarketRipple" };
  const url  = `${SITE}/share/${type}/${id}`;
  const desc = (entity.description ?? "").slice(0, 160) || "AI-powered market intelligence from MarketRipple.";
  return {
    title:       entity.title,
    description: desc,
    openGraph: {
      type:      "article",
      title:     entity.title,
      description: desc,
      url,
      siteName:  "MarketRipple",
    },
    twitter: {
      card:        "summary_large_image",
      title:       entity.title,
      description: desc,
    },
    alternates: { canonical: `${SITE}${entity.href}` },
  };
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default async function SharePage({
  params,
}: {
  params: Promise<{ type: string; id: string }>;
}) {
  const { type, id } = await params;
  if (!isValid(type)) notFound();

  const entity = await fetchEntity(type, id);
  if (!entity) notFound();

  const gradient = TYPE_COLOR[type];
  const label    = TYPE_LABEL[type];

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100">
      {/* ── Hero ──────────────────────────────────────────────────────────── */}
      <div className={`bg-gradient-to-br ${gradient} py-16`}>
        <div className="mx-auto max-w-3xl px-6">
          {/* Branding */}
          <Link href="/" className="mb-8 inline-flex items-center gap-2 text-white/70 hover:text-white transition">
            <div className="flex h-7 w-7 items-center justify-center rounded-[10px] bg-white/20">
              <svg viewBox="0 0 24 24" fill="currentColor" className="h-4 w-4">
                <path d="M12 2 L14.4 9.6 L22 9.6 L15.8 14.1 L18.2 21.7 L12 17 L5.8 21.7 L8.2 14.1 L2 9.6 L9.6 9.6 Z"/>
              </svg>
            </div>
            <span className="text-sm font-semibold">MarketRipple</span>
          </Link>

          {/* Type badge */}
          <div className="mb-4 flex items-center gap-2">
            <span className="inline-flex items-center gap-1.5 rounded-full bg-white/20 px-3 py-1 text-xs font-medium text-white">
              {TYPE_ICON[type]}
              {label}
            </span>
            {entity.sector && (
              <span className="rounded-full bg-white/10 px-3 py-1 text-xs text-white/70">
                {entity.sector}
              </span>
            )}
          </div>

          {/* Title */}
          <h1 className="text-3xl font-bold text-white leading-tight sm:text-4xl">
            {entity.title}
          </h1>

          {/* Scores row */}
          {(entity.score !== undefined || entity.confidence !== undefined) && (
            <div className="mt-4 flex gap-4">
              {entity.score !== undefined && (
                <div className="text-center">
                  <div className="text-2xl font-bold text-white">{entity.score}</div>
                  <div className="text-xs text-white/60">Opportunity Score</div>
                </div>
              )}
              {entity.confidence !== undefined && (
                <div className="text-center">
                  <div className="text-2xl font-bold text-white">{entity.confidence}%</div>
                  <div className="text-xs text-white/60">AI Confidence</div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* ── Body ──────────────────────────────────────────────────────────── */}
      <div className="mx-auto max-w-3xl px-6 py-12">
        {/* AI Summary */}
        {entity.description && (
          <div className="mb-8 rounded-xl border border-white/[0.08] bg-white/[0.03] p-6">
            <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-300">
              <Brain className="h-4 w-4 text-violet-400" />
              AI Summary
            </div>
            <p className="text-slate-300 leading-relaxed">{entity.description}</p>
            {entity.summary && (
              <p className="mt-3 text-slate-400 text-sm leading-relaxed">{entity.summary}</p>
            )}
          </div>
        )}

        {/* Why MarketRipple */}
        <div className="mb-8 grid gap-4 sm:grid-cols-3">
          {[
            { icon: <Brain className="h-5 w-5 text-violet-400" />, title: "AI-Powered Analysis", desc: "Every insight is generated by AI trained on Indian market data." },
            { icon: <Shield className="h-5 w-5 text-emerald-400" />, title: "Evidence-Backed", desc: "Every conclusion links to sources you can verify independently." },
            { icon: <TrendingUp className="h-5 w-5 text-sky-400" />, title: "Full Transparency", desc: "See exactly how the AI reached its conclusions." },
          ].map(card => (
            <div key={card.title} className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-4">
              <div className="mb-2">{card.icon}</div>
              <div className="mb-1 text-sm font-semibold text-white">{card.title}</div>
              <div className="text-xs text-slate-400 leading-relaxed">{card.desc}</div>
            </div>
          ))}
        </div>

        {/* CTA */}
        <div className="rounded-xl border border-violet-500/20 bg-violet-500/10 p-6 text-center">
          <p className="mb-2 text-lg font-semibold text-white">
            Continue Reading on MarketRipple
          </p>
          <p className="mb-5 text-sm text-slate-400">
            Get the full AI analysis, investment thesis, scenario breakdown, and related intelligence — free, no signup required.
          </p>
          <Link
            href={entity.href as any}
            className="inline-flex items-center gap-2 rounded-xl bg-violet-600 px-6 py-3 font-semibold text-white shadow-lg shadow-violet-500/20 transition hover:bg-violet-500"
          >
            View Full Analysis
            <ArrowRight className="h-4 w-4" />
          </Link>
        </div>

        {/* Disclaimer */}
        <p className="mt-8 text-center text-xs text-slate-600">
          MarketRipple provides AI-generated market intelligence for research and educational purposes only.
          Not investment advice. Users remain responsible for all investment decisions.
        </p>

        {/* Back to home */}
        <div className="mt-6 text-center">
          <Link
            href="/"
            className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-300 transition"
          >
            <ExternalLink className="h-3.5 w-3.5" />
            Explore all market intelligence on MarketRipple
          </Link>
        </div>
      </div>
    </main>
  );
}
