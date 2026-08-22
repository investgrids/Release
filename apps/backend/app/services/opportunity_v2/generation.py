"""
Fail-closed AI narrative generation — the direct fix for V1's confirmed
title-truncation bug (owner correction, 2026-08-22). V1's `_call_ai()` was
a single hardcoded DeepSeek call, no fallback provider; on any failure it
silently substituted the first article's raw headline sliced to 8 words
(confirmed live: 28/121 real V1 rows show this exact signature) or a
generic "{sector} Growth Opportunity" (6x duplicate "Defence Investment
Opportunity" rows). Neither fallback exists here at all.

Mirrors app/services/aipe/article_generator.py's own proven pattern
exactly: _call_with_fallback (multi-provider, not single-provider),
higher max_tokens, and _parse_and_validate's fail-closed contract (parse
failure or a missing required field -> None, never a fabricated
substitute). generate_narrative() runs LAST in the pipeline (owner
instruction) — only after the deterministic thesis (gate -> coherence ->
identity -> scoring) already exists, so a generation failure never blocks
the deterministic candidate from being persisted; it only means that
candidate's narrative_status becomes "failed_capacity" instead of
"generated" (see orchestration.py).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

import structlog

from app.services.ai_service import _call_with_fallback

log = structlog.get_logger(__name__)

_REQUIRED_FIELDS = ["title", "summary", "matters", "benefits", "risks", "invalidate", "why_bullets"]

_SYSTEM_PROMPT = """You are an Indian equity market analyst writing for a
real investment-thesis card. You will be given a SINGLE, already-verified-
coherent set of real market developments (real headlines, real companies,
real sectors) that a separate deterministic system has already confirmed
belong to one investable thesis. Do not second-guess or reinterpret that
grouping — write about exactly what's given, nothing broader.

Title requirements (strict):
- 6-12 words, a complete descriptive phrase, never a sentence fragment.
- Names the real theme/sector/company the evidence is actually about.
- Never a copy or truncation of any single input headline.
- Never a generic template like "{Sector} Growth Opportunity" or
  "{Sector} Investment Opportunity".

Return ONLY valid JSON, no markdown, no explanation."""


@dataclass
class NarrativeResult:
    title: str
    summary: str
    matters: str
    benefits: str
    risks: list[str]
    invalidate: str
    why_bullets: list[str]


def _strip_fences(text: str) -> str:
    text = re.sub(r"^```(?:json)?\s*", "", text.strip())
    return re.sub(r"\s*```$", "", text).strip()


def _parse_and_validate(raw: str) -> NarrativeResult | None:
    text = _strip_fences(raw)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            log.warning("opportunity_v2.generation.no_json_found", preview=text[:150])
            return None
        try:
            data = json.loads(match.group())
        except json.JSONDecodeError:
            log.warning("opportunity_v2.generation.json_parse_failed", preview=text[:150])
            return None

    for field in _REQUIRED_FIELDS:
        if not data.get(field):
            log.warning("opportunity_v2.generation.missing_required_field", field=field)
            return None

    title = str(data["title"]).strip()
    word_count = len(title.split())
    if word_count < 4 or word_count > 20:
        # A real length guard, not exact-6-12 enforcement (models don't
        # hit an exact word count reliably) -- but under 4 words or 20+
        # is unambiguously wrong (a raw-headline-style fragment on one
        # end, a run-on sentence on the other), not a borderline case
        # worth accepting.
        log.warning("opportunity_v2.generation.title_length_out_of_range", title=title, words=word_count)
        return None
    if title.rstrip().endswith((",", ";", "and", "the", "of", "to", "for", "with")):
        # The literal V1 symptom this replaces: a title that reads as a
        # sentence fragment cut off mid-clause.
        log.warning("opportunity_v2.generation.title_looks_truncated", title=title)
        return None
    if re.fullmatch(r"[\w &]+ (Growth|Investment) Opportunity", title):
        # V1's OTHER confirmed fallback shape: a bare "{Sector} Growth/
        # Investment Opportunity" template with no real specific content
        # at all (confirmed live: 6x duplicate "Defence Investment
        # Opportunity" rows sitting at V1's score ceiling). An LLM
        # collapsing to this exact generic shape is treated the same as
        # V1's own fallback would be -- rejected, not accepted just
        # because an LLM said it this time.
        log.warning("opportunity_v2.generation.title_is_generic_template", title=title)
        return None

    risks = data.get("risks")
    why_bullets = data.get("why_bullets")
    if not isinstance(risks, list) or not risks:
        return None
    if not isinstance(why_bullets, list) or not why_bullets:
        return None

    return NarrativeResult(
        title=title,
        summary=str(data["summary"]).strip(),
        matters=str(data["matters"]).strip(),
        benefits=str(data["benefits"]).strip(),
        risks=[str(r) for r in risks],
        invalidate=str(data["invalidate"]).strip(),
        why_bullets=[str(b) for b in why_bullets],
    )


def _build_prompt(evidence_text: str, sectors: list[str], companies: list[str]) -> str:
    return f"""EVIDENCE (already confirmed coherent -- one real thesis):
{evidence_text[:2000]}

REAL SECTORS INVOLVED: {sectors}
REAL COMPANIES INVOLVED: {companies}

Return exactly this JSON shape:
{{
  "title": "<6-12 word specific investment thesis title>",
  "summary": "<2-3 sentence summary of why this is an opportunity>",
  "matters": "<why this matters for investors, 1-2 sentences>",
  "benefits": "<who benefits and how, naming the real companies above>",
  "risks": ["<risk1>", "<risk2>", "<risk3>"],
  "invalidate": "<what could invalidate this thesis>",
  "why_bullets": ["<bullet1>", "<bullet2>", "<bullet3>", "<bullet4>"]
}}"""


async def generate_narrative(evidence_text: str, sectors: list[str], companies: list[str]) -> NarrativeResult | None:
    """None on ANY failure -- no provider succeeding, unparseable JSON, a
    missing required field, or a title that fails validation. The caller
    (orchestration.py) persists the deterministic candidate regardless and
    sets narrative_status="failed_capacity" in that case; this function
    itself never substitutes a fallback string of any kind."""
    prompt = _build_prompt(evidence_text, sectors, companies)
    try:
        raw = await _call_with_fallback(prompt, system=_SYSTEM_PROMPT, max_tokens=1400, priority="background")
    except Exception as exc:
        log.warning("opportunity_v2.generation.ai_call_failed", error=str(exc)[:200])
        return None

    if not raw:
        return None

    return _parse_and_validate(raw)
