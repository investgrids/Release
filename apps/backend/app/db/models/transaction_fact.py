"""
TransactionFact — Deep Filing Evidence Phase 1C, first structured fact
family (owner design, 2026-09-17). One row per (source_document_id,
field_code), mirroring financial_fact.py's own established shape (one
row per metric, not one denormalized row per filing) and its "missing
is never silently absent" philosophy: every field in the known
vocabulary gets a row for every SourceDocument checked, either
POPULATED with real provenance or explicitly NOT_FOUND -- never a
silently-missing column indistinguishable from "never checked."

Built directly against two real specimens (Deep Filing Evidence Source
Reality Audit, 2026-09-17):

  ZODIAC (nse-4021315061) -- a real SEBI Reg 30 filing whose Annexure I
  is a standardized numbered "Sr. No. / Particulars / Details" table
  (mandated by SEBI Master Circular HO/49/14/14(7)2025-CFD-POD2/I/
  3762/2026). Each of the ten numbered particulars is the source
  document's OWN explicit field label -- extraction here does not
  invent field membership, it reads a label the filing itself already
  assigns, then narrows to the specific token within that already-
  scoped span (e.g. the first "NN%" inside the "Percentage of
  shareholding / control acquired" row, never a percentage found
  anywhere else in the document).

  PRIMO (nse-302e32d5d4) -- plain prose, no such table. Stake
  percentage and target entity name ARE extractable from one real,
  narrow, grammatically coherent phrase ("51% Equity Stake in Flow
  Tech Chemicals Private Limited"). Consideration is genuinely absent
  from the filing's own text -- no currency figure, no "crore"/"lakh",
  nothing. This is the deliberate negative/partial specimen: a
  TransactionFact for PRIMO must record consideration_amount as
  NOT_FOUND, never infer a value the source document does not state.

The governing rule, per owner instruction: a field is populated only
when the extractor can point to the exact text that establishes BOTH
which field a value belongs to and the value itself -- page_number +
source_span_text together ARE that proof. A value found by keyword
presence alone, with no established field membership, is not a fact
this table accepts.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint

from app.db.base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


POPULATED = "POPULATED"
NOT_FOUND = "NOT_FOUND"   # this field's known vocabulary was checked against this document and no value could be bound to it -- never silently absent

# field_code vocabulary -- narrow, first slice only (owner instruction:
# "keep the first schema narrow"). transaction_status/transaction_date/
# business_purpose deliberately deferred, not designed speculatively here.
TARGET_ENTITY_NAME = "target_entity_name"
STAKE_PERCENTAGE = "stake_percentage"
CONSIDERATION_TYPE = "consideration_type"
CONSIDERATION_AMOUNT = "consideration_amount"

FIELD_CODES = (TARGET_ENTITY_NAME, STAKE_PERCENTAGE, CONSIDERATION_TYPE, CONSIDERATION_AMOUNT)


class TransactionFact(Base):
    __tablename__ = "transaction_facts"

    id = Column(Integer, primary_key=True, autoincrement=True)

    source_document_id = Column(String(36), ForeignKey("source_documents.id"), nullable=False, index=True)
    # Denormalized, matching financial_fact.py's own symbol denormalization --
    # every fact traces to its originating announcement without a join.
    raw_evidence_id = Column(String(36), ForeignKey("raw_evidence.id"), nullable=False, index=True)

    field_code = Column(String(48), nullable=False)
    field_name = Column(String(120), nullable=False)   # human-readable, e.g. "Percentage of shareholding / control acquired"

    value_text = Column(Text, nullable=True)
    value_numeric = Column(Float, nullable=True)
    unit = Column(String(16), nullable=True)            # "pct" | "inr" | None

    extraction_status = Column(String(16), nullable=False, index=True)   # POPULATED | NOT_FOUND
    extraction_method = Column(String(64), nullable=False)               # e.g. "sebi_reg30_annexure_table" | "prose_stake_and_target_phrase"
    # The extractor's own rule version at the time this row was written --
    # a method NAME staying the same across a later regex/pattern change
    # would otherwise make an old and a new POPULATED row indistinguishable.
    # Bump this in transaction_fact_extractor.py whenever an existing
    # strategy's matching rule changes, not when a brand-new field/method
    # is only added alongside it.
    extraction_method_version = Column(String(16), nullable=False)

    # Provenance -- the exact proof a future reader (or CD3) can check
    # without re-fetching the document. page_number is 1-indexed into
    # the owning SourceDocument's page_texts_json. source_span_text is
    # the literal excerpt this value was read from, NEVER a paraphrase.
    page_number = Column(Integer, nullable=True)
    source_span_text = Column(Text, nullable=True)

    extracted_at = Column(DateTime(timezone=True), nullable=False, default=_now)

    __table_args__ = (
        # Re-running extraction against the same document version replaces
        # this field's own row (see transaction_fact_extractor.py's
        # persist step) -- never accumulates duplicate facts for one
        # (document, field) pair.
        UniqueConstraint("source_document_id", "field_code", name="ux_transaction_fact_identity"),
        Index("ix_transaction_fact_raw_evidence", "raw_evidence_id"),
    )
