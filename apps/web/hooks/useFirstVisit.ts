"use client";
import { useState, useEffect, useCallback } from "react";

const KEY_ONBOARDED = "marketripple_onboarded";
const KEY_LAST_VISIT = "last_visit";

/**
 * Detects first-time vs returning visitors via localStorage.
 * Easy to replace: swap localStorage.getItem/setItem calls with API calls
 * once authentication is added.
 */
export function useFirstVisit() {
  // null = unknown (SSR / before hydration)
  const [isFirstVisit, setIsFirstVisit] = useState<boolean | null>(null);
  const [lastVisit, setLastVisit] = useState<string | null>(null);

  useEffect(() => {
    try {
      const onboarded = localStorage.getItem(KEY_ONBOARDED) === "true";
      const lv = localStorage.getItem(KEY_LAST_VISIT);
      setIsFirstVisit(!onboarded);
      setLastVisit(lv);
      localStorage.setItem(KEY_LAST_VISIT, new Date().toISOString());
    } catch {
      setIsFirstVisit(false);
    }
  }, []);

  const completeOnboarding = useCallback(() => {
    try {
      localStorage.setItem(KEY_ONBOARDED, "true");
      localStorage.setItem(KEY_LAST_VISIT, new Date().toISOString());
    } catch {}
    setIsFirstVisit(false);
  }, []);

  const skipOnboarding = useCallback(() => {
    try {
      localStorage.setItem(KEY_ONBOARDED, "true");
    } catch {}
    setIsFirstVisit(false);
  }, []);

  // Dev utility — reset to first-visit state
  const resetOnboarding = useCallback(() => {
    try {
      localStorage.removeItem(KEY_ONBOARDED);
      localStorage.removeItem(KEY_LAST_VISIT);
    } catch {}
    setIsFirstVisit(true);
  }, []);

  return { isFirstVisit, lastVisit, completeOnboarding, skipOnboarding, resetOnboarding };
}
