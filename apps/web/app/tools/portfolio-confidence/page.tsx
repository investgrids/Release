import { ShieldCheck, Target, Compass, SearchCheck } from "lucide-react";
import { fetchAPI } from "@/lib/api";
import { PortfolioConfidenceForm } from "./PortfolioConfidenceForm";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "https://www.marketripple.in";

const WHY_THIS_MATTERS = [
  {
    title: "Stay Ahead",
    body: "See important developments across your holdings early.",
    icon: <ShieldCheck className="h-4 w-4" />,
    tint: "bg-sky-500/10 text-sky-600 dark:text-sky-300",
  },
  {
    title: "Focus on What Matters",
    body: "Identify companies that need your attention today.",
    icon: <Target className="h-4 w-4" />,
    tint: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-300",
  },
  {
    title: "See the Big Picture",
    body: "Discover themes and events affecting multiple holdings.",
    icon: <Compass className="h-4 w-4" />,
    tint: "bg-amber-500/10 text-amber-600 dark:text-amber-300",
  },
  {
    title: "Find Blind Spots",
    body: "Know where Market Ripple has limited intelligence coverage.",
    icon: <SearchCheck className="h-4 w-4" />,
    tint: "bg-accent-violet/10 text-accent-violet",
  },
];

const HOW_IT_WORKS = [
  { n: "1", title: "Match", body: "We match your holdings with our tracked company universe." },
  { n: "2", title: "Measure", body: "We analyze real market events and news from the last 90 days." },
  { n: "3", title: "Score", body: "Each holding gets a coverage verdict: Strong, Moderate, Thin or Unresolved." },
  { n: "4", title: "Investigate", body: "Explore deeper with AI Search for companies with thin coverage." },
];

// Static shell (eyebrow, H1, description, input form chrome, why-this-
// matters, how-it-works, privacy) renders server-side, same as before —
// a crawler or no-JS first paint sees the real explanation of what this
// tool does, not just a loading shell. Only the results-after-submission
// portion (inside PortfolioConfidenceForm, a client component) is
// interactive/dynamic — nothing here blocks on it or on portfolio
// analysis, which only ever runs after the user submits.
export default async function PortfolioConfidencePage() {
  const universeTotal = await fetchAPI<{ total: number }>("/api/companies/?page_size=6")
    .then(d => d.total)
    .catch(() => null);

  const heroLeft = (
    <div className="pt-2">
      <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-accent-violet">
        Portfolio Intelligence
      </p>
      <h1 className="mt-3 text-[32px] font-bold leading-[1.1] tracking-tight text-text-primary sm:text-[42px]">
        Portfolio Intelligence Brief
      </h1>
      <p className="mt-4 max-w-md text-[15px] leading-relaxed text-text-secondary">
        What&apos;s happening across the companies you own — right now. Get a daily intelligence
        brief powered by real events, news, and market impact across your holdings.
      </p>
      <div className="mt-6 flex flex-wrap items-center gap-x-5 gap-y-2 text-[11.5px] text-text-secondary">
        <span>No login required</span>
        <span className="h-1 w-1 rounded-full bg-text-muted/40" />
        <span>No broker connection</span>
        <span className="h-1 w-1 rounded-full bg-text-muted/40" />
        <span>No portfolio storage</span>
      </div>
    </div>
  );

  return (
    <main className="bg-bg">
      {/* Data integrity: this tool orchestrates existing, real Market
          Ripple signals (entity matching, events, news, live prices,
          intelligence themes) — it is not a new intelligence engine and
          never fabricates a number. See PortfolioConfidenceForm.tsx. */}
      <script
        type="application/ld+json"
        // biome-ignore lint/security/noDangerouslySetInnerHtml: static JSON-LD
        dangerouslySetInnerHTML={{ __html: JSON.stringify({
          "@context": "https://schema.org",
          "@type": "WebApplication",
          name: "Portfolio Intelligence Brief",
          applicationCategory: "FinanceApplication",
          operatingSystem: "Any (web-based)",
          url: `${SITE_URL}/tools/portfolio-confidence`,
          description:
            "See what's happening across the companies you own — real events, news, market-moving price signals, and shared themes across your holdings, plus where Market Ripple's intelligence coverage is thin.",
          offers: { "@type": "Offer", price: "0", priceCurrency: "INR" },
          provider: { "@type": "Organization", name: "MarketRipple", url: SITE_URL },
        }) }}
      />
      <script
        type="application/ld+json"
        // biome-ignore lint/security/noDangerouslySetInnerHtml: static JSON-LD
        dangerouslySetInnerHTML={{ __html: JSON.stringify({
          "@context": "https://schema.org",
          "@type": "HowTo",
          name: "How the Portfolio Intelligence Brief works",
          step: HOW_IT_WORKS.map(s => ({
            "@type": "HowToStep",
            position: Number(s.n),
            name: s.title,
            text: s.body,
          })),
        }) }}
      />

      <div className="mx-auto max-w-6xl px-4 pb-6 pt-10 sm:pt-14">
        <PortfolioConfidenceForm universeTotal={universeTotal} heroLeft={heroLeft} howItWorks={HOW_IT_WORKS} />

        {/* Why this matters — static, server-rendered */}
        <div className="mt-8 rounded-2xl border border-surface-border/10 bg-surface-card p-6">
          <p className="text-[13px] font-semibold text-text-primary">Why this matters</p>
          <div className="mt-4 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
            {WHY_THIS_MATTERS.map(w => (
              <div key={w.title} className="flex items-start gap-3">
                <span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${w.tint}`}>
                  {w.icon}
                </span>
                <div>
                  <p className="text-[13px] font-semibold text-text-primary">{w.title}</p>
                  <p className="mt-0.5 text-[12px] leading-relaxed text-text-secondary">{w.body}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </main>
  );
}
