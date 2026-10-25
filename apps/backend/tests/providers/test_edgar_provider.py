"""EdgarProvider unit tests — mocked, no live SEC calls."""
from __future__ import annotations

import pytest

import app.providers.edgar_provider as edgar
from app.providers.edgar_provider import EdgarProvider, _parse_atom
from app.providers.base import RawItem
from app.services.company_identity.resolver import ResolutionResult, ResolutionStatus
from app.services.company_identity.classifier import IdentifierType

_ATOM = """<?xml version="1.0" encoding="ISO-8859-1" ?>
<feed xmlns="http://www.w3.org/2005/Atom">
<title>Latest Filings</title>
<entry>
  <title>8-K - APPLE INC (0000320193) (Filer)</title>
  <link rel="alternate" type="text/html" href="https://www.sec.gov/Archives/edgar/data/320193/000032019326000111/0000320193-26-000111-index.htm"/>
  <updated>2026-10-24T16:30:00-04:00</updated>
  <category scheme="x" term="8-K" label="form type"/>
</entry>
<entry>
  <title>8-K/A - APPLE INC (0000320193) (Filer)</title>
  <link rel="alternate" href="https://www.sec.gov/Archives/edgar/data/320193/000032019326000112/0000320193-26-000112-index.htm"/>
  <updated>2026-10-24T17:00:00-04:00</updated>
</entry>
</feed>"""


def test_parse_atom_extracts_fields():
    rows = _parse_atom(_ATOM)
    assert len(rows) == 2
    r0 = rows[0]
    assert r0["form"] == "8-K"
    assert r0["company"] == "APPLE INC"
    assert r0["cik"] == "0000320193"
    assert r0["accession"] == "0000320193-26-000111"
    assert r0["published_at"] == "2026-10-24"
    assert rows[1]["form"] == "8-K/A"
    assert rows[1]["accession"] == "0000320193-26-000112"


def test_parse_atom_malformed_returns_empty():
    assert _parse_atom("not xml at all") == []


def test_normalize_shape_and_no_fabrication():
    p = EdgarProvider()
    rows = _parse_atom(_ATOM)
    item = p.normalize(rows[0])
    assert item is not None
    assert item.id == "edgar-0000320193-26-000111"   # accession-based identity
    assert item.event_type == "filing"
    assert item.impact_score is None                  # never a fabricated score
    assert item.companies == []                       # no company link without resolution
    assert "APPLE INC" in item.headline and "8-K" in item.headline
    assert "Source: SEC EDGAR" in item.summary
    assert item.extra["accession"] == "0000320193-26-000111"
    assert item.extra["form"] == "8-K" and item.extra["cik"] == "0000320193"


def test_amendment_is_a_distinct_event():
    p = EdgarProvider()
    rows = _parse_atom(_ATOM)
    base = p.normalize(rows[0])
    amend = p.normalize(rows[1])
    assert base.id != amend.id            # distinct accession -> distinct event
    assert amend.extra["form"] == "8-K/A"


def test_normalize_requires_identity():
    p = EdgarProvider()
    assert p.normalize({"form": "8-K", "company": "X", "accession": ""}) is None
    assert p.normalize({"form": "", "company": "X", "accession": "a-b-c"}) is None
    assert p.normalize({"form": "8-K", "company": "", "accession": "a-b-c"}) is None


class _FakeSession:
    async def __aenter__(self):
        return "db"
    async def __aexit__(self, *a):
        return False


async def test_resolve_companies_links_only_on_resolved(monkeypatch):
    # map two CIKs to tickers; one resolves, one does not
    async def fake_map(self):
        return {320193: "AAPL", 999: "ZZZ"}

    async def fake_resolve(db, ticker):
        if ticker == "AAPL":
            return ResolutionResult(status=ResolutionStatus.RESOLVED,
                                    identifier_type=IdentifierType.COMPANY, entity_id="ENT1")
        return ResolutionResult(status=ResolutionStatus.UNRESOLVED,
                                identifier_type=IdentifierType.COMPANY)

    monkeypatch.setattr(EdgarProvider, "_cik_ticker_map", fake_map)
    monkeypatch.setattr(edgar, "resolve_identifier", fake_resolve)
    monkeypatch.setattr(edgar, "AsyncSessionLocal", lambda: _FakeSession())

    resolved = RawItem(id="edgar-a", headline="Apple - 8-K", event_type="filing",
                       extra={"cik": "0000320193"})
    unresolved = RawItem(id="edgar-b", headline="Zed - 8-K", event_type="filing",
                         extra={"cik": "0000000999"})
    no_ticker = RawItem(id="edgar-c", headline="None - 8-K", event_type="filing",
                        extra={"cik": "0000012345"})

    p = EdgarProvider()
    await p._resolve_companies([resolved, unresolved, no_ticker])

    assert resolved.companies == ["ENT1"]   # RESOLVED -> link
    assert unresolved.companies == []        # UNRESOLVED -> no link, never fabricated
    assert no_ticker.companies == []         # no ticker mapping -> no link
