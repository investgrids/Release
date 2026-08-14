"use client";

import { useEffect, useRef, useState } from "react";

// Wraps a `pending` boolean (e.g. from useTransition) so a loading
// indicator only appears if the transition is actually slow — 2026-08
// audit, explicit request: hub tab switches (Companies/Ripple) trigger a
// real server round-trip via router.push with zero loading feedback
// today, but flashing a spinner for every sub-300ms switch would be worse
// than showing nothing. Only flips true once `pending` has been true
// continuously for `delayMs`; clears immediately the instant pending
// goes false, whichever comes first.
export function useDelayedPending(pending: boolean, delayMs = 600): boolean {
  const [showLoading, setShowLoading] = useState(false);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (pending) {
      timeoutRef.current = setTimeout(() => setShowLoading(true), delayMs);
    } else {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      setShowLoading(false);
    }
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, [pending, delayMs]);

  return showLoading;
}
