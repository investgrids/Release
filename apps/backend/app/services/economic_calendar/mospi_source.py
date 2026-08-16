"""
MOSPI CPI / IIP schedule ingestion — Phase 5A.3.

Real, verified text extraction from MOSPI's own official "Advance
Release Calendar" PDF via pypdf (pure-Python, no system dependency —
confirmed working against the actual document, unlike page-image
rendering which needs poppler and isn't available in every
environment). Confirmed live 2026-08-16 against two real documents
(the FY2026-27 "FINAL 05.02.2026" and "Updated 25.05.2026" versions):
CPI is released the 12th of every month, IIP the 28th, both stated
explicitly per month rather than inferred — this parser reads the
document's own stated dates, never assumes the 12th/28th cadence for a
month the document doesn't explicitly list.

Known real limitation, disclosed rather than worked around: MOSPI's
mospi.gov.in website is a client-rendered React SPA — a plain HTTP GET
returns an empty shell, not the actual page content, so there is no
simple way to programmatically discover *today's* current PDF URL the
way rbi_source.py discovers RBI's schedule from one stable page. V1
therefore points at a specific, manually-verified PDF URL
(_CURRENT_PDF_URL below) rather than a self-updating discovery step.
This needs periodic human re-verification (confirm the URL still
resolves to the current fiscal year's calendar) until either MOSPI
exposes a stable JSON endpoint or a headless-browser render is added
to discover the current link automatically. Documented honestly here
rather than either silently scraping a guessed URL pattern or silently
generating dates from a cadence assumption.

Second real, disclosed constraint: mospi.gov.in's TLS certificate does
not verify cleanly from this environment (self-signed cert in the
chain, confirmed on both the apex and www hosts) — a real, external
issue with the government site's certificate chain, not a bug in this
code. `verify=False` is used narrowly, only for this one government
PDF host, with this comment as the paper trail — flagged for the
owner's awareness rather than silently disabling verification with no
explanation. A proper fix would pin/bundle the correct intermediate CA
rather than skip verification; not done here since that's an
infrastructure decision, not a parsing one.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import httpx
import structlog

from app.services.economic_calendar.sync_engine import CalendarCandidate

log = structlog.get_logger(__name__)

# See module docstring — manually verified 2026-08-16 against the live
# MOSPI site (found via the site's own search, since the page that
# links to it is JS-rendered and not otherwise discoverable by a plain
# HTTP client). Needs periodic re-verification; not self-updating.
_CURRENT_PDF_URL = (
    "https://www.mospi.gov.in/uploads/documents/releaseCalender/"
    "1779709510470-ADVANCE%20RELEASE%20CALENDAR%202026-27%20Updated%2025.05.2026.pdf"
)
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; InvestGridsBot/1.0)"}
_IST = ZoneInfo("Asia/Kolkata")

# Scoped narrowly to this one government host — never a generic HTTP-client
# setting. See module docstring's "second real, disclosed constraint" for
# why: mospi.gov.in's own certificate chain doesn't verify (self-signed
# cert, confirmed on both apex and www), not a bug in this code. Logged
# loudly on every single call (below) specifically so this can't become
# invisible technical debt — if MOSPI's certificate is ever fixed, this
# constant (and the one log line depending on it) is the entire footprint
# to remove.
_SKIP_TLS_VERIFICATION_FOR_MOSPI_ONLY = True

_MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "september": 9, "oct": 10, "october": 10,
    "nov": 11, "november": 11, "dec": 12, "december": 12,
}

# "12th Sep All India Consumer Price Index (CPI)" / "28th \nMarch \nAll
# India Index of Industrial Production (IIP)" — \s+ tolerates the real
# PDF's line-wrapping on longer month names, confirmed against the
# actual extracted text of both live documents.
_CPI_PATTERN = re.compile(
    r"(\d{1,2})(?:st|nd|rd|th)\s+([A-Za-z]+)\s+All\s+India\s+Consumer\s+Price\s+Index",
    re.IGNORECASE,
)
_IIP_PATTERN = re.compile(
    r"(\d{1,2})(?:st|nd|rd|th)\s+([A-Za-z]+)\s+All\s+India\s+Index\s+of\s+Industrial\s+Production",
    re.IGNORECASE,
)
# Document title carries the fiscal year, e.g. "ADVANCE RELEASE CALENDAR (2026-27)"
_FISCAL_YEAR = re.compile(r"ADVANCE RELEASE CALENDAR\s*\((\d{4})-(\d{2})\)", re.IGNORECASE)


def _extract_full_text(pdf_bytes: bytes) -> str:
    from pypdf import PdfReader
    from io import BytesIO
    reader = PdfReader(BytesIO(pdf_bytes))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _assign_years(entries: list[tuple[int, str]], fiscal_start_year: int) -> list[tuple[int, int, int]]:
    """entries: [(day, month_name)] in document order. A MoSPI fiscal
    year runs April -> March, so the year increments exactly once, the
    first time the month sequence drops from December (12) back down
    to a smaller month number (January onward) — tracked here rather
    than assumed per-entry, since the document itself never repeats
    the year on every single row."""
    out = []
    year = fiscal_start_year
    prev_month = 0
    for day, month_name in entries:
        month = _MONTHS.get(month_name.lower())
        if month is None:
            continue
        if prev_month == 12 and month < 12 and month <= prev_month:
            year += 1
        elif prev_month != 0 and month < prev_month and prev_month >= 10:
            year += 1
        out.append((day, month, year))
        prev_month = month
    return out


def _sequential_reference_periods(count: int, fiscal_start_year: int, fiscal_start_month: int = 4) -> list[str]:
    """Real-data finding (confirmed 2026-08-16 against the live 'Updated
    25.05.2026' document): a same-cadence release can slip into the
    NEXT month's block — May 2026's IIP release is dated 1st June in
    the document, immediately followed by June's own regular 28th-June
    release. Grouping by literal release-month would collide those two
    into the same identity_key (both "2026-06"). MoSPI's own document
    doesn't state which underlying period each CPI/IIP print covers
    (unlike its GDP rows, which do say "Q1, FY 2026-27" etc.) — rather
    than assert a specific lag convention this document doesn't confirm,
    reference_period is assigned purely by POSITION: the Nth CPI (or
    IIP) entry encountered, in document order, is period N, mapped to
    consecutive fiscal months starting at April — regardless of which
    visual month-block the document places it under. Robust to exactly
    this kind of one-off slip without guessing a specific reference
    period the source document itself doesn't state."""
    out = []
    month, year = fiscal_start_month, fiscal_start_year
    for _ in range(count):
        out.append(f"{year:04d}-{month:02d}")
        month += 1
        if month > 12:
            month = 1
            year += 1
    return out


async def fetch_mospi_candidates() -> list[CalendarCandidate]:
    log.warning(
        "mospi_calendar.tls_verification_skipped",
        reason="mospi.gov.in certificate chain does not verify from this environment (self-signed cert)",
        scope="mospi_source.py only — not a generic HTTP-client setting",
        url=_CURRENT_PDF_URL,
    )
    try:
        async with httpx.AsyncClient(
            headers=_HEADERS, timeout=25, follow_redirects=True,
            verify=not _SKIP_TLS_VERIFICATION_FOR_MOSPI_ONLY,
        ) as client:
            resp = await client.get(_CURRENT_PDF_URL)
            resp.raise_for_status()
    except Exception as exc:
        log.warning("mospi_calendar.fetch_failed", error=str(exc)[:200])
        return []

    try:
        text = _extract_full_text(resp.content)
    except Exception as exc:
        log.warning("mospi_calendar.parse_failed", error=str(exc)[:200])
        return []

    fy_match = _FISCAL_YEAR.search(text)
    if not fy_match:
        log.warning("mospi_calendar.fiscal_year_not_found")
        return []
    fiscal_start_year = int(fy_match.group(1))

    cpi_raw = [(int(d), m) for d, m in _CPI_PATTERN.findall(text)]
    iip_raw = [(int(d), m) for d, m in _IIP_PATTERN.findall(text)]
    if not cpi_raw and not iip_raw:
        log.warning("mospi_calendar.no_entries_found")
        return []

    candidates = []
    for category, raw, importance in (
        ("india_cpi", cpi_raw, "critical"),
        ("india_iip", iip_raw, "high"),
    ):
        dated_entries = _assign_years(raw, fiscal_start_year)
        ref_periods = _sequential_reference_periods(len(dated_entries), fiscal_start_year)
        for (day, month, year), reference_period in zip(dated_entries, ref_periods):
            try:
                local_dt = datetime(year, month, day, 16, 0, tzinfo=_IST)   # MOSPI releases at 4:00 PM IST (confirmed cadence)
            except ValueError:
                continue
            candidates.append(CalendarCandidate(
                identity_key=f"{category}:IN:{reference_period}",
                reference_period=reference_period,
                title="India CPI" if category == "india_cpi" else "India IIP (Index of Industrial Production)",
                category=category,
                country="IN",
                scheduled_at=local_dt.astimezone(timezone.utc),
                source_timezone="Asia/Kolkata",
                importance=importance,
                source="mospi",
                source_url=_CURRENT_PDF_URL,
                source_tier="tier_1",
            ))
    return candidates
