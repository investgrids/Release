"use client";

import {
  GitCompare, ShieldAlert, Layers, TrendingUp, Clock, Briefcase, GitBranch, ChevronRight,
} from "lucide-react";
import { API_BASE_URL as API } from "@/lib/api";

export interface FollowUpItem {
  text: string;
  query: string;
  difficulty: "beginner" | "intermediate" | "advanced";
}
export interface FollowUpGroup {
  key: string;
  label: string;
  icon: string;
  items: FollowUpItem[];
}

const ICONS: Record<string, typeof GitCompare> = {
  compare: GitCompare,
  risk: ShieldAlert,
  deeper: Layers,
  macro: TrendingUp,
  horizon: Clock,
  portfolio: Briefcase,
  ripple: GitBranch,
};

function trackClick(responseId: string | null, group: FollowUpGroup, item: FollowUpItem, position: number) {
  if (!responseId) return;
  // Fire-and-forget — never blocks or delays the actual navigation.
  fetch(`${API}/api/ai/search/followup-click`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ response_id: responseId, category: group.key, item_text: item.text, item_query: item.query, position }),
    keepalive: true,
  }).catch(() => {});
}

/**
 * "Continue Your Research" — grouped, contextual follow-ups built entirely
 * from this answer's own structured evidence (companies, sectors, decision
 * gaps, risks, policies, the ripple graph — see the backend's followups.py
 * module docstring). Never a flat generic list, never the LLM inventing
 * questions from scratch. Renders nothing when there's nothing grounded to
 * suggest, rather than padding with filler.
 */
export function FollowUpIntelligence({
  groups,
  responseId,
  onFollowUp,
}: {
  groups: FollowUpGroup[] | undefined;
  responseId: string | null;
  onFollowUp: (q: string) => void;
}) {
  if (!groups || groups.length === 0) return null;

  return (
    <div className="rounded-[20px] border border-surface-border/7 bg-text-primary/[0.03] p-5">
      <p className="mb-4 text-[13px] font-semibold text-text-primary">Continue Your Research</p>
      <div className="space-y-4">
        {groups.map(group => {
          const Icon = ICONS[group.icon] ?? GitCompare;
          return (
            <div key={group.key}>
              <div className="mb-2 flex items-center gap-1.5">
                <Icon className="h-3.5 w-3.5 text-violet-400" />
                <p className="text-[11px] font-semibold uppercase tracking-wide text-text-secondary">{group.label}</p>
              </div>
              <div className="flex flex-wrap gap-2">
                {group.items.map((item, i) => (
                  <button
                    key={i}
                    onClick={() => {
                      trackClick(responseId, group, item, i);
                      onFollowUp(item.query);
                    }}
                    className="group flex items-center gap-1 rounded-full border border-surface-border/8 bg-text-primary/[0.02] px-3 py-1.5 text-left text-[11.5px] text-text-secondary transition hover:border-violet-500/30 hover:bg-violet-500/[0.08] hover:text-violet-600 dark:text-violet-300"
                  >
                    {item.text}
                    <ChevronRight className="h-3 w-3 shrink-0 text-text-muted transition group-hover:text-violet-400" />
                  </button>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
