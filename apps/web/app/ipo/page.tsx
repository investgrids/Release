import type { Metadata } from "next";
import { IPOHubContent } from "@/app/ipo-hub/IPOHubContent";
import { getIpoData } from "@/app/ipo-hub/IPOHubServer";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "https://www.marketripple.in";
const TITLE = "IPO Calendar India: Open, Upcoming & Recently Listed NSE IPOs";
const DESCRIPTION =
  "Track every IPO on NSE: open and upcoming issues with dates, price bands, lot sizes and listing dates, plus recently listed Mainboard and SME IPOs. Exchange-sourced and updated through the day.";

export const metadata: Metadata = {
  title: TITLE,
  description: DESCRIPTION,
  alternates: { canonical: `${SITE_URL}/ipo` },
  openGraph: {
    type: "website", title: TITLE, description: DESCRIPTION, url: `${SITE_URL}/ipo`, siteName: "MarketRipple",
    images: [{ url: "/opengraph-image", width: 1200, height: 630, alt: "MarketRipple IPO Calendar" }],
  },
  twitter: { card: "summary_large_image", title: TITLE, description: DESCRIPTION },
};

export const revalidate = 600;

export default async function IPOPage() {
  const data = await getIpoData();
  const live = (data?.ipos ?? []).filter(i => i.status === "Ongoing" || i.status === "Upcoming").slice(0, 20);

  // The global breadcrumb component already emits the BreadcrumbList for /ipo; adding another here would duplicate it.
  const jsonLd = [
    ...(live.length ? [{
      "@context": "https://schema.org", "@type": "ItemList", name: "Open and upcoming IPOs on NSE",
      itemListElement: live.map((i, n) => ({
        "@type": "ListItem", position: n + 1, url: `${SITE_URL}/ipo/${i.id}`,
        item: {
          "@type": "Event", name: `${i.name} IPO`, url: `${SITE_URL}/ipo/${i.id}`,
          ...(i.openDate ? { startDate: i.openDate } : {}), ...(i.closeDate ? { endDate: i.closeDate } : {}),
          eventStatus: "https://schema.org/EventScheduled", eventAttendanceMode: "https://schema.org/OnlineEventAttendanceMode",
          location: { "@type": "VirtualLocation", url: `${SITE_URL}/ipo/${i.id}` },
          description: `${i.type ?? ""} IPO${i.priceMin && i.priceMax ? ` with a price band of ₹${i.priceMin}–₹${i.priceMax}` : ""}${i.lotSize ? `, lot size ${i.lotSize} shares` : ""}.`,
        },
      })),
    }] : []),
  ];

  return (
    <>
      {jsonLd.length > 0 && <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd).replace(/</g, "\\u003c") }} />}
      <IPOHubContent headingLevel="h1" initialData={data} />
    </>
  );
}
