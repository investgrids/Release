import { fetchAPI } from "@/lib/api";

interface Event {
  id: string; title: string; summary: string;
  impact_score: number; confidence: number;
  sectors: string[]; companies: { symbol: string; name: string; impact: string }[];
  category: string; date: string;
}

async function getEvents() {
  try { return await fetchAPI<Event[]>("/api/events"); }
  catch { return [] as Event[]; }
}

const IMPACT_COLOR: Record<string, string> = {
  Positive: "text-emerald-300 bg-emerald-500/10 border-emerald-500/20",
  Negative: "text-rose-300 bg-rose-500/10 border-rose-500/20",
  Neutral:  "text-slate-300 bg-white/5 border-white/10",
};

const CAT_COLORS: Record<string, string> = {
  Government: "border-violet-500/20 bg-violet-500/10 text-violet-300",
  Policy:     "border-sky-500/20 bg-sky-500/10 text-sky-300",
  Macro:      "border-amber-500/20 bg-amber-500/10 text-amber-300",
  Global:     "border-slate-500/20 bg-slate-500/10 text-slate-300",
  RBI:        "border-indigo-500/20 bg-indigo-500/10 text-indigo-300",
};

export default async function PoliciesPage() {
  const allEvents = await getEvents();
  // Show Government + Policy category events as "policies"
  const policy = allEvents.filter((e) => ["Government", "Policy", "RBI", "Macro"].includes(e.category));

  return (
    <main className="min-w-0 space-y-6 pb-10">
      <div>
        <p className="text-sm uppercase tracking-[0.24em] text-sky-300">Intelligence</p>
        <h1 className="mt-2 text-4xl font-semibold tracking-tight text-white">Government Policies</h1>
        <p className="mt-1 text-sm text-slate-400">Policy announcements, budget decisions, and regulatory changes with market impact.</p>
      </div>

      {/* Category filter chips */}
      <div className="flex flex-wrap gap-2">
        {["All", "Government", "Policy", "RBI", "Macro"].map((cat) => (
          <span key={cat}
            className={`rounded-full border px-3 py-1 text-xs font-medium ${cat === "All" ? "border-sky-500/30 bg-sky-500/10 text-sky-300" : (CAT_COLORS[cat] ?? "border-white/10 bg-white/5 text-slate-400")}`}>
            {cat}
          </span>
        ))}
      </div>

      {/* Events list */}
      {policy.length > 0 ? (
        <div className="space-y-4">
          {policy.map((e) => (
            <article key={e.id}
              className="rounded-[20px] border border-white/10 bg-white/[0.03] p-5 shadow-glow backdrop-blur-xl transition hover:-translate-y-0.5 hover:border-white/20">
              {/* Top row */}
              <div className="flex flex-wrap items-center gap-2">
                <span className={`rounded-full border px-2.5 py-0.5 text-[11px] font-medium ${CAT_COLORS[e.category] ?? "border-white/10 bg-white/5 text-slate-300"}`}>
                  {e.category}
                </span>
                <span className="rounded-full border border-white/10 bg-white/5 px-2.5 py-0.5 text-[11px] text-slate-400">
                  Impact {e.impact_score.toFixed(1)}
                </span>
                <span className="text-[11px] text-slate-600">
                  {e.date ? new Date(e.date).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" }) : ""}
                </span>
              </div>

              <h3 className="mt-3 text-base font-semibold leading-snug text-white">{e.title}</h3>
              <p className="mt-2 text-sm leading-6 text-slate-400">{e.summary}</p>

              {/* Companies affected */}
              {e.companies?.length > 0 && (
                <div className="mt-4 flex flex-wrap gap-2">
                  <p className="w-full text-[10px] uppercase tracking-widest text-slate-500">Companies Affected</p>
                  {e.companies.map((c) => (
                    <span key={c.symbol}
                      className={`rounded-full border px-2.5 py-1 text-[11px] ${IMPACT_COLOR[c.impact] ?? IMPACT_COLOR["Neutral"]}`}>
                      {c.name} · {c.impact}
                    </span>
                  ))}
                </div>
              )}

              {/* Sectors */}
              {e.sectors?.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {e.sectors.map((s) => (
                    <span key={s} className="rounded-full border border-white/8 bg-white/5 px-2 py-0.5 text-[10px] text-slate-500">{s}</span>
                  ))}
                </div>
              )}
            </article>
          ))}
        </div>
      ) : (
        <div className="flex items-center justify-center rounded-[20px] border border-white/10 bg-white/[0.03] py-20">
          <p className="text-slate-500">Start the backend to load policy events.</p>
        </div>
      )}

      <div className="rounded-[20px] border border-amber-500/20 bg-amber-500/[0.04] p-4">
        <p className="text-xs text-amber-300">
          📋 <strong>Live Policy Feed:</strong> Real-time government notifications require{" "}
          <strong>SEBI Circular API</strong>, <strong>RBI Press Release RSS</strong>, and{" "}
          <strong>PIB (Press Information Bureau) API</strong>.
        </p>
      </div>
    </main>
  );
}
