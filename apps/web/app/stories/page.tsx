import { fetchAPI } from "@/lib/api";

interface Story {
  id: string;
  title: string;
  description: string;
  theme: string;
  image: string;
}

async function getStories() {
  try { return await fetchAPI<Story[]>("/api/stories"); }
  catch { return [] as Story[]; }
}

const THEME_COLORS: Record<string, string> = {
  "Macro + Government": "border-violet-500/30 bg-violet-500/10 text-violet-300",
  "Technology":          "border-sky-500/30 bg-sky-500/10 text-sky-300",
  "Consumer + Energy":   "border-amber-500/30 bg-amber-500/10 text-amber-300",
  "Defence":             "border-emerald-500/30 bg-emerald-500/10 text-emerald-300",
};

const GRADIENT_OVERLAYS = [
  "from-sky-900/80 via-sky-900/20",
  "from-violet-900/80 via-violet-900/20",
  "from-emerald-900/80 via-emerald-900/20",
  "from-amber-900/80 via-amber-900/20",
];

export default async function StoriesPage() {
  const stories = await getStories();
  const featured = stories[0];
  const rest = stories.slice(1);

  return (
    <main className="min-w-0 space-y-6 pb-10">
      <div>
        <p className="text-sm uppercase tracking-[0.24em] text-sky-300">Intelligence</p>
        <h1 className="mt-2 text-4xl font-semibold tracking-tight text-white">Market Stories</h1>
        <p className="mt-1 text-sm text-slate-400">Deep-dive narratives on the macro themes shaping Indian markets.</p>
      </div>

      {/* Featured story */}
      {featured && (
        <div className="group relative overflow-hidden rounded-[24px] border border-white/10 shadow-glow">
          {featured.image && (
            <div
              className="absolute inset-0 bg-cover bg-center transition duration-700 group-hover:scale-105"
              style={{ backgroundImage: `url(${featured.image})` }}
            />
          )}
          <div className={`absolute inset-0 bg-gradient-to-t ${GRADIENT_OVERLAYS[0]} to-transparent`} />
          <div className="relative flex min-h-[280px] flex-col justify-end p-7">
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-full border border-sky-500/30 bg-sky-500/10 px-3 py-0.5 text-xs font-medium text-sky-300">
                Featured Story
              </span>
              <span className={`rounded-full border px-3 py-0.5 text-xs font-medium ${THEME_COLORS[featured.theme] ?? "border-white/20 bg-white/10 text-white"}`}>
                {featured.theme}
              </span>
            </div>
            <h2 className="mt-3 text-2xl font-bold text-white leading-tight">{featured.title}</h2>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-300">{featured.description}</p>
          </div>
        </div>
      )}

      {/* Rest of stories */}
      {rest.length > 0 && (
        <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
          {rest.map((s, i) => (
            <div key={s.id}
              className="group relative overflow-hidden rounded-[20px] border border-white/10 shadow-glow transition hover:-translate-y-0.5 hover:border-white/20">
              {s.image && (
                <div
                  className="h-48 w-full bg-cover bg-center transition duration-700 group-hover:scale-105"
                  style={{ backgroundImage: `url(${s.image})` }}
                />
              )}
              {!s.image && (
                <div className="h-48 w-full bg-gradient-to-br from-sky-500/10 to-violet-500/10" />
              )}
              <div className={`absolute left-0 right-0 top-0 h-48 bg-gradient-to-t ${GRADIENT_OVERLAYS[(i + 1) % GRADIENT_OVERLAYS.length]} to-transparent opacity-60`} />

              <div className="p-5">
                <span className={`rounded-full border px-2.5 py-0.5 text-[11px] font-medium ${THEME_COLORS[s.theme] ?? "border-white/10 bg-white/5 text-slate-300"}`}>
                  {s.theme}
                </span>
                <h3 className="mt-3 text-base font-bold text-white leading-snug group-hover:text-sky-300 transition">{s.title}</h3>
                <p className="mt-2 text-sm leading-5 text-slate-400 line-clamp-2">{s.description}</p>
                <div className="mt-4 flex items-center gap-1 text-[11px] text-sky-400 group-hover:text-sky-300">
                  <span>Read story</span>
                  <span>→</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {stories.length === 0 && (
        <div className="flex items-center justify-center rounded-[20px] border border-white/10 bg-white/[0.03] py-20">
          <p className="text-slate-500">Start the backend to load stories.</p>
        </div>
      )}
    </main>
  );
}
