"use client";

// AIAnswerShell — the shared shell every AI Answer ui_mode renders inside
// (2026-09-21 AI Answer UI work, built directly against the two reference
// mockups: Switch Comparison and Policy Impact). Owns exactly the elements
// common to every intent layout — header, main-card chrome, Key Evidence
// table, Evidence Confidence, Source Integrity, the Ripple/Related/
// Methodology nav row, the footer disclaimer, and the universal degraded
// state — never intent-specific content, which is passed in as `children`
// (the main card body) and `sidebarSnapshot` (the top sidebar card).
//
// Built against fields the V3 response ALREADY populates today
// (confidence_breakdown, related_events/news/policies, validation,
// ui_mode/intent) — not against answer_experience_v2, which stays
// unpopulated while AEV2_BUILD_COMPLETE is False. This lets the new
// intent-aware UI be built and tested end-to-end now, against real live
// data, without waiting on AEV2's own readiness gate. Once AEV2 is live,
// the Evidence Confidence card's score is meant to be replaced by
// answer_experience_v2.confidence directly (see that card's own comment)
// rather than the local re-derivation this file currently does.
import { useState } from "react";
import Link from "next/link";
import {
  AlertTriangle, ChevronRight, Plus, SlidersHorizontal, MoreHorizontal,
  ShieldCheck, GitBranch, Sparkles, ExternalLink,
} from "lucide-react";
import { AIDisclaimer } from "./AIDisclaimer";
import type { UIMode, ConfidenceContract } from "@/app/ai-search/AISearchClient";

// The shell's own chrome needs one extra mode beyond the backend's 8:
// "degraded" covers every way an answer failed to reach a real layout
// (synthesis failure, unrecognized ui_mode, or a valid-but-unbuilt one)
// — see answerTypes.ts's DegradedAnswer. It is never sent by the
// backend; it only exists so the shell's chrome metadata stays a single
// lookup table instead of each degraded caller inventing its own label.
export type ShellMode = UIMode | "degraded";

// ── ui_mode -> shell chrome (kind label + intent badge + icon) ────────────
// The ONE place a ui_mode maps to display copy for the shared chrome —
// intent-specific layouts never invent their own version of this text.
export const UI_MODE_META: Record<ShellMode, { kindLabel: string; badgeLabel: string }> = {
  direct_company_research: { kindLabel: "Company research", badgeLabel: "Company research" },
  switch_analysis:          { kindLabel: "Evidence-based comparison", badgeLabel: "Switch comparison" },
  company_comparison:       { kindLabel: "Evidence-based comparison", badgeLabel: "Company comparison" },
  factual_lookup:           { kindLabel: "Factual answer", badgeLabel: "Factual lookup" },
  policy_macro_impact:      { kindLabel: "Policy transmission analysis", badgeLabel: "Policy & macro" },
  market_pulse:             { kindLabel: "Market pulse", badgeLabel: "Market pulse" },
  event_impact:             { kindLabel: "Event impact analysis", badgeLabel: "Event impact" },
  sector_theme_research:    { kindLabel: "Sector & theme research", badgeLabel: "Sector / theme" },
  // 2026-09-22, intent-coverage audit — explicit recognized-but-
  // unsupported modes. These never reach a successful AIAnswerShell
  // render in practice today (toAIAnswer degrades them before that),
  // but ShellMode's own exhaustiveness still requires real chrome copy
  // here, not a placeholder — see DegradedAnswerLayout.tsx for the
  // actual user-facing message each one shows.
  technical_timing:         { kindLabel: "Technical timing", badgeLabel: "Technical timing" },
  company_discovery:        { kindLabel: "Company discovery", badgeLabel: "Company discovery" },
  portfolio_review:         { kindLabel: "Portfolio review", badgeLabel: "Portfolio review" },
  earnings_preview:         { kindLabel: "Earnings preview", badgeLabel: "Earnings preview" },
  multi_company_comparison: { kindLabel: "Multi-company comparison", badgeLabel: "Multi-company comparison" },
  degraded:                 { kindLabel: "Analysis unavailable", badgeLabel: "Degraded" },
};

const BREADCRUMB_LABEL: Record<ShellMode, string> = {
  direct_company_research: "Company Research",
  switch_analysis: "Switch Comparison",
  company_comparison: "Comparison",
  factual_lookup: "Factual Lookup",
  policy_macro_impact: "Policy Impact",
  market_pulse: "Market Pulse",
  event_impact: "Event Impact",
  sector_theme_research: "Sector Research",
  technical_timing: "Technical Timing",
  company_discovery: "Company Discovery",
  portfolio_review: "Portfolio Review",
  earnings_preview: "Earnings Preview",
  multi_company_comparison: "Multi-Company Comparison",
  degraded: "Analysis Unavailable",
};

export interface EvidenceRow {
  id: string;
  date: string | null;
  source: string;
  headline: string;
  href?: string;
  // Which displayed claim(s) this row backs, e.g. ["Summary", "What
  // happened"] — optional so existing callers that don't have a
  // per-claim citation map (news/events/policies built without
  // AEV2-style evidence_refs) render exactly as before.
  citedBy?: string[];
}

export interface EvidenceCoverageSummary {
  newsSourceCount: number;
  eventSourceCount: number;
  policySourceCount: number;
  // Optional: only AEV2-sourced answers can honestly populate this (see
  // EvidenceCoverageCard's own comment). Undefined/0 for every other
  // caller — never inferred from data that shouldn't be surfaced.
  filingSourceCount?: number;
  // Optional: not every data source this card can be built from carries
  // a conflict signal (e.g. AEV2Response has no contradiction_flagged
  // field at all) — undefined means "unknown," and the card omits the
  // conflict line entirely rather than asserting a fact it doesn't have.
  contradictionFlagged?: boolean;
}

interface AIAnswerShellProps {
  query: string;
  uiMode: ShellMode;
  generatedAt?: string | null;
  evidenceFreshAsOf?: string | null;
  sourceCount: number;
  synthesisIncomplete?: boolean;
  degradedNotice?: string;
  evidenceRows: EvidenceRow[];
  confidence?: ConfidenceContract | null;
  evidenceCoverage?: EvidenceCoverageSummary | null;
  sidebarSnapshot?: React.ReactNode;
  // Per-intent section visibility — the shell must let a layout make a
  // card disappear rather than forcing every intent into the same fixed
  // collection (review, 2026-09-21: factual_lookup has no meaningful
  // confidence score, Ripple position, or methodology to show, and a
  // universally-present-but-empty card is exactly the "generic fallback
  // content" this engagement's own visual-review requirement forbids).
  // Both default to true so every OTHER intent keeps today's full shell
  // without having to opt back in explicitly.
  showConfidence?: boolean;
  showRelatedLinks?: boolean;
  onNewSearch: () => void;
  onRefine?: () => void;
  children: React.ReactNode;
}

// ── Evidence Confidence — pure display over the backend-owned
// ConfidenceContract (postprocess.build_confidence_contract). The
// frontend does NOT compute the score: no weighting, no missing-
// component handling, no rounding, no "unscored" decision — all of that
// is the backend's job (review correction, 2026-09-21: an earlier build
// of this card reimplemented the 0.35/0.25/0.25/0.15 formula in React,
// creating a second scoring path that could silently drift from the
// backend's own copy). This card only formats `contract.score` and
// `contract.components` for display.
const CONFIDENCE_FACTORS: { key: keyof ConfidenceContract["components"]; label: string; hint: string }[] = [
  { key: "evidence_quality", label: "Evidence Quality", hint: "Sources, company & sector confirmation" },
  { key: "market_confirmation", label: "Market Confirmation", hint: "Does live price/market action agree?" },
  { key: "historical_similarity", label: "Historical Match", hint: "How closely past precedents line up" },
  { key: "data_freshness", label: "Data Freshness", hint: "How recent the underlying evidence is" },
];

function barColor(v: number) {
  return v >= 70 ? "from-emerald-500 to-emerald-300" : v >= 40 ? "from-amber-500 to-amber-300" : "from-rose-500 to-rose-300";
}

function EvidenceConfidenceCard({ confidence }: { confidence: ConfidenceContract | null | undefined }) {
  if (!confidence || confidence.status === "unscored" || confidence.score == null) {
    return (
      <div className="rounded-[20px] border border-surface-border/7 bg-text-primary/[0.03] p-5">
        <p className="text-[13px] font-semibold text-text-primary mb-1">Evidence Confidence</p>
        <p className="text-[11px] text-text-muted">Unscored — not enough evidence signal for this answer.</p>
      </div>
    );
  }
  return (
    <div className="rounded-[20px] border border-surface-border/7 bg-text-primary/[0.03] p-5">
      <div className="mb-4 flex items-center justify-between">
        <p className="flex items-center gap-1.5 text-[13px] font-semibold text-text-primary">
          Evidence Confidence
          <span className="text-text-muted" title="An evidence-based composite — sources, market confirmation, historical precedent, and data freshness. Never the model's own self-rating.">ⓘ</span>
        </p>
        <p className="text-[16px] font-black tabular-nums text-text-primary">{Math.round(confidence.score)}%</p>
      </div>
      <div className="space-y-3">
        {CONFIDENCE_FACTORS.map(f => {
          const raw = confidence.components[f.key];
          const v = raw == null ? null : Math.max(0, Math.min(100, Number(raw) || 0));
          return (
            <div key={f.key as string}>
              <div className="mb-1 flex items-baseline justify-between">
                <p className="text-[11px] font-medium text-text-secondary">{f.label}</p>
                <p className="text-[10px] tabular-nums text-text-muted">{v == null ? "—" : `${Math.round(v)}%`}</p>
              </div>
              <div className="h-1.5 overflow-hidden rounded-full bg-text-primary/[0.06]">
                {v != null && <div className={`h-full rounded-full bg-gradient-to-r ${barColor(v)}`} style={{ width: `${v}%` }} />}
              </div>
              <p className="mt-0.5 text-[9.5px] text-text-muted">{f.hint}</p>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Evidence Coverage (renamed from "Source Integrity", review
// correction 2026-09-21: real source COUNTS prove coverage, not
// integrity — a trust/provenance rating implies a deterministic
// source-quality classification this codebase doesn't compute today, so
// claiming "integrity" here would overstate what the data supports).
// Reports only honest counts plus the one real signal already computed
// (validation.py's contradiction_flagged, when the caller has it).
// `filingSourceCount` (2026-09-22, direct_company_research) is the one
// exception to the earlier "no Exchange/company filings bucket" rule —
// that rule was about the plain V3 response's internal-only
// CompanyAnnouncement attribution (commit 7ced017); AEV2's own evidence
// catalog already reformats the same rows into anonymized {id, type,
// title, date} entries as a reviewed, non-internal part of its own
// response shape, so counting them here is a different, already-
// sanctioned use of the data, not a resurfacing of the internal field.
function EvidenceCoverageCard({ summary }: { summary: EvidenceCoverageSummary | null | undefined }) {
  if (!summary) return null;
  const rows: { label: string; count: number }[] = [
    { label: "verified news source", count: summary.newsSourceCount },
    { label: "structured market event", count: summary.eventSourceCount },
    { label: "government / regulatory source", count: summary.policySourceCount },
    { label: "exchange / company filing", count: summary.filingSourceCount ?? 0 },
  ].filter(r => r.count > 0);
  const hasConflictSignal = summary.contradictionFlagged !== undefined;
  if (rows.length === 0 && !hasConflictSignal) return null;
  return (
    <div className="rounded-[20px] border border-surface-border/7 bg-text-primary/[0.03] p-5">
      <p className="mb-3 flex items-center gap-1.5 text-[13px] font-semibold text-text-primary">
        <ShieldCheck size={14} strokeWidth={1.8} className="text-violet-400" />
        Evidence Coverage
      </p>
      <div className="space-y-2.5">
        {rows.map(r => (
          <p key={r.label} className="text-[11.5px] text-text-secondary">
            {r.count} {r.label}{r.count === 1 ? "" : "s"}
          </p>
        ))}
        {hasConflictSignal && (
          <p className="text-[11.5px] text-text-secondary">
            {summary.contradictionFlagged
              ? "Conflicting evidence found across sources"
              : "No material conflicting evidence — views are consistent across sources"}
          </p>
        )}
      </div>
    </div>
  );
}

function RelatedLinksNav() {
  const items = [
    { label: "Ripple impact", icon: <GitBranch size={13} strokeWidth={1.8} /> },
    { label: "Related intelligence", icon: <Sparkles size={13} strokeWidth={1.8} /> },
    { label: "Methodology", icon: <ExternalLink size={13} strokeWidth={1.8} /> },
  ];
  return (
    <div className="rounded-[20px] border border-surface-border/7 bg-text-primary/[0.03] divide-y divide-surface-border/6">
      {items.map(it => (
        <Link
          key={it.label}
          href={it.label === "Methodology" ? "/knowledge/ai-methodology" : "#"}
          className="flex items-center justify-between gap-2 px-4 py-3 text-[12px] font-medium text-text-secondary hover:text-text-primary transition"
        >
          <span className="flex items-center gap-2">{it.icon}{it.label}</span>
          <ChevronRight size={14} className="text-text-muted" />
        </Link>
      ))}
    </div>
  );
}

function KeyEvidenceTable({ rows, kindLabel }: { rows: EvidenceRow[]; kindLabel: string }) {
  const [showAll, setShowAll] = useState(false);
  if (rows.length === 0) return null;
  const visible = showAll ? rows : rows.slice(0, 3);
  return (
    <div className="rounded-[20px] border border-surface-border/7 bg-text-primary/[0.03] p-5">
      <div className="mb-3 flex items-center justify-between">
        <p className="text-[13px] font-semibold text-text-primary">
          {kindLabel === "Policy transmission analysis" ? "Key policy evidence and sources" : "Key evidence and sources"}
        </p>
        {rows.length > 3 && (
          <button onClick={() => setShowAll(s => !s)} className="text-[11px] font-medium text-violet-400 hover:text-violet-600 dark:hover:text-violet-300 transition flex items-center gap-1">
            {showAll ? "Show fewer" : `View all sources (${rows.length})`}
            <ChevronRight size={12} />
          </button>
        )}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-[11.5px]">
          <thead>
            <tr className="text-[9.5px] uppercase tracking-wider text-text-muted">
              <th className="pb-2 pr-3 font-semibold">#</th>
              <th className="pb-2 pr-3 font-semibold">Date</th>
              <th className="pb-2 pr-3 font-semibold">Source</th>
              <th className="pb-2 font-semibold">Headline / Key point</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((row, i) => (
              <tr key={row.id} className="border-t border-surface-border/5">
                <td className="py-2 pr-3 text-text-muted tabular-nums">[{i + 1}]</td>
                <td className="py-2 pr-3 text-text-muted whitespace-nowrap">{row.date ?? "—"}</td>
                <td className="py-2 pr-3 text-text-secondary whitespace-nowrap">{row.source}</td>
                <td className="py-2 text-text-secondary">
                  {row.href ? <span className="hover:text-text-primary transition">{row.headline}</span> : row.headline}
                  {row.citedBy && row.citedBy.length > 0 && (
                    <span className="ml-1.5 text-[9.5px] text-text-muted">
                      Cited by: {row.citedBy.join(", ")}
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── Universal degraded state — the one variant every ui_mode falls back
// to on synthesis_incomplete, so a future ui_mode can never reintroduce
// the "scattered per-section conditional" class of leak this engagement
// already found and fixed twice elsewhere (DegradedSearchAnswer,
// DegradedMarketPulse). Real evidence still shows; nothing else does.
function DegradedAnswerBody({ notice, evidenceRows, kindLabel }: { notice?: string; evidenceRows: EvidenceRow[]; kindLabel: string }) {
  return (
    <>
      <div className="flex items-start gap-3 rounded-[16px] border border-amber-500/25 bg-amber-500/[0.06] px-4 py-3">
        <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5 text-amber-400" />
        <p className="text-[12.5px] leading-5 text-amber-700/90 dark:text-amber-200/90">
          <span className="font-semibold text-amber-600 dark:text-amber-300">Full analysis wasn&apos;t available for this query.</span>{" "}
          {notice || "The real evidence found is shown below, with no generated conclusion, confidence score, or outlook."}
        </p>
      </div>
      <KeyEvidenceTable rows={evidenceRows} kindLabel={kindLabel} />
    </>
  );
}

export function AIAnswerShell({
  query, uiMode, generatedAt, evidenceFreshAsOf, sourceCount, synthesisIncomplete, degradedNotice,
  evidenceRows, confidence, evidenceCoverage, sidebarSnapshot,
  showConfidence = true, showRelatedLinks = true, onNewSearch, onRefine, children,
}: AIAnswerShellProps) {
  const meta = UI_MODE_META[uiMode];
  const breadcrumb = BREADCRUMB_LABEL[uiMode];

  return (
    <div className="space-y-4 pb-36" data-testid="ai-answer-shell" data-ui-mode={uiMode}>
      <p className="text-[11px] text-text-muted">
        <Link href="/ai-search" className="hover:text-text-secondary transition">AI Search</Link>
        <span className="mx-1.5">/</span>
        <span className="text-text-secondary">{breadcrumb}</span>
      </p>

      {/* Header */}
      <div className="rounded-[20px] border border-surface-border/7 bg-text-primary/[0.03] px-5 py-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <h1 className="text-[20px] sm:text-[22px] font-bold text-text-primary leading-snug">{query}</h1>
            <p className="mt-1 text-[11px] text-text-muted">
              {generatedAt && <>Generated on {generatedAt}</>}
              {generatedAt && evidenceFreshAsOf && <span className="mx-1.5">|</span>}
              {evidenceFreshAsOf && <>Evidence fresh as of {evidenceFreshAsOf}</>}
            </p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <button onClick={onNewSearch} className="flex items-center gap-1.5 rounded-[12px] border border-surface-border/10 bg-text-primary/[0.04] px-3 py-1.5 text-[12px] font-medium text-text-secondary hover:bg-text-primary/[0.08] transition">
              <Plus className="h-3.5 w-3.5" /> New Search
            </button>
            {/* Refine stays disabled for every AEV2-shell render
                (2026-09-22, intent-coverage audit) — the legacy Refine
                endpoint (POST /api/ai/search/refine) still returns
                investment_verdict/decision_engine_v2/ai_conclusion
                directly, never a CoreAnswer or AEV2 payload (see
                ai_search_refine.py's own module docstring). Wiring an
                AEV2 answer's onRefine into that endpoint would route an
                AEV2 user into the exact prohibited plain-V3 concepts
                this whole shell exists to keep unreachable. `onRefine`
                is therefore intentionally never wired to this button's
                onClick, regardless of whether a caller passes one —
                AIAnswerShell itself owns this decision so a future
                layout activation can't accidentally re-enable it by
                simply passing a legacy handler through. Legacy Refine
                (RefineAnalysisPanel.tsx, the pre-AEV2-shell UI) is
                completely unaffected — that component tree never
                renders through AIAnswerShell at all. Once Refine
                becomes a real contextual request through the canonical
                pipeline (not a sibling answer engine), this button
                should read a real `onRefine` again. */}
            <button
              type="button"
              disabled
              aria-disabled="true"
              title="Refinement is being upgraded for this answer format."
              className="flex items-center gap-1.5 rounded-[12px] border border-surface-border/10 bg-text-primary/[0.04] px-3 py-1.5 text-[12px] font-medium text-text-muted opacity-50 cursor-not-allowed"
            >
              <SlidersHorizontal className="h-3.5 w-3.5" /> Refine
            </button>
            <button className="flex h-8 w-8 items-center justify-center rounded-[10px] border border-surface-border/10 bg-text-primary/[0.04] text-text-secondary hover:bg-text-primary/[0.08] transition">
              <MoreHorizontal className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[1fr_320px] gap-4 items-start">
        {/* Main column */}
        <div className="space-y-4 min-w-0">
          <div className="rounded-[20px] border border-surface-border/7 bg-text-primary/[0.03] p-5">
            <div className="flex flex-wrap items-center gap-2 mb-4">
              <Sparkles size={15} strokeWidth={1.8} className="text-violet-400" />
              <p className="text-[14px] font-bold text-text-primary">{meta.kindLabel}</p>
              <span className="rounded-full bg-violet-500/20 border border-violet-500/30 px-2.5 py-0.5 text-[10px] font-bold text-violet-600 dark:text-violet-300 uppercase tracking-wider">
                {meta.badgeLabel}
              </span>
              {sourceCount > 0 && (
                <span className="rounded-full border border-surface-border/8 bg-text-primary/[0.03] px-2.5 py-0.5 text-[10px] font-medium text-text-secondary">
                  {sourceCount} verified source{sourceCount === 1 ? "" : "s"}
                </span>
              )}
              <span className="rounded-full border border-amber-500/20 bg-amber-500/[0.05] px-2.5 py-0.5 text-[10px] font-medium text-amber-600 dark:text-amber-400">
                Not investment advice
              </span>
            </div>

            {synthesisIncomplete ? (
              <DegradedAnswerBody notice={degradedNotice} evidenceRows={evidenceRows} kindLabel={meta.kindLabel} />
            ) : (
              children
            )}
          </div>

          {!synthesisIncomplete && <KeyEvidenceTable rows={evidenceRows} kindLabel={meta.kindLabel} />}

          <AIDisclaimer />
        </div>

        {/* Sidebar */}
        <div className="space-y-4 min-w-0">
          {sidebarSnapshot}
          {showConfidence && <EvidenceConfidenceCard confidence={confidence} />}
          <EvidenceCoverageCard summary={evidenceCoverage} />
          {showRelatedLinks && <RelatedLinksNav />}
        </div>
      </div>
    </div>
  );
}
