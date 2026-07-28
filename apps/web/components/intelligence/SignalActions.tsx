"use client";

import { useState } from "react";
import Link from "next/link";
import { Sparkles, GitCompare, Building2, Link2, Check, Radar } from "lucide-react";
import { trackEvent } from "@/lib/analytics";

/**
 * Signal detail page — Quick Actions + Share (UI-only redesign, no new
 * backend calls). A small client island inside the server-rendered signal
 * page, same reasoning as AskAICta.tsx: the page itself stays a Server
 * Component, only the handful of genuinely interactive controls (copy-to-
 * clipboard, share-intent links, which need window/navigator) need to be
 * client-side.
 */
export function SignalActions({
  headline, url, companies, opportunityId,
}: {
  headline: string; url: string; companies: string[]; opportunityId?: string | number | null;
}) {
  const [copied, setCopied] = useState(false);

  const copyLink = async () => {
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      trackEvent("signal_copy_link");
      setTimeout(() => setCopied(false), 1800);
    } catch { /* clipboard permission denied — no-op, button just won't confirm */ }
  };

  const compareHref = companies.length >= 2 ? `/compare?a=${companies[0]}&b=${companies[1]}` : null;
  const shareText = encodeURIComponent(headline);
  const shareUrl = encodeURIComponent(url);

  return (
    <div className="space-y-3">
      <div className="rounded-[16px] border border-white/[0.08] bg-white/[0.02] p-4 backdrop-blur">
        <p className="mb-3 text-[10px] font-bold uppercase tracking-[0.14em] text-slate-500">Quick Actions</p>
        <div className="space-y-1.5">
          <Link href={`/ai-search?q=${encodeURIComponent(headline)}` as any}
            onClick={() => trackEvent("signal_cta_click", { action: "analyze_ai" })}
            className="flex items-center gap-2.5 rounded-[10px] px-2.5 py-2 text-[12.5px] font-medium text-slate-300 transition hover:bg-white/[0.05] hover:text-violet-300">
            <Sparkles className="h-3.5 w-3.5 shrink-0" /> Analyze with AI
          </Link>
          {compareHref && (
            <Link href={compareHref as any}
              onClick={() => trackEvent("signal_cta_click", { action: "compare" })}
              className="flex items-center gap-2.5 rounded-[10px] px-2.5 py-2 text-[12.5px] font-medium text-slate-300 transition hover:bg-white/[0.05] hover:text-violet-300">
              <GitCompare className="h-3.5 w-3.5 shrink-0" /> Compare {companies[0]} vs {companies[1]}
            </Link>
          )}
          {opportunityId != null && (
            <Link href={`/opportunity-radar/${opportunityId}`}
              onClick={() => trackEvent("signal_cta_click", { action: "opportunity" })}
              className="flex items-center gap-2.5 rounded-[10px] px-2.5 py-2 text-[12.5px] font-medium text-slate-300 transition hover:bg-white/[0.05] hover:text-violet-300">
              <Radar className="h-3.5 w-3.5 shrink-0" /> View Related Opportunity
            </Link>
          )}
          <Link href="/companies"
            className="flex items-center gap-2.5 rounded-[10px] px-2.5 py-2 text-[12.5px] font-medium text-slate-300 transition hover:bg-white/[0.05] hover:text-violet-300">
            <Building2 className="h-3.5 w-3.5 shrink-0" /> Browse All Companies
          </Link>
          <button onClick={copyLink}
            className="flex w-full items-center gap-2.5 rounded-[10px] px-2.5 py-2 text-left text-[12.5px] font-medium text-slate-300 transition hover:bg-white/[0.05] hover:text-violet-300">
            {copied ? <Check className="h-3.5 w-3.5 shrink-0 text-emerald-400" /> : <Link2 className="h-3.5 w-3.5 shrink-0" />}
            {copied ? "Copied!" : "Copy Link"}
          </button>
        </div>
      </div>

      <div className="rounded-[16px] border border-white/[0.08] bg-white/[0.02] p-4 backdrop-blur">
        <p className="mb-3 text-[10px] font-bold uppercase tracking-[0.14em] text-slate-500">Share Intelligence</p>
        <div className="flex gap-2">
          <a href={`https://www.linkedin.com/sharing/share-offsite/?url=${shareUrl}`} target="_blank" rel="noopener noreferrer"
            onClick={() => trackEvent("signal_share", { channel: "linkedin" })}
            className="flex h-8 flex-1 items-center justify-center rounded-[10px] border border-white/10 bg-white/[0.03] text-[11px] font-semibold text-slate-400 transition hover:border-white/20 hover:text-white">
            LinkedIn
          </a>
          <a href={`https://twitter.com/intent/tweet?text=${shareText}&url=${shareUrl}`} target="_blank" rel="noopener noreferrer"
            onClick={() => trackEvent("signal_share", { channel: "x" })}
            className="flex h-8 flex-1 items-center justify-center rounded-[10px] border border-white/10 bg-white/[0.03] text-[11px] font-semibold text-slate-400 transition hover:border-white/20 hover:text-white">
            X
          </a>
          <a href={`https://wa.me/?text=${shareText}%20${shareUrl}`} target="_blank" rel="noopener noreferrer"
            onClick={() => trackEvent("signal_share", { channel: "whatsapp" })}
            className="flex h-8 flex-1 items-center justify-center rounded-[10px] border border-white/10 bg-white/[0.03] text-[11px] font-semibold text-slate-400 transition hover:border-white/20 hover:text-white">
            WhatsApp
          </a>
        </div>
      </div>
    </div>
  );
}
