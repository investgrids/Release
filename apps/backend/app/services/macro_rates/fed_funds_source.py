"""
US Federal Funds effective rate — Phase 5C.

Fetches the Federal Reserve's own H.15 Selected Interest Rates RDF feed
directly (federalreserve.gov/feeds/data/H15_H15.XML) — tier 1,
first-party, same domain already trusted by
economic_calendar/fed_source.py for FOMC meeting scheduling. Confirmed
live 2026-08-17: 30 <item> entries, one per series, each with a real
<cb:value>/<cb:observationPeriod> pair. The "Federal funds" coverage
item is this module's only target.

This feed gives one dated snapshot per fetch, not a bulk history (unlike
the Treasury yield-curve feed) — the effective funds rate barely moves
between FOMC decisions anyway, so a snapshot fetched periodically and
persisted only on real change (via macro_rates/persistence.py) builds an
accurate, sparse history without needing a separate bulk-download path.
Trend is therefore decision-driven, the same shape as RBI's repo rate,
not a statistically-thresholded continuous series like Treasury yields.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date, datetime
from xml.etree import ElementTree as ET

import httpx
import structlog

log = structlog.get_logger(__name__)

_URL = "https://www.federalreserve.gov/feeds/data/H15_H15.XML"
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; InvestGridsBot/1.0)"}
_NS = {
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rss": "http://purl.org/rss/1.0/",
    "cb": "http://www.cbwiki.net/wiki/index.php/Specification_1.1",
}
_TARGET_COVERAGE = "Federal funds"


@dataclass
class FedFundsObservation:
    status: str                      # "live" | "unavailable"
    value: float | None = None
    observation_date: date | None = None
    source: str = "fed_h15"
    reason: str | None = None


def _fetch_sync() -> str | None:
    try:
        with httpx.Client(headers=_HEADERS, timeout=15, follow_redirects=True) as client:
            resp = client.get(_URL)
            resp.raise_for_status()
            return resp.text
    except Exception as exc:
        log.warning("fed_funds.fetch_failed", error=str(exc)[:200])
        return None


def _parse(xml_text: str) -> FedFundsObservation:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        log.warning("fed_funds.parse_failed", error=str(exc)[:200])
        return FedFundsObservation(status="unavailable", reason="xml_parse_failed")

    for item in root.findall("rss:item", _NS):
        coverage_el = item.find(".//cb:coverage", _NS)
        if coverage_el is None or (coverage_el.text or "").strip() != _TARGET_COVERAGE:
            continue
        value_el = item.find(".//cb:value", _NS)
        period_el = item.find(".//cb:observationPeriod", _NS)
        if value_el is None or not value_el.text:
            return FedFundsObservation(status="unavailable", reason="federal_funds_value_missing")
        try:
            value = float(value_el.text)
        except ValueError:
            return FedFundsObservation(status="unavailable", reason="federal_funds_value_unparseable")
        obs_date = None
        if period_el is not None and period_el.text:
            try:
                obs_date = datetime.strptime(period_el.text.strip(), "%Y-%m-%d").date()
            except ValueError:
                obs_date = None
        return FedFundsObservation(status="live", value=value, observation_date=obs_date)

    return FedFundsObservation(status="unavailable", reason="federal_funds_series_not_found")


async def get_fed_funds_rate() -> FedFundsObservation:
    loop = asyncio.get_event_loop()
    text = await loop.run_in_executor(None, _fetch_sync)
    if text is None:
        return FedFundsObservation(status="unavailable", reason="source_fetch_failed")
    return _parse(text)
