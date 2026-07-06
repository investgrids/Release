import { redirect } from "next/navigation";

export default function MarketSignalsPage() {
  redirect("/market-intelligence?tab=overview");
}
