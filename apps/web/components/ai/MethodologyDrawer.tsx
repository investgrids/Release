"use client";

import { useEffect, useRef } from "react";
import Link from "next/link";
import { X, ChevronRight, Layers, GitBranch, BarChart2, AlertTriangle, BookOpen } from "lucide-react";
import { ConfidenceBadge } from "./ConfidenceBadge";
import type { RelationshipStep } from "@/components/ai/AITransparencyPanel";
import { isRealSymbol } from "@/lib/text";

interface MethodologyDrawerProps {
  open: boolean;
  onClose: () => void;
  title: string;
  reasoning: string;
  confidence: number | null;
  events?: { title: string; href?: string }[];
  companies?: { name: string; symbol?: string; href?: string }[];
  relationshipChain?: RelationshipStep[];
  assumptions?: string[];
  limitations?: string[];
  /** CD3-C fix: same raw confidence_service.py breakdown AITransparencyPanel
   * takes -- when it includes a real `ai_certainty` component, the caption
   * below must disclose it rather than describing the score as purely
   * evidence-based (measurement_type=HYBRID_RUBRIC, not EVIDENCE_COMPOSITE,
   * per app/services/measurement_semantics.py). Optional: callers that
   * don't have the breakdown get the honest evidence-only wording instead
   * of a false claim either way. */
  confidenceBreakdown?: Record<string, number>;
}

export function MethodologyDrawer({
  open,
  onClose,
  title,
  reasoning,
  confidence,
  events = [],
  companies = [],
  relationshipChain = [],
  assumptions = [],
  limitations = [],
  confidenceBreakdown,
}: MethodologyDrawerProps) {
  const aiCertainty = confidenceBreakdown?.ai_certainty;
  const confidenceCaption = aiCertainty != null
    ? "Confidence combines real evidence signals (data completeness, historical precedent, market and sector confirmation) with a small self-assessed component from the model itself -- not a purely evidence-based figure."
    : "Confidence reflects the strength of evidence supporting this analysis, based on data completeness, historical precedent, and market confirmation.";
  const drawerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleKey);
    document.body.style.overflow = "hidden";
    drawerRef.current?.focus();
    return () => {
      document.removeEventListener("keydown", handleKey);
      document.body.style.overflow = "";
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Drawer panel */}
      <div
        ref={drawerRef}
        role="dialog"
        aria-modal="true"
        aria-label="AI Methodology"
        tabIndex={-1}
        className="fixed right-0 top-0 z-50 flex h-full w-full max-w-[480px] flex-col border-l border-surface-border/10 bg-surface-card shadow-2xl outline-none"
        style={{ animation: "slideInRight 0.22s cubic-bezier(0.16,1,0.3,1)" }}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-surface-border/8 px-5 py-4">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-violet-400">AI Methodology</p>
            <h2 className="mt-0.5 text-[14px] font-semibold text-text-primary leading-snug line-clamp-2">{title}</h2>
          </div>
          <button
            onClick={onClose}
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-surface-border/10 bg-text-primary/5 text-text-secondary hover:bg-text-primary/10 hover:text-text-primary transition"
            aria-label="Close methodology drawer"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>

        {/* Scrollable content */}
        <div className="flex-1 overflow-y-auto p-5 space-y-5">

          {/* Confidence */}
          <section aria-label="Confidence score">
            <p className="text-[10px] font-bold uppercase tracking-[0.12em] text-text-muted mb-2">Confidence</p>
            <div className="rounded-[12px] border border-surface-border/8 bg-text-primary/[0.03] p-3">
              <div className="flex items-center justify-between mb-2">
                <ConfidenceBadge score={confidence} showLabel size="md" />
                <span className="text-[20px] font-black text-text-primary tabular-nums">{confidence === null || confidence === undefined ? "—" : `${confidence}%`}</span>
              </div>
              <div className="h-2 w-full overflow-hidden rounded-full bg-text-primary/[0.06]">
                {confidence !== null && confidence !== undefined && (
                  <div
                    className="h-full rounded-full bg-gradient-to-r from-sky-500 to-violet-500 transition-all duration-700"
                    style={{ width: `${confidence}%` }}
                  />
                )}
              </div>
              <p className="mt-2 text-[11px] text-text-secondary">
                {confidenceCaption}
              </p>
            </div>
          </section>

          {/* Reasoning */}
          <section aria-label="AI reasoning">
            <div className="flex items-center gap-2 mb-2">
              <Layers className="h-3.5 w-3.5 text-violet-400" aria-hidden="true" />
              <p className="text-[10px] font-bold uppercase tracking-[0.12em] text-text-muted">Why AI Reached This Conclusion</p>
            </div>
            <p className="text-[12px] text-text-secondary leading-6">{reasoning}</p>
          </section>

          {/* Relationship Chain */}
          {relationshipChain.length > 0 && (
            <section aria-label="Relationship chain">
              <div className="flex items-center gap-2 mb-2">
                <GitBranch className="h-3.5 w-3.5 text-sky-400" aria-hidden="true" />
                <p className="text-[10px] font-bold uppercase tracking-[0.12em] text-text-muted">Relationship Chain</p>
              </div>
              <div className="space-y-1.5">
                {relationshipChain.map((step, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <div className="flex flex-col items-center">
                      <div className="flex h-5 w-5 items-center justify-center rounded-full border border-sky-500/30 bg-sky-500/10 text-[9px] font-bold text-sky-400">
                        {i + 1}
                      </div>
                      {i < relationshipChain.length - 1 && (
                        <div className="h-4 w-px bg-text-primary/10" />
                      )}
                    </div>
                    <div className="flex-1 rounded-[10px] border border-surface-border/5 bg-text-primary/[0.02] px-3 py-2">
                      <div className="flex items-center gap-1.5">
                        <span className="text-[11px] font-medium text-text-primary">{step.from}</span>
                        <ChevronRight className="h-3 w-3 text-text-muted" />
                        <span className="text-[11px] font-medium text-sky-600 dark:text-sky-300">{step.to}</span>
                        <ConfidenceBadge score={step.confidence} showLabel={false} size="sm" className="ml-auto" />
                      </div>
                      <p className="mt-0.5 text-[10px] text-text-muted">{step.reason}</p>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* Events Analyzed */}
          {events.length > 0 && (
            <section aria-label="Events analyzed">
              <div className="flex items-center gap-2 mb-2">
                <BarChart2 className="h-3.5 w-3.5 text-amber-400" aria-hidden="true" />
                <p className="text-[10px] font-bold uppercase tracking-[0.12em] text-text-muted">Market Events Considered</p>
              </div>
              <div className="space-y-1">
                {events.map((ev, i) => (
                  <div key={i} className="flex items-center gap-2 rounded-[8px] bg-text-primary/[0.02] px-2.5 py-1.5">
                    <div className="h-1 w-1 rounded-full bg-amber-400 shrink-0" />
                    {ev.href ? (
                      <Link href={ev.href as any} className="text-[11px] text-text-secondary hover:text-text-primary transition line-clamp-1">
                        {ev.title}
                      </Link>
                    ) : (
                      <span className="text-[11px] text-text-secondary line-clamp-1">{ev.title}</span>
                    )}
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* Companies Analyzed */}
          {companies.length > 0 && (
            <section aria-label="Companies analyzed">
              <p className="text-[10px] font-bold uppercase tracking-[0.12em] text-text-muted mb-2">Companies Analyzed</p>
              <div className="flex flex-wrap gap-1.5">
                {companies.map((co, i) => (
                  <span key={i} className="rounded-full border border-surface-border/10 bg-text-primary/[0.03] px-2.5 py-0.5 text-[11px] text-text-secondary">
                    {isRealSymbol(co.symbol) ? `${co.name} (${co.symbol})` : co.name}
                  </span>
                ))}
              </div>
            </section>
          )}

          {/* Assumptions */}
          {assumptions.length > 0 && (
            <section aria-label="Assumptions">
              <p className="text-[10px] font-bold uppercase tracking-[0.12em] text-text-muted mb-2">Assumptions</p>
              <ul className="space-y-1.5">
                {assumptions.map((a, i) => (
                  <li key={i} className="flex items-start gap-2 text-[11px] text-text-secondary">
                    <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-slate-500" />
                    {a}
                  </li>
                ))}
              </ul>
            </section>
          )}

          {/* Limitations */}
          {limitations.length > 0 && (
            <section aria-label="Limitations">
              <div className="flex items-center gap-2 mb-2">
                <AlertTriangle className="h-3.5 w-3.5 text-amber-500/70" aria-hidden="true" />
                <p className="text-[10px] font-bold uppercase tracking-[0.12em] text-text-muted">Known Limitations</p>
              </div>
              <ul className="space-y-1.5">
                {limitations.map((lim, i) => (
                  <li key={i} className="flex items-start gap-2 text-[11px] text-amber-600/70 dark:text-amber-300/70">
                    <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-amber-400/50" />
                    {lim}
                  </li>
                ))}
              </ul>
            </section>
          )}

          {/* Learn more links */}
          <section aria-label="Learn more" className="rounded-[14px] border border-surface-border/8 bg-text-primary/[0.02] p-4 space-y-2">
            <div className="flex items-center gap-2 mb-3">
              <BookOpen className="h-3.5 w-3.5 text-violet-400" aria-hidden="true" />
              <p className="text-[11px] font-semibold text-text-primary">Learn More</p>
            </div>
            {[
              { label: "How MarketRipple Thinks", href: "/how-marketripple-thinks" },
              { label: "AI & Methodology", href: "/ai-methodology" },
            ].map(link => (
              <Link
                key={link.href}
                href={link.href}
                className="flex items-center justify-between rounded-[10px] bg-text-primary/[0.03] px-3 py-2 text-[11px] text-text-secondary hover:bg-text-primary/[0.06] hover:text-text-primary transition"
              >
                {link.label}
                <ChevronRight className="h-3.5 w-3.5 text-text-muted" />
              </Link>
            ))}
          </section>
        </div>
      </div>

      <style>{`
        @keyframes slideInRight {
          from { transform: translateX(100%); opacity: 0; }
          to   { transform: translateX(0);    opacity: 1; }
        }
      `}</style>
    </>
  );
}
