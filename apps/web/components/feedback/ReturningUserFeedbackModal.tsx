/**
 * Returning-user product feedback popup — global, mounted once in
 * app/layout.tsx. Renders nothing on first visit or for anyone who has
 * already submitted; a returning visitor sees it once per qualifying
 * session per the cadence rules in feedback-storage.ts.
 *
 * Client-only and self-contained: no SSR impact (renders null until its
 * own useEffect decides to open), no blocking of navigation, page render,
 * or other API requests.
 */
"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { usePathname } from "next/navigation";
import { X, Loader2, Check } from "lucide-react";
import { API_BASE_URL } from "@/lib/api";
import { trackEvent } from "@/lib/analytics";
import { evaluateReturningVisit, recordDismissal, recordSubmission } from "./feedback-storage";
import { REASON_OPTIONS, IMPROVEMENT_OPTIONS, type FeedbackOption } from "./feedback-types";

type Stage = "closed" | "open" | "submitting" | "success" | "error";

// Give the app a moment to finish initializing (esp. on a deep link)
// before evaluating whether to interrupt with anything.
const SHOW_DELAY_MS = 4000;

function deviceCategory(): string {
  if (typeof window === "undefined") return "unknown";
  const w = window.innerWidth;
  if (w < 768) return "mobile";
  if (w < 1024) return "tablet";
  return "desktop";
}

function OptionChips({
  options, selected, onToggle,
}: { options: FeedbackOption[]; selected: string[]; onToggle: (key: string) => void }) {
  return (
    <div className="flex flex-wrap gap-2" role="group">
      {options.map(o => {
        const active = selected.includes(o.key);
        return (
          <button
            key={o.key}
            type="button"
            aria-pressed={active}
            onClick={() => onToggle(o.key)}
            className={`rounded-full border px-3 py-1.5 text-[12.5px] transition ${
              active
                ? "border-accent-violet/40 bg-accent-violet/15 text-accent-violet"
                : "border-surface-border/12 bg-text-primary/[0.02] text-text-secondary hover:bg-text-primary/[0.05]"
            }`}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}

export function ReturningUserFeedbackModal() {
  const pathname = usePathname();
  const [stage, setStage] = useState<Stage>("closed");
  const [visitCount, setVisitCount] = useState(0);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [emailError, setEmailError] = useState(false);
  const [reasons, setReasons] = useState<string[]>([]);
  const [improvements, setImprovements] = useState<string[]>([]);
  const [otherReason, setOtherReason] = useState("");
  const [otherImprovement, setOtherImprovement] = useState("");
  const [additional, setAdditional] = useState("");

  const dialogRef = useRef<HTMLDivElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const previouslyFocused = useRef<HTMLElement | null>(null);

  // Decide once per session, after a short idle delay, whether to open.
  useEffect(() => {
    // Never interrupt an in-progress AI Search query/read.
    if (pathname?.startsWith("/ai-search")) return;
    const timer = setTimeout(() => {
      if (typeof document !== "undefined" && document.body.style.overflow === "hidden") {
        // Another modal/drawer already owns the screen — skip quietly
        // rather than stacking on top of it.
        return;
      }
      const { shouldShow, visitCount: vc } = evaluateReturningVisit();
      if (shouldShow) {
        setVisitCount(vc);
        setStage("open");
      }
    }, SHOW_DELAY_MS);
    return () => clearTimeout(timer);
    // Intentionally run once per mount — a client-side route change must
    // not re-trigger the eligibility check.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const close = useCallback((dismissed: boolean) => {
    if (dismissed) {
      recordDismissal(visitCount);
      trackEvent("returning_feedback_closed");
    }
    setStage("closed");
  }, [visitCount]);

  // Focus management + scroll lock while open.
  useEffect(() => {
    if (stage === "closed") return;
    if (stage === "open") trackEvent("returning_feedback_shown");
    previouslyFocused.current = document.activeElement as HTMLElement | null;
    document.body.style.overflow = "hidden";
    closeButtonRef.current?.focus();
    return () => {
      document.body.style.overflow = "";
      previouslyFocused.current?.focus?.();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stage === "closed"]);

  // Escape to close + a real Tab focus trap (nothing else in this app has
  // one — the feature spec calls for proper dialog semantics here).
  useEffect(() => {
    if (stage === "closed") return;
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") { close(true); return; }
      if (e.key !== "Tab" || !dialogRef.current) return;
      const focusables = dialogRef.current.querySelectorAll<HTMLElement>(
        'button, [href], input, textarea, select, [tabindex]:not([tabindex="-1"])'
      );
      if (focusables.length === 0) return;
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [stage, close]);

  function toggle(list: string[], setList: (v: string[]) => void, key: string) {
    setList(list.includes(key) ? list.filter(k => k !== key) : [...list, key]);
  }

  const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

  async function submit() {
    if (email.trim() && !EMAIL_RE.test(email.trim())) {
      setEmailError(true);
      return;
    }
    setEmailError(false);
    setStage("submitting");
    try {
      const res = await fetch(`${API_BASE_URL}/api/feedback/returning-user`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: name.trim() || undefined,
          email: email.trim() || undefined,
          reasons: reasons.map(k => REASON_OPTIONS.find(o => o.key === k)?.label ?? k),
          improvements: improvements.map(k => IMPROVEMENT_OPTIONS.find(o => o.key === k)?.label ?? k),
          other_reason: reasons.includes("other") ? (otherReason.trim() || undefined) : undefined,
          other_improvement: improvements.includes("other") ? (otherImprovement.trim() || undefined) : undefined,
          additional_feedback: additional.trim() || undefined,
          visit_count: visitCount,
          page: typeof window !== "undefined" ? window.location.pathname : undefined,
          device_category: deviceCategory(),
          referrer: typeof document !== "undefined" ? (document.referrer || undefined) : undefined,
          timestamp: new Date().toISOString(),
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      recordSubmission();
      trackEvent("returning_feedback_submitted", {
        reason_count: reasons.length,
        improvement_count: improvements.length,
      });
      setStage("success");
      setTimeout(() => setStage("closed"), 1800);
    } catch {
      setStage("error");
    }
  }

  if (stage === "closed") return null;

  const busy = stage === "submitting";

  return (
    <div className="fixed inset-0 z-[250] flex items-end justify-center sm:items-center">
      {/* Backdrop — click also counts as an unanswered dismissal */}
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-[2px]"
        onClick={() => stage !== "success" && close(true)}
        aria-hidden="true"
      />

      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="rufm-title"
        className="relative w-full sm:max-w-[560px] max-h-[92vh] sm:max-h-[85vh] overflow-y-auto rounded-t-[24px] sm:rounded-[20px] border border-surface-border/10 bg-surface-card shadow-[0_20px_60px_rgba(0,0,0,0.35)] sm:mx-4"
      >
        {stage === "success" ? (
          <div className="flex flex-col items-center gap-3 px-8 py-14 text-center">
            <div className="flex h-11 w-11 items-center justify-center rounded-full bg-emerald-500/15">
              <Check className="h-5 w-5 text-emerald-500" />
            </div>
            <h2 className="text-[17px] font-semibold text-text-primary">Thanks — this helps.</h2>
            <p className="text-[13.5px] text-text-secondary">
              We&apos;ll use your feedback to make Market Ripple more useful.
            </p>
          </div>
        ) : (
          <>
            <div className="flex items-start justify-between gap-4 px-6 pt-6 sm:px-7 sm:pt-7">
              <div>
                <h2 id="rufm-title" className="text-[19px] font-semibold text-text-primary">
                  👋 Welcome back
                </h2>
                <p className="mt-1.5 max-w-[420px] text-[13.5px] leading-relaxed text-text-secondary">
                  We noticed you came back to Market Ripple. We&apos;d love to understand what
                  brought you back — it helps us build the things that are actually useful to you.
                </p>
              </div>
              <button
                ref={closeButtonRef}
                type="button"
                aria-label="Close"
                onClick={() => close(true)}
                className="shrink-0 rounded-full p-1.5 text-text-muted transition hover:bg-text-primary/[0.06] hover:text-text-primary"
              >
                <X className="h-4.5 w-4.5" />
              </button>
            </div>

            <div className="space-y-6 px-6 py-6 sm:px-7">
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <div>
                  <label htmlFor="rufm-name" className="mb-1.5 block text-[12.5px] font-medium text-text-secondary">
                    Name <span className="text-text-muted">(optional)</span>
                  </label>
                  <input
                    id="rufm-name"
                    type="text"
                    value={name}
                    onChange={e => setName(e.target.value.slice(0, 128))}
                    placeholder="Your name"
                    className="w-full rounded-[10px] border border-surface-border/12 bg-text-primary/[0.02] px-3 py-2 text-[13px] text-text-primary placeholder:text-text-muted focus:border-accent-violet/40 focus:outline-none"
                  />
                </div>
                <div>
                  <label htmlFor="rufm-email" className="mb-1.5 block text-[12.5px] font-medium text-text-secondary">
                    Email <span className="text-text-muted">(optional — if you&apos;d like a reply)</span>
                  </label>
                  <input
                    id="rufm-email"
                    type="email"
                    value={email}
                    onChange={e => { setEmail(e.target.value); if (emailError) setEmailError(false); }}
                    placeholder="you@example.com"
                    aria-invalid={emailError}
                    className={`w-full rounded-[10px] border bg-text-primary/[0.02] px-3 py-2 text-[13px] text-text-primary placeholder:text-text-muted focus:outline-none ${
                      emailError ? "border-rose-500/50 focus:border-rose-500/50" : "border-surface-border/12 focus:border-accent-violet/40"
                    }`}
                  />
                  {emailError && (
                    <p role="alert" className="mt-1 text-[11.5px] text-rose-500">Enter a valid email address, or leave this blank.</p>
                  )}
                </div>
              </div>

              <fieldset>
                <legend className="mb-2.5 text-[13.5px] font-semibold text-text-primary">
                  What brought you back today?
                </legend>
                <OptionChips options={REASON_OPTIONS} selected={reasons} onToggle={k => toggle(reasons, setReasons, k)} />
                {reasons.includes("other") && (
                  <input
                    type="text"
                    value={otherReason}
                    onChange={e => setOtherReason(e.target.value.slice(0, 280))}
                    placeholder="Tell us more"
                    aria-label="Something else — what brought you back"
                    className="mt-2.5 w-full rounded-[10px] border border-surface-border/12 bg-text-primary/[0.02] px-3 py-2 text-[13px] text-text-primary placeholder:text-text-muted focus:border-accent-violet/40 focus:outline-none"
                  />
                )}
              </fieldset>

              <fieldset>
                <legend className="mb-2.5 text-[13.5px] font-semibold text-text-primary">
                  What would make Market Ripple more useful to you?
                </legend>
                <OptionChips options={IMPROVEMENT_OPTIONS} selected={improvements} onToggle={k => toggle(improvements, setImprovements, k)} />
                {improvements.includes("other") && (
                  <input
                    type="text"
                    value={otherImprovement}
                    onChange={e => setOtherImprovement(e.target.value.slice(0, 280))}
                    placeholder="Tell us more"
                    aria-label="Something else — what would make Market Ripple more useful"
                    className="mt-2.5 w-full rounded-[10px] border border-surface-border/12 bg-text-primary/[0.02] px-3 py-2 text-[13px] text-text-primary placeholder:text-text-muted focus:border-accent-violet/40 focus:outline-none"
                  />
                )}
              </fieldset>

              <div>
                <label htmlFor="rufm-additional" className="mb-2.5 block text-[13.5px] font-semibold text-text-primary">
                  Anything you wish Market Ripple did better?
                </label>
                <textarea
                  id="rufm-additional"
                  value={additional}
                  onChange={e => setAdditional(e.target.value.slice(0, 3000))}
                  placeholder="Tell us what you were looking for..."
                  rows={3}
                  className="w-full resize-none rounded-[12px] border border-surface-border/12 bg-text-primary/[0.02] px-3.5 py-2.5 text-[13px] text-text-primary placeholder:text-text-muted focus:border-accent-violet/40 focus:outline-none"
                />
              </div>

              {stage === "error" && (
                <p role="alert" className="text-[12.5px] text-rose-500">
                  We couldn&apos;t save your feedback. Please try again.
                </p>
              )}
            </div>

            <div className="sticky bottom-0 border-t border-surface-border/8 bg-surface-card px-6 py-4 sm:px-7">
              <button
                type="button"
                onClick={submit}
                disabled={busy}
                className="flex w-full items-center justify-center gap-2 rounded-[12px] bg-accent-violet px-4 py-3 text-[14px] font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {busy && <Loader2 className="h-4 w-4 animate-spin" />}
                {busy ? "Saving..." : "Save Feedback"}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
