"""
Raw Evidence capture — Phase 1B Batch 2 (owner instruction, 2026-08-23).

Purely additive: hooked into app/providers/base.py::BaseProvider.
fetch_and_normalize() (the single shared entrypoint all 6 wired
providers already call), captures every raw item BEFORE normalize()
filters/transforms it, and returns the exact same list[RawItem] as
before — job_ingest_news()/job_ingest_policy() and every other existing
caller are completely unmodified. No consumer reads this table yet.

Only RSS, NSE, RBI, PIB, SEBI, Fed are wired (BaseProvider.
capture_raw_evidence=True on those 6 classes only) — BSE stays excluded
per owner instruction (already known bot-blocked/unreliable; wiring it
here wouldn't produce anything meaningfully different from the 0 real
rows it already contributes elsewhere).
"""
from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from uuid import uuid4

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.raw_evidence import RawEvidence

log = structlog.get_logger(__name__)

_FIXED_SOURCE_IDS = {
    "NSE": "nse_corporate_announcements",
    "RBI": "rbi_press_releases",
    "PIB": "pib_finance",
    "SEBI": "sebi_circulars",
    "Fed": "fed_press_releases",
}

_RSS_FEED_SOURCE_IDS = {
    "Economic Times": "rss_economic_times_markets",
    "Moneycontrol": "rss_moneycontrol_latest",
    "NDTV Profit": "rss_ndtv_profit",
    "Business Standard": "rss_business_standard_markets",
    "Livemint": "rss_livemint_markets",
    "Google News India": "rss_google_news_india",
}


def resolve_source_id(source_name: str, raw: dict) -> str | None:
    if source_name == "RSS":
        return _RSS_FEED_SOURCE_IDS.get(raw.get("source", ""))
    return _FIXED_SOURCE_IDS.get(source_name)


def _extract_external_id(source_name: str, raw: dict) -> str | None:
    """RSS/RBI/PIB/SEBI/Fed already compute a stable "id" key inside
    their own fetch_latest() (see each provider's own hashlib usage).
    NSE's raw JSON does not — confirmed live against real NSE API
    responses (2026-08-23): the "an_no" field nse_provider.py::
    _normalize_announcement reads for its own uid does not actually
    exist in real announcement payloads (a pre-existing dead reference —
    that normalize path already silently falls back to a content hash in
    practice today). NSE's real, genuinely stable field for an
    announcement is "seq_id" (a real NSE-assigned sequence number,
    confirmed present in live data) — used here instead. Board meetings
    use bm_symbol+bm_timestamp, matching _normalize_board_meeting's own
    uid_src composition."""
    if source_name == "NSE":
        kind = raw.get("_kind")
        if kind == "board_meeting":
            symbol, ts = raw.get("bm_symbol", ""), raw.get("bm_timestamp", "")
            return f"nse-bm-{symbol}-{ts}" if symbol and ts else None
        if kind == "corporate_action":
            return None   # no stable NSE-provided id field found for this sub-feed — falls back to content-hash identity, still correct
        seq_id = raw.get("seq_id")
        return f"nse-{seq_id}" if seq_id else None
    return raw.get("id")


def _extract_title(source_name: str, raw: dict) -> str | None:
    """Same real-field-name gap as _extract_external_id: NSE's raw dict
    has no "headline"/"title" key. Mirrors nse_provider.py's own
    normalize precedence (attchmntText/bm_desc body text preferred over
    the desc/bm_purpose category label) rather than inventing a new
    rule."""
    if source_name == "NSE":
        text = raw.get("attchmntText") or raw.get("bm_desc") or raw.get("desc") or raw.get("bm_purpose") or raw.get("subject")
        return text[:512] if text else None
    return raw.get("headline") or raw.get("title") or None


def _extract_published_at_raw(source_name: str, raw: dict) -> str | None:
    """Same real-field-name gap as external_id/title: NSE's raw dict has
    no "published_at" key. Confirmed live: announcements carry
    "sort_date" ("2026-08-23 09:52:01"); board meetings carry
    "bm_timestamp" ("%d-%b-%Y %H:%M:%S", matching _normalize_board_
    meeting's own parse). Every other wired provider already puts a
    usable value under "published_at" in its own fetch_latest()."""
    if source_name == "NSE":
        kind = raw.get("_kind")
        if kind == "board_meeting":
            return raw.get("bm_timestamp")
        return raw.get("sort_date")
    return raw.get("published_at")


def _parse_published_at(raw_value: str | None) -> datetime | None:
    """Real parsed datetime or None — NEVER a relative string like
    '2h ago' (the confirmed news_articles.published_at bug). Providers in
    this codebase emit ISO-ish "%Y-%m-%d"/"%Y-%m-%d %H:%M:%S" strings or
    NSE's "%d-%b-%Y %H:%M:%S" for board meetings; this parser fails
    closed (returns None) on anything it can't confidently parse, rather
    than storing an unparseable string."""
    if not raw_value:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S%z", "%d-%b-%Y %H:%M:%S"):
        try:
            dt = datetime.strptime(raw_value, fmt)
            return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
        except ValueError:
            continue
    return None


def _content_hash(raw: dict) -> str:
    """sha256 over a stable JSON serialization of the raw dict — this is
    the payload_hash. Deliberately excludes nothing (the whole raw dict
    IS the payload); a genuine content change anywhere in it produces a
    new version, an unrelated re-fetch with byte-identical content
    produces the same hash and gets suppressed."""
    stable = json.dumps(raw, sort_keys=True, default=str)
    return hashlib.sha256(stable.encode("utf-8")).hexdigest()


async def capture_raw_evidence(
    db: AsyncSession, source_name: str, entries: list[tuple[dict, str]],
) -> dict:
    """entries: list of (raw_dict, quality) — quality is one of
    good | filtered | invalid | parse_error, already determined by the
    caller (fetch_and_normalize's own normalize()/validate() outcomes).
    Returns per-source counts for the caller to log/aggregate."""
    now = datetime.now(timezone.utc)
    source_type = source_name.lower()

    attempted = len(entries)
    written = 0
    suppressed_duplicate = 0
    skipped_no_source = 0

    for raw, quality in entries:
        source_id = resolve_source_id(source_name, raw)
        if source_id is None:
            skipped_no_source += 1
            continue

        external_id = _extract_external_id(source_name, raw)
        evidence_key = f"{source_type}:{external_id}" if external_id else f"{source_type}:{_content_hash(raw)[:16]}"
        payload_hash = _content_hash(raw)

        existing = (await db.execute(
            select(RawEvidence.id).where(
                RawEvidence.evidence_key == evidence_key, RawEvidence.payload_hash == payload_hash,
            ).limit(1)
        )).scalar_one_or_none()
        if existing is not None:
            suppressed_duplicate += 1
            continue

        db.add(RawEvidence(
            id=str(uuid4()), evidence_key=evidence_key, payload_hash=payload_hash,
            source_id=source_id, source_type=source_type, external_id=external_id,
            title=_extract_title(source_name, raw),
            published_at=_parse_published_at(_extract_published_at_raw(source_name, raw)),
            observed_at=now, ingested_at=now,
            source_url=raw.get("url") or None,
            raw_payload=json.dumps(raw, default=str),
            mime_type="application/json",
            quality=quality,
        ))
        written += 1

    if written:
        try:
            await db.commit()
        except Exception as exc:
            await db.rollback()
            log.warning("warehouse.raw_evidence.commit_failed", source=source_name, error=str(exc)[:160])
            return {"attempted": attempted, "written": 0, "suppressed_duplicate": 0, "skipped_no_source": skipped_no_source, "error": str(exc)[:160]}

    log.info("warehouse.raw_evidence.captured", source=source_name, attempted=attempted,
              written=written, suppressed_duplicate=suppressed_duplicate, skipped_no_source=skipped_no_source)
    return {"attempted": attempted, "written": written, "suppressed_duplicate": suppressed_duplicate, "skipped_no_source": skipped_no_source}
