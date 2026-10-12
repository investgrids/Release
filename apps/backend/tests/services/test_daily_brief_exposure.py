"""Daily Brief V2.1: investor implications that work without event sector tags. Uses the October 12, 2026 production-shaped sample (sector index
moves, USD/INR lower, Brent rising, the RBI-measures bond headline) plus sparse and contradictory cases. No network, no DB, no LLM."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

import app.api.daily_brief_intelligence as brief
import app.services.ai_service as ai
from app.services import daily_brief_drivers as d
from app.services import daily_brief_exposure as x
from app.services.market_session_state import classify_session

IST = ZoneInfo("Asia/Kolkata")

SECTORS_OCT_12 = [
    {"id": "it", "name": "IT", "value": "-1.3%", "positive": False}, {"id": "banking", "name": "Banking", "value": "-0.8%", "positive": False},
    {"id": "pharma", "name": "Pharma", "value": "-0.1%", "positive": False}, {"id": "auto", "name": "Auto", "value": "+0.5%", "positive": True},
    {"id": "energy", "name": "Energy", "value": "-0.4%", "positive": False}, {"id": "fmcg", "name": "FMCG", "value": "-2.0%", "positive": False},
    {"id": "infra", "name": "Infra", "value": "-1.1%", "positive": False}, {"id": "metal", "name": "Metal", "value": "-0.7%", "positive": False},
    {"id": "realty", "name": "Realty", "value": "+0.9%", "positive": True}, {"id": "psu-bank", "name": "PSU Bank", "value": "-1.4%", "positive": False},
    {"id": "private-bank", "name": "Private Bank", "value": "-0.6%", "positive": False},
]
FACTS_OCT_12 = [
    {"entity_key": "USD_INR", "entity_type": "forex", "direction": "down", "value": "95.76", "source": "Forex market data", "observed_at": "2026-10-12T16:00:00Z"},
    {"entity_key": "BRENT_CRUDE", "entity_type": "commodity", "direction": "rising", "value": "106.85", "source": "Global futures market data", "observed_at": "2026-10-12T16:00:00Z"},
]
DRIVERS_OCT_12 = {"items": [
    {"headline": "India benchmark bond posts worst day in six months on RBI measures", "source": "Economic Times", "evidence_label": "potential_contributor", "companies": []},
    {"headline": "IT, telecom stocks decline as market selloff resumes amid FII outflows", "source": "Business Standard", "evidence_label": "potential_contributor", "companies": []},
]}
CAUSAL = ("because", "due to", "caused", "driven by", "led to", "resulted in", "triggered", "impact")


def build(sectors=SECTORS_OCT_12, facts=FACTS_OCT_12, drivers=DRIVERS_OCT_12, company_sectors=None, label="Mon 12 Oct 2026 close"):
    return x.build_exposure(sectors=sectors, smoves=d.sector_moves(sectors), facts=facts, drivers=drivers, as_of_label=label, company_sectors=company_sectors)


# ── verified sector performance: independent of any tag ──────────────────────────────────────────────────────────────

def test_sector_performance_is_shown_without_any_event_sector_tag():
    perf = build()["sector_performance"]
    assert perf["available"] and perf["as_of"] == "Mon 12 Oct 2026 close" and "market data provider" in perf["source"]
    assert [(r["name"], r["pct"]) for r in perf["leaders"]] == [("Realty", 0.9), ("Auto", 0.5)]
    assert [(r["name"], r["pct"]) for r in perf["laggards"]] == [("FMCG", -2.0), ("PSU Bank", -1.4), ("IT", -1.3)]


def test_unavailable_sector_quotes_are_reported_not_invented():
    perf = build(sectors=[])["sector_performance"]
    assert perf["available"] is False and perf["leaders"] == [] and perf["laggards"] == [] and perf["note"]
    assert build(sectors=[{"name": "IT", "value": "—"}])["sector_performance"]["available"] is False


# ── exposure: verified variables vs reported ones ───────────────────────────────────────────────────────────────────

def test_october_12_variables_are_found_with_their_evidence_level():
    out = build()
    keys = [(e["variable"], e["evidence"]) for e in out["exposure"]]
    assert keys == [("rupee_stronger", "verified"), ("crude_rising", "verified"), ("yields_rising", "reported")]
    rupee = out["exposure"][0]
    assert rupee["observed"] == "USD/INR lower at 95.76" and rupee["source"] == "Forex market data" and rupee["observed_at"] == "2026-10-12T16:00:00Z"
    assert "Rule table" not in rupee["basis"] and "not derived from this session's data" in rupee["basis"]
    reported = out["exposure"][2]
    assert reported["observed"].startswith("Reported: India benchmark bond") and reported["source"] == "Economic Times" and reported["observed_at"] is None


def test_yields_are_never_called_verified():
    assert all(e["evidence"] == "reported" for e in build()["exposure"] if e["variable"].startswith("yields"))


@pytest.mark.parametrize("headline,expected", [
    ("India benchmark bond posts worst day in six months on RBI measures", "yields_rising"),
    ("RBI measures to support rupee weigh on govt bonds, domestic equities", "yields_rising"),
    ("Bond yields jump as selloff deepens", "yields_rising"),
    ("Bond yields ease after policy", "yields_falling"),
    ("Government bonds rally on rate-cut hopes", "yields_falling"),
])
def test_yield_direction_comes_from_the_headline_wording(headline, expected):
    out = build(facts=[], drivers={"items": [{"headline": headline, "source": "ET", "evidence_label": "potential_contributor", "companies": []}]})
    assert [e["variable"] for e in out["exposure"]] == [expected]


def test_unrelated_headlines_create_no_yield_exposure():
    out = build(facts=[], drivers={"items": [{"headline": "Sensex ends lower as banks drag", "source": "ET", "evidence_label": "potential_contributor", "companies": []}]})
    assert out["exposure"] == []


# ── overlap: agreement AND disagreement are both stated, never as cause ─────────────────────────────────────────────

def test_overlap_reports_agreement_and_contradiction_without_causal_language():
    out = build()
    by = {(o["sector"], o["variable"]): o for o in out["overlap"]}
    assert by[("IT", "rupee_stronger")]["agrees"] is True and by[("IT", "rupee_stronger")]["verified_move_pct"] == -1.3
    assert by[("PSU Bank", "yields_rising")]["agrees"] is True
    assert by[("Realty", "yields_rising")]["agrees"] is False and "against" in by[("Realty", "yields_rising")]["text"]      # Realty rose +0.9%
    assert by[("Auto", "yields_rising")]["agrees"] is False
    for o in out["overlap"]:
        assert "An observation, not an attribution." in o["text"]
        assert not any(w in o["text"].lower() for w in CAUSAL)


def test_flat_sector_moves_are_not_reported_as_overlap():
    sectors = [{"name": "IT", "value": "+0.0%"}, {"name": "Pharma", "value": "-0.05%"}]
    assert build(sectors=sectors)["overlap"] == []


def test_contradictory_evidence_rupee_weaker_but_it_fell():
    facts = [dict(FACTS_OCT_12[0], direction="up", value="96.40")]
    out = build(facts=facts, drivers={"items": []})
    it = next(o for o in out["overlap"] if o["sector"] == "IT")
    assert it["typical"] == "helped" and it["agrees"] is False and it["verified_move_pct"] == -1.3
    assert not any(w in it["text"].lower() for w in CAUSAL)


# ── sparse data ─────────────────────────────────────────────────────────────────────────────────────────────────────

def test_sparse_data_keeps_performance_and_says_what_is_missing():
    out = build(facts=[], drivers={"items": []})
    assert out["sector_performance"]["available"] and out["exposure"] == [] and out["overlap"] == [] and out["company_links"] == []
    assert any("No market variable" in n for n in out["exposure_notes"]) and any("No development names a company" in n for n in out["exposure_notes"])


# ── company links ───────────────────────────────────────────────────────────────────────────────────────────────────

def test_company_links_use_the_company_master_and_stay_mentions():
    drivers = {"items": [{"headline": "TCS wins large deal", "evidence_label": "potential_contributor", "source": "ET",
                          "companies": [{"symbol": "TCS", "relation": "mentioned"}, {"symbol": "NOSECTOR", "relation": "mentioned"}]}]}
    out = build(facts=[], drivers=drivers, company_sectors={"TCS": "IT"})
    assert out["company_links"] == [{"sector": "IT", "companies": ["TCS"], "via": ["TCS wins large deal"],
                                     "basis": "Named in the development; sector from the company master (not an assessment of impact)"}]


# ── assembled endpoint ──────────────────────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def stubs(monkeypatch):
    async def snapshot(session):
        return {"nifty": {"name": "NIFTY 50", "value": "22,363.35", "pct": -0.70}, "sensex": None, "banknifty": None, "vix": None,
                "breadth": {"advances": 18, "declines": 30, "unchanged": 1}, "sectors": SECTORS_OCT_12, "movers": {"gainers": [], "losers": []},
                "sentiment_score": None, "market_status": brief._status_for(session)}

    async def none_list(*a, **k):
        return []

    async def facts(session):
        base = dict(name="n", value="1", source="s", evidence={}, claim="c", affected_sectors=[], affected_companies=[], observed_at=None, confidence=None, fact_key="k")
        return [dict(base, **f, fact_key=f"market:{f['entity_key']}:x") for f in FACTS_OCT_12]

    async def hist(events):
        return {"available": False, "message": ""}

    async def drv(session, now):
        e = {"id": "r1", "headline": "India benchmark bond posts worst day in six months on RBI measures", "one_liner": "x", "priority_tier": "Critical", "importance": 8,
             "sectors": [], "tickers": [], "source": "news", "origin": "Economic Times", "is_structural": False, "triaged_at": now.isoformat()}
        return [e], {}, {}

    async def scn():
        return [], None

    async def company_sectors(symbols):
        return {}

    async def no_llm(*a, **k):
        raise AssertionError("LLM call")

    for name, fn in (("_get_snapshot", snapshot), ("_read_raw_events", none_list), ("_get_facts", facts), ("_get_historical_context", hist),
                     ("_get_watch_next", none_list), ("_get_driver_inputs", drv), ("_get_scenario_inputs", scn), ("_get_company_sectors", company_sectors)):
        monkeypatch.setattr(brief, name, fn)
    monkeypatch.setattr(ai, "_call_with_fallback", no_llm)


@pytest.mark.asyncio
async def test_endpoint_implications_are_populated_with_no_event_tags_and_keep_the_legacy_keys(monkeypatch, stubs):
    monkeypatch.setattr(brief, "classify_session", lambda: classify_session(datetime(2026, 10, 12, 17, 0, tzinfo=IST)))
    imp = (await brief.get_daily_brief_intelligence())["investor_implications"]
    assert imp["items"] == []                                              # still no tag-derived rows: the sample has none
    assert imp["note"] is None                                            # but the section is no longer 'empty'
    assert imp["sector_performance"]["available"] and imp["sector_performance"]["as_of"] == "Mon 12 Oct 2026 close"
    assert [e["variable"] for e in imp["exposure"]] == ["rupee_stronger", "crude_rising", "yields_rising"]
    assert any(o["sector"] == "IT" and o["agrees"] for o in imp["overlap"])


@pytest.mark.asyncio
async def test_live_session_labels_the_sector_snapshot_as_live_not_a_close(monkeypatch, stubs):
    monkeypatch.setattr(brief, "classify_session", lambda: classify_session(datetime(2026, 10, 12, 11, 0, tzinfo=IST)))
    imp = (await brief.get_daily_brief_intelligence())["investor_implications"]
    assert imp["sector_performance"]["as_of"].startswith("live, retrieved ") and "close" not in imp["sector_performance"]["as_of"]
