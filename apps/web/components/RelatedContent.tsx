"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { API_BASE_URL as API } from "@/lib/api";
import {
  Zap, Building2, BookOpen, Target, Activity,
  TrendingUp, ArrowRight, Sparkles,
} from "lucide-react";

export type RelatedEntityType =
  | "event" | "company" | "story" | "opportunity" | "ripple" | "search";

interface RelatedItem {
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
}


const TYPE_META: Record<string, { icon: React.ReactNode; label: string; color: string }> = {
  events:       { icon: <Zap className="h-3.5 w-3.5" />,       label: "Related Events",       color: "violet" },
  companies:    { icon: <Building2 className="h-3.5 w-3.5" />, label: "Related Companies",    color: "sky"    },
  stories:      { icon: <BookOpen className="h-3.5 w-3.5" />,  label: "Related Stories",      color: "amber"  },
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
        <div key={i} className="h-12 rounded-lg bg-white/[0.04]" />
      ))}
    </div>
  );
}

export function RelatedContent({
  entityType, entityId, title, sector, className = "",
}: RelatedContentProps) {
  const [groups,  setGroups]  = useState<RelatedGroup[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!entityId) return;
    const params = new URLSearchParams();
    if (title)  params.set("title",  title);
    if (sector) params.set("sector", sector);
    fetch(`${API}/api/related/${entityType}/${encodeURIComponent(entityId)}?${params}`)
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (!data) return;
        const built: RelatedGroup[] = [];
        for (const [key, items] of Object.entries(data as Record<string, RelatedItem[]>)) {
          if (!Array.isArray(items) || items.length === 0) continue;
          const meta = TYPE_META[key] ?? TYPE_META.events;
          built.push({ type: key, ...meta, items: items.slice(0, 5) });
        }
        setGroups(built);
      })
      .catch(() => {/* ignore */})
      .finally(() => setLoading(false));
  }, [entityType, entityId, title, sector]);

  if (!loading && groups.length === 0) return null;

  return (
    <section className={`rounded-xl border border-white/[0.06] bg-white/[0.02] p-4 ${className}`}>
      <div className="mb-3 flex items-center gap-2">
        <Sparkles className="h-4 w-4 text-violet-400" />
        <h3 className="text-sm font-semibold text-white">Related Intelligence</h3>
      </div>

      {loading ? (
        <Skeleton />
      ) : (
        <div className="space-y-4">
          {groups.map(group => (
            <div key={group.type}>
              <div className={`mb-2 flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider ${COLOR_CLASSES[group.color] ?? "text-slate-400"}`}>
                {group.icon}
                {group.label}
              </div>
              <ul className="space-y-1">
                {group.items.map(item => (
                  <li key={item.id}>
                    <Link
                      href={item.href as any}
                      className="group flex items-center gap-2 rounded-lg px-3 py-2 text-xs transition hover:bg-white/[0.05]"
                    >
                      <span className="flex-1 text-slate-300 group-hover:text-white line-clamp-2 leading-snug">
                        {item.title}
                      </span>
                      {item.score !== undefined && (
                        <span className="shrink-0 text-[10px] font-medium text-slate-500">
                          {item.score}%
                        </span>
                      )}
                      <ArrowRight className="h-3 w-3 shrink-0 text-slate-600 group-hover:text-slate-400" />
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
