import { BarChart3 } from "lucide-react";
import { getSectorRankings } from "@/lib/companyRankings";
import { CompanyRankingsView } from "./CompanyRankingsView";

export async function CompanyRankingsContent({ headingLevel = "h1" }: { headingLevel?: "h1" | "h2" }) {
  const Heading = headingLevel;
  const data = await getSectorRankings("Banking");

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
            Companies ranked by MarketRipple Score — a combined view of financial strength, valuation, market
            behaviour and current intelligence, published only once a company's real evidence clears a fixed
            eligibility bar. Never a screener guess, never a fabricated number for a company that isn't ready.
          </p>
        </div>
      </div>

      <div className="mt-10">
        <CompanyRankingsView data={data} />
      </div>

      <div className="mt-10 rounded-[20px] border border-surface-border/8 bg-text-primary/[0.02] p-6">
        <h2 className="text-[15px] font-bold text-text-primary">How These Rankings Work</h2>
        <p className="mt-2 max-w-2xl text-[13px] leading-relaxed text-text-secondary">
          Every ranked company has a MarketRipple Score computed from real financial data, valuation, market
          behaviour and evidence — reviewed and approved for publication before it appears here. A company that
          hasn't cleared that bar yet is shown as unranked with its real reason, never filled in with a
          different, unrelated score. Banking is the only sector with an approved methodology today; other
          sectors will be added as their own methodologies are reviewed and approved.
        </p>
      </div>
    </main>
  );
}
