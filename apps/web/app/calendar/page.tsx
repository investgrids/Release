import type { Metadata } from "next";
import { CalendarContent } from "./CalendarContent";

export const metadata: Metadata = {
  title: "Policy & Calendar",
  description:
    "Government and regulatory decisions that moved the market, plus the scheduled events that could move it next — RBI meetings, GDP prints, earnings, and more.",
  openGraph: {
    title: "Policy & Calendar | MarketRipple",
    description: "Recent policy events and the upcoming economic calendar, in one place.",
    images: [{ url: "/opengraph-image", width: 1200, height: 630, alt: "MarketRipple — AI-Powered Market Intelligence" }],
  },
};

export default function CalendarPage() {
  return <CalendarContent headingLevel="h1" />;
}
