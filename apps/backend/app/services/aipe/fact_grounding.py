"""
Fact Grounding — Phase 1 of the AI Article Pipeline fix (2026-08-10).

Core principle (per the approved spec): the LLM never has authority over
facts or causal claims, only over how to phrase them. This module is
deliberately scoped to NOT change the generation schema or break any
downstream consumer (insights.py, the article page) — it adds two things
on top of the existing pipeline:

  1. Real per-company price-move grounding, fetched from the same live
     quote service the article page already uses (market_data_service),
     injected into the prompt's existing {market_context} slot so the LLM
     writes from real numbers instead of inventing a direction/magnitude.
  2. Deterministic post-generation validators that catch the LLM when it
     contradicts those same real numbers or contradicts the source event's
     own text — run in quality_validator's spirit (a required gate, not a
     style suggestion): shared boilerplate reasons across companies,
     sentiment/magnitude mismatches against the real price move, and
     status-tense mismatches (a draft event described as decided, or vice
     versa).

Deliberately NOT built here (would be a schema change / Phase 2 territory,
per the user's own scoping decision): a full upstream Fact Object with
per-field source_fields, keyword/tag grounding (already solved differently
— see seo_intelligence.py, which computes keywords from real entities
rather than trusting LLM output), and a regenerate-with-errors loop.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any

import structlog

log = structlog.get_logger(__name__)

# ── Real price-move fetch ────────────────────────────────────────────────────

_LARGE_MOVE_THRESHOLD_PCT = 2.0  # a move at/above this magnitude must not be described as "neutral"
_SIGN_MISMATCH_TOLERANCE_PCT = 0.3  # small moves near zero can't reliably contradict a stated direction


async def fetch_price_moves(symbols: list[str]) -> dict[str, float] | None:
    """Real today's % change per symbol, via the same market_data_service
    the article page's live quotes already use.

    Returns `None` ONLY on a total fetch failure (the underlying call
    raised) — this is a real, meaningful signal, not just "no data": it's
    what lets validate_fact_grounding() distinguish "we checked and it's
    consistent" from "we never got the chance to check" (see that
    function's fail-closed handling). Returns `{}` when there was simply
    nothing to fetch (no candidate symbols) or the call succeeded but found
    no live quotes for these symbols — both legitimate, not a failure.
    Generation itself must still proceed either way; only the downstream
    validator's severity depends on which case this was."""
    if not symbols:
        return {}
    try:
        from app.services.market_data_service import market_data_service
        quotes = await market_data_service.get_quotes([s.upper() for s in symbols[:10]])
        return {q.symbol.upper(): q.change_percent for q in quotes}
    except Exception as exc:
        log.warning("fact_grounding.price_fetch_failed", error=str(exc)[:200])
        return None


def format_price_grounding(price_moves: dict[str, float]) -> str:
    """Appended into the existing {market_context} prompt slot (see
    article_generator.py) — no template schema change needed since every
    article type's prompt already includes market_context."""
    if not price_moves:
        return ""
    parts = [f"{sym} {pct:+.2f}%" for sym, pct in price_moves.items()]
    return "REAL PRICE MOVES TODAY (ground your company analysis in these — do not invent a different direction or magnitude): " + ", ".join(parts)


# ── Post-generation validators ───────────────────────────────────────────────

_DRAFT_PATTERNS = re.compile(r"\b(draft|proposal|proposed|consider(ing|s)?|likely to|may |could |plans? to|considering)\b", re.IGNORECASE)
_DECIDED_PATTERNS = re.compile(r"\b(finaliz(ed|es)|has decided|decision has been made|approved|ruling|has ruled|enacted|implemented)\b", re.IGNORECASE)

_REASON_SIMILARITY_THRESHOLD = 0.90


def check_shared_causal_reasons(companies_affected: list[dict[str, Any]]) -> list[str]:
    """Catches the exact production bug the spec names: the same boilerplate
    causal reason reused verbatim (or near-verbatim) for two different
    companies, which reads as real per-company analysis but isn't."""
    errors: list[str] = []
    reasons = [
        (c.get("symbol") or c.get("name") or "?", (c.get("reason") or "").strip())
        for c in (companies_affected or [])
        if (c.get("reason") or "").strip()
    ]
    for i in range(len(reasons)):
        for j in range(i + 1, len(reasons)):
            sym_a, reason_a = reasons[i]
            sym_b, reason_b = reasons[j]
            similarity = SequenceMatcher(None, reason_a.lower(), reason_b.lower()).ratio()
            if similarity >= _REASON_SIMILARITY_THRESHOLD:
                errors.append(f"SHARED_CAUSAL_REASON: {sym_a} and {sym_b} have near-identical reasons ({similarity:.0%} match)")
    return errors


def check_sentiment_magnitude_consistency(
    companies_affected: list[dict[str, Any]],
    price_moves: dict[str, float],
) -> list[str]:
    """Catches the exact production bug the spec names: a -5.84% move
    tagged 'neutral', or a stated impact direction that contradicts a real,
    unambiguous price move. Only checks companies we actually have a real
    fetched price for — silent (not an error) when quote data is
    unavailable, since that's a data-availability gap, not a fact error."""
    errors: list[str] = []
    for c in (companies_affected or []):
        sym = (c.get("symbol") or "").upper()
        if sym not in price_moves:
            continue
        move = price_moves[sym]
        impact = (c.get("impact") or "neutral").lower()

        if abs(move) >= _LARGE_MOVE_THRESHOLD_PCT and impact == "neutral":
            errors.append(f"SENTIMENT_MAGNITUDE_MISMATCH: {sym} moved {move:+.2f}% (large) but is tagged neutral")
        elif move >= _SIGN_MISMATCH_TOLERANCE_PCT and impact == "negative":
            errors.append(f"SENTIMENT_DIRECTION_MISMATCH: {sym} is up {move:+.2f}% but is tagged negative")
        elif move <= -_SIGN_MISMATCH_TOLERANCE_PCT and impact == "positive":
            errors.append(f"SENTIMENT_DIRECTION_MISMATCH: {sym} is down {move:+.2f}% but is tagged positive")
    return errors


def check_status_tense(source_text: str, body_text: str) -> list[str]:
    """Catches a draft/proposed regulatory or corporate event being written
    up as finalized (or the reverse) — the exact 'MPC decision vs NBFC
    draft' confusion the spec names. Both texts are real (source_text is
    the triage event's own headline+summary; body_text is the LLM's
    what_happened/why_it_matters) — this never introduces a new fact, it
    only checks the LLM's tense against the source's own tense."""
    errors: list[str] = []
    source_is_draft = bool(_DRAFT_PATTERNS.search(source_text))
    source_is_decided = bool(_DECIDED_PATTERNS.search(source_text))
    body_is_decided = bool(_DECIDED_PATTERNS.search(body_text))
    body_is_draft = bool(_DRAFT_PATTERNS.search(body_text))

    # Only flag when the source is unambiguous (draft XOR decided) and the
    # body asserts the opposite unambiguous state — a source that mentions
    # both, or a body that hedges with both, is genuinely ambiguous prose,
    # not a clear-cut status error.
    if source_is_draft and not source_is_decided and body_is_decided and not body_is_draft:
        errors.append("STATUS_MISMATCH: source event is a draft/proposal but article describes it as finalized/decided")
    if source_is_decided and not source_is_draft and body_is_draft and not body_is_decided:
        errors.append("STATUS_MISMATCH: source event is decided/final but article describes it as a pending draft")
    return errors


def validate_fact_grounding(
    article: dict[str, Any],
    price_moves: dict[str, float] | None,
    source_headline: str,
    source_summary: str,
) -> tuple[bool, list[str]]:
    """Required gate — same 'do not publish on failure' severity as
    quality_validator's required checks, run as an additional check
    alongside it (see publisher.py). Returns (passed, errors).

    price_moves=None means fetch_price_moves() hit a TOTAL failure (not
    "no data found for these symbols", which is a normal `{}`/partial
    dict) — this is treated as fail-CLOSED, not fail-open, whenever the
    article actually has companies that needed checking. The earlier
    version of this function silently skipped any company with no matching
    price entry, which meant a total market-data outage produced zero
    validation errors and published unchecked — exactly on the volatile,
    fast-moving sessions where feeds are most likely to lag and this check
    matters most. A company-less article (pure macro/policy piece) is
    unaffected either way, since there's nothing to check against real
    prices regardless of fetch status.
    """
    errors: list[str] = []
    companies = article.get("companies_affected") or []
    has_symbol_companies = any((c.get("symbol") or "") for c in companies)

    if price_moves is None:
        if has_symbol_companies:
            errors.append(
                "PRICE_DATA_UNAVAILABLE: could not fetch real price moves — "
                "unable to verify company sentiment/impact tags against reality"
            )
        price_moves = {}

    errors += check_shared_causal_reasons(companies)
    errors += check_sentiment_magnitude_consistency(companies, price_moves)

    body_text = " ".join(filter(None, [article.get("what_happened"), article.get("why_it_matters")]))
    source_text = " ".join(filter(None, [source_headline, source_summary]))
    if body_text and source_text:
        errors += check_status_tense(source_text, body_text)

    return len(errors) == 0, errors
