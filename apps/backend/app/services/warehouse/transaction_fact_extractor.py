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

  prose_* -- PRIMO's real plain-letter shape: no table exists, but
  stake percentage and target name co-occur in one real, grammatically
  coherent phrase ("NN% Equity Stake in <Target> Limited"), which is
  itself the field-binding evidence. Consideration has no equivalent
  real prose pattern demonstrated -- if this module cannot point to a
  real phrase that binds a value to that field, it reports NOT_FOUND,
  never a guess.

Each field is tried against BOTH strategies independently (table
anchor first, prose pattern second) rather than classifying "what kind
of filing is this" up front -- this is what lets ZODIAC populate via
the table and PRIMO populate target/stake via prose while both
correctly report NOT_FOUND for whatever their own real text does not
support, with no per-document-type branching to keep in sync.
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
_METHOD_PROSE_CONSIDERATION = "prose_currency_pattern"

# Bump when an EXISTING strategy's own matching rule changes (a regex
# tightened/loosened, a new value pattern tried within an already-scoped
# span) -- not when a new field or a brand-new method is only added
# alongside the others. Lets a later reader tell "extracted by
# sebi_reg30_annexure_table under rule v1" apart from a future v2 that
# reuses the same method name.
_EXTRACTOR_VERSION = "1.0"

_NUMBERED_ITEM_RE = re.compile(r"\n\s*\d{1,2}\.\s{1,3}")

_TABLE_ANCHORS = {
    TARGET_ENTITY_NAME: re.compile(r"Name of the target entity", re.IGNORECASE),
    STAKE_PERCENTAGE: re.compile(r"Percentage of shareholding", re.IGNORECASE),
    CONSIDERATION_TYPE: re.compile(r"Consideration\s*-\s*whether cash", re.IGNORECASE),
    CONSIDERATION_AMOUNT: re.compile(r"Cost of acquisition", re.IGNORECASE),
}

_TABLE_NAME_RE = re.compile(r"Name:\s*([^\n]+)", re.IGNORECASE)
_PERCENT_RE = re.compile(r"(\d{1,3}(?:\.\d+)?)\s*%")
_CASH_RE = re.compile(r"\bcash consideration\b", re.IGNORECASE)
_SHARE_SWAP_RE = re.compile(r"\bshare\s*swap\b", re.IGNORECASE)
_CURRENCY_AMOUNT_RE = re.compile(r"₹\s?([\d,]+(?:\.\d+)?)")

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
        elif field_code == STAKE_PERCENTAGE:
            m = _PERCENT_RE.search(span)
            if m:
                return TransactionFactCandidate(
                    field_code, _FIELD_NAMES[field_code], POPULATED, _METHOD_TABLE,
                    value_numeric=float(m.group(1)), unit="pct",
                    page_number=page_num, source_span_text=span.strip()[:500],
                )
        elif field_code == CONSIDERATION_TYPE:
            if _CASH_RE.search(span):
                return TransactionFactCandidate(
                    field_code, _FIELD_NAMES[field_code], POPULATED, _METHOD_TABLE,
                    value_text="CASH", page_number=page_num, source_span_text=span.strip()[:500],
                )
            if _SHARE_SWAP_RE.search(span):
                return TransactionFactCandidate(
                    field_code, _FIELD_NAMES[field_code], POPULATED, _METHOD_TABLE,
                    value_text="SHARE_SWAP", page_number=page_num, source_span_text=span.strip()[:500],
                )
        elif field_code == CONSIDERATION_AMOUNT:
            m = _CURRENCY_AMOUNT_RE.search(span)
            if m:
                return TransactionFactCandidate(
                    field_code, _FIELD_NAMES[field_code], POPULATED, _METHOD_TABLE,
                    value_numeric=float(m.group(1).replace(",", "")), unit="inr",
                    page_number=page_num, source_span_text=span.strip()[:500],
                )
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


def _try_prose_consideration_amount(pages: list[str]) -> TransactionFactCandidate | None:
    for page_num, page_text in enumerate(pages, start=1):
        m = _CURRENCY_AMOUNT_RE.search(page_text)
        if m:
            return TransactionFactCandidate(
                CONSIDERATION_AMOUNT, _FIELD_NAMES[CONSIDERATION_AMOUNT], POPULATED, _METHOD_PROSE_CONSIDERATION,
                value_numeric=float(m.group(1).replace(",", "")), unit="inr",
                page_number=page_num, source_span_text=m.group(0),
            )
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

    if CONSIDERATION_AMOUNT not in candidates:
        found = _try_prose_consideration_amount(pages)
        if found is not None:
            candidates[CONSIDERATION_AMOUNT] = found

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
