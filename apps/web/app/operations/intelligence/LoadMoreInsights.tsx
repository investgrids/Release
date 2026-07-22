"use client";

import { useState } from "react";
import Link from "next/link";
import { Loader2, ArrowRight } from "lucide-react";
import { API_BASE_URL as API } from "@/lib/api";
import { TYPE_LABEL, fmtRelative, type FeedArticle } from "./shared";

export function LoadMoreInsights({ initialItems, startOffset, total }: { initialItems: FeedArticle[]; startOffset: number; total: number }) {
  const [items, setItems] = useState<FeedArticle[]>(initialItems);
  const [offset, setOffset] = useState(startOffset);
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(startOffset >= total);
  const PAGE = 12;

  async function loadMore() {
    setLoading(true);
    try {
      const r = await fetch(`${API}/api/insights/?limit=${PAGE}&offset=${offset}`);
      if (r.ok) {
        const d = await r.json();
        setItems(prev => [...prev, ...(d.items ?? [])]);
        const nextOffset = offset + PAGE;
        setOffset(nextOffset);
        if (nextOffset >= (d.total ?? total)) setDone(true);
      }
    } catch {} finally {
      setLoading(false);
    }
  }

  return (
    <>
      {items.length > 0 && (
        <div className="mt-5 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {items.map(a => (
            <Link
              key={a.slug}
              href={`/newsroom/article/${a.slug}` as any}
              className="group rounded-2xl border border-white/[0.07] bg-white/[0.02] p-5 transition hover:border-white/20 hover:bg-white/[0.04]"
            >
              <span className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider text-slate-400">
                {TYPE_LABEL[a.article_type] ?? "Intelligence"}
              </span>
              <h3 className="mt-2.5 text-[14px] font-bold leading-snug text-white line-clamp-2 group-hover:text-violet-200 transition">
                {a.headline}
              </h3>
              {(a.key_takeaway || a.executive_summary) && (
                <p className="mt-1.5 line-clamp-2 text-[12px] leading-5 text-slate-500">
                  {a.key_takeaway ?? a.executive_summary}
                </p>
              )}
              <div className="mt-3 flex items-center justify-between text-[10px] text-slate-600">
                <span>{fmtRelative(a.published_at)}</span>
                {a.confidence_score != null && <span className="text-emerald-400 font-semibold">{Math.round(a.confidence_score * 100)}% confidence</span>}
              </div>
            </Link>
          ))}
        </div>
      )}
      {!done && (
        <div className="mt-8 flex justify-center">
          <button
            onClick={loadMore}
            disabled={loading}
            className="flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.04] px-6 py-3 text-[13px] font-semibold text-slate-200 transition hover:border-violet-500/40 hover:bg-white/[0.07] disabled:opacity-50"
          >
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowRight className="h-4 w-4" />}
            {loading ? "Loading…" : "Load more intelligence"}
          </button>
        </div>
      )}
    </>
  );
}
