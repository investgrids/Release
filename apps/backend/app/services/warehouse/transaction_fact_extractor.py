"""
TransactionFact extraction — Deep Filing Evidence Phase 1C (owner
design, 2026-09-17). Deterministic only, no LLM. Operates on a
SourceDocument's already-extracted page_texts_json -- this module
never fetches or parses PDF bytes itself (that's source_document.py's
job) and never modifies the SourceDocument it reads.

Two real, narrow strategies, each calibrated against one real specimen
(module docstring in app/db/models/transaction_fact.py has the full
justification):

  sebi_reg30_annexure_table -- ZODIAC's real Annexure I: a standardized
  numbered "Sr. No. / Particulars / Details" table the SEBI circular
  itself mandates. Field membership comes from the document's own
  numbered label, never from a keyword search; a field-specific regex
  is then applied ONLY inside that field's own already-scoped span
  (from its label to the next numbered item), never the whole document.

  prose_stake_and_target_phrase -- PRIMO's real plain-letter shape: no
  table exists, but stake percentage and target name co-occur in one
  real, grammatically coherent phrase ("NN% Equity Stake in <Target>
  Limited"), which is itself the field-binding evidence. There is
  deliberately NO equivalent whole-document prose strategy for
  consideration (see Phase 1C-R1 below) -- if this module cannot point
  to a real phrase that binds a value to that field, it reports
  NOT_FOUND, never a guess.

Each field is tried against BOTH strategies independently (table
anchor first, prose pattern second) rather than classifying "what kind
of filing is this" up front -- this is what lets ZODIAC populate via
the table and PRIMO populate target/stake via prose while both
correctly report NOT_FOUND for whatever their own real text does not
support, with no per-document-type branching to keep in sync.

Phase 1C-R1 (owner design, 2026-09-17): an unseen 10-filing cohort run
against the original version of this module found 2 confirmed false
extractions, both structural, not random noise -- see
_EXTRACTOR_VERSION's own comment below for the full diagnosis and the
governing rule this revision adds: an enumerated option listed in a
field's own LABEL text (e.g. a "...cash consideration or share swap..."
question) is never evidence of which option a filing actually
selected. The label is always separated from its answer before any
keyword classification runs, and a structured field whose value
notation isn't supported reports NOT_FOUND rather than falling back to
an unscoped whole-document search for a replacement number.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.transaction_fact import (
    CONSIDERATION_AMOUNT, CONSIDERATION_TYPE, NOT_FOUND, POPULATED, STAKE_PERCENTAGE,
    TARGET_ENTITY_NAME, TransactionFact,
)

_FIELD_NAMES = {
    TARGET_ENTITY_NAME: "Name of the target entity",
    STAKE_PERCENTAGE: "Percentage of shareholding / control acquired",
    CONSIDERATION_TYPE: "Consideration -- cash / share swap / other",
    CONSIDERATION_AMOUNT: "Cost of acquisition / consideration amount",
}

_METHOD_TABLE = "sebi_reg30_annexure_table"
_METHOD_PROSE_STAKE_TARGET = "prose_stake_and_target_phrase"

# Bump when an EXISTING strategy's own matching rule changes (a regex
# tightened/loosened, a new value pattern tried within an already-scoped
# span) -- not when a new field or a brand-new method is only added
# alongside the others. Lets a later reader tell "extracted by
# sebi_reg30_annexure_table under rule v1" apart from a future v2 that
# reuses the same method name.
#
# 1.1 -- Phase 1C-R1 (owner design, 2026-09-17), a bounded safety
# correction after the first unseen 10-filing cohort found 2 confirmed
# false extractions (see AUROPHARMA/JUNIPER regressions below):
#   - item-boundary recognition extended to the two other real
#     formats the cohort demonstrated (lettered "a)"/"b)" and
#     number-without-period "7 "/"8 ") -- previously only "1."/"2."
#     was recognized, so a lettered or unpunctuated table's span
#     bled across neighboring fields.
#   - consideration_type no longer scans its whole post-label span
#     for CASH/SHARE_SWAP keywords: the label text itself always
#     lists "share swap" as one of the enumerated options, which is
#     never evidence of the SELECTED option. The label is now
#     explicitly trimmed off (at its own "...of the same" ending)
#     before any keyword search runs on the answer alone.
#   - currency now also recognizes "Rs." (not just "₹") and the
#     crore/lakh magnitude words the cohort demonstrated ("₹248 crore"
#     must normalize to 2,480,000,000, never the bare "248").
#   - the unscoped whole-document consideration-amount fallback is
#     removed entirely: a recognized field with an unsupported value
#     notation is NOT_FOUND, never a reason to search the rest of the
#     document for a different, unrelated number (JUNIPER's real
#     failure mode -- a correctly-scoped match failed on "Rs." and
#     the old fallback then found an unrelated "₹248" on a later
#     press-release annexure page).
#
# 1.2 -- Phase 1C-R2 + TargetFact R1 (owner design, 2026-09-18):
#   - CONSIDERATION_AMOUNT currency matching now requires a lexical
#     boundary before "Rs" and a real leading digit in the captured
#     amount (see _CURRENCY_AMOUNT_RE/_is_safe_currency_match/
#     _parse_currency_amount above) -- fixes the real GUJENERGY crash
#     (an incidental "...shareholde|rs," substring was previously
#     misread as a currency token with an empty numeric capture).
#   - TARGET_ENTITY_NAME now also recognizes a bare or short-sub-label
#     corporate name (no literal "Name:" prefix required) via
#     _TABLE_NAME_FALLBACK_RE, tried only when the original "Name:"
#     match fails -- covers the real DALBHARAT/HMVL/GREENLAM/UTLSOLAR/
#     HERANBA/INDIACEM cohort, all previously NOT_FOUND despite a real,
#     well-formed answer being present.
_EXTRACTOR_VERSION = "1.2"

_NUMBERED_ITEM_RE = re.compile(
    r"\n\s*(?:"
    r"\d{1,2}\.\s{1,3}"        # "1.  ", "9.  " (ZODIAC/GLAND/JSWINFRA/BSL/QMSMEDI shape)
    r"|[a-j]\)\s+"             # "a) ", "g) " (AUROPHARMA/IBULLSLTD/RBA shape)
    r"|\d{1,2}\s+[A-Z][a-z]"   # "7 Nature", "8 Cost" (JUNIPER shape -- number, no period, capitalized word)
    r")"
)

_TABLE_ANCHORS = {
    TARGET_ENTITY_NAME: re.compile(r"Name of the target entity", re.IGNORECASE),
    STAKE_PERCENTAGE: re.compile(r"Percentage of shareholding", re.IGNORECASE),
    CONSIDERATION_TYPE: re.compile(r"Consideration\s*-\s*whether cash", re.IGNORECASE),
    CONSIDERATION_AMOUNT: re.compile(r"Cost of acquisition", re.IGNORECASE),
}

# Every real specimen's consideration-type LABEL ends with some form of
# "...and details of the same" immediately before the real answer
# begins (confirmed across ZODIAC/GLAND/AUROPHARMA/JUNIPER/IBULLSLTD/
# RBA/MAITHANALL). Tolerates a missing space in "ofthe" (a real pypdf
# extraction artifact seen in MAITHANALL) and a line break anywhere.
# This is the label/answer boundary itself -- text before it is the
# enumerated-options question, never evidence of which option was
# actually selected.
_LABEL_END_RE = re.compile(r"of\s*\n?\s*the\s*\n?\s*same\b", re.IGNORECASE)

_TABLE_NAME_RE = re.compile(r"Name:\s*([^\n]+)", re.IGNORECASE)

# TargetFact R1 (owner design, 2026-09-18): a read-only Target Entity
# Coverage Audit of the 6 real target_entity_name NOT_FOUND misses from
# the Assembly V2 fresh-cohort audit (DALBHARAT, HMVL, GREENLAM,
# UTLSOLAR, HERANBA, INDIACEM) found exactly ONE recurring root cause,
# not six unrelated shapes: _TABLE_NAME_RE's literal "Name:" sub-label
# is over-fit to ZODIAC's specific answer-rendering convention. Every
# miss's real table answer instead states the corporate name either
# bare (no sub-label at all -- DALBHARAT/GREENLAM/UTLSOLAR/INDIACEM,
# 4/6) or after a short generic sub-label with no colon
# ("Target Entity" -- HMVL). ("Name of Entity :" -- HERANBA -- already
# self-resolves correctly with this same fallback: the colon is outside
# the character class below, so the match naturally starts fresh at the
# real name right after it, exactly like ZODIAC's own "Name:" already
# does via _TABLE_NAME_RE.)
#
# This fallback reuses _PROSE_STAKE_TARGET_RE's own exact corporate-
# suffix character class and length bound verbatim -- the same
# discipline that strategy already enforces (a real corporate suffix
# required, never a bare word), applied here to the TARGET_ENTITY_NAME
# field's own already-scoped table span instead of a stake-percentage-
# anchored prose phrase. Never widens scope beyond that span; only
# tried when _TABLE_NAME_RE's stricter, already-correct match fails.
_TABLE_NAME_FALLBACK_RE = re.compile(r"([A-Z][A-Za-z0-9&.,'\s]{2,100}?(?:Private\s+Limited|Limited|Ltd\.?|LLP))")

# The one concrete sub-label demonstrated to lack a natural character-
# class boundary (no colon) before the real name, so it would otherwise
# be swept into the fallback match above (HMVL: "Target Entity \n
# Assetgro Fintech Private Limited"). Stripped from the FRONT of an
# already-matched candidate, never from the span itself -- narrowly
# scoped to this one demonstrated real label wording, not a general
# label-stripping heuristic.
_TARGET_KNOWN_SUBLABEL_PREFIX_RE = re.compile(r"^Target\s+Entity\s*", re.IGNORECASE)
_PERCENT_RE = re.compile(r"(\d{1,3}(?:\.\d+)?)\s*%")
_CASH_RE = re.compile(r"\bcash\b", re.IGNORECASE)
_SHARE_SWAP_RE = re.compile(r"\bshare\s*swap\b", re.IGNORECASE)
# IBULLSLTD's real answer never uses the words "share swap" at all --
# it states the mechanism directly ("issuance of ... equity shares").
# Narrow, proximity-bounded (not a bare "equity shares" anywhere-in-text
# check): only counts when "issuance of" and "equity shares" occur
# together as one real clause.
_ISSUANCE_SHARES_RE = re.compile(r"\bissuance\s+of\b[\s\S]{0,80}?\bequity\s+shares\b", re.IGNORECASE)
# "₹" or "Rs." (both real, demonstrated), optionally followed by a real
# demonstrated Indian magnitude word -- never a bare naked number with
# no currency marker at all.
#
# Phase 1C-R2 (owner design, 2026-09-18): GUJENERGY regression -- real
# prose ("...their respective shareholders, pursuant to...") contains
# the bare substring "rs," (the tail of "shareholders" immediately
# followed by a comma). Without a lexical boundary before "Rs", that
# substring itself matched as a currency token, and the old capture
# group `[\d,]+` allowed the "match" to consist of nothing but that one
# comma -- a captured amount with zero digits. `\b` before "Rs" (never
# needed before "₹", which is already a non-word character no real word
# can absorb) requires a real word boundary immediately before the
# currency marker, so "shareholde|rs," never qualifies (both sides of
# that "r" are word characters). Requiring the capture group to START
# with a digit (`\d[\d,]*` instead of `[\d,]+`) is the second, redundant
# layer -- even if a future boundary-adjacent regression reopened a
# similar false match, a group that cannot be all-punctuation can never
# again produce an empty numeric string.
_CURRENCY_AMOUNT_RE = re.compile(r"(?:₹|\bRs\.?)\s?(\d[\d,]*(?:\.\d+)?)\s*(crore|lakh)?", re.IGNORECASE)
_CRORE_MULTIPLIER = 1_00_00_000  # 1 crore = 10,000,000
_LAKH_MULTIPLIER = 1_00_000      # 1 lakh = 100,000


def _parse_currency_amount(match: re.Match) -> float | None:
    """Phase 1C-R2 (2026-09-18): defense-in-depth, never raises. Even
    with the regex/`_is_safe_currency_match` hardening above, this
    function independently refuses to convert anything that is not
    cleanly all-digits-with-an-optional-decimal-point once commas are
    stripped -- a malformed currency candidate returns None (the caller
    treats that exactly like NOT_FOUND) rather than letting a bare
    ValueError from `float()` propagate up and abort extraction of
    every OTHER field in the same document, which is precisely what the
    real GUJENERGY specimen did before this fix. Scoped narrowly to
    invalid currency-match parsing -- this is not a general
    try/except-everything net."""
    raw = match.group(1).replace(",", "")
    if not re.fullmatch(r"\d+(?:\.\d+)?", raw):
        return None
    base = float(raw)
    magnitude = (match.group(2) or "").lower()
    if magnitude == "crore":
        return base * _CRORE_MULTIPLIER
    if magnitude == "lakh":
        return base * _LAKH_MULTIPLIER
    return base


def _is_safe_currency_match(match: re.Match) -> bool:
    """R1 (MAITHANALL regression, found during the frozen-cohort rerun
    that verified the original R1 fix): a real, fully-expanded Indian-
    grouped rupee figure always carries at least one comma (even the
    smallest realistic amount, e.g. "1,00,000"); a bare number with no
    comma grouping is only ever safe to accept when a real magnitude
    word (crore/lakh) is cleanly captured immediately after it. A bare,
    comma-free number with NO magnitude word attached is never treated
    as a complete rupee figure -- accepting it would be exactly the
    naked-number-to-INR inference this extractor must never make. This
    is what catches MAITHANALL's real OCR-corrupted "Rs. 113.3? Crore"
    (a stray "?" breaks the magnitude-word match, and the bare "113.3"
    is off by a factor of 10 million from the real 113.3 CRORE) --
    correctly declining rather than silently repairing the corruption.

    R2 (2026-09-18): the capture group is now guaranteed (by the regex
    itself) to start with a real digit, so a GUJENERGY-shaped bare-
    comma match can no longer reach this function at all -- this
    docstring addendum records that the comma/magnitude heuristic below
    was never itself wrong, the input reaching it just wasn't validated
    yet."""
    has_comma = "," in match.group(1)
    has_magnitude = bool(match.group(2))
    return has_comma or has_magnitude

# Real, narrow prose phrase demonstrated by PRIMO's own filing: the
# percentage and target name co-occur in one coherent clause. Requires
# a real corporate suffix on the captured name -- never accepts a bare
# word as a company name.
_PROSE_STAKE_TARGET_RE = re.compile(
    r"(\d{1,3}(?:\.\d+)?)\s*%\s*\n?\s*equity\s+stake\s+in\s+"
    r"([A-Z][A-Za-z0-9&.,'\s]{2,100}?(?:Private\s+Limited|Limited|Ltd\.?|LLP))",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class TransactionFactCandidate:
    field_code: str
    field_name: str
    extraction_status: str
    extraction_method: str
    value_text: str | None = None
    value_numeric: float | None = None
    unit: str | None = None
    page_number: int | None = None
    source_span_text: str | None = None
    extraction_method_version: str = _EXTRACTOR_VERSION


def _span_after(text: str, anchor: re.Pattern) -> tuple[str, int] | None:
    """The text from just after `anchor`'s match to the start of the
    NEXT numbered item (or end of text) -- the field's own scoped span,
    established by the document's own numbering, never the whole
    document. Returns (span, match_start_offset) or None."""
    m = anchor.search(text)
    if not m:
        return None
    next_item = _NUMBERED_ITEM_RE.search(text, m.end())
    span = text[m.end():next_item.start()] if next_item else text[m.end():]
    return span, m.start()


def _try_table_field(pages: list[str], field_code: str) -> TransactionFactCandidate | None:
    anchor = _TABLE_ANCHORS[field_code]
    for page_num, page_text in enumerate(pages, start=1):
        result = _span_after(page_text, anchor)
        if result is None:
            continue
        span, _ = result

        if field_code == TARGET_ENTITY_NAME:
            m = _TABLE_NAME_RE.search(span)
            if m:
                return TransactionFactCandidate(
                    field_code, _FIELD_NAMES[field_code], POPULATED, _METHOD_TABLE,
                    value_text=m.group(1).strip(), page_number=page_num, source_span_text=span.strip()[:500],
                )
            # TargetFact R1: no "Name:" sub-label present -- try the
            # bare/short-sub-label corporate-name shape instead (see the
            # fallback's own definition above for the real demonstrated
            # cases this covers).
            m2 = _TABLE_NAME_FALLBACK_RE.search(span)
            if m2:
                name = _TARGET_KNOWN_SUBLABEL_PREFIX_RE.sub("", m2.group(1).strip())
                name = re.sub(r"\s+", " ", name).strip()
                return TransactionFactCandidate(
                    field_code, _FIELD_NAMES[field_code], POPULATED, _METHOD_TABLE,
                    value_text=name, page_number=page_num, source_span_text=span.strip()[:500],
                )
        elif field_code == STAKE_PERCENTAGE:
            m = _PERCENT_RE.search(span)
            if m:
                return TransactionFactCandidate(
                    field_code, _FIELD_NAMES[field_code], POPULATED, _METHOD_TABLE,
                    value_numeric=float(m.group(1)), unit="pct",
                    page_number=page_num, source_span_text=span.strip()[:500],
                )
        elif field_code == CONSIDERATION_TYPE:
            # R1: the label itself always lists "share swap" as one of the
            # enumerated options -- never evidence of which option was
            # actually selected. Trim the label off at its own "...of the
            # same" ending and classify ONLY the answer that follows. No
            # end-of-label marker found -> can't safely separate label
            # from answer, so decline rather than risk contamination.
            label_end = _LABEL_END_RE.search(span)
            if not label_end:
                return None
            answer = span[label_end.end():].strip()
            if _CASH_RE.search(answer):
                return TransactionFactCandidate(
                    field_code, _FIELD_NAMES[field_code], POPULATED, _METHOD_TABLE,
                    value_text="CASH", page_number=page_num, source_span_text=answer[:500],
                )
            if _SHARE_SWAP_RE.search(answer) or _ISSUANCE_SHARES_RE.search(answer):
                return TransactionFactCandidate(
                    field_code, _FIELD_NAMES[field_code], POPULATED, _METHOD_TABLE,
                    value_text="SHARE_SWAP", page_number=page_num, source_span_text=answer[:500],
                )
        elif field_code == CONSIDERATION_AMOUNT:
            m = _CURRENCY_AMOUNT_RE.search(span)
            if m and _is_safe_currency_match(m):
                amount = _parse_currency_amount(m)
                # R2: _parse_currency_amount's own defense-in-depth can
                # still decline (None) even after a match passes the
                # regex + _is_safe_currency_match gates -- falls through
                # to NOT_FOUND below exactly like any other declined
                # match, never a partially-built POPULATED candidate.
                if amount is not None:
                    return TransactionFactCandidate(
                        field_code, _FIELD_NAMES[field_code], POPULATED, _METHOD_TABLE,
                        value_numeric=amount, unit="inr",
                        page_number=page_num, source_span_text=span.strip()[:500],
                    )
            # R1: a recognized field whose value notation this extractor
            # doesn't support (e.g. USD, or a format the currency regex
            # doesn't match, or a number _is_safe_currency_match declined)
            # is NOT_FOUND -- never a reason to escape this field's own
            # scoped span and search the rest of the document for a
            # different, unrelated number (JUNIPER's real failure mode;
            # see the removed prose consideration-amount fallback).
        # Anchor found on this page but the value pattern didn't match
        # within its own scoped span -- a real, narrow field-not-
        # populated case, not a reason to keep searching other pages
        # for the same label (the document only states this once).
        return None
    return None


def _try_prose_stake_and_target(pages: list[str]) -> tuple[TransactionFactCandidate, TransactionFactCandidate] | None:
    for page_num, page_text in enumerate(pages, start=1):
        m = _PROSE_STAKE_TARGET_RE.search(page_text)
        if not m:
            continue
        span = m.group(0).strip()
        stake = TransactionFactCandidate(
            STAKE_PERCENTAGE, _FIELD_NAMES[STAKE_PERCENTAGE], POPULATED, _METHOD_PROSE_STAKE_TARGET,
            value_numeric=float(m.group(1)), unit="pct", page_number=page_num, source_span_text=span,
        )
        target = TransactionFactCandidate(
            TARGET_ENTITY_NAME, _FIELD_NAMES[TARGET_ENTITY_NAME], POPULATED, _METHOD_PROSE_STAKE_TARGET,
            value_text=re.sub(r"\s+", " ", m.group(2)).strip(), page_number=page_num, source_span_text=span,
        )
        return stake, target
    return None


def extract_transaction_facts(pages: list[str]) -> list[TransactionFactCandidate]:
    """Pure function -- no DB, no fetch. `pages` is the SourceDocument's
    own page_texts (already deterministically extracted, see
    source_document.py). Always returns exactly one candidate per field
    in FIELD_CODES order, POPULATED or NOT_FOUND -- never omits a field
    silently."""
    candidates: dict[str, TransactionFactCandidate] = {}

    for field_code in (TARGET_ENTITY_NAME, STAKE_PERCENTAGE, CONSIDERATION_TYPE, CONSIDERATION_AMOUNT):
        found = _try_table_field(pages, field_code)
        if found is not None:
            candidates[field_code] = found

    if TARGET_ENTITY_NAME not in candidates or STAKE_PERCENTAGE not in candidates:
        prose = _try_prose_stake_and_target(pages)
        if prose is not None:
            stake, target = prose
            candidates.setdefault(STAKE_PERCENTAGE, stake)
            candidates.setdefault(TARGET_ENTITY_NAME, target)

    out = []
    for field_code in (TARGET_ENTITY_NAME, STAKE_PERCENTAGE, CONSIDERATION_TYPE, CONSIDERATION_AMOUNT):
        out.append(candidates.get(field_code) or TransactionFactCandidate(
            field_code, _FIELD_NAMES[field_code], NOT_FOUND, "none_matched",
        ))
    return out


async def persist_transaction_facts(
    db: AsyncSession, *, source_document_id: str, raw_evidence_id: str, candidates: list[TransactionFactCandidate],
) -> list[TransactionFact]:
    """Upserts one row per (source_document_id, field_code) -- re-running
    extraction against the same document version replaces that field's
    own prior row rather than accumulating duplicates."""
    now = datetime.now(timezone.utc)
    rows = []
    for c in candidates:
        existing = (await db.execute(
            select(TransactionFact).where(
                TransactionFact.source_document_id == source_document_id, TransactionFact.field_code == c.field_code,
            ).limit(1)
        )).scalar_one_or_none()
        if existing is not None:
            existing.value_text = c.value_text
            existing.value_numeric = c.value_numeric
            existing.unit = c.unit
            existing.extraction_status = c.extraction_status
            existing.extraction_method = c.extraction_method
            existing.extraction_method_version = c.extraction_method_version
            existing.page_number = c.page_number
            existing.source_span_text = c.source_span_text
            existing.extracted_at = now
            rows.append(existing)
        else:
            row = TransactionFact(
                source_document_id=source_document_id, raw_evidence_id=raw_evidence_id,
                field_code=c.field_code, field_name=c.field_name,
                value_text=c.value_text, value_numeric=c.value_numeric, unit=c.unit,
                extraction_status=c.extraction_status, extraction_method=c.extraction_method,
                extraction_method_version=c.extraction_method_version,
                page_number=c.page_number, source_span_text=c.source_span_text, extracted_at=now,
            )
            db.add(row)
            rows.append(row)
    await db.commit()
    return rows
