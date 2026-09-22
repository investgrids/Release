"use client";

// First intent layout built against the exhaustive registry (2026-09-21
// AI Answer UI work, build order item 1 — chosen first for being the
// most deterministic and easiest to validate). A factual lookup has no
// meaningful confidence score, Ripple position, risks, or methodology to
// show, so this layout turns those sections off rather than rendering
// them empty (see AIAnswerShell's showConfidence/showRelatedLinks docs).
import { AIAnswerShell } from "../AIAnswerShell";
import type { FactualLookupAnswer } from "../answerTypes";

export function FactualLookupLayout({
  answer, onNewSearch, onRefine,
}: {
  answer: FactualLookupAnswer;
  onNewSearch: () => void;
  onRefine?: () => void;
}) {
  const { raw } = answer;
  const directAnswer = raw.answer?.bottom_line || raw.answer?.summary || "";
  const elaboration = raw.answer?.summary && raw.answer.summary !== directAnswer ? raw.answer.summary : null;

  return (
    <AIAnswerShell
      query={answer.query}
      uiMode="factual_lookup"
      sourceCount={answer.sourceCount}
      evidenceRows={answer.evidenceRows}
      confidence={answer.confidence}
      evidenceCoverage={answer.evidenceCoverage}
      showConfidence={false}
      showRelatedLinks={false}
      onNewSearch={onNewSearch}
      onRefine={onRefine}
    >
      {directAnswer ? (
        <>
          <p className="text-[15px] leading-7 font-semibold text-text-primary">{directAnswer}</p>
          {elaboration && <p className="mt-3 text-[13px] leading-6 text-text-secondary">{elaboration}</p>}
        </>
      ) : (
        <p className="text-[13px] text-text-muted">
          No direct answer was generated for this question. The evidence found is shown below.
        </p>
      )}
    </AIAnswerShell>
  );
}
