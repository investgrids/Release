import Link from "next/link";
import { Flame, Sparkles, AlertTriangle, Trophy, Newspaper, ArrowRight } from "lucide-react";
import { fetchAPI } from "@/lib/api";

// Real data only, every section — no fabricated numbers. Confirmed live
// before building this: /api/company-scores/ has no score-history field
// (so no honest "Fastest Improving Companies" section is possible without
// a backend change), and there's no comparison-usage tracking anywhere in
// the app (so no honest "Recently Compared Companies" either) — both were
// in the original 7-section spec, both omitted here rather than faked,
// same principle already agreed for Opportunity Radar's "Today's
// Opportunities". The 5 sections below are each backed by a real endpoint.

interface CompanyScoreContributor {
  reason: string | null;
  source_type: "article" | "opportunity";
  signed_magnitude: number;
  signal_at: string | null;
}
interface CompanyScoreRow {
  symbol: string;
  score: number | null;
  confidence: number | null;
  signal_count: number;
  sector: string | null;
  top_contributors: CompanyScoreContributor[];
}
interface SectorRow { id: string; name: string; value: string; positive: boolean; }
interface ArticleRow { slug: string; headline: string; angle_entity?: string | null; published_at?: string; }

async function getCompanyScores(): Promise<CompanyScoreRow[]> {
  const data = await fetchAPI<{ companies: CompanyScoreRow[] }>("/api/company-scores/?limit=50").catch(() => null);
  return data?.companies ?? [];
}
async function getSectors(): Promise<SectorRow[]> {
  return await fetchAPI<SectorRow[]>("/api/sectors").catch(() => []) ?? [];
}
async function getLatestCompanyArticles(): Promise<ArticleRow[]> {
  const data = await fetchAPI<{ items: ArticleRow[] }>("/api/insights/?article_type=company_intelligence&limit=4").catch(() => null);
  return data?.items ?? [];
}

function displayName(symbol: string) {
  return symbol.replace(/^NSE_/, "");
}

function SectionCard({
  icon, title, href, children,
}: { icon: React.ReactNode; title: string; href: string; children: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-surface-border/7 bg-surface-card p-4">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-violet-500/10 text-accent-violet">{icon}</span>
          <h3 className="text-[13px] font-bold text-text-primary">{title}</h3>
        </div>
        <Link href={href as any} className="flex items-center gap-0.5 text-[11px] font-semibold text-accent-violet hover:opacity-80 transition">
          View All <ArrowRight className="h-3 w-3" />
        </Link>
      </div>
      {children}
    </div>
  );
}

export async function OverviewTab() {
  const [scores, sectors, articles] = await Promise.all([
    getCompanyScores(),
    getSectors(),
    getLatestCompanyArticles(),
  ]);

  const scored = scores.filter(s => s.score !== null);
  // "Trending" = most recently signaled, not a fabricated popularity metric.
  const trending = [...scored]
    .sort((a, b) => new Date(b.top_contributors[0]?.signal_at ?? 0).getTime() - new Date(a.top_contributors[0]?.signal_at ?? 0).getTime())
    .slice(0, 5);
  const topPicks = [...scored].sort((a, b) => (b.score ?? 0) - (a.score ?? 0)).slice(0, 5);
  const underPressure = [...scored].sort((a, b) => (a.score ?? 0) - (b.score ?? 0)).slice(0, 5);
  const bestSectors = [...sectors]
    .map(s => ({ ...s, pct: parseFloat(s.value) }))
    .sort((a, b) => b.pct - a.pct)
    .slice(0, 5);

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <SectionCard icon={<Flame className="h-3.5 w-3.5" />} title="Trending Companies" href="/companies?tab=all-companies">
        {trending.length === 0 ? <p className="text-[12px] text-text-muted">No recent signals yet.</p> : (
          <ul className="space-y-2">
            {trending.map(c => (
              <li key={c.symbol}>
                <Link href={`/companies/${displayName(c.symbol)}`} className="flex items-center justify-between rounded-lg px-2 py-1.5 transition hover:bg-text-primary/[0.04]">
                  <span className="text-[12.5px] font-semibold text-text-primary">{displayName(c.symbol)}</span>
                  <span className="text-[11px] text-text-muted line-clamp-1 max-w-[55%] text-right">{c.top_contributors[0]?.reason ?? ""}</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </SectionCard>

      <SectionCard icon={<Sparkles className="h-3.5 w-3.5" />} title="AI Top Picks" href="/companies?tab=best-stocks">
        {topPicks.length === 0 ? <p className="text-[12px] text-text-muted">No scored companies yet.</p> : (
          <ul className="space-y-2">
            {topPicks.map(c => (
              <li key={c.symbol}>
                <Link href={`/companies/${displayName(c.symbol)}`} className="flex items-center justify-between rounded-lg px-2 py-1.5 transition hover:bg-text-primary/[0.04]">
                  <span className="text-[12.5px] font-semibold text-text-primary">{displayName(c.symbol)}</span>
                  <span className="text-[12px] font-bold text-emerald-400 tabular-nums">{c.score?.toFixed(0)}</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </SectionCard>

      <SectionCard icon={<AlertTriangle className="h-3.5 w-3.5" />} title="Companies Under Pressure" href="/companies?tab=all-companies">
        {underPressure.length === 0 ? <p className="text-[12px] text-text-muted">No scored companies yet.</p> : (
          <ul className="space-y-2">
            {underPressure.map(c => (
              <li key={c.symbol}>
                <Link href={`/companies/${displayName(c.symbol)}`} className="flex items-center justify-between rounded-lg px-2 py-1.5 transition hover:bg-text-primary/[0.04]">
                  <span className="text-[12.5px] font-semibold text-text-primary">{displayName(c.symbol)}</span>
                  <span className="text-[12px] font-bold text-amber-500 tabular-nums">{c.score?.toFixed(0)}</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </SectionCard>

      <SectionCard icon={<Trophy className="h-3.5 w-3.5" />} title="Best Performing Sectors" href="/companies?tab=sectors">
        {bestSectors.length === 0 ? <p className="text-[12px] text-text-muted">Sector data unavailable.</p> : (
          <ul className="space-y-2">
            {bestSectors.map(s => (
              <li key={s.id}>
                <Link href={`/sectors/${s.id}`} className="flex items-center justify-between rounded-lg px-2 py-1.5 transition hover:bg-text-primary/[0.04]">
                  <span className="text-[12.5px] font-semibold text-text-primary">{s.name}</span>
                  <span className={`text-[12px] font-bold tabular-nums ${s.positive ? "text-emerald-400" : "text-rose-400"}`}>{s.value}</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </SectionCard>

      <SectionCard icon={<Newspaper className="h-3.5 w-3.5" />} title="Latest Company Intelligence" href="/newsroom">
        {articles.length === 0 ? <p className="text-[12px] text-text-muted">No company articles yet.</p> : (
          <ul className="space-y-2">
            {articles.map(a => (
              <li key={a.slug}>
                <Link href={`/newsroom/article/${a.slug}`} className="block rounded-lg px-2 py-1.5 transition hover:bg-text-primary/[0.04]">
                  <span className="line-clamp-2 text-[12.5px] font-semibold leading-snug text-text-primary">{a.headline}</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </SectionCard>
    </div>
  );
}
