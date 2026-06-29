interface DashboardHeroProps {
  date: string;
  status: "Market Open" | "Market Closed";
  greeting: string;
}

export function DashboardHero({ date, status, greeting }: DashboardHeroProps) {
  const open = status === "Market Open";
  return (
    <div className="flex items-start justify-between">
      <div>
        <h1 className="text-2xl font-semibold text-white">{greeting}, Intelligence Seeker 👋</h1>
        <p className="mt-1 text-sm text-slate-400">Here&apos;s what&apos;s shaping the markets today.</p>
      </div>
      <div className="text-right shrink-0">
        <p className="text-sm text-slate-400">{date}</p>
        <p className={`mt-1 flex items-center justify-end gap-1.5 text-sm font-medium ${open ? "text-emerald-400" : "text-rose-400"}`}>
          <span className={`h-2 w-2 rounded-full inline-block ${open ? "bg-emerald-400" : "bg-rose-400"}`} />
          {status}
        </p>
      </div>
    </div>
  );
}
