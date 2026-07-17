"""
Answer Template base — the mechanism that keeps the LLM constrained to
"elaborate, don't invent."

Every template splits its `required_sections` into two groups:
  - deterministic sections: populated directly from `DecisionResult` /
    evidence, computed by the template's own `deterministic_sections()`
    function — no LLM involved, so verdict/drivers/opportunities/risks/
    ripple/historical numbers can never be hallucinated.
  - `llm_sections`: prose the LLM is asked to write (e.g. "executive
    summary", "why this conclusion"), constrained by a JSON block of the
    same computed facts injected into the prompt, with an explicit
    instruction not to introduce new numeric claims.

`build_prompt`/`render` are shared free functions (not per-template
methods) so every template gets identical prompt discipline and JSON
parsing/fallback behavior — a template module only supplies data, not
control flow.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Callable

from app.ai_pipeline.contracts import DecisionResult, Evidence

DeterministicSectionsFn = Callable[[DecisionResult, list[Evidence]], dict]


@dataclass(frozen=True)
class AnswerTemplate:
    key: str
    label: str
    required_sections: tuple[str, ...]
    llm_sections: tuple[str, ...]        # must be a subset of required_sections
    system_prompt: str
    deterministic_sections: DeterministicSectionsFn


def decision_facts_json(decision: DecisionResult, evidence: list[Evidence]) -> str:
    """The ONLY facts the LLM is allowed to build prose from."""
    top_evidence = sorted(evidence, key=lambda e: e.magnitude * e.confidence, reverse=True)[:10]
    facts = {
        "verdict": decision.verdict,
        "mood": decision.mood,
        "risk_level": decision.risk_level,
        "horizon": decision.horizon,
        "confidence_score": decision.confidence.total_score,
        "confidence_level": decision.confidence.level,
        "confidence_reasons": decision.confidence.reasons,
        "top_drivers": [
            {"label": d.label, "score": d.score, "direction": d.direction}
            for d in decision.drivers[:6]
        ],
        "opportunities": decision.opportunities,
        "risks": decision.risks,
        "beneficiaries": decision.beneficiaries,
        "losers": decision.losers,
        "missing_data": decision.missing_data,
        "supporting_evidence": [
            {"source": e.source, "entity": e.entity, "claim": e.claim, "polarity": e.polarity}
            for e in top_evidence
        ],
    }
    return json.dumps(facts, indent=2)


def build_prompt(template: AnswerTemplate, query: str, decision: DecisionResult, evidence: list[Evidence]) -> str:
    facts_json = decision_facts_json(decision, evidence)
    sections_list = ", ".join(f'"{s}"' for s in template.llm_sections)
    return (
        f"User question: {query}\n\n"
        f"Computed facts (do not contradict or invent numbers beyond these):\n{facts_json}\n\n"
        f"Return ONLY a JSON object with exactly these keys: {sections_list}. "
        f"Each value is a concise, well-written string (2-4 sentences) that explains and "
        f"elaborates on the computed facts above in plain English for an investor. "
        f"Do not introduce new statistics, percentages, or company names not already present "
        f"in the facts. If missing_data is non-empty, acknowledge the gap honestly rather than "
        f"filling it in. Return only the JSON object, no markdown fences, no extra text."
    )


def parse_llm_json(raw: str) -> dict:
    text = raw.strip()
    if "```" in text:
        parts = text.split("```")
        text = parts[1] if len(parts) > 1 else text
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


def render(
    template: AnswerTemplate,
    raw_llm_text: str,
    query: str,
    decision: DecisionResult,
    evidence: list[Evidence],
) -> dict:
    answer = dict(template.deterministic_sections(decision, evidence))

    llm_parsed: dict = {}
    if raw_llm_text:
        try:
            llm_parsed = parse_llm_json(raw_llm_text)
        except Exception:
            llm_parsed = {}

    for section in template.llm_sections:
        value = llm_parsed.get(section)
        if isinstance(value, str) and value.strip():
            answer[section] = value.strip()
        else:
            # Deterministic fallback so the section is never silently absent —
            # the answer validator checks presence, and this keeps the
            # contract honest even when the LLM call fails or is malformed.
            answer[section] = _fallback_prose(section, decision)

    answer["template"] = template.key
    return answer


def _fallback_prose(section: str, decision: DecisionResult) -> str:
    if decision.missing_data:
        gap_note = f" Note: {decision.missing_data[0]}."
    else:
        gap_note = ""
    return (
        f"Based on {decision.confidence.level.lower()} confidence evidence "
        f"({decision.confidence.total_score:.0f}/100), the {decision.mood.lower()} market context "
        f"points to a {decision.risk_level.lower()}-risk, {decision.horizon.lower()} outlook.{gap_note}"
    )
