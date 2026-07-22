import type { Metadata } from "next";
import { Building2 } from "lucide-react";
import { ArticleTypeList } from "@/components/newsroom/ArticleTypeList";

export const metadata: Metadata = {
  title: "Company Intelligence | AI Newsroom",
  description: "What's moving individual stocks — earnings, filings, and news, and what it means for investors.",
  alternates: { canonical: "/newsroom/companies" },
};

export default async function CompanyIntelligencePage(
  { searchParams }: { searchParams: Promise<{ page?: string }> }
) {
  const { page: pageParam } = await searchParams;
  const page = Math.max(1, parseInt(pageParam ?? "1", 10) || 1);

  return (
    <div className="mx-auto max-w-4xl px-4 py-8 sm:px-6">
      <div className="mb-8">
        <p className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">
          <Building2 className="h-3 w-3 text-sky-400" /> AI Newsroom
        </p>
        <h1 className="mt-2 text-[26px] font-black leading-tight text-white md:text-[30px]">
          Company Intelligence
        </h1>
        <p className="mt-2 max-w-2xl text-[13.5px] leading-6 text-slate-400">
          What's moving individual stocks — earnings, filings, and news, and what it means for investors.
        </p>
      </div>
      <ArticleTypeList
        articleType="company_intelligence"
        basePath="/newsroom/companies"
        page={page}
        emptyText="No company intelligence published in the last cycle — check back soon."
      />
    </div>
  );
}
