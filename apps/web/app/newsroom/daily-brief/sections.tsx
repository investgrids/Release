import Link from "next/link";
import { BadgeCheck, CircleAlert, MessageSquareQuote, ChevronRight, Compass, Layers, Target } from "lucide-react";
import { cleanText } from "@/lib/text";

// ── Types: the four sections the Daily Brief API adds (all optional so an older backend response still renders) ─────────────

export type EvidenceLabel = "confirmed_driver" | "potential_contributor" | "commentary";
export interface DriverItem {
  id: string | null; headline: string; source: string | null; published_at: string | null;
  evidence_label: EvidenceLabel; relevance: string[];
  sectors: { name: string; verified_move_pct: number | null }[];
  companies: { symbol: string; relation: "mentioned" }[];
  articles_merged: number;
  links: { event: string | null; article: string | null };
}
export interface MarketDrivers { items: DriverItem[]; groups: Record<EvidenceLabel, DriverItem[]>; note: string | null; method: string }
export interface Implications {
  items: { sector: string; verified_move_pct: number | null; why: string; developments: { id: string | null; headline: string; evidence_label: EvidenceLabel }[];
           companies_mentioned: string[]; companies_label: string | null }[];
  note: string | null;
}
export interface Scenarios {
  available: boolean; reason?: string; target: string; generated_at: string;
  current_signals?: { label: string; reading: string | null; direction: string; detail: string | null }[];
  scenarios?: { key: "bullish" | "neutral" | "bearish"; title: string; condition: string; watch: string[] }[];
  catalysts?: string[]; gift_nifty_status?: string | null; note?: string;
}
export interface Takeaway {
  development: { headline: string; evidence_label: EvidenceLabel; text: string; id: string | null } | null;
  uncertainty: string; monitor: string[];
}

// Brand: primary #6366F1 (indigo), secondary #14B8A6 (teal); status colours as the site uses them (emerald up, rose down, amber caution).
const LABEL_META: Record<EvidenceLabel, { text: string; cls: string; Icon: typeof BadgeCheck; blurb: string }> = {
  confirmed_driver: {
    text: "Confirmed", Icon: BadgeCheck, blurb: "An authoritative source ties the development to the move, and verified data agrees.",
    cls: "border-[#14B8A6]/35 bg-[#14B8A6]/10 text-teal-700 dark:text-teal-300",
  },
  potential_contributor: {
    text: "Potential contributor", Icon: CircleAlert, blurb: "Significant and in the same session as a move. Timing alone does not show cause.",
    cls: "border-amber-500/35 bg-amber-500/10 text-amber-700 dark:text-amber-300",
  },
  commentary: {
    text: "Commentary", Icon: MessageSquareQuote, blurb: "Analysis or opinion, shown for context rather than as a driver.",
    cls: "border-surface-border/20 bg-text-primary/[0.04] text-text-secondary",
  },
};

const FOCUS = "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#6366F1]";

function fmtIST(iso: string | null): string | null {
  if (!iso) return null;
  try {
    return new Date(iso).toLocaleString("en-IN", { timeZone: "Asia/Kolkata", day: "numeric", month: "short", hour: "numeric", minute: "2-digit", hour12: true }) + " IST";
  } catch {
    return null;
  }
}

function Move({ pct }: { pct: number | null }) {
  if (pct === null) return <span className="text-text-muted">no verified move</span>;
  return <span className={`font-semibold tabular-nums ${pct >= 0 ? "text-emerald-600 dark:text-emerald-400" : "text-rose-600 dark:text-rose-400"}`}>{pct >= 0 ? "+" : ""}{pct.toFixed(2)}%</span>;
}

function SectionTitle({ title, note, id }: { title: string; note?: string; id: string }) {
  return (
    <div className="mb-4 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
      <h2 id={id} className="text-[19px] font-bold tracking-tight text-text-primary">{title}</h2>
      {note && <p className="max-w-xl text-[11.5px] leading-snug text-text-muted">{note}</p>}
    </div>
  );
}

// ── What moved the market today? ───────────────────────────────────────────────────────────────────────────────────────

function DriverRow({ it }: { it: DriverItem }) {
  const meta = LABEL_META[it.evidence_label];
  const published = fmtIST(it.published_at);
  return (
    <li className="rounded-2xl border border-surface-border/10 bg-surface-card/60 p-4 sm:p-5">
      <div className="flex flex-wrap items-center gap-2">
        <span className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-[10.5px] font-bold uppercase tracking-wide ${meta.cls}`}>
          <meta.Icon className="h-3 w-3" aria-hidden="true" /> {meta.text}
        </span>
        <span className="text-[11px] text-text-muted">
          {[it.source, published].filter(Boolean).join(" · ")}
        </span>
      </div>
      <h3 className="mt-2 text-[15px] font-semibold leading-snug text-text-primary">
        {it.links.event ? <Link href={it.links.event} className={`rounded-sm hover:text-[#6366F1] ${FOCUS}`}>{cleanText(it.headline)}</Link> : cleanText(it.headline)}
      </h3>
      <ul className="mt-2 space-y-1">
        {it.relevance.map((r, i) => <li key={i} className="text-[12.5px] leading-relaxed text-text-secondary">{r}</li>)}
      </ul>
      {(it.sectors.length > 0 || it.companies.length > 0) && (
        <div className="mt-3 flex flex-wrap items-center gap-1.5">
          {it.sectors.map(s => (
            <span key={s.name} className="inline-flex items-center gap-1.5 rounded-full border border-surface-border/15 bg-text-primary/[0.03] px-2.5 py-1 text-[11px] text-text-secondary">
              {s.name} <Move pct={s.verified_move_pct} />
            </span>
          ))}
          {it.companies.map(c => (
            <Link key={c.symbol} href={`/companies/${c.symbol}`} className={`inline-flex items-center gap-1 rounded-full border border-surface-border/15 px-2.5 py-1 text-[11px] text-text-secondary transition hover:text-text-primary ${FOCUS}`}>
              {c.symbol} <span className="text-text-muted">mentioned</span>
            </Link>
          ))}
        </div>
      )}
      {(it.links.event || it.links.article) && (
        <div className="mt-3 flex flex-wrap gap-4">
          {it.links.article && <Link href={it.links.article} className={`inline-flex items-center gap-0.5 rounded-sm text-[12px] font-semibold text-[#6366F1] hover:opacity-80 ${FOCUS}`}>Read the analysis <ChevronRight className="h-3 w-3" aria-hidden="true" /></Link>}
          {it.links.event && <Link href={it.links.event} className={`inline-flex items-center gap-0.5 rounded-sm text-[12px] font-semibold text-text-secondary hover:text-text-primary ${FOCUS}`}>Event details <ChevronRight className="h-3 w-3" aria-hidden="true" /></Link>}
        </div>
      )}
    </li>
  );
}

export function MarketDriversSection({ drivers, sessionLabel }: { drivers: MarketDrivers; sessionLabel: string }) {
  const order: EvidenceLabel[] = ["confirmed_driver", "potential_contributor", "commentary"];
  return (
    <section aria-labelledby="drivers-title" className="mt-10">
      <SectionTitle id="drivers-title" title="What moved the market today?" note={`Up to five developments, each shown once and labelled by how strong the evidence is. ${sessionLabel}.`} />
      {drivers.items.length === 0 ? (
        <p className="rounded-2xl border border-dashed border-surface-border/20 p-6 text-[13px] text-text-muted">{drivers.note ?? "No development met the evidence threshold for this session."}</p>
      ) : (
        <div className="space-y-6">
          {order.map(label => {
            const rows = drivers.groups[label] ?? [];
            if (rows.length === 0) return null;
            const meta = LABEL_META[label];
            return (
              <div key={label}>
                <p className="mb-2 flex flex-wrap items-baseline gap-x-3 text-[12px] font-semibold uppercase tracking-wide text-text-secondary">
                  {meta.text === "Confirmed" ? "Confirmed drivers" : meta.text === "Potential contributor" ? "Potential contributors" : "Commentary"}
                  <span className="text-[11px] font-normal normal-case tracking-normal text-text-muted">{meta.blurb}</span>
                </p>
                <ul className="space-y-3">{rows.map(it => <DriverRow key={it.id ?? it.headline} it={it} />)}</ul>
              </div>
            );
          })}
        </div>
      )}
      <div className="mt-4 flex flex-wrap items-center justify-between gap-2 text-[11.5px] text-text-muted">
        <span>{drivers.items.length > 0 && drivers.note ? drivers.note : drivers.method}</span>
        <Link href="/events" className={`inline-flex items-center gap-0.5 rounded-sm font-semibold text-[#6366F1] hover:opacity-80 ${FOCUS}`}>All events <ChevronRight className="h-3 w-3" aria-hidden="true" /></Link>
      </div>
    </section>
  );
}

// ── Investor implications ───────────────────────────────────────────────────────────────────────────────────────────

export function ImplicationsSection({ implications }: { implications: Implications }) {
  return (
    <section aria-labelledby="implications-title">
      <SectionTitle id="implications-title" title="Investor implications" note="Where attention is warranted, from verified sector moves. Not a recommendation." />
      {implications.items.length === 0 ? (
        <p className="rounded-2xl border border-dashed border-surface-border/20 p-5 text-[12.5px] text-text-muted">{implications.note ?? "No sector is tied to a verified development yet."}</p>
      ) : (
        <ul className="space-y-3">
          {implications.items.map(r => (
            <li key={r.sector} className="rounded-2xl border border-surface-border/10 bg-surface-card/60 p-4">
              <div className="flex items-center justify-between gap-3">
                <p className="text-[14px] font-semibold text-text-primary">{r.sector}</p>
                <p className="text-[13px]"><Move pct={r.verified_move_pct} /></p>
              </div>
              <p className="mt-1 text-[12.5px] leading-relaxed text-text-secondary">{r.why}</p>
              <ul className="mt-2 space-y-0.5">
                {r.developments.slice(0, 2).map(d => <li key={d.id ?? d.headline} className="truncate text-[11.5px] text-text-muted">{LABEL_META[d.evidence_label].text}: {cleanText(d.headline)}</li>)}
              </ul>
              {r.companies_mentioned.length > 0 && (
                <p className="mt-2 text-[11.5px] text-text-muted">
                  {r.companies_label}:{" "}
                  {r.companies_mentioned.map((s, i) => (
                    <span key={s}>{i > 0 && ", "}<Link href={`/companies/${s}`} className={`rounded-sm font-medium text-text-secondary hover:text-text-primary ${FOCUS}`}>{s}</Link></span>
                  ))}
                </p>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

// ── Next-session scenarios ──────────────────────────────────────────────────────────────────────────────────────────

const SCENARIO_TONE: Record<string, string> = {
  bullish: "border-emerald-500/25 bg-emerald-500/[0.05]",
  neutral: "border-surface-border/15 bg-text-primary/[0.025]",
  bearish: "border-rose-500/25 bg-rose-500/[0.05]",
};
const DIR_DOT: Record<string, string> = { positive: "bg-emerald-500", negative: "bg-rose-500", neutral: "bg-slate-400", contextual: "bg-[#6366F1]" };

export function ScenariosSection({ scenarios }: { scenarios: Scenarios }) {
  return (
    <section aria-labelledby="scenarios-title">
      <SectionTitle id="scenarios-title" title={`Next session: ${scenarios.target}`} note="Conditional scenarios, kept separate from the completed session. Not predictions." />
      {!scenarios.available || !scenarios.scenarios ? (
        <p className="rounded-2xl border border-dashed border-surface-border/20 p-5 text-[12.5px] text-text-muted">{scenarios.reason ?? "Scenarios are unavailable right now."}</p>
      ) : (
        <div className="space-y-3">
          {scenarios.scenarios.map(s => (
            <div key={s.key} className={`rounded-2xl border p-4 ${SCENARIO_TONE[s.key]}`}>
              <p className="text-[13px] font-bold text-text-primary">{s.title}</p>
              <p className="mt-1 text-[12.5px] leading-relaxed text-text-secondary">{s.condition}</p>
              <p className="mt-2 text-[11px] font-semibold uppercase tracking-wide text-text-muted">Observe</p>
              <ul className="mt-0.5 list-inside list-disc text-[12px] text-text-secondary marker:text-text-muted">{s.watch.map(w => <li key={w}>{w}</li>)}</ul>
            </div>
          ))}
          {scenarios.current_signals && scenarios.current_signals.length > 0 && (
            <div className="rounded-2xl border border-surface-border/10 p-4">
              <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-text-muted">Overnight readings now{scenarios.gift_nifty_status === "stale" ? " (GIFT Nifty is stale)" : ""}</p>
              <ul className="grid gap-x-4 gap-y-1.5 sm:grid-cols-2">
                {scenarios.current_signals.map(r => (
                  <li key={r.label} className="flex items-center gap-2 text-[12px] text-text-secondary">
                    <span aria-hidden="true" className={`h-2 w-2 shrink-0 rounded-full ${DIR_DOT[r.direction] ?? "bg-slate-400"}`} />
                    <span className="font-medium text-text-primary">{r.label}</span>
                    <span className="truncate text-text-muted">{r.reading}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {scenarios.catalysts && scenarios.catalysts.length > 0 && (
            <p className="text-[12px] leading-relaxed text-text-secondary"><span className="font-semibold text-text-primary">Scheduled catalysts: </span>{scenarios.catalysts.join("; ")}.</p>
          )}
        </div>
      )}
    </section>
  );
}

// ── Investor takeaway ───────────────────────────────────────────────────────────────────────────────────────────────

export function TakeawaySection({ takeaway }: { takeaway: Takeaway }) {
  return (
    <section aria-labelledby="takeaway-title" className="mt-10 rounded-3xl bg-gradient-to-br from-[#6366F1]/45 via-[#6366F1]/10 to-[#14B8A6]/45 p-px">
      <div className="rounded-[calc(1.5rem-1px)] bg-surface-card p-6 sm:p-7">
        <h2 id="takeaway-title" className="text-[19px] font-bold tracking-tight text-text-primary">Investor takeaway</h2>
        <div className="mt-4 grid gap-6 md:grid-cols-3">
          <div>
            <p className="mb-1.5 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-text-muted"><Layers className="h-3.5 w-3.5 text-[#6366F1]" aria-hidden="true" /> The development</p>
            {takeaway.development ? (
              <>
                <p className="text-[14px] font-semibold leading-snug text-text-primary">{cleanText(takeaway.development.headline)}</p>
                <p className="mt-1.5 text-[12.5px] leading-relaxed text-text-secondary">{takeaway.development.text}</p>
              </>
            ) : <p className="text-[12.5px] leading-relaxed text-text-secondary">No single development stands out for this session.</p>}
          </div>
          <div>
            <p className="mb-1.5 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-text-muted"><Compass className="h-3.5 w-3.5 text-amber-500" aria-hidden="true" /> Key uncertainty</p>
            <p className="text-[13px] leading-relaxed text-text-secondary">{takeaway.uncertainty}</p>
          </div>
          <div>
            <p className="mb-1.5 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-text-muted"><Target className="h-3.5 w-3.5 text-[#14B8A6]" aria-hidden="true" /> What to monitor</p>
            {takeaway.monitor.length > 0 ? (
              <ul className="space-y-1.5">{takeaway.monitor.map(m => <li key={m} className="text-[12.5px] leading-snug text-text-secondary">{m}</li>)}</ul>
            ) : <p className="text-[12.5px] text-text-secondary">Nothing specific is scheduled.</p>}
          </div>
        </div>
      </div>
    </section>
  );
}
