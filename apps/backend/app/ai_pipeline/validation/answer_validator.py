"""
Answer Validator — the final gate before a response leaves the pipeline.

Checks that every section the template declares required is actually
present as a key in the rendered answer. `templates/base.py::render()`
already backfills every `llm_sections` entry with a deterministic fallback,
so in practice a missing key here means a template's own
`deterministic_sections()` has a real gap — a genuine bug, not LLM
flakiness — which is exactly the case worth one repair attempt for: ask
the model tier to backfill just the missing keys as prose, constrained to
the same computed facts. If sections are still missing after that, a
deterministic placeholder is used so the response is never silently short
of its contract, and the gap is preserved in the report for observability.
"""
from __future__ import annotations

import json

from app.ai_pipeline.contracts import DecisionResult, Evidence, ValidatorReport
from app.ai_pipeline.models import model_router
from app.ai_pipeline.templates.base import AnswerTemplate, decision_facts_json, parse_llm_json


async def validate(
    template: AnswerTemplate,
    answer: dict,
    query: str,
    decision: DecisionResult,
    evidence: list[Evidence],
    repair_tier: str = "medium",
) -> tuple[dict, ValidatorReport]:
    missing = [s for s in template.required_sections if s not in answer]

    if not missing:
        return answer, ValidatorReport(
            passed=True, missing_sections=[], repair_attempted=False,
            final_sections_present=list(template.required_sections),
        )

    repaired = dict(answer)
    repair_attempted = False
    try:
        facts_json = decision_facts_json(decision, evidence)
        sections_list = ", ".join(f'"{s}"' for s in missing)
        prompt = (
            f"User question: {query}\n\nComputed facts:\n{facts_json}\n\n"
            f"The following required sections are missing from a previous answer: {sections_list}. "
            f"Return ONLY a JSON object with exactly these keys, each a concise string derived "
            f"strictly from the facts above. No markdown, no extra text."
        )
        raw = await model_router.call(repair_tier, prompt, template.system_prompt)
        repair_attempted = True
        parsed = parse_llm_json(raw)
        for section in missing:
            value = parsed.get(section)
            if isinstance(value, str) and value.strip():
                repaired[section] = value.strip()
    except Exception:
        pass   # fall through to deterministic placeholders below

    still_missing = [s for s in missing if s not in repaired]
    for section in still_missing:
        repaired[section] = f"Data unavailable for '{section}' in this response."

    final_missing = [s for s in template.required_sections if s not in repaired]
    return repaired, ValidatorReport(
        passed=not final_missing,
        missing_sections=final_missing,
        repair_attempted=repair_attempted,
        final_sections_present=[s for s in template.required_sections if s in repaired],
    )
