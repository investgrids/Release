"use client";
import { useState, useEffect, useCallback } from "react";

const KEY_THEMES = "preferred_themes";

/**
 * Manages user theme/interest preferences in localStorage.
 * Future: sync to user profile in DB when auth is added.
 */
export function useLocalPreferences() {
  const [themes, setThemes] = useState<string[]>([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    try {
      const s = localStorage.getItem(KEY_THEMES);
      if (s) setThemes(JSON.parse(s));
    } catch {}
    setLoaded(true);
  }, []);

  const saveThemes = useCallback((selected: string[]) => {
    setThemes(selected);
    try { localStorage.setItem(KEY_THEMES, JSON.stringify(selected)); } catch {}
  }, []);

  const toggleTheme = useCallback((theme: string) => {
    setThemes(prev => {
      const next = prev.includes(theme)
        ? prev.filter(t => t !== theme)
        : [...prev, theme];
      try { localStorage.setItem(KEY_THEMES, JSON.stringify(next)); } catch {}
      return next;
    });
  }, []);

  return { themes, loaded, saveThemes, toggleTheme };
}
