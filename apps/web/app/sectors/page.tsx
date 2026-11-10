import type { Metadata } from "next";
import { SectorsContent } from "./SectorsContent";

export const metadata: Metadata = {
  title: "Sectors — NSE Sectoral Performance",
  alternates: { canonical: "/sectors" },
};

export default function SectorsPage() {
  return <SectorsContent headingLevel="h1" />;
}
