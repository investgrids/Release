"""
Why It Matters — AI Article V2 Phase B, grounded reasoning layer (owner
decision, 2026-08-30). A real LLM call, constrained: the model sees only
the real evidence/financial/price/historical context already assembled
in the ArticleEvidenceBundle. It has no retrieval tool and no ability to
add facts of its own — every number its OWN generated text asserts is
independently re-extracted and checked against a real "allowed" set
built from that same bundle (numeric_validation.py), never trusted from
the model's own self-report of which facts it used.

Failure behavior (owner's explicit instruction): Why It Matters is NEVER
required for publication. If a bundle has solid evidence/financial
context but the reasoning layer fails validation after a bounded retry,
the result is simply omitted — never a weakened validator, never a
forced lower-quality version to satisfy a template. A company with no
FinancialFact rows (e.g. TCS) or only quarantined ones (e.g. YESBANK)
is not a failure either — it means the prompt legitimately has less to
reason from, not that something should be invented to fill the gap.

Relevant-facts selection here (select_relevant_financial_facts) is a
real but deliberately interim Phase B heuristic: prefer the small set of
ratio metrics a reader recognizes as health signals, and cap how many
facts ever reach the prompt regardless of how many a company has. Real
event-topic relevance matching (e.g. an NPA-related filing should
prioritize NPA facts specifically) is Phase C, not built here.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

import structlog

from app.services.ai_service import _call_with_fallback
from app.services.warehouse.article_evidence_bundle import ArticleEvidenceBundle, Claim
from app.services.warehouse.numeric_validation import (
    build_allowed_values, validate_numeric_claims, validate_period_claims,
)

log = structlog.get_logger(__name__)

_MAX_ATTEMPTS = 2
_MAX_FACTS_IN_PROMPT = 6
_HEADLINE_RATIO_METRICS = ("gross_npa_pct", "net_npa_pct", "cet1_ratio", "roa")

_SYSTEM_PROMPT = (
    "You write the \"Why It Matters\" section of a real financial news article. "
    "You may ONLY use the facts given to you in the user message below — you "
    "have no ability to retrieve, recall, or estimate any other information. "
    "Every number you write (percentages, rupee/dollar figures, ratios) must "
    "match, in the same or an equivalent format, a number given to you "
    "exactly — never invent, round to a suspiciously different value, or "
    "convert a number using an assumed exchange rate. You may reason about "
    "what the given facts imply (financial strength, risk, market reaction) "
    "without introducing new quantitative claims. If the facts given are too "
    "thin to say anything substantive, write a short, honest paragraph "
    "acknowledging that rather than filling the gap with a fabricated number.\n\n"
    "Respond with JSON only, no markdown fences:\n"
    '{"why_it_matters": "1-3 sentence paragraph", "claims": '
    '[{"text": "...", "type": "FACT"|"INTERPRETATION", "evidence_refs": '
    '["EVIDENCE:<id8>" or "FACT:<metric_code>", ...]}]}'
)


def select_relevant_financial_facts(financial_context, max_facts: int = _MAX_FACTS_IN_PROMPT) -> list:
    if financial_context is None or not financial_context.has_real_facts:
        return []
    facts = list(financial_context.facts)
    facts.sort(key=lambda f: (f.metric_code not in _HEADLINE_RATIO_METRICS, f.metric_code))
    return facts[:max_facts]


def _format_fact_value(f) -> str:
    if f.unit == "pct":
        return f"{f.value * 100:.2f}%"
    if f.unit == "inr":
        return f"₹{f.value / 1e7:,.0f} crore"
    return str(f.value)


def _build_prompt(bundle: ArticleEvidenceBundle, selected_facts: list, retry_errors: list[dict] | None) -> str:
    lines = [f"Company: {bundle.company_name} ({bundle.symbol})"]

    if bundle.evidence:
        lines.append("\nWHAT HAPPENED (real, verified evidence):")
        for e in bundle.evidence[:3]:
            lines.append(f"  [EVIDENCE:{e.raw_evidence_id[:8]}] {e.title}")

    if bundle.price_move_pct is not None:
        lines.append(f"\nREAL PRICE MOVE TODAY: {bundle.symbol} {bundle.price_move_pct:+.2f}%  [FACT:price_move]")

    if selected_facts:
        lines.append("\nVERIFIED FINANCIAL FACTS (quality-passed, use exactly as given):")
        for f in selected_facts:
            period = f"FY{f.fiscal_year}" + (f" Q{f.fiscal_quarter}" if f.fiscal_quarter else "")
            lines.append(f"  [FACT:{f.metric_code}] {f.metric_name} = {_format_fact_value(f)} (as of {period})")

    if bundle.historical_events:
        lines.append("\nRELATED HISTORICAL CONTEXT (real, verified precedent — may inform interpretation, not new numeric claims):")
        for h in bundle.historical_events[:2]:
            lines.append(f"  - {h.get('event', '')} ({h.get('date', '')})")

    lines.append("\nDo not use any number not listed above. If unsure, omit the claim rather than guess.")

    if retry_errors:
        bad = ", ".join(e["raw_text"] for e in retry_errors if e.get("raw_text"))
        lines.append(
            f"\nYour previous attempt used unsupported number(s): {bad}. "
            "Remove or correct these — use ONLY the numbers listed above."
        )

    return "\n".join(lines)


def _parse_response(raw: str) -> dict | None:
    text = raw.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", text)
        if not m:
            return None
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            return None


def _build_claims(raw_claims: list, bundle: ArticleEvidenceBundle, selected_facts: list) -> list[Claim]:
    fact_codes = {f.metric_code for f in selected_facts}
    evidence_by_short_id = {e.raw_evidence_id[:8]: e.raw_evidence_id for e in bundle.evidence[:3]}
    claims: list[Claim] = []
    for rc in raw_claims or []:
        if not isinstance(rc, dict):
            continue
        text = (rc.get("text") or "").strip()
        if not text:
            continue
        claim_type = rc.get("type") if rc.get("type") in ("FACT", "INTERPRETATION") else "INTERPRETATION"
        evidence_ids: list[str] = []
        financial_fact_ids: list[str] = []
        for ref in rc.get("evidence_refs") or []:
            ref = str(ref)
            m = re.search(r"FACT:([a-zA-Z0-9_]+)", ref)
            if m and m.group(1) in fact_codes:
                financial_fact_ids.append(m.group(1))
                continue
            m = re.search(r"EVIDENCE:([a-fA-F0-9]+)", ref)
            if m and m.group(1) in evidence_by_short_id:
                evidence_ids.append(evidence_by_short_id[m.group(1)])
        claims.append(Claim(text=text, claim_type=claim_type, evidence_ids=evidence_ids, financial_fact_ids=financial_fact_ids))
    return claims


@dataclass(frozen=True)
class WhyItMattersResult:
    text: str | None
    claims: list[Claim] = field(default_factory=list)
    status: str = "omitted_no_evidence"  # "ok" | "omitted_no_evidence" | "omitted_generation_failed" | "omitted_validation_failed"
    attempts: int = 0
    validation_errors: list[dict] = field(default_factory=list)


async def build_why_it_matters(bundle: ArticleEvidenceBundle) -> WhyItMattersResult:
    """The one real entry point. Never raises — a generation or validation
    failure degrades to a real, honest omission (see module docstring),
    exactly like compose_what_happened_from_evidence returning None for a
    company with no evidence."""
    has_financial = bool(bundle.financial_context and bundle.financial_context.has_real_facts)
    if not bundle.resolved or (not bundle.evidence and not has_financial):
        return WhyItMattersResult(text=None, status="omitted_no_evidence")

    selected_facts = select_relevant_financial_facts(bundle.financial_context)
    allowed = build_allowed_values(bundle, bundle.evidence[:3])

    retry_errors: list[dict] | None = None
    last_errors: list[dict] = []
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        prompt = _build_prompt(bundle, selected_facts, retry_errors)
        try:
            raw = await _call_with_fallback(prompt, system=_SYSTEM_PROMPT, max_tokens=500, priority="background")
        except Exception as exc:
            log.warning("why_it_matters.generation_failed", symbol=bundle.symbol, attempt=attempt, error=str(exc)[:200])
            return WhyItMattersResult(text=None, status="omitted_generation_failed", attempts=attempt)

        if not raw:
            last_errors = [{"raw_text": "<empty response>", "value": 0, "kind": "empty"}]
            retry_errors = last_errors
            continue

        parsed = _parse_response(raw)
        if parsed is None or not parsed.get("why_it_matters"):
            last_errors = [{"raw_text": "<unparseable or empty JSON>", "value": 0, "kind": "parse_error"}]
            retry_errors = last_errors
            continue

        text = parsed["why_it_matters"]
        numeric_ok, numeric_errors = validate_numeric_claims(text, allowed)
        period_ok, period_errors = validate_period_claims(text, bundle.financial_context, bundle.evidence[:3])

        if numeric_ok and period_ok:
            claims = _build_claims(parsed.get("claims") or [], bundle, selected_facts)
            return WhyItMattersResult(text=text, claims=claims, status="ok", attempts=attempt)

        last_errors = numeric_errors + [
            {"raw_text": f"FY{e['fiscal_year']}" + (f" Q{e['fiscal_quarter']}" if e.get("fiscal_quarter") else ""),
             "value": 0, "kind": "period"}
            for e in period_errors
        ]
        retry_errors = last_errors
        log.info("why_it_matters.validation_failed", symbol=bundle.symbol, attempt=attempt, errors=last_errors)

    return WhyItMattersResult(text=None, status="omitted_validation_failed", attempts=_MAX_ATTEMPTS, validation_errors=last_errors)
