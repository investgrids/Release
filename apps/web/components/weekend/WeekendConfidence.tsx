"use client";

import { useState } from "react";
import { ChevronDown } from "lucide-react";
import type { WeekendConfidenceComponents } from "@/types/weekendIntelligence";
import type { EvidenceQuality } from "./weekendLabels";

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

/**
 * evidenceQuality/sourceTypeCount/companyCount/sectorCount (2026-08-22,
 * owner correction): folded in from the two cards this replaced ("Since
 * Close" and "Evidence Quality") — real provenance/methodology detail
 * that's more useful here, next to the confidence explanation it
 * supports, than spent as two of the homepage's four scarce above-the-
 * fold card slots. Every value here already existed elsewhere on the
 * page; nothing new is computed.
 */
export function WeekendConfidence({ components, evidenceQuality, sourceTypeCount, companyCount, sectorCount }: {
  components: WeekendConfidenceComponents | null;
  evidenceQuality?: EvidenceQuality;
  sourceTypeCount?: number;
  companyCount?: number;
  sectorCount?: number;
}) {
  const [open, setOpen] = useState(false);
  if (!components) return null;

  const reasons = reasonsFor(components);

  return (
    <div>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex items-center gap-1 rounded text-[11px] font-semibold text-violet-400 transition duration-200 hover:text-violet-300 active:scale-[0.97] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400/50"
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
          {evidenceQuality && (
            <div className="mt-2.5 border-t border-surface-border/10 pt-2.5">
              <p className="text-[11px] font-bold text-text-secondary">
                Evidence quality: <span className="font-black">{evidenceQuality.label}</span>
              </p>
              <p className="mt-0.5 text-[11px] leading-relaxed text-text-muted">
                {evidenceQuality.description.charAt(0).toUpperCase() + evidenceQuality.description.slice(1)}
                {sourceTypeCount != null && companyCount != null && sectorCount != null &&
                  ` · ${companyCount} compan${companyCount === 1 ? "y" : "ies"} · ${sectorCount} sector${sectorCount === 1 ? "" : "s"}`}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
