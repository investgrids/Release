import type { Metadata } from "next";
import { CommoditiesContent } from "./CommoditiesContent";
import { getCommodities } from "@/lib/commodities";
import { safeJsonLd } from "@/lib/text";

const SITE = process.env.NEXT_PUBLIC_SITE_URL ?? "https://www.marketripple.in";

export const metadata: Metadata = {
  title: "Commodity & Energy Prices Today — Gold, Silver, Crude Oil",
  description: "Live gold, silver, copper, platinum, Brent crude, WTI crude, natural gas, and India petrol prices with 7-day trend charts, AI market insights, and India-relevant impact analysis.",
  openGraph: {
    type: "website",
    title: "Commodity & Energy Prices Today — MarketRipple",
    description: "Live metals and energy prices with real 7-day trend data.",
    url: `${SITE}/commodities`,
    siteName: "MarketRipple",
    images: [{ url: "/opengraph-image", width: 1200, height: 630, alt: "MarketRipple — AI-Powered Market Intelligence" }],
  },
  alternates: { canonical: `${SITE}/commodities` },
};

// Real FAQ content (AEO) — every answer either reads live data passed in
// (gold/silver/crude prices) or is a stable, factual explainer (Brent vs
// WTI, why India's petrol price tracks global crude, update cadence) that
// doesn't need live data and won't go stale. No invented numbers.
function buildFaqs(data: Awaited<ReturnType<typeof getCommodities>>) {
  const find = (id: string) => data?.metals.find(c => c.id === id) ?? data?.energy.find(c => c.id === id);
  const gold = find("gold");
  const brent = find("brent");
  const wti = find("wti");
  const petrol = find("petrol");

  const faqs: { question: string; answer: string }[] = [];
  if (gold) {
    faqs.push({
      question: "What is the gold price today?",
      answer: `Gold is trading at ${gold.price} ${gold.unit}, ${gold.positive ? "up" : "down"} ${gold.change} (${gold.pct >= 0 ? "+" : ""}${gold.pct.toFixed(2)}%) on the day. Prices are sourced from COMEX gold futures via yfinance, delayed roughly 15 minutes.`,
    });
  }
  if (brent && wti) {
    faqs.push({
      question: "What is the difference between Brent crude and WTI crude oil?",
      answer: `Brent crude (currently ${brent.price} ${brent.unit}) is the global seaborne benchmark, priced off North Sea oil and used to price roughly two-thirds of the world's traded crude, including most of India's imports. WTI crude (currently ${wti.price} ${wti.unit}) is the US domestic benchmark, priced off oil delivered at Cushing, Oklahoma. The two normally move together but can diverge on regional supply, storage, and shipping factors.`,
    });
  }
  if (petrol && brent) {
    faqs.push({
      question: "Why do India's petrol prices track global crude oil prices?",
      answer: `India imports over 80% of the crude oil it refines, so retail petrol and diesel pricing here is directly exposed to global crude benchmarks like Brent (currently ${brent.price} ${brent.unit}), along with the rupee-dollar exchange rate, refining margins, and state/central taxes and duties.`,
    });
  }
  faqs.push({
    question: "How often are these commodity prices updated?",
    answer: "Metal and energy futures prices refresh roughly every 2 minutes from COMEX, NYMEX, and ICE data via yfinance, delayed about 15 minutes from live exchange feeds. AI market insights refresh roughly every 30 minutes.",
  });
  faqs.push({
    question: "Which commodities does MarketRipple track?",
    answer: "Four metals — gold, silver, copper, and platinum — and four energy commodities — Brent crude oil, WTI crude oil, natural gas, and India retail petrol — each with a live price, day high/low, and a real 7-day price trend chart.",
  });
  return faqs;
}

export default async function CommoditiesHubPage() {
  const data = await getCommodities();
  const faqs = buildFaqs(data);
  const url = `${SITE}/commodities`;

  const allCommodities = data ? [...data.metals, ...data.energy] : [];
  const collectionJsonLd = {
    "@context": "https://schema.org",
    "@type": "CollectionPage",
    name: "Commodity & Energy Prices Today — MarketRipple",
    url,
    breadcrumb: {
      "@type": "BreadcrumbList",
      itemListElement: [
        { "@type": "ListItem", position: 1, name: "MarketRipple", item: SITE },
        { "@type": "ListItem", position: 2, name: "Commodities", item: url },
      ],
    },
    ...(allCommodities.length > 0 && {
      mainEntity: {
        "@type": "ItemList",
        itemListElement: allCommodities.map((c, i) => ({
          "@type": "ListItem",
          position: i + 1,
          name: c.name,
          url: `${url}/${c.id}`,
        })),
      },
    }),
  };
  const faqJsonLd = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: faqs.map(f => ({
      "@type": "Question",
      name: f.question,
      acceptedAnswer: { "@type": "Answer", text: f.answer },
    })),
  };

  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: safeJsonLd(collectionJsonLd) }} />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: safeJsonLd(faqJsonLd) }} />
      <CommoditiesContent headingLevel="h1" initialData={data} faqs={faqs} />
    </>
  );
}
