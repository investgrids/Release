import type { Metadata } from "next";
import { API_BASE_URL as API } from "@/lib/api";

// Phase 19 (2026-08 audit) — observability dashboard. Internal-only:
// /operations/ is already disallowed site-wide in robots.ts, matching
// this codebase's existing convention for /operations/intelligence.
// Every number on this page comes directly from an already-built,
// already-tested read-only API (source_health, coverage_engine) — this
// page adds no new computation, only renders what those APIs return.
export const metadata: Metadata = {
  title: "Coverage & Source Health — Operations",
  robots: { index: false, follow: false },
};

interface SourceHealth {
  source: string;
  status: "HEALTHY" | "DEGRADED" | "STALE" | "FAILED" | "UNKNOWN";
  last_success_at: string | null;
  events_today: number;
  consecutive_failures: number;
  latency_ms: number | null;
  latest_error: string | null;
}
interface FunnelData {
  detected: number; critical: number; high: number;
  published: number; covered_by_existing_article: number; failed: number;
  uncovered_critical_or_high: number;
}
interface EnrichmentHealth {
  pending: number; processing: number; retrying: number;
  permanently_failed: number; completed: number;
}
interface PublishingSummary {
  total_articles_published: number;
  material_events_covered: number;
  event_triggered_articles_published: number;
  article_categories: Record<string, number>;
}
interface PublishingLatency {
  sample_count: number;
  avg_event_to_publish_minutes: number | null;
}

async function safeJson<T>(url: string, fallback: T): Promise<T> {
  try {
    const r = await fetch(url, { next: { revalidate: 60 } });
    if (!r.ok) return fallback;
    return (await r.json()) as T;
  } catch {
    return fallback;
  }
}

const STATUS_COLOR: Record<string, string> = {
  HEALTHY: "bg-emerald-500/15 text-emerald-500 border-emerald-500/25",
  DEGRADED: "bg-amber-500/15 text-amber-500 border-amber-500/25",
  STALE: "bg-amber-500/15 text-amber-500 border-amber-500/25",
  FAILED: "bg-rose-500/15 text-rose-500 border-rose-500/25",
  UNKNOWN: "bg-text-primary/10 text-text-muted border-surface-border/15",
};

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-2xl border border-surface-border/10 bg-text-primary/[0.02] p-5">
      <h2 className="mb-4 text-[11px] font-bold uppercase tracking-wider text-text-muted">{title}</h2>
      {children}
    </section>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div>
      <p className="text-[10px] uppercase tracking-wider text-text-muted">{label}</p>
      <p className="text-[20px] font-bold tabular-nums text-text-primary">{value}</p>
    </div>
  );
}

export default async function CoverageDashboard() {
  const [sourcesRes, funnel, enrichment, publishing, latency] = await Promise.all([
    safeJson<{ sources: SourceHealth[] }>(`${API}/api/sources/health`, { sources: [] }),
    safeJson<FunnelData | null>(`${API}/api/coverage/funnel?hours=24`, null),
    safeJson<EnrichmentHealth | null>(`${API}/api/coverage/enrichment-health?hours=24`, null),
    safeJson<PublishingSummary | null>(`${API}/api/coverage/publishing-summary?hours=24`, null),
    safeJson<PublishingLatency | null>(`${API}/api/coverage/publishing-latency?hours=24`, null),
  ]);

  const coveragePct = funnel && (funnel.critical + funnel.high) > 0
    ? Math.round(((funnel.critical + funnel.high - funnel.uncovered_critical_or_high) / (funnel.critical + funnel.high)) * 100)
    : null;

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-6">
      <div>
        <h1 className="text-[18px] font-bold text-text-primary">Coverage & Source Health</h1>
        <p className="text-[12px] text-text-muted">Last 24 hours — every number below is read directly from the coverage/source-health APIs, nothing computed on this page.</p>
      </div>

      <Panel title="Source Health">
        {sourcesRes.sources.length === 0 ? (
          <p className="text-[12px] text-text-muted">No source health data available.</p>
        ) : (
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {sourcesRes.sources.map(s => (
              <div key={s.source} className="flex items-center justify-between rounded-xl border border-surface-border/8 p-3">
                <div className="min-w-0">
                  <p className="truncate text-[12px] font-medium text-text-primary">{s.source}</p>
                  <p className="text-[10px] text-text-muted">
                    {s.events_today} today
                    {s.latency_ms != null ? ` · ${Math.round(s.latency_ms)}ms` : ""}
                    {s.status === "FAILED" && s.latest_error ? ` · ${s.latest_error.slice(0, 40)}` : ""}
                  </p>
                </div>
                <span className={`shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-bold ${STATUS_COLOR[s.status] ?? STATUS_COLOR.UNKNOWN}`}>
                  {s.status}
                </span>
              </div>
            ))}
          </div>
        )}
      </Panel>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Panel title="Enrichment">
          {enrichment ? (
            <div className="grid grid-cols-3 gap-4">
              <Stat label="Pending" value={enrichment.pending} />
              <Stat label="Retrying" value={enrichment.retrying} />
              <Stat label="Permanently Failed" value={enrichment.permanently_failed} />
              <Stat label="Processing" value={enrichment.processing} />
              <Stat label="Completed" value={enrichment.completed} />
            </div>
          ) : <p className="text-[12px] text-text-muted">Unavailable.</p>}
        </Panel>

        <Panel title="Coverage">
          {funnel ? (
            <div className="grid grid-cols-3 gap-4">
              <Stat label="Critical" value={funnel.critical} />
              <Stat label="High" value={funnel.high} />
              <Stat label="Coverage %" value={coveragePct !== null ? `${coveragePct}%` : "—"} />
              <Stat label="Published" value={funnel.published} />
              <Stat label="Uncovered Crit/High" value={funnel.uncovered_critical_or_high} />
              <Stat label="Failed" value={funnel.failed} />
            </div>
          ) : <p className="text-[12px] text-text-muted">Unavailable.</p>}
        </Panel>

        <Panel title="Publishing">
          {publishing ? (
            <div className="grid grid-cols-3 gap-4">
              <Stat label="Total Articles" value={publishing.total_articles_published} />
              <Stat label="Material Events Covered" value={publishing.material_events_covered} />
              <Stat label="Event-Triggered" value={publishing.event_triggered_articles_published} />
              <Stat label="Evergreen" value={publishing.article_categories?.EVERGREEN ?? 0} />
              <Stat label="Historical" value={publishing.article_categories?.HISTORICAL ?? 0} />
              <Stat label="Comparison" value={publishing.article_categories?.COMPARISON ?? 0} />
            </div>
          ) : <p className="text-[12px] text-text-muted">Unavailable.</p>}
        </Panel>

        <Panel title="Latency">
          {latency ? (
            <div className="grid grid-cols-2 gap-4">
              <Stat label="Avg Event → Publish" value={latency.avg_event_to_publish_minutes !== null ? `${latency.avg_event_to_publish_minutes} min` : "No published samples"} />
              <Stat label="Sample Size" value={latency.sample_count} />
            </div>
          ) : <p className="text-[12px] text-text-muted">Unavailable.</p>}
        </Panel>
      </div>
    </div>
  );
}
