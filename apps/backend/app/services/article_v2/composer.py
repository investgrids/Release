"""
Article V2 Phase C6 — Grounded Composer (owner design, 2026-09-01).

This is where user-facing prose finally gets written. It is deliberately
NOT where any new analytical decision gets made — the owner's own
framing: "Take the already-approved C4 decision, C2 evidence set, C3
context and C5 identity/headline envelope, and express only those
verified facts clearly." C6 never searches for additional evidence,
never selects a new FinancialFact, never reinterprets C4's content_type/
publication_action, and never decides an event is more important than
the upstream pipeline already determined. If a real fact was excluded
by C2, filtered by C3, or never made it into C2's supporting_evidence,
this module structurally cannot see it — it only ever reads
`evidence_set.primary_evidence`/`.supporting_evidence` and
`context.financial_context`/`.market_reaction`, never `.excluded_evidence`
and never queries FinancialFact/read_service directly.

## Two different compositions, not one template forced onto both

FACTUAL_UPDATE stays concise: What Happened -> Key Details (only the
material verified facts actually available) -> Source/Updated. No LLM
call at all — every FACTUAL_UPDATE is fully deterministic, code-composed
from already-verified structured fields, mirroring the same pattern
`article_evidence_bundle.py::compose_what_happened_from_evidence`
already established and this codebase already praised. A 120-word
factual update with nothing invented is better than a padded one.

FULL_ARTICLE allows: What Happened -> Why It Matters -> Verified Context
-> What to Watch, in that order (the owner's own explicit ordering).
Every section is conditional — no evidence/context for a section means
that section is simply absent, never a padded placeholder.

## Claim-level provenance

Every section is built FROM a list of ComposedClaim objects, and the
section's rendered `text` is derived from those claims' own text (for
the deterministic sections, by direct concatenation — there is no
separate step where prose could drift from the claims that justify it).
For Why It Matters, the one LLM-generated section, the model itself
returns a structured `claims` list alongside its prose (the exact same
established pattern `why_it_matters.py` uses) — this doesn't guarantee
the prose and claims are byte-identical, but it is the same provenance
discipline already accepted for Phase B, extended here with a stricter
interpretation boundary (see below). Nothing downstream should ever
render `ComposedArticle` prose without also being able to show its
`all_claims` list — that IS the anti-"destroy the provenance graph"
contract.

## Numeric boundary

Reuses `numeric_validation.py`'s `build_allowed_values()`/
`validate_numeric_claims()` verbatim (via a thin duck-typed shim
bridging C2/C3's dataclasses to the shape those functions expect — the
same shim pattern `headline_engine.py` already established, kept local
to this module rather than shared, matching that same precedent) for
the one LLM-generated section. Every number the LLM writes — rupee
amounts, percentages, ratios — must trace to a real number already in
the closed evidence/context envelope, or the whole "why_it_matters"
text is rejected outright and the section is dropped, never silently
corrected.

## Interpretation boundary — temporal, not causal; explanatory, not
## predictive

The owner's own contrast, verbatim: "A fundraising proposal matters
because additional capital can strengthen the bank's capital position"
is acceptable when grounded in real capital-ratio context; "The
fundraising will accelerate loan growth and boost profitability" is
not, merely because a capital ratio number exists. "Shares rose 4.8%
after the announcement" describes real temporal sequence (C3 already
establishes the window); "Investors welcomed the acquisition, sending
shares up 4.8%" invents causality and investor intent neither C2 nor C3
ever established. Two small, deliberately narrow denylists
(`_CAUSAL_INTENT_DENYLIST`, `_PREDICTIVE_DENYLIST`) enforce this on the
model's ACTUAL generated text, the same "never trust the model's own
self-report" discipline `numeric_validation.py` already established for
numbers — checked here for language instead.

## Deterministic fallback

FACTUAL_UPDATE never touches an LLM, so provider failure is a non-issue
for it by construction. For FULL_ARTICLE, if Why It Matters fails to
generate or fails validation after the bounded retry, the section is
simply omitted — the composition degrades to a real, grounded article
built from What Happened + Verified Context + What to Watch (What
Happened, at minimum, is always present), never an empty page and never
fabricated analysis pretending to exist.

## What C6 explicitly refuses to compose

A C4 `SKIP` or a C5 `NO_PUBLICATION` can never reach this module's
output — `compose_article()` raises `ComposerRefusal` immediately for
either, rather than silently returning something. This is a hard
invariant, not a best-effort check.

## What C6 deliberately does NOT solve

If manual inspection of the shadow run finds a AGM/BRSR/Web-Link-Letter
FACTUAL_UPDATE that is perfectly grounded but still not useful to a
reader, that is an editorial-selection question for C4's publication
policy, not a C6 composer defect — explicitly deferred to a future C7
full-funnel review, per the owner's own instruction not to contaminate
headline/composition engineering with editorial-policy changes.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

import structlog

from app.services.ai_service import _call_with_fallback
from app.services.article_v2.company_name import resolve_company_name
from app.services.article_v2.context_builder import ArticleContextBundle
from app.services.article_v2.decision_engine import FACTUAL_UPDATE, FULL_ARTICLE, _has_numeric_substance
from app.services.article_v2.decision_engine import SKIP as C4_SKIP
from app.services.article_v2.decision_engine import ArticleDecision
from app.services.article_v2.evidence_set_builder import ArticleEvidenceSet
from app.services.article_v2.headline_engine import HeadlineResult
from app.services.article_v2.identity import NO_PUBLICATION, ArticleIdentity, PublicationResolution
from app.services.warehouse.numeric_validation import build_allowed_values, validate_numeric_claims

log = structlog.get_logger(__name__)

_MAX_ATTEMPTS = 2

_SOURCE_LABELS = {
    "nse": "an NSE regulatory filing", "rss": "a published news report", "rbi": "an RBI release",
    "pib": "a PIB release", "sebi": "a SEBI release", "fed": "a US Federal Reserve release",
}

# A real, already-scheduled future date attached to THIS development --
# never a market prediction. Deliberately narrow: only fires when the
# primary evidence itself names a real upcoming date tied to one of
# these real NSE-filing phrasings.
_SCHEDULED_DATE_MARKERS = ["to be held on", "scheduled for", "record date", "cut-off date", "cut off date"]

_DATE_DMY_RE = re.compile(r"\b(\d{1,2})[-\s]([A-Za-z]{3,9})[-\s]?(\d{4})\b")
_DATE_MDY_RE = re.compile(r"\b([A-Za-z]{3,9})\s+(\d{1,2}),?\s+(\d{4})\b")
_MONTHS = {
    "jan": "January", "feb": "February", "mar": "March", "apr": "April", "may": "May", "jun": "June",
    "jul": "July", "aug": "August", "sep": "September", "sept": "September", "oct": "October",
    "nov": "November", "dec": "December",
}

# Real, observed causal/intent language the owner's own example named
# directly ("Investors welcomed... sending shares up") -- deliberately
# narrow and conservative, matching the same denylist discipline
# headline_engine.py's clickbait check already established, not a broad
# style guide.
_CAUSAL_INTENT_DENYLIST = [
    "investors welcomed", "investors cheered", "sending shares", "sent shares",
    "boosted investor confidence", "driving shares", "causing shares", "triggered a rally",
    "fueled a rally", "in response to the", "reacting to the news", "prompting investors",
    "sparked a rally", "spurred investors", "investors reacted",
]
_PREDICTIVE_DENYLIST = [
    "is expected to", "is likely to", "will likely", "is set to", "is poised to",
    "is projected to", "will boost", "will accelerate", "is forecast to", "is anticipated to",
    "will drive", "will strengthen",
]

_WHY_IT_MATTERS_SYSTEM_PROMPT = (
    "You write the \"Why It Matters\" section of a real financial news article. "
    "You may ONLY use the facts given to you below -- you cannot retrieve, recall, or "
    "estimate anything else. Every number you write must match, in the same or an "
    "equivalent format, a number given to you exactly -- never invent or convert one. "
    "You may explain why a verified fact matters (for example, why a capital ratio is "
    "relevant to a fundraising decision) using only reasoning the given facts directly "
    "support. If a price move is given, state it only as a fact that occurred on the "
    "same day as the development -- NEVER as something the development caused, and "
    "NEVER attribute intent, sentiment, or a reaction to investors (no \"investors "
    "welcomed\", no \"sending shares up\", no \"in response to\"). Never predict a "
    "future outcome (no \"is expected to\", no \"will boost\", no \"is set to\"). If the "
    "given facts are too thin to say anything substantive, write a short, honest "
    "paragraph acknowledging that rather than filling the gap.\n\n"
    "Respond with JSON only, no markdown fences:\n"
    '{"why_it_matters": "1-3 sentence paragraph", "claims": '
    '[{"text": "...", "type": "FACT"|"INTERPRETATION", "evidence_refs": '
    '["EVIDENCE:<id8>" or "FACT:<metric_code>", ...]}]}'
)


class ComposerRefusal(ValueError):
    """Raised when C6 is asked to compose something it must never
    compose -- a C4 SKIP or a C5 NO_PUBLICATION. A hard invariant, not a
    best-effort check."""


@dataclass(frozen=True)
class ComposedClaim:
    text: str
    claim_type: str  # "FACT" | "INTERPRETATION"
    evidence_ids: list[str] = field(default_factory=list)
    financial_fact_ids: list[str] = field(default_factory=list)
    validation_status: str = "VERIFIED"  # "VERIFIED" | "REJECTED" -- reserved for a future per-claim re-check


@dataclass(frozen=True)
class ComposedSection:
    name: str
    text: str
    claims: list[ComposedClaim] = field(default_factory=list)


@dataclass(frozen=True)
class ComposedArticle:
    content_type: str
    headline: str
    sections: list[ComposedSection]
    all_claims: list[ComposedClaim]
    llm_status: str  # "not_used" | "ok" | "omitted_generation_failed" | "omitted_validation_failed" | "omitted_no_context"
    llm_attempts: int
    word_count: int
    llm_validation_notes: list[str] = field(default_factory=list)  # the last rejection's reasons, for observability
    depth_gate_downgraded: bool = False  # C8.4 -- True when C4's FULL_ARTICLE was composed as FACTUAL_UPDATE instead


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
    """Same duck-typed adapter pattern headline_engine.py already
    established, kept local to this module rather than shared."""
    def __init__(self, context: ArticleContextBundle | None):
        self.price_move_pct = context.market_reaction.price_move_pct if context and context.market_reaction else None
        self.financial_context = _FinancialContextShim(context.financial_context) if context else None


def _company_name(evidence_set: ArticleEvidenceSet) -> str:
    return resolve_company_name(
        verified_company_name=evidence_set.company_name,
        primary_evidence_title=evidence_set.primary_evidence.title if evidence_set.primary_evidence else None,
        symbol=evidence_set.symbol,
    )


def _format_value(value: float, unit: str) -> str:
    if unit == "pct":
        return f"{value * 100:.2f}%"
    if unit == "inr":
        return f"Rs {value / 1e7:,.0f} crore"
    return str(value)


def _extract_scheduled_date(text: str) -> str | None:
    m = _DATE_DMY_RE.search(text)
    if m:
        day, mon_raw, year = m.groups()
        mon = _MONTHS.get(mon_raw[:3].lower())
        if mon:
            return f"{mon} {int(day)}, {year}"
    m = _DATE_MDY_RE.search(text)
    if m:
        mon_raw, day, year = m.groups()
        mon = _MONTHS.get(mon_raw[:3].lower())
        if mon:
            return f"{mon} {int(day)}, {year}"
    return None


def _check_causal_or_predictive(text: str) -> str | None:
    t = text.lower()
    for phrase in _CAUSAL_INTENT_DENYLIST + _PREDICTIVE_DENYLIST:
        if phrase in t:
            return phrase
    return None


def _parse_json_response(raw: str) -> dict | None:
    text = raw.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", text)
        if not m:
            return None
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            return None


# ── Deterministic sections (no LLM, ever) ───────────────────────────────

def _compose_what_happened(evidence_set: ArticleEvidenceSet) -> ComposedSection:
    primary = evidence_set.primary_evidence
    date_str = primary.published_at.strftime("%d %B %Y") if primary.published_at else "an unspecified date"
    source_label = _SOURCE_LABELS.get(primary.source_type, f"a {primary.source_type} source")
    company = _company_name(evidence_set)
    text = f'On {date_str}, {company} was the subject of {source_label}: "{primary.title}"'
    claim = ComposedClaim(text=text, claim_type="FACT", evidence_ids=[primary.raw_evidence_id])
    return ComposedSection(name="what_happened", text=text, claims=[claim])


def _compose_context_section(
    evidence_set: ArticleEvidenceSet, context: ArticleContextBundle | None, *, name: str,
) -> ComposedSection | None:
    """Shared by FACTUAL_UPDATE's "Key Details" and FULL_ARTICLE's
    "Verified Context" -- same real underlying facts (C2 supporting
    evidence + C3 financial context + C3 market reaction), just a
    different section label depending on content_type. Only ever reads
    the ACCEPTED lists -- never evidence_set.excluded_evidence, never
    queries FinancialFact directly."""
    claims: list[ComposedClaim] = []
    for s in evidence_set.supporting_evidence:
        if s.title:
            claims.append(ComposedClaim(
                text=f'Related filing: "{s.title}"', claim_type="FACT", evidence_ids=[s.raw_evidence_id],
            ))
    if context:
        for f in context.financial_context:
            period = f"FY{f.fiscal_year}" + (f" Q{f.fiscal_quarter}" if f.fiscal_quarter else "")
            text = f"{f.metric_name}: {_format_value(f.value, f.unit)} (as of {period})"
            if f.prior_period_value is not None and f.prior_period_label:
                text += f", versus {_format_value(f.prior_period_value, f.unit)} in {f.prior_period_label}"
            claims.append(ComposedClaim(text=text, claim_type="FACT", financial_fact_ids=[f.metric_code]))
        if context.market_reaction:
            mr = context.market_reaction
            direction = "gained" if mr.price_move_pct >= 0 else "declined"
            text = f"{evidence_set.symbol} shares {direction} {abs(mr.price_move_pct):.2f}% on the day this was reported ({mr.note})"
            claims.append(ComposedClaim(text=text, claim_type="FACT"))
    if not claims:
        return None
    text = " ".join(c.text for c in claims)
    return ComposedSection(name=name, text=text, claims=claims)


def _compose_what_to_watch(evidence_set: ArticleEvidenceSet) -> ComposedSection | None:
    primary = evidence_set.primary_evidence
    title = primary.title or ""
    if not any(marker in title.lower() for marker in _SCHEDULED_DATE_MARKERS):
        return None
    date = _extract_scheduled_date(title)
    if not date:
        return None
    company = _company_name(evidence_set)
    text = f"{company} has a real, already-scheduled date of {date} related to this development."
    claim = ComposedClaim(text=text, claim_type="FACT", evidence_ids=[primary.raw_evidence_id])
    return ComposedSection(name="what_to_watch", text=text, claims=[claim])


def _compose_source_updated(evidence_set: ArticleEvidenceSet) -> ComposedSection:
    primary = evidence_set.primary_evidence
    source_label = _SOURCE_LABELS.get(primary.source_type, primary.source_type)
    date_str = primary.published_at.strftime("%d %B %Y") if primary.published_at else "an unspecified date"
    text = f"Source: {source_label}, published {date_str}."
    return ComposedSection(name="source_updated", text=text, claims=[])


# ── Why It Matters (the one LLM-using section, FULL_ARTICLE only) ──────

def _should_attempt_why_it_matters(context: ArticleContextBundle | None) -> bool:
    """Only attempt the LLM call when there is real grounded material to
    reason from -- financial context or a market reaction. This is a
    deterministic gate, not a hope that the model declines gracefully on
    thin input; it's how "no-context article doesn't invent a Why It
    Matters section" is actually guaranteed rather than merely likely."""
    if context is None:
        return False
    return bool(context.financial_context) or context.market_reaction is not None


def _has_synthesizable_depth(evidence_set: ArticleEvidenceSet, context: ArticleContextBundle | None) -> bool:
    """C8.4 hardening (owner review, 2026-09-01): C4's FULL_ARTICLE
    decision is necessary but not sufficient. HEG's real 500-event C7
    case cleared C4's own depth gate through multiple independent
    HIGH-substantiveness supporting items (a real cascade of director
    appointment/resignation filings, each individually substantive) but
    had nothing to actually SYNTHESIZE: no financial context, no market
    reaction, no numeric substance in the primary evidence itself -- so
    Why It Matters correctly never even attempted, and composition fell
    back to a raw 15-item filing list (474 words, no analysis). This is
    the "does this FULL_ARTICLE have something to explain, not merely
    many related documents" gate the owner asked for -- checked at
    COMPOSE time, once real section-building is about to happen, not by
    re-deciding C4's own content_type/publication_action (those are
    untouched; this only controls which SHAPE gets composed).

    True when either of the two real sources of synthesizable depth
    exist: (1) the same real material Why It Matters itself requires
    (financial context or a market reaction -- if that's there, the LLM
    has something concrete to explain), or (2) the owner's own explicit
    allowance -- a single detailed primary filing with real, verified
    numeric substance can carry a FULL_ARTICLE on its own, with no
    upstream C3 context required at all."""
    if _should_attempt_why_it_matters(context):
        return True
    if evidence_set.primary_evidence and evidence_set.primary_evidence.title:
        return _has_numeric_substance(evidence_set.primary_evidence.title)
    return False


def _build_why_it_matters_prompt(
    evidence_set: ArticleEvidenceSet, context: ArticleContextBundle | None, retry_notes: list[str] | None,
) -> str:
    lines = [f"Company: {_company_name(evidence_set)} ({evidence_set.symbol})"]
    lines.append("\nWHAT HAPPENED (real, verified evidence):")
    lines.append(f"  [EVIDENCE:{evidence_set.primary_evidence.raw_evidence_id[:8]}] {evidence_set.primary_evidence.title}")
    for s in evidence_set.supporting_evidence[:2]:
        lines.append(f"  [EVIDENCE:{s.raw_evidence_id[:8]}] {s.title}")

    if context and context.market_reaction:
        mr = context.market_reaction
        lines.append(
            f"\nREAL PRICE MOVE (same day, temporal only -- NOT a claim of causation): "
            f"{evidence_set.symbol} {mr.price_move_pct:+.2f}%  [FACT:price_move]"
        )
    if context and context.financial_context:
        lines.append("\nVERIFIED FINANCIAL FACTS (quality-passed, use exactly as given):")
        for f in context.financial_context:
            period = f"FY{f.fiscal_year}" + (f" Q{f.fiscal_quarter}" if f.fiscal_quarter else "")
            lines.append(f"  [FACT:{f.metric_code}] {f.metric_name} = {_format_value(f.value, f.unit)} (as of {period})")

    lines.append(
        "\nDo not use any number not listed above. Do not attribute intent, sentiment, or "
        "causation to the price move. Do not predict a future outcome."
    )
    if retry_notes:
        lines.append(f"\nYour previous attempt was rejected: {'; '.join(retry_notes)}. Fix this and try again.")
    return "\n".join(lines)


def _build_llm_claims(
    raw_claims: list, evidence_set: ArticleEvidenceSet, context: ArticleContextBundle | None,
) -> list[ComposedClaim]:
    fact_codes = {f.metric_code for f in (context.financial_context if context else [])}
    all_evidence = [evidence_set.primary_evidence] + list(evidence_set.supporting_evidence)
    ev_by_short = {e.raw_evidence_id[:8]: e.raw_evidence_id for e in all_evidence if e}
    claims: list[ComposedClaim] = []
    for rc in raw_claims or []:
        if not isinstance(rc, dict):
            continue
        text = (rc.get("text") or "").strip()
        if not text:
            continue
        claim_type = rc.get("type") if rc.get("type") in ("FACT", "INTERPRETATION") else "INTERPRETATION"
        evidence_ids: list[str] = []
        financial_fact_ids: list[str] = []
        for ref in rc.get("evidence_refs") or []:
            ref = str(ref)
            m = re.search(r"FACT:([a-zA-Z0-9_]+)", ref)
            if m and m.group(1) in fact_codes:
                financial_fact_ids.append(m.group(1))
                continue
            m = re.search(r"EVIDENCE:([a-fA-F0-9]+)", ref)
            if m and m.group(1) in ev_by_short:
                evidence_ids.append(ev_by_short[m.group(1)])
        claims.append(ComposedClaim(text=text, claim_type=claim_type, evidence_ids=evidence_ids, financial_fact_ids=financial_fact_ids))
    return claims


async def _generate_why_it_matters(
    evidence_set: ArticleEvidenceSet, context: ArticleContextBundle | None,
) -> tuple[ComposedSection | None, str, int, list[str]]:
    if not _should_attempt_why_it_matters(context):
        return None, "omitted_no_context", 0, []

    shim = _BundleShim(context)
    allowed = build_allowed_values(shim, [evidence_set.primary_evidence] + list(evidence_set.supporting_evidence))

    retry_notes: list[str] | None = None
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        prompt = _build_why_it_matters_prompt(evidence_set, context, retry_notes)
        try:
            raw = await _call_with_fallback(prompt, system=_WHY_IT_MATTERS_SYSTEM_PROMPT, max_tokens=350, priority="background")
        except Exception as exc:
            log.warning("composer.why_it_matters_generation_failed", symbol=evidence_set.symbol, error=str(exc)[:200])
            return None, "omitted_generation_failed", attempt, [f"generation_failed: {str(exc)[:150]}"]

        if not raw:
            retry_notes = ["empty response"]
            continue
        parsed = _parse_json_response(raw)
        if parsed is None or not parsed.get("why_it_matters"):
            retry_notes = ["unparseable or empty JSON"]
            continue

        text = parsed["why_it_matters"]
        numeric_ok, numeric_errors = validate_numeric_claims(text, allowed)
        causal_hit = _check_causal_or_predictive(text)

        if numeric_ok and not causal_hit:
            claims = _build_llm_claims(parsed.get("claims") or [], evidence_set, context)
            section = ComposedSection(name="why_it_matters", text=text, claims=claims)
            return section, "ok", attempt, []

        notes: list[str] = []
        if not numeric_ok:
            notes.append(f"unsupported number(s): {[e['raw_text'] for e in numeric_errors]}")
        if causal_hit:
            notes.append(f"unsupported causal/predictive language: {causal_hit!r}")
        retry_notes = notes
        log.info("composer.why_it_matters_validation_failed", symbol=evidence_set.symbol, attempt=attempt, notes=notes)

    return None, "omitted_validation_failed", _MAX_ATTEMPTS, (retry_notes or [])


# ── Entry point ──────────────────────────────────────────────────────────

async def compose_article(
    decision: ArticleDecision, evidence_set: ArticleEvidenceSet, context: ArticleContextBundle | None,
    identity: ArticleIdentity, resolution: PublicationResolution, headline_result: HeadlineResult,
) -> ComposedArticle:
    """The one real entry point. Refuses outright (raises
    ComposerRefusal) for anything C4 or C5 already said not to publish
    -- never a best-effort attempt on a SKIP or a NO_PUBLICATION."""
    if decision.content_type == C4_SKIP:
        raise ComposerRefusal("C4 decided SKIP for this development -- C6 never composes a SKIP.")
    if decision.content_type not in (FULL_ARTICLE, FACTUAL_UPDATE):
        raise ComposerRefusal(f"unrecognized content_type {decision.content_type!r} -- refusing to compose.")
    if resolution.publication_action == NO_PUBLICATION:
        raise ComposerRefusal("C5 resolved this to NO_PUBLICATION (a real in-batch duplicate) -- C6 never composes it.")
    if evidence_set.primary_evidence is None:
        raise ComposerRefusal("no usable primary evidence -- nothing to compose.")
    if not headline_result.h1:
        raise ComposerRefusal("no usable headline -- nothing to compose.")

    sections: list[ComposedSection] = []
    all_claims: list[ComposedClaim] = []

    what_happened = _compose_what_happened(evidence_set)
    sections.append(what_happened)
    all_claims += what_happened.claims

    llm_status = "not_used"
    llm_attempts = 0
    llm_validation_notes: list[str] = []

    # C8.4: a FULL_ARTICLE decision from C4 is necessary but not
    # sufficient -- compose it as FULL_ARTICLE-shaped only when there is
    # real synthesizable depth; otherwise compose the SAME concise
    # FACTUAL_UPDATE shape used everywhere else, never a padded list of
    # filings pretending to be analysis.
    effective_content_type = decision.content_type
    depth_gate_downgraded = False
    if decision.content_type == FULL_ARTICLE and not _has_synthesizable_depth(evidence_set, context):
        effective_content_type = FACTUAL_UPDATE
        depth_gate_downgraded = True

    if effective_content_type == FULL_ARTICLE:
        why_section, llm_status, llm_attempts, llm_validation_notes = await _generate_why_it_matters(evidence_set, context)
        if why_section:
            sections.append(why_section)
            all_claims += why_section.claims

        verified_context = _compose_context_section(evidence_set, context, name="verified_context")
        if verified_context:
            sections.append(verified_context)
            all_claims += verified_context.claims

        what_to_watch = _compose_what_to_watch(evidence_set)
        if what_to_watch:
            sections.append(what_to_watch)
            all_claims += what_to_watch.claims
    else:
        key_details = _compose_context_section(evidence_set, context, name="key_details")
        if key_details:
            sections.append(key_details)
            all_claims += key_details.claims

    sections.append(_compose_source_updated(evidence_set))

    word_count = sum(len(s.text.split()) for s in sections)

    if depth_gate_downgraded:
        llm_validation_notes = [
            *llm_validation_notes,
            "C4 decided FULL_ARTICLE but no synthesizable depth existed (no financial/market context, no "
            "numeric substance in primary evidence) -- composed as FACTUAL_UPDATE instead of a raw filing list",
        ]

    return ComposedArticle(
        content_type=effective_content_type, headline=headline_result.h1, sections=sections,
        all_claims=all_claims, llm_status=llm_status, llm_attempts=llm_attempts, word_count=word_count,
        llm_validation_notes=llm_validation_notes, depth_gate_downgraded=depth_gate_downgraded,
    )
