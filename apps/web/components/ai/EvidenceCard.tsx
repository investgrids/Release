import Link from "next/link";
import {
  Landmark, FileText, TrendingUp, BarChart2,
  Newspaper, History, Building2, Globe,
} from "lucide-react";

export type EvidenceType =
  | "government"
  | "filing"
  | "earnings"
  | "indicator"
  | "news"
  | "historical"
  | "company"
  | "global";

const EVIDENCE_CONFIG: Record<EvidenceType, { label: string; icon: typeof Landmark; cls: string }> = {
  government: { label: "Government Announcement", icon: Landmark,    cls: "border-violet-500/20 bg-violet-500/[0.06] text-violet-400" },
  filing:     { label: "Corporate Filing",         icon: FileText,    cls: "border-sky-500/20 bg-sky-500/[0.06] text-sky-400" },
  earnings:   { label: "Company Earnings",          icon: TrendingUp,  cls: "border-emerald-500/20 bg-emerald-500/[0.06] text-emerald-400" },
  indicator:  { label: "Economic Indicator",        icon: BarChart2,   cls: "border-amber-500/20 bg-amber-500/[0.06] text-amber-400" },
  news:       { label: "Breaking News",             icon: Newspaper,   cls: "border-rose-500/20 bg-rose-500/[0.06] text-rose-400" },
  historical: { label: "Historical Pattern",        icon: History,     cls: "border-slate-500/20 bg-slate-500/[0.06] text-slate-400" },
  company:    { label: "Company Report",            icon: Building2,   cls: "border-teal-500/20 bg-teal-500/[0.06] text-teal-400" },
  global:     { label: "Global Event",              icon: Globe,       cls: "border-indigo-500/20 bg-indigo-500/[0.06] text-indigo-400" },
};

export interface EvidenceCardProps {
  type: EvidenceType;
  title: string;
  summary?: string;
  href?: string;
  date?: string;
}

export function EvidenceCard({ type, title, summary, href, date }: EvidenceCardProps) {
  const config = EVIDENCE_CONFIG[type] ?? EVIDENCE_CONFIG.news;
  const Icon = config.icon;

  const inner = (
    <div
      className={`flex items-start gap-2.5 rounded-[12px] border p-3 transition ${config.cls} ${
        href ? "cursor-pointer hover:opacity-80" : ""
      }`}
    >
      <Icon className="h-3.5 w-3.5 shrink-0 mt-0.5" aria-hidden="true" />
      <div className="min-w-0 flex-1">
        <div className="flex items-start justify-between gap-2">
          <p className="text-[11px] font-semibold text-white leading-snug line-clamp-2">{title}</p>
          {date && <span className="text-[10px] text-slate-500 shrink-0">{date}</span>}
        </div>
        {summary && (
          <p className="mt-0.5 text-[10px] text-slate-400 line-clamp-2">{summary}</p>
        )}
        <span className="mt-1 inline-block text-[9px] font-medium uppercase tracking-wider opacity-70">
          {config.label}
        </span>
      </div>
    </div>
  );

  if (href) {
    return (
      <Link href={href as any} target="_blank" rel="noopener noreferrer" aria-label={`Evidence: ${title}`}>
        {inner}
      </Link>
    );
  }

  return inner;
}

interface EvidenceGridProps {
  items: EvidenceCardProps[];
  maxVisible?: number;
}

export function EvidenceGrid({ items, maxVisible = 3 }: EvidenceGridProps) {
  const visible = items.slice(0, maxVisible);
  const remaining = items.length - maxVisible;

  return (
    <div className="space-y-1.5">
      <p className="text-[10px] font-bold uppercase tracking-[0.12em] text-slate-500">
        Supporting Evidence
      </p>
      <div className="grid gap-1.5 sm:grid-cols-2">
        {visible.map((item, i) => (
          <EvidenceCard key={i} {...item} />
        ))}
      </div>
      {remaining > 0 && (
        <p className="text-[11px] text-slate-500">+{remaining} more sources</p>
      )}
    </div>
  );
}
