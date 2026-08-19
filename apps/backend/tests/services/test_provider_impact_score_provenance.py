"""
Impact-score provenance fix — "Companies That Matter Today" audit.

Confirmed live: several providers hardcoded a static per-source/per-category
impact_score constant (NSE announcements=7.5, BSE=6.5, RBI/Fed=9.0, PIB=8.0,
SEBI=8.5, RSS per-feed 6.5-8.0) that the real Event Impact Pipeline
(app.services.scoring_engine) never consumes as an input -- it computes
impact purely from event_type/source/companies/sectors/similar-historical-
events, fresh each time. Confirmed in the real dev DB: 1,739 events sitting
at exactly impact_score=7.5 with enrichment_status in
{pending, processing, failed} -- zero of them 'done' -- while the frontend
(LiveMarketTab.tsx) divided this already-wrong number by 10, rendering as
"0.8" for every one of them with no indication it was never really scored.

These tests confirm impact_score is None at ingestion for every provider
that previously hardcoded it -- the honest "not yet scored" signal the rest
of the stack (event_scale.normalize_impact_score, lib/scoring.ts's
isUnscored/compareScoresDesc) already correctly handles.
"""
from __future__ import annotations

from app.providers.base import RawItem
from app.providers.bse_provider import BSEProvider
from app.providers.nse_provider import NSEProvider
from app.providers.pib_provider import PIBProvider
from app.providers.rbi_provider import RBIProvider
from app.providers.rss_provider import RSSProvider
from app.providers.sebi_provider import SEBIProvider


def test_rawitem_default_impact_score_is_none():
    """The RawItem constructor's own default must be None, not a magic
    number (was 7.0) -- a provider that forgets to set impact_score
    explicitly must not silently inherit a fabricated placeholder."""
    item = RawItem(id="x", headline="test")
    assert item.impact_score is None


def test_nse_general_announcement_impact_score_is_none():
    provider = NSEProvider()
    raw = {"desc": "General Update", "attchmntText": "Company informed the Exchange about a routine matter.",
           "symbol": "TESTCO", "an_no": "12345", "sort_date": "2026-08-17"}
    item = provider._normalize_announcement(raw)
    assert item is not None
    assert item.impact_score is None


def test_nse_board_meeting_impact_score_is_none():
    provider = NSEProvider()
    raw = {"bm_desc": "Board meeting to consider quarterly results.", "bm_symbol": "TESTCO",
           "bm_timestamp": "17-Aug-2026 10:00:00"}
    item = provider._normalize_board_meeting(raw)
    assert item is not None
    assert item.impact_score is None


def test_nse_corporate_action_impact_score_is_none():
    provider = NSEProvider()
    raw = {"subject": "Interim Dividend - Rs 5 Per Share", "symbol": "TESTCO", "exDate": "20-Aug-2026"}
    item = provider._normalize_corporate_action(raw)
    assert item is not None
    assert item.impact_score is None


def test_bse_announcement_impact_score_is_none():
    provider = BSEProvider()
    raw = {"NEWSSUB": "Test announcement", "NEWSID": "n1", "scrip_cd": "500001", "NEWS_DT": "2026-08-17"}
    item = provider.normalize(raw)
    assert item is not None
    assert item.impact_score is None


def test_rbi_impact_score_is_none():
    provider = RBIProvider()
    item = provider.normalize({"headline": "RBI issues circular", "id": "rbi-1"})
    assert item is not None
    assert item.impact_score is None


def test_pib_impact_score_is_none():
    provider = PIBProvider()
    item = provider.normalize({"headline": "Cabinet approves new policy", "id": "pib-1"})
    assert item is not None
    assert item.impact_score is None


def test_sebi_impact_score_is_none():
    provider = SEBIProvider()
    item = provider.normalize({"headline": "SEBI issues new regulation", "id": "sebi-1"})
    assert item is not None
    assert item.impact_score is None


def test_rss_impact_score_is_none_regardless_of_per_feed_weight():
    """Even though the raw dict carries a per-feed weight (see _FEEDS),
    normalize() must not use it as the article's impact_score -- a
    per-source constant was never a per-article score."""
    provider = RSSProvider()
    raw = {"headline": "Nifty rallies as RBI holds rates", "summary": "Indian markets react to RBI policy.",
           "source": "Economic Times", "impact_score": 8.0, "published_at": "2026-08-17"}
    item = provider.normalize(raw)
    assert item is not None
    assert item.impact_score is None
