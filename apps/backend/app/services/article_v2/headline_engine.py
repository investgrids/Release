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

_MAX_TOPIC_LEN = 110

# C8.2 hardening (owner review, 2026-09-01): these used to cap the
# capture group itself at a raw character count ({4,110}), which can
# and did slice a real clause mid-word -- IDBI's real 500-event C7 case
# produced 'has written t' as its topic, cut off inside "to". The
# regexes now capture up to the full real clause (a much higher bound,
# just to keep pathological input bounded); the actual display-length
# cap is applied afterward by _truncate_at_word_boundary(), which never
# cuts inside a word.
#
# A second, deeper instance of the same real defect class found via
# C8's manual review of HEG's composed output: the earlier [^.]
# ("anything but a period") capture stops at the FIRST period at all --
# including an abbreviation's internal periods, not just a real
# sentence end. HEG's real primary text ("...CEO of the company
# w.e.f. September 01, 2026.") produced the topic "...of the company w"
# -- cut off right after the first letter of "w.e.f." before the length
# cap even had a chance to apply. Real Indian-filing abbreviations
# (w.e.f., Dr., Mr., Ms.) make this a real, recurring shape, not a
# one-off. Fixed by capturing through ANY character (periods included)
# up to the length bound, and letting _truncate_at_word_boundary() be
# the ONLY thing that ever shortens the result -- it cuts on real word
# boundaries, never mid-abbreviation, never mid-word.
_TOPIC_PATTERNS = [
    re.compile(r"""['"]([^'"]{6,400})['"]"""),
    re.compile(r"\babout\s+(.{4,400})", re.IGNORECASE),
    re.compile(r"\bregarding\s+(.{4,400})", re.IGNORECASE),
    re.compile(r"\bNotice of\s+(.{4,400})", re.IGNORECASE),
    re.compile(r"\bto consider\s+(.{4,400})", re.IGNORECASE),
]


def _truncate_at_word_boundary(text: str, max_len: int) -> str:
    """Never cuts mid-word -- the direct fix for IDBI's real broken
    headline ('...has written t'). Truncates at the last real word
    boundary at or before max_len and marks the truncation visibly with
    an ellipsis, rather than presenting a cut-off fragment as if it were
    complete. A single "word" longer than max_len (pathological, not
    seen in real data) is left whole rather than butchered."""
    text = text.strip()
    if len(text) <= max_len:
        return text
    cut = text.rfind(" ", 0, max_len)
    if cut <= 0:
        return text
    return text[:cut].rstrip(",.;:—-") + "…"

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
                return _truncate_at_word_boundary(_compress_topic(topic), _MAX_TOPIC_LEN)
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
        topic = _truncate_at_word_boundary(stripped, _MAX_TOPIC_LEN) or "a recent regulatory filing"

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


def _disambiguate_fallback(
    base_headline: str, evidence_set: ArticleEvidenceSet, identity: ArticleIdentity,
    other_accepted_headlines: dict[str, str],
) -> tuple[str, list[str]]:
    """Repairs a colliding fallback with real, already-verified facts --
    never an artificial suffix like a bracketed time bucket. Tries the
    development's own real numeric anchor first (adds real information,
    not just distinguishing noise), then the company's real exchange
    symbol as a last resort. If the two developments are still this
    close after both real repairs, that's an honest residual --
    reported, not hidden.

    C8.3 hardening (owner review, 2026-09-01): dropped the
    keyword-anchor-tag repair tier that used to sit here. Real 500-event
    data showed it appending the exact SAME generic text ("Annual
    General Meeting") to every company whose development collapses to
    that same generic keyword anchor -- it made a headline different
    from the ONE collision it was checked against at generation time,
    but not from the batch as a whole (SAREGAMA still collided with 3
    OTHER companies even after 2 of them had already run this same
    repair). Per explicit instruction: "don't append generic anchors" --
    a headline that still can't be distinguished with real numeric/
    symbol facts is a real signal the underlying development may belong
    in EVENT_ONLY, not something to force-distinguish with more text.
    See composer.py's finalize_batch_uniqueness() for the batch-wide
    closure this residual now feeds into."""
    if not _headline_collides(base_headline, identity, other_accepted_headlines):
        return base_headline, []

    anchor_display = _format_numeric_anchor(identity.anchor)
    if anchor_display and anchor_display not in base_headline:
        candidate = f"{base_headline} [{anchor_display}]"
        if not _headline_collides(candidate, identity, other_accepted_headlines):
            return candidate, []
        base_headline = candidate  # keep the real enrichment even if not yet sufficient

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
    "The headline's SUBJECT must be the PRIMARY DEVELOPMENT below — never a RELATED filing. "
    "Related filings may only be used to add a real corroborating detail to a headline that "
    "is already about the primary development; they must never become what the headline is "
    "ABOUT. "
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
    """C8.2 hardening (owner review, 2026-09-01): primary and supporting
    evidence used to be listed together under one flat "VERIFIED
    EVIDENCE" heading with no distinction -- a real found bug (NEWGEN's
    real 500-event C7 case) let the model draw its headline's SUBJECT
    from a supporting "Schedule of meet" filing instead of the primary
    volume-increase notice. Split into two clearly-labeled sections so
    the model can tell which evidence IS the story and which merely
    corroborates it; see the matching instruction in _SYSTEM_PROMPT and
    the post-generation _check_subject_hijack() structural backstop
    below (never trust the prompt change alone to hold)."""
    lines = [f"Company: {evidence_set.symbol}"]
    lines.append("\nPRIMARY DEVELOPMENT (the headline's subject MUST be this, and only this):")
    if evidence_set.primary_evidence and evidence_set.primary_evidence.title:
        lines.append(f"  [{evidence_set.primary_evidence.source_type}] {evidence_set.primary_evidence.title}")

    if evidence_set.supporting_evidence:
        lines.append("\nSUPPORTING CONTEXT (may corroborate a detail; must NEVER become the headline's subject):")
        for e in evidence_set.supporting_evidence:
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


# C8.2 hardening (owner review, 2026-09-01): "Headline subject may come
# from primary evidence + verified C3 context only; supporting evidence
# may corroborate but must never introduce the subject." The prompt
# restructuring above asks for this; this is the structural backstop
# that actually enforces it on the model's REAL generated text, the
# same "never trust intent, check the output" discipline every other
# validator in this module already follows. A real margin (not just
# "supporting >= primary") avoids flagging a headline that legitimately
# leans on a supporting detail without making it the subject.
_HIJACK_MARGIN = 0.05


def _check_subject_hijack(headline: str, evidence_set: ArticleEvidenceSet) -> str | None:
    """Returns the offending supporting evidence's title (truncated) if
    the headline reads as more about a SUPPORTING item than the PRIMARY
    one; None if the primary development is clearly the subject."""
    if not evidence_set.primary_evidence or not evidence_set.primary_evidence.title:
        return None
    h_tokens = _tokenize(headline)
    primary_sim = _jaccard(h_tokens, _tokenize(evidence_set.primary_evidence.title))
    best_supporting_sim = 0.0
    best_supporting_title = None
    for s in evidence_set.supporting_evidence:
        if not s.title:
            continue
        sim = _jaccard(h_tokens, _tokenize(s.title))
        if sim > best_supporting_sim:
            best_supporting_sim = sim
            best_supporting_title = s.title
    if best_supporting_sim >= primary_sim + _HIJACK_MARGIN:
        return (best_supporting_title or "")[:80]
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

        hijacked_by = _check_subject_hijack(headline, evidence_set)
        if hijacked_by:
            notes.append(f"headline subject appears to be supporting evidence, not primary ({hijacked_by!r})")

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


@dataclass(frozen=True)
class BatchUniquenessResult:
    kept: bool
    collided_with: str | None = None


def finalize_batch_uniqueness(
    ordered_candidates: list[tuple[ArticleIdentity, str]],
) -> dict[str, BatchUniquenessResult]:
    """C8.3 hardening (owner review, 2026-09-01): "Before accepting the
    complete publication set, every different ArticleIdentity must have
    a headline below the near-duplicate threshold against every OTHER
    accepted identity." The per-item disambiguation in
    generate_headline() only ever checks a new headline against
    headlines already accepted EARLIER in the batch -- real 500-event
    data showed that's not the same guarantee: SAREGAMA's headline was
    accepted first, then three LATER companies (SANDESH/PPAP/JINDRILL)
    each independently collided against it, and even after each one's
    own real-fact repairs ran, several residuals remained >=0.50
    Jaccard. This is a real, final, exhaustive pass over the WHOLE
    accepted ARTICLE-tier set -- run once, after every ARTICLE-tier
    candidate in a batch has a real headline, and BEFORE any of them are
    composed.

    `ordered_candidates` must be (identity, headline) pairs for
    ARTICLE-tier candidates ONLY, in real processing order -- EVENT_ONLY/
    REJECT candidates never reach here since they never get a headline
    at all (see composer.py's finalize_batch_uniqueness call site /
    scripts/article_v2_c8_shadow_run.py). First-seen-in-batch wins, same
    convention identity.py's own resolve_uniqueness() already
    established; a later collision does NOT get a forced suffix or a
    generic anchor tag -- per explicit instruction, an unresolved
    collision is itself a real signal the colliding development(s)
    likely belong in EVENT_ONLY, not something to paper over with more
    text. The caller is responsible for actually downgrading the tier
    for any `kept=False` result."""
    accepted: list[tuple[str, str]] = []
    result: dict[str, BatchUniquenessResult] = {}
    for identity, headline in ordered_candidates:
        if not headline:
            result[identity.identity_key] = BatchUniquenessResult(kept=False, collided_with=None)
            continue
        collision = next(
            (other_key for other_key, other_headline in accepted
             if _jaccard(_tokenize(headline), _tokenize(other_headline)) >= _HEADLINE_UNIQUENESS_JACCARD_THRESHOLD),
            None,
        )
        if collision:
            result[identity.identity_key] = BatchUniquenessResult(kept=False, collided_with=collision)
        else:
            accepted.append((identity.identity_key, headline))
            result[identity.identity_key] = BatchUniquenessResult(kept=True)
    return result
