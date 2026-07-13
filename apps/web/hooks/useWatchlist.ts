"use client";

import { useCallback, useEffect, useState } from "react";

export type WatchlistItemType = "company" | "sector" | "event" | "theme" | "index" | "commodity";

export interface WatchlistItem {
  id: string;
  type: WatchlistItemType;
  label: string;
  ticker?: string;
  subtitle?: string;
  addedAt: number;
}

const STORAGE_KEY = "mr_watchlist";

function readStorage(): WatchlistItem[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as WatchlistItem[]) : [];
  } catch {
    return [];
  }
}

function writeStorage(items: WatchlistItem[]) {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(items)); } catch { /**/ }
}

export function useWatchlist() {
  const [items, setItems] = useState<WatchlistItem[]>([]);

  useEffect(() => { setItems(readStorage()); }, []);

  const add = useCallback((item: Omit<WatchlistItem, "addedAt">) => {
    setItems(prev => {
      if (prev.some(i => i.id === item.id)) return prev;
      const next = [{ ...item, addedAt: Date.now() }, ...prev];
      writeStorage(next);
      return next;
    });
  }, []);

  const remove = useCallback((id: string) => {
    setItems(prev => {
      const next = prev.filter(i => i.id !== id);
      writeStorage(next);
      return next;
    });
  }, []);

  const toggle = useCallback((item: Omit<WatchlistItem, "addedAt">) => {
    setItems(prev => {
      const exists = prev.some(i => i.id === item.id);
      const next = exists ? prev.filter(i => i.id !== item.id) : [{ ...item, addedAt: Date.now() }, ...prev];
      writeStorage(next);
      return next;
    });
  }, []);

  const isWatched = useCallback((id: string) => items.some(i => i.id === id), [items]);

  const clear = useCallback(() => { setItems([]); writeStorage([]); }, []);

  return { items, add, remove, toggle, isWatched, clear, count: items.length };
}
