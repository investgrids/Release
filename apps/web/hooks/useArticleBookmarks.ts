"use client";

import { useCallback, useEffect, useState } from "react";

export interface BookmarkedArticle {
  slug: string;
  headline: string;
  articleType: string;
  addedAt: number;
}

const STORAGE_KEY = "mr_article_bookmarks";

function readStorage(): BookmarkedArticle[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as BookmarkedArticle[]) : [];
  } catch {
    return [];
  }
}

function writeStorage(items: BookmarkedArticle[]) {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(items)); } catch { /**/ }
}

export function useArticleBookmarks() {
  const [items, setItems] = useState<BookmarkedArticle[]>([]);

  useEffect(() => { setItems(readStorage()); }, []);

  const toggle = useCallback((article: Omit<BookmarkedArticle, "addedAt">) => {
    setItems(prev => {
      const exists = prev.some(i => i.slug === article.slug);
      const next = exists
        ? prev.filter(i => i.slug !== article.slug)
        : [{ ...article, addedAt: Date.now() }, ...prev];
      writeStorage(next);
      return next;
    });
  }, []);

  const isBookmarked = useCallback((slug: string) => items.some(i => i.slug === slug), [items]);

  return { items, toggle, isBookmarked, count: items.length };
}
