"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import type { ReactNode } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import dynamic from "next/dynamic";
import { TrackPageVisit } from "@/components/TrackPageVisit";
import { Target, Building2, BarChart2, Sparkles, MailX, ArrowRight } from "lucide-react";
import { MarketContextStrip } from "@/components/MarketContextStrip";
import { NextSteps } from "@/components/NextSteps";
import { useBreadcrumbOverride } from "@/components/Breadcrumbs";
import { isRealSymbol, truncateForQuery } from "@/lib/text";
import { AIDisclaimer } from "@/components/ai/AIDisclaimer";
import { ShareInsightCard } from "@/components/ShareInsightCard";
import { SmartCTA } from "@/components/SmartCTA";
import { RelatedContent, type RelatedItem } from "@/components/RelatedContent";
import { HistoricalMemory } from "@/components/HistoricalMemory";
import { useIntelligence } from "@/hooks/useIntelligence";
import { IntelligenceBlock, type IntelligenceObject } from "@/components/intelligence/IntelligenceBlock";
import { type EvidenceFact } from "@/components/article/EvidenceList";
import { API_BASE_URL as API } from "@/lib/api";
import "reactflow/dist/style.css";

const ReactFlow  = dynamic(() => import("reactflow").then(m => m.default),     { ssr: false });
const Background = dynamic(() => import("reactflow").then(m => m.Background),  { ssr: false });
const Controls   = dynamic(() => import("reactflow").then(m => m.Controls),    { ssr: false });
// Recharts split into its own lazy chunk (2026-08 performance audit) — see
// EventSidebarCharts.tsx's own header comment for why.
const SectorDonut         = dynamic(() => import("./EventSidebarCharts").then(m => m.SectorDonut),         { ssr: false });
const MarketReactionChart = dynamic(() => import("./EventSidebarCharts").then(m => m.MarketReactionChart), { ssr: false });


// ── Types ─────────────────────────────────────────────────────────────────────
interface Company  { symbol: string; name: string; impact_type: string; impact_score: number | null; reason: string }
interface Sector   { sector: string; impact: string; impact_score: number | null }
interface Step     { date: string; title: string; description: string; order: number }
interface Policy   { id: number; title: string; ministry: string; announcement_date: string; summary: string; url: string }
interface HistEvt  { id: string; slug?: string; title: string; event_date: string; impact_score: number | null; similarity_score: number | null; reason: string }
interface NewsItem { id: string; headline: string; source: string; published_at: string; summary: string; url: string }
interface GNode    { id: string; label: string; type: string; metadata: Record<string, unknown> }
interface GEdge    { source: string; target: string; relationship: string }
interface MarketIndex { name: string; ticker: string; value: string; pct_change: number; positive: boolean; change_str: string }
interface MarketStatus { is_open: boolean; status: string; time_ist: string; date: string }
interface MarketData   { marketStatus: MarketStatus; marketIndices: MarketIndex[] }
interface ChartPoint   { label: string; value: number }
interface MacroRelease {
  metric: string;
  release_value: number | null;
  previous_value: number | null;
  expected_value: number | null;
  surprise: number | null;
  unit: string | null;
  period: string | null;
  geography: string;
  importance: string | null;
  affected_sectors: string[];
  affected_companies: string[];
  source: string | null;
  source_url: string | null;
}

export interface EventDetail {
  event: { id: string; slug?: string; title: string; description: string; source: string; event_type: string; event_date: string; enrichment_status: string };
  summary: { text: string; why_it_matters: string; key_bullets: string[]; immediate_impact: string; long_term_impact: string; risk_factors: string[]; opportunities: string[] };
  impactScore: number | null;
  confidence: number | null;
  companies: Company[];
  beneficiaries: Company[];
  losers: Company[];
  affectedSectors: Sector[];
  timeline: Step[];
  governmentPolicies: Policy[];
  historicalEvents: HistEvt[];
  relatedNews: NewsItem[];
  graph: { nodes: GNode[]; edges: GEdge[] };
  marketReaction: { short_term?: string; medium_term?: string; volatility?: string; sentiment?: string };
  aiAnalysis: { bull_case?: string; bear_case?: string; base_case?: string; key_risks?: string[]; catalysts?: string[] };
  macroRelease?: MacroRelease | null;
}

// ── Deep Intelligence (Layer 2) types — mirrors
// app/schemas/event_deep_research.py exactly. One consolidated fetch,
// see DeepIntelligencePanel below.
interface DRTimelineStep { date: string | null; title: string; description: string; kind: string }
interface DRScenario { label: "Bull" | "Base" | "Bear"; outcome: string; key_drivers: string[]; confidence: "High" | "Medium" | "Low" | null }
interface DRHistoricalPattern { id: string; slug?: string; title: string; event_date: string | null; similarity_score: number | null; impact_score: number | null; reason: string | null }
interface DRSecondOrderEffect { level: "immediate" | "sector" | "company" | "broader"; description: string; status: "observed" | "likely" | "potential" }
interface DRRiskItem { risk: string; why_it_matters: string | null }
interface DRReasoning { data_used: string[]; sources: string[]; analysis_timestamp: string | null; confidence: number | null; summary: string | null }
interface DeepResearch {
  event_id: string;
  timeline: DRTimelineStep[];
  scenarios: DRScenario[];
  scenario_status: "shown" | "not_applicable" | "unavailable";
  historical_patterns: DRHistoricalPattern[];
  second_order_effects: DRSecondOrderEffect[];
  risks: DRRiskItem[];
  reasoning: DRReasoning;
  generated_at: string;
}

// ── Constants ─────────────────────────────────────────────────────────────────
const TABS = ["Overview", "Event Intelligence", "Companies", "Sectors", "Timeline", "Historical", "Related News", "Graph"] as const;
type Tab = typeof TABS[number];

const COMPANY_PALETTE = ["bg-violet-500","bg-sky-500","bg-emerald-500","bg-amber-500","bg-rose-500"];
const DONUT_COLORS    = ["#f43f5e","#f97316","#eab308","#22c55e"];

// ── Helpers ───────────────────────────────────────────────────────────────────
// null means the Scoring Engine had insufficient evidence — never coerce
// that into the bottom "Low Impact" bucket, which would claim a real
// (low) score was computed when none was.
function scoreColor(s: number | null | undefined) {
  if (s === null || s === undefined) return { text: "text-text-muted", ring: "#475569", border: "border-surface-border/10", bg: "bg-text-primary/[0.06]" };
  if (s >= 85) return { text: "text-rose-400",  ring: "#f43f5e", border: "border-rose-500",  bg: "bg-rose-500/15"  };
  if (s >= 70) return { text: "text-amber-400", ring: "#f59e0b", border: "border-amber-400", bg: "bg-amber-500/15" };
  if (s >= 50) return { text: "text-sky-400",   ring: "#38bdf8", border: "border-sky-400",   bg: "bg-sky-500/15"   };
  return               { text: "text-text-secondary", ring: "rgb(var(--text-muted))", border: "border-surface-border/10", bg: "bg-text-primary/[0.05]" };
}

function scoreLabel(s: number | null | undefined) {
  if (s === null || s === undefined) return "Unscored";
  if (s >= 85) return "Very High Impact";
  if (s >= 70) return "High Impact";
  if (s >= 50) return "Medium Impact";
  return "Low Impact";
}

// A zero score is as uninformative as no score at all (not yet meaningfully
// scored) — treat both the same way rather than presenting "0" as if it
// were a confident "no impact" verdict.
function hasRealScore(s: number | null | undefined): s is number {
  return s !== null && s !== undefined && s > 0;
}

// Same 0-100 -> High/Medium/Low bucket thresholds as the backend's
// _confidence_bucket (event_deep_research_service.py) — kept in sync so
// the qualitative label a user sees never implies a precision the
// underlying score doesn't have.
function confidenceTier(c: number | null | undefined): "High" | "Medium" | "Low" | null {
  if (c === null || c === undefined) return null;
  if (c >= 66) return "High";
  if (c >= 33) return "Medium";
  return "Low";
}

function impactBg(v?: string) {
  if (!v) return "bg-text-primary/[0.09] text-text-secondary border-surface-border/7";
  if (v === "positive" || v === "bullish") return "bg-emerald-500/20 text-emerald-600 dark:text-emerald-300 border-emerald-500/30";
  if (v === "negative" || v === "bearish") return "bg-rose-500/20 text-rose-600 dark:text-rose-300 border-rose-500/30";
  return "bg-amber-500/20 text-amber-600 dark:text-amber-300 border-amber-500/30";
}

function fmt(s?: string) {
  if (!s) return "";
  try { return new Date(s).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" }); }
  catch { return s.slice(0, 10); }
}

function srcInitials(src: string) {
  return src.split(/[\s\-_]/g).slice(0, 2).map(w => w[0] || "").join("").toUpperCase() || "N";
}

// ── Question-in-title Q&A (Event Explorer card) ─────────────────────────────
// A lot of ingested headlines are themselves phrased as two sentences — a
// factual statement plus a bolted-on question ("...after weak Q1 results.
// What are Morgan Stanley, Nomura, others saying?"). Surface that question
// explicitly inside the card, but ONLY answer it from real, verifiably
// on-topic data — never invent what an analyst said. Real named entities
// (bank names, people) in a fabricated "answer" would be actively harmful,
// not just generically dishonest, so the grounding check here is strict.
function extractQuestion(title: string): string | null {
  const sentences = title.split(/(?<=[.!?])\s+/).map(s => s.trim()).filter(Boolean);
  const q = sentences.find(s => s.endsWith("?"));
  // A title that's ONE single question start-to-finish isn't "a question
  // bolted onto a headline" — nothing else on the card would be
  // duplicated, so there's no separate fact/question split worth calling
  // out.
  return q && sentences.length > 1 ? q : null;
}

// Capitalized multi-word sequences ("Morgan Stanley", "Jaguar Land Rover")
// as a cheap proper-noun heuristic — good enough to gate whether the
// question is asking about something specific and checkable, vs. generic
// ("What happens next?", which has no named entity to verify against).
function extractNamedEntities(text: string): string[] {
  const matches = text.match(/\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b/g) || [];
  const STOP = new Set(["What", "Who", "Why", "How", "When", "Where", "Which", "Others", "Saying"]);
  return Array.from(new Set(matches.filter(m => !STOP.has(m) && m.length > 2)));
}

function deriveQuestionAnswer(data: EventDetail, question: string): string | null {
  const entities = extractNamedEntities(question);
  const haystack = [
    data.summary.why_it_matters, data.summary.text,
    ...(data.relatedNews ?? []).map(n => `${n.headline} ${n.summary ?? ""}`),
  ].join(" \n ");
  if (!haystack.trim()) return null;
  // Question names specific entities (banks, people, companies) — only
  // answer if the real text actually mentions them; otherwise showing
  // why_it_matters would imply it addresses something it doesn't.
  if (entities.length > 0) {
    const allMentioned = entities.every(e => haystack.toLowerCase().includes(e.toLowerCase()));
    if (!allMentioned) return null;
  }
  const answer = data.summary.why_it_matters || data.summary.text;
  return answer && answer.length > 15 ? answer : null;
}

function mapCategory(cat: string): string {
  const m: Record<string, string> = {
    "Government": "Regulatory",
    "Policy": "Regulatory",
    "RBI": "Monetary",
    "Macro": "Fiscal",
    "Global": "Global",
    "Corporate": "Corporate",
    "Results": "Earnings",
  };
  return m[cat] ?? cat;
}

// ── ScoreRing ─────────────────────────────────────────────────────────────────
function ScoreRing({ score, size = 80 }: { score: number | null | undefined; size?: number }) {
  const sc      = scoreColor(score);
  const r       = (size - 8) / 2;
  const circ    = 2 * Math.PI * r;
  const unscored = score === null || score === undefined;
  const dash    = unscored ? 0 : (score / 100) * circ;
  return (
    <div className="relative flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }}>
        <circle cx={size/2} cy={size/2} r={r} stroke="rgb(var(--text-primary) / 0.06)" strokeWidth={6} fill="none"/>
        {!unscored && (
          <circle cx={size/2} cy={size/2} r={r} stroke={sc.ring} strokeWidth={6} fill="none"
            strokeLinecap="round" strokeDasharray={`${dash} ${circ}`}
            style={{ filter: `drop-shadow(0 0 5px ${sc.ring}80)` }}/>
        )}
      </svg>
      <div className="absolute text-center">
        {unscored ? (
          <div className="text-[10px] font-medium leading-tight text-text-muted">N/A</div>
        ) : (
          <div className={`text-xl font-black leading-none ${sc.text}`}>{Math.round(score)}</div>
        )}
        <div className="text-[8px] text-text-muted mt-0.5">{unscored ? "Unscored" : "/ 100"}</div>
      </div>
    </div>
  );
}

// ── KpiCard ───────────────────────────────────────────────────────────────────
function KpiCard({ label, value, sub, icon, color, border }: {
  label: string; value: string | number; sub: string; icon: ReactNode; color: string; border: string;
}) {
  return (
    <div className={`rounded-[20px] border bg-text-primary/[0.025] p-4 transition hover:-translate-y-0.5 hover:shadow-lg ${border}`}>
      <div className="mb-2 flex items-center justify-between">
        <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-text-muted">{label}</p>
        <span className="text-text-secondary">{icon}</span>
      </div>
      <p className={`text-2xl font-black leading-none ${color}`}>{value}</p>
      <p className="mt-1.5 text-[10px] text-text-muted">{sub}</p>
    </div>
  );
}

// ── EmptyState ────────────────────────────────────────────────────────────────
function Empty({ msg }: { msg: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <div className="mb-2 flex h-8 w-8 items-center justify-center rounded-full bg-text-primary/[0.04]">
        <svg className="h-4 w-4 text-text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
        </svg>
      </div>
      <p className="text-[12px] text-text-muted">{msg}</p>
    </div>
  );
}

// ── Card ──────────────────────────────────────────────────────────────────────
function Card({ title, action, children, className = "" }: {
  title?: string; action?: React.ReactNode; children: React.ReactNode; className?: string;
}) {
  return (
    <div className={`rounded-[20px] border border-surface-border/8 bg-text-primary/[0.025] p-4 ${className}`}>
      {(title || action) && (
        <div className="mb-3 flex items-center justify-between">
          {title && <h3 className="text-[12px] font-semibold uppercase tracking-wider text-text-muted">{title}</h3>}
          {action}
        </div>
      )}
      {children}
    </div>
  );
}

// ── Macro Data ────────────────────────────────────────────────────────────────
// Only rendered when the backend actually extracted a real, structured
// figure for this event (see app/services/macro_extraction.py — most
// events don't have one, and this card simply doesn't render then, rather
// than showing a placeholder). Every number here is a real value already
// resolved server-side; this component only formats and compares them.
function formatMacroValue(value: number | null, unit: string | null): string {
  if (value === null || value === undefined) return "—";
  if (unit === "%") return `${value.toFixed(1)}%`;
  if (unit === "₹ crore") return `₹${value.toLocaleString("en-IN")} cr`;
  if (unit === "$ billion") return `$${value.toFixed(1)}bn`;
  return `${value}${unit ? ` ${unit}` : ""}`;
}

function MacroDataCard({ macro }: { macro: MacroRelease }) {
  const hasDelta = macro.release_value !== null && macro.previous_value !== null;
  const delta = hasDelta ? (macro.release_value as number) - (macro.previous_value as number) : null;
  return (
    <Card title={`${macro.metric}${macro.period ? ` — ${macro.period}` : ""}`}>
      <div className="flex flex-wrap items-end gap-x-6 gap-y-3">
        <div>
          <p className="text-[10px] uppercase tracking-wider text-text-muted">Released</p>
          <p className="text-[22px] font-bold text-text-primary">{formatMacroValue(macro.release_value, macro.unit)}</p>
        </div>
        {macro.previous_value !== null && (
          <div>
            <p className="text-[10px] uppercase tracking-wider text-text-muted">Previous</p>
            <p className="text-[14px] font-medium text-text-secondary">{formatMacroValue(macro.previous_value, macro.unit)}</p>
          </div>
        )}
        {delta !== null && (
          <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${delta >= 0 ? "bg-emerald-500/15 text-emerald-500" : "bg-rose-500/15 text-rose-500"}`}>
            {delta >= 0 ? "+" : ""}{delta.toFixed(2)}{macro.unit === "%" ? " pts" : ""}
          </span>
        )}
      </div>
      {macro.affected_sectors.length > 0 && (
        <p className="mt-3 text-[12px] text-text-secondary">
          <span className="text-text-muted">Typically sensitive: </span>
          {macro.affected_sectors.join(", ")}
        </p>
      )}
      {/* Source named as plain text, never a clickable off-site link. */}
      {macro.source && (
        <p className="mt-2 text-[10px] text-text-muted">Source: {macro.source}{macro.geography && macro.geography !== "India" ? ` · ${macro.geography}` : ""}</p>
      )}
    </Card>
  );
}

// ── Facts vs Interpretation (Phase 14, 2026-08 audit) ───────────────────────
// Same honest split already built for newsroom articles (EvidenceList) —
// reused directly here rather than forked, just fed from Event's own real
// fields instead of IntelligenceArticle's. FACT: dated/sourced things that
// happened (event date, source, a real extracted macro figure, dated
// timeline steps). INTERPRETATION: the enrichment pipeline's own AI read
// of why it matters, risks, and opportunities — never presented as
// confirmed fact.
function buildEventFacts(data: EventDetail): { facts: EvidenceFact[]; interpretations: EvidenceFact[]; sources: string[] } {
  const facts: EvidenceFact[] = [];
  if (data.event.event_date) facts.push({ label: "Event date", detail: data.event.event_date });
  if (data.event.source) facts.push({ label: "Source", detail: data.event.source });
  const macro = data.macroRelease;
  if (macro && macro.release_value !== null && macro.release_value !== undefined) {
    facts.push({ label: `${macro.metric} released`, detail: `${formatMacroValue(macro.release_value, macro.unit)}${macro.period ? ` (${macro.period})` : ""}` });
    if (macro.previous_value !== null && macro.previous_value !== undefined) {
      facts.push({ label: "Previous value", detail: formatMacroValue(macro.previous_value, macro.unit) });
    }
  }
  for (const t of data.timeline.slice(0, 4)) {
    if (t.date) facts.push({ label: t.title, detail: t.date });
  }

  // Risk/opportunity bullets deliberately NOT itemized here — that's the
  // Event Intelligence tab's job (Key Risks / Growth Catalysts cards, full
  // probability-framed treatment), not a duplicate one-line summary here.
  // "Why it matters" also deliberately absent (2026-08 redesign) — Layer 1
  // now has its own dedicated Why It Matters card with the full text; an
  // interpretation entry here would just repeat it inside Deep
  // Intelligence's evidence list.
  const interpretations: EvidenceFact[] = [];

  const sources = Array.from(new Set([
    ...(data.relatedNews || []).map(n => n.source).filter(Boolean),
    ...(data.governmentPolicies || []).map(p => p.ministry).filter(Boolean),
    ...(macro?.source ? [macro.source] : []),
  ]));

  return { facts, interpretations, sources };
}

// ── Layer 1: Most Affected (sectors) ────────────────────────────────────────
// Materiality-thresholded — showing all 8-10 AI-tagged sectors at once is
// noise, not signal (2026-08 UX redesign). Sorted by real impact_score;
// top 3 shown open, the rest behind a real count, never a fabricated
// "why" reason (the backend has no per-sector rationale field — omitted
// rather than invented).
function MostAffectedSectors({ data }: { data: EventDetail }) {
  const [expanded, setExpanded] = useState(false);
  if (!data.affectedSectors.length) return null;
  const sorted = [...data.affectedSectors].sort((a, b) => (b.impact_score ?? 0) - (a.impact_score ?? 0));
  const TOP_N = 3;
  const top = sorted.slice(0, TOP_N);
  const rest = sorted.slice(TOP_N);
  const tier = (score: number | null) => score !== null && score >= 60 ? "High" : score !== null && score >= 35 ? "Medium" : "Low";
  const row = (s: Sector) => (
    <div key={s.sector} className="flex items-center justify-between gap-3 py-1.5">
      <span className="text-[13px] font-medium text-text-primary">{s.sector}</span>
      <div className="flex items-center gap-2">
        {s.impact_score !== null && s.impact_score !== undefined && (
          <span className="text-[10px] font-semibold text-text-muted">{tier(s.impact_score)}</span>
        )}
        <span className={`rounded-full border px-2 py-0.5 text-[9px] font-semibold capitalize ${impactBg(s.impact)}`}>
          {s.impact === "positive" ? "↑ Positive" : s.impact === "negative" ? "↓ Negative" : "Neutral"}
        </span>
      </div>
    </div>
  );
  return (
    <Card title="Most Affected" className="mb-4 break-inside-avoid">
      <div className="divide-y divide-surface-border/5">{top.map(row)}</div>
      {rest.length > 0 && (
        <>
          {expanded && <div className="divide-y divide-surface-border/5 border-t border-surface-border/5">{rest.map(row)}</div>}
          <button onClick={() => setExpanded(e => !e)} className="mt-2 text-[11px] font-medium text-sky-400 hover:text-sky-600 dark:text-sky-300 transition">
            {expanded ? "Show fewer sectors" : `${rest.length} other sector${rest.length > 1 ? "s" : ""} with lower/indirect impact →`}
          </button>
        </>
      )}
    </Card>
  );
}

// ── Layer 1: Affected Companies ─────────────────────────────────────────────
// Grouped Positive/Negative/Neutral — a group with zero members is never
// rendered (2026-08 UX redesign: "why are we spending 150px telling the
// user there's nothing here?"). Zero companies overall gets one honest
// sentence, not three empty cards.
function AffectedCompaniesSummary({ data, goTab }: { data: EventDetail; goTab: (t: Tab) => void }) {
  const classifiedSymbols = new Set([...data.beneficiaries, ...data.losers].map(c => c.symbol));
  const neutral = data.companies.filter(c => !classifiedSymbols.has(c.symbol));
  const groups = [
    { list: data.beneficiaries, label: "Positive",  dot: "bg-emerald-400", text: "text-emerald-400" },
    { list: data.losers,        label: "Negative",  dot: "bg-rose-400",    text: "text-rose-400"    },
    { list: neutral,            label: "Neutral / unclear", dot: "bg-text-muted", text: "text-text-secondary" },
  ].filter(g => g.list.length > 0);

  if (data.companies.length === 0) {
    return (
      <Card title="Company-Level Impact" className="mb-4 break-inside-avoid">
        <p className="text-[12px] text-text-muted">No sufficiently reliable company-level relationship has been established yet.</p>
      </Card>
    );
  }

  return (
    <Card title="Affected Companies" className="mb-4 break-inside-avoid" action={<span className="text-[11px] text-text-muted">{data.companies.length} compan{data.companies.length === 1 ? "y" : "ies"} identified</span>}>
      <div className="space-y-3">
        {groups.map(g => (
          <div key={g.label}>
            <p className={`mb-1.5 text-[10px] font-bold uppercase tracking-wider ${g.text}`}>{g.label}</p>
            <div className="space-y-1.5">
              {g.list.slice(0, 5).map((c, i) => (
                <div key={i} className="flex items-center gap-2">
                  <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${g.dot}`}/>
                  {isRealSymbol(c.symbol) ? (
                    <Link href={`/companies/${c.symbol}`} className="flex-1 min-w-0 text-[12px] font-medium text-text-primary hover:text-sky-600 dark:text-sky-300 transition truncate">{c.name || c.symbol}</Link>
                  ) : (
                    <span className="flex-1 min-w-0 text-[12px] font-medium text-text-primary truncate">{c.name}</span>
                  )}
                  <span className={`shrink-0 text-[11px] font-bold ${g.text}`}>{c.impact_score === null || c.impact_score === undefined ? "—" : Math.round(c.impact_score)}</span>
                </div>
              ))}
              {g.list.length > 5 && (
                <button onClick={() => goTab("Companies")} className="text-[11px] text-sky-400 hover:text-sky-600 dark:text-sky-300 transition">+{g.list.length - 5} more →</button>
              )}
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}

// ── Layer 1: Historical Precedent (compact) ─────────────────────────────────
// Only the single closest real match, only when it has a real score — the
// explicit "No fabricated historical statistic" guard (2026-08 redesign).
// Full detail (reason, all matches) lives in Deep Intelligence's Historical
// Evidence section; this is deliberately just the headline fact.
function HistoricalPrecedentCompact({ data }: { data: EventDetail }) {
  const top = data.historicalEvents[0];
  const topScore = top?.impact_score;
  return (
    <Card title="Historical Precedent" className="mb-4 break-inside-avoid">
      {!top || !hasRealScore(topScore) ? (
        <p className="text-[12px] text-text-muted">No sufficiently similar historical precedent found.</p>
      ) : (
        <Link href={`/events/${top.slug || top.id}`} className="flex items-start gap-3 rounded-xl -m-1 p-1 hover:bg-text-primary/[0.03] transition">
          <div className="flex h-10 w-10 shrink-0 flex-col items-center justify-center rounded-xl bg-text-primary/[0.05]">
            <span className="text-[15px] font-black text-text-primary">{Math.round(topScore)}</span>
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-[12px] font-medium text-text-primary line-clamp-2">{top.title}</p>
            <p className="mt-0.5 text-[10px] text-text-muted">
              {top.similarity_score !== null && top.similarity_score !== undefined && top.similarity_score > 0 && `${Math.round(top.similarity_score * 100)}% similar · `}
              Impact score {Math.round(topScore)}/100
            </p>
          </div>
        </Link>
      )}
    </Card>
  );
}

// ── Layer 1: What Could Change This View ────────────────────────────────────
// Reframed from "monitoring checklist" language on purpose (2026-08
// redesign): this product has no login/watchlist/persistent alerting, so
// "monitor X" is a feature promise it can't keep. These are informational
// conditions — what would change the read above — sourced from the same
// real risk_factors the AI enrichment already produced, not a second AI
// call and not a generic "watch the news" filler.
function WhatCouldChangeView({ data }: { data: EventDetail }) {
  const items = (data.summary.risk_factors ?? []).slice(0, 5);
  if (!items.length) return null;
  return (
    <Card title="What Could Change This View" className="mb-4 break-inside-avoid">
      <ul className="space-y-2">
        {items.map((r, i) => (
          <li key={i} className="flex items-start gap-2 text-[13px] leading-5 text-text-secondary">
            <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-amber-400"/>{r}
          </li>
        ))}
      </ul>
    </Card>
  );
}

// ── Layer 1: Bottom Line ─────────────────────────────────────────────────────
// One real, composed conclusion — not a restatement of What Happened or a
// re-listing of every risk/opportunity already shown above. Built only
// from fields that exist; a component is simply omitted when its source
// field is empty rather than filled with boilerplate.
function BottomLineCard({ data }: { data: EventDetail }) {
  const opp = data.summary.opportunities?.[0];
  const risk = data.summary.risk_factors?.[0];
  const tier = confidenceTier(data.confidence);
  if (!opp && !risk && !hasRealScore(data.impactScore)) return null;
  return (
    <div className="mb-4 break-inside-avoid rounded-[20px] border border-violet-500/15 bg-violet-500/[0.03] p-4">
      <p className="mb-2 text-[10px] font-bold uppercase tracking-wider text-violet-400">Bottom Line</p>
      <div className="space-y-1.5 text-[13px] leading-5 text-text-secondary">
        {opp && <p><span className="font-semibold text-emerald-400">Opportunity — </span>{opp}</p>}
        {risk && <p><span className="font-semibold text-rose-400">Risk — </span>{risk}</p>}
        <p><span className="font-semibold text-text-primary">Confidence — </span>{tier ?? "Unscored, pending more analysis"}</p>
      </div>
    </div>
  );
}

// ── Layer 1: Evidence strip ─────────────────────────────────────────────────
// Always-visible counts, never a collapsed "Evidence ▸" the user has to
// click just to learn whether evidence exists (2026-08 redesign — explicit
// product feedback: don't hide the existence of evidence). The detail
// itself (per-source facts, AI reasoning) lives one click away in Deep
// Intelligence's Sources & AI Transparency section.
function EvidenceStrip({ data, onOpen }: { data: EventDetail; onOpen: () => void }) {
  const sourceCount = new Set((data.relatedNews ?? []).map(n => n.source).filter(Boolean)).size;
  const relatedCount = data.historicalEvents.length;
  const companyCount = data.companies.length;
  if (!sourceCount && !relatedCount && !companyCount) return null;
  return (
    <div className="mb-4 flex break-inside-avoid items-center justify-between gap-3 rounded-xl border border-surface-border/6 bg-text-primary/[0.015] px-4 py-2.5">
      <p className="text-[11px] text-text-muted">
        {[
          sourceCount > 0 ? `${sourceCount} source${sourceCount > 1 ? "s" : ""}` : null,
          relatedCount > 0 ? `${relatedCount} related event${relatedCount > 1 ? "s" : ""}` : null,
          companyCount > 0 ? `${companyCount} company relationship${companyCount > 1 ? "s" : ""}` : null,
        ].filter(Boolean).join(" · ")}
      </p>
      <button onClick={onOpen} className="shrink-0 text-[11px] font-semibold text-sky-400 hover:text-sky-600 dark:text-sky-300 transition">View evidence →</button>
    </div>
  );
}

// ── Tab: Overview (Layer 1 — Event Intelligence) ────────────────────────────
// Understandable in 10-20 seconds: header/verdict live above this tab
// already (VerdictCard); this tab covers What Happened → Why It Matters →
// Most Affected → Affected Companies → Historical Precedent → What Could
// Change This View → Bottom Line → Evidence strip → Deep Intelligence
// entry point. Zero new AI calls — everything here reuses the single
// /api/events/{id} fetch this page already makes.
function OverviewTab({ data, goTab, initialRelated }: { data: EventDetail; goTab: (t: Tab) => void; initialRelated?: Record<string, RelatedItem[]> | null }) {
  // Expanded by default (2026-08 audit, explicit request) — still exactly
  // one consolidated fetch (DeepIntelligencePanel's own effect fires once
  // on mount instead of on click), not a return to the old multi-call
  // accordion.
  const [deepOpen, setDeepOpen] = useState(true);
  const deepRef = useRef<HTMLDivElement>(null);
  const isPending = data.event.enrichment_status !== "done";

  const openDeepIntelligence = useCallback(() => {
    setDeepOpen(true);
    requestAnimationFrame(() => deepRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }));
  }, []);

  return (
    <div className="space-y-4">
      {isPending && (
        <div className="flex items-center gap-3 rounded-xl border border-amber-500/20 bg-amber-500/[0.06] px-4 py-3">
          <div className="h-4 w-4 animate-spin rounded-full border-2 border-amber-400 border-t-transparent"/>
          <div>
            <span className="text-[13px] font-semibold text-amber-600 dark:text-amber-300">AI enrichment in progress</span>
            <span className="ml-2 text-[11px] text-amber-400/70">Companies, sectors, timeline will populate automatically.</span>
          </div>
        </div>
      )}

      {/* Real structured macro figure, when the backend extracted one —
          shown first since it's a verified fact, ahead of AI-generated
          summary text. Full-width — a status fact, not part of either
          column below. */}
      {data.macroRelease && <MacroDataCard macro={data.macroRelease} />}

      {/* Two-column layout (2026-08 audit, explicit request — left/right,
          not accordions). A fixed left-group/right-group split can't stay
          height-balanced across events (some have long AI summaries and
          many companies, some have almost nothing), so this uses CSS
          multi-column flow instead: the browser distributes cards across
          the two columns by actual rendered height, keeping both sides
          roughly equal for every event rather than a manual split that's
          only balanced by coincidence. `break-inside-avoid` keeps each
          card intact (never split across the column break). Stacks to one
          column on narrow screens. */}
      <div className="columns-1 gap-4 lg:columns-2 [column-fill:balance]">
        {/* What Happened */}
        {data.summary.text && (
          <div className="mb-4 break-inside-avoid">
            <Card>
              <div className="flex items-start gap-3">
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-violet-500/20">
                  <svg className="h-4 w-4 text-violet-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/>
                  </svg>
                </div>
                <div className="flex-1 min-w-0">
                  <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-violet-400">What Happened</p>
                  <p className="text-[13px] leading-5 text-text-secondary">{data.summary.text}</p>
                  {data.summary.key_bullets?.length > 0 && (
                    <ul className="mt-3 space-y-1">
                      {data.summary.key_bullets.slice(0, 3).map((b, i) => (
                        <li key={i} className="flex items-start gap-2 text-[12px] text-text-secondary">
                          <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-violet-400"/>
                          {b}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>
            </Card>
          </div>
        )}

        {/* Why It Matters */}
        {data.summary.why_it_matters && (
          <div className="mb-4 break-inside-avoid">
            <Card>
              <div className="flex items-start gap-3">
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-sky-500/20">
                  <svg className="h-4 w-4 text-sky-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
                  </svg>
                </div>
                <div className="flex-1 min-w-0">
                  <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-sky-400">Why It Matters</p>
                  <p className="text-[13px] leading-5 text-text-secondary">{data.summary.why_it_matters}</p>
                </div>
              </div>
            </Card>
          </div>
        )}

        <MostAffectedSectors data={data} />
        <AffectedCompaniesSummary data={data} goTab={goTab} />
        <HistoricalPrecedentCompact data={data} />
        <WhatCouldChangeView data={data} />
        <BottomLineCard data={data} />
        <EvidenceStrip data={data} onOpen={openDeepIntelligence} />
      </div>

      <div ref={deepRef}>
        <DeepIntelligencePanel data={data} initialRelated={initialRelated} open={deepOpen} onToggle={() => setDeepOpen(o => !o)} />
      </div>

      <AIDisclaimer />
    </div>
  );
}

// ── Layer 2: Deep Intelligence ───────────────────────────────────────────────
// Single consolidated fetch (GET /api/events/{id}/deep-research) replacing
// what used to be up to 5 independent AI-backed component calls
// (InvestmentThesisCard, ScenarioAnalysis, MonitoringChecklist,
// PatternIntelligenceCard, MultiHorizonOutlookCard) — one request, fired
// once on first expand, result cached in local state for the rest of the
// page's life (no React Query wired up anywhere in this codebase yet; this
// matches the existing fetch-once-on-first-activation pattern used
// elsewhere rather than introducing it just for this one panel).
function DeepIntelligencePanel({ data, initialRelated, open, onToggle }: {
  data: EventDetail; initialRelated?: Record<string, RelatedItem[]> | null; open: boolean; onToggle: () => void;
}) {
  const [dr, setDr] = useState<DeepResearch | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);
  const fetchedRef = useRef(false);

  useEffect(() => {
    if (!open || fetchedRef.current) return;
    fetchedRef.current = true;
    setLoading(true);
    fetch(`${API}/api/events/${data.event.id}/deep-research`)
      .then(r => { if (!r.ok) throw new Error(String(r.status)); return r.json(); })
      .then((j: DeepResearch) => setDr(j))
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, [open, data.event.id]);

  const { facts: eventFacts, sources: eventSources } = buildEventFacts(data);

  return (
    <div className="overflow-hidden rounded-[20px] border border-surface-border/6 bg-text-primary/[0.01]">
      <button onClick={onToggle} className="flex w-full items-center gap-3 px-5 py-4 text-left transition hover:bg-text-primary/[0.03]">
        <div className="flex-1 min-w-0">
          <p className="text-[13px] font-semibold text-text-secondary">Deep Intelligence</p>
          <p className="mt-0.5 text-[11px] text-text-muted">Historical Evidence · Scenario Analysis · Ripple Effects · Risks · Sources</p>
        </div>
        <svg className={`h-4 w-4 shrink-0 text-text-muted transition-transform duration-200 ${open ? "rotate-180" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7"/>
        </svg>
      </button>

      {open && (
        <div className="space-y-4 border-t border-surface-border/6 p-4">
          {loading && (
            <div className="flex items-center gap-3 rounded-xl border border-surface-border/8 bg-text-primary/[0.02] px-4 py-3">
              <div className="h-4 w-4 animate-spin rounded-full border-2 border-violet-400 border-t-transparent"/>
              <span className="text-[13px] text-text-secondary">Loading deeper analysis…</span>
            </div>
          )}
          {error && !loading && (
            <p className="text-[12px] text-text-muted">Deep Intelligence couldn't be loaded right now.</p>
          )}

          {dr && !loading && (
            // Balanced multi-column layout (2026-08 audit, explicit
            // request — same fix as Overview: a fixed left/right group
            // can't stay height-balanced across events, since which
            // sections even render (Scenario Analysis, Risks &
            // Invalidation, Historical Evidence) varies a lot per event.
            // CSS multi-column flow distributes cards by actual rendered
            // height instead, so both columns stay roughly equal
            // regardless of which sections are present this time.
            // `break-inside-avoid` keeps each card intact. Stacks to one
            // column on narrow screens.
            <div className="columns-1 gap-4 lg:columns-2 [column-fill:balance]">
              {/* Historical Evidence — merges what used to be two
                  separate concepts (Historical Comparison + Pattern
                  Intelligence) into one, since both answered "has this
                  happened before" with heavily overlapping,
                  hard-to-trust-separately content. Real similarity search
                  only; deliberately no invented "what happened next"
                  narrative — that outcome isn't tracked anywhere real, so
                  it's omitted rather than guessed. */}
              {dr.historical_patterns.length > 0 && (
                <Card title="Historical Evidence" className="mb-4 break-inside-avoid">
                  <div className="space-y-3">
                    {dr.historical_patterns.slice(0, 3).map((h, i) => (
                      <Link key={i} href={`/events/${h.slug || h.id}`} className="flex items-start gap-3 rounded-xl -m-1 p-1 hover:bg-text-primary/[0.03] transition">
                        <div className="flex h-10 w-10 shrink-0 flex-col items-center justify-center rounded-xl bg-text-primary/[0.05]">
                          <span className="text-[14px] font-black text-text-primary">{h.impact_score !== null && h.impact_score !== undefined ? Math.round(h.impact_score) : "—"}</span>
                        </div>
                        <div className="min-w-0 flex-1">
                          <p className="text-[12px] font-medium text-text-primary line-clamp-2">{h.title}</p>
                          <p className="mt-0.5 text-[10px] text-text-muted">
                            {h.similarity_score !== null && h.similarity_score !== undefined && h.similarity_score > 0 && `${Math.round(h.similarity_score * 100)}% similar · `}
                            {h.event_date ? fmt(h.event_date) : ""}
                          </p>
                          {h.reason && <p className="mt-1 text-[11px] text-text-secondary">{h.reason}</p>}
                        </div>
                      </Link>
                    ))}
                  </div>
                </Card>
              )}

              {/* Scenario Analysis — conditionally rendered. Only made
                  the AI call at all (server-side) when the event is
                  materially high-impact AND genuinely uncertain (see
                  event_deep_research_service._scenario_worthy); a
                  routine low-materiality event or a well-understood
                  high-impact one gets nothing here, not an empty card. */}
              {dr.scenario_status === "shown" && (
                <Card title="Scenario Analysis" className="mb-4 break-inside-avoid">
                  <div className="space-y-3">
                    {dr.scenarios.map(s => {
                      const color = s.label === "Bull" ? "text-emerald-400 border-emerald-500/20" : s.label === "Bear" ? "text-rose-400 border-rose-500/20" : "text-amber-400 border-amber-500/20";
                      return (
                        <div key={s.label} className={`rounded-xl border bg-text-primary/[0.02] p-3 ${color.split(" ")[1]}`}>
                          <div className="mb-1.5 flex items-center justify-between">
                            <p className={`text-[10px] font-bold uppercase tracking-wider ${color.split(" ")[0]}`}>{s.label} Case</p>
                            {s.confidence && <span className="text-[9px] text-text-muted">{s.confidence} confidence</span>}
                          </div>
                          <p className="text-[12px] leading-5 text-text-secondary">{s.outcome}</p>
                          {s.key_drivers.length > 0 && (
                            <ul className="mt-2 space-y-1">
                              {s.key_drivers.map((d, i) => (
                                <li key={i} className="text-[10px] text-text-muted">· {d}</li>
                              ))}
                            </ul>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </Card>
              )}
              {dr.scenario_status === "unavailable" && (
                <p className="mb-4 break-inside-avoid text-[11px] text-text-muted">Scenario analysis temporarily unavailable for this event.</p>
              )}

              {/* Ripple Effects — read-only reuse of the Ripple Engine's
                  own stored graph, Observed/Likely/Potential labeled.
                  Never triggers a fresh ripple generation just from
                  opening this panel — see
                  event_deep_research_service._get_second_order_effects. */}
              <Card title="Ripple Effects" className="mb-4 break-inside-avoid" action={<Link href={`/ripple/${data.event.slug || data.event.id}`} className="text-[11px] text-sky-400 hover:text-sky-600 dark:text-sky-300">Full ripple chain →</Link>}>
                {dr.second_order_effects.length === 0 ? (
                  <p className="text-[12px] text-text-muted">No ripple analysis generated for this event yet.</p>
                ) : (
                  <div className="space-y-2">
                    {dr.second_order_effects.map((e, i) => (
                      <div key={i} className="flex items-start gap-2 text-[12px] leading-5 text-text-secondary">
                        <span className={`mt-0.5 shrink-0 rounded-full border px-1.5 py-0 text-[9px] font-semibold uppercase tracking-wide ${
                          e.status === "observed" ? "border-emerald-500/30 text-emerald-400" : e.status === "likely" ? "border-sky-500/30 text-sky-400" : "border-amber-500/30 text-amber-400"
                        }`}>{e.status}</span>
                        <span>{e.description}</span>
                      </div>
                    ))}
                  </div>
                )}
              </Card>

              {/* Risks & Invalidation — the complete risk list, only
                  shown when it has more to say than Layer 1's "What
                  Could Change This View" already did (same source field;
                  showing an identical short list twice would be exactly
                  the duplication this redesign removed elsewhere). */}
              {dr.risks.length > 3 && (
                <Card title="Risks & Invalidation" className="mb-4 break-inside-avoid">
                  <ul className="space-y-2">
                    {dr.risks.map((r, i) => (
                      <li key={i} className="flex items-start gap-2 text-[13px] leading-5 text-text-secondary">
                        <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-rose-400"/>{r.risk}
                      </li>
                    ))}
                  </ul>
                </Card>
              )}

              {/* Sources & AI Transparency */}
              <Card title="Sources & AI Transparency" className="mb-4 break-inside-avoid">
                <div className="grid grid-cols-3 gap-3 border-b border-surface-border/6 pb-3">
                  <div>
                    <p className="text-[9px] font-bold uppercase tracking-wider text-text-muted">AI Confidence</p>
                    <p className="mt-1 text-[15px] font-bold tabular-nums text-text-primary">{dr.reasoning.confidence !== null && dr.reasoning.confidence !== undefined ? `${Math.round(dr.reasoning.confidence)}%` : "—"}</p>
                  </div>
                  <div>
                    <p className="text-[9px] font-bold uppercase tracking-wider text-text-muted">Sources</p>
                    <p className="mt-1 text-[15px] font-bold tabular-nums text-text-primary">{eventSources.length || "—"}</p>
                  </div>
                  <div>
                    <p className="text-[9px] font-bold uppercase tracking-wider text-text-muted">Updated</p>
                    <p className="mt-1 text-[12px] font-semibold text-text-primary">{dr.reasoning.analysis_timestamp ? fmt(dr.reasoning.analysis_timestamp) : "—"}</p>
                  </div>
                </div>
                {dr.reasoning.summary && <p className="mt-3 text-[12px] leading-5 text-text-secondary">{dr.reasoning.summary}</p>}
                {dr.reasoning.data_used.length > 0 && (
                  <p className="mt-2 text-[11px] text-text-muted">Data used: {dr.reasoning.data_used.join(", ")}</p>
                )}
                {eventFacts.length > 0 && (
                  <ul className="mt-3 space-y-1 border-t border-surface-border/6 pt-3">
                    {eventFacts.slice(0, 6).map((f, i) => (
                      <li key={i} className="text-[11px] leading-5 text-text-secondary">
                        <span className="font-medium text-text-primary">{f.label}</span>{f.detail ? ` — ${f.detail}` : ""}
                      </li>
                    ))}
                  </ul>
                )}
                {/* Source named as plain text, never a clickable
                    off-site link — see feedback_no_external_links. */}
                {eventSources.length > 0 && (
                  <p className="mt-3 text-[11px] text-text-muted">Sources: {eventSources.join(", ")}</p>
                )}
              </Card>
            </div>
          )}

          <RelatedContent
            entityType="event"
            entityId={data.event.id}
            title={data.event.title}
            sector={data.affectedSectors?.[0]?.sector}
            initialData={initialRelated}
          />
        </div>
      )}
    </div>
  );
}

// ── Tab: Companies ────────────────────────────────────────────────────────────
// `companies` is the full identified list; `beneficiaries`/`losers` are the
// subset the backend classified with a clear direction (event_service.py's
// impact_type === "beneficiary"/"loser"). A company can be identified but
// classified neither way (e.g. impact_type "neutral", or unset) — found live
// on a routine "financial results" filing showing "Companies: 1" with both
// beneficiaries and losers empty, so the company silently vanished from this
// tab entirely. The `neutral` group below is exactly that leftover set —
// still rendered, so "1 company identified" never again means "0 shown."
function CompaniesTab({ data }: { data: EventDetail }) {
  if (!data.companies.length) return <Empty msg="Company analysis not yet available."/>;
  const classifiedSymbols = new Set([...data.beneficiaries, ...data.losers].map(c => c.symbol));
  const neutral = data.companies.filter(c => !classifiedSymbols.has(c.symbol));
  const STYLE: Record<string, { badge: string; border: string; bg: string; impact: string }> = {
    emerald: { badge: "bg-emerald-500/20 text-emerald-600 dark:text-emerald-300", border: "border-emerald-500/10", bg: "bg-emerald-500/[0.04]", impact: "text-emerald-400" },
    rose:    { badge: "bg-rose-500/20 text-rose-600 dark:text-rose-300",       border: "border-rose-500/10", bg: "bg-rose-500/[0.04]", impact: "text-rose-400" },
    slate:   { badge: "bg-text-primary/10 text-text-secondary",                border: "border-surface-border/10", bg: "bg-text-primary/[0.02]", impact: "text-text-secondary" },
  };
  return (
    <div className="space-y-4">
      {[
        { list: data.beneficiaries, label: "Beneficiaries",          color: "emerald", tag: "↑ BENEFIT" },
        { list: data.losers,        label: "Negatively Affected",    color: "rose",    tag: "↓ RISK"    },
        { list: neutral,            label: "Mentioned — Impact Unclear", color: "slate", tag: "NEUTRAL"  },
      ].filter(g => g.list.length > 0).map(group => {
        const s = STYLE[group.color];
        return (
        <Card key={group.label} title={group.label}>
          <div className="space-y-2">
            {group.list.map((c, i) => {
              const real = isRealSymbol(c.symbol);
              const avatar = (
                <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-[11px] font-bold ${s.badge} ${real ? "transition hover:opacity-80" : ""}`}>
                  {(real ? c.symbol : c.name).slice(0, 3)}
                </div>
              );
              const nameEl = (
                <span className="text-[13px] font-semibold text-text-primary">{c.name || c.symbol}</span>
              );
              return (
              <div key={i} className={`flex items-center gap-3 rounded-xl border px-3 py-2.5 ${s.border} ${s.bg}`}>
                {real ? <Link href={`/companies/${c.symbol}`}>{avatar}</Link> : avatar}
                <div className="min-w-0 flex-1">
                  {real ? (
                    <Link href={`/companies/${c.symbol}`} className="hover:text-sky-600 dark:text-sky-300 transition">{nameEl}</Link>
                  ) : nameEl}
                  {c.reason && <p className="text-[11px] text-text-muted line-clamp-1">{c.reason}</p>}
                </div>
                <div className="shrink-0 text-right">
                  <p className="text-[10px] text-text-muted">Impact</p>
                  <p className={`text-[14px] font-black ${c.impact_score === null || c.impact_score === undefined ? "text-text-muted" : s.impact}`}>
                    {c.impact_score === null || c.impact_score === undefined ? "—" : c.impact_score.toFixed(0)}
                  </p>
                </div>
                <span className={`rounded-full px-2 py-0.5 text-[9px] font-bold ${s.badge}`}>
                  {group.tag}
                </span>
              </div>
              );
            })}
          </div>
        </Card>
        );
      })}
    </div>
  );
}

// ── Tab: Sectors ──────────────────────────────────────────────────────────────
function SectorsTab({ data }: { data: EventDetail }) {
  if (!data.affectedSectors.length) return <Empty msg="Sector analysis not yet available."/>;
  const realScores = data.affectedSectors
    .map(s => s.impact_score)
    .filter((v): v is number => v !== null && v !== undefined);
  const maxScore = realScores.length ? Math.max(...realScores, 1) : 1;
  return (
    <Card title="Affected Sectors">
      <div className="space-y-3">
        {data.affectedSectors.map((s, i) => {
          const score = s.impact_score;
          return (
            <div key={i}>
              <div className="mb-1 flex items-center justify-between">
                <span className="text-[13px] font-medium text-text-primary">{s.sector}</span>
                <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold capitalize ${impactBg(s.impact)}`}>{s.impact}</span>
              </div>
              <div className="h-1.5 rounded-full bg-text-primary/[0.06]">
                {score !== null && score !== undefined && (
                  <div className={`h-1.5 rounded-full ${s.impact === "positive" ? "bg-emerald-500" : s.impact === "negative" ? "bg-rose-500" : "bg-amber-500"}`}
                    style={{ width: `${(score / maxScore) * 100}%` }}/>
                )}
              </div>
              <p className="mt-0.5 text-[10px] text-text-muted">{score !== null && score !== undefined ? `Score: ${score.toFixed(1)}` : "Score: Unscored"}</p>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

// ── Tab: Timeline ─────────────────────────────────────────────────────────────
function TimelineTab({ data }: { data: EventDetail }) {
  if (!data.timeline.length) return <Empty msg="Timeline will be generated once AI enrichment completes."/>;
  return (
    <Card title="Full Event Timeline">
      <div>
        {data.timeline.map((t, i) => (
          <div key={i} className="flex gap-4">
            <div className="flex flex-col items-center">
              <div className={`mt-1 h-3 w-3 shrink-0 rounded-full border-2 ${i === 0 ? "border-violet-400 bg-violet-400" : "border-surface-border/10 bg-transparent"}`}/>
              {i < data.timeline.length - 1 && <div className="w-0.5 flex-1 bg-text-primary/[0.06] my-1 min-h-[24px]"/>}
            </div>
            <div className="pb-5">
              <p className="text-[11px] text-text-muted mb-0.5">{t.date}</p>
              <p className="text-[14px] font-semibold text-text-primary">{t.title}</p>
              {t.description && <p className="mt-1 text-[13px] leading-5 text-text-secondary">{t.description}</p>}
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}

// ── Tab: Historical ───────────────────────────────────────────────────────────
function HistoricalTab({ data }: { data: EventDetail }) {
  const sectors   = data.affectedSectors.slice(0, 4).map(s => s.sector);
  const sentiment = data.marketReaction?.sentiment ?? undefined;
  const category  = data.event.event_type ?? undefined;

  return (
    <HistoricalMemory
      category={category}
      sectors={sectors}
      sentiment={sentiment}
      limit={10}
    />
  );
}

// ── Tab: Related News ─────────────────────────────────────────────────────────
function NewsTab({ data }: { data: EventDetail }) {
  if (!data.relatedNews.length) return <Empty msg="No related news articles linked to this event yet."/>;
  return (
    <div className="space-y-3">
      {data.relatedNews.map((n, i) => (
        <div key={i} className="flex items-start gap-3 rounded-[20px] border border-surface-border/6 bg-text-primary/[0.02] p-4">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-sky-500/20 text-[13px] font-bold text-sky-600 dark:text-sky-300">
            {srcInitials(n.source)}
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-[14px] font-semibold text-text-primary">{n.headline}</p>
            <p className="mt-0.5 text-[11px] text-text-muted">{n.source} · {n.published_at?.slice(0, 10)}</p>
            {n.summary && <p className="mt-1.5 text-[12px] text-text-secondary line-clamp-2">{n.summary}</p>}
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Tab: Event Intelligence ─────────────────────────────────────────────────────
// Two-layer structure, matching OverviewTab's Level 1/Deep-Research pattern:
// Layer 1 (always visible) is the primary investment stance — Bull/Base/
// Bear case. Layer 2 (collapsed by default, same toggle style as Overview's
// "Deep Research") holds the supplementary detail — market outlook tags,
// key risks, growth catalysts.
function EventIntelligenceTab({ data, intelligence, intelligenceLoading }: {
  data: EventDetail;
  intelligence: IntelligenceObject | null;
  intelligenceLoading: boolean;
}) {
  const ai = data.aiAnalysis;
  const mr = data.marketReaction;
  const hasBullBearBase = Boolean(ai.bull_case || ai.base_case || ai.bear_case);
  const hasOutlook = Object.values(mr).some(Boolean);
  const hasRisks = (ai.key_risks?.length ?? 0) > 0;
  const hasCatalysts = (ai.catalysts?.length ?? 0) > 0;
  const hasLegacyContent = hasBullBearBase || hasOutlook || hasRisks || hasCatalysts;
  const isPending = data.event.enrichment_status !== "done";

  // Two intelligence sources exist for this event: the newer unified
  // /api/intelligence/event/{id} (richer — key takeaway, market story,
  // opportunities, risks, company stance, sectors, themes, historical
  // context, monitoring points) and the older per-event aiAnalysis field
  // (bull/base/bear case, key risks, catalysts). 2026-08 audit — user-
  // reported both were rendering at once (once as a compact block above
  // the tab bar, once as this tab's own content), repeating the same
  // risk/opportunity content in two different shapes. Fix: this tab shows
  // ONE of them — the richer unified source when it has real content,
  // falling back to the legacy fields only when the unified source
  // genuinely has nothing — never both together.
  const hasUnifiedContent = Boolean(intelligence && (intelligence.market_story || intelligence.key_takeaway));

  if (hasUnifiedContent) {
    return <IntelligenceBlock data={intelligence!} compact={false} collapsible={false} twoLayer />;
  }

  if (intelligenceLoading && !hasLegacyContent) {
    return (
      <div className="flex items-center gap-3 rounded-xl border border-surface-border/8 bg-text-primary/[0.02] px-4 py-3">
        <div className="h-4 w-4 animate-spin rounded-full border-2 border-violet-400 border-t-transparent"/>
        <span className="text-[13px] text-text-secondary">Loading intelligence…</span>
      </div>
    );
  }

  // Honest empty state (2026-08 audit — user-reported: tab looked
  // completely blank with no explanation whenever an event's AI analysis
  // hadn't been generated yet, which is common while enrichment is
  // pending/queued/rate-limited). Never silently render nothing.
  if (!hasLegacyContent) {
    return isPending ? (
      <div className="flex items-center gap-3 rounded-xl border border-amber-500/20 bg-amber-500/[0.06] px-4 py-3">
        <div className="h-4 w-4 animate-spin rounded-full border-2 border-amber-400 border-t-transparent"/>
        <div>
          <span className="text-[13px] font-semibold text-amber-600 dark:text-amber-300">AI enrichment in progress</span>
          <span className="ml-2 text-[11px] text-amber-400/70">Bull/bear case, risks, and catalysts will populate automatically.</span>
        </div>
      </div>
    ) : (
      <Empty msg="No AI analysis was generated for this event."/>
    );
  }

  return (
    <div className="space-y-4">
      {/* Layer 1: Bull/Base/Bear case — the core stance, always visible.
          No probability badge — this codebase never presents a fixed,
          unearned percentage as if it were a real computed likelihood. */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        {[
          { label: "Bull Case", v: ai.bull_case, color: "text-emerald-400", border: "border-emerald-500/20" },
          { label: "Base Case", v: ai.base_case, color: "text-amber-400",   border: "border-amber-500/20"  },
          { label: "Bear Case", v: ai.bear_case, color: "text-rose-400",    border: "border-rose-500/20"   },
        ].filter(x => x.v).map(x => (
          <div key={x.label} className={`rounded-[20px] border bg-text-primary/[0.02] p-4 ${x.border}`}>
            <p className={`mb-2 text-[10px] font-bold uppercase tracking-wider ${x.color}`}>{x.label}</p>
            <p className="text-[13px] leading-5 text-text-secondary">{x.v}</p>
          </div>
        ))}
      </div>

      {/* Deeper Analysis — always expanded (2026-08 redesign, explicit
          product feedback: deeper analysis should not be collapsible).
          This is legacy fallback content (only reached when this event
          has no unified /api/intelligence data, see hasUnifiedContent
          above), so it's real analysis the user came here to read, not
          optional extra detail worth hiding behind a click. */}
      {(hasOutlook || hasRisks || hasCatalysts) && (
        <div className="overflow-hidden rounded-[20px] border border-surface-border/6 bg-text-primary/[0.01]">
          <div className="px-5 py-4">
            <p className="text-[13px] font-semibold text-text-secondary">Deeper Analysis</p>
            <p className="mt-0.5 text-[11px] text-text-muted">Market Outlook · Key Risks · Growth Catalysts</p>
          </div>

          <div className="space-y-4 border-t border-surface-border/6 p-4">
              {hasOutlook && (
                <Card title="Market Outlook">
                  <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                    {[
                      { label: "Short Term",  v: mr.short_term  },
                      { label: "Medium Term", v: mr.medium_term },
                      { label: "Volatility",  v: mr.volatility  },
                      { label: "Sentiment",   v: mr.sentiment   },
                    ].map(row => (
                      <div key={row.label} className="rounded-xl border border-surface-border/6 bg-text-primary/[0.02] p-3 text-center">
                        <p className="text-[10px] text-text-muted">{row.label}</p>
                        <span className={`mt-1.5 inline-block rounded-full border px-2.5 py-0.5 text-[11px] font-semibold capitalize ${impactBg(row.v)}`}>
                          {row.v || "—"}
                        </span>
                      </div>
                    ))}
                  </div>
                </Card>
              )}

              <div className="grid grid-cols-2 gap-3">
                {hasRisks && (
                  <Card title="Key Risks">
                    <ul className="space-y-2">
                      {ai.key_risks!.map((r, i) => (
                        <li key={i} className="flex items-start gap-2 text-[13px] text-text-secondary">
                          <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-rose-400"/>{r}
                        </li>
                      ))}
                    </ul>
                  </Card>
                )}
                {hasCatalysts && (
                  <Card title="Growth Catalysts">
                    <ul className="space-y-2">
                      {ai.catalysts!.map((c, i) => (
                        <li key={i} className="flex items-start gap-2 text-[13px] text-text-secondary">
                          <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-emerald-400"/>{c}
                        </li>
                      ))}
                    </ul>
                  </Card>
                )}
              </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Tab: Graph ────────────────────────────────────────────────────────────────
function GraphTab({ data }: { data: EventDetail }) {
  if (!data.graph.nodes.length) return <Empty msg="Knowledge graph will be generated after AI enrichment."/>;
  const rfNodes = data.graph.nodes.map((n, i) => ({
    id: n.id, data: { label: n.label },
    position: { x: 100 + (i % 4) * 200, y: 80 + Math.floor(i / 4) * 140 },
    style: { background: n.type === "event" ? "#6366f1" : n.type === "company" ? "#22c55e" : "#f59e0b", color: "#fff", border: "none", borderRadius: 10, fontSize: 11, padding: "6px 10px" },
  }));
  const rfEdges = data.graph.edges.map((e, i) => ({
    id: `e${i}`, source: e.source, target: e.target, label: e.relationship,
    style: { stroke: "rgb(var(--text-primary) / 0.15)" }, labelStyle: { fill: "#94a3b8", fontSize: 9 },
  }));
  return (
    <div className="h-[600px] w-full overflow-hidden rounded-[20px] border border-surface-border/10">
      <ReactFlow nodes={rfNodes} edges={rfEdges} fitView>
        <Background color="rgb(var(--surface-border))" gap={16}/>
        <Controls style={{ background: "rgb(var(--text-primary) / 0.05)" }}/>
      </ReactFlow>
    </div>
  );
}

// ── Right Panel ───────────────────────────────────────────────────────────────
function RightPanel({
  data, marketData, chartData, chartPeriod, onPeriod,
}: {
  data: EventDetail;
  marketData: MarketData | null;
  chartData: ChartPoint[];
  chartPeriod: string;
  onPeriod: (p: string) => void;
}) {
  const sc = scoreColor(data.impactScore);
  const status  = marketData?.marketStatus;
  const indices = marketData?.marketIndices ?? [];
  const periods = ["1D", "5D", "1M", "3M", "6M"];

  // Mini donut for sector distribution — unscored sectors are omitted
  // rather than given a fabricated minimal slice.
  const sectorData = data.affectedSectors
    .filter(s => s.impact_score !== null && s.impact_score !== undefined)
    .slice(0, 4)
    .map((s, i) => ({
      name: s.sector, value: Math.max(1, s.impact_score as number), color: DONUT_COLORS[i],
    }));

  return (
    <div className="space-y-4">

      {/* Impact breakdown */}
      <Card title="Impact Breakdown">
        <div className="flex items-center justify-center py-2">
          <ScoreRing score={data.impactScore} size={96} />
        </div>
        <div className="mt-3 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-[11px] text-text-muted">Impact Score</span>
            <span className={`text-[12px] font-bold ${sc.text}`}>{hasRealScore(data.impactScore) ? Math.round(data.impactScore) : "—"}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-[11px] text-text-muted">Confidence</span>
            <span className="text-[12px] font-bold text-text-primary">{data.confidence === null || data.confidence === undefined ? "—" : `${Math.round(data.confidence)}%`}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-[11px] text-text-muted">Assessment</span>
            <span className={`rounded-full border px-2 py-0.5 text-[9px] font-semibold ${sc.text} border-current/30`}>
              {scoreLabel(data.impactScore)}
            </span>
          </div>
        </div>
      </Card>

      {/* Sector distribution mini donut */}
      {sectorData.length > 0 && (
        <Card title="Sector Distribution">
          <div className="relative h-[100px]">
            <SectorDonut sectorData={sectorData} />
          </div>
          <div className="mt-2 space-y-1.5">
            {sectorData.map((s, i) => (
              <div key={i} className="flex items-center gap-1.5">
                <div className="h-2 w-2 shrink-0 rounded-full" style={{ background: s.color }}/>
                <span className="flex-1 text-[10px] text-text-secondary truncate">{s.name}</span>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Market Chart */}
      <Card>
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-[12px] font-semibold uppercase tracking-wider text-text-muted">Market Reaction</h3>
          <div className="flex items-center gap-1.5">
            <div className={`h-1.5 w-1.5 rounded-full ${status?.is_open ? "bg-emerald-400 animate-pulse" : "bg-slate-600"}`}/>
            <span className="text-[10px] text-text-muted capitalize">{status?.status ?? "—"}</span>
          </div>
        </div>
        <div className="mb-2 flex gap-1">
          {periods.map(p => (
            <button key={p} onClick={() => onPeriod(p)}
              className={`flex-1 rounded-lg py-1 text-[10px] font-semibold transition ${chartPeriod === p ? "bg-text-primary/[0.10] text-text-primary" : "text-text-muted hover:text-text-secondary"}`}>
              {p}
            </button>
          ))}
        </div>
        <div className="h-[90px] -mx-1">
          {chartData.length > 0 ? (
            <MarketReactionChart chartData={chartData} />
          ) : (
            <div className="flex h-full items-center justify-center">
              <p className="text-[11px] text-text-muted">Fetching market data…</p>
            </div>
          )}
        </div>
        {indices.length > 0 && (
          <div className="mt-3 space-y-2 border-t border-surface-border/6 pt-3">
            {indices.map((idx, i) => (
              <div key={i} className="flex items-center justify-between">
                <span className="text-[11px] text-text-secondary truncate">{idx.name}</span>
                <span className={`text-[12px] font-bold ${idx.positive ? "text-emerald-400" : "text-rose-400"}`}>{idx.change_str || "—"}</span>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Related News quick list */}
      {data.relatedNews.length > 0 && (
        <Card title="Related News">
          <div className="space-y-3">
            {data.relatedNews.slice(0, 3).map((n, i) => (
              <div key={i} className="flex items-start gap-2.5">
                <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-text-primary/[0.06] text-[10px] font-bold text-text-secondary">
                  {srcInitials(n.source)}
                </div>
                <div className="min-w-0">
                  <p className="text-[11px] font-medium text-text-primary line-clamp-2 leading-4">{n.headline}</p>
                  <p className="mt-0.5 text-[10px] text-text-muted">{n.source} · {n.published_at?.slice(0, 10)}</p>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Gov Policies */}
      {data.governmentPolicies.length > 0 && (
        <Card title="Government Policies">
          <div className="space-y-3">
            {data.governmentPolicies.map((p, i) => (
              <div key={i} className="flex items-start gap-2.5 border-b border-surface-border/5 pb-3 last:border-0 last:pb-0">
                <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-violet-500/20">
                  <svg className="h-3.5 w-3.5 text-violet-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
                  </svg>
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-start justify-between gap-1">
                    <p className="text-[12px] font-medium text-text-primary line-clamp-2">{p.title}</p>
                  </div>
                  <p className="text-[10px] text-text-muted">{p.ministry} · {p.announcement_date?.slice(0, 10)}</p>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Historical Memory sidebar preview */}
      <HistoricalMemory
        category={data.event.event_type ?? undefined}
        sectors={data.affectedSectors.slice(0, 4).map(s => s.sector)}
        sentiment={data.marketReaction?.sentiment ?? undefined}
        limit={3}
      />

    </div>
  );
}

// ── VerdictCard ───────────────────────────────────────────────────────────────
function VerdictCard({ data }: { data: EventDetail }) {
  const score = data.impactScore;
  // .find(isRealSymbol), not [0] (2026-08 audit — GSC 404 report):
  // beneficiaries/losers are AI-extracted and can rank a placeholder
  // symbol ("N/A") as the #1 entry; confirmed live via
  // /companies/N/A showing up as a crawled 404 sourced from exactly
  // this unguarded [0] pick (the same array IS guarded elsewhere in
  // this file, e.g. the CompaniesTab list below).
  const topBen = data.beneficiaries.find(c => isRealSymbol(c.symbol));
  const topRisk = data.losers.find(c => isRealSymbol(c.symbol));

  // Tier label derived from the real impact score (not fabricated text) —
  // deliberately doesn't restate why_it_matters, which now has its own
  // dedicated Why It Matters card (2026-08 redesign — repeating it here
  // was the same duplicate the earlier audit already removed once).
  const verdict =
    score === null || score === undefined ? "Impact assessment is still being analysed." :
    score >= 85 ? "This event is actively moving markets. Take notice." :
    score >= 70 ? "Notable market implications — relevant if you hold related stocks." :
    score >= 50 ? "Moderate impact. Monitor if you are exposed to the affected sectors." :
    "Low broad impact — unlikely to affect diversified portfolios significantly.";

  const sc = scoreColor(score);
  const tier = confidenceTier(data.confidence);

  return (
    <div className="mb-5 rounded-[20px] border border-sky-500/[0.15] bg-gradient-to-r from-surface-card to-surface-bg p-5">
      <div className="flex items-start gap-5">
        {/* Verdict */}
        <div className="min-w-0 flex-1">
          <div className="mb-2 flex items-center gap-2">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-sky-400" />
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-sky-400">Investment Verdict</p>
          </div>
          <p className="text-[15px] font-semibold leading-snug text-text-primary">{verdict}</p>
          {tier && <p className="mt-1.5 text-[11px] text-text-muted">Confidence: <span className="font-semibold text-text-secondary">{tier}</span></p>}
        </div>

        {/* Top pick + risk */}
        <div className="flex shrink-0 gap-6 text-right">
          {topBen && (
            <div>
              <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-emerald-500">Top Pick</p>
              <Link href={`/companies/${topBen.symbol}`}
                className="block text-[14px] font-bold text-emerald-600 dark:text-emerald-300 transition hover:text-emerald-700 dark:text-emerald-200">
                {topBen.name || topBen.symbol}
              </Link>
              <p className="text-[10px] text-text-muted">↑ Benefits most</p>
            </div>
          )}
          {topRisk && (
            <div>
              <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-rose-500">Caution</p>
              <Link href={`/companies/${topRisk.symbol}`}
                className="block text-[14px] font-bold text-rose-600 dark:text-rose-300 transition hover:text-rose-700 dark:text-rose-200">
                {topRisk.name || topRisk.symbol}
              </Link>
              <p className="text-[10px] text-text-muted">↓ At risk</p>
            </div>
          )}
        </div>
      </div>

      {/* Action row */}
      <div className="mt-4 flex items-center gap-3 border-t border-surface-border/5 pt-3">
        <Link
          href={`/ai-search?q=${encodeURIComponent(`What should I do about: ${truncateForQuery(data.event.title)}`)}`}
          className="inline-flex items-center gap-1.5 rounded-xl bg-violet-600 px-4 py-2 text-[13px] font-bold text-text-primary transition hover:bg-violet-500"
        >
          <Sparkles className="h-3.5 w-3.5" />
          Ask AI what this means for me
        </Link>
        {topBen && (
          <Link href={`/companies/${topBen.symbol}`}
            className="text-[12px] font-medium text-emerald-400 transition hover:text-emerald-600 dark:text-emerald-300">
            Research {topBen.name || topBen.symbol} →
          </Link>
        )}
        <Link href={`/ripple/${data.event.slug || data.event.id}`}
          className="ml-auto text-[12px] font-medium text-text-muted transition hover:text-text-secondary">
          See ripple chain →
        </Link>
      </div>
    </div>
  );
}

// ── WhatNextSection ───────────────────────────────────────────────────────────
function WhatNextSection({ data }: { data: EventDetail }) {
  const q         = (s: string) => encodeURIComponent(s);
  // .find(isRealSymbol), not [0] — see VerdictCard's identical fix above.
  const topBen    = data.beneficiaries.find(c => isRealSymbol(c.symbol));
  const topRisk   = data.losers.find(c => isRealSymbol(c.symbol));
  const topSec    = data.affectedSectors[0]?.sector;
  const title     = truncateForQuery(data.event.title);
  // Same leftover-set reasoning as CompaniesTab: a company can be identified
  // without a benefit/risk classification. When that's the only company on
  // record, the primary action should still name it instead of falling
  // through to a generic "ask AI" suggestion.
  const classifiedSymbols = new Set([...data.beneficiaries, ...data.losers].map(c => c.symbol));
  const topNeutral = data.companies.find(c => !classifiedSymbols.has(c.symbol) && isRealSymbol(c.symbol));

  return (
    <NextSteps config={{
      // No takeaway here (2026-08 audit — user-reported two "Key
      // Takeaway" blocks on this page): the Event Intelligence tab above
      // already surfaces one via IntelligenceBlock. Repeating a second,
      // differently-derived one at the bottom of every tab was the
      // duplicate, not this section's actual recommendations below.
      primary: topBen ? {
        label: `Research ${topBen.name || topBen.symbol}`,
        why:   `Because they're the highest-conviction beneficiary — this event directly improves their order book and revenue outlook.`,
        href:  `/companies/${topBen.symbol}`,
      } : topNeutral ? {
        label: `Research ${topNeutral.name || topNeutral.symbol}`,
        why:   `Because they're the company this event is actually about — start there before asking AI for a broader read.`,
        href:  `/companies/${topNeutral.symbol}`,
      } : {
        label: `Ask AI: Who benefits most from this event?`,
        why:   `Because identifying specific winners is the first step toward an actionable investment thesis.`,
        href:  `/ai-search?q=${q(`Which companies benefit most from "${title}"?`)}`,
      },
      groups: [
        {
          label: "Understand More",
          actions: [
            {
              label: `Ask AI: How long will this impact last?`,
              why:   `Because duration determines whether to buy now or wait for a better entry after the initial market reaction.`,
              href:  `/ai-search?q=${q(`How long will the market impact of "${title}" last and what should investors do?`)}`,
            },
            topSec ? {
              label: `Trace the ripple across ${topSec}`,
              why:   `Because indirect effects in adjacent sectors often create the best risk-adjusted opportunities.`,
              href:  `/ripple/${data.event.slug || data.event.id}`,
            } : {
              label: "Trace the full ripple chain",
              why:   "Because second-order effects compound — the real opportunity is often two steps removed from the headline.",
              href:  `/ripple/${data.event.slug || data.event.id}`,
            },
          ],
        },
        ...(topRisk ? [{
          label: "Monitor",
          actions: [{
            label: `Watch ${topRisk.name || topRisk.symbol}`,
            why:   `Because they face the most direct headwind — when the risk is fully priced in, that signals a potential entry.`,
            href:  `/companies/${topRisk.symbol}`,
          }],
        }] : []),
      ],
      path: [data.event.event_type || "Event", topSec || "Sector", topBen?.name || topBen?.symbol || "Company", "Investment Thesis"].filter(Boolean) as string[],
    }} />
  );
}

// ── Skeleton ──────────────────────────────────────────────────────────────────
function Skeleton() {
  return (
    <div className="animate-pulse space-y-4">
      <div className="h-8 w-48 rounded-xl bg-text-primary/[0.04]"/>
      <div className="h-28 rounded-[20px] bg-text-primary/[0.04]"/>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {[1,2,3,4].map(i => <div key={i} className="h-24 rounded-[20px] bg-text-primary/[0.04]"/>)}
      </div>
      <div className="h-10 rounded-xl bg-text-primary/[0.04]"/>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_280px]">
        <div className="space-y-3">
          {[160,200,140].map((h,i) => <div key={i} className="rounded-[20px] bg-text-primary/[0.04]" style={{ height: h }}/>)}
        </div>
        <div className="space-y-3">
          {[140,180,120].map((h,i) => <div key={i} className="rounded-[20px] bg-text-primary/[0.04]" style={{ height: h }}/>)}
        </div>
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────
// initialDetail (optional) comes from the server-rendered wrapper
// (page.tsx), which fetches the same /api/events/{id} endpoint server-side
// purely so crawlers and the first paint see real content instead of a
// loading skeleton. This component still fetches its own fresh copy (plus
// market data/chart, which the server wrapper doesn't fetch) exactly as
// before.
export default function EventExplorerPage({ initialDetail, initialRelated }: { initialDetail?: EventDetail | null; initialRelated?: Record<string, RelatedItem[]> | null } = {}) {
  const { id } = useParams<{ id: string }>();
  const [data,        setData]        = useState<EventDetail | null>(initialDetail ?? null);
  const [marketData,  setMarketData]  = useState<MarketData | null>(null);
  const [chartData,   setChartData]   = useState<ChartPoint[]>([]);
  const [chartPeriod, setChartPeriod] = useState("1D");
  const [activeTab,   setActiveTab]   = useState<Tab>("Overview");
  const [loading,     setLoading]     = useState(!initialDetail);
  const [error,       setError]       = useState("");
  // Guards the very first effect run only — see CompanyPageClient.tsx's
  // identical pattern for the full reasoning.
  const skippedFirstResetRef = useRef(!!initialDetail);

  const { data: intelligence, loading: intelligenceLoading } = useIntelligence("event", id || undefined);

  useEffect(() => {
    if (!id) return;
    if (skippedFirstResetRef.current) {
      skippedFirstResetRef.current = false;
    } else {
      setLoading(true);
    }
    Promise.all([
      fetch(`${API}/api/events/${id}`).then(r => { if (!r.ok) throw new Error(`${r.status}`); return r.json(); }),
      fetch(`${API}/api/events/${id}/market-data`).then(r => r.ok ? r.json() : null).catch(() => null),
      fetch(`${API}/api/events/${id}/market-chart?period=1D`).then(r => r.ok ? r.json() : null).catch(() => null),
    ]).then(([evtData, mkt, chart]) => {
      setData(evtData);
      if (mkt)   setMarketData(mkt);
      if (chart) setChartData(chart.data ?? []);
    }).catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [id]);

  const handlePeriod = useCallback(async (period: string) => {
    setChartPeriod(period);
    if (!id) return;
    try {
      const r = await fetch(`${API}/api/events/${id}/market-chart?period=${period}`);
      if (r.ok) { const j = await r.json(); setChartData(j.data ?? []); }
    } catch { /* silent */ }
  }, [id]);

  useEffect(() => {
    if (!id) return;
    const iv = setInterval(async () => {
      try {
        const r = await fetch(`${API}/api/events/${id}/market-data`);
        if (r.ok) setMarketData(await r.json());
      } catch { /* silent */ }
    }, 60_000);
    return () => clearInterval(iv);
  }, [id]);

  // SEO fix: the site-wide breadcrumb otherwise falls back to humanizing
  // the raw id ("nse-bm-139fb66a89" -> "Nse Bm 139fb66a89") — confirmed
  // live, same class of bug as the ripple pages. Overrides with the real
  // event title once loaded.
  useBreadcrumbOverride(
    data?.event?.title ? [{ label: "Events", href: "/events" }, { label: data.event.title }] : null
  );

  if (loading) return <main className="min-w-0 pb-10"><Skeleton/></main>;

  if (error || !data) return (
    <main className="min-w-0 pb-10 flex flex-col items-center justify-center py-32">
      <MailX className="h-8 w-8 text-text-muted mb-3" />
      <p className="text-xl font-bold text-text-secondary">Event not found</p>
      <p className="mt-1 text-[13px] text-text-muted">{error}</p>
      <Link href="/events" className="mt-5 flex items-center gap-1.5 text-sm text-sky-400 hover:text-sky-600 dark:text-sky-300 transition">
        <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7"/>
        </svg>
        Back to Events
      </Link>
    </main>
  );

  const ev = data.event;
  const sc = scoreColor(data.impactScore);

  const CATEGORY_PILL: Record<string,string> = {
    Government: "bg-violet-500/20 text-violet-600 dark:text-violet-300 border-violet-500/30",
    Policy:     "bg-sky-500/20 text-sky-600 dark:text-sky-300 border-sky-500/30",
    Corporate:  "bg-emerald-500/20 text-emerald-600 dark:text-emerald-300 border-emerald-500/30",
    RBI:        "bg-indigo-500/20 text-indigo-600 dark:text-indigo-300 border-indigo-500/30",
    Macro:      "bg-amber-500/20 text-amber-600 dark:text-amber-300 border-amber-500/30",
    Global:     "bg-slate-500/30 text-text-secondary border-surface-border/7",
    Results:    "bg-teal-500/20 text-teal-600 dark:text-teal-300 border-teal-500/30",
  };
  const catPill = CATEGORY_PILL[ev.event_type] ?? "bg-slate-500/20 text-text-secondary border-surface-border/7";
  const titleQuestion = extractQuestion(ev.title);
  const questionAnswer = titleQuestion ? deriveQuestionAnswer(data, titleQuestion) : null;

  return (
    <main className="min-w-0 pb-10">
      <TrackPageVisit type="event" id={ev.id} title={ev.title} subtitle={ev.event_type} href={`/events/${ev.slug || ev.id}`} />
      <MarketContextStrip />

      {/* ── Actions ───────────────────────────────────────────────────── */}
      {/* No breadcrumb here (2026-08 audit — user-reported: this row
          hand-rolled its own "Events / {title}" trail, duplicating both
          the site-wide Breadcrumbs component (rendered once from the root
          layout, with the real BreadcrumbList JSON-LD) and the <h1>/Quick
          Answer directly below, which already restate the title. Only the
          genuinely non-duplicated actions (Share, Watchlist) stay. */}
      <div className="mb-4 flex items-center justify-end gap-2">
        <ShareInsightCard
          entityType="event"
          entityId={ev.id}
          title={ev.title}
          summary={data.summary?.text}
        />
        <button className="flex items-center gap-1.5 rounded-xl border border-violet-500/30 bg-violet-500/10 px-3 py-1.5 text-[12px] text-violet-600 dark:text-violet-300 hover:bg-violet-500/20 transition">
          <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z"/>
          </svg>
          Watchlist
        </button>
      </div>

      {/* ── Contextual quick links ────────────────────────────────────── */}
      <div className="mb-4 flex flex-wrap gap-2">
        <Link href="/market-intelligence"
          className="flex items-center gap-1.5 rounded-full border border-violet-500/30 bg-violet-500/10 px-3 py-1.5 text-[11px] font-semibold text-violet-600 dark:text-violet-300 hover:bg-violet-500/20 transition">
          ✦ Intelligence Feed
        </Link>
        <SmartCTA variant="ask-ai" href={`/ai-search?q=${encodeURIComponent(`What are the investment implications of: ${truncateForQuery(ev.title)}`)}`} />
        {data.beneficiaries?.[0] && (
          <SmartCTA variant="see-companies" href={`/companies/${data.beneficiaries[0].symbol}`} context={data.beneficiaries[0].name || data.beneficiaries[0].symbol} />
        )}
        <SmartCTA variant="view-ripple" href={`/ripple/${ev.slug || ev.id}`} />
      </div>

      {/* ── Event Explorer card ──────────────────────────────────────────── */}
      {/* Restored per explicit request (2026-08 audit) — kept as the main
          event-identity display; the redundant plain-text description in
          page.tsx's server-rendered header was removed instead, so this
          card's own description is no longer said twice on the page. */}
      <div className="mb-5">
        <p className="mb-1 text-[11px] font-semibold uppercase tracking-[0.22em] text-text-muted">Event Explorer</p>
        <div className="rounded-[24px] border border-surface-border/8 bg-text-primary/[0.025] p-5">
          <div className="flex items-start gap-5">
            <div className="min-w-0 flex-1">
              <div className="mb-2 flex flex-wrap items-center gap-2">
                <span className={`rounded-full border px-2.5 py-0.5 text-[10px] font-medium ${catPill}`}>{mapCategory(ev.event_type || "Event")}</span>
                {hasRealScore(data.impactScore) && (
                  <span className={`rounded-full border px-2.5 py-0.5 text-[10px] font-semibold ${sc.text} border-current/20`}>
                    {scoreLabel(data.impactScore)}
                  </span>
                )}
                {ev.enrichment_status !== "done" && (
                  <span className="flex items-center gap-1 rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-[10px] text-amber-600 dark:text-amber-300">
                    <div className="h-1.5 w-1.5 animate-pulse rounded-full bg-amber-400"/>
                    AI enriching…
                  </span>
                )}
              </div>
              {/* The server wrapper (page.tsx) renders the real <h1> when
                  it found the event server-side (the common case) — falls
                  back to rendering it here too if that fetch ever came
                  back empty. */}
              {initialDetail ? (
                <p className="text-xl font-bold leading-snug text-text-primary">{ev.title}</p>
              ) : (
                <h1 className="text-xl font-bold leading-snug text-text-primary">{ev.title}</h1>
              )}
              {titleQuestion && (
                <div className="mt-3 rounded-xl border border-sky-500/15 bg-sky-500/[0.04] p-3">
                  <p className="text-[10px] font-bold uppercase tracking-wider text-sky-500">Question</p>
                  <p className="mt-0.5 text-[13px] font-medium text-text-primary">{titleQuestion}</p>
                  {questionAnswer ? (
                    <>
                      <p className="mt-2 text-[10px] font-bold uppercase tracking-wider text-text-muted">Answer</p>
                      <p className="mt-0.5 text-[12px] leading-5 text-text-secondary">{questionAnswer}</p>
                    </>
                  ) : (
                    <p className="mt-2 text-[11px] text-text-muted">Not yet answered — no verified commentary or further detail has been captured for this event yet.</p>
                  )}
                </div>
              )}
              {/* No description line here (2026-08 audit, per explicit
                  request) — this exact text (truncated) was one of three
                  near-identical renderings above the fold; the Overview
                  tab's What Happened card just below is now the single
                  real place for it, shown in full, not clipped. */}
              <div className="mt-2 flex flex-wrap items-center gap-3 text-[11px] text-text-muted">
                {ev.event_date && <span>{fmt(ev.event_date)}</span>}
                {ev.source && <><span>·</span><span>{ev.source}</span></>}
              </div>
            </div>
            <div className="flex shrink-0 items-center gap-4">
              <div className="text-center">
                <ScoreRing score={data.impactScore} size={80}/>
                <p className="mt-1 text-[10px] text-text-muted">Impact</p>
              </div>
              <div className="text-center">
                <ScoreRing score={data.confidence} size={80}/>
                <p className="mt-1 text-[10px] text-text-muted">Confidence</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ── KPI cards ─────────────────────────────────────────────────────── */}
      <div className="mb-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <KpiCard label="Impact Score"       value={hasRealScore(data.impactScore) ? Math.round(data.impactScore) : "—"} sub={hasRealScore(data.impactScore) ? scoreLabel(data.impactScore) : "Pending analysis"} icon={<Target className="h-4 w-4" />} color={sc.text} border={`${sc.border}/20`}/>
        <KpiCard label="Companies Affected" value={data.companies.length || "—"} sub={`${data.beneficiaries.length} benefit · ${data.losers.length} at risk`} icon={<Building2 className="h-4 w-4" />} color="text-sky-400"     border="border-sky-500/15"/>
        <KpiCard label="Sectors Impacted"   value={data.affectedSectors.length || "—"} sub={data.affectedSectors[0]?.sector ?? "Analyzing…"} icon={<BarChart2 className="h-4 w-4" />} color="text-emerald-400" border="border-emerald-500/15"/>
        <KpiCard label="Confidence Level"   value={data.confidence !== null && data.confidence !== undefined ? `${Math.round(data.confidence)}%` : "—"} sub={data.confidence === null || data.confidence === undefined ? "Unscored" : data.confidence >= 80 ? "High Confidence" : data.confidence >= 60 ? "Moderate" : "Low Confidence"} icon={<Sparkles className="h-4 w-4" />} color="text-violet-400" border="border-violet-500/15"/>
      </div>

      {/* ── Verdict card ─────────────────────────────────────────────────── */}
      {hasRealScore(data.impactScore) && <VerdictCard data={data} />}

      {/* ── Tab bar ───────────────────────────────────────────────────────── */}
      <div className="mb-5 flex items-center overflow-x-auto border-b border-surface-border/6 scrollbar-hide" role="tablist">
        {TABS.map(tab => (
          <button key={tab} onClick={() => setActiveTab(tab)}
            role="tab"
            aria-selected={activeTab === tab}
            id={`tab-${tab.toLowerCase().replace(/\s+/g, "-")}`}
            className={`-mb-px whitespace-nowrap px-4 py-2.5 text-[13px] font-medium transition border-b-2 ${
              activeTab === tab
                ? "border-violet-500 text-text-primary"
                : "border-transparent text-text-muted hover:text-text-secondary"
            }`}>
            {tab}
            {tab === "Companies" && data.companies.length > 0 && (
              <span className="ml-1.5 rounded-full bg-text-primary/[0.08] px-1.5 py-0.5 text-[9px] text-text-secondary">{data.companies.length}</span>
            )}
            {tab === "Related News" && data.relatedNews.length > 0 && (
              <span className="ml-1.5 rounded-full bg-text-primary/[0.08] px-1.5 py-0.5 text-[9px] text-text-secondary">{data.relatedNews.length}</span>
            )}
          </button>
        ))}
      </div>

      {/* ── Content + Right panel ─────────────────────────────────────────── */}
      <div className="grid grid-cols-1 items-start gap-5 lg:grid-cols-[1fr_280px]">
        <div className="min-w-0" role="tabpanel" aria-labelledby={`tab-${activeTab.toLowerCase().replace(/\s+/g, "-")}`}>
          {activeTab === "Overview"      && <OverviewTab   data={data} goTab={setActiveTab} initialRelated={initialRelated}/>}
          {activeTab === "Companies"     && <CompaniesTab  data={data}/>}
          {activeTab === "Sectors"       && <SectorsTab    data={data}/>}
          {activeTab === "Timeline"      && <TimelineTab   data={data}/>}
          {activeTab === "Historical"    && <HistoricalTab data={data}/>}
          {activeTab === "Related News"  && <NewsTab       data={data}/>}
          {activeTab === "Event Intelligence" && <EventIntelligenceTab data={data} intelligence={intelligence} intelligenceLoading={intelligenceLoading}/>}
          {activeTab === "Graph"         && <GraphTab      data={data}/>}

          <WhatNextSection data={data} />
        </div>

        <aside className="lg:sticky lg:top-[84px]">
          <RightPanel
            data={data}
            marketData={marketData}
            chartData={chartData}
            chartPeriod={chartPeriod}
            onPeriod={handlePeriod}
          />
        </aside>
      </div>
    </main>
  );
}
