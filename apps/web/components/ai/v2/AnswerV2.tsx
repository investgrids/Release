"use client";

// AI Search V2 answer renderer (Step 6). One component per answer kind, all driven by answer_availability (the Step 5 contract). White surfaces, one calm hierarchy:
// what is the answer, what supports it, what is known versus not established, who and what matters, what to look at next. Empty sections do not render.
import { useState } from "react";
import Link from "next/link";
import { AlertCircle, ArrowRight, Lightbulb, ListChecks, RotateCcw, Sparkles } from "lucide-react";
import { Avatar, ChangePill, IconTile, KIND_BADGE, KIND_DOT, RangeBar, Sparkline } from "./visuals";
import { AISearchFeedback } from "@/components/ai/AISearchFeedback";
import { AIDisclaimer } from "@/components/ai/AIDisclaimer";
import {
  EVIDENCE_TYPE_LABEL, authorizedVerdict, evidenceStrength, followUps, internalSourceLink, norm, partialNotice, resolveKind, temporaryCopy, unavailableCopy,
  type V2IndexEntry, type V2Result, type V2Snapshot,
} from "./contract";

const CARD = "rounded-2xl border border-surface-border/10 bg-surface-card shadow-[0_1px_2px_rgba(16,24,40,0.05)]";
const LABEL = "text-[11px] font-semibold uppercase tracking-[0.08em] text-text-muted";
const BODY = "text-[15px] leading-7 text-text-secondary";

function Section({ label, children, testId, icon }: { label: string; children: React.ReactNode; testId?: string; icon?: React.ComponentType<{ className?: string }> }) {
  return (
    <section className="space-y-3" data-testid={testId}>
      {icon ? (
        <div className="flex items-center gap-2.5"><IconTile icon={icon} /><h2 className="text-[15px] font-semibold text-text-primary">{label}</h2></div>
      ) : (
        <h2 className={LABEL}>{label}</h2>
      )}
      {children}
    </section>
  );
}

const isDup = (text: string, others: string[]) => {
  const n = norm(text);
  return !n || others.some((o) => { const m = norm(o); return m === n || (m.length > 20 && (m.includes(n) || n.includes(m))); });
};

// ── evidence ──────────────────────────────────────────────────────────────────────────────────────────────────────────────

interface Listed { key: string; title: string; kind: string; source?: string; date?: string; cited: boolean }

function listedEvidence(r: V2Result): Listed[] {
  const cited = new Set((r.evidence_index ?? []).filter((e) => (r.claim_sources ?? []).some((c) => c.sources.includes(e.id))).map((e) => norm(e.title)));
  const out: Listed[] = [];
  (r.related_events ?? []).forEach((e) => out.push({ key: `e-${e.id}`, title: e.title, kind: "event", source: e.source, date: e.date, cited: cited.has(norm(e.title)) }));
  (r.news ?? []).forEach((n) => out.push({ key: `n-${n.id}`, title: n.headline, kind: "news", source: n.source, date: n.published_at, cited: cited.has(norm(n.headline)) }));
  (r.policies ?? []).forEach((p) => out.push({ key: `p-${p.id}`, title: p.title, kind: "policy", source: p.ministry, date: p.status, cited: cited.has(norm(p.title)) }));
  return out;
}

function SourceChips({ ids, index }: { ids: string[]; index: Map<string, V2IndexEntry> }) {
  const seen = new Set<string>();
  const chips = ids.map((id) => index.get(id)).filter((e): e is V2IndexEntry => !!e).map((e) => `${e.source ? e.source + " · " : ""}${EVIDENCE_TYPE_LABEL[e.kind] ?? "Evidence"}`).filter((t) => !seen.has(t) && !!seen.add(t));
  if (!chips.length) return null;
  return (
    <span className="mt-1.5 flex flex-wrap gap-1.5" data-testid="source-chips">
      {chips.map((c) => <span key={c} className="rounded-md border border-surface-border/10 px-1.5 py-0.5 text-[11px] text-text-muted">{c}</span>)}
    </span>
  );
}

function EvidenceRow({ e }: { e: Listed }) {
  return (
    <li className="px-4 py-3">
      <p className="text-[13.5px] font-medium leading-snug text-text-primary">{e.title}</p>
      <p className="mt-1 text-[12px] text-text-muted">
        {[EVIDENCE_TYPE_LABEL[e.kind], e.source, e.date].filter(Boolean).join(" · ")}
        {e.cited && <span className="ml-2 text-violet-600">Used in this answer</span>}
      </p>
    </li>
  );
}

const EVIDENCE_SHOWN = 5;

/** The items the answer actually used come first; the rest sit behind one disclosure so a long list never outweighs the answer. */
function EvidenceList({ items, count }: { items: Listed[]; count: number }) {
  if (!items.length) return null;
  const ordered = [...items.filter((e) => e.cited), ...items.filter((e) => !e.cited)];
  const head = ordered.slice(0, EVIDENCE_SHOWN);
  const rest = ordered.slice(EVIDENCE_SHOWN);
  return (
    <Section label={`Evidence reviewed (${count})`} testId="evidence-list">
      <ul className={`${CARD} divide-y divide-surface-border/10`}>
        {head.map((e) => <EvidenceRow key={e.key} e={e} />)}
        {rest.length > 0 && (
          <li>
            <details>
              <summary className="cursor-pointer px-4 py-3 text-[13px] font-medium text-violet-600">Show {rest.length} more</summary>
              <ul className="divide-y divide-surface-border/10 border-t border-surface-border/10">{rest.map((e) => <EvidenceRow key={e.key} e={e} />)}</ul>
            </details>
          </li>
        )}
      </ul>
    </Section>
  );
}

function FollowUps({ questions, onAsk, label = "Where to look next" }: { questions: string[]; onAsk: (q: string) => void; label?: string }) {
  if (!questions.length) return null;
  return (
    <Section label={label} testId="follow-ups">
      <ul className="space-y-2">
        {questions.map((q) => (
          <li key={q}>
            <button type="button" onClick={() => onAsk(q)} className="w-full rounded-xl border border-surface-border/10 bg-surface-card px-4 py-3 text-left text-[14px] leading-snug text-text-primary transition hover:border-violet-500/40">
              {q}
            </button>
          </li>
        ))}
      </ul>
    </Section>
  );
}

const CRUMB: Record<string, string> = { comparison: "Comparison", sector: "Sector and event impact", company: "Company", market: "Market" };

/** Breadcrumb ("AI Search / Comparison"), then the question as the page title. */
function Header({ r, kindLabel }: { r: V2Result; kindLabel: string }) {
  const crumb = (r.specialist && CRUMB[r.specialist]) || kindLabel;
  return (
    <header className="space-y-2" data-testid="answer-header">
      <p className="text-[12.5px] text-text-muted"><span>AI Search</span><span className="mx-1.5">/</span><span data-testid="crumb">{crumb}</span></p>
      <h1 className="text-[26px] font-semibold leading-tight tracking-tight text-text-primary sm:text-[30px]">{r.query}</h1>
    </header>
  );
}

function Footer({ r, onFeedbackMeta }: { r: V2Result; onFeedbackMeta?: Meta }) {
  return (
    <footer className="space-y-4 pt-2">
      {onFeedbackMeta && r.response_id ? <AISearchFeedback meta={onFeedbackMeta} /> : null}
      <AIDisclaimer />
    </footer>
  );
}

type Meta = { responseId: string | null; query: string; specialist?: string | null; schemaVersion?: string | null; cached: boolean; latencyMs: number | null; provider: string | null };

interface Props {
  result: V2Result;
  onFollowUp: (q: string) => void;
  onRetry?: () => void;
  /** Clears the answer and returns to an empty search. */
  onNewSearch?: () => void;
  feedbackMeta?: Meta;
  /** Today's example questions, offered as next steps on a state that cannot answer. */
  nextQuestions?: string[];
}

// ── comparison ────────────────────────────────────────────────────────────────────────────────────────────────────────────

const compared = (r: V2Result) => (r.specialist === "comparison" ? (r.companies ?? []).filter((c) => c.symbol && c.name).slice(0, 3) : []);
const inr = (n: number) => `₹${n.toLocaleString("en-IN", { minimumFractionDigits: 1, maximumFractionDigits: 1 })}`;
const pe1 = (n: number) => n.toFixed(1);
const pb2 = (n: number) => n.toFixed(2);
/** Market cap arrives in INR crore. */
const capText = (cr: number) => (cr >= 100000 ? `₹${(cr / 100000).toFixed(2)} lakh Cr` : `₹${cr.toLocaleString("en-IN", { maximumFractionDigits: 0 })} Cr`);

type Rel = "lower" | "higher" | null;
/** How each company's multiple sits against the other compared companies. A multiple has no good or bad value on its own, so this only ever says lower or higher than the others, and says nothing for a single
 * company or for equal values. A lower multiple is a cheaper valuation, not automatically a better company. */
function relativeMultiples(cs: { symbol: string; snapshot?: V2Snapshot | null }[], key: "pe" | "pb"): Map<string, Rel> {
  const vals = cs.map((c) => [c.symbol, c.snapshot?.[key]] as const).filter((x): x is readonly [string, number] => typeof x[1] === "number");
  const out = new Map<string, Rel>();
  if (vals.length < 2) return out;
  const lo = Math.min(...vals.map((v) => v[1])), hi = Math.max(...vals.map((v) => v[1]));
  if (lo === hi) return out;
  vals.forEach(([sym, v]) => out.set(sym, v === lo ? "lower" : v === hi ? "higher" : null));
  return out;
}
const REL_CHIP: Record<string, string> = {
  lower: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
  higher: "bg-amber-500/10 text-amber-700 dark:text-amber-300",
  none: "bg-sky-500/10 text-sky-700 dark:text-sky-300",
};

/** A multiple as a tinted chip. Colour is relative (lower/higher than the compared company) and is always also written out. */
function Multiple({ label, value, rel }: { label: string; value: string; rel: Rel | undefined }) {
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-[12px] ${REL_CHIP[rel ?? "none"]}`} data-rel={rel ?? "none"}>
      {label} <b className="tabular-nums">{value}</b>{rel && <span className="text-[11px] font-medium opacity-90">· {rel}</span>}
    </span>
  );
}

/** Side-by-side, built only from fields the contract carries: live price and move, the valuation figures the answer was given, and which kinds of evidence exist for each company. */
const initials = (name: string) => name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]).join("").toUpperCase();

/** Change over the last five sessions from the daily closes the answer already carries. Needs at least two closes; otherwise there is no figure. */
const fiveDay = (chart?: number[] | null) => {
  const c = (chart ?? []).filter((n) => typeof n === "number" && n > 0);
  if (c.length < 2) return null;
  const pct = (c[c.length - 1] / c[0] - 1) * 100;
  return { text: `${pct >= 0 ? "+" : ""}${pct.toFixed(1)}%`, up: pct >= 0 };
};

/** The company's own latest sourced development: its first claim that rests on a news item, event or filing and does not also name another compared company. */
function latestDevelopment(r: V2Result, c: { symbol: string; name: string }, others: { symbol: string; name: string }[], nums: Map<string, number>) {
  const kind = new Map((r.evidence_index ?? []).map((e) => [e.id, e.kind]));
  const mentions = (t: string, x: { symbol: string; name: string }) => norm(t).includes(norm(x.name)) || norm(t).split(" ").includes(norm(x.symbol));
  const hit = (r.claim_sources ?? []).find((cl) =>
    (cl.status ?? "ok") === "ok" && cl.company === c.symbol && cl.sources.some((id) => ["news", "event", "announcement", "policy"].includes(kind.get(id) ?? "")) && !others.some((o) => mentions(cl.claim, o)));
  if (!hit) return null;
  const marks = Array.from(new Set(hit.sources.map((id) => nums.get(id)).filter((n): n is number => !!n))).sort((a, b) => a - b);
  return { text: hit.claim, marks };
}

function ComparisonTable({ r }: { r: V2Result }) {
  const cs = compared(r);
  if (cs.length < 2) return null;
  const nums = evidenceNumbers(r, listedEvidence(r));
  const relPe = relativeMultiples(cs, "pe");
  const relPb = relativeMultiples(cs, "pb");
  const cov = r.conclusion_scope?.coverage ?? {};
  const has = (sym: string, k: "valuation" | "operating") => (cov[sym] ? (cov[sym][k] ? "Available" : "Not yet available") : null);
  const rows: [string, (c: (typeof cs)[number]) => React.ReactNode][] = [
    ["Latest development", (c) => {
      const d = latestDevelopment(r, c, cs.filter((o) => o.symbol !== c.symbol), nums);
      return d ? <span>{d.text}{d.marks.length > 0 && <span className="ml-1 tabular-nums text-text-muted">{d.marks.map((n) => `[${n}]`).join(" ")}</span>}</span> : "—";
    }],
    ["Price reaction", (c) => {
      const f = fiveDay(c.chart);
      return f ? <span className="flex flex-wrap items-center gap-2"><ChangePill text={f.text} up={f.up} /><span className="text-[11.5px] text-text-muted">5-day</span><Sparkline data={c.chart} w={64} h={22} /></span> : "—";
    }],
    ["Latest price", (c) => (c.price ? <span className="tabular-nums">₹{c.price}</span> : "—")],
    ["Today", (c) => (c.change ? <ChangePill text={c.change} up={!!c.positive} /> : "—")],
    ["P/E", (c) => (c.snapshot?.pe != null ? <Multiple label="" value={pe1(c.snapshot.pe)} rel={relPe.get(c.symbol)} /> : "—")],
    ["P/B", (c) => (c.snapshot?.pb != null ? <Multiple label="" value={pb2(c.snapshot.pb)} rel={relPb.get(c.symbol)} /> : "—")],
    ["Valuation evidence", (c) => has(c.symbol, "valuation") ?? "—"],
    ["Operating results", (c) => has(c.symbol, "operating") ?? "—"],
  ];
  const visible = rows.filter(([, f]) => cs.some((c) => f(c) !== "—"));
  const anyRel = relPe.size > 0 || relPb.size > 0;
  return (
    <div data-testid="comparison">
    <div className="overflow-x-auto rounded-xl border border-surface-border/10" data-testid="comparison-table">
      <table className="w-full table-fixed text-left text-[12.5px] sm:text-[13.5px]">
        <thead>
          <tr className="border-b border-surface-border/10">
            <th scope="col" className="w-[30%] px-3 py-3 text-[12px] font-medium text-text-muted sm:px-4">Factor</th>
            {cs.map((c) => (
              <th key={c.symbol} scope="col" className="px-3 py-3 sm:px-4">
                <div className="flex items-center gap-2.5">
                  <span className="hidden sm:block"><Avatar name={c.name} /></span>
                  <div className="min-w-0">
                    <Link href={`/companies/${encodeURIComponent(c.symbol)}`} className="font-semibold text-text-primary hover:text-violet-600">{c.name}</Link>
                    <span className="block text-[11.5px] font-normal text-text-muted">NSE: {c.symbol}</span>
                  </div>
                </div>
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-surface-border/10">
          {visible.map(([label, f]) => (
            <tr key={label} className="transition-colors hover:bg-violet-500/[0.03]">
              <th scope="row" className="px-3 py-2.5 text-[12.5px] font-medium text-text-primary sm:px-4 sm:text-[13px]">{label}</th>
              {cs.map((c) => <td key={c.symbol} className="break-words px-3 py-2.5 align-top text-text-secondary sm:px-4">{f(c)}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
    {anyRel && <p className="mt-2 text-[11.5px] leading-4 text-text-muted" data-testid="multiple-legend">Colour compares the companies in this table: green is the lower multiple, amber the higher. A lower multiple is a cheaper valuation, not automatically a better company.</p>}
    </div>
  );
}

// ── right rail ────────────────────────────────────────────────────────────────────────────────────────────────────────────

function RailCard({ title, testId, children }: { title: string; testId: string; children: React.ReactNode }) {
  return (
    <section className={`${CARD} p-4`} data-testid={testId}>
      <h2 className="mb-3 text-[14px] font-semibold text-text-primary">{title}</h2>
      {children}
    </section>
  );
}

/** Identity and live figures for the companies in the answer. Only fields the contract carries; a figure that was not fetched is simply not listed. */
function EntitySnapshot({ r }: { r: V2Result }) {
  const cs = (r.companies ?? []).filter((c) => c.symbol && c.name).slice(0, 3);
  if (!cs.length) return null;
  const comparison = r.specialist === "comparison";
  return (
    <RailCard title="Entity snapshot" testId="entity-snapshot">
      <ul className="space-y-4">
        {cs.map((c) => {
          const s = c.snapshot ?? {};
          const price = c.price ? Number.parseFloat(c.price.replace(/,/g, "")) : null;
          return (
            <li key={c.symbol} className="rounded-xl border border-surface-border/10 p-3 transition hover:border-violet-500/30">
              <div className="flex items-center gap-3">
                <Avatar name={c.name} />
                <div className="min-w-0 flex-1">
                  <Link href={`/companies/${encodeURIComponent(c.symbol)}`} className="block truncate text-[14px] font-semibold text-text-primary hover:text-violet-600">{c.name}</Link>
                  <p className="flex flex-wrap items-center gap-x-2 text-[11.5px] text-text-muted"><span>NSE: {c.symbol}</span>{s.sector && <span className="rounded-md bg-slate-500/10 px-1.5 py-0.5 text-[11px] font-medium text-text-secondary" data-testid="sector-chip">{s.sector}</span>}</p>
                </div>
                <Sparkline data={c.chart} w={72} h={28} />
              </div>
              {c.price && (
                <div className="mt-3 flex items-center justify-between gap-2">
                  <p className="text-[20px] font-semibold tabular-nums tracking-tight text-text-primary">₹{c.price}</p>
                  {c.change && <ChangePill text={c.change} up={!!c.positive} />}
                </div>
              )}
              {s.market_cap_cr != null && (
                <div className="mt-3 flex items-center justify-between text-[12.5px]"><span className="text-text-muted">Market cap</span><span className="font-semibold tabular-nums text-text-primary" data-testid="market-cap">{capText(s.market_cap_cr)}</span></div>
              )}
              {s.week52_low != null && s.week52_high != null && (
                <div className="mt-3">
                  <p className="mb-1.5 text-[11.5px] font-medium text-text-muted">52-week range</p>
                  <RangeBar low={s.week52_low} high={s.week52_high} price={price} fmt={inr} />
                </div>
              )}
              {!comparison && c.reason && <p className="mt-3 text-[12.5px] leading-5 text-text-muted">{c.reason}</p>}
            </li>
          );
        })}
      </ul>
    </RailCard>
  );
}

/** Sectors the answer names. Companies live in the entity snapshot. */
function SectorsCard({ r }: { r: V2Result }) {
  const sectors = (r.sectors ?? []).filter((s) => s.name);
  if (!sectors.length) return null;
  return (
    <RailCard title="Sectors involved" testId="involves">
      <ul className="divide-y divide-surface-border/10">
        {sectors.map((s) => (
          <li key={s.name} className="py-2.5 first:pt-0 last:pb-0">
            <p className="text-[13.5px] font-semibold text-text-primary">{s.name}</p>
            {s.explanation && <p className="mt-0.5 text-[12.5px] leading-5 text-text-muted">{s.explanation}</p>}
          </li>
        ))}
      </ul>
    </RailCard>
  );
}

/** Which kinds of evidence were found. Describes the evidence, never how likely the answer is to be right, and carries no score. */
function CoverageCard({ r }: { r: V2Result }) {
  const s = evidenceStrength(r);
  if (!s) return null;
  const rows = [...s.found.map((k) => [k, true] as const), ...s.missing.map((k) => [k, false] as const)];
  return (
    <RailCard title="Evidence coverage" testId="evidence-coverage">
      <p className="mb-3 text-[12.5px] text-text-secondary">{s.found.length} of {rows.length} kinds of evidence found</p>
      <ul className="flex flex-wrap gap-2 text-[12.5px]">
        {rows.map(([k, ok]) => (
          <li key={k} className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 ${ok ? "border-emerald-500/25 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300" : "border-surface-border/10 text-text-muted"}`}>
            <span aria-hidden className="text-[10px]">{ok ? "✓" : "–"}</span>
            <span>{k.charAt(0).toUpperCase() + k.slice(1)}</span>
            <span className="sr-only">{ok ? "found" : "not available"}</span>
          </li>
        ))}
      </ul>
      <p className="mt-3 text-[11.5px] leading-4 text-text-muted">This describes the evidence, not how likely the answer is to be right.</p>
    </RailCard>
  );
}

const SOURCE_ONE: Record<string, string> = { event: "market event", news: "news article", policy: "policy item", announcement: "exchange filing", context: "live data point" };
const SOURCE_MANY: Record<string, string> = { event: "market events", news: "news articles", policy: "policy items", announcement: "exchange filings", context: "live data points" };

function SourcesCard({ items }: { items: Listed[] }) {
  if (!items.length) return null;
  const kinds = Array.from(new Set(items.map((e) => e.kind)));
  return (
    <RailCard title="Sources" testId="sources-summary">
      <ul className="space-y-2.5">
        {kinds.map((k) => {
          const rows = items.filter((e) => e.kind === k);
          const names = Array.from(new Set(rows.map((e) => e.source).filter(Boolean))).slice(0, 4).join(", ");
          return (
            <li key={k} className="flex gap-2.5">
              <span aria-hidden className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${KIND_DOT[k] ?? "bg-slate-400"}`} />
              <div className="min-w-0">
                <p className="text-[13px] font-medium text-text-primary">{rows.length} {(rows.length === 1 ? SOURCE_ONE : SOURCE_MANY)[k] ?? "evidence items"}</p>
                {names && <p className="text-[12px] text-text-muted">{names}</p>}
              </div>
            </li>
          );
        })}
      </ul>
    </RailCard>
  );
}

function MethodologyRow() {
  return (
    <Link href="/ai-methodology" className={`${CARD} flex items-center justify-between px-4 py-3 text-[14px] font-semibold text-text-primary transition hover:border-violet-500/40`} data-testid="methodology-link">
      <span className="flex items-center gap-2.5"><IconTile icon={Sparkles} tone="sky" />Methodology</span><ArrowRight className="h-4 w-4 text-text-muted" aria-hidden />
    </Link>
  );
}

// ── evidence table ────────────────────────────────────────────────────────────────────────────────────────────────────────

const fmtDate = (s?: string) => {
  if (!s) return "";
  const d = new Date(s);
  return Number.isNaN(+d) || !/\d{4}-\d{2}-\d{2}/.test(s) ? s : d.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric", timeZone: "Asia/Kolkata" });
};
const TABLE_SHOWN = 6;

/** The order evidence is numbered in: items the answer used first. The table rows and every [n] marker use this one ordering. */
const orderedEvidence = (items: Listed[]) => [...items.filter((e) => e.cited), ...items.filter((e) => !e.cited)];

/** Evidence-index id -> the [n] it carries in the table. Matched by title, because the index and the listed items come from different arrays. */
function evidenceNumbers(r: V2Result, items: Listed[]): Map<string, number> {
  const pos = new Map(orderedEvidence(items).map((e, i) => [norm(e.title), i + 1]));
  const out = new Map<string, number>();
  (r.evidence_index ?? []).forEach((e) => { const n = pos.get(norm(e.title)); if (n) out.set(e.id, n); });
  return out;
}

/** The sources behind the answer as a numbered table (number, date, source, headline). Items the answer used come first. Plain text; nothing links off-site. */
function KeyEvidenceTable({ items, count }: { items: Listed[]; count: number }) {
  const [all, setAll] = useState(false);
  if (!items.length) return null;
  const ordered = orderedEvidence(items);
  const shown = all ? ordered : ordered.slice(0, TABLE_SHOWN);
  return (
    <section className="space-y-3" data-testid="evidence-list">
      <div className="flex items-center gap-2.5"><IconTile icon={ListChecks} tone="sky" /><h2 className="text-[15px] font-semibold text-text-primary">Key evidence and sources <span className="font-normal text-text-muted">({count})</span></h2></div>
      <div className={`${CARD} overflow-x-auto`}>
        <table className="w-full text-left text-[13px]">
          <thead>
            <tr className="border-b border-surface-border/10 text-[11.5px] font-medium text-text-muted">
              <th scope="col" className="w-10 px-4 py-2.5">#</th>
              <th scope="col" className="hidden w-28 px-2 py-2.5 sm:table-cell">Date</th>
              <th scope="col" className="hidden w-40 px-2 py-2.5 sm:table-cell">Source</th>
              <th scope="col" className="px-2 py-2.5">Headline</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-surface-border/10">
            {shown.map((e, i) => (
              <tr key={e.key} className="align-top">
                <td className="px-4 py-2.5 tabular-nums text-text-muted">[{i + 1}]</td>
                <td className="hidden px-2 py-2.5 text-text-secondary sm:table-cell">{fmtDate(e.date) || "—"}</td>
                <td className="hidden px-2 py-2.5 text-text-secondary sm:table-cell">{e.source || EVIDENCE_TYPE_LABEL[e.kind]}</td>
                <td className="px-2 py-2.5 text-text-primary">
                  {e.title}
                  <span className="mt-0.5 block text-[11.5px] text-text-muted sm:hidden">{[e.source, fmtDate(e.date)].filter(Boolean).join(" · ")}</span>
                  <span className="mt-1 flex flex-wrap items-center gap-1.5"><span className={`rounded-md px-1.5 py-0.5 text-[11px] font-medium ${KIND_BADGE[e.kind] ?? KIND_BADGE.context}`}>{EVIDENCE_TYPE_LABEL[e.kind]}</span>{e.cited && <span className="rounded-md bg-violet-500/10 px-1.5 py-0.5 text-[11px] font-medium text-violet-700">Used in this answer</span>}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {ordered.length > TABLE_SHOWN && (
          <button type="button" onClick={() => setAll((v) => !v)} className="w-full border-t border-surface-border/10 px-4 py-2.5 text-left text-[13px] font-medium text-violet-600" data-testid="evidence-toggle">
            {all ? "Show fewer" : `Show ${ordered.length - TABLE_SHOWN} more`}
          </button>
        )}
      </div>
    </section>
  );
}

/** Next questions as numbered cards. */
function NextSteps({ questions, onAsk }: { questions: string[]; onAsk: (q: string) => void }) {
  if (!questions.length) return null;
  return (
    <section className="space-y-3" data-testid="follow-ups">
      <div className="flex items-center gap-2.5"><IconTile icon={ArrowRight} tone="emerald" /><h2 className="text-[15px] font-semibold text-text-primary">Where to look next</h2></div>
      <ol className="grid gap-3 sm:grid-cols-2">
        {questions.map((q, i) => (
          <li key={q}>
            <button type="button" onClick={() => onAsk(q)} className="group flex h-full w-full items-start gap-3 rounded-2xl border border-surface-border/10 bg-surface-card px-4 py-3.5 text-left text-[14px] leading-snug text-text-primary shadow-[0_1px_2px_rgba(16,24,40,0.05)] transition hover:-translate-y-0.5 hover:border-violet-500/40 hover:shadow-md">
              <span aria-hidden className="mt-px flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-violet-500/10 text-[12px] font-semibold text-violet-700">{i + 1}</span>
              <span className="flex-1">{q}</span>
              <ArrowRight className="mt-0.5 h-4 w-4 shrink-0 text-text-muted transition group-hover:translate-x-0.5 group-hover:text-violet-600" aria-hidden />
            </button>
          </li>
        ))}
      </ol>
    </section>
  );
}

// ── page head and chips ──────────────────────────────────────────────────────────────────────────────────────────────────

const SPECIALIST_CHIP: Record<string, string> = { comparison: "Comparison", sector: "Sector and event impact", company: "Company", market: "Market" };
const CARD_TITLE: Record<string, string> = { comparison: "Evidence-based comparison", sector: "Evidence-based impact analysis" };

function Chip({ children, tone = "plain" }: { children: React.ReactNode; tone?: "plain" | "violet" }) {
  return <span className={`rounded-full border px-2.5 py-0.5 text-[11.5px] ${tone === "violet" ? "border-violet-500/30 bg-violet-500/10 text-violet-700" : "border-surface-border/10 text-text-secondary"}`}>{children}</span>;
}

/** Breadcrumb, the question as the title, "New search" on the right, and when the answer was produced. */
function PageHead({ r, crumb, onNewSearch }: { r: V2Result; crumb: string; onNewSearch?: () => void }) {
  const [at] = useState(() => new Date());
  const stamp = at.toLocaleString("en-IN", { day: "numeric", month: "short", year: "numeric", hour: "numeric", minute: "2-digit", hour12: true, timeZone: "Asia/Kolkata" });
  const newest = listedEvidence(r).map((e) => e.date).filter((d): d is string => !!d && /\d{4}-\d{2}-\d{2}/.test(d)).sort().pop();
  return (
    <header className="space-y-2" data-testid="answer-header">
      <p className="text-[12.5px] text-text-muted"><span>AI Search</span><span className="mx-1.5">/</span><span data-testid="crumb">{crumb}</span></p>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <h1 className="min-w-0 flex-1 text-[26px] font-semibold leading-tight tracking-tight text-text-primary sm:text-[30px]">{r.query}</h1>
        {onNewSearch && (
          <button type="button" onClick={onNewSearch} className="inline-flex shrink-0 items-center gap-2 rounded-xl border border-surface-border/10 bg-surface-card px-3.5 py-2 text-[13px] font-medium text-text-primary transition hover:border-violet-500/40" data-testid="new-search">
            <RotateCcw className="h-4 w-4" aria-hidden /> New search
          </button>
        )}
      </div>
      <p className="text-[12.5px] text-text-muted" data-testid="answered-at">Answered {stamp} IST{newest ? <span> · Latest evidence {fmtDate(newest)}</span> : null}</p>
    </header>
  );
}

// ── research and partial research ────────────────────────────────────────────────────────────────────────────────────────

function ResearchView({ result: r, onFollowUp, onNewSearch, feedbackMeta }: Props) {
  const partial = resolveKind(r) === "partial_research";
  const a = r.answer ?? {};
  const lead = a.summary ?? "";
  const short = a.bottom_line && !isDup(a.bottom_line, [lead]) ? a.bottom_line : null;
  const index = new Map((r.evidence_index ?? []).map((e) => [e.id, e]));
  const claims = (r.claim_sources ?? []).filter((c) => c.claim && (c.status ?? "ok") === "ok" && !isDup(c.claim, [lead, a.bottom_line ?? ""]));
  const drivers = (r.key_drivers ?? []).filter((d) => d.title && d.explanation && !isDup(d.explanation, [lead, a.bottom_line ?? "", ...claims.map((c) => c.claim)]));
  const meaning = ([["Why", a.why_it_happened], ["Near term", a.immediate_impact], ["Medium term", a.medium_term], ["Longer term", a.long_term], ["Already priced in", a.what_priced_in]] as [string, string | undefined][])
    .filter(([, t]) => t && t.trim() && !isDup(t, [lead, a.bottom_line ?? "", ...claims.map((c) => c.claim)]));
  const what = !claims.length && a.what_happened && a.what_happened.trim() && !isDup(a.what_happened, [lead]) ? a.what_happened : null;
  const limits = (a.risks ?? []).filter((t) => t && !isDup(t, [lead, a.bottom_line ?? ""]));
  const opps = (a.opportunities ?? []).filter(Boolean);
  const notice = partial ? partialNotice(r) : null;
  const verdict = authorizedVerdict(r);
  const listed = listedEvidence(r);
  const questions = followUps(r);
  const spec = r.specialist ?? "";
  const crumb = SPECIALIST_CHIP[spec] ?? (partial ? "Partial answer" : "Answer");
  const cardTitle = partial ? "Partial answer" : CARD_TITLE[spec] ?? "Evidence-based answer";
  const count = r.answer_availability?.evidence_count ?? listed.length;

  return (
    <div className="space-y-6" data-testid="answer-research" data-kind={partial ? "partial_research" : "research"}>
      <PageHead r={r} crumb={crumb} onNewSearch={onNewSearch} />
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="min-w-0 space-y-6">
          <section className={`${CARD} relative space-y-6 overflow-hidden p-5 sm:p-6`} data-testid="answer-card">
            <div aria-hidden className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-violet-500 via-fuchsia-400 to-sky-400" />
            <div className="flex flex-wrap items-center gap-2">
              <IconTile icon={Sparkles} />
              <h2 className="mr-1 text-[16px] font-semibold text-text-primary">{cardTitle}</h2>
              {SPECIALIST_CHIP[spec] && <Chip tone="violet">{SPECIALIST_CHIP[spec]}</Chip>}
              {count > 0 && <Chip>{count} {count === 1 ? "source" : "sources"} reviewed</Chip>}
              <Chip>Not investment advice</Chip>
            </div>
            {notice && (
              <div className="rounded-xl border border-surface-border/10 border-l-4 border-l-violet-500 px-4 py-3" role="note" data-testid="partial-notice">
                <p className="text-[14px] font-semibold text-text-primary">{notice.title}</p>
                <p className="mt-1 text-[14px] leading-6 text-text-secondary">{notice.body}</p>
                {notice.missing.length > 0 && <p className="mt-2 text-[13px] text-text-muted">Not yet available: {notice.missing.join("; ")}.</p>}
              </div>
            )}
            <div className="space-y-3">
              <p className="text-[21px] font-semibold leading-snug tracking-tight text-text-primary sm:text-[24px]" data-testid="lead">{lead}</p>
              {short && <p className={BODY} data-testid="in-short"><span className="font-semibold text-text-primary">In short: </span>{short}</p>}
            </div>
            <ComparisonTable r={r} />
            {verdict && (
              <div data-testid="verdict" className="rounded-xl border border-surface-border/10 px-4 py-3 text-[15px] text-text-primary">
                <p className={LABEL}>MarketRipple view</p>
                <p className="mt-1"><span className="font-semibold">{verdict.rating}</span>{verdict.direction ? <span className="text-text-secondary"> · {verdict.direction}</span> : null}</p>
                <p className="mt-1 text-[12.5px] text-text-muted">A research view, not a recommendation to buy or sell.</p>
              </div>
            )}
            {(claims.length > 0 || what) && (
              <Section label="What the evidence shows" testId="observations" icon={ListChecks}>
                <ul className="space-y-4">
                  {claims.map((c) => (
                    <li key={c.claim} className="border-l-2 border-surface-border/20 pl-4">
                      <p className="text-[15px] leading-7 text-text-primary">{c.claim}</p>
                      <SourceChips ids={c.sources} index={index} />
                    </li>
                  ))}
                  {what && <li className="border-l-2 border-surface-border/20 pl-4"><p className="text-[15px] leading-7 text-text-primary">{what}</p></li>}
                </ul>
              </Section>
            )}
            {(drivers.length > 0 || meaning.length > 0) && (
              <Section label="What it means" testId="meaning" icon={Lightbulb}>
                <div className="space-y-3">
                  {drivers.map((d) => <p key={d.title} className={BODY}><span className="font-semibold text-text-primary">{d.title}. </span>{d.explanation}</p>)}
                  {meaning.map(([k, t]) => <p key={k} className={BODY}><span className="font-semibold text-text-primary">{k}. </span>{t}</p>)}
                </div>
              </Section>
            )}
            {(limits.length > 0 || opps.length > 0) && (
              <Section label="Known limits" testId="limits" icon={AlertCircle}>
                <ul className="space-y-2">
                  {limits.map((t) => <li key={t} className={`${BODY} flex gap-3`}><span aria-hidden className="mt-3 h-1 w-1 shrink-0 rounded-full bg-text-muted" />{t}</li>)}
                  {opps.map((t) => <li key={t} className={`${BODY} flex gap-3`}><span aria-hidden className="mt-3 h-1 w-1 shrink-0 rounded-full bg-text-muted" />{t}</li>)}
                </ul>
              </Section>
            )}
          </section>
          <NextSteps questions={questions} onAsk={onFollowUp} />
          <KeyEvidenceTable items={listed} count={count} />
          <Footer r={r} onFeedbackMeta={feedbackMeta} />
        </div>
        <aside className="min-w-0 space-y-4">
          <EntitySnapshot r={r} />
          <SectorsCard r={r} />
          <CoverageCard r={r} />
          <SourcesCard items={listed} />
          <MethodologyRow />
        </aside>
      </div>
    </div>
  );
}

// ── education and product information ────────────────────────────────────────────────────────────────────────────────────

const EDU_NEXT: Record<string, string[]> = {
  pe_ratio: ["What is TCS's current P/E?", "Compare HDFC Bank and ICICI Bank"],
  fii_flows: ["How much did FIIs sell today?", "What is driving the Banking sector today?"],
  marketripple_score: ["How is HDFC Bank doing as a business?", "Compare HDFC Bank and ICICI Bank"],
};

function ExplainerView({ result: r, onFollowUp, feedbackMeta }: Props) {
  const product = resolveKind(r) === "product_information";
  const e = r.education ?? {};
  const link = internalSourceLink(e.source);
  const sections = (r.key_drivers ?? []).filter((d) => d.title && d.explanation);
  const note = r.answer?.bottom_line && !isDup(r.answer.bottom_line, [r.answer.summary ?? ""]) ? r.answer.bottom_line : null;
  const next = EDU_NEXT[e.topic ?? ""] ?? [];
  return (
    <article className="mx-auto max-w-[720px] space-y-8" data-testid={product ? "answer-product" : "answer-education"} data-kind={product ? "product_information" : "education"}>
      <Header r={r} kindLabel={product ? "MarketRipple guide" : "Explained"} />
      <div className="space-y-3">
        <h1 className="text-[26px] font-semibold leading-tight tracking-tight text-text-primary sm:text-[30px]">{e.title || r.query}</h1>
        <p className="text-[17px] leading-8 text-text-secondary" data-testid="lead">{r.answer?.summary}</p>
      </div>
      {e.beyond_published_detail && (
        <div className={`${CARD} border-l-4 border-l-violet-500 px-5 py-4`} role="note" data-testid="partial-notice">
          <p className="text-[14px] font-semibold text-text-primary">Answered in part</p>
          <p className="mt-1 text-[14px] leading-6 text-text-secondary">This covers what MarketRipple publishes about the score. The detail you asked for is not part of the published methodology.</p>
        </div>
      )}
      {sections.length > 0 && (
        <div className="space-y-6" data-testid="explainer-sections">
          {sections.map((d) => (
            <section key={d.title} className="space-y-1.5">
              <h2 className="text-[15px] font-semibold text-text-primary">{d.title}</h2>
              <p className={BODY}>{d.explanation}</p>
            </section>
          ))}
        </div>
      )}
      {note && <p className="text-[14px] leading-6 text-text-muted" data-testid="explainer-note">{note}</p>}
      <div className={`${CARD} px-5 py-4 text-[13px] leading-5 text-text-muted`} data-testid="explainer-basis">
        <p>
          <span className="font-semibold text-text-secondary">{product ? "From the MarketRipple methodology." : "From MarketRipple's reviewed glossary."}</span>
          {" "}{product ? "This describes how the product works. It is not live market data for any company." : "This is a general explanation, not live market evidence, and not a forecast or a recommendation."}
        </p>
        {link && <p className="mt-2"><Link href={link.href} className="font-medium text-violet-600 hover:underline">{link.label}</Link></p>}
      </div>
      <FollowUps questions={next} onAsk={onFollowUp} label="Try next" />
      <Footer r={r} onFeedbackMeta={feedbackMeta} />
    </article>
  );
}

// ── unavailable and temporarily unavailable ──────────────────────────────────────────────────────────────────────────────

function NoticeView({ result: r, onFollowUp, onRetry, feedbackMeta, nextQuestions }: Props) {
  const temp = resolveKind(r) === "temporarily_unavailable";
  const copy = temp ? temporaryCopy(r.answer_availability?.reason) : unavailableCopy(r);
  const related = !temp ? listedEvidence(r) : [];
  const suggestions = (r.company_suggestions ?? []).slice(0, 4);
  const own = followUps(r);
  const next = (own.length ? own : nextQuestions ?? []).slice(0, 4);
  return (
    <article className="mx-auto max-w-[720px] space-y-8" data-testid={temp ? "answer-temporary" : "answer-unavailable"} data-kind={temp ? "temporarily_unavailable" : "unavailable"} data-reason={r.answer_availability?.reason ?? ""}>
      <Header r={r} kindLabel={temp ? "Temporarily unavailable" : "No answer"} />
      <div className="space-y-3">
        <h1 className="text-[24px] font-semibold leading-tight tracking-tight text-text-primary sm:text-[28px]" data-testid="notice-title">{copy.title}</h1>
        {copy.body && <p className="text-[16px] leading-7 text-text-secondary" data-testid="notice-body">{copy.body}</p>}
        {copy.retry && onRetry && (
          <button type="button" onClick={onRetry} className="mt-2 rounded-xl bg-violet-600 px-4 py-2 text-[13px] font-semibold text-white transition hover:bg-violet-500" data-testid="retry">Try again</button>
        )}
      </div>
      {suggestions.length > 0 && (
        <Section label="Did you mean" testId="did-you-mean">
          <div className="flex flex-wrap gap-2">
            {suggestions.map((c) => (
              <button key={c.symbol} type="button" onClick={() => onFollowUp(`How is ${c.name} doing as a business?`)} className="rounded-full border border-surface-border/10 bg-surface-card px-3.5 py-1.5 text-[13px] text-text-primary hover:border-violet-500/40">{c.name}</button>
            ))}
          </div>
        </Section>
      )}
      {related.length > 0 && <EvidenceList items={related} count={r.answer_availability?.evidence_count ?? related.length} />}
      <FollowUps questions={next} onAsk={onFollowUp} label={temp ? "Meanwhile" : "Try instead"} />
      <Footer r={r} onFeedbackMeta={feedbackMeta} />
    </article>
  );
}

export function AnswerV2(props: Props) {
  switch (resolveKind(props.result)) {
    case "education":
    case "product_information":
      return <ExplainerView {...props} />;
    case "unavailable":
    case "temporarily_unavailable":
      return <NoticeView {...props} />;
    default:
      return <ResearchView {...props} />;
  }
}
