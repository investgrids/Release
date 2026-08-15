"use client";

import { useState } from "react";
import { ChevronDown } from "lucide-react";
import type { WeekendConfidenceComponents } from "@/types/weekendIntelligence";

/**
 * Confidence disclosure — brief §10: show the percentage plainly (already
 * rendered in WeekendHero), and offer a small, keyboard-accessible
 * affordance that reveals WHY, in plain English, never the raw five
 * unexplained percentages or the weighting formula itself. No arbitrary
 * Low/Moderate/High label is invented — this app has no established
 * confidence-tier convention to reuse (checked), so only the number and
 * its plain-English explanation are shown.
 */
function reasonsFor(components: WeekendConfidenceComponents): string[] {
  const raw = components.raw ?? {};
  const reasons: string[] = [];
  if ((raw.baseline_quality ?? 1) < 0.5) reasons.push("Last trading session's closing baseline is unavailable");
  if ((raw.source_diversity ?? 1) < 0.5) reasons.push("Evidence is concentrated in fewer source types");
  if ((raw.agreement ?? 1) < 0.5) reasons.push("Signals conflict across sectors and companies this weekend");
  if ((raw.evidence_strength ?? 1) < 0.4) reasons.push("Evidence volume is still building");
  if ((raw.historical_support ?? 1) < 0.3) reasons.push("No strong historical analogue was found");
  return reasons;
}

export function WeekendConfidence({ components }: { components: WeekendConfidenceComponents | null }) {
  const [open, setOpen] = useState(false);
  if (!components) return null;

  const reasons = reasonsFor(components);

  return (
    <div>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex items-center gap-1 text-[11px] font-semibold text-violet-400 transition hover:text-violet-300"
      >
        How confident is this?
        <ChevronDown className={`h-3.5 w-3.5 transition-transform ${open ? "rotate-180" : ""}`} aria-hidden="true" />
      </button>
      {open && (
        <div className="mt-2 rounded-lg border border-surface-border/15 bg-surface-border/5 p-3">
          {reasons.length > 0 ? (
            <>
              <p className="text-[11px] font-bold text-text-secondary">Confidence is lower because:</p>
              <ul className="mt-1.5 space-y-1">
                {reasons.map((r) => (
                  <li key={r} className="flex gap-1.5 text-[11px] leading-relaxed text-text-muted">
                    <span aria-hidden="true">·</span> {r}
                  </li>
                ))}
              </ul>
            </>
          ) : (
            <p className="text-[11px] leading-relaxed text-text-muted">
              This outlook is supported by strong, diverse, and internally consistent evidence.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
