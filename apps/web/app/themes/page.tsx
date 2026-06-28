import { fetchAPI } from "@/lib/api";

interface Radar {
  id: string; theme: string; score: number;
  reason: string; confidence: number; beneficiaries: string[];
}

async function getRadar() {
  try { return await fetchAPI<Radar[]>("/api/radar"); }
  catch { return [] as Radar[]; }
}

function scoreGrade(score: number) {
  if (score >= 90) return { label: "Strong Buy", color: "text-emerald-300 bg-emerald-500/10 border-emerald-500/30" };
  if (score >= 80) return { label: "Accumulate",  color: "text-sky-300 bg-sky-500/10 border-sky-500/30" };
  if (score >= 70) return { label: "Watch",       color: "text-amber-300 bg-amber-500/10 border-amber-500/30" };
  return { label: "Monitor", color: "text-slate-300 bg-white/5 border-white/10" };
}

function confidenceBar(c: number) {
  const pct = Math.round(c * 100);
  return (
    <div className="mt-3">
      <div className="mb-1 flex justify-between text-[11px] text-slate-500">
        <span>AI Confidence</span><span>{pct}%</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-white/5">
        <div className="h-full rounded-full bg-gradient-to-r from-sky-500 to-violet-500" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

export default async function ThemesPage() {
  const themes = await getRadar();

  const topTheme = themes[0];

  return (
    <main className="min-w-0 space-y-6 pb-10">
      <div>
        <p className="text-sm uppercase tracking-[0.24em] text-sky-300">Intelligence</p>
        <h1 className="mt-2 text-4xl font-semibold tracking-tight text-white">Top Themes</h1>
        <p className="mt-1 text-sm text-slate-400">AI-ranked investment themes shaping the Indian market right now.</p>
      </div>

      {/* Top theme hero */}
      {topTheme && (
        <div className="rounded-[24px] border border-violet-500/20 bg-violet-500/[0.04] p-6 shadow-glow backdrop-blur-xl">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <span className="rounded-full border border-violet-500/30 bg-violet-500/10 px-3 py-0.5 text-xs font-medium text-violet-300">
                # 1 Theme · Score {topTheme.score}
              </span>
              <h2 className="mt-3 text-2xl font-bold text-white">{topTheme.theme}</h2>
              <p className="mt-2 max-w-xl text-sm leading-6 text-slate-300">{topTheme.reason}</p>
            </div>
            <div className="text-center">
              <div className="flex h-20 w-20 items-center justify-center rounded-2xl bg-violet-500/20 text-3xl font-black text-violet-300">
                {topTheme.score}
              </div>
              <p className="mt-1 text-[11px] text-slate-500">AI Score</p>
            </div>
          </div>
          <div className="mt-5 flex flex-wrap gap-2">
            {topTheme.beneficiaries.map((b) => (
              <span key={b} className="rounded-full border border-violet-500/20 bg-violet-500/10 px-3 py-1 text-xs text-violet-200">{b}</span>
            ))}
          </div>
          {confidenceBar(topTheme.confidence)}
        </div>
      )}

      {/* All themes grid */}
      <div className="grid gap-4 xl:grid-cols-2">
        {themes.map((t, i) => {
          const grade = scoreGrade(t.score);
          return (
            <article key={t.id}
              className="rounded-[20px] border border-white/10 bg-white/[0.03] p-5 shadow-glow backdrop-blur-xl transition hover:-translate-y-0.5 hover:border-white/20">
              <div className="flex items-start justify-between gap-4">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-sky-500/20 to-violet-500/10 text-base font-bold text-slate-300">
                  #{i + 1}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className={`rounded-full border px-2.5 py-0.5 text-[11px] font-medium ${grade.color}`}>{grade.label}</span>
                    <span className="text-[11px] text-slate-500">Score {t.score}</span>
                  </div>
                  <h3 className="mt-2 text-base font-semibold text-white">{t.theme}</h3>
                  <p className="mt-1.5 text-sm leading-5 text-slate-400">{t.reason}</p>
                </div>
              </div>

              {confidenceBar(t.confidence)}

              <div className="mt-4">
                <p className="mb-2 text-[10px] uppercase tracking-widest text-slate-500">Key Beneficiaries</p>
                <div className="flex flex-wrap gap-2">
                  {t.beneficiaries.map((b) => (
                    <span key={b} className="rounded-full border border-white/10 bg-white/5 px-2.5 py-1 text-[11px] text-slate-300">{b}</span>
                  ))}
                </div>
              </div>
            </article>
          );
        })}
      </div>

      {themes.length === 0 && (
        <div className="flex items-center justify-center rounded-[20px] border border-white/10 bg-white/[0.03] py-20">
          <p className="text-slate-500">Start the backend to load theme data.</p>
        </div>
      )}
    </main>
  );
}
