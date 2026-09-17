"""
SourceDocument capture — Deep Filing Evidence Phase 1B (owner design,
2026-09-17). Deterministic fetch + hash + extract only -- no LLM
anywhere in this module, no interpretation of the extracted text. The
raw extracted filing text IS the evidence this module produces; turning
it into a structured fact is a separate, later concern (Phase 1C).

Not wired into any ingestion cycle or C1-C8.5 call site by this commit
-- this is the standalone substrate primitive, callable on demand.
Fetching a specific announcement's attachment stays an explicit,
per-evidence-item decision for now, matching the owner's "don't modify
C1-C8.5 merely because new evidence exists" instruction.

Real operational bounds (owner instruction), all enforced before or
during parsing, never after silently succeeding:
  - MIME validation is on the real byte signature (%PDF-), never the
    server's own Content-Type header, which is reported but not trusted.
  - _MAX_BYTES / _MAX_PAGES are hard refusals (SIZE_LIMIT_EXCEEDED), not
    a silent truncation to "the first N pages" -- an oversized document
    is a real, honest gap to report, not a partial fact to guess from.
  - A real HTTP/network failure is FETCH_FAILED, distinct from a
    genuine "this document has no usable text" (TEXT_UNAVAILABLE) --
    same "source truth is not quality truth" split financial_fact.py
    already established.
  - No OCR: a document that parses fine but yields ~no real text stays
    TEXT_UNAVAILABLE.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from uuid import uuid4

import httpx
import pypdf
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.source_document import (
    EXTRACTED, FETCH_FAILED, PARSE_FAILED, SIZE_LIMIT_EXCEEDED, TEXT_UNAVAILABLE,
    UNSUPPORTED_MIME, SourceDocument,
)

log = structlog.get_logger(__name__)

_MAX_BYTES = 20 * 1024 * 1024   # real specimens sampled topped out at ~8MB (SHIPROCKET); generous real headroom, not unbounded
_MAX_PAGES = 50                 # real specimens sampled were 1-7 pages; generous real headroom
_TIMEOUT_SECONDS = 25
_PDF_MAGIC = b"%PDF-"
_MIN_REAL_TEXT_CHARS = 40       # below this, a "successfully parsed" PDF is treated as carrying no real text (scanned/image), not a genuine short document
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; InvestGridsBot/1.0)"}


def _extraction_method_version() -> str:
    return pypdf.__version__


def _extract_pages(content: bytes) -> list[str]:
    from io import BytesIO
    reader = pypdf.PdfReader(BytesIO(content))
    if len(reader.pages) > _MAX_PAGES:
        raise _SizeLimitExceeded(f"page_count={len(reader.pages)} exceeds _MAX_PAGES={_MAX_PAGES}")
    return [page.extract_text() or "" for page in reader.pages]


class _SizeLimitExceeded(Exception):
    pass


async def fetch_source_document(db: AsyncSession, *, raw_evidence_id: str, url: str) -> SourceDocument:
    """The one real entry point. Always returns a persisted SourceDocument
    row (committed) describing what happened -- success or a specific,
    honest failure status -- never raises for a real-world fetch/parse
    problem (only for a genuine programming error). A byte-identical
    re-fetch of a URL already recorded for this raw_evidence_id returns
    the EXISTING row rather than writing a duplicate."""
    now = datetime.now(timezone.utc)

    # NSE's archive host (nsearchives.nseindia.com) does not respond to
    # HEAD (confirmed live -- times out even from production), so there
    # is no cheap pre-download size check available; _MAX_BYTES is
    # enforced DURING download instead, via streaming -- an oversized
    # response is aborted as soon as the cap is crossed, never fully
    # pulled into memory first.
    try:
        async with httpx.AsyncClient(headers=_HEADERS, timeout=_TIMEOUT_SECONDS, follow_redirects=True) as client:
            async with client.stream("GET", url) as resp:
                resp.raise_for_status()
                mime_type = resp.headers.get("content-type")
                chunks = bytearray()
                async for chunk in resp.aiter_bytes():
                    chunks.extend(chunk)
                    if len(chunks) > _MAX_BYTES:
                        return await _persist(db, raw_evidence_id, url, now, status=SIZE_LIMIT_EXCEEDED,
                                               mime_type=mime_type,
                                               error_detail=f"response exceeded _MAX_BYTES={_MAX_BYTES} during download")
                content = bytes(chunks)
    except Exception as exc:
        log.warning("warehouse.source_document.fetch_failed", raw_evidence_id=raw_evidence_id, url=url, error=str(exc)[:200])
        return await _persist(db, raw_evidence_id, url, now, status=FETCH_FAILED, error_detail=str(exc)[:300])

    content_hash = hashlib.sha256(content).hexdigest()

    existing = (await db.execute(
        select(SourceDocument).where(
            SourceDocument.raw_evidence_id == raw_evidence_id, SourceDocument.content_hash == content_hash,
        ).limit(1)
    )).scalar_one_or_none()
    if existing is not None:
        log.info("warehouse.source_document.suppressed_duplicate", raw_evidence_id=raw_evidence_id, url=url)
        return existing

    if not content.startswith(_PDF_MAGIC):
        return await _persist(db, raw_evidence_id, url, now, status=UNSUPPORTED_MIME,
                               content_hash=content_hash, byte_size=len(content), mime_type=mime_type,
                               error_detail="downloaded bytes do not carry a real PDF signature (%PDF-)")

    try:
        page_texts = _extract_pages(content)
    except _SizeLimitExceeded as exc:
        return await _persist(db, raw_evidence_id, url, now, status=SIZE_LIMIT_EXCEEDED,
                               content_hash=content_hash, byte_size=len(content), mime_type=mime_type,
                               error_detail=str(exc))
    except Exception as exc:
        log.warning("warehouse.source_document.parse_failed", raw_evidence_id=raw_evidence_id, url=url, error=str(exc)[:200])
        return await _persist(db, raw_evidence_id, url, now, status=PARSE_FAILED,
                               content_hash=content_hash, byte_size=len(content), mime_type=mime_type,
                               error_detail=str(exc)[:300])

    real_text_chars = sum(len(t.strip()) for t in page_texts)
    if real_text_chars < _MIN_REAL_TEXT_CHARS:
        return await _persist(db, raw_evidence_id, url, now, status=TEXT_UNAVAILABLE,
                               content_hash=content_hash, byte_size=len(content), mime_type=mime_type,
                               page_count=len(page_texts))

    return await _persist(db, raw_evidence_id, url, now, status=EXTRACTED,
                           content_hash=content_hash, byte_size=len(content), mime_type=mime_type,
                           page_count=len(page_texts), page_texts=page_texts)


async def _persist(
    db: AsyncSession, raw_evidence_id: str, url: str, retrieved_at: datetime, *, status: str,
    content_hash: str | None = None, byte_size: int | None = None, mime_type: str | None = None,
    page_count: int | None = None, page_texts: list[str] | None = None, error_detail: str | None = None,
) -> SourceDocument:
    doc = SourceDocument(
        id=str(uuid4()), raw_evidence_id=raw_evidence_id, canonical_url=url,
        content_hash=content_hash, byte_size=byte_size, mime_type=mime_type,
        retrieved_at=retrieved_at, extraction_status=status,
        extraction_method="pypdf" if status in (EXTRACTED, TEXT_UNAVAILABLE) else None,
        extraction_method_version=_extraction_method_version() if status in (EXTRACTED, TEXT_UNAVAILABLE) else None,
        error_detail=error_detail, page_count=page_count,
        page_texts_json=json.dumps(page_texts) if page_texts is not None else None,
    )
    db.add(doc)
    try:
        await db.commit()
    except Exception as exc:
        await db.rollback()
        log.warning("warehouse.source_document.commit_failed", raw_evidence_id=raw_evidence_id, error=str(exc)[:200])
        raise
    log.info("warehouse.source_document.captured", raw_evidence_id=raw_evidence_id, url=url,
              status=status, byte_size=byte_size, page_count=page_count)
    return doc
