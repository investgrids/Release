import Link from "next/link";
import { ShieldCheck, ArrowRight } from "lucide-react";

// Tools hub — the first of 5 planned. Structured the same way every other
// nav hub already is (a real home page, sub-items in SiteHeader's NAV_PRIMARY
// pointing at real standalone pages): adding tool 2 later means adding one
// entry to TOOLS below and one to NAV_PRIMARY's sub array, not a redesign.
interface ToolEntry {
  slug: string;
  title: string;
  description: string;
  icon: React.ReactNode;
}

const TOOLS: ToolEntry[] = [
  {
    slug: "portfolio-confidence",
    title: "Portfolio Data Confidence Check",
    description: "Paste your holdings and see, honestly, how much real event and news coverage we're actually tracking on each one.",
    icon: <ShieldCheck className="h-5 w-5" />,
  },
];

export default function ToolsHubPage() {
  return (
    <main className="mx-auto max-w-3xl px-4 py-10 sm:py-14">
      <h1 className="text-2xl font-bold tracking-tight text-text-primary sm:text-3xl">Tools</h1>
      <p className="mt-1.5 text-sm leading-relaxed text-text-secondary">
        Small, standalone tools built directly on this platform&apos;s own real data — no
        separate scoring model, no fabricated numbers, just honest answers to specific
        questions.
      </p>

      <div className="mt-8 space-y-3">
        {TOOLS.map(tool => (
          <Link
            key={tool.slug}
            href={`/tools/${tool.slug}` as any}
            className="flex items-start gap-4 rounded-[20px] border border-surface-border/10 bg-surface-card p-5 transition hover:border-sky-500/30 hover:bg-text-primary/[0.02]"
          >
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-[14px] bg-gradient-to-br from-sky-500/20 to-emerald-500/20 border border-surface-border/10 text-sky-600 dark:text-sky-300">
              {tool.icon}
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-[14px] font-semibold text-text-primary">{tool.title}</p>
              <p className="mt-1 text-[12.5px] leading-relaxed text-text-secondary">{tool.description}</p>
            </div>
            <ArrowRight className="mt-2 h-4 w-4 shrink-0 text-text-muted" />
          </Link>
        ))}
      </div>
    </main>
  );
}
