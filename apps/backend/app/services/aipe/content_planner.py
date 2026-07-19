"""
Content Planner — decides which article type to generate for a given
intelligence signal.

Inputs: MIE triage event + current market context (session, mood, themes)
Output: (article_type, story_id, priority)

The planner ensures we produce 3-8 high-quality stories per day by:
  1. Matching event characteristics to the right template
  2. Using session awareness (morning → morning_intelligence, 4PM → market_wrap)
  3. Respecting the daily article limit
"""
from __future__ import annotations

import re
from datetime import datetime, timezone, timedelta
from typing import Any

_IST = timezone(timedelta(hours=5, minutes=30))


def _ist_now() -> datetime:
    return datetime.now(_IST)


def _session() -> str:
    now = _ist_now()
    h, m = now.hour, now.minute
    mins = h * 60 + m
    if mins < 9 * 60 + 15:
        return "pre_market"
    if mins <= 15 * 60 + 30:
        return "live"
    return "post_market"


def _text(event: dict[str, Any]) -> str:
    return " ".join([
        event.get("headline") or event.get("title") or "",
        event.get("one_liner") or event.get("summary") or "",
    ]).lower()


# ── Keyword → article type mappings ──────────────────────────────────────────
_POLICY_KW = [
    "rbi", "repo rate", "rate cut", "rate hike", "monetary policy", "sebi",
    "budget", "gst", "government policy", "ministry", "regulation", "circular",
    "federal reserve", "fomc", "ecb",
]
_RIPPLE_KW = [
    "crude", "oil", "gold", "silver", "commodity", "inflation", "global cues",
    "us markets", "fed rate", "dollar", "rupee depreciation", "exchange rate",
]
_COMPANY_KW = [
    "results", "earnings", "quarterly", "q1", "q2", "q3", "q4", "revenue",
    "profit", "loss", "guidance", "management", "ceo", "acquisition", "merger",
    "fundraise", "ipo listing",
]
_OPPORTUNITY_KW = [
    "opportunity", "buy", "undervalued", "dip", "correction", "52-week low",
    "strong buy", "upgrade", "outperform", "rally", "breakout",
]
_THEME_KW = [
    "theme", "megatrend", "ev", "electric vehicle", "renewable", "ai", "data centre",
    "defence", "railways", "infrastructure", "pli", "semiconductor",
]


def select_article_type(
    event: dict[str, Any],
    market_context: dict[str, Any] | None = None,
) -> tuple[str, str, int]:
    """
    Returns (article_type, story_id, priority).

    story_id:
      - Daily stories: "morning-YYYY-MM-DD", "wrap-YYYY-MM-DD"
      - Breaking: "breaking-{event_id[:16]}"
      - Policy: "policy-{slug}"
      - Other: "intel-{event_id[:16]}"

    priority: 1 (highest) → 10 (lowest)
    """
    text = _text(event)
    session = _session()
    today = _ist_now().strftime("%Y-%m-%d")
    event_id = event.get("event_id") or event.get("id") or "unknown"
    sectors = event.get("sectors") or []
    companies = event.get("tickers") or event.get("companies") or []
    urgency = int(event.get("urgency") or 0)
    is_structural = bool(event.get("is_structural"))

    # ── Session-based overrides ───────────────────────────────────────────────
    # Pre-market: generate morning intelligence (once per day)
    if session == "pre_market":
        return "morning_intelligence", f"morning-{today}", 1

    # Post-market after 3:30 PM: generate market wrap
    now = _ist_now()
    if now.hour == 15 and now.minute >= 30 or now.hour >= 16:
        return "market_wrap", f"wrap-{today}", 2

    # ── Content type selection ────────────────────────────────────────────────
    # Policy / Macro
    if any(kw in text for kw in _POLICY_KW):
        slug = re.sub(r"[^a-z0-9]", "-", text[:40].strip())
        return "policy_intelligence", f"policy-{slug}-{today}", 1

    # High urgency + multi-sector ripple
    if urgency >= 8 and len(sectors) >= 3:
        return "ripple_intelligence", f"ripple-{event_id[:16]}-{today}", 2

    # Structural / commodity ripple
    if any(kw in text for kw in _RIPPLE_KW) or is_structural:
        return "ripple_intelligence", f"ripple-{event_id[:16]}-{today}", 3

    # Company-specific earnings/results
    if any(kw in text for kw in _COMPANY_KW) and companies:
        co_name = (companies[0] if isinstance(companies[0], str) else companies[0].get("symbol", "co"))[:10]
        return "company_intelligence", f"company-{co_name}-{today}", 4

    # Sector-wide event
    if len(sectors) >= 2 and not any(kw in text for kw in _COMPANY_KW):
        sector_slug = sectors[0].lower().replace(" ", "-")[:20] if sectors else "sector"
        return "sector_intelligence", f"sector-{sector_slug}-{today}", 4

    # Theme-related
    if any(kw in text for kw in _THEME_KW):
        return "theme_intelligence", f"theme-{event_id[:16]}-{today}", 5

    # Opportunity
    if any(kw in text for kw in _OPPORTUNITY_KW) and urgency >= 6:
        return "opportunity_intelligence", f"opp-{event_id[:16]}-{today}", 5

    # High urgency breaking (fallback for very urgent events)
    if urgency >= 8:
        return "breaking_intelligence", f"breaking-{event_id[:16]}", 2

    # Default: event analysis (breaking)
    return "breaking_intelligence", f"intel-{event_id[:16]}-{today}", 6


# Canonical theme baskets, shared with the Theme Engine's scoring worker so
# a "theme" angle always names one of the same 12 themes the rest of the
# app already tracks (theme_worker.THEMES), rather than inventing new ones.
def _theme_engine_baskets() -> dict[str, list[str]]:
    from app.services.intelligence.theme_worker import THEMES
    return THEMES


def _match_theme(companies_affected: list[dict[str, Any]], sectors_affected: list[dict[str, Any]]) -> str | None:
    themes = _theme_engine_baskets()
    tickers = {str(c.get("symbol", "")).upper() for c in (companies_affected or []) if c.get("symbol")}
    for theme_name, basket in themes.items():
        if tickers & set(basket):
            return theme_name
    sector_names = [str(s.get("name", "")) for s in (sectors_affected or []) if s.get("name")]
    for theme_name in themes:
        head = theme_name.split(" & ")[0].lower()
        if any(head in s.lower() or s.lower() in theme_name.lower() for s in sector_names):
            return theme_name
    return None


_QUESTION_TEMPLATES = [
    "Should I Buy {company} After {event_phrase}?",
    "Is {event_phrase} Good or Bad for {company} Investors?",
]


def plan_extra_angles(
    primary_article_type: str,
    primary_story_id: str,
    primary_headline: str,
    companies_affected: list[dict[str, Any]],
    sectors_affected: list[dict[str, Any]],
    max_companies: int = 2,
    max_questions: int = 2,
) -> list[tuple[str, str, str, str | None, str | None]]:
    """
    Given the just-published primary article's own AI-vetted companies/sectors,
    decide which additional angle-specific articles to spin off from the same
    event — turning one event into several search-intent-targeted pages
    (e.g. RBI policy → primary overview + HDFC angle + ICICI angle + Banking
    sector rollup + Banking theme + "Should I Buy HDFC?" question) instead of
    exactly one article.

    Returns a list of (article_type, story_id, angle, angle_entity, question_text)
    tuples — question_text is only set for "question" angles (used both as the
    {question} prompt variable and to force a deterministic, search-matching
    headline rather than trusting the AI to phrase it exactly right).
    Skips an angle that would just duplicate what the primary article already is.
    """
    plans: list[tuple[str, str, str, str | None, str | None]] = []

    companies = [c for c in (companies_affected or []) if c.get("symbol")]
    for c in companies[:max_companies]:
        symbol = str(c["symbol"]).upper()
        if primary_article_type == "company_intelligence" and symbol in primary_story_id.upper():
            continue  # primary already IS this company's angle
        plans.append((
            "company_intelligence",
            f"{primary_story_id}-co-{symbol}",
            "per_company",
            symbol,
            None,
        ))

    sectors = [s for s in (sectors_affected or []) if s.get("name")]
    if len(sectors) >= 2 and primary_article_type != "sector_intelligence":
        top_sector = str(sectors[0]["name"])
        sector_slug = re.sub(r"[^a-z0-9]+", "-", top_sector.lower())[:20].strip("-")
        plans.append((
            "sector_intelligence",
            f"{primary_story_id}-sector-{sector_slug}",
            "sector_rollup",
            top_sector,
            None,
        ))

    if primary_article_type != "theme_intelligence":
        theme = _match_theme(companies_affected, sectors_affected)
        if theme:
            theme_slug = re.sub(r"[^a-z0-9]+", "-", theme.lower())[:20].strip("-")
            plans.append((
                "theme_intelligence",
                f"{primary_story_id}-theme-{theme_slug}",
                "theme",
                theme,
                None,
            ))

    event_phrase = re.sub(r"\s+", " ", primary_headline).strip()
    if len(event_phrase) > 60:
        event_phrase = event_phrase[:57].rsplit(" ", 1)[0] + "..."
    for i, c in enumerate(companies[:max_questions]):
        company_name = str(c.get("name") or c["symbol"])
        symbol = str(c["symbol"]).upper()
        q_template = _QUESTION_TEMPLATES[i % len(_QUESTION_TEMPLATES)]
        question_text = q_template.format(company=company_name, event_phrase=event_phrase)
        q_slug = re.sub(r"[^a-z0-9]+", "-", question_text.lower())[:40].strip("-")
        plans.append((
            "question_intelligence",
            f"{primary_story_id}-q-{symbol}-{q_slug[:20]}",
            "question",
            symbol,
            question_text,
        ))

    return plans


def should_generate_today(
    article_type: str,
    story_id: str,
    existing_story_ids: set[str],
    daily_count: int,
    max_per_day: int = 8,
) -> tuple[bool, str]:
    """
    Check if we should generate a new article or skip.
    Returns (should_generate, reason).
    """
    if daily_count >= max_per_day:
        return False, f"Daily limit reached ({daily_count}/{max_per_day})"

    # Morning and wrap: exactly one per day
    if article_type in ("morning_intelligence", "market_wrap"):
        if story_id in existing_story_ids:
            return False, f"{article_type} already generated for today"
        return True, "Scheduled daily intelligence"

    return True, f"New {article_type} approved"
