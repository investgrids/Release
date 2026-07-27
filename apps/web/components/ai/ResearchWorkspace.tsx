"use client";

import { useState } from "react";
import { Check, Trash2, FileText, ChevronRight, Loader2, Download } from "lucide-react";
import { API_BASE_URL as API } from "@/lib/api";
import type { ResearchSessionState } from "@/lib/hooks/useResearchSession";

interface SummaryResult {
  companies_researched: string[];
  key_conclusions: string[];
  risks_identified: string[];
  open_questions: string[];
  suggested_next_research: string[];
  degraded: boolean;
}

/**
 * "Current Research" sidebar card — the session's own accumulated state,
 * nothing invented. Renders nothing until at least one real search has
 * happened this session. Queries double as the "Research Timeline" the
 * spec asks for — a separate timeline visualization would just be the
 * same list twice; this renders it once, connected, clickable.
 */
export function ResearchWorkspace({
  session,
  onReopenQuery,
  onExploreCompany,
  onExploreSector,
  onClear,
}: {
  session: ResearchSessionState;
  onReopenQuery: (text: string) => void;
  onExploreCompany: (symbol: string) => void;
  onExploreSector: (sector: string) => void;
  onClear: () => void;
}) {
  const [summary, setSummary] = useState<SummaryResult | null>(null);
  const [status, setStatus] = useState<"idle" | "loading" | "error">("idle");

  const hasAny = session.companies.length > 0 || session.sectors.length > 0 || session.queries.length > 0;
  if (!hasAny) return null;

  function downloadSummaryMarkdown() {
    if (!summary) return;
    const today = new Date().toLocaleDateString("en-IN", { year: "numeric", month: "long", day: "numeric" });
    const lines: string[] = [
      "# Research Session Summary", "",
      `**Generated:** ${today} · MarketRipple AI Search`, "",
    ];
    if (summary.companies_researched.length) lines.push("## Companies Researched", "", ...summary.companies_researched.map(c => `- ${c}`), "");
    if (summary.key_conclusions.length) lines.push("## Key Conclusions", "", ...summary.key_conclusions.map(c => `- ${c}`), "");
    if (summary.risks_identified.length) lines.push("## Risks Identified", "", ...summary.risks_identified.map(c => `- ${c}`), "");
    if (summary.open_questions.length) lines.push("## Open Questions", "", ...summary.open_questions.map(c => `- ${c}`), "");
    if (summary.suggested_next_research.length) lines.push("## Suggested Next Research", "", ...summary.suggested_next_research.map(c => `- ${c}`), "");
    lines.push("---", "*AI-generated research, not investment advice. Verify independently before making decisions.*");

    const blob = new Blob([lines.join("\n")], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `marketripple-session-summary-${Date.now().toString().slice(-8)}.md`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  async function generateSummary() {
    setStatus("loading");
    try {
      const res = await fetch(`${API}/api/ai/search/session-summary`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          companies: session.companies.map(c => c.symbol),
          sectors: session.sectors,
          queries: session.queries.map(q => q.text),
          current_verdict: session.currentVerdict,
        }),
      });
      if (!res.ok) throw new Error();
      const data: SummaryResult = await res.json();
      if (data.degraded) throw new Error();
      setSummary(data);
      setStatus("idle");
    } catch {
      setStatus("error");
    }
  }

  return (
    <div className="rounded-[20px] border border-white/[0.07] bg-white/[0.03] p-4">
      <div className="mb-3 flex items-center justify-between">
        <p className="text-[12px] font-semibold text-slate-200">Current Research</p>
        <button onClick={onClear} title="Clear session" className="text-slate-600 hover:text-rose-400 transition">
          <Trash2 size={12} strokeWidth={1.8} />
        </button>
      </div>

      <div className="space-y-3">
        {session.companies.length > 0 && (
          <div>
            <p className="mb-1.5 text-[9px] uppercase tracking-wider text-slate-500">Companies</p>
            <div className="space-y-1">
              {session.companies.map(c => (
                <button key={c.symbol} onClick={() => onExploreCompany(c.symbol)}
                  className="flex w-full items-center gap-1.5 rounded-[8px] px-1.5 py-1 text-left transition hover:bg-white/[0.05]">
                  <Check className="h-3 w-3 shrink-0 text-emerald-400" />
                  <span className="truncate text-[11px] text-slate-300">{c.symbol}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {session.sectors.length > 0 && (
          <div>
            <p className="mb-1.5 text-[9px] uppercase tracking-wider text-slate-500">Sectors</p>
            <div className="space-y-1">
              {session.sectors.map(s => (
                <button key={s} onClick={() => onExploreSector(s)}
                  className="flex w-full items-center gap-1.5 rounded-[8px] px-1.5 py-1 text-left transition hover:bg-white/[0.05]">
                  <Check className="h-3 w-3 shrink-0 text-sky-400" />
                  <span className="truncate text-[11px] text-slate-300">{s}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {session.events.length > 0 && (
          <div>
            <p className="mb-1.5 text-[9px] uppercase tracking-wider text-slate-500">Events</p>
            <div className="space-y-1">
              {session.events.slice(0, 4).map(e => (
                <div key={e} className="flex items-center gap-1.5 px-1.5 py-0.5">
                  <Check className="h-3 w-3 shrink-0 text-amber-400" />
                  <span className="truncate text-[11px] text-slate-400">{e}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {session.policies.length > 0 && (
          <div>
            <p className="mb-1.5 text-[9px] uppercase tracking-wider text-slate-500">Policies</p>
            <div className="space-y-1">
              {session.policies.slice(0, 4).map(p => (
                <div key={p} className="flex items-center gap-1.5 px-1.5 py-0.5">
                  <Check className="h-3 w-3 shrink-0 text-violet-400" />
                  <span className="truncate text-[11px] text-slate-400">{p}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {session.queries.length > 0 && (
          <div>
            <p className="mb-1.5 text-[9px] uppercase tracking-wider text-slate-500">Queries</p>
            <div className="relative space-y-0.5 pl-3">
              <div className="absolute left-[3px] top-1 bottom-1 w-px bg-white/[0.08]" />
              {session.queries.slice(-6).map(q => (
                <button key={q.id} onClick={() => onReopenQuery(q.text)}
                  className="group relative flex w-full items-start gap-2 rounded-[8px] py-1 pl-2 text-left transition hover:bg-white/[0.05]">
                  <span className="absolute -left-3 top-[7px] h-1.5 w-1.5 rounded-full bg-violet-400" />
                  <span className="truncate text-[11px] text-slate-400 group-hover:text-violet-300 transition">{q.text}</span>
                  <ChevronRight className="ml-auto h-3 w-3 shrink-0 text-slate-600 opacity-0 group-hover:opacity-100 transition" />
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      <div className="mt-3 border-t border-white/[0.06] pt-3">
        {!summary ? (
          <button onClick={generateSummary} disabled={status === "loading"}
            className="flex w-full items-center justify-center gap-1.5 rounded-[10px] border border-white/10 bg-white/[0.03] px-3 py-1.5 text-[11px] font-medium text-slate-300 transition hover:bg-white/[0.06] disabled:opacity-50">
            {status === "loading" ? <Loader2 className="h-3 w-3 animate-spin" /> : <FileText className="h-3 w-3" />}
            {status === "loading" ? "Generating…" : "Generate Research Summary"}
          </button>
        ) : (
          <div className="space-y-2.5 text-[11px]">
            {summary.key_conclusions.length > 0 && (
              <div>
                <p className="mb-1 font-semibold text-slate-300">Key Conclusions</p>
                <ul className="space-y-0.5 text-slate-400">
                  {summary.key_conclusions.map((c, i) => <li key={i}>• {c}</li>)}
                </ul>
              </div>
            )}
            {summary.risks_identified.length > 0 && (
              <div>
                <p className="mb-1 font-semibold text-slate-300">Risks Identified</p>
                <ul className="space-y-0.5 text-slate-400">
                  {summary.risks_identified.map((c, i) => <li key={i}>• {c}</li>)}
                </ul>
              </div>
            )}
            {summary.open_questions.length > 0 && (
              <div>
                <p className="mb-1 font-semibold text-slate-300">Open Questions</p>
                <ul className="space-y-0.5 text-slate-400">
                  {summary.open_questions.map((c, i) => <li key={i}>• {c}</li>)}
                </ul>
              </div>
            )}
            {summary.suggested_next_research.length > 0 && (
              <div>
                <p className="mb-1 font-semibold text-slate-300">Suggested Next Research</p>
                <div className="flex flex-col gap-1">
                  {summary.suggested_next_research.map((q, i) => (
                    <button key={i} onClick={() => onReopenQuery(q)}
                      className="rounded-[8px] border border-violet-500/20 bg-violet-500/[0.06] px-2 py-1 text-left text-violet-300 transition hover:bg-violet-500/10">
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            )}
            <button onClick={downloadSummaryMarkdown}
              className="flex w-full items-center justify-center gap-1.5 rounded-[10px] border border-white/10 bg-white/[0.03] px-3 py-1.5 text-[11px] font-medium text-slate-300 transition hover:bg-white/[0.06]">
              <Download className="h-3 w-3" /> Export as Markdown
            </button>
          </div>
        )}
        {status === "error" && <p className="mt-1.5 text-[10px] text-rose-400">Couldn&apos;t generate a summary right now.</p>}
      </div>
    </div>
  );
}
