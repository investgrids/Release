import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { fetchAPI } from "@/lib/api";
import { StaticBreadcrumbs } from "@/components/Breadcrumbs";
import { type IPO, type IPOData, STATUS_LABEL, band, daysFromToday, fmt, minInvest, rupee, when } from "@/app/ipo-hub/ipoFormat";
import { LotCalculator, Timeline } from "./IPOTools";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "https://www.marketripple.in";
export const revalidate = 600;

async function load(id: string): Promise<IPO | null> {
  try {
    return await fetchAPI<IPO>(`/api/ipo/${encodeURIComponent(id)}`, { revalidate: 600 });
  } catch {
    return null;   // unknown id (or NSE unreachable with nothing cached): the page 404s rather than inventing content
  }
}

function summary(i: IPO): string {
  const board = i.type ? `${i.type} ` : "";
  const price = i.priceMin != null && i.priceMax != null ? ` with a price band of ${band(i)} per share` : "";
  const lot = i.lotSize ? ` and a lot size of ${i.lotSize.toLocaleString("en-IN")} shares` : "";
  switch (i.status) {
    case "Upcoming": return `${i.name} has an upcoming ${board}IPO on NSE. Bidding opens on ${fmt(i.openDate, true)} and closes on ${fmt(i.closeDate, true)}${price}${lot}.`;
    case "Ongoing": return `The ${board}IPO of ${i.name} is open for bidding on NSE until ${fmt(i.closeDate, true)}${price}${lot}.`;
    case "Closed": return `Bidding for the ${board}IPO of ${i.name} closed on ${fmt(i.closeDate, true)}${price}${lot}. ${i.listingDate ? `Listing is scheduled for ${fmt(i.listingDate, true)}.` : "NSE has not published a listing date yet."}`;
    case "Listed": return `${i.name} listed on NSE on ${fmt(i.listingDate, true)}${i.issuePrice ? ` after a ${board}IPO issued at ${rupee(i.issuePrice)} per share` : ""}. Bidding ran from ${fmt(i.openDate, true)} to ${fmt(i.closeDate, true)}${lot}.`;
    default: return `The ${board}IPO of ${i.name} was withdrawn or postponed, according to NSE's issue list.`;
  }
}

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }): Promise<Metadata> {
  const ipo = await load((await params).id);
  if (!ipo) return { title: "IPO not found", robots: { index: false } };
  const title = `${ipo.name} IPO: Price Band, Dates, Lot Size & Listing`;
  const description = summary(ipo).slice(0, 300);
  const url = `${SITE_URL}/ipo/${ipo.id}`;
  return {
    title, description,
    alternates: { canonical: url },
    robots: ipo.status === "Withdrawn" ? { index: false, follow: true } : { index: true, follow: true },
    openGraph: { type: "article", title, description, url, siteName: "MarketRipple", images: [{ url: "/opengraph-image", width: 1200, height: 630, alt: `${ipo.name} IPO` }] },
    twitter: { card: "summary_large_image", title, description },
  };
}

function Fact({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-[16px] border border-surface-border/10 bg-text-primary/[0.02] px-4 py-3">
      <dt className="text-[10px] font-semibold uppercase tracking-wider text-text-muted">{label}</dt>
      <dd className="mt-1 text-[16px] font-bold tabular-nums text-text-primary">{value}</dd>
      {hint && <p className="mt-0.5 text-[10.5px] text-text-muted">{hint}</p>}
    </div>
  );
}

const BADGE: Record<IPO["status"], string> = {
  Upcoming: "bg-sky-500/10 text-sky-700 dark:text-sky-300 border-sky-500/25",
  Ongoing: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border-emerald-500/25",
  Closed: "bg-amber-500/10 text-amber-700 dark:text-amber-300 border-amber-500/25",
  Listed: "bg-violet-500/10 text-violet-700 dark:text-violet-300 border-violet-500/25",
  Withdrawn: "bg-rose-500/10 text-rose-700 dark:text-rose-300 border-rose-500/25",
};

export default async function IPODetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const ipo = await load(id);
  if (!ipo) notFound();

  const list = await fetchAPI<IPOData>("/api/ipo/", { revalidate: 600 }).catch(() => null);
  const related = (list?.ipos ?? []).filter(i => i.id !== ipo.id && (i.status === "Ongoing" || i.status === "Upcoming")).slice(0, 4);

  const o = daysFromToday(ipo.openDate), c = daysFromToday(ipo.closeDate), l = daysFromToday(ipo.listingDate);
  const steps: { label: string; date: string; state: "done" | "active" | "next" }[] = [
    { label: "Bidding opens", date: fmt(ipo.openDate, true), state: o != null && o <= 0 ? "done" : "next" },
    { label: "Bidding closes", date: fmt(ipo.closeDate, true), state: c != null && c < 0 ? "done" : o != null && o <= 0 ? "active" : "next" },
    { label: "Listing on NSE", date: ipo.listingDate ? fmt(ipo.listingDate, true) : "Not announced yet", state: l != null && l <= 0 ? "done" : c != null && c < 0 ? "active" : "next" },
  ];
  const min = minInvest(ipo);
  const url = `${SITE_URL}/ipo/${ipo.id}`;
  const jsonLd = {
    "@context": "https://schema.org", "@type": "Event", name: `${ipo.name} IPO`, url,
    ...(ipo.openDate ? { startDate: ipo.openDate } : {}), ...(ipo.closeDate ? { endDate: ipo.closeDate } : {}),
    eventStatus: ipo.status === "Withdrawn" ? "https://schema.org/EventCancelled" : "https://schema.org/EventScheduled",
    eventAttendanceMode: "https://schema.org/OnlineEventAttendanceMode",
    location: { "@type": "VirtualLocation", url }, description: summary(ipo),
  };

  return (
    <main className="min-w-0 space-y-6 pb-10">
      <StaticBreadcrumbs items={[{ label: "IPO Calendar", href: "/ipo" }, { label: `${ipo.name} IPO` }]} />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd).replace(/</g, "\\u003c") }} />

      <header className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <span className={`inline-flex items-center whitespace-nowrap rounded-full border px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wide ${BADGE[ipo.status]}`}>{STATUS_LABEL[ipo.status]}</span>
          {ipo.type && <span className="rounded-md bg-text-primary/[0.07] px-2 py-0.5 text-[11px] font-bold text-text-secondary">{ipo.type}</span>}
          <span className="text-[12px] font-semibold text-text-muted">NSE: {ipo.symbol}</span>
        </div>
        <h1 className="text-3xl font-bold leading-tight tracking-tight text-text-primary sm:text-4xl">{ipo.name} IPO</h1>
        <p className="max-w-3xl text-[15px] leading-relaxed text-text-secondary">{summary(ipo)}</p>
        {ipo.status !== "Withdrawn" && <p className="text-[13px] font-semibold text-violet-700 dark:text-violet-300">{when(ipo)}</p>}
      </header>

      {ipo.status !== "Withdrawn" && (
        <section aria-label="Timeline" className="rounded-[22px] border border-surface-border/10 bg-text-primary/[0.02] p-5">
          <h2 className="mb-4 text-[15px] font-bold text-text-primary">Timeline</h2>
          <Timeline steps={steps} />
        </section>
      )}

      <section aria-label="Key facts">
        <h2 className="mb-3 text-[15px] font-bold text-text-primary">Key facts</h2>
        <dl className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Fact label="Price band" value={band(ipo)} hint="per share" />
          <Fact label="Final issue price" value={ipo.issuePrice ? rupee(ipo.issuePrice) : "Not on record"} />
          <Fact label="Lot size" value={ipo.lotSize ? `${ipo.lotSize.toLocaleString("en-IN")} shares` : "Not published"} />
          <Fact label="Min. investment" value={min ? rupee(min) : "—"} hint={min ? "1 lot at the upper band" : undefined} />
          <Fact label="Shares on offer" value={ipo.sharesOffered ? ipo.sharesOffered.toLocaleString("en-IN") : "Not published"} />
          <Fact label="Issue value (est.)" value={ipo.issueValue ?? "—"} hint={ipo.issueValue ? "Shares × upper band" : undefined} />
          <Fact label="Bidding window" value={`${fmt(ipo.openDate)} – ${fmt(ipo.closeDate)}`} />
          <Fact label="Listing date" value={ipo.listingDate ? fmt(ipo.listingDate, true) : "Not announced"} />
        </dl>
        {ipo.subscription && (
          <p className="mt-3 text-[13px] text-text-secondary">Subscription so far: {Object.entries(ipo.subscription).map(([k, v]) => `${k.toUpperCase()} ${v}×`).join(" · ")}</p>
        )}
      </section>

      {ipo.lotSize && ipo.priceMax && ipo.status !== "Withdrawn" && <LotCalculator lotSize={ipo.lotSize} priceMin={ipo.priceMin} priceMax={ipo.priceMax} />}

      <section aria-label="How to read these numbers" className="rounded-[22px] border border-surface-border/10 bg-text-primary/[0.02] p-5">
        <h2 className="text-[15px] font-bold text-text-primary">How to read these numbers</h2>
        <dl className="mt-3 grid gap-4 text-[13px] leading-relaxed text-text-secondary md:grid-cols-3">
          <div><dt className="font-semibold text-text-primary">Price band</dt><dd>The range within which investors can bid. The final issue price is fixed inside it after bidding closes.</dd></div>
          <div><dt className="font-semibold text-text-primary">Lot size</dt><dd>The minimum number of shares in one application. Bids are made in multiples of a lot.</dd></div>
          <div><dt className="font-semibold text-text-primary">Mainboard and SME</dt><dd>SME IPOs list on a separate NSE platform for smaller companies, usually with larger lot values and thinner trading.</dd></div>
        </dl>
      </section>

      {related.length > 0 && (
        <section aria-label="Other open and upcoming IPOs">
          <h2 className="mb-3 text-[15px] font-bold text-text-primary">Other open and upcoming IPOs</h2>
          <ul className="grid gap-3 sm:grid-cols-2">
            {related.map(r => (
              <li key={r.id}>
                <Link href={`/ipo/${r.id}`} className="block rounded-[16px] border border-surface-border/10 bg-text-primary/[0.02] px-4 py-3 transition hover:border-violet-500/30">
                  <p className="text-[13px] font-semibold text-text-primary">{r.name} IPO</p>
                  <p className="mt-0.5 text-[12px] tabular-nums text-text-secondary">{band(r)} · {when(r)}</p>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-surface-border/10 pt-4">
        <Link href="/ipo" className="text-[13px] font-semibold text-violet-700 hover:underline dark:text-violet-300">&larr; All IPOs</Link>
        <p className="max-w-2xl text-[11.5px] leading-relaxed text-text-muted">Source: NSE issue lists. Dates, price bands, lot sizes and issue prices are as NSE publishes them; minimum investment and issue value are calculations. MarketRipple does not publish grey-market premiums or subscribe/avoid ratings. This is information, not investment advice.</p>
      </div>
    </main>
  );
}
