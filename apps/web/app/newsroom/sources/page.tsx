import type { Metadata } from "next";
import { Clock, ExternalLink } from "lucide-react";
import { API_BASE_URL as API } from "@/lib/api";
import { cleanText } from "@/lib/text";

export const metadata: Metadata = {
  title: "Live Sources | AI Newsroom",
  description: "Raw wire headlines, refreshed continuously — the real-time evidence AI Newsroom articles are synthesized from.",
  alternates: { canonical: "/newsroom/sources" },
};

interface NewsCard {
  id: string;
  headline: string;
  summary: string;
  source: string;
  published_at: string;
  url?: string;
  sectors: string[];
}

async function getLiveSources(): Promise<NewsCard[]> {
  try {
    const res = await fetch(`${API}/api/news/`, { cache: "no-store" });
    if (!res.ok) return [];
    return res.json();
  } catch {
    return [];
  }
}

export default async function LiveSourcesPage() {
  const news = await getLiveSources();

  return (
    <div className="mx-auto max-w-4xl px-4 py-8 sm:px-6">
      <div className="mb-8">
        <p className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">
          <Clock className="h-3 w-3 text-slate-400" /> AI Newsroom
        </p>
        <h1 className="mt-2 text-[26px] font-black leading-tight text-white md:text-[30px]">
          Live Sources
        </h1>
        <p className="mt-2 max-w-2xl text-[13.5px] leading-6 text-slate-400">
          Raw wire headlines, refreshed continuously — the real-time evidence AI Newsroom articles
          are synthesized from. Unprocessed, not AI-written.
        </p>
      </div>

      {news.length === 0 ? (
        <p className="rounded-xl border border-white/[0.07] bg-white/[0.03] p-8 text-center text-[13px] text-slate-500">
          No live sources fetched right now — check back soon.
        </p>
      ) : (
        // Attribution, not navigation: the row itself isn't a link — only
        // the small "View original" text is, so leaving MarketRipple is an
        // explicit, secondary choice rather than what clicking the headline
        // does by default.
        <ul className="divide-y divide-white/[0.06] rounded-xl border border-white/[0.07] bg-white/[0.02]">
          {news.map((n) => (
            <li key={n.id} className="flex items-start justify-between gap-4 px-5 py-3.5">
              <div className="min-w-0">
                <p className="text-[13.5px] font-medium leading-5 text-slate-200">{cleanText(n.headline)}</p>
                {n.summary && (
                  <p className="mt-1 line-clamp-1 text-[12px] leading-5 text-slate-500">{cleanText(n.summary)}</p>
                )}
                {n.sectors?.length > 0 && (
                  <div className="mt-1.5 flex flex-wrap gap-1">
                    {n.sectors.slice(0, 3).map((s, i) => (
                      <span key={i} className="rounded-full border border-white/10 bg-white/5 px-1.5 py-0.5 text-[10px] text-slate-500">
                        {s}
                      </span>
                    ))}
                  </div>
                )}
                {n.url && (
                  <a
                    href={n.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mt-1.5 inline-flex items-center gap-1 text-[10.5px] font-medium text-slate-500 transition hover:text-sky-400"
                  >
                    View original <ExternalLink className="h-2.5 w-2.5" />
                  </a>
                )}
              </div>
              <span className="shrink-0 text-[11px] text-slate-600">
                {n.source} · {n.published_at}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
