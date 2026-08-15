import { History } from "lucide-react";
import type { WeekendHistoricalAnalogue } from "@/types/weekendIntelligence";

/**
 * "Similar Historical Setups" — brief §18. Only rendered when the
 * backend actually found analogues (historical_analogues.length > 0).
 * When zero, this component renders nothing — no manufactured analogue,
 * no empty card. Brief's optional "no strong historical analogue" quiet
 * line is intentionally not duplicated here since WeekendConfidence's
 * disclosure already surfaces that same fact when it's the reason
 * confidence is lower, avoiding a second place saying the same thing.
 */
export function WeekendHistoricalContext({ analogues }: { analogues: WeekendHistoricalAnalogue[] }) {
  if (analogues.length === 0) return null;

  return (
    <section className="rounded-2xl border border-surface-border/7 bg-surface-card p-5">
      <div className="mb-3 flex items-center gap-2">
        <History className="h-4 w-4 text-text-muted" aria-hidden="true" />
        <h2 className="text-[13px] font-black text-text-primary">Similar Historical Setups</h2>
      </div>
      <ul className="space-y-3">
        {analogues.slice(0, 3).map((a) => (
          <li key={a.id} className="rounded-xl border border-surface-border/10 p-3">
            <div className="flex items-center justify-between gap-2">
              <p className="text-[12px] font-bold text-text-primary">{a.event_title}</p>
              {a.event_date && <span className="shrink-0 text-[10px] text-text-muted">{a.event_date}</span>}
            </div>
            {a.nifty_1d != null && (
              <p className="mt-1 text-[11px] text-text-secondary">
                Next-day Nifty move:{" "}
                <span className={`font-black tabular-nums ${a.nifty_1d >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                  {a.nifty_1d >= 0 ? "+" : ""}{a.nifty_1d.toFixed(1)}%
                </span>
              </p>
            )}
            {a.key_lesson && <p className="mt-1 text-[11px] leading-relaxed text-text-muted">{a.key_lesson}</p>}
          </li>
        ))}
      </ul>
    </section>
  );
}
