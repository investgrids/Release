"""
Article Generator — creates intelligence articles using type-specific templates
and real historical data from HistoricalMarketEvent.

Philosophy:
  - Use ONLY verified historical data fetched from the DB.
  - Never hallucinate history — the prompt explicitly says "only use provided data".
  - Each article type gets its own specialized prompt from content_templates.py.
  - Include the live MIE context (story, mood, themes) to ground the article.
"""
from __future__ import annotations

import json
import re
import uuid
from typing import Any

import structlog

from app.services.ai_service import _call_with_fallback
from app.services.aipe.content_templates import SYSTEM_PROMPT, get_template
from app.services.aipe.fact_grounding import fetch_price_moves, format_price_grounding

log = structlog.get_logger(__name__)


async def generate_intelligence_article(
    article_type: str,
    event: dict[str, Any],
    mie_context: dict[str, Any],
    historical: list[dict[str, Any]],
    question: str = "",
    failure_log: list[dict] | None = None,
) -> dict[str, Any] | None:
    """
    Generate a structured intelligence article using the appropriate template.

    Args:
        article_type: One of the 12 AIPE article types
        event: Triage event or MIE context dict
        mie_context: Current MIE state (story, mood, themes, etc.)
        historical: Verified historical events from HistoricalMarketEvent DB
        failure_log: optional, purely additive (see _call_provider's own
            docstring) -- when passed, every skipped/failed provider
            attempt on the way to this call's result (or lack of one)
            appends a structured {model, provider, reason} record to it.
            Built for candidate_lifecycle.py's real provider-attempt
            visibility on scheduled/synthetic candidates (2026-08-30) --
            every existing caller that doesn't pass one sees identical
            behavior to before this parameter existed.

    Returns:
        Parsed article dict or None on failure.
    """
    template = get_template(article_type)

    # Build template variables
    sectors = event.get("sectors") or []
    if isinstance(sectors, list) and sectors and isinstance(sectors[0], dict):
        sectors_str = ", ".join(s.get("name", "") for s in sectors[:6])
    else:
        sectors_str = ", ".join(str(s) for s in sectors[:6]) or "Multiple sectors"

    tickers = event.get("tickers") or event.get("companies") or []
    if isinstance(tickers, list) and tickers and isinstance(tickers[0], dict):
        companies_str = ", ".join(c.get("symbol") or c.get("name", "") for c in tickers[:6])
    else:
        companies_str = ", ".join(str(t) for t in tickers[:6]) or "Multiple companies"

    themes_str = ", ".join(mie_context.get("themes") or []) or "Markets"
    historical_str = _format_historical(historical, limit=10 if article_type == "historical_intelligence" else 4)

    nifty_chg = mie_context.get("nifty_chg")
    nifty_change_str = f"{nifty_chg:+.2f}%" if nifty_chg is not None else "data unavailable"

    market_context_str = _format_market_context(mie_context)

    # Fact Grounding, Phase 1 (2026-08-10) — real per-company price moves,
    # fetched from the same live quote service the article page itself
    # uses, injected into the existing market_context slot so the LLM
    # writes company impact from real numbers instead of inventing a
    # direction/magnitude. See fact_grounding.py's module docstring for the
    # full rationale; validate_fact_grounding() below cross-checks the
    # LLM's actual output against these same numbers after generation.
    candidate_symbols = [
        (c.get("symbol") or c.get("name") or "") for c in tickers
    ] if isinstance(tickers, list) and tickers and isinstance(tickers[0], dict) else (
        [str(t) for t in tickers] if isinstance(tickers, list) else []
    )
    candidate_symbols = [s for s in candidate_symbols if s]
    price_moves = await fetch_price_moves(candidate_symbols) if candidate_symbols else {}
    price_grounding = format_price_grounding(price_moves)
    if price_grounding:
        market_context_str = f"{market_context_str} | {price_grounding}"

    user_prompt = template.format(
        headline=event.get("headline") or event.get("title") or "Market Event",
        summary=(event.get("one_liner") or event.get("summary") or "")[:600],
        article_type=article_type.replace("_", " ").title(),
        market_context=market_context_str,
        market_mood=mie_context.get("mood", "Uncertain"),
        sectors=sectors_str,
        companies=companies_str,
        themes=themes_str,
        historical=historical_str,
        nifty_change=nifty_change_str,
        session=mie_context.get("session", "live"),
        question=question,
    )

    try:
        raw = await _call_with_fallback(user_prompt, system=SYSTEM_PROMPT, max_tokens=3000, failure_log=failure_log, priority="background")
    except Exception as exc:
        log.error("article_generator.ai_error", type=article_type, error=str(exc))
        if failure_log is not None:
            failure_log.append({"model": None, "provider": None, "reason": f"exception:{exc}"[:200]})
        return None

    if not raw:
        return None

    parsed = _parse_and_validate(raw, article_type, event)
    if parsed is None and failure_log is not None:
        failure_log.append({"model": None, "provider": None, "reason": "schema_parse_failed"})
    if parsed is not None:
        # Pipeline-internal only — never a real IntelligenceArticle column;
        # publisher.py reads this to run validate_fact_grounding() against
        # the SAME price snapshot the prompt itself was grounded in, rather
        # than re-fetching (which could drift between generation and
        # validation, and doubles the live-quote API load for no benefit).
        parsed["_price_moves_grounding"] = price_moves
    return parsed


def _format_market_context(ctx: dict[str, Any]) -> str:
    """Format MIE context into a clean string for the prompt."""
    parts = []
    if ctx.get("story"):
        parts.append(f"Market Narrative: {ctx['story']}")
    if ctx.get("mood"):
        parts.append(f"Mood: {ctx['mood']} (pulse: {ctx.get('pulse', '=')})")
    if ctx.get("sector_rotation"):
        parts.append(f"Sector Rotation: {ctx['sector_rotation']}")
    if ctx.get("opportunity"):
        parts.append(f"Current Opportunity: {ctx['opportunity']}")
    if ctx.get("risk"):
        parts.append(f"Current Risk: {ctx['risk']}")
    return " | ".join(parts) if parts else "Market context not available"


def _format_historical(historical: list[dict[str, Any]], limit: int = 4) -> str:
    """
    Format verified historical events for the prompt.
    Explicitly marks them as real — AI must not add others.

    Accepts the terse {event, date, outcome, sentiment, sectors} shape used
    everywhere, and transparently uses richer fields (nifty_1w/1m, winners,
    losers, key_lesson) when present — used by Historical Intelligence pages,
    which need more than a one-line-per-event summary to synthesize a pattern
    across many events rather than ground one.
    """
    if not historical:
        return "No verified historical precedents available for this event type."

    lines = [f"VERIFIED HISTORICAL DATA — {min(len(historical), limit)} events (use only these — do not add others):"]
    for h in historical[:limit]:
        line = f"- {h.get('event', 'Unknown event')} ({h.get('date', '—')}{', ' + h['category'] if h.get('category') else ''})"
        moves = []
        if h.get("outcome") is not None:
            moves.append(f"1D: {h['outcome']:+.1f}%")
        if h.get("nifty_1w") is not None:
            moves.append(f"1W: {h['nifty_1w']:+.1f}%")
        if h.get("nifty_1m") is not None:
            moves.append(f"1M: {h['nifty_1m']:+.1f}%")
        if moves:
            line += " → Nifty " + ", ".join(moves)
        if h.get("sentiment"):
            line += f" | Sentiment: {h['sentiment']}"
        if h.get("sectors"):
            line += f" | Sectors: {', '.join(h['sectors'][:3])}"
        lines.append(line)
        if h.get("winners"):
            w = ", ".join(f"{x.get('symbol', '?')} ({x.get('return_1m')}% 1M)" for x in h["winners"][:3] if isinstance(x, dict))
            if w:
                lines.append(f"    Winners: {w}")
        if h.get("losers"):
            l = ", ".join(str(x.get("symbol", "?")) if isinstance(x, dict) else str(x) for x in h["losers"][:3])
            if l:
                lines.append(f"    Losers: {l}")
        if h.get("key_lesson"):
            lines.append(f"    Lesson: {h['key_lesson']}")
    return "\n".join(lines)


def _parse_and_validate(
    raw: str,
    article_type: str,
    event: dict[str, Any],
) -> dict[str, Any] | None:
    """Parse AI response JSON and validate required fields."""
    text = raw.strip()
    # Strip markdown fences
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", text)
        if m:
            try:
                data = json.loads(m.group())
            except json.JSONDecodeError:
                log.error("article_generator.json_parse_failed", preview=text[:150])
                return None
        else:
            log.error("article_generator.no_json_found", preview=text[:150])
            return None

    # Validate required fields
    required = ["headline", "executive_summary", "key_takeaway"]
    for field in required:
        if not data.get(field):
            log.warning("article_generator.missing_required_field", field=field)
            return None

    # Ensure slug is clean and unique
    raw_slug = data.get("slug") or re.sub(r"[^\w\s-]", "", data.get("headline", ""))
    slug = re.sub(r"[^a-z0-9-]", "-", raw_slug.lower())
    slug = re.sub(r"-+", "-", slug).strip("-")[:100]
    event_suffix = (event.get("event_id") or event.get("id") or str(uuid.uuid4())[:8])[:8]
    data["slug"] = f"{slug}-{event_suffix}"

    # Ensure article_type is set
    data["article_type"] = article_type

    _normalize_pipe_enum_leaks(data)

    return data


# content_templates.py's schema documents enum-shaped fields as pipe-joined
# hints ("positive|negative|neutral", "immediate|short|medium|long") — the
# LLM sometimes echoes that hint text verbatim instead of picking one value,
# producing live-confirmed output like impact="positive|neutral" and
# timeframe="short|medium" (renders on the frontend, via a CSS `capitalize`
# transform, as the garbled "Positive|Neutral" / "short|medium" seen in
# production). Same root-cause class as the earlier "[specific date]"
# unfilled-placeholder bug — a content-shaped safety net at the parse
# boundary, not a prompt fix, since a prompt change can reduce but can't
# reliably guarantee this never recurs. Takes the first listed value rather
# than rejecting the whole article — these are small structured fields
# where a deterministic pick is safe, and the rest of the generation is
# usually otherwise good.
_ENUM_FIELD_SPECS: list[tuple[str, tuple[str, ...]]] = [
    ("companies_affected", ("impact", "timeframe")),
    ("sectors_affected", ("impact", "magnitude")),
    ("opportunities", ("timeframe", "risk")),
    ("risks", ("severity",)),
]


def _normalize_pipe_enum_leaks(data: dict[str, Any]) -> None:
    for list_field, keys in _ENUM_FIELD_SPECS:
        for item in (data.get(list_field) or []):
            if not isinstance(item, dict):
                continue
            for key in keys:
                val = item.get(key)
                if isinstance(val, str) and "|" in val:
                    first = val.split("|", 1)[0].strip()
                    if first:
                        item[key] = first


def compute_seo_score(article: dict[str, Any]) -> int:
    """Heuristic SEO score 0-100 based on article completeness."""
    score = 0
    hl = article.get("headline") or ""
    st = article.get("seo_title") or ""
    md = article.get("meta_description") or ""
    wh = article.get("what_happened") or ""

    if hl:                                                      score += 12
    if 40 <= len(st) <= 65:                                     score += 15
    if 120 <= len(md) <= 160:                                   score += 15
    if article.get("slug"):                                     score += 8
    if len(article.get("faqs") or []) >= 2:                    score += 12
    if len(article.get("companies_affected") or []) >= 2:      score += 10
    if len(article.get("sectors_affected") or []) >= 1:        score += 8
    if article.get("historical_context"):                       score += 10
    if len(article.get("what_to_watch_next") or []) >= 3:      score += 5
    if len(article.get("ripple_effect") or []) >= 2:           score += 5
    return min(score, 100)
