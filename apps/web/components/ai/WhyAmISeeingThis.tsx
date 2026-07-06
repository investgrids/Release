"use client";

import { useState, useEffect, useRef } from "react";
import { HelpCircle, X, GitBranch, Clock, TrendingUp, AlertTriangle } from "lucide-react";
import Link from "next/link";

interface WhyProps {
  reason: string;
  influences?: string[];
  relationshipChain?: string[];
  historicalExamples?: string[];
  alternativeScenarios?: string[];
  confidenceExplanation?: string;
  className?: string;
}

export function WhyAmISeeingThis({
  reason,
  influences = [],
  relationshipChain = [],
  historicalExamples = [],
  alternativeScenarios = [],
  confidenceExplanation,
  className = "",
}: WhyProps) {
  const [open, setOpen] = useState(false);
  const modalRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", handleKey);
    modalRef.current?.focus();
    return () => document.removeEventListener("keydown", handleKey);
  }, [open]);

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className={`inline-flex items-center gap-1 text-[10px] text-slate-600 hover:text-slate-400 transition ${className}`}
        aria-label="Why am I seeing this insight?"
        aria-expanded={open}
      >
        <HelpCircle className="h-3 w-3" aria-hidden="true" />
        Why am I seeing this?
      </button>

      {open && (
        <>
          <div
            className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm"
            onClick={() => setOpen(false)}
            aria-hidden="true"
          />
          <div
            ref={modalRef}
            role="dialog"
            aria-modal="true"
            aria-label="Why you are seeing this insight"
            tabIndex={-1}
            className="fixed left-1/2 top-1/2 z-50 w-full max-w-[440px] -translate-x-1/2 -translate-y-1/2 rounded-[20px] border border-white/10 bg-[#080c14] p-5 shadow-2xl outline-none"
            style={{ animation: "scaleIn 0.18s cubic-bezier(0.16,1,0.3,1)" }}
          >
            <div className="flex items-start justify-between gap-3 mb-4">
              <div>
                <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-violet-400">Why Am I Seeing This?</p>
                <h3 className="mt-1 text-[14px] font-semibold text-white">About This Insight</h3>
              </div>
              <button
                onClick={() => setOpen(false)}
                className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-white/10 bg-white/5 text-slate-400 hover:text-white transition"
                aria-label="Close"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>

            <div className="space-y-4 max-h-[60vh] overflow-y-auto pr-1">
              <Section>
                <p className="text-[12px] text-slate-300 leading-6">{reason}</p>
              </Section>

              {influences.length > 0 && (
                <Section icon={<TrendingUp className="h-3.5 w-3.5 text-emerald-400" />} title="What Influenced This">
                  <ul className="space-y-1">
                    {influences.map((item, i) => (
                      <li key={i} className="flex items-start gap-2 text-[11px] text-slate-400">
                        <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-emerald-400" />
                        {item}
                      </li>
                    ))}
                  </ul>
                </Section>
              )}

              {relationshipChain.length > 0 && (
                <Section icon={<GitBranch className="h-3.5 w-3.5 text-sky-400" />} title="Relationship Chain">
                  <div className="flex flex-wrap items-center gap-1">
                    {relationshipChain.map((step, i) => (
                      <span key={i} className="flex items-center gap-1">
                        <span className="rounded-full border border-white/10 bg-white/[0.04] px-2 py-0.5 text-[10px] text-slate-300">
                          {step}
                        </span>
                        {i < relationshipChain.length - 1 && (
                          <span className="text-slate-600 text-[10px]">→</span>
                        )}
                      </span>
                    ))}
                  </div>
                </Section>
              )}

              {historicalExamples.length > 0 && (
                <Section icon={<Clock className="h-3.5 w-3.5 text-amber-400" />} title="Historical Examples">
                  <ul className="space-y-1">
                    {historicalExamples.map((ex, i) => (
                      <li key={i} className="flex items-start gap-2 text-[11px] text-slate-400">
                        <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-amber-400" />
                        {ex}
                      </li>
                    ))}
                  </ul>
                </Section>
              )}

              {alternativeScenarios.length > 0 && (
                <Section icon={<AlertTriangle className="h-3.5 w-3.5 text-rose-400" />} title="Alternative Scenarios">
                  <ul className="space-y-1">
                    {alternativeScenarios.map((sc, i) => (
                      <li key={i} className="flex items-start gap-2 text-[11px] text-slate-400">
                        <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-rose-400" />
                        {sc}
                      </li>
                    ))}
                  </ul>
                </Section>
              )}

              {confidenceExplanation && (
                <Section title="Confidence Explanation">
                  <p className="text-[11px] text-slate-400 leading-5">{confidenceExplanation}</p>
                </Section>
              )}
            </div>

            <div className="mt-4 pt-4 border-t border-white/5">
              <Link
                href="/how-marketripple-thinks"
                className="text-[11px] text-violet-400 hover:text-violet-300 transition"
                onClick={() => setOpen(false)}
              >
                Learn how MarketRipple thinks →
              </Link>
            </div>
          </div>

          <style>{`
            @keyframes scaleIn {
              from { opacity: 0; transform: translate(-50%, -48%) scale(0.96); }
              to   { opacity: 1; transform: translate(-50%, -50%) scale(1); }
            }
          `}</style>
        </>
      )}
    </>
  );
}

function Section({
  icon,
  title,
  children,
}: {
  icon?: React.ReactNode;
  title?: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      {title && (
        <div className="flex items-center gap-1.5 mb-1.5">
          {icon}
          <p className="text-[10px] font-bold uppercase tracking-[0.12em] text-slate-500">{title}</p>
        </div>
      )}
      {children}
    </div>
  );
}
