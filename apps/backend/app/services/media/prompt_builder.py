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
"""
from __future__ import annotations

import re

STYLE_GUIDE_VERSION = "v1"
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
     "A modern glass banking tower skyline at dusk"),
    (re.compile(r"crude|oil|energy|opec|petroleum|gas price", re.I),
     "An offshore oil rig platform illuminated at night"),
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


def _pick_subject(headline: str, article_type: str, sectors: list[str]) -> str:
    haystack = f"{headline} {article_type} {' '.join(sectors)}"
    for pattern, subject in _SUBJECT_RULES:
        if pattern.search(haystack):
            return subject
    return _DEFAULT_SUBJECT


def build_prompt(headline: str, article_type: str, sectors: list[str] | None = None) -> tuple[str, str, str]:
    """Returns (prompt, prompt_version, style_name)."""
    subject = _pick_subject(headline, article_type, sectors or [])
    prompt = f"{subject}. {STYLE_SUFFIX}"
    return prompt, STYLE_GUIDE_VERSION, STYLE_NAME
