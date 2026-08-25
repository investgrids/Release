"use client";

import { useEffect, useState, useRef } from "react";
import Link from "next/link";
import { API_BASE_URL as API } from "@/lib/api";
import {
  Zap, Building2, Target, Activity,
  TrendingUp, ArrowRight, Sparkles,
} from "lucide-react";

export type RelatedEntityType =
  | "event" | "company" | "story" | "opportunity" | "ripple" | "search" | "comparison";

export interface RelatedItem {
  id:       string;
  title:    string;
  subtitle?: string;
  href:     string;
  badge?:   string;
  score?:   number;
}

interface RelatedGroup {
  type:  string;
  icon:  React.ReactNode;
  label: string;
  items: RelatedItem[];
  color: string;
}

interface RelatedContentProps {
  entityType: RelatedEntityType;
  entityId:   string;
  title?:     string;
  sector?:    string;
  className?: string;
  // Server-fetched /api/related/{type}/{id} response (SEO Phase 2, §2.4) —
  // when provided, seeds initial render with real data instead of the
  // empty-then-fetch pattern, so this block's links exist in the server
  // HTML crawlers see, not just after a client round-trip.
  initialData?: Record<string, RelatedItem[]> | null;
}


// "stories" removed (2026-07-28) — the Story model is confirmed dead (see
// the SEO/Growth audit's Critical Finding #3); /api/related never returns
// this key anymore, kept only as dead weight before this cleanup.
const TYPE_META: Record<string, { icon: React.ReactNode; label: string; color: string }> = {
  events:       { icon: <Zap className="h-3.5 w-3.5" />,       label: "Related Events",       color: "violet" },
  companies:    { icon: <Building2 className="h-3.5 w-3.5" />, label: "Related Companies",    color: "sky"    },
  opportunities:{ icon: <Target className="h-3.5 w-3.5" />,    label: "Opportunities",        color: "emerald"},
  ripple:       { icon: <Activity className="h-3.5 w-3.5" />,  label: "Ripple Analyses",      color: "rose"   },
};

const COLOR_CLASSES: Record<string, string> = {
  violet:  "border-violet-500/20 text-violet-400",
  sky:     "border-sky-500/20 text-sky-400",
  amber:   "border-amber-500/20 text-amber-400",
  emerald: "border-emerald-500/20 text-emerald-400",
  rose:    "border-rose-500/20 text-rose-400",
};

function Skeleton() {
  return (
    <div className="animate-pulse space-y-2">
      {Array.from({ length: 3 }).map((_, i) => (
        <div key={i} className="h-12 rounded-lg bg-text-primary/[0.04]" />
      ))}
    </div>
  );
}

function buildGroups(data: Record<string, RelatedItem[]>): RelatedGroup[] {
  const built: RelatedGroup[] = [];
  for (const [key, items] of Object.entries(data)) {
    if (!Array.isArray(items) || items.length === 0) continue;
    const meta = TYPE_META[key] ?? TYPE_META.events;
    built.push({ type: key, ...meta, items: items.slice(0, 5) });
  }
  return built;
}

export function RelatedContent({
  entityType, entityId, title, sector, className = "", initialData,
}: RelatedContentProps) {
  const [groups,  setGroups]  = useState<RelatedGroup[]>(initialData ? buildGroups(initialData) : []);
  const [loading, setLoading] = useState(!initialData);
  // Guards the very first effect run only — see CompanyPageClient.tsx's
  // identical pattern for the full reasoning.
  const skippedFirstResetRef = useRef(!!initialData);

  // Real, systemic bug found+fixed 2026-08-25 (3IINFOLTD/IIFL wrong-
  // entity-intelligence audit) — see components/intelligence/
  // InvestmentThesis.tsx's identical fix for the full explanation of
  // `cancelled`.
  useEffect(() => {
    if (!entityId) return;
    if (skippedFirstResetRef.current) {
      skippedFirstResetRef.current = false;
      return;
    }
    let cancelled = false;
    const params = new URLSearchParams();
    if (title)  params.set("title",  title);
    if (sector) params.set("sector", sector);
    fetch(`${API}/api/related/${entityType}/${encodeURIComponent(entityId)}?${params}`)
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (!data || cancelled) return;
        setGroups(buildGroups(data as Record<string, RelatedItem[]>));
      })
      .catch(() => {/* ignore */})
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [entityType, entityId, title, sector]);

  if (!loading && groups.length === 0) return null;

  return (
    <section className={`rounded-xl border border-surface-border/6 bg-text-primary/[0.02] p-4 ${className}`}>
      <div className="mb-3 flex items-center gap-2">
        <Sparkles className="h-4 w-4 text-violet-400" />
        <h3 className="text-sm font-semibold text-text-primary">Related Intelligence</h3>
      </div>

      {loading ? (
        <Skeleton />
      ) : (
        <div className="space-y-4">
          {groups.map(group => (
            <div key={group.type}>
              <div className={`mb-2 flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider ${COLOR_CLASSES[group.color] ?? "text-text-secondary"}`}>
                {group.icon}
                {group.label}
              </div>
              <ul className="space-y-1">
                {group.items.map(item => (
                  <li key={item.id}>
                    <Link
                      href={item.href as any}
                      className="group flex items-center gap-2 rounded-lg px-3 py-2 text-xs transition hover:bg-text-primary/[0.05]"
                    >
                      <span className="flex-1 text-text-secondary group-hover:text-text-primary line-clamp-2 leading-snug">
                        {item.title}
                      </span>
                      {item.score !== undefined && (
                        <span className="shrink-0 text-[10px] font-medium text-text-muted">
                          {item.score}%
                        </span>
                      )}
                      <ArrowRight className="h-3 w-3 shrink-0 text-text-muted group-hover:text-text-secondary" />
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
