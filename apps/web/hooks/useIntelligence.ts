"use client";

import { useState, useEffect, useRef } from "react";
import type { IntelligenceObject } from "@/components/intelligence/IntelligenceBlock";
import { API_BASE_URL as API } from "@/lib/api";


type ContextType = "home" | "company" | "event" | "theme" | "news" | "search";

function buildUrl(type: ContextType, id?: string, query?: string): string {
  switch (type) {
    case "home":    return `${API}/api/intelligence/home`;
    case "company": return `${API}/api/intelligence/company/${encodeURIComponent(id ?? "")}`;
    case "event":   return `${API}/api/intelligence/event/${encodeURIComponent(id ?? "")}`;
    case "theme":   return `${API}/api/intelligence/theme/${encodeURIComponent(id ?? "")}`;
    case "news":    return `${API}/api/intelligence/news/${encodeURIComponent(id ?? "")}`;
    case "search":  return `${API}/api/intelligence/search?q=${encodeURIComponent(query ?? "")}`;
  }
}

export function useIntelligence(
  type: ContextType,
  id?: string,
  query?: string,
): {
  data:    IntelligenceObject | null;
  loading: boolean;
  error:   string | null;
} {
  const [data,    setData]    = useState<IntelligenceObject | null>(null);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (type === "search" && !query) { setLoading(false); return; }
    if (type !== "home" && type !== "search" && !id) { setLoading(false); return; }

    abortRef.current?.abort();
    const ac = new AbortController();
    abortRef.current = ac;
    setLoading(true);
    setError(null);

    const url = buildUrl(type, id, query);

    fetch(url, { signal: ac.signal })
      .then(r => {
        if (!r.ok) throw new Error(`${r.status}`);
        return r.json();
      })
      .then((d: IntelligenceObject) => {
        setData(d);
        setLoading(false);
      })
      .catch(e => {
        if (e.name === "AbortError") return;
        setError(e.message || "Failed to load intelligence");
        setLoading(false);
      });

    return () => { ac.abort(); };
  }, [type, id, query]);

  return { data, loading, error };
}
