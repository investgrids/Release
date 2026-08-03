"use client";

import { useEffect, useState } from "react";
import { Sun, Moon } from "lucide-react";

const STORAGE_KEY = "mr-theme";

/**
 * Light/dark toggle. Light is the app default (bare :root in globals.css,
 * no attribute needed); this only ever sets/clears data-theme="dark" on
 * <html> — the same mechanism the FOUC-prevention script in layout.tsx
 * reads on next load. Renders a disabled placeholder until mounted so the
 * icon never flips visibly during hydration (the real theme is already
 * correct pre-hydration via that script; this component just needs to
 * agree with it before rendering the "live" icon).
 */
export function ThemeToggle() {
  const [mounted, setMounted] = useState(false);
  const [isDark, setIsDark] = useState(false);

  useEffect(() => {
    setIsDark(document.documentElement.getAttribute("data-theme") === "dark");
    setMounted(true);
  }, []);

  function toggle() {
    const next = !isDark;
    setIsDark(next);
    if (next) {
      document.documentElement.setAttribute("data-theme", "dark");
      localStorage.setItem(STORAGE_KEY, "dark");
    } else {
      document.documentElement.removeAttribute("data-theme");
      localStorage.setItem(STORAGE_KEY, "light");
    }
  }

  return (
    <button
      onClick={toggle}
      aria-label={mounted ? (isDark ? "Switch to light theme" : "Switch to dark theme") : "Toggle theme"}
      title={mounted ? (isDark ? "Switch to light theme" : "Switch to dark theme") : undefined}
      className="flex h-9 w-9 items-center justify-center rounded-full border border-surface-border bg-surface-card text-text-secondary transition hover:bg-surface-card/70 hover:text-text-primary"
    >
      {mounted && isDark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
    </button>
  );
}
