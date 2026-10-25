"""EcbProvider unit tests — mocked, no live ECB calls."""
from __future__ import annotations

from app.providers.ecb_provider import EcbProvider, _parse_rss

_RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
<title>ECB - European Central Bank</title>
<item>
  <title>Monetary policy decisions</title>
  <link>https://www.ecb.europa.eu/press/pr/date/2026/html/ecb.mp261024.en.html</link>
  <description>The Governing Council today decided to keep the three key ECB interest rates unchanged.</description>
  <pubDate>Thu, 24 Oct 2026 14:15:00 +0200</pubDate>
</item>
<item>
  <title>ECB publishes euro area statistics</title>
  <link>https://www.ecb.europa.eu/press/stats/x.en.html</link>
  <description>Latest data release.</description>
  <pubDate>Tue, 20 Oct 2026 10:00:00 +0200</pubDate>
</item>
</channel></rss>"""


def test_parse_rss_extracts_items():
    rows = _parse_rss(_RSS)
    assert len(rows) == 2
    assert rows[0]["headline"] == "Monetary policy decisions"
    assert rows[0]["url"].startswith("https://www.ecb.europa.eu/")
    assert rows[0]["published_at"] == "2026-10-24"


def test_parse_rss_malformed_returns_empty():
    assert _parse_rss(b"not xml") == []


def test_normalize_shape_attribution_and_impact():
    p = EcbProvider()
    item = p.normalize(_parse_rss(_RSS)[0])
    assert item is not None
    assert item.id.startswith("ecb-")
    assert item.event_type == "policy"
    assert item.ministry == "European Central Bank"
    assert item.impact_score is None
    assert item.source == "ECB"
    assert "(Source: ECB)" in item.summary                 # explicit attribution
    assert item.url.startswith("https://www.ecb.europa.eu/")   # original source preserved
    assert item.url in item.summary                        # original link retained in text (no url column)


def test_normalize_truncates_long_body_not_full_text():
    p = EcbProvider()
    long_desc = "x" * 2000
    item = p.normalize({"headline": "Long release", "summary": long_desc, "url": "u", "published_at": "2026-10-24"})
    assert item is not None
    assert "…" in item.summary and len(item.summary) <= 1000   # brief excerpt, not full text
    assert "(Source: ECB)" in item.summary


def test_normalize_requires_headline():
    p = EcbProvider()
    assert p.normalize({"headline": "", "summary": "x"}) is None


def test_empty_description_still_attributes():
    p = EcbProvider()
    item = p.normalize({"headline": "No body", "summary": "", "url": "https://www.ecb.europa.eu/x.html", "published_at": "2026-10-24"})
    assert item is not None
    assert "(Source: ECB)" in item.summary and "ecb.europa.eu/x.html" in item.summary   # link retained even with no excerpt
