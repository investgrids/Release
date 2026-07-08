"use client";

import Link from "next/link";
import {
  Bot, Activity, Target, BookOpen, Building2,
  Search, Zap, ArrowRight,
} from "lucide-react";

export type SmartCTAVariant =
  | "ask-ai"
  | "view-ripple"
  | "explore-opportunity"
  | "read-story"
  | "see-companies"
  | "search-topic"
  | "view-event";

interface SmartCTAProps {
  variant:    SmartCTAVariant;
  href:       string;
  /** Dynamic label suffix — e.g. company name, topic */
  context?:   string;
  className?: string;
  size?:      "sm" | "md";
}

const VARIANT_DEFS: Record<SmartCTAVariant, {
  icon: React.ReactNode;
  defaultLabel: string;
  color: string;
}> = {
  "ask-ai": {
    icon:         <Bot className="h-3.5 w-3.5" />,
    defaultLabel: "Ask AI About This",
    color:        "border-violet-500/30 bg-violet-500/10 text-violet-300 hover:bg-violet-500/20 hover:border-violet-500/50",
  },
  "view-ripple": {
    icon:         <Activity className="h-3.5 w-3.5" />,
    defaultLabel: "View Ripple Intelligence",
    color:        "border-rose-500/30 bg-rose-500/10 text-rose-300 hover:bg-rose-500/20 hover:border-rose-500/50",
  },
  "explore-opportunity": {
    icon:         <Target className="h-3.5 w-3.5" />,
    defaultLabel: "Explore Opportunity",
    color:        "border-emerald-500/30 bg-emerald-500/10 text-emerald-300 hover:bg-emerald-500/20 hover:border-emerald-500/50",
  },
  "read-story": {
    icon:         <BookOpen className="h-3.5 w-3.5" />,
    defaultLabel: "Read Similar Story",
    color:        "border-amber-500/30 bg-amber-500/10 text-amber-300 hover:bg-amber-500/20 hover:border-amber-500/50",
  },
  "see-companies": {
    icon:         <Building2 className="h-3.5 w-3.5" />,
    defaultLabel: "See Related Companies",
    color:        "border-sky-500/30 bg-sky-500/10 text-sky-300 hover:bg-sky-500/20 hover:border-sky-500/50",
  },
  "search-topic": {
    icon:         <Search className="h-3.5 w-3.5" />,
    defaultLabel: "Search This Topic",
    color:        "border-white/10 bg-white/[0.04] text-slate-300 hover:bg-white/[0.08] hover:border-white/20",
  },
  "view-event": {
    icon:         <Zap className="h-3.5 w-3.5" />,
    defaultLabel: "View Event Details",
    color:        "border-violet-500/30 bg-violet-500/10 text-violet-300 hover:bg-violet-500/20 hover:border-violet-500/50",
  },
};

export function SmartCTA({ variant, href, context, className = "", size = "sm" }: SmartCTAProps) {
  const def = VARIANT_DEFS[variant];
  const label = context ? `${def.defaultLabel}${context ? `: ${context}` : ""}` : def.defaultLabel;
  const sizeClass = size === "md" ? "px-4 py-2 text-sm" : "px-3 py-1.5 text-xs";

  return (
    <Link
      href={href as any}
      className={`inline-flex items-center gap-1.5 rounded-lg border font-medium transition ${sizeClass} ${def.color} ${className}`}
    >
      {def.icon}
      {label}
      <ArrowRight className="h-3 w-3 opacity-60" />
    </Link>
  );
}

/** Render a contextual row of smart CTAs for any entity detail page */
export function SmartCTABar({
  entityType,
  entityId,
  entityTitle,
  rippleId,
  relatedStorySlug,
  relatedOpportunityId,
  className = "",
}: {
  entityType:           string;
  entityId:             string;
  entityTitle:          string;
  rippleId?:            string;
  relatedStorySlug?:    string;
  relatedOpportunityId?: string;
  className?:           string;
}) {
  const searchQuery = encodeURIComponent(entityTitle.slice(0, 100));

  return (
    <div className={`flex flex-wrap gap-2 ${className}`}>
      <SmartCTA
        variant="ask-ai"
        href={`/ai-search?q=${searchQuery}`}
      />
      {rippleId && (
        <SmartCTA
          variant="view-ripple"
          href={`/ripple/${rippleId}`}
        />
      )}
      {relatedOpportunityId && (
        <SmartCTA
          variant="explore-opportunity"
          href={`/radar/${relatedOpportunityId}`}
        />
      )}
      {relatedStorySlug && (
        <SmartCTA
          variant="read-story"
          href={`/stories/${relatedStorySlug}`}
        />
      )}
      {entityType !== "company" && (
        <SmartCTA
          variant="see-companies"
          href={`/companies`}
        />
      )}
    </div>
  );
}
