import { notFound } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft, Share2, Bookmark, Star, CheckCircle2, Info,
  Calendar, TrendingUp, TrendingDown, ChevronRight, Zap,
  AlertCircle, Building2, Layers, BookOpen, Clock, ExternalLink,
} from "lucide-react";
import MiniIntelligenceGraph, { makeNodeId } from "@/components/MiniIntelligenceGraph";

export const dynamic = "force-dynamic";

const API = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

// ── Data fetch ─────────────────────────────────────────────────────────────────
async function fetchArticle(slug: string) {
  try {
    const r = await fetch(`${API}/api/publishing/articles/${slug}`, { cache: "no-store" });
    if (!r.ok) return null;
    return r.json();
  } catch { return null; }
}

// ── Helpers ────────────────────────────────────────────────────────────────────
function timeAgo(iso: string | null | undefined): string {
  if (!iso) return "";
  const mins = Math.floor((Date.now() - new Date(iso).getTime()) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  if (mins < 1440) return `${Math.floor(mins / 60)}h ago`;
  return `${Math.floor(mins / 1440)}d ago`;
}

function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-IN", {
    day: "numeric", month: "short", year: "numeric",
  });
}

function fmtDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString("en-IN", {
    timeZone: "Asia/Kolkata", day: "numeric", month: "short",
    year: "numeric", hour: "2-digit", minute: "2-digit",
  }) + " IST";
}

function confLabel(score: number | null | undefined): string {
  const n = (score ?? 0) * 100;
  if (n >= 80) return "High";
  if (n >= 60) return "Medium";
  return "Low";
}

function confColor(score: number | null | undefined): string {
  const n = (score ?? 0) * 100;
  if (n >= 80) return "text-emerald-400";
  if (n >= 60) return "text-amber-400";
  return "text-rose-400";
}

function impactColor(impact: string): string {
  const i = (impact ?? "").toLowerCase();
  if (/high|strong|positive/.test(i)) return "text-emerald-400";
  if (/medium|neutral/.test(i))       return "text-amber-400";
  return "text-rose-400";
}

function sentimentPill(s: string) {
  const low = (s ?? "").toLowerCase();
  if (/positive|bullish/.test(low))  return "bg-emerald-500/15 text-emerald-400 border-emerald-500/25";
  if (/negative|bearish/.test(low))  return "bg-rose-500/15 text-rose-400 border-rose-500/25";
  return "bg-amber-500/15 text-amber-400 border-amber-500/25";
}

function articleTypeLabel(t: string) {
  const labels: Record<string, string> = {
    breaking: "Breaking",
    morning_intelligence: "Morning Intelligence",
    market_wrap: "Market Wrap",
    event_analysis: "Event Analysis",
    company_intelligence: "Company Intelligence",
    sector_intelligence: "Sector Intelligence",
    theme_intelligence: "Theme Intelligence",
    policy_intelligence: "Policy Intelligence",
    opportunity_intelligence: "Opportunity Intelligence",
    ripple_intelligence: "Ripple Intelligence",
    educational_intelligence: "Educational",
  };
  return labels[t] ?? t.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
}

function readTime(text: string): number {
  return Math.max(3, Math.ceil((text ?? "").split(/\s+/).length / 200));
}

// Mini bar chart (SVG sparkline for historical events)
function Sparkline({ values }: { values: number[] }) {
  if (!values.length) return null;
  const max = Math.max(...values.map(Math.abs), 0.01);
  const w = 80, h = 30, bw = 8, gap = 4;
  const bars = values.slice(-7);
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} className="shrink-0">
      {bars.map((v, i) => {
        const pct = Math.abs(v) / max;
        const bh  = Math.max(3, pct * (h - 4));
        const x   = i * (bw + gap);
        const y   = v >= 0 ? h - bh : 0;
        return <rect key={i} x={x} y={y} width={bw} height={bh}
          fill={v >= 0 ? "#34d399" : "#f87171"} rx={2} />;
      })}
    </svg>
  );
}

// Sector impact bar
function SectorBar({ impact }: { impact: string }) {
  const i = (impact ?? "").toLowerCase();
  const pct = /high.*positive/.test(i) ? 85
    : /positive/.test(i)     ? 60
    : /neutral/.test(i)      ? 40
    : /slight/.test(i)       ? 25
    : /negative/.test(i)     ? 20 : 40;
  const bg = /positive/.test(i) ? "bg-emerald-500"
    : /negative/.test(i)    ? "bg-rose-500"
    : "bg-amber-500";
  const label = impact || "Neutral";
  const labelCls = /positive/.test(i) ? "text-emerald-400"
    : /negative/.test(i) ? "text-rose-400" : "text-amber-400";
  return (
    <div className="flex items-center gap-2 min-w-0">
      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-white/[0.06]">
        <div className={`h-full rounded-full ${bg}`} style={{ width: `${pct}%` }} />
      </div>
      <span className={`shrink-0 text-[10px] font-semibold capitalize ${labelCls}`}>{label}</span>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// PAGE
// ═══════════════════════════════════════════════════════════════════════════════
export default async function IntelligenceArticlePage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const art = await fetchArticle(slug);
  if (!art) notFound();

  const confPct        = Math.round((art.confidence_score ?? 0) * 100);
  const sectors        = (art.sectors_affected ?? []) as any[];
  const companies      = (art.companies_affected ?? art.related_companies ?? []) as any[];
  const relCompanies   = (art.related_companies ?? []) as any[];
  const rippleEffect   = (art.ripple_effect ?? []) as any[];
  const watchNext      = (art.what_to_watch_next ?? []) as any[];
  const historical     = (art.historical_events ?? []) as any[];
  const faqs           = (art.faqs ?? []) as any[];
  const sources        = (art.sources ?? []) as any[];
  const relThemes      = (art.related_themes ?? []) as any[];
  const market         = art.market_context ?? {};
  const allText        = [art.what_happened, art.executive_summary, art.why_it_matters].filter(Boolean).join(" ");
  const readMinutes    = readTime(allText);

  // Extract horizon from market context or article type
  const horizon = market.horizon
    ?? (art.article_type === "breaking" ? "Intraday" : "Short Term (1–4 weeks)");

  // Impact label for summary sidebar
  const impactStr = sectors[0]?.impact
    ?? (art.confidence_score >= 0.7 ? "Market Positive" : "Market Neutral");

  // Parse what_happened into bullets if it contains newline-separated lines
  const whatHappenedBullets: string[] = [];
  let whatHappenedProse = art.what_happened ?? "";
  if (whatHappenedProse) {
    const lines = whatHappenedProse.split(/\n+/).filter((l: string) => l.trim().startsWith("-") || l.trim().startsWith("•") || l.trim().startsWith("*"));
    if (lines.length >= 2) {
      whatHappenedBullets.push(...lines.map((l: string) => l.replace(/^[-•*]\s*/, "").trim()));
      whatHappenedProse = whatHappenedProse.split("\n")[0] ?? "";
    }
  }

  // Suggested AI questions
  const suggestedQuestions = [
    `How will this impact ${sectors[0]?.name ?? art.article_type.replace(/_/g, " ")} stocks?`,
    watchNext[0] ? `What should I watch for ${watchNext[0].title ?? "next"}?` : null,
    companies[0] ? `Should I buy or sell ${typeof companies[0] === "string" ? companies[0] : companies[0]?.name ?? companies[0]?.symbol}?` : null,
  ].filter(Boolean).slice(0, 3) as string[];

  return (
    <div className="min-h-screen bg-[#020617]">
      <div className="mx-auto max-w-[1280px] px-5 py-8 md:px-8">

        {/* Back nav */}
        <Link href="/market-intelligence"
          className="mb-6 inline-flex items-center gap-1.5 text-[12px] font-medium text-slate-500 hover:text-slate-300 transition">
          <ArrowLeft className="h-3.5 w-3.5" />
          Back to Intelligence
        </Link>

        <div className="grid grid-cols-1 gap-8 lg:grid-cols-[1fr_320px]">

          {/* ══ LEFT COLUMN ══════════════════════════════════════════════════════ */}
          <div className="space-y-8 min-w-0">

            {/* ── 1. Header ─────────────────────────────────────────────────── */}
            <header>
              {/* Category tags */}
              <div className="mb-4 flex flex-wrap items-center gap-2">
                <span className="rounded-full bg-violet-500/20 border border-violet-500/30 px-3 py-1 text-[10px] font-black uppercase tracking-wider text-violet-400">
                  AI Intelligence
                </span>
                <span className="rounded-full border border-white/[0.1] bg-white/[0.04] px-3 py-1 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
                  {articleTypeLabel(art.article_type)}
                </span>
                {art.lifecycle_status === "updated" && (
                  <span className="rounded-full bg-amber-500/15 border border-amber-500/25 px-3 py-1 text-[10px] font-black uppercase tracking-wider text-amber-400">
                    Updated ×{art.update_count}
                  </span>
                )}
              </div>

              {/* Headline + confidence */}
              <div className="flex items-start justify-between gap-6">
                <h1 className="text-[28px] font-black leading-[1.2] tracking-tight text-white md:text-[34px]">
                  {art.headline}
                </h1>
                {/* Confidence card */}
                {confPct > 0 && (
                  <div className="hidden shrink-0 flex-col items-center rounded-2xl border border-white/[0.1] bg-[#060e1e] p-4 text-center sm:flex" style={{ minWidth: 100 }}>
                    <p className="mb-1 text-[9px] font-bold uppercase tracking-wider text-slate-500">Confidence</p>
                    <p className={`text-[26px] font-black tabular-nums ${confColor(art.confidence_score)}`}>{confPct}%</p>
                    <p className={`text-[10px] font-semibold ${confColor(art.confidence_score)}`}>{confLabel(art.confidence_score)}</p>
                    <button className="mt-1.5 text-slate-600 hover:text-slate-400 transition"><Info className="h-3 w-3" /></button>
                  </div>
                )}
              </div>

              {/* Executive summary */}
              {art.executive_summary && (
                <p className="mt-4 max-w-[620px] text-[15px] leading-[1.75] text-slate-300">
                  {art.executive_summary}
                </p>
              )}

              {/* Author row */}
              <div className="mt-5 flex flex-wrap items-center gap-3 text-[12px] text-slate-500">
                <div className="flex items-center gap-2">
                  <div className="flex h-7 w-7 items-center justify-center rounded-full bg-gradient-to-br from-violet-500 to-sky-500 text-[9px] font-black text-white">AI</div>
                  <span className="font-semibold text-slate-300">AI Intelligence Engine</span>
                  <span className="h-3.5 w-3.5 rounded-full bg-violet-500/80 flex items-center justify-center text-[8px] text-white">✓</span>
                </div>
                <span className="text-slate-700">·</span>
                {art.last_updated
                  ? <span>Updated {fmtDateTime(art.last_updated)}</span>
                  : <span>Published {fmtDateTime(art.published_at)}</span>
                }
                <span className="text-slate-700">·</span>
                <span>{readMinutes} min read</span>
                {sources.length > 0 && (
                  <>
                    <span className="text-slate-700">·</span>
                    <span>{sources.length} sources</span>
                  </>
                )}
              </div>
            </header>

            {/* ── 2. Key Takeaway ───────────────────────────────────────────── */}
            {art.key_takeaway && (
              <div className="flex items-start gap-4 rounded-2xl border border-emerald-500/25 bg-emerald-500/[0.06] p-5">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-emerald-500/30 bg-emerald-500/15">
                  <Star className="h-5 w-5 text-emerald-400" fill="currentColor" />
                </div>
                <div>
                  <p className="mb-1.5 text-[11px] font-black uppercase tracking-wider text-emerald-400">Key Takeaway</p>
                  <p className="text-[14px] leading-[1.7] text-slate-200">{art.key_takeaway}</p>
                </div>
              </div>
            )}

            {/* ── 3. What Happened ──────────────────────────────────────────── */}
            {art.what_happened && (
              <section>
                <h2 className="mb-4 text-[20px] font-black text-white">What Happened?</h2>
                <div className="grid grid-cols-1 gap-5 md:grid-cols-[1fr_180px]">
                  <div>
                    <p className="mb-4 text-[14px] leading-[1.8] text-slate-300">{whatHappenedProse}</p>
                    {whatHappenedBullets.length > 0 && (
                      <ul className="space-y-2">
                        {whatHappenedBullets.map((b, i) => (
                          <li key={i} className="flex items-start gap-2.5">
                            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" />
                            <span className="text-[13px] leading-[1.6] text-slate-300">{b}</span>
                          </li>
                        ))}
                      </ul>
                    )}
                    {whatHappenedBullets.length === 0 && art.why_it_matters && (
                      <p className="mt-3 text-[13px] leading-[1.8] text-slate-400">{art.why_it_matters}</p>
                    )}
                  </div>
                  {/* Image placeholder / market context card */}
                  <div className="hidden md:flex items-center justify-center rounded-2xl border border-white/[0.07] bg-[#060e1e] p-4">
                    <div className="text-center">
                      {art.article_type === "policy_intelligence" || art.article_type === "event_analysis" ? (
                        <>
                          <div className="mx-auto mb-2 flex h-14 w-14 items-center justify-center rounded-full border border-white/[0.1] bg-white/[0.05]">
                            <Layers className="h-6 w-6 text-violet-400" />
                          </div>
                          <p className="text-[10px] font-semibold text-slate-600 uppercase tracking-wide">{market.session ?? "Market Analysis"}</p>
                        </>
                      ) : (
                        <>
                          <div className="mx-auto mb-2 flex h-14 w-14 items-center justify-center rounded-full border border-white/[0.1] bg-white/[0.05]">
                            <TrendingUp className="h-6 w-6 text-emerald-400" />
                          </div>
                          <p className="text-[10px] font-semibold text-slate-600 uppercase tracking-wide">AI Analysis</p>
                        </>
                      )}
                      {market.nifty && (
                        <p className="mt-2 text-[13px] font-bold text-white">Nifty {market.nifty}</p>
                      )}
                      {market.mood && (
                        <p className="mt-0.5 text-[10px] text-slate-500">{market.mood}</p>
                      )}
                    </div>
                  </div>
                </div>
              </section>
            )}

            {/* ── 4. Why It Matters / Ripple Effect cards ───────────────────── */}
            {(rippleEffect.length > 0 || (sectors.length > 0 && art.why_it_matters)) && (
              <section>
                <h2 className="mb-4 text-[20px] font-black text-white">Why It Matters</h2>
                {rippleEffect.length > 0 ? (
                  <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                    {rippleEffect.slice(0, 4).map((r: any, i: number) => {
                      const icons = ["🏛️", "👥", "📈", "🌐"];
                      const titles = ["For Banks", "For Borrowers", "For the Market", "For Economy"];
                      const title = r.audience ?? r.title ?? r.sector ?? titles[i] ?? `Impact ${i + 1}`;
                      const desc  = r.effect ?? r.description ?? r.impact ?? "";
                      const sent  = r.sentiment ?? "neutral";
                      return (
                        <div key={i} className="flex flex-col rounded-2xl border border-white/[0.07] bg-[#060e1e] p-4 transition hover:border-white/[0.12]">
                          <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-xl border border-white/[0.08] bg-white/[0.04] text-[20px]">
                            {icons[i] ?? "📊"}
                          </div>
                          <p className="mb-2 text-[13px] font-bold text-white">For {title.replace(/^for\s+/i, "")}</p>
                          <p className="flex-1 text-[11px] leading-[1.6] text-slate-500">{desc}</p>
                          {sent && (
                            <div className="mt-3 flex items-center gap-1">
                              {/positive|bullish/i.test(sent) ? <TrendingUp className="h-3 w-3 text-emerald-400" /> : /negative|bearish/i.test(sent) ? <TrendingDown className="h-3 w-3 text-rose-400" /> : <span className="text-slate-500 text-[10px]">—</span>}
                              <span className={`text-[10px] font-semibold capitalize ${/positive|bullish/i.test(sent) ? "text-emerald-400" : /negative|bearish/i.test(sent) ? "text-rose-400" : "text-amber-400"}`}>
                                {sent}
                              </span>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <p className="text-[14px] leading-[1.8] text-slate-300">{art.why_it_matters}</p>
                )}
              </section>
            )}

            {/* ── 5. Historical Context ─────────────────────────────────────── */}
            {historical.length > 0 && (
              <section>
                <h2 className="mb-1.5 text-[20px] font-black text-white">Historical Context</h2>
                {art.executive_summary && (
                  <p className="mb-4 text-[12px] text-slate-500">
                    {historical.length} similar historical events found in our database
                  </p>
                )}
                <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                  {/* Table */}
                  <div className="overflow-x-auto rounded-2xl border border-white/[0.07] bg-[#060e1e]">
                    <table className="w-full text-left">
                      <thead>
                        <tr className="border-b border-white/[0.06]">
                          <th className="px-4 py-3 text-[9px] font-bold uppercase tracking-wider text-slate-600">Date</th>
                          <th className="px-4 py-3 text-[9px] font-bold uppercase tracking-wider text-slate-600">Event</th>
                          <th className="px-4 py-3 text-[9px] font-bold uppercase tracking-wider text-slate-600">Nifty</th>
                          <th className="px-4 py-3 text-[9px] font-bold uppercase tracking-wider text-slate-600">Outcome</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-white/[0.04]">
                        {historical.slice(0, 5).map((h: any, i: number) => {
                          const outcome = h.outcome ?? h.nifty_change ?? h.change ?? 0;
                          const pos = parseFloat(String(outcome)) >= 0;
                          return (
                            <tr key={i} className="hover:bg-white/[0.02]">
                              <td className="px-4 py-2.5 text-[11px] text-slate-500">{h.date ? fmtDate(h.date) : "—"}</td>
                              <td className="px-4 py-2.5 text-[11px] font-medium text-slate-300 max-w-[120px] truncate">{h.event ?? h.title ?? "Market Event"}</td>
                              <td className="px-4 py-2.5 text-[11px] font-semibold tabular-nums">
                                {h.nifty_level ?? "—"}
                              </td>
                              <td className={`px-4 py-2.5 text-[11px] font-bold tabular-nums ${pos ? "text-emerald-400" : "text-rose-400"}`}>
                                {outcome != null ? `${pos ? "+" : ""}${parseFloat(String(outcome)).toFixed(2)}%` : "—"}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                    <p className="border-t border-white/[0.04] px-4 py-2.5 text-[10px] text-slate-700">
                      Source: NSE India, Artha Intelligence Engine
                    </p>
                  </div>

                  {/* Bar chart */}
                  <div className="rounded-2xl border border-white/[0.07] bg-[#060e1e] p-5">
                    <p className="mb-4 text-[12px] font-bold text-white">
                      Performance After Similar Events
                    </p>
                    <div className="flex h-[140px] items-end gap-3">
                      {historical.slice(0, 5).map((h: any, i: number) => {
                        const v = parseFloat(String(h.outcome ?? h.nifty_change ?? 0));
                        const max = Math.max(...historical.slice(0, 5).map((x: any) => Math.abs(parseFloat(String(x.outcome ?? x.nifty_change ?? 0)))), 1);
                        const pct = Math.abs(v) / max * 100;
                        const pos = v >= 0;
                        const label = h.date ? new Date(h.date).toLocaleDateString("en-IN", { day: "2-digit", month: "short" }) : `Ev ${i + 1}`;
                        return (
                          <div key={i} className="flex flex-1 flex-col items-center gap-1">
                            <span className={`text-[9px] font-bold tabular-nums ${pos ? "text-emerald-400" : "text-rose-400"}`}>
                              {v >= 0 ? "+" : ""}{v.toFixed(2)}%
                            </span>
                            <div className="flex flex-1 w-full items-end">
                              <div
                                className={`w-full rounded-t-lg ${pos ? "bg-emerald-500" : "bg-rose-500"}`}
                                style={{ height: `${Math.max(4, pct)}%` }}
                              />
                            </div>
                            <span className="text-[8px] text-slate-600 text-center">{label}</span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </div>
              </section>
            )}

            {/* ── 6. Opportunities & Risks (if available) ───────────────────── */}
            {((art.opportunities?.length ?? 0) > 0 || (art.risks?.length ?? 0) > 0) && (
              <section>
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  {art.opportunities?.length > 0 && (
                    <div className="rounded-2xl border border-emerald-500/[0.12] bg-[#060e1e] p-5">
                      <p className="mb-3 flex items-center gap-2 text-[11px] font-black uppercase tracking-wider text-emerald-400">
                        <TrendingUp className="h-3.5 w-3.5" /> Opportunities
                      </p>
                      <ul className="space-y-2">
                        {art.opportunities.slice(0, 3).map((o: any, i: number) => (
                          <li key={i} className="flex items-start gap-2">
                            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-emerald-400" />
                            <span className="text-[12px] leading-[1.6] text-slate-300">{typeof o === "string" ? o : o.description ?? o.opportunity ?? o.text ?? JSON.stringify(o)}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {art.risks?.length > 0 && (
                    <div className="rounded-2xl border border-rose-500/[0.12] bg-[#060e1e] p-5">
                      <p className="mb-3 flex items-center gap-2 text-[11px] font-black uppercase tracking-wider text-rose-400">
                        <AlertCircle className="h-3.5 w-3.5" /> Risks to Watch
                      </p>
                      <ul className="space-y-2">
                        {art.risks.slice(0, 3).map((r: any, i: number) => (
                          <li key={i} className="flex items-start gap-2">
                            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-rose-400" />
                            <span className="text-[12px] leading-[1.6] text-slate-300">{typeof r === "string" ? r : r.description ?? r.risk ?? r.text ?? JSON.stringify(r)}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              </section>
            )}

            {/* ── 7. What to Watch Next ─────────────────────────────────────── */}
            {watchNext.length > 0 && (
              <section>
                <h2 className="mb-4 text-[20px] font-black text-white">What to Watch Next</h2>
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
                  {watchNext.slice(0, 4).map((w: any, i: number) => {
                    const title = typeof w === "string" ? w : (w.title ?? w.event ?? `Watch Item ${i + 1}`);
                    const desc  = typeof w === "string" ? "" : (w.description ?? w.why ?? w.reason ?? "");
                    const date  = typeof w === "object" ? (w.date ?? w.expected_date ?? "") : "";
                    const icons = [Calendar, TrendingUp, BookOpen, Layers];
                    const Ic = icons[i % 4];
                    return (
                      <div key={i} className="flex flex-col rounded-2xl border border-white/[0.07] bg-[#060e1e] p-4 transition hover:border-violet-500/20">
                        <div className="mb-3 flex h-9 w-9 items-center justify-center rounded-xl border border-white/[0.08] bg-white/[0.04]">
                          <Ic className="h-4 w-4 text-violet-400" />
                        </div>
                        <p className="mb-1.5 text-[12px] font-bold text-white">{title}</p>
                        {desc && <p className="flex-1 text-[11px] leading-[1.5] text-slate-500">{desc}</p>}
                        {date && (
                          <p className="mt-2 flex items-center gap-1 text-[10px] text-slate-600">
                            <Clock className="h-3 w-3" /> {date}
                          </p>
                        )}
                      </div>
                    );
                  })}
                </div>
              </section>
            )}

            {/* ── 8. FAQs ───────────────────────────────────────────────────── */}
            {faqs.length > 0 && (
              <section>
                <h2 className="mb-4 text-[20px] font-black text-white">Frequently Asked Questions</h2>
                <div className="space-y-3">
                  {faqs.map((f: any, i: number) => {
                    const q = typeof f === "string" ? f : (f.question ?? f.q ?? `Question ${i + 1}`);
                    const a = typeof f === "string" ? "" : (f.answer ?? f.a ?? "");
                    return (
                      <details key={i} className="group rounded-2xl border border-white/[0.07] bg-[#060e1e] open:border-violet-500/20">
                        <summary className="flex cursor-pointer items-center justify-between gap-3 px-5 py-4 text-[13px] font-semibold text-white list-none">
                          {q}
                          <ChevronRight className="h-4 w-4 shrink-0 text-slate-600 transition group-open:rotate-90" />
                        </summary>
                        {a && <p className="px-5 pb-4 text-[13px] leading-[1.7] text-slate-400">{a}</p>}
                      </details>
                    );
                  })}
                </div>
              </section>
            )}

            {/* ── 9. Ask AI Follow-up ───────────────────────────────────────── */}
            <section className="rounded-2xl border border-white/[0.07] bg-[#060e1e] p-6">
              <div className="mb-3 flex items-center gap-2">
                <Zap className="h-4 w-4 text-violet-400" />
                <p className="text-[13px] font-bold text-white">Ask AI follow-up</p>
              </div>
              <Link
                href={`/ai-search?q=${encodeURIComponent(`Tell me more about: ${art.headline}`)}`}
                className="flex w-full items-center justify-between rounded-xl border border-white/[0.08] bg-white/[0.03] px-4 py-3 text-[13px] text-slate-500 hover:border-violet-500/30 hover:bg-white/[0.05] transition"
              >
                <span>e.g., How will this impact {sectors[0] ? (typeof sectors[0] === "string" ? sectors[0] : sectors[0].name) : "the market"}?</span>
                <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-violet-600">
                  <Zap className="h-3.5 w-3.5 text-white" />
                </div>
              </Link>
              {suggestedQuestions.length > 0 && (
                <>
                  <p className="mt-3 text-[10px] font-semibold uppercase tracking-wider text-slate-600">Suggested questions</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {suggestedQuestions.map((q, i) => (
                      <Link key={i} href={`/ai-search?q=${encodeURIComponent(q)}`}
                        className="rounded-full border border-white/[0.08] bg-white/[0.03] px-3 py-1.5 text-[11px] text-slate-400 hover:border-violet-500/30 hover:text-violet-300 transition">
                        {q}
                      </Link>
                    ))}
                  </div>
                </>
              )}
            </section>

          </div>

          {/* ══ RIGHT SIDEBAR ════════════════════════════════════════════════════ */}
          <aside className="space-y-5">

            {/* Share + Bookmark */}
            <div className="flex items-center gap-2">
              <button className="flex flex-1 items-center justify-center gap-2 rounded-xl border border-white/[0.1] bg-white/[0.04] py-2.5 text-[12px] font-semibold text-slate-300 hover:bg-white/[0.07] transition">
                <Share2 className="h-3.5 w-3.5" /> Share
              </button>
              <button className="flex flex-1 items-center justify-center gap-2 rounded-xl border border-white/[0.1] bg-white/[0.04] py-2.5 text-[12px] font-semibold text-slate-300 hover:bg-white/[0.07] transition">
                <Bookmark className="h-3.5 w-3.5" /> Bookmark
              </button>
            </div>

            {/* ── Intelligence Summary ──────────────────────────────────────── */}
            <div className="rounded-2xl border border-white/[0.08] bg-[#060e1e] p-5">
              <p className="mb-4 text-[11px] font-black uppercase tracking-wider text-white">Intelligence Summary</p>
              <div className="space-y-3">
                {[
                  {
                    icon: <BookOpen className="h-3.5 w-3.5 text-slate-500" />,
                    label: "Event Type",
                    value: articleTypeLabel(art.article_type),
                    cls: "text-white font-semibold",
                  },
                  {
                    icon: <TrendingUp className="h-3.5 w-3.5 text-slate-500" />,
                    label: "Impact",
                    value: impactStr,
                    cls: `font-semibold ${impactColor(impactStr)}`,
                  },
                  {
                    icon: <Clock className="h-3.5 w-3.5 text-slate-500" />,
                    label: "Time Horizon",
                    value: horizon,
                    cls: "text-white font-semibold",
                  },
                  {
                    icon: <Zap className="h-3.5 w-3.5 text-slate-500" />,
                    label: "Confidence",
                    value: confPct > 0 ? `${confLabel(art.confidence_score)} (${confPct}%)` : "—",
                    cls: `font-semibold ${confColor(art.confidence_score)}`,
                  },
                  {
                    icon: <CheckCircle2 className="h-3.5 w-3.5 text-slate-500" />,
                    label: "Sources",
                    value: sources.length ? `${sources.length} Verified` : "AI Generated",
                    cls: "text-white font-semibold",
                  },
                ].map((row, i) => (
                  <div key={i} className="flex items-start gap-3">
                    <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border border-white/[0.06] bg-white/[0.03]">
                      {row.icon}
                    </div>
                    <div className="min-w-0">
                      <p className="text-[10px] text-slate-600">{row.label}</p>
                      <p className={`text-[12px] ${row.cls}`}>{row.value}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* ── Similar Historical Events ─────────────────────────────────── */}
            {historical.length > 0 && (
              <div className="rounded-2xl border border-white/[0.08] bg-[#060e1e] p-5">
                <div className="mb-4 flex items-center justify-between">
                  <p className="text-[11px] font-black uppercase tracking-wider text-white">Similar Historical Events</p>
                  <button className="text-[10px] font-semibold text-violet-400 hover:text-violet-300 transition flex items-center gap-0.5">
                    See all <ChevronRight className="h-3 w-3" />
                  </button>
                </div>
                <div className="space-y-4">
                  {historical.slice(0, 3).map((h: any, i: number) => {
                    const outcome = parseFloat(String(h.outcome ?? h.nifty_change ?? 0));
                    const pos = outcome >= 0;
                    const similarity = h.similarity ?? (90 - i * 12);
                    const sparkVals = h.sparkline ?? [outcome * 0.3, outcome * 0.6, outcome * 0.8, outcome * 0.5, outcome];
                    return (
                      <div key={i} className="border-b border-white/[0.05] pb-4 last:border-0 last:pb-0">
                        <p className="mb-0.5 text-[12px] font-bold text-white leading-snug">{h.event ?? h.title ?? "Market Event"}</p>
                        <p className="mb-2 text-[10px] text-slate-600">{h.date ? fmtDate(h.date) : "—"}</p>
                        <div className="flex items-center justify-between">
                          <div>
                            <p className="text-[10px] text-slate-600">Similarity</p>
                            <p className="text-[12px] font-bold text-violet-400">{similarity}%</p>
                            {h.banknifty_change != null && (
                              <p className={`text-[10px] font-semibold ${pos ? "text-emerald-400" : "text-rose-400"}`}>
                                Bank Nifty: {pos ? "+" : ""}{parseFloat(String(h.banknifty_change)).toFixed(2)}%
                              </p>
                            )}
                          </div>
                          <Sparkline values={sparkVals} />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* ── Top Impacted Sectors ──────────────────────────────────────── */}
            {sectors.length > 0 && (
              <div className="rounded-2xl border border-white/[0.08] bg-[#060e1e] p-5">
                <div className="mb-4 flex items-center justify-between">
                  <p className="text-[11px] font-black uppercase tracking-wider text-white">Top Impacted Sectors</p>
                  <Link href="/market-intelligence" className="text-[10px] font-semibold text-violet-400 hover:text-violet-300 transition flex items-center gap-0.5">
                    View all <ChevronRight className="h-3 w-3" />
                  </Link>
                </div>
                <div className="space-y-3">
                  {sectors.slice(0, 5).map((s: any, i: number) => {
                    const name   = typeof s === "string" ? s : (s.name ?? s.sector ?? s);
                    const impact = typeof s === "object" ? (s.impact ?? s.sentiment ?? "Neutral") : "Neutral";
                    return (
                      <div key={i}>
                        <div className="mb-1 flex items-center justify-between">
                          <span className="text-[12px] font-medium text-white">{name}</span>
                        </div>
                        <SectorBar impact={impact} />
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* ── Top Impacted Companies ────────────────────────────────────── */}
            {(relCompanies.length > 0 || companies.length > 0) && (
              <div className="rounded-2xl border border-white/[0.08] bg-[#060e1e] p-5">
                <div className="mb-4 flex items-center justify-between">
                  <p className="text-[11px] font-black uppercase tracking-wider text-white">Top Impacted Companies</p>
                  <Link href="/companies" className="text-[10px] font-semibold text-violet-400 hover:text-violet-300 transition flex items-center gap-0.5">
                    View all <ChevronRight className="h-3 w-3" />
                  </Link>
                </div>
                <div className="space-y-2">
                  {(relCompanies.length ? relCompanies : companies).slice(0, 5).map((c: any, i: number) => {
                    const name   = typeof c === "string" ? c : (c.name ?? c.company ?? c.symbol ?? c);
                    const symbol = typeof c === "object" ? (c.symbol ?? c.ticker ?? "") : "";
                    const change = typeof c === "object" ? (c.change_pct ?? c.change ?? c.nifty_change ?? null) : null;
                    const pos    = change == null ? true : parseFloat(String(change)) >= 0;
                    return (
                      <Link key={i} href={symbol ? `/companies/${symbol}` as any : "/companies"}
                        className="flex items-center justify-between rounded-xl px-3 py-2.5 transition hover:bg-white/[0.03]">
                        <div className="flex items-center gap-2.5">
                          <div className="flex h-7 w-7 items-center justify-center rounded-lg border border-white/[0.08] bg-white/[0.04] text-[9px] font-black text-slate-400">
                            {(symbol || name || "?").slice(0, 2).toUpperCase()}
                          </div>
                          <span className="text-[12px] font-medium text-white">{name}</span>
                        </div>
                        {change != null && (
                          <span className={`text-[12px] font-bold tabular-nums ${pos ? "text-emerald-400" : "text-rose-400"}`}>
                            {pos ? "+" : ""}{parseFloat(String(change)).toFixed(2)}%
                          </span>
                        )}
                      </Link>
                    );
                  })}
                </div>
              </div>
            )}

            {/* ── AI Intelligence Path ──────────────────────────────────────── */}
            {relThemes.length > 0 && (
              <div className="rounded-2xl border border-white/[0.08] bg-[#060e1e] p-5">
                <p className="mb-4 text-[11px] font-black uppercase tracking-wider text-white">AI Intelligence Path</p>
                <div className="relative space-y-0">
                  {relThemes.slice(0, 5).map((t: any, i: number) => {
                    const name = typeof t === "string" ? t : (t.theme ?? t.name ?? t);
                    const href = typeof t === "object" ? (t.link ?? t.href ?? "/market-intelligence") : "/market-intelligence";
                    const isLast = i === Math.min(relThemes.length, 5) - 1;
                    return (
                      <div key={i} className="relative flex items-start gap-3 pb-3">
                        {!isLast && (
                          <div className="absolute left-[11px] top-5 h-full w-px bg-white/[0.05]" />
                        )}
                        <div className={`relative z-10 flex h-5.5 w-5.5 shrink-0 items-center justify-center rounded-full border ${i === 0 ? "border-violet-500/60 bg-violet-500/20" : "border-white/[0.1] bg-white/[0.04]"}`}
                          style={{ width: 22, height: 22 }}>
                          <span className="h-1.5 w-1.5 rounded-full bg-current"
                            style={{ color: i === 0 ? "#a78bfa" : "#475569" }} />
                        </div>
                        <Link href={href as any} className="pt-0.5 text-[12px] font-medium text-slate-400 hover:text-white transition">
                          {name}
                        </Link>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* ── Mini Intelligence Graph ──────────────────────────────────── */}
            {(() => {
              const firstCo = companies[0] ?? relCompanies[0];
              const sym = firstCo ? (typeof firstCo === "string" ? firstCo : (firstCo.symbol ?? firstCo.ticker ?? "")) : "";
              const firstSec = sectors[0];
              const secName = firstSec ? (typeof firstSec === "string" ? firstSec : (firstSec.name ?? "")) : "";
              const graphNodeId = sym
                ? makeNodeId("company", sym)
                : secName
                ? makeNodeId("sector", secName)
                : "";
              if (!graphNodeId) return null;
              return (
                <MiniIntelligenceGraph
                  nodeId={graphNodeId}
                  title="Intelligence Graph"
                  className="border-white/[0.08] bg-[#060e1e]"
                />
              );
            })()}

            {/* ── Sources (if available) ────────────────────────────────────── */}
            {sources.length > 0 && (
              <div className="rounded-2xl border border-white/[0.08] bg-[#060e1e] p-5">
                <p className="mb-3 text-[11px] font-black uppercase tracking-wider text-white">Sources</p>
                <div className="space-y-2">
                  {sources.slice(0, 4).map((s: any, i: number) => {
                    const name = typeof s === "string" ? s : (s.name ?? s.title ?? s.source ?? s.url ?? "Source");
                    const url  = typeof s === "object" ? s.url : null;
                    return url ? (
                      <a key={i} href={url} target="_blank" rel="noopener noreferrer"
                        className="flex items-center gap-2 text-[11px] text-slate-500 hover:text-slate-300 transition">
                        <ExternalLink className="h-3 w-3 shrink-0 text-slate-700" /> {name}
                      </a>
                    ) : (
                      <p key={i} className="flex items-center gap-2 text-[11px] text-slate-600">
                        <span className="h-1 w-1 rounded-full bg-slate-700" /> {name}
                      </p>
                    );
                  })}
                </div>
              </div>
            )}

          </aside>
        </div>
      </div>
    </div>
  );
}
