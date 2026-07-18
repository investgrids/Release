"use client";

import { useEffect, useState } from "react";
import { fixMojibake } from "@/lib/text";
import { API_BASE_URL as API } from "@/lib/api";
import {
  Target, TrendingUp, ShieldAlert, CheckCircle2,
  BookOpen, Zap, Clock, Loader2,
} from "lucide-react";

// ── Types ─────────────────────────────────────────────────────────────────────

export type ThesisEntityType =
  | "event" | "company" | "story" | "opportunity" | "ripple" | "search";

interface FetchedThesis {
  executive_summary?: string;
  why_it_matters?: string;
  business_impact?: string;
  revenue_growth_impact?: string;
  supporting_evidence?: string[];
  competitive_advantages?: string[];
  key_drivers?: string[];
  key_risks?: string[];
  thesis_strength?: number;
  time_horizon?: string;
  last_updated?: string;
}

export interface InvestmentThesisCardProps {
  // ── Static content (renders immediately) ──────────────────────────────────
  /** Executive summary — the core investment thesis statement */
  thesis?: string;
  /** Why this matters to investors */
  whyItMatters?: string;
  /** Business or market impact description */
  businessImpact?: string;
  /** Revenue or growth impact description (spec field) */
  revenueGrowthImpact?: string;
  /** Key growth or opportunity drivers */
  keyDrivers?: string[];
  /** Supporting evidence items */
  supportingEvidence?: string[];
  /** Competitive advantages or structural moats */
  competitiveAdvantages?: string[];
  /** Key assumptions underpinning the thesis (collapsible) */
  assumptions?: string[];
  /** Risk factors that could invalidate the thesis (collapsible) */
  riskFactors?: string[];
  /** 0–100 thesis strength / AI confidence. null/undefined means unscored. */
  confidence?: number | null;
  /** Investment time horizon e.g. "Medium-term (6–18 months)" */
  timeHorizon?: string;
  /** ISO date string or human-readable label */
  lastUpdated?: string;

  // ── Self-fetch: provide these to enrich the card via /api/thesis ──────────
  /** Entity type — enables self-fetching from /api/thesis/{type}/{id} */
  entityType?: ThesisEntityType;
  /** Entity ID or symbol */
  entityId?: string;
  /** Title passed as context to the AI (optional but improves quality) */
  entityTitle?: string;
  /** Description passed as context to the AI */
  entityDescription?: string;
  /** Primary sector passed as context to the AI */
  entitySector?: string;
}

// ── Helpers ───────────────────────────────────────────────────────────────────


function strengthStyle(s: number) {
  if (s >= 75) return "text-emerald-400 border-emerald-500/30 bg-emerald-500/10";
  if (s >= 50) return "text-sky-400    border-sky-500/30    bg-sky-500/10";
  if (s >= 30) return "text-amber-400  border-amber-500/30  bg-amber-500/10";
  return                "text-rose-400   border-rose-500/30   bg-rose-500/10";
}

function strengthLabel(s: number) {
  if (s >= 80) return "Strong";
  if (s >= 60) return "Moderate";
  if (s >= 40) return "Developing";
  return "Speculative";
}

// strengthStyle/strengthLabel intentionally take a real number only —
// callers gate on `effectiveStrength !== null` before invoking them,
// so there is no "unscored" branch to fabricate here.

function SectionLabel({ children, color = "text-slate-500" }: { children: React.ReactNode; color?: string }) {
  return (
    <p className={`mb-1.5 text-[9px] font-bold uppercase tracking-[0.10em] ${color}`}>
      {children}
    </p>
  );
}

function Pill({ text }: { text: string }) {
  return (
    <li className="flex items-start gap-2 text-[12px] text-slate-300 leading-5">
      <CheckCircle2 className="mt-0.5 h-3 w-3 shrink-0 text-emerald-400" aria-hidden />
      {text}
    </li>
  );
}

function EvidencePill({ text }: { text: string }) {
  return (
    <li className="flex items-start gap-2 text-[12px] text-slate-400 leading-5">
      <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-sky-400" aria-hidden />
      {text}
    </li>
  );
}

function RiskPill({ text }: { text: string }) {
  return (
    <li className="flex items-start gap-1.5 text-[12px] text-slate-400 leading-5">
      <span className="mt-1 h-1 w-1 shrink-0 rounded-full bg-rose-400" aria-hidden />
      {text}
    </li>
  );
}

function TextSkeleton({ lines = 2 }: { lines?: number }) {
  return (
    <div className="space-y-1.5">
      {Array.from({ length: lines }).map((_, i) => (
        <div
          key={i}
          className="h-3 animate-pulse rounded bg-white/[0.06]"
          style={{ width: i === lines - 1 ? "65%" : "100%" }}
        />
      ))}
    </div>
  );
}

function CollapsibleSection({
  label, count, icon, children,
}: {
  label: string; count: number; icon: React.ReactNode; children: React.ReactNode;
}) {
  return (
    <details className="group">
      <summary className="flex cursor-pointer list-none items-center gap-1.5 text-[10px] font-bold uppercase tracking-[0.12em] text-slate-500 transition hover:text-slate-400">
        <span className="inline-block transition-transform group-open:rotate-90" aria-hidden>›</span>
        {icon}
        {label} ({count})
      </summary>
      <ul className="mt-2 space-y-1.5 pl-3" role="list">
        {children}
      </ul>
    </details>
  );
}

// ── Component ─────────────────────────────────────────────────────────────────

export function InvestmentThesisCard({
  thesis,
  whyItMatters,
  businessImpact,
  revenueGrowthImpact,
  keyDrivers        = [],
  supportingEvidence= [],
  competitiveAdvantages = [],
  assumptions       = [],
  riskFactors       = [],
  confidence        = null,
  timeHorizon,
  lastUpdated,
  entityType,
  entityId,
  entityTitle,
  entityDescription,
  entitySector,
}: InvestmentThesisCardProps) {

  const [fetched,  setFetched]  = useState<FetchedThesis | null>(null);
  const [fetching, setFetching] = useState(false);

  // Self-fetch enrichment when entity context is provided
  useEffect(() => {
    if (!entityType || !entityId) return;
    setFetching(true);
    const p = new URLSearchParams();
    if (entityTitle)                              p.set("title",       entityTitle);
    if (entityDescription)                        p.set("description", entityDescription.slice(0, 500));
    if (entitySector)                             p.set("sector",      entitySector);

    fetch(`${API}/api/thesis/${entityType}/${encodeURIComponent(entityId)}?${p}`)
      .then(r => r.ok ? r.json() : null)
      .then(d  => { if (d) setFetched(d as FetchedThesis); })
      .catch(() => {})
      .finally(() => setFetching(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [entityType, entityId]);

  // Merge: explicit props always win; fetched data fills every gap
  const effectiveThesis       = thesis              ?? fetched?.executive_summary;
  const effectiveWhy          = whyItMatters        ?? fetched?.why_it_matters;
  const effectiveBiz          = businessImpact      ?? fetched?.business_impact;
  const effectiveRev          = revenueGrowthImpact ?? fetched?.revenue_growth_impact;
  const effectiveDrivers      = keyDrivers.length   > 0 ? keyDrivers      : (fetched?.key_drivers       ?? []);
  const effectiveEvidence     = supportingEvidence.length > 0 ? supportingEvidence : (fetched?.supporting_evidence  ?? []);
  const effectiveAdvantages   = competitiveAdvantages.length > 0 ? competitiveAdvantages : (fetched?.competitive_advantages ?? []);
  const effectiveRisks        = riskFactors.length  > 0 ? riskFactors      : (fetched?.key_risks         ?? []);
  const effectiveStrength     = confidence ?? fetched?.thesis_strength ?? null;
  const effectiveHorizon      = timeHorizon         ?? fetched?.time_horizon;
  const effectiveUpdated      = lastUpdated         ?? fetched?.last_updated;

  const hasStatic = !!(effectiveThesis || effectiveWhy || effectiveBiz ||
    effectiveRev || effectiveDrivers.length || effectiveEvidence.length ||
    effectiveAdvantages.length || effectiveRisks.length || assumptions.length);

  const isEnriching = fetching && !fetched;

  // Empty state — nothing to show yet
  if (!hasStatic && !isEnriching) {
    return (
      <div className="rounded-[20px] border border-white/[0.07] bg-white/[0.025] p-5">
        <div className="flex items-center gap-2 mb-3">
          <div className="flex h-7 w-7 items-center justify-center rounded-xl bg-violet-500/[0.04] border border-violet-500/20">
            <Target className="h-3.5 w-3.5 text-violet-400" />
          </div>
          <span className="text-[10px] font-bold uppercase tracking-[0.12em] text-slate-500">
            Investment Thesis
          </span>
        </div>
        <p className="text-[12px] text-slate-400 leading-5">No thesis data available.</p>
      </div>
    );
  }

  return (
    <div className="rounded-[20px] border border-violet-500/20 bg-violet-500/[0.04] p-5 space-y-4">

      {/* ── Header ──────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div
            className="flex h-7 w-7 items-center justify-center rounded-xl bg-violet-500/[0.08] border border-violet-500/20"
            aria-hidden
          >
            <Target className="h-3.5 w-3.5 text-violet-400" />
          </div>
          <span className="text-[10px] font-bold uppercase tracking-[0.12em] text-slate-500">
            Investment Thesis
          </span>
        </div>

        <div className="flex items-center gap-2">
          {isEnriching && (
            <span className="flex items-center gap-1 text-[10px] text-slate-600">
              <Loader2 className="h-3 w-3 animate-spin" aria-hidden />
              Analysing…
            </span>
          )}
          {effectiveStrength !== null && effectiveStrength !== undefined && effectiveStrength > 0 && (
            <span
              className={`rounded-full border px-2.5 py-0.5 text-[10px] font-bold ${strengthStyle(effectiveStrength)}`}
              aria-label={`Thesis strength: ${effectiveStrength}%`}
            >
              {effectiveStrength}% · {strengthLabel(effectiveStrength)}
            </span>
          )}
        </div>
      </div>

      {/* ── Executive Summary ─────────────────────────────────────────── */}
      {effectiveThesis ? (
        <p className="text-[13px] text-slate-200 leading-6">{effectiveThesis}</p>
      ) : isEnriching ? (
        <TextSkeleton lines={3} />
      ) : null}

      {/* ── Time Horizon ──────────────────────────────────────────────── */}
      {effectiveHorizon && (
        <span className="inline-flex items-center gap-1.5 rounded-full border border-violet-500/30 bg-violet-500/10 px-3 py-1 text-[11px] font-medium text-violet-300">
          <Clock className="h-3 w-3" aria-hidden />
          {fixMojibake(effectiveHorizon)}
        </span>
      )}

      {/* ── Why It Matters + Business Impact ─────────────────────────── */}
      {(effectiveWhy || effectiveBiz || isEnriching) && (
        <div className={`grid gap-3 ${effectiveWhy && effectiveBiz ? "sm:grid-cols-2" : ""} grid-cols-1`}>
          {(effectiveWhy || isEnriching) && (
            <div className="rounded-[14px] border border-violet-500/15 bg-violet-500/[0.04] p-3">
              <SectionLabel color="text-violet-400">Why It Matters</SectionLabel>
              {effectiveWhy
                ? <p className="text-[12px] leading-5 text-slate-300">{effectiveWhy}</p>
                : <TextSkeleton />}
            </div>
          )}
          {(effectiveBiz || isEnriching) && (
            <div className="rounded-[14px] border border-sky-500/15 bg-sky-500/[0.04] p-3">
              <SectionLabel color="text-sky-400">Business Impact</SectionLabel>
              {effectiveBiz
                ? <p className="text-[12px] leading-5 text-slate-300">{effectiveBiz}</p>
                : <TextSkeleton />}
            </div>
          )}
        </div>
      )}

      {/* ── Revenue / Growth Impact ───────────────────────────────────── */}
      {(effectiveRev || isEnriching) && (
        <div className="rounded-[14px] border border-emerald-500/15 bg-emerald-500/[0.04] p-3">
          <div className="flex items-center gap-1.5 mb-1">
            <TrendingUp className="h-3 w-3 text-emerald-400" aria-hidden />
            <SectionLabel color="text-emerald-400">Revenue &amp; Growth Impact</SectionLabel>
          </div>
          {effectiveRev
            ? <p className="text-[12px] leading-5 text-slate-300">{effectiveRev}</p>
            : <TextSkeleton />}
        </div>
      )}

      {/* ── Key Drivers ───────────────────────────────────────────────── */}
      {effectiveDrivers.length > 0 && (
        <div>
          <div className="flex items-center gap-1.5 mb-2">
            <Zap className="h-3 w-3 text-amber-400" aria-hidden />
            <SectionLabel color="text-amber-400">Key Drivers</SectionLabel>
          </div>
          <ul className="space-y-1.5" role="list">
            {effectiveDrivers.map((d, i) => <Pill key={i} text={d} />)}
          </ul>
        </div>
      )}

      {/* ── Competitive Advantages (collapsible) ─────────────────────── */}
      {effectiveAdvantages.length > 0 && (
        <CollapsibleSection
          label="Competitive Advantages"
          count={effectiveAdvantages.length}
          icon={<BookOpen className="h-3 w-3" aria-hidden />}
        >
          {effectiveAdvantages.map((a, i) => <Pill key={i} text={a} />)}
        </CollapsibleSection>
      )}

      {/* ── Supporting Evidence (collapsible) ────────────────────────── */}
      {effectiveEvidence.length > 0 && (
        <CollapsibleSection
          label="Supporting Evidence"
          count={effectiveEvidence.length}
          icon={<BookOpen className="h-3 w-3" aria-hidden />}
        >
          {effectiveEvidence.map((e, i) => <EvidencePill key={i} text={e} />)}
        </CollapsibleSection>
      )}

      {/* ── Key Assumptions (collapsible) ─────────────────────────────── */}
      {assumptions.length > 0 && (
        <CollapsibleSection
          label="Key Assumptions"
          count={assumptions.length}
          icon={<BookOpen className="h-3 w-3" aria-hidden />}
        >
          {assumptions.map((a, i) => (
            <li key={i} className="flex items-start gap-1.5 text-[12px] text-slate-400 leading-5">
              <span className="mt-1 h-1 w-1 shrink-0 rounded-full bg-violet-400" aria-hidden />
              {a}
            </li>
          ))}
        </CollapsibleSection>
      )}

      {/* ── Key Risks (collapsible) ───────────────────────────────────── */}
      {effectiveRisks.length > 0 && (
        <CollapsibleSection
          label="Key Risks"
          count={effectiveRisks.length}
          icon={<ShieldAlert className="h-3 w-3 text-rose-400" aria-hidden />}
        >
          {effectiveRisks.map((r, i) => <RiskPill key={i} text={r} />)}
        </CollapsibleSection>
      )}

      {/* ── Last Updated ──────────────────────────────────────────────── */}
      {effectiveUpdated && (
        <p className="border-t border-white/[0.04] pt-2 text-[10px] text-slate-600">
          Analysis updated:{" "}
          {(() => {
            try {
              return new Date(effectiveUpdated).toLocaleString("en-IN", {
                day: "numeric", month: "short", year: "numeric",
                hour: "2-digit", minute: "2-digit",
              });
            } catch {
              return effectiveUpdated;
            }
          })()}
        </p>
      )}
    </div>
  );
}

/** @deprecated Use InvestmentThesisCard instead */
export const InvestmentThesis = InvestmentThesisCard;
