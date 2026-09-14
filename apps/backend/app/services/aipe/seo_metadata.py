"""
Shared article SEO metadata builder (Article V2-F1 Data Contract
Completion, 2026-09-14).

Extracted from the JSON-LD block that used to live only inline inside
`aipe/publisher.py::_publish_new_article()` -- the real production V1
article path. Before this module existed, V2 had neither that logic nor
an equivalent of its own: `article_v2/publication_translator.py` never
set `canonical_url`/`json_ld` at all, so a real V2 article would render
with no `<script type="application/ld+json">` tag whatsoever (a real,
silent SEO/AEO/GEO gap for the one article that most needs to prove the
product). Rather than write a second, independent implementation for
V2, both V1's main article path and V2's P1 translator now call this
one function -- "don't make a fourth implementation" (V1 already has
three ad hoc inline copies across publisher.py/signal_publisher.py/
comparison_publisher.py; this is the first attempt at a shared one, not
a fourth).

Scope of this extraction, deliberately bounded: only `_publish_new_
article()` (V1's main, highest-volume article path) was migrated to
call this shared builder in this patch, proven equivalent by a
byte-for-byte regression test. `publisher.py`'s OWN scheduled/historical
article path and `signal_publisher.py`/`comparison_publisher.py`'s
independent inline JSON-LD blocks were deliberately NOT touched here --
each has its own smaller shape differences (no breadcrumb, a different
default `@type`) that would need their own careful equivalence proof,
not bundled into this pass. A real, separate, smaller follow-up item,
not silently forgotten.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from app.core.config import settings

_EVERGREEN_ARTICLE_TYPES = ("educational_intelligence", "comparison_intelligence", "historical_intelligence")


def build_canonical_url(slug: str) -> str:
    """The one real production domain (see config.py's own docstring on
    `frontend_url` for the incident this guards against) plus the FINAL,
    non-redirecting article path -- `/insights/:slug` 301-redirects to
    this same path (see next.config.ts's "AI Newsroom consolidation"
    redirects), so canonical URLs must never point at the redirecting
    one."""
    site_url = (settings.frontend_url or "https://www.marketripple.in").rstrip("/")
    return f"{site_url}/newsroom/article/{slug}"


@dataclass(frozen=True)
class ArticleJsonLdInput:
    headline: str
    slug: str
    article_type: str
    meta_description: str | None
    published_at: datetime
    updated_at: datetime | None = None
    faqs: list[dict] = field(default_factory=list)


def build_article_json_ld(inp: ArticleJsonLdInput) -> dict:
    """Article/NewsArticle (+FAQPage if faqs present) -- byte-for-byte
    the same shape `_publish_new_article()` built inline before this
    module existed (see its own regression test). NewsArticle is
    Google's own distinction for timely reporting on a current event vs.
    general content -- the same line this app already draws for the
    Google News sitemap; the three genuinely evergreen types are the
    exception."""
    site_url = (settings.frontend_url or "https://www.marketripple.in").rstrip("/")
    article_path = f"/newsroom/article/{inp.slug}"
    schema_type = "Article" if inp.article_type in _EVERGREEN_ARTICLE_TYPES else "NewsArticle"
    updated_at = inp.updated_at or inp.published_at

    json_ld: dict = {
        "@context": "https://schema.org",
        "@type": schema_type,
        "headline": inp.headline,
        "description": inp.meta_description or "",
        "datePublished": inp.published_at.isoformat(),
        "dateModified": updated_at.isoformat(),
        "author": {"@type": "Organization", "name": "MarketRipple AI Intelligence Engine"},
        "publisher": {"@type": "Organization", "name": "MarketRipple"},
        "mainEntityOfPage": f"{site_url}{article_path}",
        "breadcrumb": {
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "MarketRipple", "item": site_url},
                {"@type": "ListItem", "position": 2, "name": "Newsroom", "item": f"{site_url}/newsroom"},
                {"@type": "ListItem", "position": 3, "name": inp.headline, "item": f"{site_url}{article_path}"},
            ],
        },
    }
    if inp.faqs:
        json_ld["@type"] = [schema_type, "FAQPage"]
        json_ld["mainEntity"] = [
            {
                "@type": "Question",
                "name": f.get("question", ""),
                "acceptedAnswer": {"@type": "Answer", "text": f.get("answer", "")},
            }
            for f in inp.faqs[:5]
        ]
    return json_ld
