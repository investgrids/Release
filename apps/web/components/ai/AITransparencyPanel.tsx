"use client";

import { useState } from "react";
import Link from "next/link";
import { Bot, ChevronDown, ChevronUp, ExternalLink, RefreshCw } from "lucide-react";
import { ConfidenceBadge, ConfidenceMeter } from "./ConfidenceBadge";
import { EvidenceCard, type EvidenceCardProps } from "./EvidenceCard";
import { AIDisclaimer } from "./AIDisclaimer";
import { MethodologyDrawer } from "./MethodologyDrawer";
import { WhyAmISeeingThis } from "./WhyAmISeeingThis";
import type { EvidenceType } from "./EvidenceCard";

export interface RelationshipStep {
  from: string;
  to: string;
  reason: string;
  confidence: number;
}

export interface AITransparencyProps {
  confidence: number;
  reasoning: string;
  summary?: string;
  events?: { title: string; href?: string }[];
  companies?: { name: string; symbol?: string; href?: string }[];
  stories?: { title: string; href?: string }[];
  evidence?: EvidenceCardProps[];
  relationshipChain?: RelationshipStep[];
  assumptions?: string[];
  limitations?: string[];
  updatedAt?: string;
  title?: string;
  whyReason?: string;
  whyInfluences?: string[];
  whyChain?: string[];
  whyHistorical?: string[];
  whyAlternatives?: string[];
  compact?: boolean;
  className?: string;
}

export function AITransparencyPanel({
  confidence,
  reasoning,
  summary,
  events = [],
  companies = [],
  stories = [],
  evidence = [],
  relationshipChain = [],
  assumptions = [],
  limitations = [],
  updatedAt,
  title = "AI Analysis",
  whyReason,
  whyInfluences = [],
  whyChain = [],
  whyHistorical = [],
  whyAlternatives = [],
  compact = false,
  className = "",
}: AITransparencyProps) {
  const [expanded, setExpanded] = useState(!compact);
  const [methodologyOpen, setMethodologyOpen] = useState(false);

  return (
    <>
      <div
        className={`rounded-[16px] border border-violet-500/20 bg-violet-500/[0.04] ${className}`}
        role="region"
        aria-label="AI Analysis"
      >
        {/* Header */}
        <div className="flex items-center justify-between gap-3 px-4 py-3">
          <div className="flex items-center gap-2.5">
            <div className="flex h-7 w-7 items-center justify-center rounded-xl bg-violet-500/15">
              <Bot className="h-3.5 w-3.5 text-violet-400" aria-hidden="true" />
            </div>
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center rounded-full border border-violet-500/30 bg-violet-500/10 px-2.5 py-0.5 text-[10px] font-bold text-violet-300">
                AI Generated
              </span>
              <ConfidenceBadge score={confidence} size="sm" />
            </div>
          </div>

          <div className="flex items-center gap-2">
            {updatedAt && (
              <div className="hidden sm:flex items-center gap-1 text-[10px] text-slate-600">
                <RefreshCw className="h-2.5 w-2.5" aria-hidden="true" />
                {updatedAt}
              </div>
            )}
            <button
              onClick={() => setMethodologyOpen(true)}
              className="hidden sm:flex items-center gap-1 rounded-full border border-violet-500/20 bg-violet-500/10 px-2.5 py-1 text-[10px] font-medium text-violet-400 hover:bg-violet-500/20 transition"
              aria-label="View AI methodology"
            >
              <ExternalLink className="h-2.5 w-2.5" aria-hidden="true" />
              View Methodology
            </button>
            {compact && (
              <button
                onClick={() => setExpanded(prev => !prev)}
                className="flex h-6 w-6 items-center justify-center rounded-full border border-white/10 bg-white/5 text-slate-400 hover:text-white transition"
                aria-label={expanded ? "Collapse AI analysis" : "Expand AI analysis"}
                aria-expanded={expanded}
              >
                {expanded ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
              </button>
            )}
          </div>
        </div>

        {/* Expanded content */}
        {expanded && (
          <div className="border-t border-white/5 px-4 pb-4 pt-3 space-y-4">
            {/* Summary / Reasoning */}
            <div>
              <p className="text-[10px] font-bold uppercase tracking-[0.12em] text-slate-500 mb-1.5">
                {summary ? "Summary" : "Reasoning"}
              </p>
              <p className="text-[12px] text-slate-300 leading-6">
                {summary ?? reasoning}
              </p>
              {summary && reasoning !== summary && (
                <details className="mt-2">
                  <summary className="cursor-pointer text-[10px] text-violet-400 hover:text-violet-300 transition select-none">
                    Full reasoning →
                  </summary>
                  <p className="mt-2 text-[11px] text-slate-400 leading-5">{reasoning}</p>
                </details>
              )}
            </div>

            {/* Confidence meter */}
            <ConfidenceMeter score={confidence} />

            {/* Evidence cards */}
            {evidence.length > 0 && (
              <div>
                <p className="text-[10px] font-bold uppercase tracking-[0.12em] text-slate-500 mb-2">
                  Supporting Evidence
                </p>
                <div className="grid gap-1.5 sm:grid-cols-2">
                  {evidence.slice(0, 6).map((ev, i) => (
                    <EvidenceCard key={i} {...ev} />
                  ))}
                </div>
              </div>
            )}

            {/* Supporting items row */}
            {(events.length > 0 || companies.length > 0 || stories.length > 0) && (
              <div className="grid gap-3 sm:grid-cols-3">
                {events.length > 0 && (
                  <div>
                    <p className="text-[10px] font-bold uppercase tracking-[0.12em] text-slate-500 mb-1.5">Events</p>
                    <div className="space-y-1">
                      {events.slice(0, 3).map((ev, i) => (
                        <p key={i} className="text-[11px] text-slate-400 line-clamp-1">
                          {ev.href ? (
                            <Link href={ev.href as any} className="hover:text-white transition">
                              {ev.title}
                            </Link>
                          ) : ev.title}
                        </p>
                      ))}
                    </div>
                  </div>
                )}
                {companies.length > 0 && (
                  <div>
                    <p className="text-[10px] font-bold uppercase tracking-[0.12em] text-slate-500 mb-1.5">Companies</p>
                    <div className="space-y-1">
                      {companies.slice(0, 3).map((co, i) => (
                        <p key={i} className="text-[11px] text-slate-400 line-clamp-1">
                          {co.href ? (
                            <Link href={co.href as any} className="hover:text-white transition">
                              {co.symbol ?? co.name}
                            </Link>
                          ) : (co.symbol ?? co.name)}
                        </p>
                      ))}
                    </div>
                  </div>
                )}
                {stories.length > 0 && (
                  <div>
                    <p className="text-[10px] font-bold uppercase tracking-[0.12em] text-slate-500 mb-1.5">Stories</p>
                    <div className="space-y-1">
                      {stories.slice(0, 3).map((st, i) => (
                        <p key={i} className="text-[11px] text-slate-400 line-clamp-1">
                          {st.href ? (
                            <Link href={st.href as any} className="hover:text-white transition">
                              {st.title}
                            </Link>
                          ) : st.title}
                        </p>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Footer row */}
            <div className="flex items-center justify-between gap-3 pt-1">
              <div className="flex items-center gap-3">
                <button
                  onClick={() => setMethodologyOpen(true)}
                  className="sm:hidden flex items-center gap-1 text-[10px] text-violet-400 hover:text-violet-300 transition"
                >
                  <ExternalLink className="h-2.5 w-2.5" />
                  View Methodology
                </button>
                <WhyAmISeeingThis
                  reason={whyReason ?? reasoning}
                  influences={whyInfluences}
                  relationshipChain={whyChain}
                  historicalExamples={whyHistorical}
                  alternativeScenarios={whyAlternatives}
                />
              </div>
            </div>

            {/* Disclaimer */}
            <AIDisclaimer />
          </div>
        )}
      </div>

      <MethodologyDrawer
        open={methodologyOpen}
        onClose={() => setMethodologyOpen(false)}
        title={title}
        reasoning={reasoning}
        confidence={confidence}
        events={events}
        companies={companies}
        relationshipChain={relationshipChain}
        assumptions={assumptions}
        limitations={limitations}
      />
    </>
  );
}
