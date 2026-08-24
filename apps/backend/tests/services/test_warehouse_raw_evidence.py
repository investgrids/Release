"""
Phase 1B Batch 2 — Raw Evidence verification (owner instruction,
2026-08-23). Real fetches against RSS/NSE/RBI/PIB/SEBI/Fed were already
run manually and inspected directly (documented in the design doc, not
re-run here to avoid hammering live external sources on every test
run) — those proved cases #1 (identical re-fetch suppressed, real:
NSE 60/60 and RSS 95/95 suppressed on a second real fetch), #3 (NSE's
real seq_id -> deterministic nse-<seq_id> identity), #6 (news_articles/
events/government_policies grew by exactly the logged deltas, unmodified
existing behavior), #8 (idempotent across the two real runs), #9
(capture_raw_evidence's own return dict gives real per-source counts,
confirmed in the real log output).

This file covers what's better proven deterministically than against
live, uncontrollable external sources: #2 (version history on a genuine
content change), #4 (no reliable publication timestamp), #5 (parse
failure / filtered item still stored honestly), #7 (structural
no-API-route guard), plus the underlying identity/hash functions
directly.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import delete, func, select

from app.db.session import AsyncSessionLocal
from app.db.models.raw_evidence import RawEvidence
from app.services.warehouse.raw_evidence import (
    _content_hash, _extract_external_id, _extract_published_at_raw,
    _parse_published_at, capture_raw_evidence,
)


async def _cleanup(evidence_key_prefix: str) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(delete(RawEvidence).where(RawEvidence.evidence_key.like(f"{evidence_key_prefix}%")))
        await db.commit()


@pytest.mark.asyncio
async def test_same_stable_item_changed_payload_creates_a_new_version():
    """Case #2: same evidence_key, different payload_hash -> two rows,
    an immutable version history, never an overwrite."""
    ext_id = "test-fed-versioning-1"
    raw_v1 = {"id": ext_id, "headline": "FOMC statement", "summary": "Original text.", "source": "Fed", "url": "https://x", "published_at": "2026-08-01"}
    raw_v2 = {"id": ext_id, "headline": "FOMC statement", "summary": "Revised text — a correction was issued.", "source": "Fed", "url": "https://x", "published_at": "2026-08-01"}

    try:
        async with AsyncSessionLocal() as db:
            r1 = await capture_raw_evidence(db, "Fed", [(raw_v1, "good")])
        assert r1["written"] == 1

        async with AsyncSessionLocal() as db:
            r2 = await capture_raw_evidence(db, "Fed", [(raw_v2, "good")])
        assert r2["written"] == 1, "a genuine content change must produce a new row, not be suppressed"

        # Identical re-fetch of v2 must now suppress.
        async with AsyncSessionLocal() as db:
            r3 = await capture_raw_evidence(db, "Fed", [(raw_v2, "good")])
        assert r3["written"] == 0 and r3["suppressed_duplicate"] == 1

        async with AsyncSessionLocal() as db:
            rows = (await db.execute(
                select(RawEvidence.payload_hash).where(RawEvidence.evidence_key == f"fed:{ext_id}")
            )).scalars().all()
        assert len(rows) == 2, "exactly two immutable versions under one stable evidence_key"
        assert len(set(rows)) == 2, "the two versions must have distinct payload hashes"
    finally:
        await _cleanup("fed:test-fed-versioning")


@pytest.mark.asyncio
async def test_source_without_reliable_publication_timestamp_stays_null():
    """Case #4: published_at=NULL when unparseable/absent; observed_at
    always real."""
    raw = {"id": "test-no-pubdate", "headline": "No date item", "summary": "x", "source": "RBI", "url": "https://x", "published_at": ""}
    try:
        async with AsyncSessionLocal() as db:
            await capture_raw_evidence(db, "RBI", [(raw, "good")])

        async with AsyncSessionLocal() as db:
            row = (await db.execute(
                select(RawEvidence.published_at, RawEvidence.observed_at).where(RawEvidence.evidence_key == "rbi:test-no-pubdate")
            )).first()
        assert row.published_at is None
        assert row.observed_at is not None
        assert isinstance(row.observed_at, datetime)
    finally:
        await _cleanup("rbi:test-no-pubdate")


def test_published_at_parser_never_accepts_a_relative_string():
    """Direct unit check on the exact bug class that broke
    news_articles.published_at — '2h ago' and similar must never parse
    to a fake datetime."""
    assert _parse_published_at("2h ago") is None
    assert _parse_published_at("1d ago") is None
    assert _parse_published_at("") is None
    assert _parse_published_at(None) is None
    assert _parse_published_at("�") is None  # the mojibake character found live in news_articles
    assert _parse_published_at("2026-08-23") is not None
    assert _parse_published_at("2026-08-23 09:52:01") is not None


@pytest.mark.asyncio
async def test_filtered_and_invalid_items_are_stored_with_honest_quality_not_discarded():
    """Case #5: a parse failure or filtered item must still be captured
    for auditability, never silently vanish."""
    good = {"id": "test-quality-good", "headline": "Real headline", "summary": "x", "source": "SEBI", "url": "https://x", "published_at": "2026-08-20"}
    filtered = {"id": "test-quality-filtered", "headline": "", "summary": "x", "source": "SEBI", "url": "https://x", "published_at": "2026-08-20"}
    try:
        async with AsyncSessionLocal() as db:
            result = await capture_raw_evidence(db, "SEBI", [(good, "good"), (filtered, "filtered")])
        assert result["written"] == 2, "both the good AND the filtered item must be persisted"

        async with AsyncSessionLocal() as db:
            rows = (await db.execute(
                select(RawEvidence.evidence_key, RawEvidence.quality).where(
                    RawEvidence.evidence_key.in_(["sebi:test-quality-good", "sebi:test-quality-filtered"])
                )
            )).all()
        by_key = {k: q for k, q in rows}
        assert by_key["sebi:test-quality-good"] == "good"
        assert by_key["sebi:test-quality-filtered"] == "filtered"
    finally:
        await _cleanup("sebi:test-quality")


def test_no_api_route_imports_raw_evidence_capture():
    """Case #7: no page/API request writes RawEvidence — structural
    guard, same pattern as the MarketObservation equivalent."""
    import pathlib
    api_dir = pathlib.Path(__file__).resolve().parents[2] / "app" / "api"
    offending: list[str] = []
    for path in api_dir.rglob("*.py"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "capture_raw_evidence" in text:
            offending.append(str(path))
    assert offending == [], f"capture_raw_evidence must never be imported from an API route file: {offending}"


def test_content_hash_is_stable_and_order_independent():
    d1 = {"a": 1, "b": 2}
    d2 = {"b": 2, "a": 1}
    assert _content_hash(d1) == _content_hash(d2)
    d3 = {"a": 1, "b": 3}
    assert _content_hash(d1) != _content_hash(d3)


def test_nse_external_id_uses_the_real_seq_id_field():
    """Regression guard for the real bug found live 2026-08-23: NSE's raw
    dict has no 'an_no' field in practice (a pre-existing dead reference
    in nse_provider.py's own normalize path) — the real, stable field is
    seq_id."""
    raw = {"seq_id": "106753642", "desc": "Updates"}
    assert _extract_external_id("NSE", raw) == "nse-106753642"
    assert _extract_external_id("NSE", {"desc": "Updates"}) is None  # honest None when seq_id is genuinely absent


def test_nse_published_at_uses_sort_date_not_published_at_key():
    raw = {"sort_date": "2026-08-23 09:52:01"}
    assert _extract_published_at_raw("NSE", raw) == "2026-08-23 09:52:01"
    board = {"_kind": "board_meeting", "bm_timestamp": "23-Aug-2026 09:29:52"}
    assert _extract_published_at_raw("NSE", board) == "23-Aug-2026 09:29:52"
    assert _parse_published_at(_extract_published_at_raw("NSE", board)) is not None
