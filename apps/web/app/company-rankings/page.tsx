import type { Metadata } from "next";
import { CompanyRankingsContent } from "./CompanyRankingsContent";

const SITE = process.env.NEXT_PUBLIC_SITE_URL ?? "https://www.marketripple.in";

export const metadata: Metadata = {
  title: "Company Rankings — Real MarketRipple Score",
  description: "Companies ranked by the real MarketRipple Score — financial strength, valuation, market behaviour and current intelligence. Banking today; more sectors as their methodologies are approved.",
  openGraph: {
    type: "website",
    title: "Company Rankings — MarketRipple",
    description: "Real, published MarketRipple Score rankings, starting with Banking.",
    url: `${SITE}/company-rankings`,
    siteName: "MarketRipple",
    images: [{ url: "/opengraph-image", width: 1200, height: 630, alt: "MarketRipple — AI-Powered Market Intelligence" }],
  },
  alternates: { canonical: `${SITE}/company-rankings` },
};

export default async function CompanyRankingsHubPage({
  searchParams = Promise.resolve({}),
}: {
  searchParams?: Promise<{ page?: string }>;
}) {
  const params = await searchParams;
  const page = Math.max(1, parseInt(params.page ?? "1", 10) || 1);
  return <CompanyRankingsContent headingLevel="h1" page={page} />;
}
