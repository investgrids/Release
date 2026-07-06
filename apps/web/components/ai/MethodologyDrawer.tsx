"use client";

import { useEffect, useRef } from "react";
import Link from "next/link";
import { X, ChevronRight, Layers, GitBranch, BarChart2, AlertTriangle, BookOpen } from "lucide-react";
import { ConfidenceBadge } from "./ConfidenceBadge";
import type { RelationshipStep } from "@/components/ai/AITransparencyPanel";

interface MethodologyDrawerProps {
  open: boolean;
  onClose: () => void;
  title: string;
  reasoning: string;
  confidence: number;
  events?: { title: string; href?: string }[];
  companies?: { name: string; symbol?: string; href?: string }[];
  relationshipChain?: RelationshipStep[];
  assumptions?: string[];
  limitations?: string[];
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
}: MethodologyDrawerProps) {
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
        className="fixed right-0 top-0 z-50 flex h-full w-full max-w-[480px] flex-col border-l border-white/10 bg-[#080c14] shadow-2xl outline-none"
        style={{ animation: "slideInRight 0.22s cubic-bezier(0.16,1,0.3,1)" }}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-white/8 px-5 py-4">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-violet-400">AI Methodology</p>
            <h2 className="mt-0.5 text-[14px] font-semibold text-white leading-snug line-clamp-2">{title}</h2>
          </div>
          <button
            onClick={onClose}
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-white/10 bg-white/5 text-slate-400 hover:bg-white/10 hover:text-white transition"
            aria-label="Close methodology drawer"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>

        {/* Scrollable content */}
        <div className="flex-1 overflow-y-auto p-5 space-y-5">

          {/* Confidence */}
          <section aria-label="Confidence score">
            <p className="text-[10px] font-bold uppercase tracking-[0.12em] text-slate-500 mb-2">Confidence</p>
            <div className="rounded-[12px] border border-white/8 bg-white/[0.03] p-3">
              <div className="flex items-center justify-between mb-2">
                <ConfidenceBadge score={confidence} showLabel size="md" />
                <span className="text-[20px] font-black text-white tabular-nums">{confidence}%</span>
              </div>
              <div className="h-2 w-full overflow-hidden rounded-full bg-white/[0.06]">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-sky-500 to-violet-500 transition-all duration-700"
                  style={{ width: `${confidence}%` }}
                />
              </div>
              <p className="mt-2 text-[11px] text-slate-400">
                Confidence reflects the strength of evidence supporting this analysis. It accounts for data completeness, historical precedent, and analytical consensus.
              </p>
            </div>
          </section>

          {/* Reasoning */}
          <section aria-label="AI reasoning">
            <div className="flex items-center gap-2 mb-2">
              <Layers className="h-3.5 w-3.5 text-violet-400" aria-hidden="true" />
              <p className="text-[10px] font-bold uppercase tracking-[0.12em] text-slate-500">Why AI Reached This Conclusion</p>
            </div>
            <p className="text-[12px] text-slate-300 leading-6">{reasoning}</p>
          </section>

          {/* Relationship Chain */}
          {relationshipChain.length > 0 && (
            <section aria-label="Relationship chain">
              <div className="flex items-center gap-2 mb-2">
                <GitBranch className="h-3.5 w-3.5 text-sky-400" aria-hidden="true" />
                <p className="text-[10px] font-bold uppercase tracking-[0.12em] text-slate-500">Relationship Chain</p>
              </div>
              <div className="space-y-1.5">
                {relationshipChain.map((step, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <div className="flex flex-col items-center">
                      <div className="flex h-5 w-5 items-center justify-center rounded-full border border-sky-500/30 bg-sky-500/10 text-[9px] font-bold text-sky-400">
                        {i + 1}
                      </div>
                      {i < relationshipChain.length - 1 && (
                        <div className="h-4 w-px bg-white/10" />
                      )}
                    </div>
                    <div className="flex-1 rounded-[10px] border border-white/5 bg-white/[0.02] px-3 py-2">
                      <div className="flex items-center gap-1.5">
                        <span className="text-[11px] font-medium text-white">{step.from}</span>
                        <ChevronRight className="h-3 w-3 text-slate-600" />
                        <span className="text-[11px] font-medium text-sky-300">{step.to}</span>
                        <ConfidenceBadge score={step.confidence} showLabel={false} size="sm" className="ml-auto" />
                      </div>
                      <p className="mt-0.5 text-[10px] text-slate-500">{step.reason}</p>
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
                <p className="text-[10px] font-bold uppercase tracking-[0.12em] text-slate-500">Market Events Considered</p>
              </div>
              <div className="space-y-1">
                {events.map((ev, i) => (
                  <div key={i} className="flex items-center gap-2 rounded-[8px] bg-white/[0.02] px-2.5 py-1.5">
                    <div className="h-1 w-1 rounded-full bg-amber-400 shrink-0" />
                    {ev.href ? (
                      <Link href={ev.href as any} className="text-[11px] text-slate-300 hover:text-white transition line-clamp-1">
                        {ev.title}
                      </Link>
                    ) : (
                      <span className="text-[11px] text-slate-300 line-clamp-1">{ev.title}</span>
                    )}
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* Companies Analyzed */}
          {companies.length > 0 && (
            <section aria-label="Companies analyzed">
              <p className="text-[10px] font-bold uppercase tracking-[0.12em] text-slate-500 mb-2">Companies Analyzed</p>
              <div className="flex flex-wrap gap-1.5">
                {companies.map((co, i) => (
                  <span key={i} className="rounded-full border border-white/10 bg-white/[0.03] px-2.5 py-0.5 text-[11px] text-slate-300">
                    {co.symbol ? `${co.name} (${co.symbol})` : co.name}
                  </span>
                ))}
              </div>
            </section>
          )}

          {/* Assumptions */}
          {assumptions.length > 0 && (
            <section aria-label="Assumptions">
              <p className="text-[10px] font-bold uppercase tracking-[0.12em] text-slate-500 mb-2">Assumptions</p>
              <ul className="space-y-1.5">
                {assumptions.map((a, i) => (
                  <li key={i} className="flex items-start gap-2 text-[11px] text-slate-400">
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
                <p className="text-[10px] font-bold uppercase tracking-[0.12em] text-slate-500">Known Limitations</p>
              </div>
              <ul className="space-y-1.5">
                {limitations.map((lim, i) => (
                  <li key={i} className="flex items-start gap-2 text-[11px] text-amber-300/70">
                    <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-amber-400/50" />
                    {lim}
                  </li>
                ))}
              </ul>
            </section>
          )}

          {/* Learn more links */}
          <section aria-label="Learn more" className="rounded-[14px] border border-white/8 bg-white/[0.02] p-4 space-y-2">
            <div className="flex items-center gap-2 mb-3">
              <BookOpen className="h-3.5 w-3.5 text-violet-400" aria-hidden="true" />
              <p className="text-[11px] font-semibold text-white">Learn More</p>
            </div>
            {[
              { label: "How MarketRipple Thinks", href: "/how-marketripple-thinks" },
              { label: "AI & Methodology", href: "/ai-methodology" },
              { label: "Data Sources", href: "/data-sources" },
            ].map(link => (
              <Link
                key={link.href}
                href={link.href}
                className="flex items-center justify-between rounded-[10px] bg-white/[0.03] px-3 py-2 text-[11px] text-slate-300 hover:bg-white/[0.06] hover:text-white transition"
              >
                {link.label}
                <ChevronRight className="h-3.5 w-3.5 text-slate-500" />
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
