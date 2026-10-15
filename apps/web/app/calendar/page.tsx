import type { Metadata } from "next";
import { CalendarContent } from "./CalendarContent";

const SITE = process.env.NEXT_PUBLIC_SITE_URL ?? "https://www.marketripple.in";

export const metadata: Metadata = {
  title: "Policy & Calendar",
  description:
    "Government and regulatory decisions that moved the market, plus the scheduled events that could move it next — RBI meetings, GDP prints, earnings, and more.",
  openGraph: {
    title: "Policy & Calendar | MarketRipple",
    description: "Recent policy events and the upcoming economic calendar, in one place.",
    images: [{ url: "/opengraph-image", width: 1200, height: 630, alt: "MarketRipple — AI-Powered Market Intelligence" }],
  },
  // SEO fix (2026-10-14): see app/news/layout.tsx's identical comment.
  alternates: { canonical: `${SITE}/calendar` },
};

export default function CalendarPage() {
  return <CalendarContent headingLevel="h1" />;
}
