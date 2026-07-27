"""AI Search Research Session Memory — POST /api/ai/search/session-summary.

Own router, same reasoning as the other ai_search_*.py module docstrings.
Everything else Phase 1.7 needs (ambiguous-group disambiguation, context
resolution) lives inside the existing pipeline — this is the one genuinely
new endpoint, for the explicit "Generate Research Summary" action. The
session itself is never stored server-side; this endpoint is stateless,
handed the session's own data by the client on each call.
"""
from __future__ import annotations

import json
import re

import structlog
from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from app.core.limiter import limiter

router = APIRouter()
log = structlog.get_logger(__name__)


def _parse_json_response(raw: str) -> dict | None:
    """Same fence-stripping + regex-salvage pattern as
    specialists/base.py's parse_specialist_json, minus the
    flatten_nested/degraded_response wrapping — this endpoint's schema
    (companies_researched/key_conclusions/...) isn't a specialist response,
    so that shared helper doesn't fit here without a misleading dependency."""
    if not raw:
        return None
    try:
        clean = raw.strip()
        if clean.startswith("```"):
            clean = re.sub(r"^```(?:json)?\s*", "", clean)
            clean = re.sub(r"\s*```$", "", clean).strip()
        return json.loads(clean)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except Exception:
                return None
    return None


class SessionSummaryRequest(BaseModel):
    companies: list[str] = Field(default_factory=list, max_length=20)
    sectors: list[str] = Field(default_factory=list, max_length=10)
    queries: list[str] = Field(default_factory=list, max_length=30)
    current_verdict: str | None = None


class SessionSummaryResponse(BaseModel):
    companies_researched: list[str]
    key_conclusions: list[str]
    risks_identified: list[str]
    open_questions: list[str]
    suggested_next_research: list[str]
    degraded: bool = False


@router.post("/session-summary", response_model=SessionSummaryResponse)
@limiter.limit("10/minute")
async def generate_session_summary(request: Request, body: SessionSummaryRequest):
    """One LLM call, only on the user's explicit "Generate Research
    Summary" click — never automatic, never per-query. Synthesizes across
    everything the session has already covered rather than re-deriving it
    from scratch; no new evidence is fetched here."""
    if not body.queries:
        return SessionSummaryResponse(
            companies_researched=[], key_conclusions=[], risks_identified=[],
            open_questions=[], suggested_next_research=[], degraded=True,
        )

    from app.services.ai_service import _call_with_fallback

    prompt = f"""A user's research session on MarketRipple has covered these questions, in order:
{chr(10).join(f"- {q}" for q in body.queries[-15:])}

Companies discussed: {', '.join(body.companies) or 'none identified'}
Sectors discussed: {', '.join(body.sectors) or 'none identified'}
Most recent verdict: {body.current_verdict or 'none yet'}

Synthesize this into a research session summary. Return ONLY this JSON (no fences, no commentary):
{{
  "companies_researched": ["one line per company — what was concluded about it"],
  "key_conclusions": ["2-4 bullet-point conclusions across the whole session"],
  "risks_identified": ["2-4 risks that came up across the session"],
  "open_questions": ["1-3 questions this session raised but didn't resolve"],
  "suggested_next_research": ["2-3 specific, concrete follow-up questions"]
}}

Ground every line in the actual queries listed above — never invent a company, conclusion, or
risk that wasn't plausibly covered by this specific session's questions. Research framing only —
never say Buy/Sell/Hold/Accumulate/Reduce anywhere."""

    raw = await _call_with_fallback(
        prompt,
        "You are MarketRipple's research session summarizer. Respond with valid JSON only.",
        max_tokens=1200,
    )
    parsed = _parse_json_response(raw)
    if not parsed:
        log.warning("ai_search_v3.session_summary.degraded")
        return SessionSummaryResponse(
            companies_researched=[], key_conclusions=[], risks_identified=[],
            open_questions=[], suggested_next_research=[], degraded=True,
        )

    return SessionSummaryResponse(
        companies_researched=parsed.get("companies_researched", []),
        key_conclusions=parsed.get("key_conclusions", []),
        risks_identified=parsed.get("risks_identified", []),
        open_questions=parsed.get("open_questions", []),
        suggested_next_research=parsed.get("suggested_next_research", []),
        degraded=False,
    )
