import { BarChart3 } from "lucide-react";
import { getAllCompaniesRankings } from "@/lib/companyRankings";
import { AllCompaniesRankingsView } from "./AllCompaniesRankingsView";

const PAGE_SIZE = 50;

export async function CompanyRankingsContent({ headingLevel = "h1", page = 1 }: { headingLevel?: "h1" | "h2"; page?: number }) {
  const Heading = headingLevel;
  const data = await getAllCompaniesRankings(page, PAGE_SIZE);

  return (
    <main className="mx-auto max-w-[1400px] py-8 pb-16">
      <div className="rounded-[28px] border border-surface-border/8 bg-gradient-to-br from-violet-500/[0.06] via-surface-card to-surface-card p-6 md:p-9">
        <div className="max-w-2xl">
          <div className="mb-3 flex items-center gap-2">
            <span className="flex items-center gap-1.5 rounded-full border border-violet-500/25 bg-violet-500/10 px-3 py-1 text-[11px] font-bold text-violet-600 dark:text-violet-300">
              <BarChart3 className="h-3 w-3" /> MARKETRIPPLE SCORE
            </span>
          </div>
          <Heading className="text-[30px] font-black leading-tight text-text-primary md:text-[38px]">
            Company Rankings
          </Heading>
          <p className="mt-3 text-[14px] leading-relaxed text-text-secondary">
            Every company in MarketRipple's directory, one shared MarketRipple Score formula — financial strength,
            valuation and market behaviour, ranked within each company's own real sector peer group. A company
            without enough real evidence yet, or in a sector without an approved methodology, shows an honest N/A
            with its real reason — never a screener guess, never a fabricated number, never a fake rank.
          </p>
        </div>
      </div>

      <div className="mt-10">
        <AllCompaniesRankingsView data={data} />
      </div>

      <div className="mt-10 rounded-[20px] border border-surface-border/8 bg-text-primary/[0.02] p-6">
        <h2 className="text-[15px] font-bold text-text-primary">How These Rankings Work</h2>
        <p className="mt-2 max-w-2xl text-[13px] leading-relaxed text-text-secondary">
          Every supported company's MarketRipple Score comes from the same shared formula — 8/15 Financial
          Strength, 4/15 Valuation, 3/15 Market Behaviour — whether it's a bank or a non-bank company. Current
          Intelligence is real, tracked evidence shown on each company's own page, but never part of this number.
          A company only gets a real score once all three pillars are available; otherwise it shows N/A with its
          real reason, never a filled-in guess. Rank is always within a company's own real sector peer group — a
          Banking score and a Technology score are never compared to each other.
        </p>
      </div>
    </main>
  );
}
