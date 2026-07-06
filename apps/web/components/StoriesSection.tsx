import Link from "next/link";

interface StoryItem {
  id: string;
  title: string;
  description: string;
  theme: string;
  image: string;
}

interface StoriesSectionProps {
  stories: StoryItem[];
}

export function StoriesSection({ stories }: StoriesSectionProps) {
  return (
    <section className="rounded-[28px] border border-white/10 bg-white/5 p-5 shadow-glow">
      <div className="mb-5 flex items-center justify-between">
        <div>
          <p className="text-sm uppercase tracking-[0.28em] text-slate-400">Stories</p>
          <h2 className="text-2xl font-semibold text-white">Latest narrative highlights</h2>
        </div>
        <button className="rounded-3xl bg-slate-950/80 px-4 py-2 text-sm text-slate-300 transition hover:bg-white/5">View All</button>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        {stories.map((story) => (
          <Link
            key={story.id}
            href="#"
            className="group overflow-hidden rounded-[24px] border border-white/10 bg-slate-950/90 p-5 transition hover:-translate-y-0.5 hover:border-sky-400/20"
          >
            <div className="mb-4 rounded-[22px] bg-[rgba(255,255,255,0.04)] p-4 text-sm uppercase tracking-[0.2em] text-sky-300">
              {story.theme}
            </div>
            <h3 className="text-lg font-semibold text-white">{story.title}</h3>
            <p className="mt-3 text-sm leading-6 text-slate-400">{story.description}</p>
          </Link>
        ))}
      </div>
    </section>
  );
}
