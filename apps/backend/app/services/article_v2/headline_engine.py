"""
Article V2 Phase C5.3 — Headline Engine V2 (owner design, 2026-08-31).

Only runs after identity + uniqueness resolution (C5.1/C5.2) -- never
called for NO_PUBLICATION. The one module in the whole C1-C5 chain that
uses an LLM, but the LLM gets a closed evidence envelope: it may phrase
verified facts, it cannot discover new ones. Deterministic validation
sits after generation, same bounded-retry shape why_it_matters.py
already established (2 attempts, validation errors fed back into the
retry prompt), plus a real, always-available factual fallback headline
so a provider failure never forces fabrication:

  LLM -> numeric validation -> entity validation -> unsupported-claim
  check -> uniqueness check (within this batch) -> accept/retry/fallback

Numeric validation reuses numeric_validation.py's own
build_allowed_values()/validate_numeric_claims() verbatim -- via a
small adapter (build_allowed_values expects an ArticleEvidenceBundle-
shaped object; C5 works from C2's ArticleEvidenceSet + C3's
ArticleContextBundle, so a thin, duck-typed shim bridges the two real
shapes rather than reimplementing the validator).

Three separate output fields (h1, seo_title, social_title) per the
owner's explicit instruction -- they resolve to the same real text
today, kept as separate fields so a future phase can optimize them
independently without a schema change.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.services.ai_service import _call_with_fallback
from app.services.aipe.duplicate_detector import _jaccard, _tokenize
from app.services.article_v2.context_builder import ArticleContextBundle
from app.services.article_v2.evidence_set_builder import ArticleEvidenceSet
from app.services.article_v2.identity import ArticleIdentity
from app.services.warehouse.numeric_validation import (
    AllowedValue, build_allowed_values, extract_numeric_claims, validate_numeric_claims,
)

_MAX_ATTEMPTS = 2

# Real, observed AI-headline predictive/hype tropes -- deliberately
# narrow and conservative (the owner's own explicit examples: "set to
# soar", invented consequences), not a broad style guide.
_CLICKBAIT_DENYLIST = [
    "set to soar", "set to surge", "set to skyrocket", "game-changing", "game changer",
    "could see", "poised to", "about to", "likely to jump", "likely to soar",
    "expected to skyrocket", "must-watch", "you won't believe", "shocking", "explosive",
    "huge win", "massive win", "guaranteed", "unstoppable", "breakthrough", "will surge",
    "will soar", "on the verge of",
]

_HEADLINE_UNIQUENESS_JACCARD_THRESHOLD = 0.50  # same bar duplicate_detector.py already uses

_SYSTEM_PROMPT = (
    "You write ONE real news headline for a financial news article, based ONLY on the "
    "verified facts given to you below. You have no ability to retrieve, recall, or "
    "estimate any other information. Structure: Entity + the real development + a "
    "verified number where one is given and useful + a real, evidence-supported "
    "consequence or context — but do not force every component if the evidence doesn't "
    "support it. Every number you write must match, in the same or an equivalent format, "
    "a number given to you exactly — never invent one, never round to a different value. "
    "Never write a prediction, a market-movement forecast, or a consequence the given "
    "facts don't directly support. No clickbait, no hype words, no rhetorical questions. "
    "Respond with JSON only, no markdown fences: "
    '{"headline": "..."}'
)


class ValidationOutcome:
    OK = "OK"
    FALLBACK = "FALLBACK"
    OMITTED = "OMITTED"


@dataclass(frozen=True)
class HeadlineResult:
    h1: str | None
    seo_title: str | None
    social_title: str | None
    status: str
    attempts: int
    validation_notes: list[str] = field(default_factory=list)


class _FactShim:
    def __init__(self, metric_code: str, value: float, unit: str):
        self.metric_code = metric_code
        self.value = value
        self.unit = unit


class _FinancialContextShim:
    def __init__(self, facts: list):
        self.has_real_facts = bool(facts)
        self.facts = [_FactShim(f.metric_code, f.value, f.unit) for f in facts]


class _BundleShim:
    """Duck-typed adapter bridging C2/C3's own dataclasses to the shape
    numeric_validation.build_allowed_values() expects (an
    ArticleEvidenceBundle) -- reuses the real function verbatim rather
    than reimplementing allowed-value construction."""
    def __init__(self, context: ArticleContextBundle | None):
        self.price_move_pct = context.market_reaction.price_move_pct if context and context.market_reaction else None
        self.financial_context = _FinancialContextShim(context.financial_context) if context else None


def _format_fact_value(metric_code: str, value: float, unit: str) -> str:
    if unit == "pct":
        return f"{value * 100:.2f}%"
    if unit == "inr":
        return f"Rs {value / 1e7:,.0f} crore"
    return str(value)


def _build_prompt(
    evidence_set: ArticleEvidenceSet, context: ArticleContextBundle | None, retry_errors: list[str] | None,
) -> str:
    lines = [f"Company: {evidence_set.symbol}"]
    all_evidence = [evidence_set.primary_evidence] + list(evidence_set.supporting_evidence)
    lines.append("\nVERIFIED EVIDENCE (real, linked filings/news -- the ONLY source of facts):")
    for e in all_evidence:
        if e and e.title:
            lines.append(f"  [{e.source_type}] {e.title}")

    if context and context.financial_context:
        lines.append("\nVERIFIED FINANCIAL FACTS (quality-passed, use exactly as given if relevant):")
        for f in context.financial_context:
            lines.append(f"  {f.metric_name} = {_format_fact_value(f.metric_code, f.value, f.unit)}")

    if context and context.market_reaction:
        lines.append(f"\nREAL MARKET REACTION: {context.market_reaction.price_move_pct:+.2f}% ({context.market_reaction.note})")

    lines.append("\nWrite ONE headline. Do not use any number not shown above. No predictions, no hype.")

    if retry_errors:
        lines.append(f"\nYour previous attempt was rejected: {'; '.join(retry_errors)}. Fix this and try again.")

    return "\n".join(lines)


def _parse_response(raw: str) -> str | None:
    import json
    text = raw.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        parsed = json.loads(text)
        headline = parsed.get("headline")
        return headline.strip() if isinstance(headline, str) and headline.strip() else None
    except (json.JSONDecodeError, AttributeError):
        return None


def _check_entity_mentioned(headline: str, evidence_set: ArticleEvidenceSet) -> bool:
    """A real, positive check -- the generated headline must actually
    mention the resolved company, not drift onto an unrelated subject.
    Checked against the symbol AND the leading real word(s) of the
    primary evidence's own title (a reasonable proxy for the company
    name, since LinkedEvidence carries no separate company_name field)."""
    h = headline.lower()
    if evidence_set.symbol and evidence_set.symbol.lower() in h:
        return True
    if evidence_set.primary_evidence and evidence_set.primary_evidence.title:
        first_words = evidence_set.primary_evidence.title.split()[:3]
        name_fragment = " ".join(first_words).lower().rstrip(",.:;")
        if name_fragment and any(w in h for w in re.findall(r"[a-z0-9]+", name_fragment) if len(w) > 3):
            return True
    return False


def _check_clickbait(headline: str) -> str | None:
    h = headline.lower()
    for phrase in _CLICKBAIT_DENYLIST:
        if phrase in h:
            return phrase
    return None


def _fallback_headline(
    evidence_set: ArticleEvidenceSet, identity: ArticleIdentity, other_accepted_headlines: dict[str, str],
) -> str:
    """Real, deterministic, zero-LLM-dependency fallback -- never
    fabricates, just states the real primary evidence plainly.

    Real gap found via the C5 120-event shadow run, fixed here: when the
    LLM path is exhausted for MANY candidates in the same batch (a real,
    observed provider-capacity degradation under a 19-item burst), every
    fallback is built from the same NSE boilerplate phrasing ("has
    informed the Exchange regarding/about...") -- two genuinely
    different real companies' fallback headlines can end up looking
    confusingly similar to each other even though neither is factually
    wrong (MAHSEAMLES vs METROBRAND real AGM notices hit 0.50 Jaccard,
    right at the same-headline threshold). The LLM-path uniqueness check
    never covered this, since a fallback bypasses generation entirely.
    Disambiguated here with only real, already-verified data (the
    identity's own anchor/time bucket) -- never invented text -- when a
    real collision against a DIFFERENT identity's already-used headline
    is detected."""
    title = evidence_set.primary_evidence.title if evidence_set.primary_evidence else "development"
    symbol = evidence_set.symbol or "Company"
    short = (title or "")[:120].rstrip()
    headline = f"{symbol}: {short}"

    collides_with = next(
        (other_key for other_key, other_headline in other_accepted_headlines.items()
         if other_key != identity.identity_key and _jaccard(_tokenize(headline), _tokenize(other_headline)) >= _HEADLINE_UNIQUENESS_JACCARD_THRESHOLD),
        None,
    )
    if collides_with:
        headline = f"{headline} [{identity.time_bucket}]"
    return headline


async def generate_headline(
    evidence_set: ArticleEvidenceSet, context: ArticleContextBundle | None, identity: ArticleIdentity,
    *, other_accepted_headlines: dict[str, str],
) -> HeadlineResult:
    """`other_accepted_headlines` maps identity_key -> headline text
    already accepted earlier in this batch, so a genuinely different
    identity's headline can be checked for misleading near-duplication
    against it (never against the SAME identity, which would legitimately
    reuse similar wording)."""
    if evidence_set.primary_evidence is None:
        return HeadlineResult(h1=None, seo_title=None, social_title=None, status=ValidationOutcome.OMITTED, attempts=0)

    shim = _BundleShim(context)
    allowed = build_allowed_values(shim, [evidence_set.primary_evidence] + list(evidence_set.supporting_evidence))

    retry_notes: list[str] | None = None
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        prompt = _build_prompt(evidence_set, context, retry_notes)
        try:
            raw = await _call_with_fallback(prompt, system=_SYSTEM_PROMPT, max_tokens=120, priority="background")
        except Exception as exc:
            fallback = _fallback_headline(evidence_set, identity, other_accepted_headlines)
            return HeadlineResult(
                h1=fallback, seo_title=fallback, social_title=fallback, status=ValidationOutcome.FALLBACK,
                attempts=attempt, validation_notes=[f"generation_failed: {str(exc)[:150]}"],
            )

        headline = _parse_response(raw) if raw else None
        if not headline:
            retry_notes = ["empty or unparseable response"]
            continue

        notes: list[str] = []

        numeric_ok, numeric_errors = validate_numeric_claims(headline, allowed)
        if not numeric_ok:
            notes.append(f"unsupported number(s): {[e['raw_text'] for e in numeric_errors]}")

        entity_ok = _check_entity_mentioned(headline, evidence_set)
        if not entity_ok:
            notes.append("headline does not mention the resolved company")

        clickbait_match = _check_clickbait(headline)
        if clickbait_match:
            notes.append(f"clickbait/predictive phrase: {clickbait_match!r}")

        near_dup_of = None
        for other_key, other_headline in other_accepted_headlines.items():
            if other_key == identity.identity_key:
                continue
            if _jaccard(_tokenize(headline), _tokenize(other_headline)) >= _HEADLINE_UNIQUENESS_JACCARD_THRESHOLD:
                near_dup_of = other_key
                break
        if near_dup_of:
            notes.append(f"near-duplicate of a headline already used for a different development ({near_dup_of})")

        if not notes:
            return HeadlineResult(h1=headline, seo_title=headline, social_title=headline, status=ValidationOutcome.OK, attempts=attempt)

        retry_notes = notes

    fallback = _fallback_headline(evidence_set, identity, other_accepted_headlines)
    return HeadlineResult(
        h1=fallback, seo_title=fallback, social_title=fallback, status=ValidationOutcome.FALLBACK,
        attempts=_MAX_ATTEMPTS, validation_notes=retry_notes or [],
    )
