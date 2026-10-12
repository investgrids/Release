"""Daily Brief: investor implications wired to the knowledge graph. Uses the October 12, 2026 production-shaped sample (sector index moves, USD/INR
lower, Brent rising, the RBI-measures bond headline) plus sparse, contradictory and no-graph cases. No network, no DB, no LLM."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

import app.api.daily_brief_intelligence as brief
import app.services.ai_service as ai
import app.services.daily_brief_graph as graph_mod
from app.services import daily_brief_drivers as d
from app.services import daily_brief_exposure as x
from app.services.market_session_state import classify_session
from tests.services.daily_brief_graph_fixture import fake_graph

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
G = fake_graph()


def build(sectors=SECTORS_OCT_12, facts=FACTS_OCT_12, drivers=DRIVERS_OCT_12, company_sectors=None, label="Mon 12 Oct 2026 close", graph=G):
    return x.build_exposure(sectors=sectors, smoves=d.sector_moves(sectors), facts=facts, drivers=drivers, as_of_label=label,
                            company_sectors=company_sectors, graph=graph, vocabulary=graph.sector_vocabulary if graph else None)


# ── graph reading: edges in, pressured/helped out ────────────────────────────────────────────────────────────────────

def test_graph_edges_are_read_as_written_and_inverted_for_the_opposite_move():
    weaker = G.exposure("rupee_weaker")
    assert [i["sector"] for i in weaker["helped"]] == ["IT", "Pharma", "Textiles"] and [i["sector"] for i in weaker["pressured"]][:2] == ["Airlines", "Auto"]
    stronger = G.exposure("rupee_stronger")
    assert [i["sector"] for i in stronger["pressured"]] == ["IT", "Pharma", "Textiles"] and "Airlines" in [i["sector"] for i in stronger["helped"]]
    assert stronger["inverted"] is True and "inverted" in stronger["basis"] and weaker["inverted"] is False and weaker["basis"] == "Knowledge graph: USD/INR edges to sectors"
    first = stronger["pressured"][0]
    assert first["weight"] == 0.85 and first["confidence"] == 0.95 and first["lag_days"] == 0 and "IT earns USD" in first["why"]      # the graph's own evidence travels with it


def test_exposure_is_ordered_by_graph_weight_and_capped():
    assert [i["weight"] for i in G.exposure("crude_rising")["pressured"]] == sorted([i["weight"] for i in G.exposure("crude_rising")["pressured"]], reverse=True)
    assert len(G.exposure("crude_rising")["pressured"]) <= 6
    assert G.exposure("crude_rising")["helped"][0]["sector"] == "Oil & Gas" and G.exposure("crude_falling")["pressured"][0]["sector"] == "Oil & Gas"


def test_untracked_variable_or_empty_graph_has_no_exposure():
    assert G.exposure("vix_rising") is None and graph_mod.GraphContext().exposure("crude_rising") is None
    assert G.affected_labels("commodity:crude-oil", 3) == ["Airlines", "Oil & Gas", "Paint"] and G.affected_labels("commodity:unknown") == []


def test_sector_labels_are_cleaned_for_headline_reading():
    assert graph_mod._clean_label("All Sectors") is None and graph_mod._clean_label("ALL") is None and graph_mod._clean_label("x") is None
    assert graph_mod._clean_label("Real Estate") == "Real Estate"


@pytest.mark.asyncio
async def test_unreadable_graph_returns_none_not_an_exception(monkeypatch):
    import app.db.session as session_mod

    def boom():
        raise RuntimeError("db down")

    monkeypatch.setattr(session_mod, "AsyncSessionLocal", boom)
    graph_mod._cache.update(ctx=None, at=0.0)
    assert await graph_mod.load_graph_context(force=True) is None


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


# ── exposure: verified variables vs reported ones, sectors from the graph ───────────────────────────────────────────

def test_october_12_variables_are_found_with_their_evidence_level_and_graph_sectors():
    out = build()
    assert [(e["variable"], e["evidence"]) for e in out["exposure"]] == [("rupee_stronger", "verified"), ("crude_rising", "verified"), ("yields_rising", "reported")]
    rupee = out["exposure"][0]
    assert rupee["observed"] == "USD/INR lower at 95.76" and rupee["source"] == "Forex market data" and rupee["observed_at"] == "2026-10-12T16:00:00Z"
    assert rupee["basis"].startswith("Knowledge graph:") and rupee["node"] == "currency:usd-inr"
    assert [i["sector"] for i in rupee["pressured"]] == ["IT", "Pharma", "Textiles"]
    reported = out["exposure"][2]
    assert reported["observed"].startswith("Reported: India benchmark bond") and reported["source"] == "Economic Times" and reported["observed_at"] is None
    assert reported["node"] == "policy:rbi-rate-hike" and "RBI Rate Hike" in reported["basis"]


def test_no_sector_name_comes_from_the_code_only_from_the_graph():
    custom = graph_mod.GraphContext(edges={"commodity:crude-oil": [graph_mod.Edge("sector:zzz", "Zeppelins", "hurts", 0.9, 0.9, 0, "test")]},
                                    node_labels={"commodity:crude-oil": "Crude Oil"})
    out = build(facts=[FACTS_OCT_12[1]], drivers={"items": []}, graph=custom)
    assert [i["sector"] for i in out["exposure"][0]["pressured"]] == ["Zeppelins"] and out["exposure"][0]["helped"] == []


def test_without_a_graph_there_is_no_exposure_and_the_page_says_why():
    out = build(graph=None)
    assert out["exposure"] == [] and out["overlap"] == []
    assert any("records no sector exposure" in n for n in out["exposure_notes"])
    assert out["sector_performance"]["available"]                           # the verified part never depends on the graph


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
    assert by[("FMCG", "crude_rising")]["agrees"] is True and by[("Infra", "yields_rising")]["agrees"] is True
    assert by[("Realty", "yields_rising")]["agrees"] is False and "against" in by[("Realty", "yields_rising")]["text"]        # Realty rose +0.9%
    assert by[("Auto", "yields_rising")]["agrees"] is False and by[("Auto", "crude_rising")]["agrees"] is False
    assert by[("Auto", "rupee_stronger")]["agrees"] is True and by[("Auto", "rupee_stronger")]["typical"] == "helped"
    for o in out["overlap"]:
        assert "An observation, not an attribution." in o["text"]
        assert not any(w in o["text"].lower() for w in CAUSAL)


def test_flat_sector_moves_are_not_reported_as_overlap():
    sectors = [{"name": "IT", "value": "+0.0%"}, {"name": "Pharma", "value": "-0.05%"}]
    assert build(sectors=sectors)["overlap"] == []
    assert not any(o["sector"] == "Pharma" for o in build()["overlap"])             # Pharma -0.1% is near-flat in the October 12 sample


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


# ── sectors named: vocabulary comes from the graph and the sector index names ───────────────────────────────────────

def test_sectors_mentioned_use_the_graph_vocabulary_and_never_the_pronoun():
    drivers = {"items": [
        {"headline": "IT, telecom stocks decline as market selloff resumes amid FII outflows", "evidence_label": "potential_contributor", "sectors": [], "companies": []},
        {"headline": "Banks tighten lending after RBI circular", "evidence_label": "potential_contributor", "sectors": [{"name": "Financial Services", "verified_move_pct": None}], "companies": []},
        {"headline": "Analysts say pharma outlook is strong", "evidence_label": "commentary", "sectors": [], "companies": []},
        {"headline": "Why it matters for markets", "evidence_label": "potential_contributor", "sectors": [], "companies": []},
    ]}
    found = x.sectors_mentioned(drivers, vocabulary=G.sector_vocabulary, index_names=["IT", "Banking", "Realty"])
    names = [m["name"] for m in found]
    assert "IT" in names and "Telecom" in names and "Banking" in names
    assert "Financial Services" not in names                                  # same sector as Banking: one entry
    assert "Pharma" not in names                                              # commentary items are not used
    via = {m["name"]: [v["basis"] for v in m["via"]] for m in found}
    assert via["IT"] == ["headline"] and sorted(via["Banking"]) == ["event sector tag", "headline"]
    # with no vocabulary at all nothing is guessed from the text
    assert x.sectors_mentioned({"items": [{"headline": "IT stocks fall", "evidence_label": "potential_contributor", "sectors": [], "companies": []}]}) == []


def test_variable_labels_use_plain_wording():
    assert [e["label"] for e in build()["exposure"]] == ["Rupee strengthens", "Higher crude oil prices", "Bond yields rise"]


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

    async def graph(force=False):
        return fake_graph()

    async def no_llm(*a, **k):
        raise AssertionError("LLM call")

    for name, fn in (("_get_snapshot", snapshot), ("_read_raw_events", none_list), ("_get_facts", facts), ("_get_historical_context", hist),
                     ("_get_watch_next", none_list), ("_get_driver_inputs", drv), ("_get_scenario_inputs", scn), ("_get_company_sectors", company_sectors)):
        monkeypatch.setattr(brief, name, fn)
    monkeypatch.setattr(graph_mod, "load_graph_context", graph)
    monkeypatch.setattr(ai, "_call_with_fallback", no_llm)


@pytest.mark.asyncio
async def test_endpoint_implications_are_populated_from_the_graph_with_no_event_tags(monkeypatch, stubs):
    monkeypatch.setattr(brief, "classify_session", lambda: classify_session(datetime(2026, 10, 12, 17, 0, tzinfo=IST)))
    out = await brief.get_daily_brief_intelligence()
    imp = out["investor_implications"]
    assert imp["items"] == [] and imp["note"] is None
    assert imp["sector_performance"]["available"] and imp["sector_performance"]["as_of"] == "Mon 12 Oct 2026 close"
    assert [e["variable"] for e in imp["exposure"]] == ["rupee_stronger", "crude_rising", "yields_rising"]
    assert any(o["sector"] == "IT" and o["agrees"] for o in imp["overlap"])
    assert out["market_drivers"]["window"]["start"].startswith("2026-10-09T10:00")                   # 15:30 IST on the prior trading day, from the calendar
    crude_tile = next(t for t in out["risk_details"] if t["name"] == "n" or "Brent" in t["explanation"])
    assert "typically pressures Airlines, Paint, Chemical" in crude_tile["explanation"] and "(knowledge graph)" in crude_tile["explanation"]


@pytest.mark.asyncio
async def test_endpoint_without_a_graph_makes_no_exposure_claims_and_does_not_fail(monkeypatch, stubs):
    async def none_graph(force=False):
        return None

    monkeypatch.setattr(graph_mod, "load_graph_context", none_graph)
    monkeypatch.setattr(brief, "classify_session", lambda: classify_session(datetime(2026, 10, 12, 17, 0, tzinfo=IST)))
    out = await brief.get_daily_brief_intelligence()
    assert out["investor_implications"]["exposure"] == [] and out["investor_implications"]["sector_performance"]["available"]
    assert all("knowledge graph" not in t["explanation"] for t in out["risk_details"] + out["catalyst_details"])
    assert all("typically" not in t["explanation"] for t in out["risk_details"] + out["catalyst_details"])


@pytest.mark.asyncio
async def test_live_session_labels_the_sector_snapshot_as_live_not_a_close(monkeypatch, stubs):
    monkeypatch.setattr(brief, "classify_session", lambda: classify_session(datetime(2026, 10, 12, 11, 0, tzinfo=IST)))
    imp = (await brief.get_daily_brief_intelligence())["investor_implications"]
    assert imp["sector_performance"]["as_of"].startswith("live, retrieved ") and "close" not in imp["sector_performance"]["as_of"]


# ── no hand-typed sector lists left in the fact registry ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fact_registry_affected_sectors_come_from_the_graph(monkeypatch):
    import app.api.market as market
    import app.services.fact_registry as fr
    import app.services.opening_prediction_service as ops

    written = {}

    async def fake_upsert(db, fact_key, **fields):
        written[fact_key] = fields
        return fields

    async def overview():
        return {"indices": []}

    async def signals():
        return {"brent_crude": {"value": "71.3", "direction": "rising", "change": "+1%"}, "usd_inr": {"value": "88.1", "positive": True}}

    async def graph(force=False):
        return fake_graph()

    monkeypatch.setattr(fr, "_upsert", fake_upsert)
    monkeypatch.setattr(market, "market_overview", overview)
    monkeypatch.setattr(ops, "_gather_signals", signals)
    monkeypatch.setattr(graph_mod, "load_graph_context", graph)
    await fr.refresh_market_facts(None, include_forecast=False)
    crude = next(v for k, v in written.items() if "BRENT_CRUDE" in k)
    usd = next(v for k, v in written.items() if "USD_INR" in k)
    assert crude["affected_sectors"] == ["Airlines", "Oil & Gas", "Paint", "Chemical", "Cement"]
    assert usd["affected_sectors"] == ["IT", "Pharma", "Airlines", "Textiles", "Auto"]

    async def none_graph(force=False):
        return None

    monkeypatch.setattr(graph_mod, "load_graph_context", none_graph)
    written.clear()
    await fr.refresh_market_facts(None, include_forecast=False)
    assert next(v for k, v in written.items() if "BRENT_CRUDE" in k)["affected_sectors"] == []        # never a typed-in fallback list
