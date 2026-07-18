import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import {
  ArrowLeft, TrendingUp, AlertTriangle, CheckCircle,
  Calendar, Building2, Activity,
} from "lucide-react";
import { AITransparencyPanel } from "@/components/ai/AITransparencyPanel";
import { AIDisclaimer } from "@/components/ai/AIDisclaimer";
import { InvestmentThesis, GrowthDrivers, OpportunityLifecycleCard, ScenarioAnalysis, MonitoringChecklist, PatternIntelligenceCard } from "@/components/intelligence";
import { ShareInsightCard } from "@/components/ShareInsightCard";
import { SmartCTA } from "@/components/SmartCTA";
import { RelatedContent } from "@/components/RelatedContent";
import { API_BASE_URL as API } from "@/lib/api";


interface StoryDetail {
  id: number;
  slug: string;
  title: string;
  description?: string;
  summary?: string;
  theme?: string;
  opportunity_score?: number | null;
  confidence?: number | null;
  trend?: string;
  risk_level?: string;
  time_horizon?: string;
  sectors?: string[];
  ai_summary?: {
    matters?: string;
    benefits?: string;
    risks?: string[];
    invalidate?: string;
    why_bullets?: string[];
  } | null;
  metrics?: {
    revenue_potential?: string;
    expected_cagr?: string;
    eps_growth?: string;
    investment_cycle?: string;
    market_size?: string;
  } | null;
  events?: {
    event_id?: string;
    title?: string;
    event_date?: string;
    tag?: string;
    description?: string;
  }[];
  companies?: {
    symbol?: string;
    company_name?: string;
    impact_score?: number | null;
    impact_label?: string;
    confidence?: number | null;
    reason?: string;
  }[];
  key_drivers?: string[];
}

async function getStory(slug: string): Promise<StoryDetail | null> {
  try {
    const res = await fetch(`${API}/api/stories/${slug}`, {
      next: { revalidate: 300 },
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const story = await getStory(slug);
  return {
    title: story
      ? `${story.title} — MarketRipple Stories`
      : "Story Not Found — MarketRipple",
    description:
      story?.description ??
      story?.summary ??
      "Investment theme analysis powered by AI.",
  };
}

export default async function StoryPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const story = await getStory(slug);

  if (!story) notFound();

  const score = story.opportunity_score ?? null;
  const confidence = story.confidence === null || story.confidence === undefined
    ? null
    : story.confidence <= 1
      ? Math.round(story.confidence * 100)
      : story.confidence;

  const scoreColor =
    score === null
      ? "text-slate-500"
      : score >= 80
      ? "text-emerald-400"
      : score >= 60
      ? "text-amber-400"
      : "text-rose-400";

  return (
    <main className="min-w-0 pb-16">
      {/* Back nav + share */}
      <div className="mb-6 flex items-center justify-between gap-4">
        <Link
          href="/stories"
          className="inline-flex items-center gap-2 text-sm text-slate-400 hover:text-white transition"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Stories
        </Link>
        <ShareInsightCard
          entityType="story"
          entityId={String(story.id)}
          title={story.title}
          summary={story.description ?? story.summary}
        />
      </div>

      {/* Smart CTAs */}
      <div className="mb-5 flex flex-wrap gap-2">
        <SmartCTA variant="ask-ai" href={`/ai-search?q=${encodeURIComponent(story.title.slice(0, 100))}`} />
        <SmartCTA variant="explore-opportunity" href="/radar" />
        <SmartCTA variant="see-companies" href="/companies" />
      </div>

      {/* Header */}
      <div className="mb-8 rounded-2xl border border-white/8 bg-slate-900/60 p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            {story.theme && (
              <p className="text-xs font-semibold uppercase tracking-widest text-violet-400 mb-2">
                {story.theme}
              </p>
            )}
            <h1 className="text-2xl font-bold text-white mb-3">
              {story.title}
            </h1>
            <p className="text-slate-400 text-sm leading-relaxed max-w-2xl">
              {story.description ?? story.summary ?? ""}
            </p>
            <div className="flex flex-wrap gap-2 mt-4">
              {story.sectors?.map((s: string) => (
                <span
                  key={s}
                  className="rounded-full border border-white/10 bg-white/5 px-2.5 py-0.5 text-xs text-slate-300"
                >
                  {s}
                </span>
              ))}
            </div>
          </div>
          <div className="text-center shrink-0">
            <div className={`text-4xl font-black ${scoreColor}`}>{score === null ? "—" : score}</div>
            <div className="text-xs text-slate-500 uppercase tracking-wider mt-1">
              Opportunity Score
            </div>
            <div className="mt-2 text-xs text-slate-400">
              {confidence === null ? "Confidence: Unscored" : `Confidence: ${confidence}%`}
            </div>
          </div>
        </div>

        {/* Meta row */}
        <div className="flex flex-wrap gap-3 mt-4 pt-4 border-t border-white/6">
          {story.risk_level && (
            <span className="flex items-center gap-1.5 text-xs text-slate-400">
              <AlertTriangle className="h-3.5 w-3.5 text-amber-400" />
              Risk: {story.risk_level}
            </span>
          )}
          {story.time_horizon && (
            <span className="flex items-center gap-1.5 text-xs text-slate-400">
              <Calendar className="h-3.5 w-3.5 text-sky-400" />
              {story.time_horizon}
            </span>
          )}
          {story.trend && (
            <span className="flex items-center gap-1.5 text-xs text-slate-400">
              <TrendingUp className="h-3.5 w-3.5 text-emerald-400" />
              {story.trend}
            </span>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">

          {/* AI Summary */}
          {story.ai_summary && (
            <section className="rounded-2xl border border-white/8 bg-slate-900/60 p-5">
              <h2 className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
                <Activity className="h-4 w-4 text-violet-400" />
                AI Analysis
              </h2>
              {story.ai_summary.matters && (
                <div className="mb-4">
                  <p className="text-xs text-slate-500 uppercase tracking-wider mb-1">
                    Why it Matters
                  </p>
                  <p className="text-sm text-slate-300">{story.ai_summary.matters}</p>
                </div>
              )}
              {story.ai_summary.benefits && (
                <div className="mb-4">
                  <p className="text-xs text-slate-500 uppercase tracking-wider mb-1">
                    Who Benefits
                  </p>
                  <p className="text-sm text-slate-300">{story.ai_summary.benefits}</p>
                </div>
              )}
              {story.ai_summary.why_bullets && story.ai_summary.why_bullets.length > 0 && (
                <div className="mb-4">
                  <p className="text-xs text-slate-500 uppercase tracking-wider mb-2">
                    Key Points
                  </p>
                  <ul className="space-y-1.5">
                    {story.ai_summary.why_bullets.map((b: string, i: number) => (
                      <li key={i} className="flex items-start gap-2 text-sm text-slate-300">
                        <CheckCircle className="h-4 w-4 text-emerald-400 mt-0.5 shrink-0" />
                        {b}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {story.ai_summary.risks && story.ai_summary.risks.length > 0 && (
                <div>
                  <p className="text-xs text-slate-500 uppercase tracking-wider mb-2">
                    Risks to Watch
                  </p>
                  <ul className="space-y-1.5">
                    {story.ai_summary.risks.map((r: string, i: number) => (
                      <li key={i} className="flex items-start gap-2 text-sm text-rose-300/80">
                        <AlertTriangle className="h-4 w-4 text-rose-400 mt-0.5 shrink-0" />
                        {r}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </section>
          )}

          {/* Intelligence Layer */}
          <InvestmentThesis
            entityType="story"
            entityId={String(story.id)}
            entityTitle={story.title}
            entityDescription={story.description ?? story.summary}
            entitySector={story.sectors?.[0]}
            thesis={story.summary ?? story.description ?? "This investment theme represents a structural opportunity in Indian markets."}
            whyItMatters={story.ai_summary?.matters}
            confidence={typeof story.confidence === "number"
              ? Math.round(story.confidence <= 1 ? story.confidence * 100 : story.confidence)
              : null
            }
            timeHorizon={story.time_horizon ?? "12–18 months"}
            keyDrivers={(story.key_drivers ?? []).slice(0, 4)}
            riskFactors={[
              ...(story.ai_summary?.risks ?? []).slice(0, 2),
              story.risk_level === "High" ? "High risk — significant execution uncertainty" : "Regulatory and execution risk",
              "Valuation risk — entry timing matters",
            ].filter(Boolean)}
          />

          <GrowthDrivers
            drivers={(story.ai_summary?.why_bullets ?? []).slice(0, 4).map((bullet: string, i: number) => ({
              title: bullet.length > 55 ? bullet.slice(0, 55) + "…" : bullet,
              description: bullet,
              impact: (i < 2 ? "high" : "medium") as "high" | "medium" | "low",
              timeframe: story.time_horizon ?? "Medium-term",
            }))}
          />

          <OpportunityLifecycleCard
            stage={(() => {
              const trend = story.trend ?? "stable";
              const oppScore = typeof story.opportunity_score === "number" ? story.opportunity_score : null;
              if (oppScore !== null) {
                if (trend === "up" && oppScore > 80) return "strong-momentum" as const;
                if (trend === "up" && oppScore > 60) return "developing" as const;
              }
              if (trend === "down") return "mature" as const;
              return "emerging" as const;
            })()}
            description={`${story.risk_level ?? "Moderate"} risk · ${story.time_horizon ?? "Medium-term"} horizon`}
            whyAssigned={story.ai_summary?.matters ?? `This theme scores ${story.opportunity_score ?? "N/A"}/100 on opportunity with a ${story.trend === "up" ? "rising" : "stable"} trend signal.`}
            historicalComparison={`Similar investment themes in the ${story.sectors?.[0] ?? "market"} have historically taken 12–24 months to fully play out from the ${story.trend === "up" && typeof story.opportunity_score === "number" && story.opportunity_score > 70 ? "developing" : "emerging"} stage.`}
            confidence={typeof story.opportunity_score === "number" ? Math.min(90, Math.round(story.opportunity_score * 0.85)) : null}
            expectedEvolution={story.ai_summary?.why_bullets?.[0] ?? `The theme is expected to ${story.trend === "up" ? "gain broader market recognition and institutional coverage" : "consolidate before the next major catalyst emerges"}.`}
            risks={[
              `Narrative risk: theme becomes consensus before price moves`,
              `${story.risk_level === "high" ? "High risk of adverse policy or macro reversal" : "Execution risk if key catalysts are delayed"}`,
              "Sector rotation could redirect institutional attention",
            ]}
          />

          <ScenarioAnalysis
            entityType="story"
            entityId={String(story.id)}
            entityTitle={story.title}
            entityDescription={story.description ?? story.summary}
            entitySector={story.sectors?.[0]}
          />
          <MonitoringChecklist
            entityType="story"
            entityId={String(story.id)}
            entityTitle={story.title}
            entityDescription={story.description ?? story.summary}
            entitySector={story.sectors?.[0]}
          />
          <PatternIntelligenceCard
            entityType="story"
            entityId={String(story.id)}
            entityTitle={story.title}
            entityDescription={story.description ?? story.summary}
            entitySector={story.sectors?.[0]}
          />

          {/* Companies */}
          {story.companies && story.companies.length > 0 && (
            <section className="rounded-2xl border border-white/8 bg-slate-900/60 p-5">
              <h2 className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
                <Building2 className="h-4 w-4 text-sky-400" />
                Companies Impacted
              </h2>
              <div className="space-y-2">
                {story.companies.map((c: any, i: number) => (
                  <div
                    key={i}
                    className="flex items-center justify-between py-2 border-b border-white/5 last:border-0"
                  >
                    <div>
                      <p className="text-sm font-medium text-white">
                        {c.company_name ?? c.symbol}
                      </p>
                      {c.reason && (
                        <p className="text-xs text-slate-400 mt-0.5">{c.reason}</p>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      {c.impact_label && (
                        <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-300 border border-emerald-500/20">
                          {c.impact_label}
                        </span>
                      )}
                      {c.impact_score !== null && c.impact_score !== undefined && (
                        <span className="text-sm font-mono font-semibold text-emerald-400">
                          {c.impact_score}
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* Related Events */}
          {story.events && story.events.length > 0 && (
            <section className="rounded-2xl border border-white/8 bg-slate-900/60 p-5">
              <h2 className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
                <Calendar className="h-4 w-4 text-amber-400" />
                Driving Events
              </h2>
              <div className="space-y-3">
                {story.events.map((e: any, i: number) => (
                  <div
                    key={i}
                    className="flex items-start gap-3 py-2 border-b border-white/5 last:border-0"
                  >
                    <div className="shrink-0 mt-0.5">
                      {e.tag && (
                        <span className="text-xs px-1.5 py-0.5 rounded bg-violet-500/15 text-violet-300">
                          {e.tag}
                        </span>
                      )}
                    </div>
                    <div>
                      <p className="text-sm font-medium text-white">
                        {e.event_id ? (
                          <Link
                            href={`/events/${e.event_id}`}
                            className="hover:text-violet-300 transition"
                          >
                            {e.title}
                          </Link>
                        ) : (
                          e.title
                        )}
                      </p>
                      {e.description && (
                        <p className="text-xs text-slate-400 mt-0.5">{e.description}</p>
                      )}
                      {e.event_date && (
                        <p className="text-xs text-slate-500 mt-1">
                          {new Date(e.event_date).toLocaleDateString("en-IN", {
                            day: "numeric",
                            month: "short",
                            year: "numeric",
                          })}
                        </p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}

        </div>

        <div className="space-y-6">
          {/* Metrics */}
          {story.metrics && (
            <section className="rounded-2xl border border-white/8 bg-slate-900/60 p-5">
              <h2 className="text-sm font-semibold text-white mb-4">Key Metrics</h2>
              <div className="space-y-3">
                {Object.entries(story.metrics)
                  .filter(([, v]) => v)
                  .map(([k, v]) => (
                    <div key={k} className="flex items-center justify-between">
                      <span className="text-xs text-slate-400 capitalize">
                        {k.replace(/_/g, " ")}
                      </span>
                      <span className="text-sm font-semibold text-white">{v as string}</span>
                    </div>
                  ))}
              </div>
            </section>
          )}

          {/* Key Drivers */}
          {story.key_drivers && story.key_drivers.length > 0 && (
            <section className="rounded-2xl border border-white/8 bg-slate-900/60 p-5">
              <h2 className="text-sm font-semibold text-white mb-4">Key Drivers</h2>
              <ul className="space-y-2">
                {story.key_drivers.map((d: string, i: number) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-slate-300">
                    <span className="text-violet-400 mt-0.5">-&gt;</span>
                    {d}
                  </li>
                ))}
              </ul>
            </section>
          )}

          {/* AI Transparency */}
          <AITransparencyPanel
            confidence={confidence}
            reasoning={`AI analysis for the ${story.title} investment theme based on related events, company data, and sector trends.`}
            companies={
              story.companies?.slice(0, 5).map((c: any) => ({
                name: c.company_name ?? c.symbol,
                symbol: c.symbol,
                href: `/companies/${c.symbol}`,
              })) ?? []
            }
            events={
              story.events?.slice(0, 5).map((e: any) => ({
                title: e.title,
                href: e.event_id ? `/events/${e.event_id}` : undefined,
              })) ?? []
            }
            assumptions={[
              "Based on current market conditions and publicly available data",
              "Past performance does not guarantee future results",
              "Investment decisions should consider individual risk tolerance",
            ]}
            compact
          />
        </div>
      </div>

      {/* Related Intelligence */}
      <div className="mt-6">
        <RelatedContent
          entityType="story"
          entityId={String(story.id)}
          title={story.title}
          sector={story.sectors?.[0]}
        />
      </div>

      {/* AI Disclaimer */}
      <div className="mt-8">
        <AIDisclaimer />
      </div>
    </main>
  );
}
