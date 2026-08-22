/**
 * Cookie consent state — the single source of truth for whether GA4 is
 * allowed to load (2026-08 audit). Real gate, not cosmetic: GoogleAnalytics
 * only renders its <Script> tags once this reports "granted" — Reject
 * means gtag.js never loads and no _ga/_ga_* cookies are ever set, not
 * just a banner with no effect. See legal/page.tsx's Cookie Information
 * section for the corresponding user-facing disclosure.
 *
 * localStorage, not a cookie — a decision about whether to set cookies
 * shouldn't itself require setting one just to remember the choice.
 */
"use client";

export type ConsentStatus = "granted" | "denied";

const STORAGE_KEY = "mr-cookie-consent";
const EVENT_NAME = "mr-cookie-consent-changed";

export function getConsent(): ConsentStatus | null {
  if (typeof window === "undefined") return null;
  try {
    const v = window.localStorage.getItem(STORAGE_KEY);
    return v === "granted" || v === "denied" ? v : null;
  } catch {
    return null;
  }
}

export function setConsent(status: ConsentStatus): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, status);
  } catch {
    // Storage can throw in some privacy-mode browsers — consent still
    // dispatches for this session even if it won't persist across visits.
  }
  window.dispatchEvent(new CustomEvent<ConsentStatus>(EVENT_NAME, { detail: status }));
}

export function onConsentChange(callback: (status: ConsentStatus) => void): () => void {
  const handler = (e: Event) => callback((e as CustomEvent<ConsentStatus>).detail);
  window.addEventListener(EVENT_NAME, handler);
  return () => window.removeEventListener(EVENT_NAME, handler);
}
