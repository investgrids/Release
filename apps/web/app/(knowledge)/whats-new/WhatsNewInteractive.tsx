"use client";

import { useState } from "react";
import Link from "next/link";
import { ChevronDown, Sparkles, Wrench, Bug, Clock } from "lucide-react";
import { trackEvent } from "@/lib/analytics";

// ── Types (mirrors the data shape in page.tsx) ─────────────────────────────

type ChangeType = "Feature" | "Improvement" | "Fix";

interface ChangeEntry {
  type: ChangeType;
  name: string | null;
  description: string;
  href: string | null;
}

interface Release {
  version: string;
  date: string;
  codename: string;
  headline: string;
  changes: ChangeEntry[];
}

interface FaqItem {
  id: string;
  q: string;
  a: string;
}

const BADGE_STYLES: Record<ChangeType, string> = {
  Feature: "bg-violet-50 text-violet-700 border-violet-200 dark:bg-violet-500/10 dark:text-violet-300 dark:border-violet-500/25",
  Improvement: "bg-sky-50 text-sky-700 border-sky-200 dark:bg-sky-500/10 dark:text-sky-300 dark:border-sky-500/25",
  Fix: "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-500/10 dark:text-amber-300 dark:border-amber-500/25",
};

const BADGE_ICONS: Record<ChangeType, typeof Sparkles> = {
  Feature: Sparkles,
  Improvement: Wrench,
  Fix: Bug,
};

function ChangeGroup({ type, changes }: { type: ChangeType; changes: ChangeEntry[] }) {
  const items = changes.filter((c) => c.type === type);
  if (items.length === 0) return null;
  const Icon = BADGE_ICONS[type];
  const label = type === "Feature" ? "Features" : type === "Improvement" ? "Improvements" : "Fixes";
  return (
    <div>
      <p className="mb-2 flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-[0.15em] text-text-muted">
        <Icon className="h-3 w-3" />
        {label}
      </p>
      <div className="space-y-2">
        {items.map((c, i) => (
          <div key={i} className="rounded-lg border border-surface-border/6 bg-text-primary/[0.02] p-3">
            {c.name ? (
              <p className="text-[13px] font-semibold text-text-primary">
                {c.href ? (
                  <Link href={c.href as any} className="underline decoration-dotted underline-offset-2 hover:text-violet-500 dark:hover:text-violet-400">
                    {c.name}
                  </Link>
                ) : (
                  c.name
                )}
              </p>
            ) : null}
            <p className="mt-0.5 text-[12px] leading-5 text-text-secondary">{c.description}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

export function ReleaseAccordion({ releases, defaultOpenVersion }: { releases: Release[]; defaultOpenVersion: string }) {
  const [openVersion, setOpenVersion] = useState<string | null>(defaultOpenVersion);

  function toggle(version: string) {
    const next = openVersion === version ? null : version;
    setOpenVersion(next);
    if (next) trackEvent("release_open", { version: next });
  }

  return (
    <div className="space-y-2.5">
      {releases.map((release, idx) => {
        const isOpen = openVersion === release.version;
        const panelId = `release-panel-${release.version}`;
        const triggerId = `release-trigger-${release.version}`;
        const featureCount = release.changes.filter((c) => c.type === "Feature").length;
        const otherCount = release.changes.length - featureCount;
        return (
          <div
            key={release.version}
            className={`rounded-xl border transition-colors ${
              isOpen
                ? "border-surface-border/[0.14] bg-surface-card"
                : "border-surface-border/7 bg-transparent hover:border-surface-border/[0.12] hover:bg-text-primary/[0.02]"
            }`}
          >
            <button
              id={triggerId}
              type="button"
              onClick={() => toggle(release.version)}
              aria-expanded={isOpen}
              aria-controls={panelId}
              className="flex w-full flex-wrap items-center justify-between gap-3 rounded-xl px-5 py-4 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500/50"
            >
              <div className="flex flex-wrap items-center gap-2">
                <span
                  className={`rounded-full px-3 py-1 text-[11px] font-black tracking-wide ${
                    idx === 0
                      ? "border border-violet-200 bg-violet-50 text-violet-700 dark:border-violet-500/30 dark:bg-violet-500/20 dark:text-violet-300"
                      : "border border-surface-border/8 bg-text-primary/[0.06] text-text-secondary"
                  }`}
                >
                  v{release.version}
                </span>
                <span className="text-[14px] font-bold text-text-primary">{release.codename}</span>
                {idx === 0 && (
                  <span className="rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-0.5 text-[10px] font-semibold text-emerald-700 dark:border-emerald-500/25 dark:bg-emerald-500/15 dark:text-emerald-400">
                    Latest
                  </span>
                )}
              </div>
              <div className="flex items-center gap-3">
                <span className="flex items-center gap-1 text-[11px] text-text-muted">
                  <Clock className="h-3 w-3" />
                  {release.date}
                </span>
                <span className="hidden text-[11px] text-text-muted sm:inline">
                  {featureCount ? `${featureCount} feature${featureCount > 1 ? "s" : ""}` : ""}
                  {featureCount && otherCount ? " · " : ""}
                  {otherCount ? `${otherCount} improvement${otherCount > 1 ? "s" : ""}/fix${otherCount > 1 ? "es" : ""}` : ""}
                </span>
                <ChevronDown className={`h-4 w-4 shrink-0 text-text-muted transition-transform ${isOpen ? "rotate-180" : ""}`} aria-hidden="true" />
              </div>
            </button>
            <div
              id={panelId}
              role="region"
              aria-labelledby={triggerId}
              className={`overflow-hidden transition-all duration-200 ${isOpen ? "max-h-[3000px] opacity-100" : "max-h-0 opacity-0"}`}
            >
              <div className="space-y-4 px-5 pb-5">
                <p className="text-[13px] leading-6 text-text-secondary">{release.headline}</p>
                <ChangeGroup type="Feature" changes={release.changes} />
                <ChangeGroup type="Improvement" changes={release.changes} />
                <ChangeGroup type="Fix" changes={release.changes} />
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function FaqAccordion({ faqs }: { faqs: FaqItem[] }) {
  const [openId, setOpenId] = useState<string | null>(null);

  function toggle(id: string) {
    const next = openId === id ? null : id;
    setOpenId(next);
    if (next) trackEvent("faq_open", { question_id: next });
  }

  return (
    <div className="space-y-2">
      {faqs.map((item) => {
        const isOpen = openId === item.id;
        const panelId = `faq-panel-${item.id}`;
        const triggerId = `faq-trigger-${item.id}`;
        return (
          <div
            key={item.id}
            className={`rounded-xl border transition-colors ${
              isOpen
                ? "border-surface-border/[0.12] bg-text-primary/[0.04]"
                : "border-surface-border/6 bg-transparent hover:border-surface-border/[0.10] hover:bg-text-primary/[0.02]"
            }`}
          >
            <button
              id={triggerId}
              type="button"
              onClick={() => toggle(item.id)}
              aria-expanded={isOpen}
              aria-controls={panelId}
              className="flex w-full items-start justify-between gap-4 px-5 py-4 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500/50"
            >
              <h3 className="text-[14px] font-medium leading-snug text-text-primary">{item.q}</h3>
              <ChevronDown className={`mt-0.5 h-4 w-4 shrink-0 text-text-muted transition-transform ${isOpen ? "rotate-180" : ""}`} aria-hidden="true" />
            </button>
            <div
              id={panelId}
              role="region"
              aria-labelledby={triggerId}
              className={`overflow-hidden transition-all duration-200 ${isOpen ? "max-h-[600px] opacity-100" : "max-h-0 opacity-0"}`}
            >
              <p className="px-5 pb-5 text-[13px] leading-6 text-text-secondary">{item.a}</p>
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function FeatureLinkTracker({ feature, href, children, className }: { feature: string; href: string; className?: string; children: React.ReactNode }) {
  return (
    <Link href={href as any} className={className} onClick={() => trackEvent("feature_click", { feature })}>
      {children}
    </Link>
  );
}

export function RoadmapLinkTracker({ item, children, className }: { item: string; className?: string; children: React.ReactNode }) {
  return (
    <a
      href="/contact"
      className={className}
      onClick={() => trackEvent("roadmap_click", { item })}
    >
      {children}
    </a>
  );
}
