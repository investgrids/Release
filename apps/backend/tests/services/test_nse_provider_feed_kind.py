"""
CR-2A (2026-09-13) — regression tests for NSEProvider.filter_announcements_only(),
the mechanism that lets job_ingest_news's single shared NSE fetch feed
company_announcements_service.ingest_announcements() the same
base-announcements-only subset fetch_announcements_only() used to fetch
independently, without a second network call.

The old and new subsets must be provably equivalent -- not just "one
example inserts" -- so these tests compare the SET OF ITEMS the old
(fetch_announcements_only, single-URL) and new (filter a combined
fetch_and_normalize batch) paths would produce from the same raw input,
using each provider's own real _normalize_* methods.
"""
from __future__ import annotations

from app.providers.nse_provider import NSEProvider

_RAW_ANNOUNCEMENT = {
    "an_no": "12345", "attchmntText": "Test Company Ltd has informed the Exchange about a routine matter.",
    "desc": "General Updates", "symbol": "TESTCO", "sort_date": "2026-09-13",
    "comp": "Test Company Ltd",
}
_RAW_BOARD_MEETING = {
    "bm_desc": "Board Meeting to consider financial results.",
    "bm_purpose": "Financial Results", "bm_symbol": "TESTCO",
    "bm_timestamp": "13-Sep-2026 10:00:00",
    "_kind": "board_meeting",
}
_RAW_CORPORATE_ACTION = {
    "subject": "Interim Dividend - Rs 5 Per Share", "symbol": "TESTCO",
    "exDate": "20-Sep-2026", "caBroadcastDate": "13-Sep-2026 09:00:00",
    "_kind": "corporate_action",
}


def test_announcement_items_are_tagged_with_the_announcement_feed_kind():
    provider = NSEProvider()
    item = provider._normalize_announcement(_RAW_ANNOUNCEMENT)
    assert item is not None
    assert item.extra["nse_feed_kind"] == "announcement"


def test_board_meeting_items_are_not_tagged_as_announcements():
    provider = NSEProvider()
    item = provider._normalize_board_meeting(_RAW_BOARD_MEETING)
    assert item is not None
    assert item.extra["nse_feed_kind"] == "board_meeting"


def test_corporate_action_items_are_not_tagged_as_announcements():
    provider = NSEProvider()
    item = provider._normalize_corporate_action(_RAW_CORPORATE_ACTION)
    assert item is not None
    assert item.extra["nse_feed_kind"] == "corporate_action"


def test_filter_announcements_only_matches_normalize_dispatch_exactly():
    """The core CR-2A equivalence proof: filtering a combined
    fetch_latest()-shaped batch (as normalize() would dispatch it) down
    to nse_feed_kind=="announcement" must yield EXACTLY the announcement
    items and exclude every board_meeting/corporate_action item -- the
    same selectivity fetch_announcements_only()'s single-URL fetch
    achieved by construction (it only ever hit the announcements URL)."""
    provider = NSEProvider()
    combined_raw = [_RAW_ANNOUNCEMENT, _RAW_BOARD_MEETING, _RAW_CORPORATE_ACTION]
    normalized = [provider.normalize(r) for r in combined_raw]
    normalized = [i for i in normalized if i is not None]
    assert len(normalized) == 3  # sanity: all three raw shapes normalize successfully

    announcements_only = NSEProvider.filter_announcements_only(normalized)

    assert len(announcements_only) == 1
    assert announcements_only[0].id.startswith("nse-")
    assert not announcements_only[0].id.startswith("nse-bm-")
    assert not announcements_only[0].id.startswith("nse-ca-")
    assert announcements_only[0].extra.get("company_name") == "Test Company Ltd"


def test_filter_announcements_only_is_empty_when_batch_has_no_announcements():
    provider = NSEProvider()
    combined_raw = [_RAW_BOARD_MEETING, _RAW_CORPORATE_ACTION]
    normalized = [i for i in (provider.normalize(r) for r in combined_raw) if i is not None]
    assert NSEProvider.filter_announcements_only(normalized) == []


def test_filter_announcements_only_preserves_order():
    provider = NSEProvider()
    raw_2 = dict(_RAW_ANNOUNCEMENT, an_no="99999", symbol="SECONDCO")
    combined_raw = [_RAW_ANNOUNCEMENT, _RAW_BOARD_MEETING, raw_2, _RAW_CORPORATE_ACTION]
    normalized = [i for i in (provider.normalize(r) for r in combined_raw) if i is not None]
    result = NSEProvider.filter_announcements_only(normalized)
    assert [i.companies[0] for i in result] == ["TESTCO", "SECONDCO"]
