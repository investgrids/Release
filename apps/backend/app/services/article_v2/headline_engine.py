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
from app.services.article_v2.company_name import resolve_company_name
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

# C5.1 hardening (owner review, 2026-09-01): the deterministic fallback
# used to be `f"{symbol}: {evidence_title[:120]}"` -- a truncated copy of
# the raw NSE filing text, boilerplate ("has informed the Exchange
# regarding/about...") and all. Two real problems, both found via the
# live 19-candidate shadow run: (1) it read like a scraped exchange
# notice, not a headline; (2) because every NSE filing shares the same
# boilerplate phrasing, two DIFFERENT real companies' fallback headlines
# could be dominated by identical boilerplate tokens and read as
# misleadingly similar (FIRSTCRY vs BLS at 0.53 Jaccard, OIL vs
# AXISCADES at 0.57 -- both above this module's own uniqueness bar).
# Appending a `[time_bucket]` tag helped a little but didn't fix the
# actual cause and produced an ugly, artificial-looking headline.
#
# Fixed by composing the fallback from the REAL substantive clause the
# filing is actually about -- extracted from the evidence's own text via
# pattern matching (quoted sub-headline, "about X", "regarding X", "to
# consider X", "Notice of X" -- tried in that order because a quoted
# clause or "about/regarding" almost always carries the fullest real
# content) -- with the boilerplate phrase itself stripped out entirely,
# never included in the output.
# Used only to strip the boilerplate lead-in when building the topic
# fallback below (a different job from company-name resolution, which
# now lives in company_name.py's shared resolve_company_name()).
_BOILERPLATE_STRIP_RE = re.compile(
    r"^(.*?)\s+(?:has (?:informed|submitted to)|informs)\s+(?:the exchange|bse|nse)", re.IGNORECASE,
)

_TOPIC_PATTERNS = [
    re.compile(r"""['"]([^'"]{6,110})['"]"""),
    re.compile(r"\babout\s+([^.]{4,110})", re.IGNORECASE),
    re.compile(r"\bregarding\s+([^.]{4,110})", re.IGNORECASE),
    re.compile(r"\bNotice of\s+([^.]{4,110})", re.IGNORECASE),
    re.compile(r"\bto consider\s+([^.]{4,110})", re.IGNORECASE),
]

_DATE_DMY_RE = re.compile(r"\b(\d{1,2})[-\s]([A-Za-z]{3,9})[-\s]?(\d{4})\b")
_DATE_MDY_RE = re.compile(r"\b([A-Za-z]{3,9})\s+(\d{1,2}),?\s+(\d{4})\b")
_MONTHS = {
    "jan": "January", "feb": "February", "mar": "March", "apr": "April", "may": "May", "jun": "June",
    "jul": "July", "aug": "August", "sep": "September", "sept": "September", "oct": "October",
    "nov": "November", "dec": "December",
}


def _extract_company_name(evidence_set: ArticleEvidenceSet) -> str:
    """Prefers the real, resolver-verified canonical name
    (evidence_set.company_name) over re-extracting one from filing
    prose -- see company_name.py's own module docstring for the full
    rationale (this shared implementation replaced two independently
    drifting per-module regexes, C6.1 hardening, 2026-09-01)."""
    return resolve_company_name(
        verified_company_name=evidence_set.company_name,
        primary_evidence_title=evidence_set.primary_evidence.title if evidence_set.primary_evidence else None,
        symbol=evidence_set.symbol,
    )


# Compresses the two most common templated NSE clause shapes -- shorter,
# more headline-like, AND directly reduces the shared-boilerplate token
# mass that was causing genuinely different companies' AGM/board-meeting
# fallback headlines to read as near-duplicates (real, observed:
# MAHSEAMLES vs METROBRAND at 0.50+ Jaccard on the uncompressed clause).
_TOPIC_COMPRESSIONS = [
    (re.compile(r"Notice of Annual General Meeting to be held on\s*", re.IGNORECASE), "AGM on "),
    (re.compile(r"Board Meeting to be held on\s*", re.IGNORECASE), "board meeting on "),
]

# A "to consider Other business" tail carries zero real distinguishing
# content -- real, found via the shadow run: ATALREAL and DPWIRES are two
# genuinely different real companies whose board-meeting notices differ
# ONLY by name and date once this generic filler is included, pushing
# Jaccard to 0.57+. Dropped only when the purpose is EXACTLY this known
# filler phrase -- a real, specific purpose (MOLDTECH's "approve Bonus/
# Dividend/Other business") is left untouched, since that IS genuine
# distinguishing content.
_GENERIC_PURPOSE_TAIL_RE = re.compile(
    r"\s+to consider\s+(?:other business|general business|any other business|other matters)\.?\s*$",
    re.IGNORECASE,
)


def _compress_topic(topic: str) -> str:
    for pat, repl in _TOPIC_COMPRESSIONS:
        topic = pat.sub(repl, topic)
    topic = _GENERIC_PURPOSE_TAIL_RE.sub("", topic).rstrip()
    return topic


def _extract_topic(text: str) -> str | None:
    for pat in _TOPIC_PATTERNS:
        m = pat.search(text)
        if m:
            topic = m.group(1).strip().strip("'\"").rstrip(",.;")
            if topic:
                return _compress_topic(topic)
    return None


def _extract_real_date(text: str) -> str | None:
    m = _DATE_DMY_RE.search(text)
    if m:
        day, mon_raw, _year = m.groups()
        mon = _MONTHS.get(mon_raw[:3].lower())
        if mon:
            return f"{mon} {int(day)}"
    m = _DATE_MDY_RE.search(text)
    if m:
        mon_raw, day, _year = m.groups()
        mon = _MONTHS.get(mon_raw[:3].lower())
        if mon:
            return f"{mon} {int(day)}"
    return None


def _format_numeric_anchor(anchor: str) -> str | None:
    """Turns identity.py's internal anchor repr (e.g.
    'currency_inr:8000000000.0') back into a real, human-readable figure
    -- reusing the same value the identity was built from, never a new
    number."""
    if not anchor.startswith("currency_"):
        return None
    try:
        kind, raw_value = anchor.split(":", 1)
        value = float(raw_value)
    except ValueError:
        return None
    if kind == "currency_inr" and value >= 1e7:
        return f"Rs {value / 1e7:,.0f} crore"
    if kind == "currency_usd" and value >= 1e6:
        return f"${value / 1e6:,.1f} million"
    return None


def _build_deterministic_headline(evidence_set: ArticleEvidenceSet, identity: ArticleIdentity) -> str:
    """A real, boilerplate-free headline built entirely from the
    evidence's own text -- never the raw, truncated NSE announcement.

    Topic/date extraction is scoped to the PRIMARY evidence's own title
    only, never supporting evidence -- a real bug found via the C5.1
    shadow rerun: BLS's genuinely distinct "Web Link Letter" development
    legitimately carries its company's separate BRSR filing as
    SUPPORTING context (a real, correctly-included C2 fact), but
    extracting from primary+supporting concatenated text let the quoted-
    clause pattern match the supporting item's BRSR quote instead of the
    primary evidence's own "Web Link Letter" subject -- producing an
    identical headline for two genuinely different real developments."""
    primary_title = evidence_set.primary_evidence.title if evidence_set.primary_evidence else ""
    company = _extract_company_name(evidence_set)

    topic = _extract_topic(primary_title)
    if not topic:
        stripped = _BOILERPLATE_STRIP_RE.sub("", primary_title or "", count=1)
        stripped = re.sub(r"^\s*(regarding|about)\s*", "", stripped, flags=re.IGNORECASE).strip()
        topic = (stripped[:140].rstrip() or "a recent regulatory filing")

    headline = f"{company} — {topic}"
    if not re.search(r"\d{4}", topic):  # topic doesn't already carry a real date
        date = _extract_real_date(primary_title)
        if date:
            headline = f"{headline} ({date})"
    return headline[:200].rstrip()


def _headline_collides(headline: str, identity: ArticleIdentity, other_accepted_headlines: dict[str, str]) -> bool:
    return any(
        other_key != identity.identity_key
        and _jaccard(_tokenize(headline), _tokenize(other_headline)) >= _HEADLINE_UNIQUENESS_JACCARD_THRESHOLD
        for other_key, other_headline in other_accepted_headlines.items()
    )


def _anchor_topic_tag(identity: ArticleIdentity) -> str | None:
    """Turns a keyword-anchor identity (e.g.
    'topic:web-link-letter') back into a short, real, human-readable
    tag -- the actual substance that makes THIS identity different from
    any other, not an arbitrary label. Two different identity_keys are
    guaranteed to differ in development_type, anchor, or time_bucket by
    construction; when the anchor itself is what differs, this is the
    one piece of real, already-computed distinguishing content that's
    guaranteed non-redundant."""
    if not identity.anchor.startswith("topic:"):
        return None
    words = [w for w in identity.anchor[len("topic:"):].split("-") if w][-3:]
    return " ".join(w.capitalize() for w in words) if words else None


def _disambiguate_fallback(
    base_headline: str, evidence_set: ArticleEvidenceSet, identity: ArticleIdentity,
    other_accepted_headlines: dict[str, str],
) -> tuple[str, list[str]]:
    """Repairs a colliding fallback with real, already-verified facts --
    never an artificial suffix like a bracketed time bucket. Tries the
    development's own real numeric anchor first (adds real information,
    not just distinguishing noise), then the identity's own real anchor
    topic tag, then the company's real exchange symbol as a last resort
    (redundant when the symbol already appears inside the company name,
    which the earlier two steps normally make unnecessary). If the two
    developments are still this close after all real repairs, that's an
    honest residual -- reported, not hidden."""
    if not _headline_collides(base_headline, identity, other_accepted_headlines):
        return base_headline, []

    anchor_display = _format_numeric_anchor(identity.anchor)
    if anchor_display and anchor_display not in base_headline:
        candidate = f"{base_headline} [{anchor_display}]"
        if not _headline_collides(candidate, identity, other_accepted_headlines):
            return candidate, []
        base_headline = candidate  # keep the real enrichment even if not yet sufficient

    anchor_tag = _anchor_topic_tag(identity)
    if anchor_tag and anchor_tag.lower() not in base_headline.lower():
        candidate = f"{base_headline} — re: {anchor_tag}"
        if not _headline_collides(candidate, identity, other_accepted_headlines):
            return candidate, []
        base_headline = candidate

    if evidence_set.symbol and f"({evidence_set.symbol})" not in base_headline:
        candidate = f"{base_headline} ({evidence_set.symbol})"
        if not _headline_collides(candidate, identity, other_accepted_headlines):
            return candidate, []
        base_headline = candidate

    return base_headline, [
        "residual near-duplicate of another headline in this batch after disambiguation with real "
        "anchor/symbol facts -- flagged for manual review, not silently accepted as unique",
    ]

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
            base = _build_deterministic_headline(evidence_set, identity)
            fallback, dedup_notes = _disambiguate_fallback(base, evidence_set, identity, other_accepted_headlines)
            return HeadlineResult(
                h1=fallback, seo_title=fallback, social_title=fallback, status=ValidationOutcome.FALLBACK,
                attempts=attempt, validation_notes=[f"generation_failed: {str(exc)[:150]}", *dedup_notes],
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

    base = _build_deterministic_headline(evidence_set, identity)
    fallback, dedup_notes = _disambiguate_fallback(base, evidence_set, identity, other_accepted_headlines)
    return HeadlineResult(
        h1=fallback, seo_title=fallback, social_title=fallback, status=ValidationOutcome.FALLBACK,
        attempts=_MAX_ATTEMPTS, validation_notes=(retry_notes or []) + dedup_notes,
    )
