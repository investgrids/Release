"""
BSE availability health probe — CR-2A (2026-09-13).

Deliberately separate from ingestion. BSE's announcement API is
DEFERRED_BOT_PROTECTED (see app/providers/bse_provider.py's module
docstring for the full investigation: Akamai bot-wall, confirmed
unbeatable with header spoofing, cookie warm-up, or a genuine Chrome
TLS/JA3 fingerprint via curl_cffi). Removed entirely from the hot
ingestion path (job_ingest_news, company_announcements_service) — every
call there was a guaranteed failure, 144 times/day combined.

This probe answers exactly one question once a day: "is the BSE
announcements endpoint reachable and returning real JSON right now?" It
never parses individual announcements into domain objects, never
persists a CompanyAnnouncement/Event/NewsArticle row, and never
retriggers ingestion — a successful response here is an operational
signal to reassess BSE support as its own deliberate decision, not an
automatic re-enable.
"""
from __future__ import annotations

import time

import structlog

from app.services import source_health

log = structlog.get_logger(__name__)

_URL = "https://api.bseindia.com/BseIndiaAPI/api/AnnGetData/w?strCat=-1&strPrevDate=&strScrip=&strSearch=&strToDate=&strType=C&subcategory=-1"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
    "Referer": "https://www.bseindia.com/",
}


async def check_bse_health() -> None:
    """Probes BSE's announcements endpoint once. Records the result via
    the same source_health surface every other provider already reports
    to (get_source_health("BSE") reflects this, not a separate metric).
    Never raises, never persists announcement data."""
    import httpx

    start = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(_URL, headers=_HEADERS)
    except Exception as exc:
        source_health.record_fetch(
            "BSE", success=False, failure_kind="http",
            latency_ms=(time.monotonic() - start) * 1000, error=str(exc)[:500],
        )
        log.info("bse.health_check.unreachable", error=str(exc)[:200])
        return

    elapsed_ms = (time.monotonic() - start) * 1000

    if r.status_code != 200:
        source_health.record_fetch(
            "BSE", success=False, failure_kind="http",
            latency_ms=elapsed_ms, error=f"http {r.status_code}",
        )
        log.info("bse.health_check.blocked", status_code=r.status_code)
        return

    # The known current failure mode: a 200 whose body is BSE's Akamai
    # redirect/challenge HTML, not JSON — never call .json() blindly here,
    # since that's exactly the exception this probe exists to distinguish
    # from a real recovery rather than just record as "some error".
    content_type = r.headers.get("content-type", "")
    if "json" not in content_type.lower():
        source_health.record_fetch(
            "BSE", success=False, failure_kind="parse",
            latency_ms=elapsed_ms, error=f"non-JSON content-type: {content_type!r} (bot-wall page)",
        )
        log.info("bse.health_check.blocked", reason="non_json_response", content_type=content_type)
        return

    try:
        data = r.json()
    except Exception as exc:
        source_health.record_fetch(
            "BSE", success=False, failure_kind="parse",
            latency_ms=elapsed_ms, error=f"json decode failed: {exc}",
        )
        log.info("bse.health_check.blocked", reason="json_decode_failed")
        return

    if not isinstance(data, dict) or "Table" not in data:
        source_health.record_fetch(
            "BSE", success=False, failure_kind="parse",
            latency_ms=elapsed_ms, error="JSON response missing expected 'Table' key",
        )
        log.info("bse.health_check.blocked", reason="unexpected_json_shape")
        return

    # A real, well-formed response — BSE's bot-wall may have lifted.
    # Loud on purpose: this is the one signal that should make someone
    # reconsider re-enabling BSE ingestion as a deliberate decision.
    source_health.record_fetch(
        "BSE", success=True, event_count=len(data.get("Table") or []), latency_ms=elapsed_ms,
    )
    log.warning(
        "bse.health_check.unexpected_success",
        event_count=len(data.get("Table") or []),
        message="BSE announcements API returned real JSON -- bot-wall may have lifted. "
                "Ingestion stays disabled (DEFERRED_BOT_PROTECTED) until a deliberate re-enable decision.",
    )
