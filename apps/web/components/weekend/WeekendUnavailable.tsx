import Link from "next/link";
import { Calendar, Building2, Sparkles, Clock3 } from "lucide-react";

type Kind = "no_snapshot" | "insufficient_evidence" | "error";

const COPY: Record<Kind, { title: string; body: string }> = {
  no_snapshot: {
    title: "Preparing the next market session",
    body: "We're still collecting enough verified information to build the next-session outlook.",
  },
  insufficient_evidence: {
    title: "No material change detected",
    body: "Current weekend evidence is not strong enough to support a directional outlook yet.",
  },
  error: {
    title: "Weekend Intelligence is temporarily unavailable",
    body: "You can still explore Events, Companies, and AI Search while this comes back.",
  },
};

// Real schedule, not a guess — mirrors scheduler.py's own
// weekend_intelligence_checkpoint_morning/_evening cron (Sat/Sun 09:00 &
// 18:00 IST, see register_jobs). Computed server-side from real IST time
// so a visitor in any timezone sees the right next-check time, not their
// browser's local clock.
function nextCheckpointLabel(): string {
  const ist = new Date(Date.now() + 5.5 * 3600_000);
  const h = ist.getUTCHours();
  const isBeforeMorning = h < 9;
  const isBeforeEvening = h < 18;
  if (isBeforeMorning) return "around 9:00 AM IST";
  if (isBeforeEvening) return "around 6:00 PM IST";
  return "tomorrow around 9:00 AM IST";
}

/**
 * The honest, calm state for every non-"ok" case that isn't "degraded"
 * (degraded still renders the full page — see WeekendHomePage). Brief
 * §6.A/§6.B and §28 are explicit: never show fake empty cards, never
 * force a Positive/Negative/Bullish/Bearish label when the evidence
 * doesn't support one, and never present a raw error as the primary
 * experience.
 */
export function WeekendUnavailable({ kind }: { kind: Kind }) {
  const copy = COPY[kind];
  // Only the two states that are genuinely "wait for the next scheduled
  // checkpoint" — an "error" isn't on a schedule, so telling someone to
  // "check back at 6 PM" would be a false promise if the real cause is a
  // job actually failing.
  const nextCheck = kind !== "error" ? nextCheckpointLabel() : null;
  return (
    <div className="mx-auto flex max-w-lg flex-col items-center gap-4 rounded-2xl border border-surface-border/7 bg-surface-card px-6 py-14 text-center shadow-[0_1px_2px_rgb(var(--text-primary)/0.04),0_10px_28px_-8px_rgb(var(--text-primary)/0.06)]">
      <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-violet-500/10">
        <Clock3 className="h-6 w-6 text-violet-400" aria-hidden="true" />
      </div>
      <div>
        <p className="text-[11px] font-black uppercase tracking-wider text-violet-400">Weekend Intelligence</p>
        <h1 className="mt-1 text-[20px] font-black text-text-primary">{copy.title}</h1>
      </div>
      <p className="max-w-sm text-[13px] leading-relaxed text-text-secondary">{copy.body}</p>
      {nextCheck && (
        <p className="flex items-center gap-1.5 rounded-full border border-violet-500/15 bg-violet-500/[0.06] px-3 py-1.5 text-[12px] font-semibold text-violet-500 dark:text-violet-300">
          <Clock3 className="h-3.5 w-3.5" aria-hidden="true" />
          Check back {nextCheck}
        </p>
      )}

      {kind === "error" && (
        <div className="mt-2 flex flex-wrap items-center justify-center gap-2">
          <Link href="/events" className="flex items-center gap-1.5 rounded-lg border border-surface-border/20 bg-surface-border/5 px-3 py-1.5 text-[12px] font-semibold text-text-primary transition hover:border-violet-400/40">
            <Calendar className="h-3.5 w-3.5" aria-hidden="true" /> Events
          </Link>
          <Link href="/companies" className="flex items-center gap-1.5 rounded-lg border border-surface-border/20 bg-surface-border/5 px-3 py-1.5 text-[12px] font-semibold text-text-primary transition hover:border-violet-400/40">
            <Building2 className="h-3.5 w-3.5" aria-hidden="true" /> Companies
          </Link>
          <Link href="/ai-search" className="flex items-center gap-1.5 rounded-lg border border-surface-border/20 bg-surface-border/5 px-3 py-1.5 text-[12px] font-semibold text-text-primary transition hover:border-violet-400/40">
            <Sparkles className="h-3.5 w-3.5" aria-hidden="true" /> AI Search
          </Link>
        </div>
      )}
    </div>
  );
}
