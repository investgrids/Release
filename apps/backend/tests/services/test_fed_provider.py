"""
Regression suite — app.providers.fed_provider (Phase 5, 2026-08 audit).
Pure unit tests against the XML parsing/filtering logic, no network.
"""
from __future__ import annotations

from app.providers.fed_provider import FedProvider, _parse_xml

_SAMPLE_FEED = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<title>FRB: Press Release - All Releases</title>
<item>
<title>Federal Reserve issues FOMC statement</title>
<link>https://www.federalreserve.gov/newsevents/pressreleases/monetary20260812a.htm</link>
<description>The Federal Reserve decided to maintain the target range for the federal funds rate at 4-1/4 to 4-1/2 percent.</description>
<pubDate>Wed, 12 Aug 2026 14:00:00 EST</pubDate>
<category>Monetary Policy</category>
</item>
<item>
<title>Federal Reserve Board approves application by Example Bancshares</title>
<link>https://www.federalreserve.gov/newsevents/pressreleases/orders20260811a.htm</link>
<description>Approval of a merger application.</description>
<pubDate>Tue, 11 Aug 2026 10:00:00 EST</pubDate>
<category>Orders on Banking Applications</category>
</item>
<item>
<title>Agencies announce threshold for smaller loan exemption</title>
<link>https://www.federalreserve.gov/newsevents/pressreleases/bcreg20260810a.htm</link>
<description>Joint agency announcement.</description>
<pubDate>Mon, 10 Aug 2026 09:00:00 EST</pubDate>
<category>Banking and Consumer Regulatory Policy</category>
</item>
</channel>
</rss>
"""


def test_filters_to_monetary_policy_category_only():
    items = _parse_xml(_SAMPLE_FEED)
    assert len(items) == 1
    assert "FOMC" in items[0]["headline"]


def test_non_monetary_items_excluded():
    items = _parse_xml(_SAMPLE_FEED)
    headlines = [i["headline"] for i in items]
    assert not any("Bancshares" in h for h in headlines)
    assert not any("smaller loan exemption" in h for h in headlines)


def test_parsed_fields_present():
    items = _parse_xml(_SAMPLE_FEED)
    item = items[0]
    assert item["id"].startswith("fed-")
    assert item["url"].startswith("https://www.federalreserve.gov/")
    assert item["published_at"] == "2026-08-12"
    assert "target range" in item["summary"]


def test_empty_feed_returns_empty_list():
    assert _parse_xml(b"<rss><channel></channel></rss>") == []


def test_malformed_xml_returns_empty_list_not_raises():
    assert _parse_xml(b"not valid xml <<<") == []


def test_normalize_builds_source_and_leaves_impact_score_unscored():
    """impact_score must be None at ingestion -- not a hardcoded per-source
    placeholder (was 9.0 before this fix). The real, differentiated score
    comes from the Event Impact Pipeline once enrichment completes; see
    app/providers/base.py's RawItem docstring for the full rationale.
    Confirmed live: several providers previously reused this same fixed-
    constant pattern, which meant every Fed item looked identically
    "9.0-important" in the UI regardless of actual content."""
    provider = FedProvider()
    raw = {
        "id": "fed-abc123", "headline": "Federal Reserve issues FOMC statement",
        "summary": "Rate decision text.", "url": "https://www.federalreserve.gov/x.htm",
        "published_at": "2026-08-12",
    }
    item = provider.normalize(raw)
    assert item is not None
    assert item.source == "Fed"
    assert item.event_type == "policy"
    assert item.impact_score is None
    assert item.ministry == "US Federal Reserve"


def test_normalize_returns_none_for_empty_headline():
    provider = FedProvider()
    assert provider.normalize({"headline": "", "id": "x"}) is None
