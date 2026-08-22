"""
MarketRipple Illustration Style Guide — every generated image prompt is
built from a real subject (matched from the article's own headline/type/
sectors, same keyword approach as the frontend's gradient/icon fallback in
components/ArticleArt.tsx) plus this fixed style suffix, so the whole
platform reads as one consistent visual brand instead of a grab-bag of
AI-generated pictures.

STYLE_GUIDE_VERSION is stored on every GeneratedMedia row. Bump it when the
suffix changes — that's what makes "regenerate all images with the improved
style" a real, well-defined operation later instead of a guess.

Per-article variation (2026-08 fix, user-reported "same image is coming
for most of the articles") — confirmed live: 267 generated images across
the whole platform used only 10 distinct prompt strings (the fixed
_SUBJECT_RULES sentences below, verbatim, with no per-article detail),
and pollinations.ai returns the same/cached image for identical prompt
text with no seed. Fixed two ways: the subject sentence now folds in the
article's real sector when one exists (the generic "company" bucket was
the worst offender — any company in any sector shared one identical
sentence), and every call gets a lighting/mood variation plus a seed,
both deterministically derived from the article's own headline+id so a
regeneration of the SAME article reproduces the SAME look, but two
different articles never collide.
"""
from __future__ import annotations

import hashlib
import re

STYLE_GUIDE_VERSION = "v2"
STYLE_NAME = "editorial-navy"

STYLE_SUFFIX = (
    "Premium editorial illustration for a financial intelligence platform. "
    "Dark navy background, subtle blue and purple lighting, modern geometric "
    "composition, professional publication quality, no text, no logos, no "
    "watermarks, no photorealistic faces, no fake screenshots, clean "
    "investment magazine aesthetic, consistent visual language."
)

# Same category rules as ArticleArt.tsx, kept in sync deliberately — the
# fallback icon and the real generated image should agree on what a story
# is "about" even though only one of them is showing at a time.
_SUBJECT_RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\brbi\b|reserve bank|monetary policy|repo rate", re.I),
     "A grand government reserve bank building with classical columns"),
    (re.compile(r"\bbank(ing)?\b|nbfc|hdfc|icici|financ", re.I),
     "A modern glass banking tower skyline"),
    (re.compile(r"crude|oil|energy|opec|petroleum|gas price", re.I),
     "An offshore oil rig platform"),
    (re.compile(r"\bai\b|artificial intelligence|semiconductor|chip|technology|it services", re.I),
     "Abstract semiconductor chip circuitry with glowing data pathways"),
    (re.compile(r"defence|defense|manufactur|industrial", re.I),
     "A modern industrial manufacturing facility with geometric machinery"),
    (re.compile(r"risk|crash|sell-?off|volatil|warning", re.I),
     "A dramatic bear market scene with a descending stock chart"),
    (re.compile(r"breaking", re.I),
     "A dynamic radio broadcast tower with signal waves"),
    (re.compile(r"opportunity|theme", re.I),
     "An upward-trending financial growth chart with rising bar graphs"),
    (re.compile(r"gdp|economy|inflation|fiscal|budget", re.I),
     "A national parliament or government economic building"),
    (re.compile(r"company|earnings|quarterly|profit|revenue", re.I),
     "A modern corporate office tower with reflective glass"),
]

_DEFAULT_SUBJECT = "An abstract financial market data visualization with flowing line charts"

# Rotating scene/lighting modifiers — picked deterministically per article
# (see build_prompt), not just appended once, so the same category bucket
# stops producing one identical sentence. Kept generic/atmospheric rather
# than naming specific colors that could clash with STYLE_SUFFIX's own
# navy/blue/purple palette instruction.
_SCENE_VARIATIONS = [
    "at dusk with warm amber accents",
    "at dawn with soft cool morning light",
    "under a starlit night sky",
    "bathed in golden hour light",
    "beneath dramatic storm-lit clouds",
    "in crisp, clear midday light",
    "under soft, diffused overcast light",
    "illuminated by city lights at twilight",
    "with a sweeping wide-angle perspective",
    "from a dramatic low-angle perspective",
    "with a shallow depth of field and soft bokeh",
    "in a minimalist, high-contrast composition",
]


def _pick_subject(headline: str, article_type: str, sectors: list[str]) -> str:
    haystack = f"{headline} {article_type} {' '.join(sectors)}"
    for pattern, subject in _SUBJECT_RULES:
        if pattern.search(haystack):
            return subject
    return _DEFAULT_SUBJECT


def build_prompt(
    headline: str, article_type: str, sectors: list[str] | None = None, article_id: str | None = None,
) -> tuple[str, str, str, int]:
    """Returns (prompt, prompt_version, style_name, seed)."""
    sectors = sectors or []
    subject = _pick_subject(headline, article_type, sectors)
    # Real sector detail, not just the coarse category sentence — the
    # single biggest source of repetition was the generic "company" bucket
    # (any earnings/profit/revenue article, any sector) sharing one
    # identical sentence regardless of which real company/sector it was.
    if sectors:
        subject = f"{subject}, representing the {sectors[0]} sector"

    # Deterministic per real article identity (headline+id), not random —
    # a later regeneration of the exact same article reproduces the same
    # look, but any two different articles get a different variation/seed
    # even when they land in the same subject bucket.
    variation_key = f"{headline}|{article_id or ''}"
    digest = hashlib.sha256(variation_key.encode()).hexdigest()
    digest_int = int(digest, 16)
    scene = _SCENE_VARIATIONS[digest_int % len(_SCENE_VARIATIONS)]
    seed = digest_int % (2**31 - 1)

    prompt = f"{subject}, {scene}. {STYLE_SUFFIX}"
    return prompt, STYLE_GUIDE_VERSION, STYLE_NAME, seed
