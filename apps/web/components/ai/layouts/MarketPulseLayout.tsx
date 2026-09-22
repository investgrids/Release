"use client";

// market_pulse — canonical-core audit (2026-09-22). Sourced ENTIRELY
// from AEV2MarketPulseAnswer (answerTypes.ts), itself built only from
// assemble_aev2()'s real, separate AEV2MarketPulse shape — never a
// plain SearchResult field. See answerTypes.ts's own module-boundary
// comment: no live HTTP path to this data exists yet, so this component
// is developed and tested against fixtures mirroring exactly what
// aev2/market_pulse.py already produces server-side.
//
// No generic Research Outlook, investment verdict, suitability,
// horizon, or self-rated confidence section — AEV2MarketPulseAnswer
// carries no `raw: SearchResult` and AEV2MarketPulse itself has no
// field for any of them (aev2/market_pulse.py's own docstring: risk's
// self-rated confidence is dropped unconditionally; there is no
// standard four-component confidence formula here at all). Evidence
// Coverage + real source timestamps stand in for it instead (section 11
// below).
import { AIAnswerShell } from "../AIAnswerShell";
import type { AEV2MarketPulseAnswer } from "../answerTypes";
import { formatShortDate } from "../answerTypes";
import type { AEV2MarketMover, AEV2MarketValue } from "../aev2Types";

function ValueBadge({ mv, positiveHint }: { mv: AEV2MarketValue | null; positiveHint?: boolean }) {
  if (!mv) return <span className="text-text-muted">—</span>;
  const isNegative = mv.value.trim().startsWith("-");
  const color = positiveHint === undefined
    ? "text-text-primary"
    : isNegative ? "text-rose-400" : "text-emerald-400";
  return <span className={`tabular-nums font-semibold ${color}`}>{mv.value}</span>;
}

function MoverRow({ mover }: { mover: AEV2MarketMover }) {
  return (
    <div className="rounded-[14px] border border-surface-border/7 bg-text-primary/[0.02] px-4 py-3">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-[13px] font-bold text-text-primary">{mover.company}</p>
          <p className="text-[11px] text-text-muted">{mover.ticker}</p>
        </div>
        <div className="text-right">
          <ValueBadge mv={mover.change} positiveHint={!mover.change?.value.trim().startsWith("-")} />
          <p className="text-[11px] text-text-muted">
            <ValueBadge mv={mover.price} />
          </p>
        </div>
      </div>
      {/* Verified market drivers — real EventTriage-linked evidence
          only; [] renders the honest "no verified driver" state, never
          a filled-in placeholder. */}
      {mover.verified_drivers.length > 0 ? (
        <ul className="mt-2 space-y-1">
          {mover.verified_drivers.map((d, i) => (
            <li key={i} className="text-[11px] text-text-secondary">
              <span className="font-semibold text-text-primary">{d.driver}</span>
              {d.confidence_tier && <span className="text-text-muted"> · {d.confidence_tier} confidence</span>}
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-2 text-[11px] text-text-muted">No verified driver identified for this move.</p>
      )}
      {mover.narrative && (
        <p className="mt-1.5 text-[11.5px] leading-5 text-text-secondary">{mover.narrative}</p>
      )}
    </div>
  );
}

export function MarketPulseLayout({
  answer, onNewSearch, onRefine,
}: {
  answer: AEV2MarketPulseAnswer;
  onNewSearch: () => void;
  onRefine?: () => void;
}) {
  const { aev2: mp } = answer;
  const asOfDisplay = formatShortDate(mp.as_of) ?? mp.as_of;

  return (
    <AIAnswerShell
      query={answer.query}
      uiMode="market_pulse"
      sourceCount={mp.evidence_coverage.tracked_event_count + mp.evidence_coverage.calendar_event_count}
      evidenceRows={[]}
      evidenceCoverage={null}
      showConfidence={false}
      sidebarSnapshot={
        <div className="space-y-4">
          {/* 1. Market state */}
          <div className="rounded-[20px] border border-surface-border/7 bg-text-primary/[0.03] p-5">
            <p className="text-[13px] font-semibold text-text-primary mb-1">Market State</p>
            <p className="text-[12px] text-text-secondary capitalize">{mp.market_status ?? "unknown"}</p>
            <p className="text-[11px] text-text-muted capitalize">Session: {mp.market_session ?? "unknown"}</p>
            {asOfDisplay && <p className="mt-1 text-[10px] text-text-muted">As of {asOfDisplay}</p>}
          </div>
          {/* 11. Evidence Coverage — stands in for the standard research
              confidence formula, which has no comparable
              historical_similarity/company-attribution contract here. */}
          <div className="rounded-[20px] border border-surface-border/7 bg-text-primary/[0.03] p-5">
            <p className="text-[13px] font-semibold text-text-primary mb-2">Evidence Coverage</p>
            <p className="text-[11px] text-text-secondary">
              {mp.evidence_coverage.movers_with_driver} of {mp.evidence_coverage.movers_total} movers have a verified driver
            </p>
            <p className="text-[11px] text-text-secondary">{mp.evidence_coverage.tracked_event_count} tracked event citation(s)</p>
            <p className="text-[11px] text-text-secondary">{mp.evidence_coverage.calendar_event_count} upcoming calendar source(s)</p>
          </div>
        </div>
      }
      onNewSearch={onNewSearch}
      onRefine={onRefine}
    >
      {/* 10. Generated summary — validated only; structurally omitted
          (not a filler sentence) when synthesis is unavailable. */}
      {mp.generated_summary && (
        <div>
          <p className="text-[10px] uppercase tracking-widest text-text-muted mb-1.5">Market Summary</p>
          <p className="text-[15px] leading-7 font-semibold text-text-primary">{mp.generated_summary.text}</p>
        </div>
      )}
      {mp.synthesis_status === "unavailable" && (
        <p className="text-[12px] text-text-muted italic">
          A written summary couldn't be shown for this update. The real market data below is unaffected.
        </p>
      )}

      {/* 2. Major indices with five-day movement */}
      {mp.indices.length > 0 && (
        <div className="mt-5">
          <p className="text-[10px] uppercase tracking-widest text-text-muted mb-1.5">Major Indices</p>
          <div className="grid gap-3 sm:grid-cols-2">
            {mp.indices.map(idx => (
              <div key={idx.ticker} className="rounded-[14px] border border-surface-border/7 bg-text-primary/[0.02] px-4 py-3">
                <div className="flex items-center justify-between">
                  <p className="text-[13px] font-bold text-text-primary">{idx.name}</p>
                  <ValueBadge mv={idx.change} positiveHint={!idx.change?.value.trim().startsWith("-")} />
                </div>
                <p className="text-[13px] text-text-secondary tabular-nums">{idx.price?.value ?? "—"}</p>
                {idx.chart.length > 0 && (
                  <div className="mt-2 flex items-end gap-0.5 h-6">
                    {idx.chart.map((pt, i) => {
                      const values = idx.chart.map(p => p.value);
                      const min = Math.min(...values), max = Math.max(...values);
                      const range = max - min || 1;
                      const h = Math.max(4, ((pt.value - min) / range) * 24);
                      return <div key={i} className="flex-1 rounded-sm bg-violet-400/50" style={{ height: `${h}px` }} title={`${pt.label}: ${pt.value}`} />;
                    })}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 3. Leading and lagging ETF-based sectors */}
      {(mp.sector_movement.leading.length > 0 || mp.sector_movement.lagging.length > 0) && (
        <div className="mt-5 grid gap-4 sm:grid-cols-2">
          <div>
            <p className="text-[10px] uppercase tracking-widest text-text-muted mb-1.5">Leading Sectors</p>
            <ul className="space-y-1.5">
              {mp.sector_movement.leading.map(s => (
                <li key={s.id} className="flex items-center justify-between text-[12.5px]">
                  <span className="text-text-primary font-medium">{s.name}</span>
                  <ValueBadge mv={s.change} positiveHint={!s.change?.value.trim().startsWith("-")} />
                </li>
              ))}
            </ul>
          </div>
          <div>
            <p className="text-[10px] uppercase tracking-widest text-text-muted mb-1.5">Lagging Sectors</p>
            <ul className="space-y-1.5">
              {mp.sector_movement.lagging.map(s => (
                <li key={s.id} className="flex items-center justify-between text-[12.5px]">
                  <span className="text-text-primary font-medium">{s.name}</span>
                  <ValueBadge mv={s.change} positiveHint={!s.change?.value.trim().startsWith("-")} />
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {/* 4 & 5. Top gainers, losers, most active — with verified drivers */}
      {(mp.movers.gainers.length > 0 || mp.movers.losers.length > 0) && (
        <div className="mt-5 grid gap-4 sm:grid-cols-2">
          {mp.movers.gainers.length > 0 && (
            <div>
              <p className="text-[10px] uppercase tracking-widest text-text-muted mb-1.5">Top Gainers</p>
              <div className="space-y-2">
                {mp.movers.gainers.map(m => <MoverRow key={m.ticker} mover={m} />)}
              </div>
            </div>
          )}
          {mp.movers.losers.length > 0 && (
            <div>
              <p className="text-[10px] uppercase tracking-widest text-text-muted mb-1.5">Top Losers</p>
              <div className="space-y-2">
                {mp.movers.losers.map(m => <MoverRow key={m.ticker} mover={m} />)}
              </div>
            </div>
          )}
        </div>
      )}
      {mp.movers.most_active.length > 0 && (
        <div className="mt-5">
          <p className="text-[10px] uppercase tracking-widest text-text-muted mb-1.5">Most Active</p>
          <div className="space-y-2">
            {mp.movers.most_active.map(m => <MoverRow key={m.ticker} mover={m} />)}
          </div>
        </div>
      )}

      {/* 6. Theme momentum — clearly labeled as a computed score, never
          confused with the verified-driver evidence above. */}
      {mp.theme_momentum.length > 0 && (
        <div className="mt-5">
          <p className="text-[10px] uppercase tracking-widest text-text-muted mb-1.5">Theme Momentum</p>
          <p className="text-[10.5px] text-text-muted mb-2">Computed score — 60% live price signal, 40% recent news activity.</p>
          <div className="flex flex-wrap gap-2">
            {mp.theme_momentum.map(t => (
              <div key={t.theme} className="rounded-full border border-surface-border/10 bg-text-primary/[0.03] px-3 py-1.5 text-[11.5px]">
                <span className="font-semibold text-text-primary">{t.theme}</span>
                <span className="ml-1.5 text-text-muted">{t.score != null ? Math.round(t.score) : "—"}/100 · {t.momentum ?? "stable"}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 7. Biggest public Opportunity — score explicitly labeled, never
          a forecast probability. Omitted entirely when none resolves. */}
      {mp.biggest_opportunity && (
        <div className="mt-5 rounded-[14px] border border-emerald-500/20 bg-emerald-500/[0.05] px-4 py-3">
          <p className="text-[10px] uppercase tracking-widest text-text-muted mb-1">Biggest Opportunity</p>
          <a href={mp.biggest_opportunity.href} className="text-[13px] font-semibold text-text-primary hover:underline">
            {mp.biggest_opportunity.title}
          </a>
          {mp.biggest_opportunity.opportunity_score != null && (
            <p className="mt-1 text-[11px] text-text-muted">
              Opportunity score: <span className="font-bold text-emerald-600 dark:text-emerald-300">{Math.round(mp.biggest_opportunity.opportunity_score)}</span>
            </p>
          )}
        </div>
      )}

      {/* 8. Verified risk or AI-identified consideration — the two
          branches are NEVER shown with the same label. */}
      {mp.risk_context && (
        <div className="mt-5 rounded-[14px] border border-amber-500/20 bg-amber-500/[0.05] px-4 py-3">
          <p className="text-[10px] uppercase tracking-widest text-amber-600 dark:text-amber-400 mb-1">
            {mp.risk_context.source === "tracked_event" ? "Verified market risk" : "AI-identified consideration"}
          </p>
          <p className="text-[13px] text-text-primary">
            {mp.risk_context.source === "tracked_event" ? mp.risk_context.title : mp.risk_context.text}
          </p>
          {mp.risk_context.source === "tracked_event" && mp.risk_context.published_at && (
            <p className="mt-1 text-[10px] text-text-muted">{formatShortDate(mp.risk_context.published_at) ?? mp.risk_context.published_at}</p>
          )}
        </div>
      )}

      {/* 9. Upcoming calendar events */}
      {mp.upcoming_events.length > 0 && (
        <div className="mt-5">
          <p className="text-[10px] uppercase tracking-widest text-text-muted mb-1.5">Upcoming</p>
          <ul className="space-y-1.5">
            {mp.upcoming_events.map(e => (
              <li key={e.id} className="flex items-center justify-between text-[12.5px]">
                <span className="text-text-primary">{e.title}</span>
                <span className="text-text-muted">{e.date ?? ""}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* 10 (cont.) Generated conclusion — validated only. */}
      {mp.generated_conclusion && (
        <div className="mt-5">
          <p className="text-[10px] uppercase tracking-widest text-text-muted mb-1.5">Analysis</p>
          <p className="text-[13px] leading-6 text-text-secondary">{mp.generated_conclusion.text}</p>
        </div>
      )}
    </AIAnswerShell>
  );
}
