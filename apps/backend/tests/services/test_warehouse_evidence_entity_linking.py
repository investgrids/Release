"""
EvidenceEntityLink — real DB-backed tests (Warehouse Consumption Phase 2,
"the major unlock", owner decision 2026-08-25).

This is the direct, executable re-run of the adversarial case the owner
specified after the audit's ICICIBANK case study, on real data:

    ICICI Bank bond issuance       -> ICICIBANK       (linked)
    ICICI Lombard filing           -> ICICIGI         (linked, DIFFERENT entity)
    Senores filing mentioning bank -> NOT ICICIBANK subject (never linked)
    ICICI Direct article/byline    -> NOT ICICIBANK   (never linked)

Company Master data is real and sourced, not fabricated: ICICIBANK and
ICICIGI's symbol/name/ISIN below are copied verbatim from a real live
NSE EQUITY_L.csv snapshot (artifacts/nse_eq.csv, fetched during the C1
reconciliation this session) -- the same real-data discipline
test_company_identity.py's own fixture already uses, just inlined here
rather than extending that shared fixture file.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import delete, select

from app.db.models.evidence_entity_link import EvidenceEntityLink
from app.db.models.raw_evidence import RawEvidence
from app.db.session import AsyncSessionLocal
from app.services.company_identity.importer import parse_nse_eq_csv, upsert_company_entities
from app.services.warehouse.evidence_entity_linking import (
    backfill_nse_entity_links, extract_nse_symbol, link_nse_evidence_to_entity,
)
from app.services.warehouse.raw_evidence import capture_raw_evidence
from app.services.warehouse.source_registry_seed import seed_source_registry

# Real rows, verbatim from a live NSE EQUITY_L.csv snapshot -- see module
# docstring. Header format matches parse_nse_eq_csv's own real contract.
_REAL_EQ_CSV = """SYMBOL,NAME OF COMPANY, SERIES, DATE OF LISTING, PAID UP VALUE, MARKET LOT, ISIN NUMBER, FACE VALUE
ICICIBANK,ICICI Bank Limited,EQ,17-SEP-1997,2,1,INE090A01021,2
ICICIGI,ICICI Lombard General Insurance Company Limited,EQ,27-SEP-2017,10,1,INE765G01017,10
"""


def _tag() -> str:
    return uuid.uuid4().hex[:8]


@pytest.fixture
async def real_entities():
    """Real ICICIBANK + ICICIGI CompanyEntity/CompanyAlias rows, via the
    actual importer -- not a hand-crafted ORM insert -- so this test
    proves the real end-to-end resolution path, not a shortcut around it."""
    async with AsyncSessionLocal() as db:
        rows = parse_nse_eq_csv(_REAL_EQ_CSV)
        summary = await upsert_company_entities(db, rows, allowed_series={"EQ"})
        await db.commit()
    yield summary
    async with AsyncSessionLocal() as db:
        from app.db.models.company_entity import CompanyEntity, CompanyAlias
        await db.execute(delete(CompanyAlias).where(CompanyAlias.alias_value.in_(["ICICIBANK", "ICICIGI"])))
        await db.execute(delete(CompanyEntity).where(CompanyEntity.isin.in_(["INE090A01021", "INE765G01017"])))
        await db.commit()


@pytest.fixture
async def source_id():
    """Real, seeded source registry -- capture_raw_evidence() resolves
    its own real, hardcoded source_id internally per source name (e.g.
    "nse_corporate_announcements" for NSE, a real RSS feed id looked up
    from the item's own `source` field for RSS) via resolve_source_id();
    it never accepts a caller-supplied source_id, so a fixture creating
    an arbitrary one (as read_service.py's own tests correctly do, since
    THAT code path takes source_id as a plain parameter) doesn't apply
    here. seed_source_registry() is upsert-based, safe to call
    regardless of what already exists. Yields the real
    "nse_corporate_announcements" id for the handful of tests that build
    a RawEvidence row directly (bypassing capture_raw_evidence) and need
    a real, valid source_id FK value."""
    async with AsyncSessionLocal() as db:
        await seed_source_registry(db)
        await db.commit()
    yield "nse_corporate_announcements"


async def _cleanup(evidence_key_prefix: str) -> None:
    async with AsyncSessionLocal() as db:
        ids = (await db.execute(
            select(RawEvidence.id).where(RawEvidence.evidence_key.like(f"{evidence_key_prefix}%"))
        )).scalars().all()
        if ids:
            await db.execute(delete(EvidenceEntityLink).where(EvidenceEntityLink.raw_evidence_id.in_(ids)))
        await db.execute(delete(RawEvidence).where(RawEvidence.evidence_key.like(f"{evidence_key_prefix}%")))
        await db.commit()


# ── extract_nse_symbol ───────────────────────────────────────────────────────

def test_extract_symbol_from_plain_announcement():
    assert extract_nse_symbol({"symbol": "ICICIBANK", "_kind": None}) == "ICICIBANK"


def test_extract_symbol_from_board_meeting_uses_bm_symbol():
    assert extract_nse_symbol({"symbol": None, "bm_symbol": "ICICIBANK", "_kind": "board_meeting"}) == "ICICIBANK"


def test_extract_symbol_absent_returns_none():
    assert extract_nse_symbol({"_kind": None}) is None


# ── The real adversarial case, end to end via capture_raw_evidence() ───────

@pytest.mark.asyncio
async def test_icici_bank_filing_links_to_icicibank_entity(real_entities, source_id):
    tag = _tag()
    raw = {
        "id": f"test-icici-bond-{tag}", "an_no": None, "seq_id": f"seq-{tag}",
        "symbol": "ICICIBANK", "_kind": None,
        "attchmntText": "ICICI Bank Limited priced USD 1 billion Senior Unsecured Fixed Rate Notes.",
        "sort_date": "2026-08-24 13:05:34",
    }
    try:
        async with AsyncSessionLocal() as db:
            result = await capture_raw_evidence(db, "NSE", [(raw, "good")])
        assert result["written"] == 1

        async with AsyncSessionLocal() as db:
            # real evidence_key format: "nse:" + _extract_external_id()'s
            # own f"nse-{seq_id}" -- i.e. "nse:nse-{seq_id}", not "nse:{seq_id}"
            links = (await db.execute(
                select(EvidenceEntityLink).join(RawEvidence, EvidenceEntityLink.raw_evidence_id == RawEvidence.id)
                .where(RawEvidence.evidence_key == f"nse:nse-seq-{tag}")
            )).scalars().all()
            from app.db.models.company_entity import CompanyAlias
            icicibank_entity_id = (await db.execute(
                select(CompanyAlias.entity_id).where(CompanyAlias.alias_value == "ICICIBANK")
            )).scalar_one()

        assert len(links) == 1
        assert links[0].relationship_type == "subject"
        assert links[0].resolution_method == "source_symbol"
        assert links[0].entity_id == icicibank_entity_id, "must resolve to the real ICICIBANK entity, not merely 'some' entity"
    finally:
        await _cleanup(f"nse:nse-seq-{tag}")


@pytest.mark.asyncio
async def test_icici_lombard_filing_links_to_a_different_entity_than_icicibank(real_entities, source_id):
    """The exact real-world confusion the audit found: two real, distinct
    companies sharing the 'ICICI' brand prefix must resolve to two
    different, correct entity_ids -- never collapse to the same one."""
    tag = _tag()
    icici_bank_raw = {
        "id": f"test-icicibank-{tag}", "seq_id": f"seq-bank-{tag}", "symbol": "ICICIBANK", "_kind": None,
        "attchmntText": "ICICI Bank Limited regulation 30 disclosure.", "sort_date": "2026-08-24",
    }
    icici_lombard_raw = {
        "id": f"test-icicigi-{tag}", "seq_id": f"seq-gi-{tag}", "symbol": "ICICIGI", "_kind": None,
        "attchmntText": "ICICI Lombard General Insurance Company Limited allotment of shares.", "sort_date": "2026-08-24",
    }
    try:
        async with AsyncSessionLocal() as db:
            await capture_raw_evidence(db, "NSE", [(icici_bank_raw, "good"), (icici_lombard_raw, "good")])

        async with AsyncSessionLocal() as db:
            bank_link = (await db.execute(
                select(EvidenceEntityLink).join(RawEvidence, EvidenceEntityLink.raw_evidence_id == RawEvidence.id)
                .where(RawEvidence.evidence_key == f"nse:nse-seq-bank-{tag}")
            )).scalar_one()
            gi_link = (await db.execute(
                select(EvidenceEntityLink).join(RawEvidence, EvidenceEntityLink.raw_evidence_id == RawEvidence.id)
                .where(RawEvidence.evidence_key == f"nse:nse-seq-gi-{tag}")
            )).scalar_one()

        assert bank_link.entity_id != gi_link.entity_id, "ICICI Bank and ICICI Lombard are different real companies -- must never resolve to the same entity_id"
    finally:
        await _cleanup(f"nse:nse-seq-bank-{tag}")
        await _cleanup(f"nse:nse-seq-gi-{tag}")


@pytest.mark.asyncio
async def test_rss_evidence_mentioning_icici_is_never_linked(real_entities, source_id):
    """The other two real adversarial cases from the audit -- a Senores
    Pharmaceuticals filing that only names ICICI Bank as its lender, and
    an 'ICICI Direct'-bylined market-holiday notice -- were both RSS-
    class items in the real data (the byline one genuinely was RSS; the
    Senores-mentions-ICICI-as-lender case is itself an NSE filing, but
    about SENORES, not ICICIBANK -- covered by the next test). This test
    proves the simpler, structural half of that safety property: RSS
    evidence is never linked at all, regardless of what its title
    mentions, because linking is scoped to NSE only -- there is no title/
    keyword matching code path that could ever produce a wrong link from
    RSS content."""
    tag = _tag()
    raw = {
        "id": f"rss-icici-mention-{tag}",
        "headline": "NSE and BSE to Remain Open — ICICI Direct",
        "summary": "Market holiday calendar notice.",
        "source": "Economic Times", "url": "https://x", "published_at": "2026-08-24",
    }
    try:
        async with AsyncSessionLocal() as db:
            result = await capture_raw_evidence(db, "RSS", [(raw, "good")])
        assert result["written"] == 1

        async with AsyncSessionLocal() as db:
            links = (await db.execute(
                select(EvidenceEntityLink).join(RawEvidence, EvidenceEntityLink.raw_evidence_id == RawEvidence.id)
                .where(RawEvidence.evidence_key == f"rss:{raw['id']}")
            )).scalars().all()
        assert links == [], "RSS evidence must never be linked, regardless of what its title/content mentions"
    finally:
        await _cleanup(f"rss:{raw['id']}")


@pytest.mark.asyncio
async def test_nse_filing_about_a_different_company_that_merely_names_icici_bank_is_not_linked_to_icicibank(real_entities, source_id):
    """The real Senores Pharmaceuticals case: an NSE filing whose own
    `symbol` is SENORES (a company not in this test's real-entity
    fixture, so it resolves UNRESOLVED), even though its text body names
    ICICI Bank as a lender. Must never link to ICICIBANK just because the
    text mentions it -- resolution goes through the filing's own real
    `symbol` field, never free-text matching."""
    tag = _tag()
    raw = {
        "id": f"test-senores-{tag}", "seq_id": f"seq-senores-{tag}", "symbol": "SENORES", "_kind": None,
        "attchmntText": "Senores Pharmaceuticals Limited corporate guarantee for credit facilities from ICICI Bank Limited.",
        "sort_date": "2026-08-24",
    }
    try:
        async with AsyncSessionLocal() as db:
            result = await capture_raw_evidence(db, "NSE", [(raw, "good")])
        assert result["written"] == 1, "the filing itself must still be captured -- an unresolvable symbol must never block capture"

        async with AsyncSessionLocal() as db:
            links = (await db.execute(
                select(EvidenceEntityLink).join(RawEvidence, EvidenceEntityLink.raw_evidence_id == RawEvidence.id)
                .where(RawEvidence.evidence_key == f"nse:nse-seq-senores-{tag}")
            )).scalars().all()
        assert links == [], "SENORES is unresolved in this test's real-entity set -- must stay unlinked, never fall back to matching ICICI Bank from the body text"
    finally:
        await _cleanup(f"nse:nse-seq-senores-{tag}")


@pytest.mark.asyncio
async def test_unresolvable_symbol_leaves_evidence_captured_but_unlinked(source_id):
    """No real_entities fixture here on purpose -- an empty Company
    Master must never crash capture, just leave everything unlinked."""
    tag = _tag()
    raw = {"id": f"test-unknown-{tag}", "seq_id": f"seq-unknown-{tag}", "symbol": "TOTALLYFAKESYMBOL", "_kind": None,
           "attchmntText": "Some filing.", "sort_date": "2026-08-24"}
    try:
        async with AsyncSessionLocal() as db:
            result = await capture_raw_evidence(db, "NSE", [(raw, "good")])
        assert result["written"] == 1, "capture must succeed even when linking can't"

        async with AsyncSessionLocal() as db:
            links = (await db.execute(
                select(EvidenceEntityLink).join(RawEvidence, EvidenceEntityLink.raw_evidence_id == RawEvidence.id)
                .where(RawEvidence.evidence_key == f"nse:nse-seq-unknown-{tag}")
            )).scalars().all()
        assert links == []
    finally:
        await _cleanup(f"nse:nse-seq-unknown-{tag}")


# ── Backfill ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_backfill_links_existing_unlinked_nse_rows_deterministically(real_entities, source_id):
    tag = _tag()
    now = datetime.now(timezone.utc)
    raw = {"id": f"test-backfill-{tag}", "seq_id": f"seq-backfill-{tag}", "symbol": "ICICIBANK", "_kind": None}
    try:
        # Insert directly, bypassing capture_raw_evidence -- simulates a
        # row that was captured before this feature existed.
        async with AsyncSessionLocal() as db:
            db.add(RawEvidence(
                id=str(uuid.uuid4()), evidence_key=f"nse:seq-backfill-{tag}", payload_hash="x" * 64,
                source_id=source_id, source_type="nse", external_id=f"seq-backfill-{tag}",
                title="ICICI Bank filing", published_at=None, observed_at=now, ingested_at=now,
                raw_payload=json.dumps(raw), mime_type="application/json", quality="good",
            ))
            await db.commit()

        async with AsyncSessionLocal() as db:
            links_before = (await db.execute(
                select(EvidenceEntityLink).join(RawEvidence, EvidenceEntityLink.raw_evidence_id == RawEvidence.id)
                .where(RawEvidence.evidence_key == f"nse:seq-backfill-{tag}")
            )).scalars().all()
        assert links_before == [], "sanity: no link exists before the backfill runs"

        async with AsyncSessionLocal() as db:
            summary = await backfill_nse_entity_links(db)
        assert summary["linked"] >= 1

        async with AsyncSessionLocal() as db:
            links_after = (await db.execute(
                select(EvidenceEntityLink).join(RawEvidence, EvidenceEntityLink.raw_evidence_id == RawEvidence.id)
                .where(RawEvidence.evidence_key == f"nse:seq-backfill-{tag}")
            )).scalars().all()
        assert len(links_after) == 1
    finally:
        await _cleanup(f"nse:seq-backfill-{tag}")


@pytest.mark.asyncio
async def test_rerunning_backfill_never_creates_a_duplicate_link(real_entities, source_id):
    tag = _tag()
    now = datetime.now(timezone.utc)
    raw = {"id": f"test-rerun-{tag}", "seq_id": f"seq-rerun-{tag}", "symbol": "ICICIBANK", "_kind": None}
    try:
        async with AsyncSessionLocal() as db:
            db.add(RawEvidence(
                id=str(uuid.uuid4()), evidence_key=f"nse:seq-rerun-{tag}", payload_hash="y" * 64,
                source_id=source_id, source_type="nse", external_id=f"seq-rerun-{tag}",
                title="ICICI Bank filing", published_at=None, observed_at=now, ingested_at=now,
                raw_payload=json.dumps(raw), mime_type="application/json", quality="good",
            ))
            await db.commit()

        async with AsyncSessionLocal() as db:
            await backfill_nse_entity_links(db)
        async with AsyncSessionLocal() as db:
            second = await backfill_nse_entity_links(db)
        assert second["linked"] == 0, "the second run must find nothing left to link -- proves already_linked filtering works"

        async with AsyncSessionLocal() as db:
            links = (await db.execute(
                select(EvidenceEntityLink).join(RawEvidence, EvidenceEntityLink.raw_evidence_id == RawEvidence.id)
                .where(RawEvidence.evidence_key == f"nse:seq-rerun-{tag}")
            )).scalars().all()
        assert len(links) == 1, "exactly one link, never a duplicate on rerun"
    finally:
        await _cleanup(f"nse:seq-rerun-{tag}")
