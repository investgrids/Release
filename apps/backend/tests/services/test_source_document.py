"""
Deep Filing Evidence Phase 1A/1B — real tests for source_document.py.
Network-dependent paths (real extraction, dedup suppression) are real
live tests against the actual NSE archive, matching this codebase's
existing convention for genuinely external fetches (mospi_source.py,
nse_xbrl_client.py). Safety-bound logic (MIME rejection, fetch
failure, size/page limits, no-OCR text-unavailable) is tested fully
offline via a mocked httpx stream and real pypdf-constructed PDFs --
no hand-written PDF byte strings, no network required for those.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import delete, select

from app.db.models.raw_evidence import RawEvidence
from app.db.models.source_document import (
    EXTRACTED, FETCH_FAILED, PARSE_FAILED, SIZE_LIMIT_EXCEEDED, TEXT_UNAVAILABLE,
    UNSUPPORTED_MIME, SourceDocument,
)
from app.db.models.source_registry import Source
from app.db.session import AsyncSessionLocal
from app.services.warehouse import source_document as sd


async def _seed_raw_evidence(db, evidence_key: str) -> str:
    """A synthetic Source + RawEvidence pair, self-contained -- never
    assumes source_registry_seed.py's real rows exist in whatever DB
    this suite happens to run against (test isolation precedent from
    test_warehouse_read_service.py)."""
    source_id = f"test_source_{uuid.uuid4().hex[:8]}"
    db.add(Source(id=source_id, name="Test Source", source_type="api", collection_method="test"))
    await db.commit()
    row_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    db.add(RawEvidence(
        id=row_id, evidence_key=evidence_key, payload_hash="x",
        source_id=source_id, source_type="nse",
        observed_at=now, ingested_at=now, mime_type="application/json", quality="good",
    ))
    await db.commit()
    return row_id


async def _cleanup(raw_evidence_ids: list[str]) -> None:
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(select(RawEvidence.source_id).where(RawEvidence.id.in_(raw_evidence_ids)))).scalars().all()
        await db.execute(delete(SourceDocument).where(SourceDocument.raw_evidence_id.in_(raw_evidence_ids)))
        await db.execute(delete(RawEvidence).where(RawEvidence.id.in_(raw_evidence_ids)))
        if rows:
            await db.execute(delete(Source).where(Source.id.in_(rows)))
        await db.commit()


def _blank_pdf_bytes(page_count: int) -> bytes:
    from io import BytesIO
    from pypdf import PdfWriter
    writer = PdfWriter()
    for _ in range(page_count):
        writer.add_blank_page(width=200, height=200)
    buf = BytesIO()
    writer.write(buf)
    return buf.getvalue()


class _FakeStreamResponse:
    def __init__(self, chunks, content_type="application/pdf", status_error=None):
        self._chunks = chunks
        self.headers = {"content-type": content_type}
        self._status_error = status_error

    def raise_for_status(self):
        if self._status_error:
            raise self._status_error

    async def aiter_bytes(self):
        for c in self._chunks:
            yield c


class _FakeStreamCtx:
    def __init__(self, response):
        self._response = response

    async def __aenter__(self):
        return self._response

    async def __aexit__(self, *a):
        return False


def _mock_client(chunks=None, stream_raises=None, status_error=None, content_type="application/pdf"):
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.__aexit__.return_value = False
    if stream_raises is not None:
        client.stream = MagicMock(side_effect=stream_raises)
    else:
        resp = _FakeStreamResponse(chunks or [b""], content_type=content_type, status_error=status_error)
        client.stream = MagicMock(return_value=_FakeStreamCtx(resp))
    return client


# ── Offline: safety-bound logic ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_fetch_failure_is_recorded_as_fetch_failed_never_raises():
    async with AsyncSessionLocal() as db:
        raw_evidence_id = await _seed_raw_evidence(db, "test:fetch-fail")
        try:
            with patch("httpx.AsyncClient", return_value=_mock_client(stream_raises=ConnectionError("refused"))):
                doc = await sd.fetch_source_document(db, raw_evidence_id=raw_evidence_id, url="https://example.test/x.pdf")
            assert doc.extraction_status == FETCH_FAILED
            assert doc.content_hash is None
            assert "refused" in (doc.error_detail or "")
        finally:
            await _cleanup([raw_evidence_id])


@pytest.mark.asyncio
async def test_http_error_status_is_recorded_as_fetch_failed():
    async with AsyncSessionLocal() as db:
        raw_evidence_id = await _seed_raw_evidence(db, "test:http-error")
        try:
            import httpx
            err = httpx.HTTPStatusError("404", request=MagicMock(), response=MagicMock(status_code=404))
            with patch("httpx.AsyncClient", return_value=_mock_client(chunks=[b""], status_error=err)):
                doc = await sd.fetch_source_document(db, raw_evidence_id=raw_evidence_id, url="https://example.test/missing.pdf")
            assert doc.extraction_status == FETCH_FAILED
        finally:
            await _cleanup([raw_evidence_id])


@pytest.mark.asyncio
async def test_non_pdf_bytes_are_rejected_as_unsupported_mime_never_parsed():
    """MIME validation is on the real byte signature, never the server's
    Content-Type header -- a server claiming application/pdf while
    serving HTML must still be rejected before ever reaching pypdf."""
    async with AsyncSessionLocal() as db:
        raw_evidence_id = await _seed_raw_evidence(db, "test:not-a-pdf")
        try:
            with patch("httpx.AsyncClient", return_value=_mock_client(chunks=[b"<html>not a pdf</html>"], content_type="application/pdf")):
                doc = await sd.fetch_source_document(db, raw_evidence_id=raw_evidence_id, url="https://example.test/fake.pdf")
            assert doc.extraction_status == UNSUPPORTED_MIME
            assert doc.content_hash is not None
            assert doc.page_count is None
        finally:
            await _cleanup([raw_evidence_id])


@pytest.mark.asyncio
async def test_oversized_response_is_rejected_during_streaming_not_after(monkeypatch):
    monkeypatch.setattr(sd, "_MAX_BYTES", 10)
    async with AsyncSessionLocal() as db:
        raw_evidence_id = await _seed_raw_evidence(db, "test:oversized")
        try:
            big_chunk = b"%PDF-" + b"x" * 100
            with patch("httpx.AsyncClient", return_value=_mock_client(chunks=[big_chunk])):
                doc = await sd.fetch_source_document(db, raw_evidence_id=raw_evidence_id, url="https://example.test/huge.pdf")
            assert doc.extraction_status == SIZE_LIMIT_EXCEEDED
            assert doc.content_hash is None
        finally:
            await _cleanup([raw_evidence_id])


@pytest.mark.asyncio
async def test_blank_page_pdf_with_no_real_text_is_text_unavailable_no_ocr():
    """Real pypdf-constructed PDF, genuinely valid, genuinely zero
    extractable text -- confirms the no-OCR contract: this must be
    TEXT_UNAVAILABLE, never a crash, never a fabricated summary."""
    async with AsyncSessionLocal() as db:
        raw_evidence_id = await _seed_raw_evidence(db, "test:blank")
        try:
            blank = _blank_pdf_bytes(2)
            with patch("httpx.AsyncClient", return_value=_mock_client(chunks=[blank])):
                doc = await sd.fetch_source_document(db, raw_evidence_id=raw_evidence_id, url="https://example.test/blank.pdf")
            assert doc.extraction_status == TEXT_UNAVAILABLE
            assert doc.page_count == 2
            assert doc.page_texts_json is None
        finally:
            await _cleanup([raw_evidence_id])


@pytest.mark.asyncio
async def test_page_count_beyond_max_pages_is_rejected_not_truncated(monkeypatch):
    monkeypatch.setattr(sd, "_MAX_PAGES", 2)
    async with AsyncSessionLocal() as db:
        raw_evidence_id = await _seed_raw_evidence(db, "test:too-many-pages")
        try:
            many_pages = _blank_pdf_bytes(5)
            with patch("httpx.AsyncClient", return_value=_mock_client(chunks=[many_pages])):
                doc = await sd.fetch_source_document(db, raw_evidence_id=raw_evidence_id, url="https://example.test/manypages.pdf")
            assert doc.extraction_status == SIZE_LIMIT_EXCEEDED
            assert doc.page_texts_json is None
        finally:
            await _cleanup([raw_evidence_id])


@pytest.mark.asyncio
async def test_corrupt_pdf_bytes_that_pass_the_magic_check_are_parse_failed():
    """Passes the %PDF- signature check but is otherwise garbage --
    pypdf must raise, and that must surface as PARSE_FAILED, not an
    unhandled exception."""
    async with AsyncSessionLocal() as db:
        raw_evidence_id = await _seed_raw_evidence(db, "test:corrupt")
        try:
            corrupt = b"%PDF-1.4\n" + b"\x00\x01\x02garbage not a real pdf structure" * 5
            with patch("httpx.AsyncClient", return_value=_mock_client(chunks=[corrupt])):
                doc = await sd.fetch_source_document(db, raw_evidence_id=raw_evidence_id, url="https://example.test/corrupt.pdf")
            assert doc.extraction_status == PARSE_FAILED
        finally:
            await _cleanup([raw_evidence_id])


@pytest.mark.asyncio
async def test_byte_identical_refetch_is_suppressed_not_duplicated():
    async with AsyncSessionLocal() as db:
        raw_evidence_id = await _seed_raw_evidence(db, "test:dedup")
        try:
            blank = _blank_pdf_bytes(1)
            with patch("httpx.AsyncClient", return_value=_mock_client(chunks=[blank])):
                first = await sd.fetch_source_document(db, raw_evidence_id=raw_evidence_id, url="https://example.test/same.pdf")
                second = await sd.fetch_source_document(db, raw_evidence_id=raw_evidence_id, url="https://example.test/same.pdf")
            assert first.id == second.id

            rows = (await db.execute(
                select(SourceDocument).where(SourceDocument.raw_evidence_id == raw_evidence_id)
            )).scalars().all()
            assert len(rows) == 1
        finally:
            await _cleanup([raw_evidence_id])


@pytest.mark.asyncio
async def test_changed_content_at_the_same_url_becomes_a_new_version_never_an_overwrite():
    """The core Phase 1A invariant: NSE re-serving different bytes from
    the same URL must produce a NEW immutable row, never silently
    overwrite the old one -- both real historical versions must remain
    queryable."""
    async with AsyncSessionLocal() as db:
        raw_evidence_id = await _seed_raw_evidence(db, "test:versioned")
        try:
            first_bytes = _blank_pdf_bytes(1)
            second_bytes = _blank_pdf_bytes(3)  # genuinely different content -> different hash
            with patch("httpx.AsyncClient", return_value=_mock_client(chunks=[first_bytes])):
                first = await sd.fetch_source_document(db, raw_evidence_id=raw_evidence_id, url="https://example.test/same.pdf")
            with patch("httpx.AsyncClient", return_value=_mock_client(chunks=[second_bytes])):
                second = await sd.fetch_source_document(db, raw_evidence_id=raw_evidence_id, url="https://example.test/same.pdf")

            assert first.id != second.id
            assert first.content_hash != second.content_hash
            assert first.page_count == 1
            assert second.page_count == 3

            rows = (await db.execute(
                select(SourceDocument).where(SourceDocument.raw_evidence_id == raw_evidence_id)
            )).scalars().all()
            assert len(rows) == 2  # both real versions preserved, neither overwritten
            assert {r.id for r in rows} == {first.id, second.id}
        finally:
            await _cleanup([raw_evidence_id])


# ── Real live tests: real NSE archive fetch, real extraction ────────────

@pytest.mark.asyncio
async def test_real_live_zodiac_pdf_is_extracted_with_real_investor_facts():
    """Real production specimen (Deep Filing Evidence Source Reality
    Audit, 2026-09-17): confirms the exact fact the audit found -- the
    PDF contains the subsidiary/business detail the bare NSE title
    lacks, and it is real extractable text, no OCR needed."""
    async with AsyncSessionLocal() as db:
        raw_evidence_id = await _seed_raw_evidence(db, "test:zodiac-live")
        try:
            url = "https://nsearchives.nseindia.com/corporate/ZODIAC_15092026141846_Reg_30_Final.pdf"
            doc = await sd.fetch_source_document(db, raw_evidence_id=raw_evidence_id, url=url)
            assert doc.extraction_status == EXTRACTED
            assert doc.page_count and doc.page_count >= 1
            pages = json.loads(doc.page_texts_json)
            full_text = " ".join(pages).lower()
            assert "subsidiary" in full_text or "incorporat" in full_text
        finally:
            await _cleanup([raw_evidence_id])


@pytest.mark.asyncio
async def test_real_live_refetch_of_the_same_url_is_suppressed():
    async with AsyncSessionLocal() as db:
        raw_evidence_id = await _seed_raw_evidence(db, "test:zodiac-live-dedup")
        try:
            url = "https://nsearchives.nseindia.com/corporate/ZODIAC_15092026141846_Reg_30_Final.pdf"
            first = await sd.fetch_source_document(db, raw_evidence_id=raw_evidence_id, url=url)
            second = await sd.fetch_source_document(db, raw_evidence_id=raw_evidence_id, url=url)
            assert first.id == second.id
        finally:
            await _cleanup([raw_evidence_id])
