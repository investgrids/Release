import Link from "next/link";
import {
  BadgeCheck, BarChart3, CalendarCheck, CalendarClock, ChevronRight, CircleAlert, Fuel, Info, IndianRupee, Landmark, Lightbulb,
  MessageSquareQuote, Shuffle, TrendingDown, TrendingUp, ArrowDown, ArrowUp, type LucideIcon,
} from "lucide-react";
import { cleanText } from "@/lib/text";

// ── Types: the sections the Daily Brief API adds (all optional so an older backend response still renders) ──────────────────

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
  // Tag-derived rows (event sector tags); often empty because most events carry no sector tag.
  items: { sector: string; verified_move_pct: number | null; why: string; developments: { id: string | null; headline: string; evidence_label: EvidenceLabel }[];
           companies_mentioned: string[]; companies_label: string | null }[];
  note: string | null;
  sector_performance?: { available: boolean; leaders: { name: string; pct: number }[]; laggards: { name: string; pct: number }[]; as_of: string; source: string; note: string | null };
  exposure?: { variable: string; label: string; evidence: "verified" | "reported"; observed: string; source: string | null; observed_at: string | null;
               pressured: string[]; helped: string[]; why: string; basis: string }[];
  overlap?: { sector: string; verified_move_pct: number; variable: string; typical: "pressured" | "helped"; agrees: boolean; text: string }[];
  company_links?: { sector: string; companies: string[]; via: string[]; basis: string }[];
  sectors_mentioned?: { name: string; via: { basis: string; headline: string }[] }[];
  exposure_notes?: string[];
}
export interface Scenarios {
  available: boolean; reason?: string; target: string; generated_at: string;
  current_signals?: { label: string; reading: string | null; direction: string; detail: string | null; interpretation?: string | null; source?: string | null;
                      observed_at?: string | null; time_basis?: "quote time" | "session date" | "retrieved" | "prior session" | null }[];
  setup?: { title: string; text: string };
  scenarios?: { key: "bullish" | "neutral" | "bearish"; title: string; condition: string; confirmation?: string; watch: string[] }[];
  catalysts?: string[]; gift_nifty_status?: string | null; note?: string;
}
export interface Takeaway {
  development: { headline: string; evidence_label: EvidenceLabel; text: string; id: string | null } | null;
  uncertainty: string; monitor: string[];
}

// Brand: primary #6366F1 (indigo), secondary #14B8A6 (teal); status colours as the site uses them (emerald up, rose down, amber caution).
const FOCUS = "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#6366F1]";
const CARD = "rounded-2xl border border-surface-border/10 bg-surface-card/70 shadow-[0_1px_2px_rgba(15,23,42,0.04)]";
const SUBCARD = "rounded-xl border border-surface-border/10 bg-text-primary/[0.02] p-3.5";

const LABEL_META: Record<EvidenceLabel, { text: string; cls: string; Icon: LucideIcon }> = {
  confirmed_driver: { text: "Confirmed", Icon: BadgeCheck, cls: "border-[#14B8A6]/30 bg-[#14B8A6]/12 text-teal-800 dark:text-teal-300" },
  potential_contributor: { text: "Potential contributor", Icon: CircleAlert, cls: "border-amber-500/30 bg-amber-400/20 text-amber-800 dark:bg-amber-500/15 dark:text-amber-300" },
  commentary: { text: "Commentary", Icon: MessageSquareQuote, cls: "border-surface-border/20 bg-text-primary/[0.05] text-text-secondary" },
};

export function fmtIST(iso: string | null | undefined): string | null {
  if (!iso) return null;
  try {
    return new Date(iso).toLocaleString("en-IN", { timeZone: "Asia/Kolkata", day: "numeric", month: "short", hour: "numeric", minute: "2-digit", hour12: true }) + " IST";
  } catch {
    return null;
  }
}

function pctText(p: number): string {
  return `${p >= 0 ? "+" : ""}${p.toFixed(2)}%`;
}

function CardHeader({ icon: Icon, title, subtitle, right, info, titleId }: { icon: LucideIcon; title: string; subtitle?: string; right?: React.ReactNode; info?: string; titleId?: string }) {
  return (
    <div className="mb-4 flex items-start justify-between gap-3">
      <div className="flex min-w-0 items-start gap-3">
        <Icon className="mt-0.5 h-5 w-5 shrink-0 text-[#6366F1]" strokeWidth={1.75} aria-hidden="true" />
        <div className="min-w-0">
          <h2 id={titleId} className="flex items-center gap-1.5 text-[17px] font-bold leading-tight tracking-tight text-text-primary">
            {title}
            {info && <span title={info} className="inline-flex"><Info className="h-3.5 w-3.5 text-text-muted" aria-hidden="true" /><span className="sr-only">{info}</span></span>}
          </h2>
          {subtitle && <p className="mt-1 text-[12px] leading-snug text-text-muted">{subtitle}</p>}
        </div>
      </div>
      {right}
    </div>
  );
}

// ── What moved the market today? ───────────────────────────────────────────────────────────────────────────────────────

function DriverRow({ it }: { it: DriverItem }) {
  const meta = LABEL_META[it.evidence_label];
  const published = fmtIST(it.published_at);
  return (
    <li className="grid gap-x-4 gap-y-2 py-4 first:pt-0 sm:grid-cols-[8.75rem_minmax(0,1fr)_auto]">
      <div>
        <span className={`inline-flex items-center gap-1 rounded-md border px-2.5 py-1 text-[11.5px] font-semibold ${meta.cls}`}>
          <meta.Icon className="h-3 w-3" aria-hidden="true" /> {meta.text}
        </span>
      </div>
      <div className="min-w-0">
        <h3 className="text-[14px] font-semibold leading-snug text-text-primary">
          {it.links.event ? <Link href={it.links.event} className={`rounded-sm hover:text-[#6366F1] ${FOCUS}`}>{cleanText(it.headline)}</Link> : cleanText(it.headline)}
        </h3>
        <p className="mt-0.5 text-[11.5px] text-text-muted">{[it.source, published].filter(Boolean).join(" · ")}</p>
        <ul className="mt-1.5 space-y-0.5">
          {it.relevance.map((r, i) => <li key={i} className="text-[12px] leading-relaxed text-text-secondary">{r}</li>)}
        </ul>
        {(it.sectors.length > 0 || it.companies.length > 0) && (
          <div className="mt-2 flex flex-wrap items-center gap-1.5">
            {it.sectors.map(s => (
              <span key={s.name} className="inline-flex items-center gap-1.5 rounded-full border border-surface-border/15 px-2.5 py-0.5 text-[11px] text-text-secondary">
                {s.name} {s.verified_move_pct === null ? <span className="text-text-muted">no verified move</span> : <span className={`font-semibold tabular-nums ${s.verified_move_pct >= 0 ? "text-emerald-600 dark:text-emerald-400" : "text-rose-600 dark:text-rose-400"}`}>{pctText(s.verified_move_pct)}</span>}
              </span>
            ))}
            {it.companies.map(c => (
              <Link key={c.symbol} href={`/companies/${c.symbol}`} className={`inline-flex items-center gap-1 rounded-full border border-surface-border/15 px-2.5 py-0.5 text-[11px] text-text-secondary transition hover:text-text-primary ${FOCUS}`}>
                {c.symbol} <span className="text-text-muted">mentioned</span>
              </Link>
            ))}
          </div>
        )}
      </div>
      <div className="flex flex-col items-start gap-1 sm:items-end">
        {it.links.event && <Link href={it.links.event} className={`inline-flex items-center gap-0.5 whitespace-nowrap rounded-sm text-[11.5px] font-semibold text-[#6366F1] hover:opacity-80 ${FOCUS}`}>Event details <ChevronRight className="h-3 w-3" aria-hidden="true" /></Link>}
        {it.links.article && <Link href={it.links.article} className={`inline-flex items-center gap-0.5 whitespace-nowrap rounded-sm text-[11.5px] font-semibold text-text-secondary hover:text-text-primary ${FOCUS}`}>Read the analysis <ChevronRight className="h-3 w-3" aria-hidden="true" /></Link>}
      </div>
    </li>
  );
}

export function MarketDriversSection({ drivers, sessionLabel }: { drivers: MarketDrivers; sessionLabel: string }) {
  const ordered = [...(drivers.groups.confirmed_driver ?? []), ...(drivers.groups.potential_contributor ?? []), ...(drivers.groups.commentary ?? [])];
  return (
    <section aria-labelledby="drivers-title" className={`${CARD} min-w-0 p-5 sm:p-6`}>
      <CardHeader
        icon={CalendarCheck} title="What moved the market today?" titleId="drivers-title"
        subtitle={`Up to five developments, each shown once and labelled by how strong the evidence is. ${sessionLabel}`}
        right={<Link href="/events" className={`inline-flex shrink-0 items-center gap-0.5 rounded-sm text-[11.5px] font-semibold text-[#6366F1] hover:opacity-80 ${FOCUS}`}>All events <ChevronRight className="h-3 w-3" aria-hidden="true" /></Link>}
      />
      {ordered.length === 0 ? (
        <p className="rounded-xl border border-dashed border-surface-border/20 p-5 text-[13px] text-text-muted">{drivers.note ?? "No development met the evidence threshold for this session."}</p>
      ) : (
        <ul className="divide-y divide-surface-border/10">{ordered.map(it => <DriverRow key={it.id ?? it.headline} it={it} />)}</ul>
      )}
      <p className="mt-4 border-t border-surface-border/10 pt-3 text-[11px] leading-snug text-text-muted">
        {ordered.length > 0 && drivers.note ? `${drivers.note} ` : ""}{drivers.method}
      </p>
    </section>
  );
}

// ── Investor implications ───────────────────────────────────────────────────────────────────────────────────────────

const VARIABLE_ICON: Record<string, LucideIcon> = {
  crude_rising: Fuel, crude_falling: Fuel, rupee_stronger: IndianRupee, rupee_weaker: IndianRupee, yields_rising: Landmark, yields_falling: Landmark,
};
const EVIDENCE_BADGE: Record<string, string> = {
  verified: "border-[#14B8A6]/30 bg-[#14B8A6]/12 text-teal-800 dark:text-teal-300",
  reported: "border-amber-500/30 bg-amber-400/20 text-amber-800 dark:bg-amber-500/15 dark:text-amber-300",
};

function PerfBlock({ title, rows, tone, empty }: { title: string; rows: { name: string; pct: number }[]; tone: "up" | "down"; empty: string }) {
  const up = tone === "up";
  return (
    <div className={`rounded-xl border p-3 ${up ? "border-emerald-500/20 bg-emerald-500/[0.06]" : "border-rose-500/20 bg-rose-500/[0.06]"}`}>
      <p className={`mb-1.5 flex items-center gap-1.5 text-[12px] font-semibold ${up ? "text-emerald-700 dark:text-emerald-300" : "text-rose-700 dark:text-rose-300"}`}>
        {up ? <ArrowUp className="h-3 w-3" aria-hidden="true" /> : <ArrowDown className="h-3 w-3" aria-hidden="true" />} {title}
      </p>
      {rows.length === 0 ? <p className="text-[12px] text-text-muted">{empty}</p> : (
        <ul>{rows.map(r => (
          <li key={r.name} className="flex items-center justify-between border-b border-surface-border/10 py-1.5 text-[12.5px] last:border-0">
            <span className="text-text-secondary">{r.name}</span>
            <span className={`font-semibold tabular-nums ${up ? "text-emerald-600 dark:text-emerald-400" : "text-rose-600 dark:text-rose-400"}`}>{pctText(r.pct)}</span>
          </li>
        ))}</ul>
      )}
    </div>
  );
}

function SubTitle({ children, info, note }: { children: React.ReactNode; info?: string; note?: string }) {
  return (
    <div className="mb-2.5">
      <h3 className="flex items-center gap-1.5 text-[13px] font-bold text-text-primary">
        {children}
        {info && <span title={info} className="inline-flex"><Info className="h-3.5 w-3.5 text-text-muted" aria-hidden="true" /><span className="sr-only">{info}</span></span>}
      </h3>
      {note && <p className="mt-0.5 text-[11.5px] leading-snug text-text-muted">{note}</p>}
    </div>
  );
}

export function ImplicationsSection({ implications }: { implications: Implications }) {
  const perf = implications.sector_performance;
  const exposure = implications.exposure ?? [];
  const overlap = implications.overlap ?? [];
  const links = implications.company_links ?? [];
  const mentioned = implications.sectors_mentioned ?? [];
  const hasAny = !!(perf?.available || exposure.length || links.length || mentioned.length || implications.items.length);

  return (
    <section aria-labelledby="implications-title" className={`${CARD} min-w-0 p-5 sm:p-6`}>
      <CardHeader icon={BarChart3} title="Investor implications" titleId="implications-title" subtitle="Where attention is warranted, from verified sector moves. Not a recommendation."
        info="Verified performance and general exposure are kept apart: the first is observed, the second is background economics." />
      {!hasAny ? (
        <p className="rounded-xl border border-dashed border-surface-border/20 p-5 text-[12.5px] text-text-muted">{perf?.note ?? implications.note ?? "No sector information is available yet."}</p>
      ) : (
        <div className="space-y-3">
          {perf && (
            <div className={SUBCARD}>
              <SubTitle note={perf.available ? `As of ${perf.as_of}. ${perf.source}.` : undefined}>Verified sector performance</SubTitle>
              {!perf.available ? <p className="text-[12.5px] text-text-muted">{perf.note}</p> : (
                <div className="grid gap-3 sm:grid-cols-2">
                  <PerfBlock title="Sectors that rose" rows={perf.leaders} tone="up" empty="No tracked sector gained." />
                  <PerfBlock title="Sectors that fell" rows={perf.laggards} tone="down" empty="No tracked sector fell." />
                </div>
              )}
            </div>
          )}

          {(mentioned.length > 0 || links.length > 0) && (
            <div className={SUBCARD}>
              <SubTitle info="Sectors the developments name in their headline, in an event sector tag, or through a named company's sector in the company master."
                note="Based on what the articles name. This shows exposure to the news, not observed sector moves.">Sectors mentioned in today&apos;s developments</SubTitle>
              <div className="flex flex-wrap gap-2">
                {mentioned.map(m => <span key={m.name} className="rounded-full border border-surface-border/15 bg-surface-card px-3 py-1 text-[12px] text-text-secondary">{m.name}</span>)}
              </div>
              {links.length > 0 && (
                <p className="mt-2.5 text-[11.5px] text-text-muted">
                  Companies named:{" "}
                  {links.map((l, i) => (<span key={l.sector}>{i > 0 && "; "}{l.sector} (
                    {l.companies.map((s, j) => (<span key={s}>{j > 0 && ", "}<Link href={`/companies/${s}`} className={`rounded-sm font-medium text-text-secondary hover:text-text-primary ${FOCUS}`}>{s}</Link></span>))})</span>))}
                </p>
              )}
            </div>
          )}

          {exposure.length > 0 && (
            <div className={SUBCARD}>
              <SubTitle info="A short documented rule table of widely understood sensitivities. It is background economics, not an observation about these sectors."
                note="General economic sensitivities, not observed impacts.">Typical exposure by market variable</SubTitle>
              <ul className="space-y-3.5">
                {exposure.map(e => {
                  const Icon = VARIABLE_ICON[e.variable] ?? Info;
                  return (
                    <li key={e.variable}>
                      <div className="flex flex-wrap items-center gap-2">
                        <Icon className="h-4 w-4 text-amber-500" strokeWidth={1.75} aria-hidden="true" />
                        <p className="text-[13px] font-semibold text-text-primary">{e.label}</p>
                        <span className={`rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide ${EVIDENCE_BADGE[e.evidence] ?? ""}`}>{e.evidence === "verified" ? "Verified" : "Reported"}</span>
                      </div>
                      <p className="mt-1 text-[11.5px] leading-snug text-text-muted">
                        {cleanText(e.observed)}
                        {(e.source || e.observed_at) && <> · {[e.source, e.observed_at ? `retrieved ${fmtIST(e.observed_at)}` : null].filter(Boolean).join(" · ")}</>}
                      </p>
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {e.pressured.map(s => <span key={`p-${s}`} title="Typically pressured" className="inline-flex items-center gap-1.5 rounded-full border border-surface-border/15 bg-surface-card px-2.5 py-1 text-[11.5px] text-text-secondary"><span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-rose-500" />{s}<span className="sr-only"> (typically pressured)</span></span>)}
                        {e.helped.map(s => <span key={`h-${s}`} title="Typically helped" className="inline-flex items-center gap-1.5 rounded-full border border-surface-border/15 bg-surface-card px-2.5 py-1 text-[11.5px] text-text-secondary"><span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-emerald-500" />{s}<span className="sr-only"> (typically helped)</span></span>)}
                      </div>
                    </li>
                  );
                })}
              </ul>
              <p className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-text-muted">
                <span className="inline-flex items-center gap-1.5"><span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-rose-500" />typically pressured</span>
                <span className="inline-flex items-center gap-1.5"><span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-emerald-500" />typically helped</span>
              </p>
            </div>
          )}

          {overlap.length > 0 && (
            <details className={`${SUBCARD} group`}>
              <summary className={`cursor-pointer list-none text-[12.5px] font-semibold text-text-primary ${FOCUS} rounded-sm`}>
                Where moves matched or opposed typical exposure <span className="font-normal text-text-muted">({overlap.length})</span>
              </summary>
              <ul className="mt-2.5 space-y-2">
                {overlap.map(o => (
                  <li key={`${o.sector}-${o.variable}`} className="flex gap-2.5 text-[12px] leading-relaxed text-text-secondary">
                    <span aria-hidden="true" className={`mt-[6px] h-1.5 w-1.5 shrink-0 rounded-full ${o.agrees ? "bg-[#14B8A6]" : "bg-amber-500"}`} />
                    <span><span className="sr-only">{o.agrees ? "In line: " : "Against: "}</span>{o.text}</span>
                  </li>
                ))}
              </ul>
            </details>
          )}

          {implications.items.length > 0 && (
            <ul className="space-y-2">
              {implications.items.map(r => (
                <li key={r.sector} className={SUBCARD}>
                  <div className="flex items-center justify-between gap-3"><p className="text-[13px] font-semibold text-text-primary">{r.sector}</p>
                    {r.verified_move_pct !== null && <span className={`text-[12.5px] font-semibold tabular-nums ${r.verified_move_pct >= 0 ? "text-emerald-600 dark:text-emerald-400" : "text-rose-600 dark:text-rose-400"}`}>{pctText(r.verified_move_pct)}</span>}</div>
                  <p className="mt-1 text-[12px] leading-relaxed text-text-secondary">{r.why}</p>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </section>
  );
}

// ── Next session (conditional, separate from the completed session) ─────────────────────────────────────────────────────

const DIR_VALUE: Record<string, string> = { positive: "text-emerald-600 dark:text-emerald-400", negative: "text-rose-600 dark:text-rose-400" };

/** '₹-1,708 Cr' -> '-₹1,708 Cr'; '5/10 positive' -> '5/10' (the interpretation line already says what it means). */
function fmtReading(r: string | null): string {
  if (!r) return "—";
  return r.replace(/^₹-/, "-₹").replace(/\s+positive$/i, "");
}

function timeLabel(s: NonNullable<Scenarios["current_signals"]>[number]): string {
  const src = s.source ?? "";
  if (s.time_basis === "quote time" && s.observed_at) return `${src} · ${fmtIST(s.observed_at)}`;
  if (s.time_basis === "session date" && s.observed_at) {
    const m = s.observed_at.match(/^(\d{1,2})-([A-Za-z]{3})-(\d{4})$/);
    return `${src} · ${m ? `${m[1]} ${m[2]} ${m[3]}` : s.observed_at} (session figures)`;
  }
  if (s.time_basis === "prior session") return `${src} · previous session`;
  if (s.observed_at) return `${src} · retrieved ${fmtIST(s.observed_at)}`;
  return src;
}

const PATH_ICON: Record<string, { Icon: LucideIcon; cls: string }> = {
  bullish: { Icon: TrendingUp, cls: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400" },
  neutral: { Icon: Shuffle, cls: "bg-text-primary/[0.06] text-text-secondary" },
  bearish: { Icon: TrendingDown, cls: "bg-rose-500/10 text-rose-600 dark:text-rose-400" },
};

export function ScenariosSection({ scenarios }: { scenarios: Scenarios }) {
  return (
    <section aria-labelledby="scenarios-title" className={`${CARD} p-5 sm:p-6`}>
      <CardHeader icon={CalendarClock} title={`Next session: ${scenarios.target}`} titleId="scenarios-title" subtitle="Based on current overnight signals. Kept separate from the completed session. Not predictions."
        right={<span className="shrink-0 rounded-md bg-[#6366F1]/10 px-2.5 py-1 text-[11.5px] font-semibold text-[#4f46e5] dark:text-indigo-300">Conditional outlook</span>} />
      {!scenarios.available || !scenarios.scenarios ? (
        <p className="rounded-xl border border-dashed border-surface-border/20 p-5 text-[12.5px] text-text-muted">{scenarios.reason ?? "Scenarios are unavailable right now."}</p>
      ) : (
        <>
          <div className="grid gap-4 lg:grid-cols-[1.15fr_1fr_1.25fr]">
            <div className={SUBCARD}>
              <SubTitle note="Latest available values and time/source.">Current overnight readings</SubTitle>
              <ul className="grid gap-2 sm:grid-cols-2">
                {(scenarios.current_signals ?? []).map(s => (
                  <li key={s.label} className="rounded-lg border border-surface-border/10 bg-surface-card p-2.5">
                    <p className="text-[11px] font-semibold text-text-primary">{s.label}</p>
                    <p className={`mt-0.5 text-[16px] font-bold tabular-nums ${DIR_VALUE[s.direction] ?? "text-text-primary"}`}>{fmtReading(s.reading)}</p>
                    {s.interpretation && <p className="text-[11px] leading-snug text-text-secondary">{s.interpretation}</p>}
                    <p className="mt-0.5 text-[10.5px] leading-snug text-text-muted">{timeLabel(s)}</p>
                  </li>
                ))}
              </ul>
              {scenarios.gift_nifty_status === "stale" && <p className="mt-2 text-[11px] text-amber-700 dark:text-amber-300">The GIFT Nifty reading is stale.</p>}
            </div>

            <div className={SUBCARD}>
              <SubTitle>Current setup</SubTitle>
              {scenarios.setup && (
                <>
                  <p className="text-[15px] font-semibold text-[#4f46e5] dark:text-indigo-300">{scenarios.setup.title}</p>
                  <p className="mt-1.5 text-[12.5px] leading-relaxed text-text-secondary">{scenarios.setup.text}</p>
                </>
              )}
            </div>

            <div className={SUBCARD}>
              <SubTitle>Three possible paths <span className="font-normal text-text-muted">(conditional)</span></SubTitle>
              <ul className="space-y-3">
                {scenarios.scenarios.map(s => {
                  const { Icon, cls } = PATH_ICON[s.key];
                  return (
                    <li key={s.key} className="flex gap-3">
                      <span className={`mt-0.5 inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${cls}`}><Icon className="h-4 w-4" aria-hidden="true" /></span>
                      <div className="min-w-0">
                        <p className="text-[12.5px] font-bold text-text-primary">{s.title}</p>
                        <p className="mt-0.5 text-[12px] leading-relaxed text-text-secondary">{s.condition}</p>
                        {s.confirmation && <p className="mt-1 text-[11px] leading-snug text-text-muted">Confirmation to watch: {s.confirmation}</p>}
                      </div>
                    </li>
                  );
                })}
              </ul>
            </div>
          </div>
          {scenarios.catalysts && scenarios.catalysts.length > 0 && (
            <p className="mt-4 text-[12px] leading-relaxed text-text-secondary"><span className="font-semibold text-text-primary">Scheduled catalysts: </span>{scenarios.catalysts.join("; ")}.</p>
          )}
          {scenarios.note && <p className="mt-2 text-[11px] text-text-muted">{scenarios.note}</p>}
        </>
      )}
    </section>
  );
}

// ── Investor takeaway ───────────────────────────────────────────────────────────────────────────────────────────────

export function TakeawaySection({ takeaway }: { takeaway: Takeaway }) {
  return (
    <section aria-labelledby="takeaway-title" className={`${CARD} p-5 sm:p-6`}>
      <div className="flex items-center gap-3">
        <Lightbulb className="h-5 w-5 text-amber-500" strokeWidth={1.75} aria-hidden="true" />
        <h2 id="takeaway-title" className="text-[17px] font-bold tracking-tight text-text-primary">Investor takeaway</h2>
      </div>
      <div className="mt-4 grid gap-x-10 gap-y-5 md:grid-cols-3">
        <div>
          <p className="mb-1.5 text-[12px] font-semibold text-text-primary">The development</p>
          {takeaway.development ? (
            <>
              <p className="text-[13px] font-semibold leading-snug text-text-primary">{cleanText(takeaway.development.headline)}</p>
              <p className="mt-1.5 text-[12.5px] leading-relaxed text-text-secondary">{takeaway.development.text}</p>
            </>
          ) : <p className="text-[12.5px] leading-relaxed text-text-secondary">No single development stands out for this session.</p>}
        </div>
        <div>
          <p className="mb-1.5 text-[12px] font-semibold text-text-primary">Key uncertainty</p>
          <p className="text-[12.5px] leading-relaxed text-text-secondary">{takeaway.uncertainty}</p>
        </div>
        <div>
          <p className="mb-1.5 text-[12px] font-semibold text-text-primary">What to monitor</p>
          {takeaway.monitor.length > 0 ? (
            <ul className="list-disc space-y-1 pl-4 marker:text-text-muted">{takeaway.monitor.map(m => <li key={m} className="text-[12.5px] leading-snug text-text-secondary">{m}</li>)}</ul>
          ) : <p className="text-[12.5px] text-text-secondary">Nothing specific is scheduled.</p>}
        </div>
      </div>
    </section>
  );
}
