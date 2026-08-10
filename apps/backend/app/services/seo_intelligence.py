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

# ── Headline angle classification ────────────────────────────────────────────
# Mirrors the vocabulary from content_planner.py's own question templates
# (Positive/Negative/Neutral) and _COMPANY_KW/_THEME_KW keyword lists,
# reused rather than re-invented, but answers a different question: not
# "which article_type template" but "which real-world search angle does
# this article's own content actually support."
HEADLINE_ANGLES = ("news", "question", "investor", "sector", "comparison", "explanation", "historical")


def classify_headline_angle(
    article_type: str,
    companies_affected: list[dict[str, Any]],
    sectors_affected: list[dict[str, Any]],
    has_historical: bool,
) -> str:
    companies = [c for c in (companies_affected or []) if c.get("symbol")]
    sectors = [s for s in (sectors_affected or []) if s.get("name")]

    if article_type == "question_intelligence":
        return "question"
    if article_type == "comparison_intelligence":
        return "comparison"
    if article_type in ("educational_intelligence",):
        return "explanation"
    if article_type == "historical_intelligence" or (has_historical and not companies):
        return "historical"
    if len(companies) == 1 and any((c.get("impact") or "").lower() in ("positive", "negative") for c in companies):
        return "investor"
    if len(sectors) >= 2 and not companies:
        return "sector"
    if companies:
        return "news"
    return "news"


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
) -> list[dict[str, str]]:
    """sector_link_fn: the real per-sector URL resolver (publisher._sector_link)
    — passed in rather than imported, so this module has no dependency on
    publisher.py (publisher.py depends on this module, not the reverse)."""
    links: list[dict[str, str]] = []
    for c in (companies_affected or [])[:4]:
        sym = (c.get("symbol") or "").upper()
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
) -> dict[str, Any]:
    angle = classify_headline_angle(article_type, companies_affected, sectors_affected, has_historical)
    keywords = build_keyword_set(headline, companies_affected, sectors_affected, themes)
    links = internal_link_candidates(companies_affected, sectors_affected, has_historical, sector_link_fn)
    return {"headline_angle": angle, **keywords, "internal_link_candidates": links}
