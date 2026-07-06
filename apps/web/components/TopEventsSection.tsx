import Link from "next/link";
import { ClipboardList } from "lucide-react";

interface EventRow {
  id: string;
  title: string;
  score: number;
  tags: string[];
  companies: string[];
  sector: string;
  time: string;
}

function ScoreBadge({ score }: { score: number }) {
  const color =
    score >= 80 ? "text-rose-300 bg-rose-500/15 ring-rose-500/30" :
    score >= 65 ? "text-amber-300 bg-amber-500/15 ring-amber-500/30" :
    score >= 45 ? "text-sky-300 bg-sky-500/15 ring-sky-500/30" :
    "text-slate-400 bg-white/5 ring-white/10";
  const label =
    score >= 80 ? "Very High" :
    score >= 65 ? "High" :
    score >= 45 ? "Medium" : "Low";
  return (
    <div className={`flex flex-col items-center justify-center w-12 h-12 rounded-2xl ring-1 shrink-0 ${color}`}>
      <span className="text-[14px] font-black leading-none">{score}</span>
      <span className="text-[8px] font-medium leading-none mt-0.5">{label}</span>
    </div>
  );
}

function CompanyAvatars({ companies }: { companies: string[] }) {
  const shown = companies.slice(0, 4);
  const extra = companies.length - 4;
  const colors = ["bg-sky-500/20 text-sky-300", "bg-violet-500/20 text-violet-300", "bg-emerald-500/20 text-emerald-300", "bg-amber-500/20 text-amber-300"];
  return (
    <div className="flex items-center gap-1">
      {shown.map((c, i) => (
        <div key={`${i}-${c}`} className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-[8px] font-bold ${colors[i % colors.length]}`}>
          {String(c).slice(0, 3)}
        </div>
      ))}
      {extra > 0 && (
        <span className="ml-1 text-[10px] text-slate-500">+{extra}</span>
      )}
    </div>
  );
}

export function TopEventsSection({ events }: { events: EventRow[] }) {
  return (
    <div className="rounded-xl border border-white/[0.07] bg-[#0a0d16] p-5">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="flex h-6 w-6 items-center justify-center rounded-lg bg-rose-500/15">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-3.5 w-3.5 text-rose-400">
              <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/>
            </svg>
          </div>
          <h2 className="text-[14px] font-bold text-white">Top Events Today</h2>
        </div>
        <Link href="/events" className="text-[11px] text-sky-400 hover:text-sky-300 transition">View All →</Link>
      </div>

      {/* Table header */}
      <div className="mb-2 grid grid-cols-[1fr_60px_140px_90px_60px] gap-3 border-b border-white/[0.06] pb-2 text-[10px] font-semibold uppercase tracking-wider text-slate-600">
        <span>Event</span>
        <span>Impact</span>
        <span>Companies</span>
        <span>Sector</span>
        <span className="text-right">Time</span>
      </div>

      <div className="space-y-1.5">
        {events.length === 0 && (
          <div className="flex flex-col items-center justify-center py-10 text-center">
            <ClipboardList className="h-8 w-8 text-slate-500 mb-2" />
            <p className="text-[12px] text-slate-500">No events yet. Check back soon.</p>
          </div>
        )}
        {events.slice(0, 5).map((e) => (
          <Link
            key={e.id}
            href={`/events/${e.id}`}
            className="grid grid-cols-[1fr_60px_140px_90px_60px] items-center gap-3 rounded-2xl border border-white/[0.04] bg-white/[0.02] px-3 py-2.5 hover:border-sky-500/15 hover:bg-white/[0.04] transition"
          >
            {/* Title + tags */}
            <div className="min-w-0">
              <p className="text-[12px] font-semibold text-white line-clamp-1 leading-snug">{e.title}</p>
              <div className="mt-1 flex gap-1">
                {e.tags.slice(0, 2).map(t => (
                  <span key={t} className="rounded-full border border-white/[0.07] bg-white/[0.03] px-1.5 py-0.5 text-[9px] text-slate-500">{t}</span>
                ))}
              </div>
            </div>
            {/* Score */}
            <ScoreBadge score={e.score}/>
            {/* Company avatars */}
            <CompanyAvatars companies={e.companies}/>
            {/* Sector */}
            <span className="rounded-full bg-white/[0.04] px-2 py-0.5 text-center text-[10px] text-slate-400 truncate">{e.sector}</span>
            {/* Time */}
            <span className="text-right text-[11px] font-medium text-slate-500">{e.time}</span>
          </Link>
        ))}
      </div>
    </div>
  );
}
