import { Landmark, Megaphone, Newspaper, Radar, Rocket, TrendingUp } from "lucide-react";
import type { WeekendNewSinceCloseItem } from "@/types/weekendIntelligence";
import { sectorDirectionStyle } from "./weekendLabels";

const SOURCE_TYPE_LABEL: Record<string, string> = {
  event: "Event",
  policy: "Policy",
  announcement: "Announcement",
  news: "News",
  company_signal: "Company Signal",
  opportunity: "Opportunity",
};

// Real source-type icons, not a decorative repeat of the same glyph —
// each one already used elsewhere in this app for the same concept
// (Landmark for policy, Rocket for opportunities in WeekendOpportunities,
// TrendingUp for company signals), so this stays visually consistent
// rather than inventing a new icon language just for this list.
const SOURCE_TYPE_ICON: Record<string, typeof Newspaper> = {
  event: Radar,
  policy: Landmark,
  announcement: Megaphone,
  news: Newspaper,
  company_signal: TrendingUp,
  opportunity: Rocket,
};

/**
 * "What Changed Since Market Close" — brief §11, one of the most
 * important sections. Uses new_since_close (already materiality-
 * filtered by the backend), NOT changes_since_prior — see
 * WeekendChangesSincePrior for that separate, secondary concept.
 * The card itself stays a fixed 360-400px (≈5 rows visible, matching
 * the reference), but renders every real item the backend returned
 * (already ranked, never re-sorted here) — beyond the first ~5 the list
 * scrolls internally (owner correction, 2026-08-15) rather than hard-
 * truncating rows a user can never reach.
 *
 * 2026-08-22 fix (user-reported: "why homepage i am able to scroll
 * after footer also") — with a real weekend's worth of items (68 rows
 * observed live), the inner <ul>'s overflow-y-auto correctly clips and
 * scrolls it VISUALLY within the card's 400px box, but its full,
 * unclipped scrollHeight (~4600px for 68 rows) was still leaking into
 * document.documentElement.scrollHeight — confirmed live via bisection
 * (isolating this exact element dropped the homepage's real scrollable
 * height by ~2900px) and confirmed the fix by directly toggling CSS
 * containment in the browser before touching this file. `contain:
 * layout` on the card gives the browser an explicit boundary — "nothing
 * in here affects layout/scroll outside this box" — which is what
 * `overflow: hidden` alone did not guarantee here.
 */
export function WeekendChanges({ items, count }: { items: WeekendNewSinceCloseItem[]; count: number }) {
  if (items.length === 0) return null;

  return (
    <section className="flex min-h-[360px] max-h-[400px] flex-col overflow-hidden [contain:layout] rounded-2xl border border-surface-border/7 bg-surface-card p-5 shadow-[0_1px_2px_rgb(var(--text-primary)/0.04),0_10px_28px_-8px_rgb(var(--text-primary)/0.06)]">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-[13px] font-black text-text-primary">What Changed Since Market Close</h2>
        <span className="text-[10px] font-bold text-text-muted">{count} total</span>
      </div>
      <ul className="flex-1 space-y-2.5 overflow-y-auto">
        {items.map((item, i) => {
          // A neutral direction carries no real signal to show — the
          // redesign correction is explicit: don't render a meaningless
          // dash for it, leave the row clean instead.
          const style = item.direction === "neutral" ? null : sectorDirectionStyle(item.direction);
          const affected = [...item.sectors, ...item.companies].slice(0, 2).join(" · ");
          // A company-specific item (a real company named, no sector
          // framing) shows that company's avatar instead of a generic
          // source-type glyph — same initials convention as Companies to
          // Watch, so a user sees the same visual language for "this row
          // is about a real, specific company" wherever it appears.
          const primaryCompany = item.sectors.length === 0 ? item.companies[0] : undefined;
          const Icon = SOURCE_TYPE_ICON[item.source_type] ?? Newspaper;
          return (
            <li key={`${item.source_type}-${item.source_id}-${i}`} className="flex min-h-[58px] items-start gap-3">
              {primaryCompany ? (
                <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center whitespace-nowrap rounded-full border border-surface-border/10 bg-surface-bg text-[9px] font-bold text-text-secondary">
                  {primaryCompany.slice(0, 4)}
                </div>
              ) : (
                <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-surface-border/10">
                  <Icon className="h-3.5 w-3.5 text-text-muted" aria-hidden="true" />
                </div>
              )}
              <div className="min-w-0 flex-1">
                <p className="text-[13px] font-semibold leading-snug text-text-primary line-clamp-2">{item.title}</p>
                <p className="mt-0.5 text-[11px] text-text-muted">
                  {SOURCE_TYPE_LABEL[item.source_type] ?? item.source_type}
                  {affected && ` · ${affected}`}
                </p>
              </div>
              {style && (
                <span className={`shrink-0 text-[11px] font-black ${style.textClass}`}>
                  <span aria-hidden="true">{style.symbol}</span>
                  <span className="sr-only"> {style.label}</span>
                </span>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
