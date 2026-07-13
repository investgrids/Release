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

log = structlog.get_logger(__name__)


async def generate_intelligence_article(
    article_type: str,
    event: dict[str, Any],
    mie_context: dict[str, Any],
    historical: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """
    Generate a structured intelligence article using the appropriate template.

    Args:
        article_type: One of the 12 AIPE article types
        event: Triage event or MIE context dict
        mie_context: Current MIE state (story, mood, themes, etc.)
        historical: Verified historical events from HistoricalMarketEvent DB

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
    historical_str = _format_historical(historical)

    nifty_chg = mie_context.get("nifty_chg")
    nifty_change_str = f"{nifty_chg:+.2f}%" if nifty_chg is not None else "data unavailable"

    market_context_str = _format_market_context(mie_context)

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
    )

    try:
        raw = await _call_with_fallback(user_prompt, system=SYSTEM_PROMPT, max_tokens=3000)
    except Exception as exc:
        log.error("article_generator.ai_error", type=article_type, error=str(exc))
        return None

    if not raw:
        return None

    return _parse_and_validate(raw, article_type, event)


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


def _format_historical(historical: list[dict[str, Any]]) -> str:
    """
    Format verified historical events for the prompt.
    Explicitly marks them as real — AI must not add others.
    """
    if not historical:
        return "No verified historical precedents available for this event type."

    lines = ["VERIFIED HISTORICAL DATA (use only these — do not add others):"]
    for h in historical[:4]:
        line = f"- {h.get('event', 'Unknown event')} ({h.get('date', '—')})"
        if h.get("outcome") is not None:
            line += f" → Nifty 1-day: {h['outcome']:+.1f}%"
        if h.get("sentiment"):
            line += f" | Sentiment: {h['sentiment']}"
        if h.get("sectors"):
            line += f" | Sectors: {', '.join(h['sectors'][:3])}"
        lines.append(line)
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

    return data


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
