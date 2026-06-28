"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

const API = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

interface Story {
  id: string;
  title: string;
  summary: string;
  category: string;
  read_time?: number;
  image_url?: string;
  published_at?: string;
}

const TABS = ["All Stories", "My Feed", "Following", "Bookmarks"];

const STATIC_STORIES: Story[] = [
  { id: "s1", title: "The India Infrastructure Supercycle: A $1.4 Trillion Opportunity", summary: "India's infrastructure spending is entering a multi-decade supercycle driven by government initiatives and private sector participation.", category: "Infrastructure", read_time: 15, published_at: "2 hours ago" },
  { id: "s2", title: "Defence Manufacturing Boom in India", summary: "India is emerging as a major defence manufacturing hub with record exports.", category: "Defence", read_time: 8, published_at: "4 hours ago" },
  { id: "s3", title: "EV Transition: Winners & Losers", summary: "The electric vehicle shift is reshaping the Indian auto industry landscape.", category: "Automotive", read_time: 12, published_at: "6 hours ago" },
  { id: "s4", title: "AI & Automation: Impact on Indian IT", summary: "How artificial intelligence is transforming India's $250 billion IT sector.", category: "Technology", read_time: 10, published_at: "8 hours ago" },
  { id: "s5", title: "PLI Schemes Driving Manufacturing", summary: "Production-linked incentive schemes are transforming India's manufacturing landscape.", category: "Manufacturing", read_time: 9, published_at: "12 hours ago" },
  { id: "s6", title: "Semiconductor Mission: India's Chip Revolution", summary: "India's ambitious push to build a domestic semiconductor industry.", category: "Technology", read_time: 13, published_at: "1 day ago" },
  { id: "s7", title: "Green Hydrogen: The Next Energy Revolution", summary: "India bets big on green hydrogen as the future of clean energy transition.", category: "Energy", read_time: 11, published_at: "1 day ago" },
  { id: "s8", title: "Renewable Energy Growth Story", summary: "India's renewable energy capacity addition hits record levels in FY24.", category: "Energy", read_time: 7, published_at: "2 days ago" },
];

const CAT_COLORS: Record<string, string> = {
  "Infrastructure": "bg-violet-500/20 text-violet-300 border-violet-500/25",
  "Defence":        "bg-sky-500/20 text-sky-300 border-sky-500/25",
  "Automotive":     "bg-emerald-500/20 text-emerald-300 border-emerald-500/25",
  "Technology":     "bg-blue-500/20 text-blue-300 border-blue-500/25",
  "Manufacturing":  "bg-amber-500/20 text-amber-300 border-amber-500/25",
  "Energy":         "bg-teal-500/20 text-teal-300 border-teal-500/25",
  "Finance":        "bg-indigo-500/20 text-indigo-300 border-indigo-500/25",
};

const CARD_GRADS = [
  "from-violet-900/30 to-indigo-900/10",
  "from-sky-900/30 to-blue-900/10",
  "from-emerald-900/30 to-teal-900/10",
  "from-amber-900/25 to-orange-900/10",
  "from-rose-900/25 to-pink-900/10",
  "from-teal-900/30 to-cyan-900/10",
];

export default function StoriesPage() {
  const [stories, setStories] = useState<Story[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("All Stories");

  useEffect(() => {
    fetch(`${API}/api/stories`)
      .then(r => r.ok ? r.json() : [])
      .then(d => setStories(Array.isArray(d) && d.length > 0 ? d : STATIC_STORIES))
      .catch(() => setStories(STATIC_STORIES))
      .finally(() => setLoading(false));
  }, []);

  const displayStories = loading ? STATIC_STORIES : stories;
  const featured = displayStories[0];
  const popular  = displayStories.slice(1, 6);
  const grid     = displayStories.slice(6);

  const catCls = (cat: string) => CAT_COLORS[cat] ?? "bg-slate-700/40 text-slate-300 border-slate-500/25";

  return (
    <main className="min-w-0 pb-10">
      {/* Header */}
      <div className="mb-6 flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Market Stories</h1>
          <p className="mt-1 text-sm text-slate-400">In-depth analysis of market moving themes</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="mb-6 flex gap-1 rounded-xl border border-white/10 bg-white/[0.02] p-1 w-fit">
        {TABS.map(t => (
          <button key={t} onClick={() => setActiveTab(t)}
            className={`rounded-lg px-4 py-1.5 text-[13px] font-medium transition ${
              activeTab === t ? "bg-white/10 text-white" : "text-slate-500 hover:text-slate-300"
            }`}>
            {t}
          </button>
        ))}
      </div>

      {/* Featured + Popular row */}
      {featured && (
        <div className="mb-6 grid grid-cols-[1fr_320px] gap-5">
          {/* Featured story */}
          <div className="relative overflow-hidden rounded-[24px] border border-violet-500/20 bg-gradient-to-br from-violet-900/40 to-indigo-900/20 p-6">
            <div className="absolute inset-0 bg-gradient-to-br from-violet-900/30 via-transparent to-transparent"/>
            <div className="relative">
              <div className="mb-3 flex items-center gap-2">
                <span className="rounded-full border border-violet-500/30 bg-violet-500/15 px-2.5 py-0.5 text-[11px] font-medium text-violet-300">
                  Featured
                </span>
                <span className="rounded-full border border-white/10 bg-white/5 px-2.5 py-0.5 text-[11px] font-medium text-slate-400">
                  Premium
                </span>
                <span className={`ml-1 rounded-full border px-2.5 py-0.5 text-[11px] font-medium ${catCls(featured.category)}`}>
                  {featured.category}
                </span>
              </div>

              <h2 className="text-2xl font-bold leading-snug text-white">{featured.title}</h2>

              <p className="mt-1 text-[12px] font-medium text-violet-300">
                Premium Story · {featured.read_time ?? 15} min read
              </p>

              <p className="mt-3 text-[14px] leading-6 text-slate-300 line-clamp-3">
                {featured.summary}
              </p>

              <div className="mt-5 flex items-center gap-3">
                <Link href={`/stories`}
                  className="inline-flex items-center gap-1.5 rounded-xl bg-violet-500/20 px-4 py-2 text-sm font-medium text-violet-300 hover:bg-violet-500/30 transition border border-violet-500/25">
                  Read Full Story
                  <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7"/>
                  </svg>
                </Link>
              </div>
            </div>
          </div>

          {/* Popular Stories sidebar */}
          <div className="rounded-[24px] border border-white/10 bg-white/[0.03] p-4 backdrop-blur-xl">
            <h3 className="mb-3 text-[11px] font-semibold uppercase tracking-wider text-slate-400">Popular Stories</h3>
            <div className="space-y-3">
              {popular.map((s, i) => (
                <Link key={s.id} href={`/stories`}
                  className="group flex items-start gap-2.5 rounded-xl p-2 hover:bg-white/[0.03] transition">
                  <span className="mt-0.5 shrink-0 text-xl font-black text-slate-700 leading-none w-6">
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  <div className="min-w-0">
                    <p className="text-[12px] font-medium text-white line-clamp-2 leading-4 group-hover:text-sky-300 transition">
                      {s.title}
                    </p>
                    <p className="mt-1 text-[10px] text-slate-500">
                      {s.category} · {s.read_time ?? 8} min read
                    </p>
                  </div>
                </Link>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Story card grid */}
      {(grid.length > 0 || displayStories.length > 1) && (
        <>
          <p className="mb-4 text-[10px] uppercase tracking-widest text-slate-500">More Stories</p>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {(grid.length > 0 ? grid : displayStories.slice(1, 7)).map((s, i) => (
              <Link key={s.id} href={`/stories`}
                className="group rounded-[20px] border border-white/10 bg-white/[0.03] overflow-hidden backdrop-blur-xl hover:border-white/20 hover:-translate-y-0.5 transition">
                {/* Image placeholder */}
                <div className={`h-36 w-full bg-gradient-to-br ${CARD_GRADS[i % CARD_GRADS.length]} border-b border-white/5`}>
                  <div className="h-full w-full bg-gradient-to-br from-white/[0.03] to-transparent"/>
                </div>
                {/* Content */}
                <div className="p-4">
                  <div className="mb-2 flex items-center gap-1.5">
                    <span className={`rounded-full border px-2 py-0.5 text-[10px] font-medium ${catCls(s.category)}`}>
                      {s.category}
                    </span>
                    <span className="text-[10px] text-slate-600">{s.published_at}</span>
                  </div>
                  <h3 className="text-[13px] font-bold leading-snug text-white line-clamp-2 group-hover:text-sky-200 transition">
                    {s.title}
                  </h3>
                  <p className="mt-1.5 text-[12px] leading-4 text-slate-400 line-clamp-2">{s.summary}</p>
                  <p className="mt-2.5 text-[11px] text-slate-500">{s.read_time ?? 8} min read</p>
                </div>
              </Link>
            ))}
          </div>
        </>
      )}
    </main>
  );
}
