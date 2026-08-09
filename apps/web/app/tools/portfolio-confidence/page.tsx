import { ShieldCheck } from "lucide-react";
import { PortfolioConfidenceForm } from "./PortfolioConfidenceForm";

// Static shell (headline, explanation, input form chrome) renders directly
// here, server-side — same SSR lesson as /ai-search: a crawler or a
// no-JS first paint should see the real explanation of what this tool
// does, not just a loading shell. Only the results-after-submission
// portion (inside PortfolioConfidenceForm, a client component) is
// interactive/dynamic.
export default function PortfolioConfidencePage() {
  return (
    <main className="mx-auto max-w-3xl px-4 py-10 sm:py-14">
      <div className="mb-8 flex items-start gap-3">
        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-[14px] bg-gradient-to-br from-sky-500/20 to-emerald-500/20 border border-surface-border/10 text-sky-600 dark:text-sky-300">
          <ShieldCheck className="h-5 w-5" />
        </div>
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-text-primary sm:text-3xl">
            Portfolio Data Confidence Check
          </h1>
          <p className="mt-1.5 text-sm leading-relaxed text-text-secondary">
            Paste your holdings and we&apos;ll tell you, honestly, how much real event and news
            activity we&apos;re actually tracking on each one — not a fabricated score, the real
            counts. Strong coverage means we have real, recent signal to work with. Thin or
            untracked means we don&apos;t, yet — and we&apos;ll say so plainly rather than fake it.
          </p>
        </div>
      </div>

      <PortfolioConfidenceForm />

      <p className="mt-8 text-[11px] leading-relaxed text-text-muted">
        Coverage is measured over the last 90 days from real corporate filings and news
        ingestion already running on this platform — not a separate scoring model. A holding
        showing thin coverage isn&apos;t a judgment on the company; it just means we haven&apos;t
        ingested much real activity on it recently.
      </p>
    </main>
  );
}
