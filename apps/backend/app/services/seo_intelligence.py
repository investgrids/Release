"""
SEO Intelligence — Phase 3 of the Daily Brief restructure.

Deliberately NOT a new article generator and NOT a change to AIPE's LLM
prompts (article_generator.py/content_templates.py are untouched by this
module) — this is a deterministic, additive layer that runs AFTER an
article's real content already exists (companies_affected/sectors_affected
are the LLM's own already-generated, already-validated output — the same
"real data, not new fabrication" pattern publisher.py's internal_links
already uses), computing search-intent metadata from it: headline angle,
keyword set, and internal-link opportunities.

Nothing here is invented — every keyword/entity comes from the article's
own real companies/sectors/themes; there is no free-text generation.
"""
from __future__ import annotations

from typing import Any

# ── Headline angle classification — 11-strategy taxonomy ────────────────────
# Adopted 2026-08-10 per the AI Newsroom redesign audit, replacing the
# original 7-value taxonomy (news/question/investor/sector/comparison/
# explanation/historical) built for Daily Brief's own SEO layer. Old stored
# values are never deleted or rewritten in the DB — LEGACY_ANGLE_MAP
# translates them at read time (see insights.py), so historical rows keep
# their original value in storage but every API consumer always sees the
# current 11-value taxonomy.
HEADLINE_ANGLES = (
    "BREAKING_NEWS", "DATA_STATUS", "INVESTOR_IMPACT", "QUESTION_AEO",
    "COMPANY_IMPACT", "COMPARISON", "HISTORICAL_PATTERN", "SECTOR_IMPACT",
    "EARNINGS", "IPO", "RISK_OPPORTUNITY",
)

# Old value -> new value. DATA_STATUS is the closest available bucket for
# the old "explanation" (evergreen/educational content) — not a perfect
# semantic match, but the 11-strategy list has no dedicated "explainer"
# category, and DATA_STATUS ("here is a factual status/data point") is a
# reasonable catch-all rather than inventing a 12th value unilaterally.
LEGACY_ANGLE_MAP: dict[str, str] = {
    "news": "BREAKING_NEWS",
    "question": "QUESTION_AEO",
    "investor": "INVESTOR_IMPACT",
    "sector": "SECTOR_IMPACT",
    "comparison": "COMPARISON",
    "explanation": "DATA_STATUS",
    "historical": "HISTORICAL_PATTERN",
}


def resolve_headline_angle(stored_value: str | None) -> str | None:
    """Read-time translation for pre-2026-08-10 rows — see module note above."""
    if not stored_value:
        return None
    if stored_value in HEADLINE_ANGLES:
        return stored_value
    return LEGACY_ANGLE_MAP.get(stored_value, stored_value)


_EARNINGS_KEYWORDS = ("results", "earnings", "profit", "revenue", "q1 ", "q2 ", "q3 ", "q4 ", "quarterly")
_IPO_KEYWORDS = ("ipo", "listing", "public issue", "subscription", "grey market premium")
_RISK_OPPORTUNITY_KEYWORDS = ("opportunity", "risk", "warning", "caution", "downside", "upside")


def classify_headline_angle(
    article_type: str,
    headline: str,
    companies_affected: list[dict[str, Any]],
    sectors_affected: list[dict[str, Any]],
    has_historical: bool,
) -> str:
    """
    Deterministic, evidence-based classification — every branch is grounded
    in the article's own real article_type/companies/sectors/headline text,
    nothing inferred beyond what's already there. Order matters: more
    specific signals (article_type, IPO/earnings keywords) are checked
    before the more general company/sector fallbacks.
    """
    text = (headline or "").lower()
    companies = [c for c in (companies_affected or []) if c.get("symbol")]
    sectors = [s for s in (sectors_affected or []) if s.get("name")]

    if article_type == "question_intelligence":
        return "QUESTION_AEO"
    if article_type == "comparison_intelligence":
        return "COMPARISON"
    if article_type == "historical_intelligence" or (has_historical and not companies):
        return "HISTORICAL_PATTERN"
    if article_type == "educational_intelligence":
        return "DATA_STATUS"
    if any(k in text for k in _IPO_KEYWORDS):
        return "IPO"
    if any(k in text for k in _EARNINGS_KEYWORDS):
        return "EARNINGS"
    if any(k in text for k in _RISK_OPPORTUNITY_KEYWORDS):
        return "RISK_OPPORTUNITY"
    if len(companies) == 1 and article_type == "company_intelligence":
        return "COMPANY_IMPACT"
    if len(companies) >= 1 and any((c.get("impact") or "").lower() in ("positive", "negative") for c in companies):
        return "INVESTOR_IMPACT"
    if len(sectors) >= 2 and not companies:
        return "SECTOR_IMPACT"
    if companies:
        return "INVESTOR_IMPACT"
    return "BREAKING_NEWS"


# ── Keyword set — every term traceable to a real entity on the article ──────

def build_keyword_set(
    headline: str,
    companies_affected: list[dict[str, Any]],
    sectors_affected: list[dict[str, Any]],
    themes: list[str] | None = None,
) -> dict[str, list[str] | str | None]:
    companies = [c for c in (companies_affected or []) if c.get("symbol")]
    sectors = [s.get("name") for s in (sectors_affected or []) if s.get("name")]
    themes = themes or []

    primary_company = companies[0].get("name") if companies else None
    primary_sector = sectors[0] if sectors else None
    primary_keyword = (
        f"{primary_company} stock" if primary_company
        else f"{primary_sector} stocks today" if primary_sector
        else "Indian stock market today"
    )

    secondary: list[str] = []
    for c in companies[1:4]:
        name = c.get("name")
        if name:
            secondary.append(f"{name} share price")
    for s in sectors[:3]:
        secondary.append(f"{s} sector outlook")
    for t in themes[:2]:
        secondary.append(f"{t} stocks")

    entity_keywords = list(dict.fromkeys(
        [c.get("name") for c in companies if c.get("name")]
        + [c.get("symbol") for c in companies if c.get("symbol")]
        + sectors + themes
    ))

    question_keywords: list[str] = []
    if primary_company:
        question_keywords.append(f"Why is {primary_company} in the news?")
        question_keywords.append(f"Is {primary_company} a good stock to buy?")
    if primary_sector:
        question_keywords.append(f"How is the {primary_sector} sector performing today?")
    if len(companies) >= 2:
        question_keywords.append(f"{companies[0].get('name')} vs {companies[1].get('name')}: which is better?")

    return {
        "primary_keyword": primary_keyword,
        "secondary_keywords": secondary[:6],
        "entity_keywords": entity_keywords[:10],
        "question_keywords": question_keywords[:4],
    }


# ── Internal link opportunities — real routes only ───────────────────────────

def internal_link_candidates(
    companies_affected: list[dict[str, Any]],
    sectors_affected: list[dict[str, Any]],
    has_historical: bool,
    sector_link_fn,
    normalize_symbol_fn=None,
) -> list[dict[str, str]]:
    """sector_link_fn: the real per-sector URL resolver (publisher._sector_link)
    — passed in rather than imported, so this module has no dependency on
    publisher.py (publisher.py depends on this module, not the reverse).

    normalize_symbol_fn: optional app.services.symbol_normalization.normalize_symbol,
    same passed-in-not-imported pattern. Resolves malformed codes (e.g. the
    BSE numeric "BOM:500400" form) to a canonical NSE symbol via real
    name-matching, or returns None to drop the link rather than publish a
    broken /companies/BOM:500400 URL. When omitted, falls back to the bare
    upper-cased symbol (legacy behavior) for callers that haven't wired
    normalization yet."""
    links: list[dict[str, str]] = []
    for c in (companies_affected or [])[:4]:
        raw_sym = c.get("symbol") or ""
        sym = normalize_symbol_fn(raw_sym, c.get("name")) if normalize_symbol_fn else raw_sym.upper()
        if sym:
            links.append({"label": c.get("name") or sym, "href": f"/companies/{sym}", "type": "company"})
    for s in (sectors_affected or [])[:2]:
        name = s.get("name")
        if name:
            links.append({"label": f"{name} Sector", "href": sector_link_fn(name), "type": "sector"})
    if has_historical:
        links.append({"label": "Historical Patterns", "href": "/historical", "type": "historical"})
    if companies_affected and len(companies_affected) >= 2:
        links.append({"label": "Compare Companies", "href": "/compare", "type": "tool"})
    return links


def compute_seo_intelligence(
    article_type: str,
    headline: str,
    companies_affected: list[dict[str, Any]],
    sectors_affected: list[dict[str, Any]],
    themes: list[str] | None,
    has_historical: bool,
    sector_link_fn,
    normalize_symbol_fn=None,
) -> dict[str, Any]:
    angle = classify_headline_angle(article_type, headline, companies_affected, sectors_affected, has_historical)
    keywords = build_keyword_set(headline, companies_affected, sectors_affected, themes)
    links = internal_link_candidates(
        companies_affected, sectors_affected, has_historical, sector_link_fn, normalize_symbol_fn,
    )
    return {"headline_angle": angle, **keywords, "internal_link_candidates": links}
