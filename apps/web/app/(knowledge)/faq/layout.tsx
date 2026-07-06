import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "FAQ — Frequently Asked Questions | MarketRipple",
  description:
    "Answers to the most common questions about MarketRipple — how the AI works, where data comes from, what the platform covers, and what's coming next.",
  openGraph: {
    title: "FAQ — Frequently Asked Questions | MarketRipple",
    description:
      "Everything you need to know about MarketRipple's AI features, data sources, accuracy, and upcoming premium features.",
  },
};

export default function FAQLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
