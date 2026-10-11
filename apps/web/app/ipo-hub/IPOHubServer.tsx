import { fetchAPI } from "@/lib/api";
import { IPOHubContent, type IPOData } from "./IPOHubContent";

/** Fetches the NSE-backed IPO list on the server (10-minute ISR) so it is in the HTML that crawlers and the first paint receive. */
export async function getIpoData(): Promise<IPOData | null> {
  try {
    return await fetchAPI<IPOData>("/api/ipo/", { revalidate: 600 });
  } catch {
    return null;
  }
}

export async function IPOHubServer({ headingLevel = "h1" }: { headingLevel?: "h1" | "h2" }) {
  return <IPOHubContent headingLevel={headingLevel} initialData={await getIpoData()} />;
}
