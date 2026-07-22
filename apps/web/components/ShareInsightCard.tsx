"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import {
  Share2, X, Copy, Check,
  MessageCircle, Send, Link as LinkIcon,
} from "lucide-react";
import { API_BASE_URL as API } from "@/lib/api";

/* Inline SVG icons for platforms not in this lucide-react version */
const XIcon = () => (
  <svg viewBox="0 0 24 24" className="h-4 w-4" fill="currentColor" aria-hidden="true">
    <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-4.714-6.231-5.401 6.231H2.748l7.73-8.835L1.254 2.25H8.08l4.252 5.622 5.912-5.622Zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
  </svg>
);
const LinkedInIcon = () => (
  <svg viewBox="0 0 24 24" className="h-4 w-4" fill="currentColor" aria-hidden="true">
    <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 0 1-2.063-2.065 2.064 2.064 0 1 1 2.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/>
  </svg>
);

export type ShareInsightType =
  | "event" | "company" | "story" | "opportunity" | "ripple" | "search" | "article";

interface ShareInsightCardProps {
  title:       string;
  summary?:    string;
  entityType:  ShareInsightType;
  entityId:    string;
  /** Override the share URL — defaults to current page URL */
  shareUrl?:   string;
  /** Extra label shown on the trigger button */
  label?:      string;
  className?:  string;
  /** Initial count to show in the popover — omit to hide the count entirely */
  shareCount?: number;
}

const SITE = typeof window !== "undefined"
  ? window.location.origin
  : (process.env.NEXT_PUBLIC_SITE_URL ?? "https://marketripple.in");

function buildShareUrl(entityType: ShareInsightType, entityId: string): string {
  const path = `${SITE}/share/${entityType}/${entityId}`;
  return path;
}

function encode(s: string) { return encodeURIComponent(s); }

export function ShareInsightCard({
  title, summary, entityType, entityId, shareUrl, label, className = "", shareCount,
}: ShareInsightCardProps) {
  const [open,    setOpen]    = useState(false);
  const [copied,  setCopied]  = useState(false);
  const [count,   setCount]   = useState(shareCount);
  const dialogRef             = useRef<HTMLDivElement>(null);

  // Backend tracking only exists for articles today (POST /api/insights/{slug}/share)
  // — other entity types render this same component but aren't wired up yet.
  const trackShare = useCallback(() => {
    if (entityType !== "article") return;
    fetch(`${API}/api/insights/${entityId}/share`, { method: "POST" })
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d?.share_count != null) setCount(d.share_count); })
      .catch(() => {});
  }, [entityType, entityId]);

  const url  = shareUrl ?? buildShareUrl(entityType, entityId);
  const text = summary
    ? `${title} — ${summary.slice(0, 120)}…`
    : title;
  const brandedText = `${text}\n\nVia MarketRipple 📊 ${url}`;

  const channels = [
    {
      id:    "twitter",
      label: "X (Twitter)",
      icon:  <XIcon />,
      color: "bg-black hover:bg-zinc-800",
      href:  `https://twitter.com/intent/tweet?text=${encode(brandedText)}`,
    },
    {
      id:    "linkedin",
      label: "LinkedIn",
      icon:  <LinkedInIcon />,
      color: "bg-[#0A66C2] hover:bg-[#004182]",
      href:  `https://www.linkedin.com/sharing/share-offsite/?url=${encode(url)}`,
    },
    {
      id:    "whatsapp",
      label: "WhatsApp",
      icon:  <MessageCircle className="h-4 w-4" />,
      color: "bg-[#25D366] hover:bg-[#1da851]",
      href:  `https://wa.me/?text=${encode(brandedText)}`,
    },
    {
      id:    "telegram",
      label: "Telegram",
      icon:  <Send className="h-4 w-4" />,
      color: "bg-[#229ED9] hover:bg-[#1a7dac]",
      href:  `https://t.me/share/url?url=${encode(url)}&text=${encode(text)}`,
    },
  ] as const;

  const handleCopy = useCallback(async () => {
    // Track on the click itself, not gated on the clipboard write succeeding
    // — a browser blocking clipboard access doesn't mean the reader didn't
    // intend to share (the URL is still right there in the popover).
    trackShare();
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch { /* clipboard unavailable — count still recorded above */ }
  }, [url, trackShare]);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    function onPointerDown(e: PointerEvent) {
      if (dialogRef.current && !dialogRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, [open]);

  // Close on Escape
  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) { if (e.key === "Escape") setOpen(false); }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <div className={`relative inline-flex ${className}`}>
      {/* Trigger button */}
      <button
        onClick={() => setOpen(v => !v)}
        className="inline-flex items-center gap-1.5 rounded-lg border border-white/[0.08] bg-white/[0.04] px-3 py-1.5 text-xs font-medium text-slate-300 transition hover:border-violet-500/40 hover:bg-violet-500/10 hover:text-violet-300"
        aria-label="Share this insight"
        aria-expanded={open}
      >
        <Share2 className="h-3.5 w-3.5" />
        {label ?? "Share"}
        {count != null && <span className="text-slate-500">· {count.toLocaleString("en-IN")}</span>}
      </button>

      {/* Popover */}
      {open && (
        <div
          ref={dialogRef}
          role="dialog"
          aria-label="Share insight"
          className="absolute right-0 top-full z-50 mt-2 w-72 origin-top-right rounded-xl border border-white/[0.08] bg-slate-900 p-4 shadow-2xl shadow-black/60"
        >
          {/* Header */}
          <div className="mb-3 flex items-start justify-between gap-2">
            <div>
              <p className="text-xs font-semibold text-white">Share Insight</p>
              <p className="mt-0.5 line-clamp-2 text-[11px] text-slate-400">{title}</p>
            </div>
            <button
              onClick={() => setOpen(false)}
              className="shrink-0 rounded-md p-1 text-slate-500 hover:bg-white/[0.06] hover:text-slate-300"
              aria-label="Close"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>

          {/* Platform buttons */}
          <div className="mb-3 grid grid-cols-2 gap-2">
            {channels.map(ch => (
              <a
                key={ch.id}
                href={ch.href}
                target="_blank"
                rel="noopener noreferrer"
                className={`flex items-center gap-2 rounded-lg px-3 py-2 text-xs font-medium text-white transition ${ch.color}`}
                onClick={() => { trackShare(); setOpen(false); }}
              >
                {ch.icon}
                {ch.label}
              </a>
            ))}
          </div>

          {/* Copy link row */}
          <div className="flex items-center gap-2 rounded-lg border border-white/[0.06] bg-white/[0.03] px-3 py-2">
            <LinkIcon className="h-3.5 w-3.5 shrink-0 text-slate-500" />
            <span className="flex-1 truncate text-[11px] text-slate-400">{url}</span>
            <button
              onClick={handleCopy}
              className={`shrink-0 rounded-md px-2 py-1 text-[10px] font-semibold transition ${
                copied
                  ? "bg-emerald-500/20 text-emerald-400"
                  : "bg-white/[0.06] text-slate-300 hover:bg-white/[0.1]"
              }`}
              aria-label="Copy link"
            >
              {copied ? (
                <span className="flex items-center gap-1"><Check className="h-3 w-3" />Copied</span>
              ) : (
                <span className="flex items-center gap-1"><Copy className="h-3 w-3" />Copy</span>
              )}
            </button>
          </div>

          {/* Branding footer */}
          <p className="mt-2 text-center text-[10px] text-slate-600">
            Powered by MarketRipple · AI Market Intelligence
          </p>
        </div>
      )}
    </div>
  );
}
