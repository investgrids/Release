import type { Metadata } from "next";
import { Radio } from "lucide-react";
import { ArticleTypeList } from "@/components/newsroom/ArticleTypeList";

export const metadata: Metadata = {
  title: "Breaking Intelligence | AI Newsroom",
  description: "Real-time AI analysis as market-moving developments happen.",
  alternates: { canonical: "/newsroom/breaking" },
};

export default async function BreakingIntelligencePage(
  { searchParams }: { searchParams: Promise<{ page?: string }> }
) {
  const { page: pageParam } = await searchParams;
  const page = Math.max(1, parseInt(pageParam ?? "1", 10) || 1);

  return (
    <div className="mx-auto max-w-4xl px-4 py-8 sm:px-6">
      <div className="mb-8">
        <p className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">
          <Radio className="h-3 w-3 text-rose-400" /> AI Newsroom
        </p>
        <h1 className="mt-2 text-[26px] font-black leading-tight text-white md:text-[30px]">
          Breaking Intelligence
        </h1>
        <p className="mt-2 max-w-2xl text-[13.5px] leading-6 text-slate-400">
          Real-time AI analysis as market-moving developments happen.
        </p>
      </div>
      <ArticleTypeList
        articleType="breaking_intelligence"
        basePath="/newsroom/breaking"
        page={page}
        emptyText="No breaking intelligence in the last cycle — check back soon."
      />
    </div>
  );
}
