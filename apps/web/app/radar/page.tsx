import { fetchAPI } from "@/lib/api";

interface Radar {
  id: string;
  theme: string;
  score: number;
  reason: string;
  confidence: number;
  beneficiaries: string[];
}

async function getRadar() {
  try { return await fetchAPI<Radar[]>("/api/radar"); }
  catch { return [] as Radar[]; }
}

const TIER_CONFIG = [
  { min: 90, label: "Strong Buy", color: "text-emerald-300", bg: "bg-emerald-500/10 border-emerald-500/30", bar: "from-emerald-500 to-teal-400" },
  { min: 80, label: "Accumulate", color: "text-sky-300",     bg: "bg-sky-500/10 border-sky-500/30",         bar: "from-sky-500 to-cyan-400"    },
  { min: 70, label: "Watch",      color: "text-amber-300",   bg: "bg-amber-500/10 border-amber-500/30",     bar: "from-amber-500 to-yellow-400"},
  { min: 0,  label: "Monitor",    color: "text-slate-300",   bg: "bg-white/5 border-white/10",              bar: "from-slate-500 to-slate-400" },
];

function tier(score: number) {
  return TIER_CONFIG.find((t) => score >= t.min) ?? TIER_CONFIG[TIER_CONFIG.length - 1];
}

const CATEGORY_ICONS: Record<string, string> = {
  "Defence":        "🛡",
  "Green Energy":   "🌱",
  "Infrastructure": "🏗",
  "Technology":     "💡",
  "Digital":        "📡",
  "Railway":        "🚆",
  "AI":             "🤖",
};

function guessIcon(theme: string) {
  for (const [key, icon] of Object.entries(CATEGORY_ICONS)) {
    if (theme.toLowerCase().includes(key.toLowerCase())) return icon;
  }
  return "📡";
}

export default async function RadarPage() {
  const themes = await getRadar();
  const sorted = [...themes].sort((a, b) => b.score - a.score);

  return (
    <main className="min-w-0 space-y-6 pb-10">
      <div>
        <p className="text-sm uppercase tracking-[0.24em] text-sky-300">Intelligence</p>
        <h1 className="mt-2 text-4xl font-semibold tracking-tight text-white">Opportunity Radar</h1>
        <p className="mt-1 text-sm text-slate-400">AI-ranked investment themes with beneficiary mapping and confidence scores.</p>
      </div>

      {/* Score legend */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {TIER_CONFIG.map((t) => (
          <div key={t.label} className={`rounded-2xl border p-3 ${t.bg}`}>
            <p className={`text-xs font-semibold ${t.color}`}>{t.label}</p>
            <p className="mt-0.5 text-[10px] text-slate-500">Score ≥ {t.min}</p>
          </div>
        ))}
      </div>

      {/* Ranked opportunities */}
      {sorted.length > 0 ? (
        <div className="space-y-4">
          {sorted.map((item, idx) => {
            const t = tier(item.score);
            const pct = Math.round(item.confidence * 100);
            return (
              <article key={item.id}
                className="rounded-[20px] border border-white/10 bg-white/[0.03] p-5 shadow-glow backdrop-blur-xl transition hover:-translate-y-0.5 hover:border-white/20">
                <div className="flex flex-wrap items-start gap-4">
                  {/* Rank bubble */}
                  <div className="flex h-12 w-12 shrink-0 flex-col items-center justify-center rounded-2xl bg-white/5 text-center">
                    <span className="text-[10px] text-slate-500">#</span>
                    <span className="text-lg font-black text-white leading-none">{idx + 1}</span>
                  </div>

                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-xl">{guessIcon(item.theme)}</span>
                      <span className={`rounded-full border px-2.5 py-0.5 text-[11px] font-medium ${t.bg} ${t.color}`}>
                        {t.label}
                      </span>
                    </div>
                    <h3 className="mt-2 text-lg font-bold text-white">{item.theme}</h3>
                    <p className="mt-1.5 text-sm leading-6 text-slate-400">{item.reason}</p>

                    {/* Beneficiaries */}
                    {item.beneficiaries?.length > 0 && (
                      <div className="mt-3">
                        <p className="mb-2 text-[10px] uppercase tracking-widest text-slate-500">Key Beneficiaries</p>
                        <div className="flex flex-wrap gap-2">
                          {item.beneficiaries.map((b) => (
                            <span key={b} className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[11px] text-slate-300">{b}</span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Score + confidence */}
                  <div className="flex flex-col items-center gap-1 text-center">
                    <div className={`flex h-14 w-14 items-center justify-center rounded-2xl text-2xl font-black ${t.color} bg-white/5`}>
                      {item.score}
                    </div>
                    <p className="text-[10px] text-slate-500">AI Score</p>
                  </div>
                </div>

                {/* Confidence bar */}
                <div className="mt-4">
                  <div className="mb-1 flex justify-between text-[11px] text-slate-500">
                    <span>AI Confidence</span><span>{pct}%</span>
                  </div>
                  <div className="h-1.5 overflow-hidden rounded-full bg-white/5">
                    <div className={`h-full rounded-full bg-gradient-to-r ${t.bar}`} style={{ width: `${pct}%` }} />
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      ) : (
        <div className="flex items-center justify-center rounded-[20px] border border-white/10 bg-white/[0.03] py-20">
          <p className="text-slate-500">Start the backend to load radar data.</p>
        </div>
      )}
    </main>
  );
}
