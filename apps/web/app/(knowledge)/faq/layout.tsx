import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "FAQ — Frequently Asked Questions",
  description:
    "Answers to the most common questions about MarketRipple — how the AI works, where data comes from, what the platform covers, and what's coming next.",
  alternates: {
    canonical: "https://www.marketripple.in/faq",
  },
  openGraph: {
    title: "FAQ — Frequently Asked Questions | MarketRipple",
    description:
      "Everything you need to know about MarketRipple's AI features, data sources, accuracy, and upcoming premium features.",
    url: "https://www.marketripple.in/faq",
    images: [{ url: "/opengraph-image", width: 1200, height: 630, alt: "MarketRipple — AI-Powered Market Intelligence" }],
  },
};

export default function FAQLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
