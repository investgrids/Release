"use client";

import { useState } from "react";
import Link from "next/link";
import { Loader2, Sparkles, CheckCircle2, AlertTriangle, XCircle, HelpCircle } from "lucide-react";
import { API_BASE_URL as API } from "@/lib/api";

interface Suggestion { symbol: string; name: string; confidence: number }
interface HoldingResult {
  input: string;
  resolved: boolean;
  symbol: string | null;
  name: string | null;
  sector?: string | null;
  in_universe: boolean;
  event_count: number;
  news_count: number;
  level: "strong" | "light" | "thin" | "not_tracked";
  message: string;
  suggestions: Suggestion[];
  ai_search_query: string;
}
interface ConfidenceResponse {
  window_days: number;
  holdings: HoldingResult[];
  summary: { strong: number; light: number; thin: number; not_tracked: number };
}

const LEVEL_STYLE: Record<HoldingResult["level"], { badge: string; icon: React.ReactNode; label: string }> = {
  strong: {
    badge: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-300 border border-emerald-500/20",
    icon: <CheckCircle2 className="h-4 w-4" />,
    label: "Strong",
  },
  light: {
    badge: "bg-amber-500/10 text-amber-600 dark:text-amber-300 border border-amber-500/20",
    icon: <AlertTriangle className="h-4 w-4" />,
    label: "Light",
  },
  thin: {
    badge: "bg-rose-500/10 text-rose-600 dark:text-rose-300 border border-rose-500/20",
    icon: <XCircle className="h-4 w-4" />,
    label: "Thin",
  },
  not_tracked: {
    badge: "bg-text-primary/[0.06] text-text-muted border border-surface-border/12",
    icon: <HelpCircle className="h-4 w-4" />,
    label: "Not tracked",
  },
};

const PLACEHOLDER = "RELIANCE\nInfosys\nTata Motors\nPunjab & Sind Bank\n...";

export function PortfolioConfidenceForm() {
  const [raw, setRaw] = useState("");
  const [data, setData] = useState<ConfidenceResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const holdings = raw
      .split(/[\n,]/)
      .map(s => s.trim())
      .filter(Boolean);
    if (holdings.length === 0) return;

    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API}/api/tools/portfolio-confidence`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ holdings }),
      });
      if (!res.ok) throw new Error(`Request failed: ${res.status}`);
      const json: ConfidenceResponse = await res.json();
      setData(json);
    } catch {
      setError("Couldn't check your holdings right now — please try again in a moment.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <form onSubmit={handleSubmit} className="rounded-[20px] border border-surface-border/10 bg-surface-card p-5">
        <label htmlFor="holdings" className="mb-2 block text-[11px] font-bold uppercase tracking-wide text-text-muted">
          Your holdings — one per line, ticker or company name
        </label>
        <textarea
          id="holdings"
          value={raw}
          onChange={e => setRaw(e.target.value)}
          placeholder={PLACEHOLDER}
          rows={6}
          className="w-full resize-y rounded-[14px] border border-surface-border/12 bg-text-primary/[0.02] p-3 text-[13px] text-text-primary placeholder:text-text-muted focus:border-sky-500/40 focus:outline-none"
        />
        <div className="mt-3 flex items-center justify-between gap-3">
          <p className="text-[11px] text-text-muted">Up to 30 holdings at a time.</p>
          <button
            type="submit"
            disabled={loading || raw.trim().length === 0}
            className="flex items-center gap-2 rounded-[12px] bg-sky-500 px-4 py-2 text-[13px] font-semibold text-white transition hover:bg-sky-600 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {loading && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
            {loading ? "Checking…" : "Check my holdings"}
          </button>
        </div>
      </form>

      {error && (
        <p className="mt-4 rounded-[12px] border border-rose-500/20 bg-rose-500/[0.06] px-4 py-3 text-[12.5px] text-rose-600 dark:text-rose-300">
          {error}
        </p>
      )}

      {data && (
        <div className="mt-6 space-y-4">
          <div className="flex flex-wrap gap-2">
            {(["strong", "light", "thin", "not_tracked"] as const).map(level => (
              <span key={level} className={`rounded-full px-3 py-1 text-[11px] font-semibold ${LEVEL_STYLE[level].badge}`}>
                {data.summary[level]} {LEVEL_STYLE[level].label}
              </span>
            ))}
          </div>

          <div className="space-y-2.5">
            {data.holdings.map((h, i) => {
              const style = LEVEL_STYLE[h.level];
              const showBridge = h.level === "thin" || h.level === "not_tracked";
              return (
                <div key={i} className="rounded-[16px] border border-surface-border/10 bg-surface-card p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span className={`flex items-center gap-1 rounded-full px-2 py-0.5 text-[10.5px] font-bold ${style.badge}`}>
                        {style.icon} {style.label}
                      </span>
                      <p className="text-[13px] font-semibold text-text-primary">
                        {h.name ?? h.input}
                        {h.symbol && <span className="ml-1.5 text-[11px] font-normal text-text-muted">{h.symbol}</span>}
                      </p>
                    </div>
                    {h.sector && <span className="text-[10.5px] text-text-muted">{h.sector}</span>}
                  </div>
                  <p className="mt-1.5 text-[12px] leading-relaxed text-text-secondary">{h.message}</p>

                  {h.suggestions.length > 0 && (
                    <p className="mt-1.5 text-[11.5px] text-text-muted">
                      Did you mean:{" "}
                      {h.suggestions.map((s, si) => (
                        <span key={s.symbol}>
                          {si > 0 && ", "}
                          <span className="font-semibold text-text-secondary">{s.name} ({s.symbol})</span>
                        </span>
                      ))}
                      ?
                    </p>
                  )}

                  {showBridge && (
                    <Link
                      href={`/ai-search?q=${encodeURIComponent(h.ai_search_query)}`}
                      className="mt-2.5 inline-flex items-center gap-1.5 rounded-[10px] border border-violet-500/20 bg-violet-500/[0.06] px-3 py-1.5 text-[11.5px] font-semibold text-violet-600 transition hover:bg-violet-500/10 dark:text-violet-300"
                    >
                      <Sparkles className="h-3 w-3" /> Ask AI about this
                    </Link>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
