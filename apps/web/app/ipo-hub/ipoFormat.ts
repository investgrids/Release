// Pure helpers shared by the IPO list (client) and the per-IPO pages (server). No "use client" here on purpose.

export type Status = "Upcoming" | "Ongoing" | "Closed" | "Listed" | "Withdrawn";
export interface IPO {
  id: string; name: string; symbol: string; type: "Mainboard" | "SME" | null; status: Status;
  priceMin: number | null; priceMax: number | null; issuePrice: number | null;
  lotSize: number | null; sharesOffered: number | null; issueValue: string | null;
  openDate: string | null; closeDate: string | null; listingDate: string | null;
  subscription: { total?: number; retail?: number; nii?: number; qib?: number } | null;
}
export interface IPOData {
  ipos: IPO[];
  stats: { upcoming: number; ongoing: number; closed: number; listed: number; mainboard: number; sme: number };
  as_of: string | null; data_source: string; stale?: boolean;
}

export const STATUS_LABEL: Record<Status, string> = { Upcoming: "Opens soon", Ongoing: "Open now", Closed: "Awaiting listing", Listed: "Listed", Withdrawn: "Withdrawn" };
export const day = (iso: string | null) => (iso ? new Date(iso + "T00:00:00+05:30") : null);
export const fmt = (iso: string | null, withYear = false) =>
  iso ? new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", ...(withYear ? { year: "numeric" } : {}), timeZone: "Asia/Kolkata" }).format(day(iso)!) : "—";
export const rupee = (n: number | null) => (n == null ? "—" : `₹${n.toLocaleString("en-IN", { maximumFractionDigits: 2 })}`);
export const band = (i: IPO) =>
  i.priceMin != null && i.priceMax != null ? (i.priceMin === i.priceMax ? rupee(i.priceMax) : `${rupee(i.priceMin)} – ${rupee(i.priceMax)}`) : "—";

export function daysFromToday(iso: string | null): number | null {
  if (!iso) return null;
  const today = new Date(new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Kolkata" }).format(new Date()) + "T00:00:00+05:30");
  return Math.round((day(iso)!.getTime() - today.getTime()) / 86_400_000);
}
export function when(i: IPO): string {
  if (i.status === "Upcoming") {
    const d = daysFromToday(i.openDate);
    return d === 0 ? "Opens today" : d === 1 ? "Opens tomorrow" : d != null && d > 1 ? `Opens in ${d} days` : `Opens ${fmt(i.openDate)}`;
  }
  if (i.status === "Ongoing") {
    const d = daysFromToday(i.closeDate);
    return d === 0 ? "Closes today" : d === 1 ? "Closes tomorrow" : `Closes ${fmt(i.closeDate)}`;
  }
  if (i.status === "Withdrawn") return "Issue withdrawn or postponed";
  if (i.status === "Closed") return i.listingDate ? `Lists ${fmt(i.listingDate)}` : (daysFromToday(i.closeDate) ?? 0) < -21 ? "No listing on record" : "Listing date awaited";
  return `Listed ${fmt(i.listingDate)}`;
}
export const minInvest = (i: IPO) => (i.lotSize && i.priceMax ? i.lotSize * i.priceMax : null);

