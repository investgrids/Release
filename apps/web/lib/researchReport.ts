/**
 * AI Research Report (Phase 2D) — turns a single already-fetched SearchResult
 * into a shareable document. Deliberately does no new fetching or LLM calls:
 * everything here is already in memory by the time a user clicks export,
 * same "never re-derive what you already have" principle as the rest of
 * this session's features. Two outputs share one field-extraction pass:
 *   - Markdown, for the "Download as Markdown" action (Blob download).
 *   - The DOM ResearchReportView renders (for "Download as PDF", via the
 *     browser's native print-to-PDF — see that component's docstring for
 *     why this session didn't add a PDF-rendering dependency for it).
 */

// Minimal structural type — only the fields the report actually reads,
// so this file doesn't need to import page.tsx's full SearchResult shape.
export interface ReportableResult {
  query: string;
  answer?: { bottom_line?: string; summary?: string; risks?: string[]; opportunities?: string[] };
  investment_verdict?: { rating?: string; horizon?: string; confidence?: number | null };
  decision_engine_v2?: { verdict_scale?: string; why?: string };
  ai_conclusion?: { current_view?: string; reason?: string; biggest_opportunity?: string; biggest_risk?: string; investor_action_note?: string };
  timeline_intelligence?: { immediate?: string; one_week?: string; one_to_three_months?: string; six_to_twelve_months?: string; one_to_three_years?: string };
  confidence_breakdown?: { final_confidence?: number; level?: string; reasons?: string[] };
  companies?: { symbol: string; name: string; reason?: string; why_it_matters?: string }[];
  historical_comparison?: { event_title: string; event_date: string; key_lesson?: string }[];
  citations?: string[];
  response_id?: string;
}

const TIMELINE_LABELS: Record<string, string> = {
  immediate: "Immediate", one_week: "1 Week", one_to_three_months: "1–3 Months",
  six_to_twelve_months: "6–12 Months", one_to_three_years: "1–3 Years",
};

export function buildReportMarkdown(r: ReportableResult): string {
  const lines: string[] = [];
  const today = new Date().toLocaleDateString("en-IN", { year: "numeric", month: "long", day: "numeric" });

  lines.push(`# AI Research Report`);
  lines.push(``);
  lines.push(`**Query:** ${r.query}`);
  lines.push(`**Generated:** ${today} · MarketRipple AI Search`);
  lines.push(``);

  if (r.decision_engine_v2?.verdict_scale || r.investment_verdict?.rating) {
    lines.push(`## Verdict`);
    lines.push(``);
    lines.push(`**${r.decision_engine_v2?.verdict_scale || r.investment_verdict?.rating}**` +
      (r.investment_verdict?.confidence != null ? ` · ${Math.round(r.investment_verdict.confidence)}% confidence` : "") +
      (r.investment_verdict?.horizon ? ` · ${r.investment_verdict.horizon}` : ""));
    if (r.decision_engine_v2?.why) lines.push(`\n${r.decision_engine_v2.why}`);
    lines.push(``);
  }

  if (r.answer?.bottom_line || r.answer?.summary) {
    lines.push(`## Summary`);
    lines.push(``);
    lines.push(r.answer.bottom_line || r.answer.summary || "");
    lines.push(``);
  }

  if (r.ai_conclusion?.biggest_opportunity || r.ai_conclusion?.biggest_risk) {
    lines.push(`## AI Conclusion`);
    lines.push(``);
    if (r.ai_conclusion.current_view) lines.push(`- **Current View:** ${r.ai_conclusion.current_view}`);
    if (r.ai_conclusion.biggest_opportunity) lines.push(`- **Biggest Opportunity:** ${r.ai_conclusion.biggest_opportunity}`);
    if (r.ai_conclusion.biggest_risk) lines.push(`- **Biggest Risk:** ${r.ai_conclusion.biggest_risk}`);
    if (r.ai_conclusion.investor_action_note) lines.push(`- **What To Watch:** ${r.ai_conclusion.investor_action_note}`);
    lines.push(``);
  }

  const tl = r.timeline_intelligence as Record<string, string | undefined> | undefined;
  if (tl && Object.values(tl).some(Boolean)) {
    lines.push(`## Decision Timeline`);
    lines.push(``);
    for (const key of Object.keys(TIMELINE_LABELS)) {
      if (tl[key]) lines.push(`- **${TIMELINE_LABELS[key]}:** ${tl[key]}`);
    }
    lines.push(``);
  }

  if (r.companies && r.companies.length > 0) {
    lines.push(`## Companies`);
    lines.push(``);
    for (const c of r.companies) {
      lines.push(`- **${c.symbol}** (${c.name}) — ${c.why_it_matters || c.reason || ""}`);
    }
    lines.push(``);
  }

  if (r.answer?.risks?.length || r.answer?.opportunities?.length) {
    lines.push(`## Risks & Opportunities`);
    lines.push(``);
    for (const risk of r.answer?.risks || []) lines.push(`- ⚠️ ${risk}`);
    for (const opp of r.answer?.opportunities || []) lines.push(`- ✅ ${opp}`);
    lines.push(``);
  }

  if (r.historical_comparison && r.historical_comparison.length > 0) {
    lines.push(`## Historical Precedents`);
    lines.push(``);
    for (const h of r.historical_comparison) {
      lines.push(`- **${h.event_title}** (${h.event_date})${h.key_lesson ? ` — ${h.key_lesson}` : ""}`);
    }
    lines.push(``);
  }

  if (r.confidence_breakdown?.final_confidence != null) {
    lines.push(`## Confidence`);
    lines.push(``);
    lines.push(`${Math.round(r.confidence_breakdown.final_confidence)}% (${r.confidence_breakdown.level})`);
    for (const reason of r.confidence_breakdown.reasons || []) lines.push(`- ${reason}`);
    lines.push(``);
  }

  if (r.citations && r.citations.length > 0) {
    lines.push(`## Sources`);
    lines.push(``);
    for (const c of r.citations) lines.push(`- ${c}`);
    lines.push(``);
  }

  lines.push(`---`);
  lines.push(`*AI-generated research, not investment advice. Verify independently before making decisions.*`);

  return lines.join("\n");
}

function esc(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

/**
 * PDF export path: no PDF-rendering dependency was added for this (jsPDF/
 * puppeteer etc. — disproportionate for a report this session's other
 * phases keep deliberately lightweight). Instead this opens a standalone,
 * print-styled HTML document in a new tab and calls the browser's own
 * print dialog — "Save as PDF" there produces a real PDF file with zero
 * new dependencies. Built as a full HTML string (not a React portal) so it
 * never has to fight the main app's dark-theme CSS for print output.
 */
export function openResearchReport(r: ReportableResult) {
  const today = new Date().toLocaleDateString("en-IN", { year: "numeric", month: "long", day: "numeric" });
  const verdict = r.decision_engine_v2?.verdict_scale || r.investment_verdict?.rating || "";
  const tl = r.timeline_intelligence as Record<string, string | undefined> | undefined;

  const section = (title: string, body: string) => body ? `<section><h2>${esc(title)}</h2>${body}</section>` : "";
  const list = (items: string[]) => `<ul>${items.map(i => `<li>${esc(i)}</li>`).join("")}</ul>`;

  const html = `<!doctype html><html><head><meta charset="utf-8"><title>MarketRipple Research — ${esc(r.query)}</title>
<style>
  body { font-family: Georgia, 'Times New Roman', serif; color: #1a1a1a; max-width: 720px; margin: 40px auto; padding: 0 24px; line-height: 1.55; }
  h1 { font-size: 22px; margin-bottom: 4px; }
  h2 { font-size: 14px; text-transform: uppercase; letter-spacing: 0.06em; color: #555; border-bottom: 1px solid #ddd; padding-bottom: 4px; margin-top: 28px; }
  .meta { color: #666; font-size: 12px; margin-bottom: 20px; }
  .verdict { display: inline-block; font-size: 16px; font-weight: bold; padding: 4px 12px; border: 1px solid #999; border-radius: 6px; margin: 8px 0 16px; }
  ul { padding-left: 20px; }
  li { margin-bottom: 4px; font-size: 13px; }
  p { font-size: 13px; }
  .footer { margin-top: 36px; font-size: 11px; color: #888; border-top: 1px solid #ddd; padding-top: 10px; }
  @media print { body { margin: 0; } }
</style></head><body>
  <h1>AI Research Report</h1>
  <p class="meta">${esc(r.query)} &middot; Generated ${today} &middot; MarketRipple AI Search</p>
  ${verdict ? `<div class="verdict">${esc(verdict)}${r.investment_verdict?.confidence != null ? ` &middot; ${Math.round(r.investment_verdict.confidence)}% confidence` : ""}</div>` : ""}
  ${section("Summary", `<p>${esc(r.answer?.bottom_line || r.answer?.summary || "")}</p>`)}
  ${section("AI Conclusion", r.ai_conclusion ? list([
    r.ai_conclusion.current_view && `Current View: ${r.ai_conclusion.current_view}`,
    r.ai_conclusion.biggest_opportunity && `Biggest Opportunity: ${r.ai_conclusion.biggest_opportunity}`,
    r.ai_conclusion.biggest_risk && `Biggest Risk: ${r.ai_conclusion.biggest_risk}`,
    r.ai_conclusion.investor_action_note && `What To Watch: ${r.ai_conclusion.investor_action_note}`,
  ].filter(Boolean) as string[]) : "")}
  ${section("Decision Timeline", tl ? list(Object.keys(TIMELINE_LABELS).filter(k => tl[k]).map(k => `${TIMELINE_LABELS[k]}: ${tl[k]}`)) : "")}
  ${section("Companies", r.companies?.length ? list(r.companies.map(c => `${c.symbol} (${c.name}) — ${c.why_it_matters || c.reason || ""}`)) : "")}
  ${section("Risks & Opportunities", (r.answer?.risks?.length || r.answer?.opportunities?.length)
      ? list([...(r.answer?.risks || []).map(x => `Risk: ${x}`), ...(r.answer?.opportunities || []).map(x => `Opportunity: ${x}`)]) : "")}
  ${section("Historical Precedents", r.historical_comparison?.length
      ? list(r.historical_comparison.map(h => `${h.event_title} (${h.event_date})${h.key_lesson ? ` — ${h.key_lesson}` : ""}`)) : "")}
  ${section("Confidence", r.confidence_breakdown?.final_confidence != null
      ? `<p>${Math.round(r.confidence_breakdown.final_confidence)}% (${r.confidence_breakdown.level})</p>` + list(r.confidence_breakdown.reasons || []) : "")}
  ${section("Sources", r.citations?.length ? list(r.citations) : "")}
  <p class="footer">AI-generated research, not investment advice. Verify independently before making decisions.</p>
</body></html>`;

  const win = window.open("", "_blank");
  if (!win) return;
  win.document.open();
  win.document.write(html);
  win.document.close();
  let printed = false;
  const doPrint = () => { if (printed) return; printed = true; try { win.focus(); win.print(); } catch { /* window may already be closed */ } };
  win.onload = doPrint;
  // Some browsers fire onload before paint settles — a short fallback
  // timer covers that without relying on print-preview races.
  setTimeout(doPrint, 400);
}

export function downloadMarkdown(r: ReportableResult) {
  const md = buildReportMarkdown(r);
  const blob = new Blob([md], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `marketripple-research-${(r.response_id || Date.now()).toString().slice(0, 8)}.md`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
