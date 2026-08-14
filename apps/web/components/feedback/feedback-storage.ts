/**
 * Returning-user feedback popup — visit/dismissal/submission state machine.
 * localStorage (persists across sessions) for the durable counters,
 * sessionStorage (clears when the tab/browser closes) as the actual
 * definition of "a new session" — no time-based heuristic needed.
 *
 * Rules (see the feature spec): first visit never shows. First return
 * shows once. An unanswered dismissal waits 5 subsequent visits before
 * showing again. A successful submission means never again.
 */
"use client";

const KEY_VISIT_COUNT = "market_ripple_feedback_visit_count";
const KEY_LAST_SEEN = "market_ripple_feedback_last_seen";
const KEY_DISMISSED = "market_ripple_feedback_dismissed";
const KEY_SUBMITTED = "market_ripple_feedback_submitted";
const SESSION_KEY = "market_ripple_feedback_session_ticked";

const DISMISS_COOLDOWN_VISITS = 5;
const MIN_VISIT_TO_SHOW = 2; // first visit is #1 — never eligible

export interface VisitEvaluation {
  shouldShow: boolean;
  visitCount: number;
}

/**
 * Call once per app load. Increments the visit counter exactly once per
 * browser session, then reports whether this is the qualifying tick to
 * show the popup. A later re-evaluation within the same tab session (e.g.
 * a hard refresh) always reports shouldShow: false — the decision is made
 * once per session, not re-checked.
 */
export function evaluateReturningVisit(): VisitEvaluation {
  if (typeof window === "undefined") return { shouldShow: false, visitCount: 0 };
  try {
    if (localStorage.getItem(KEY_SUBMITTED) === "true") {
      return { shouldShow: false, visitCount: 0 };
    }

    const isNewSessionTick = sessionStorage.getItem(SESSION_KEY) !== "true";
    let visitCount = parseInt(localStorage.getItem(KEY_VISIT_COUNT) || "0", 10) || 0;

    if (isNewSessionTick) {
      visitCount += 1;
      localStorage.setItem(KEY_VISIT_COUNT, String(visitCount));
      localStorage.setItem(KEY_LAST_SEEN, new Date().toISOString());
      sessionStorage.setItem(SESSION_KEY, "true");
    }

    if (!isNewSessionTick) return { shouldShow: false, visitCount };
    if (visitCount < MIN_VISIT_TO_SHOW) return { shouldShow: false, visitCount };

    const dismissedAtRaw = localStorage.getItem(KEY_DISMISSED);
    const dismissedAt = dismissedAtRaw ? parseInt(dismissedAtRaw, 10) : null;
    if (dismissedAt != null && !Number.isNaN(dismissedAt) && visitCount < dismissedAt + DISMISS_COOLDOWN_VISITS) {
      return { shouldShow: false, visitCount };
    }

    return { shouldShow: true, visitCount };
  } catch {
    return { shouldShow: false, visitCount: 0 };
  }
}

export function recordDismissal(visitCount: number) {
  try {
    localStorage.setItem(KEY_DISMISSED, String(visitCount));
  } catch {}
}

export function recordSubmission() {
  try {
    localStorage.setItem(KEY_SUBMITTED, "true");
    localStorage.removeItem(KEY_DISMISSED);
  } catch {}
}
