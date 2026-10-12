"""Daily Brief V2 Part A: 'What moved the market', investor implications, next-session scenarios and the investor takeaway. Covers dedup,
ranking, evidence labels, sparse data, and the guarantees that no causation, impact score, direction, probability or company impact is
invented. Pure functions plus the assembled endpoint with stubs; no network, no DB, no LLM."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

import app.api.daily_brief_intelligence as brief
import app.services.ai_service as ai
from app.services import daily_brief_composer as composer
from app.services import daily_brief_content as content
from app.services import daily_brief_drivers as d
from app.services.market_session_state import classify_session

IST = ZoneInfo("Asia/Kolkata")
NOW = datetime(2026, 10, 12, 12, 0, tzinfo=timezone.utc)      # 17:30 IST, after the close


def ev(eid, headline, *, tier="High", importance=6, sectors=(), tickers=(), source="news", origin="Economic Times", hours_ago=3, structural=False):
    return {"id": eid, "headline": headline, "one_liner": headline, "priority_tier": tier, "importance": importance, "sectors": list(sectors),
            "tickers": list(tickers), "source": source, "origin": origin, "is_structural": structural,
            "triaged_at": (NOW - timedelta(hours=hours_ago)).isoformat(), "sentiment": "bullish", "direction": "up", "confidence": 8}


SNAP = {
    "nifty": {"name": "NIFTY 50", "value": "22,363.35", "pct": -0.70}, "sensex": {"name": "SENSEX", "value": "71,924", "pct": -0.76},
    "banknifty": {"name": "BANK NIFTY", "value": "54,918", "pct": -0.61}, "vix": None,
    "breadth": {"advances": 18, "declines": 30, "unchanged": 1},
    "sectors": [{"id": "it", "name": "IT", "value": "-1.3%", "positive": False}, {"id": "bank", "name": "Banking", "value": "-0.8%", "positive": False},
                {"id": "pharma", "name": "Pharma", "value": "+0.1%", "positive": True}, {"id": "fmcg", "name": "FMCG", "value": "-2.0%", "positive": False}],
}
FACTS = [
    {"entity_key": "USD_INR", "entity_type": "forex", "direction": "down", "change_pct": None, "numeric_value": None},
    {"entity_key": "BRENT_CRUDE", "entity_type": "commodity", "direction": "rising", "change_pct": None, "numeric_value": None},
    {"entity_key": "INDIA_VIX", "entity_type": "market_index", "direction": "up", "change_pct": 6.2, "numeric_value": 6.2},
]


def build(events, snapshot=SNAP, facts=FACTS, **kw):
    return d.build_market_drivers(events, snapshot=snapshot, facts=facts, now=NOW, **kw)


# ── dedup ─────────────────────────────────────────────────────────────────────────────────────────────────────────

def test_same_development_from_several_outlets_is_shown_once():
    events = [
        ev("a", "RBI keeps repo rate unchanged at 5.5% and holds stance", origin="RBI", source="policy", tier="Critical"),
        ev("b", "RBI keeps repo rate unchanged at 5.5%, holds its stance", origin="Livemint"),
        ev("c", "RBI holds repo rate at 5.5% and keeps stance unchanged", origin="NDTV Profit"),
        ev("d", "Infosys wins large cloud deal from European bank", sectors=["IT"], tickers=["INFY"]),
    ]
    out = build(events)
    heads = [i["headline"] for i in out["items"]]
    assert sum("repo rate" in h.lower() for h in heads) == 1
    rbi = next(i for i in out["items"] if "repo" in i["headline"].lower())
    assert rbi["articles_merged"] == 3 and any("3 articles" in r for r in rbi["relevance"])


def test_same_event_id_is_always_merged_and_different_numbers_are_not():
    same = d.cluster_events([ev("x", "Sensex ends 560 points lower"), ev("x", "Different wording entirely about the close")])
    assert len(same) == 1
    diff = d.cluster_events([ev("p", "Company profit rises 12% in the quarter", origin="A"), ev("q", "Company profit rises 15% in the quarter", origin="B")])
    assert len(diff) == 2


# ── evidence labels ───────────────────────────────────────────────────────────────────────────────────────────────

RUPEE = ev("r1", "Rupee opens over 1% higher on RBI measures to curb dollar demand", origin="RBI", source="policy", tier="Critical", importance=9)


def test_confirmed_needs_authority_source_attribution_and_a_matching_verified_move():
    out = build([RUPEE])
    it = out["items"][0]
    assert it["evidence_label"] == "confirmed_driver"                                  # RBI + 'on RBI measures' + USD/INR verified lower = rupee higher
    assert any("source itself ties" in r for r in it["relevance"])
    # the verified data disagrees (USD/INR up while the headline says rupee higher): not confirmed
    contradicting = [dict(FACTS[0], direction="up")] + FACTS[1:]
    assert build([RUPEE], facts=contradicting)["items"][0]["evidence_label"] == "potential_contributor"
    # same headline from a non-authoritative outlet: not confirmed
    assert build([dict(RUPEE, origin="Economic Times", source="news")])["items"][0]["evidence_label"] == "potential_contributor"
    # no causal connector in the headline: not confirmed
    assert build([dict(RUPEE, headline="Rupee higher at 95.73, RBI active")])["items"][0]["evidence_label"] == "potential_contributor"


def test_same_day_coincidence_is_a_potential_contributor_and_says_timing_is_not_cause():
    e = ev("t1", "TCS wins large deal from European bank", sectors=["IT"], tickers=["TCS"])
    it = build([e])["items"][0]
    assert it["evidence_label"] == "potential_contributor"
    text = " ".join(it["relevance"])
    assert "Coincided with IT -1.30%" in text and "Timing alone does not show that this caused the move" in text
    assert "caused" not in text.replace("does not show that this caused", "")


def test_commentary_is_separated_and_limited():
    events = [
        ev("c1", "Nifty outlook: what to expect next week", tier="High"),
        ev("c2", "Stocks to watch: ten picks for tomorrow", tier="High"),
        ev("c3", "Should you buy banks after the fall?", tier="High"),
        ev("m1", "RBI announces new liquidity framework", origin="RBI", source="policy", tier="Critical"),
    ]
    out = build(events)
    assert len(out["groups"]["commentary"]) == 1
    assert all(i["evidence_label"] != "commentary" for i in out["groups"]["potential_contributor"] + out["groups"]["confirmed_driver"])


def test_low_priority_single_company_items_are_not_market_developments():
    assert build([ev("l1", "Small company appoints new auditor", tier="Low", importance=2, tickers=["XYZ"])])["items"] == []


# ── ranking, cap and sparse data ────────────────────────────────────────────────────────────────────────────────

def test_ranking_prefers_confirmed_then_importance_freshness_and_never_pads():
    topics = ["Crude oil inventories draw unexpectedly", "Monsoon rainfall deficit narrows across states", "Steel import duty extended by government",
              "Airline fuel surcharge raised on domestic routes", "Cement makers announce price hike", "Tea exports touch record volume",
              "Telecom spectrum auction schedule revealed", "Fertiliser subsidy outlay increased for rabi season"]
    events = [RUPEE] + [ev(f"e{i}", topic, sectors=["Banking"], tier="High", hours_ago=i + 1) for i, topic in enumerate(topics)]
    out = build(events)
    assert len(out["items"]) == d.MAX_ITEMS and out["items"][0]["evidence_label"] == "confirmed_driver"
    fresh_first = [i["id"] for i in out["items"][1:]]
    assert fresh_first == sorted(fresh_first, key=lambda x: int(x[1:]))                # equal evidence: fresher first
    sparse = build([RUPEE])
    assert len(sparse["items"]) == 1 and "nothing was added to fill the space" in sparse["note"]
    empty = build([])
    assert empty["items"] == [] and empty["note"] == "No development met the evidence threshold for this session."


def test_no_impact_score_direction_or_confidence_is_exposed():
    it = build([RUPEE, ev("t1", "TCS wins large deal", sectors=["IT"], tickers=["TCS"])])["items"][0]
    blob = repr(it).lower()
    for forbidden in ("impact", "bullish", "bearish", "sentiment", "confidence", "priority_score", "importance", "score"):
        assert forbidden not in blob.replace("evidence_label", "")


def test_company_connections_are_only_ever_mentioned():
    out = build([ev("t1", "TCS wins large deal", sectors=["IT"], tickers=["tcs.ns", "INFY"])])
    assert out["items"][0]["companies"] == [{"symbol": "TCS", "relation": "mentioned"}, {"symbol": "INFY", "relation": "mentioned"}]


def test_links_carry_event_slug_and_published_article():
    out = build([ev("t1", "TCS wins large deal", sectors=["IT"])], event_meta={"t1": {"slug": "tcs-deal-abc", "title": "TCS wins large deal", "source": "Economic Times", "published_at": "2026-10-12T05:00:00+00:00"}},
                article_links={"t1": "/newsroom/article/tcs-deal-analysis"})
    it = out["items"][0]
    assert it["links"] == {"event": "/events/tcs-deal-abc", "article": "/newsroom/article/tcs-deal-analysis"}
    assert it["source"] == "Economic Times" and it["published_at"].startswith("2026-10-12T05:00")
    assert all(v is None or v.startswith("/") for v in it["links"].values())          # internal links only


# ── implications ───────────────────────────────────────────────────────────────────────────────────────────────────

def test_implications_name_sectors_with_verified_moves_and_only_mention_companies():
    drivers = build([ev("t1", "TCS wins large deal from European bank", sectors=["IT"], tickers=["TCS"]),
                     ev("b1", "Banks tighten lending standards after RBI circular", sectors=["Banking"], tickers=["HDFCBANK"], tier="High")])
    imp = d.build_implications(drivers)
    names = {r["sector"]: r for r in imp["items"]}
    assert names["IT"]["verified_move_pct"] == -1.3 and "-1.30%" in names["IT"]["why"]
    assert names["IT"]["companies_mentioned"] == ["TCS"] and "not an assessment of impact" in names["IT"]["companies_label"]
    blob = repr(imp).lower()
    for forbidden in ("buy", "sell", "bullish", "bearish", "outperform", "target"):
        assert forbidden not in blob


def test_implications_exclude_commentary_and_say_so_when_empty():
    drivers = build([ev("c1", "Banking outlook: what to expect", sectors=["Banking"])])
    imp = d.build_implications(drivers)
    assert imp["items"] == [] and imp["note"]


# ── scenarios ─────────────────────────────────────────────────────────────────────────────────────────────────────

ROWS = [
    {"label": "GIFT Nifty", "value": "-0.4%", "direction": "negative", "detail": "Overnight GIFT City signal"},
    {"label": "Global Breadth", "value": "4/10 positive", "direction": "neutral", "detail": "40% positive"},
    {"label": "FII Flow", "value": "-Rs 1,200 Cr", "direction": "negative", "detail": "Previous session, NSE"},
    {"label": "India VIX", "value": "15.2", "direction": "contextual", "detail": "calm"},
    {"label": "S&P 500 Fut", "value": "-0.5%", "direction": "negative", "detail": "Overnight US futures"},
]
CATALYSTS = [{"date": "Oct 14, 2026", "title": "CPI inflation data", "category": "Macro"}]


def scen(rows=ROWS, status="live"):
    return d.build_scenarios(rows, CATALYSTS, target_label="Tue 13 Oct 2026", generated_at="2026-10-12T12:00:00+00:00", gift_status=status)


def test_scenarios_are_conditional_with_no_probability_target_or_range():
    out = scen()
    assert out["available"] and [s["key"] for s in out["scenarios"]] == ["bullish", "neutral", "bearish"]
    assert out["scenarios"][0]["condition"].startswith("If ") and "GIFT Nifty indicates a higher open" in out["scenarios"][0]["condition"]
    assert "CPI inflation data (Oct 14, 2026)" in out["catalysts"]
    text = " ".join([s["condition"] + " " + " ".join(s["watch"]) for s in out["scenarios"]]).lower()      # what a reader is told in each scenario
    for forbidden in ("probab", "chance", "target", "support", "resistance", "range", "expected move", "likely", "%"):
        assert forbidden not in text
    assert set(out["scenarios"][0]) == {"key", "title", "condition", "watch"}                            # no probability/target/range fields at all
    assert not any(s.get("expected") or s.get("probability") for s in out["scenarios"])


def test_scenarios_unavailable_without_signals_and_stale_gift_is_reported():
    out = d.build_scenarios([{"label": "India VIX", "value": "15", "direction": "contextual"}], [], target_label="x", generated_at="t", gift_status=None)
    assert out["available"] is False and out["reason"]
    assert scen(status="stale")["gift_nifty_status"] == "stale"


# ── takeaway ─────────────────────────────────────────────────────────────────────────────────────────────────────

def test_takeaway_is_distinct_from_summary_and_states_uncertainty_and_observables():
    drivers = build([RUPEE, ev("t1", "TCS wins large deal from European bank", sectors=["IT"], tickers=["TCS"])])
    sc = scen()
    verdict = {"kind": "realized", "direction": "Negative", "headline": "Lower close"}
    tk = d.build_takeaway(drivers, sc, verdict, composer.breadth_tone(SNAP["breadth"]), CATALYSTS)
    assert tk["development"]["headline"].startswith("Rupee opens") and tk["development"]["evidence_label"] == "confirmed_driver"
    assert tk["uncertainty"] and tk["monitor"] and len(tk["monitor"]) <= 4
    session = classify_session(datetime(2026, 10, 12, 17, 0, tzinfo=IST))
    summary = content.build_summary(session, verdict, [], [], [])
    assert not set(content.sentences_of(tk["uncertainty"])) & set(content.sentences_of(summary))
    assert content.normalise(tk["development"]["text"]) not in content.normalise(summary)


def test_takeaway_without_confirmed_driver_says_cause_is_not_established():
    tk = d.build_takeaway(build([ev("t1", "TCS wins large deal", sectors=["IT"])]), scen(), {"direction": "Negative"}, "broad_decline", CATALYSTS)
    assert "No development is confirmed" in tk["uncertainty"]
    none = d.build_takeaway(build([]), scen(), {"direction": "Negative"}, None, [])
    assert none["development"] is None and "not established" in none["uncertainty"]


def test_event_window_starts_at_the_previous_close():
    from datetime import date
    start, hours = d.window_start_utc(date(2026, 10, 12), NOW)
    assert start == datetime(2026, 10, 9, 15, 30, tzinfo=IST).astimezone(timezone.utc) and 24 <= hours <= 120


# ── assembled endpoint ───────────────────────────────────────────────────────────────────────────────────────────

def _endpoint_stubs(monkeypatch, when, events=None):
    async def snapshot(session):
        return {**SNAP, "sentiment_score": None, "market_status": brief._status_for(session), "movers": {"gainers": [], "losers": []}}

    async def none_list(*a, **k):
        return []

    async def facts(session):
        return [dict(f, name=f["entity_key"], fact_key=f"market:{f['entity_key']}:x", value="1", source="s", evidence={}, claim="c",
                     affected_sectors=[], affected_companies=[], observed_at=None, confidence=None) for f in FACTS]

    async def hist(events):
        return {"available": False, "message": ""}

    async def drv(session, now):
        return (events or []), {}, {}

    async def scn():
        return ROWS, "live"

    async def forecast(session):
        return {"kind": "forecast", "headline": "Opening outlook", "direction": "Neutral", "reasoning": "r", "confidence": None, "primary_drivers": [], "risks": [],
                "target_date": session.forecast_target_date.isoformat(), "forecast": {"signals": []}}

    async def no_llm(*a, **k):
        raise AssertionError("LLM call")

    for name, fn in (("_get_snapshot", snapshot), ("_read_raw_events", none_list), ("_get_facts", facts), ("_get_historical_context", hist),
                     ("_get_watch_next", lambda: _watch()), ("_get_driver_inputs", drv), ("_get_scenario_inputs", scn), ("_get_forecast_verdict", forecast)):
        monkeypatch.setattr(brief, name, fn)
    monkeypatch.setattr(ai, "_call_with_fallback", no_llm)
    monkeypatch.setattr(brief, "classify_session", lambda: classify_session(when))


async def _watch():
    return CATALYSTS


@pytest.mark.asyncio
@pytest.mark.parametrize("when,state,scenarios_available", [
    (datetime(2026, 10, 12, 8, 30, tzinfo=IST), "pre_open", True),
    (datetime(2026, 10, 12, 11, 0, tzinfo=IST), "open", False),
    (datetime(2026, 10, 12, 17, 0, tzinfo=IST), "after_close", True),
    (datetime(2026, 10, 10, 12, 0, tzinfo=IST), "weekend", True),
    (datetime(2026, 10, 20, 12, 0, tzinfo=IST), "holiday", True),
])
async def test_all_new_sections_across_sessions(monkeypatch, when, state, scenarios_available):
    _endpoint_stubs(monkeypatch, when, events=[RUPEE])
    out = await brief.get_daily_brief_intelligence()
    assert out["session"]["state"] == state
    assert out["market_drivers"]["items"][0]["evidence_label"] == "confirmed_driver"
    assert out["scenarios"]["available"] is scenarios_available
    assert out["takeaway"]["development"] and out["investor_implications"] is not None
    if scenarios_available:
        assert out["scenarios"]["target"].startswith(composer._fmt_date(classify_session(when).forecast_target_date))


@pytest.mark.asyncio
async def test_sparse_and_empty_data_render_honestly_and_old_keys_remain(monkeypatch):
    _endpoint_stubs(monkeypatch, datetime(2026, 10, 12, 17, 0, tzinfo=IST), events=[])
    out = await brief.get_daily_brief_intelligence()
    assert out["market_drivers"]["items"] == [] and out["market_drivers"]["note"]
    assert out["investor_implications"]["items"] == [] and out["takeaway"]["development"] is None
    for old in ("market_verdict", "market_snapshot", "events", "facts", "summary", "why_today_matters", "stocks_to_watch", "sector_intelligence",
                "historical_context", "catalysts", "risks", "catalyst_details", "risk_details", "what_to_watch_next", "questions", "evidence", "generated_at"):
        assert old in out


@pytest.mark.asyncio
async def test_faq_names_evidence_labels_and_never_claims_cause(monkeypatch):
    _endpoint_stubs(monkeypatch, datetime(2026, 10, 12, 17, 0, tzinfo=IST),
                    events=[RUPEE, ev("t1", "TCS wins large deal from European bank", sectors=["IT"], tickers=["TCS"])])
    out = await brief.get_daily_brief_intelligence()
    q = next(x for x in out["questions"] if x["question"].startswith("What may have moved the market"))
    assert "Confirmed:" in q["answer"] and "Potential contributors:" in q["answer"] and "Timing alone does not establish cause" in q["answer"]
    answers = [content.normalise(x["answer"]) for x in out["questions"]]
    assert len(answers) == len(set(answers))
    tk = out["takeaway"]
    for s in content.sentences_of(tk["uncertainty"]):
        assert content.normalise(s) not in {content.normalise(x) for x in content.sentences_of(out["summary"])}


def test_other_angles_on_the_same_development_share_one_slot():
    # the three RBI-measures stories of 2026-10-12: rupee rally, intervention, bond sell-off (different wording, same development, minutes apart)
    events = [
        ev("a", "Rupee opens over 1% higher at 95.73 on RBI measures to curb dollar demand", origin="Business Standard", tier="Critical"),
        ev("b", "RBI measures, intervention spark rupee's sharpest rally in six months", origin="Economic Times", tier="Critical"),
        ev("c", "India benchmark bond posts worst day in six months on RBI measures", origin="Economic Times", tier="Critical"),
        ev("d", "Goodluck India shares surge 17% as merger expands", origin="Economic Times", tier="High"),
    ]
    out = build(events)
    assert len(out["items"]) == 2
    rbi = next(i for i in out["items"] if "rbi" in i["headline"].lower() or "rupee" in i["headline"].lower())
    assert rbi["articles_merged"] == 3 and any("other angles on the same development" in r for r in rbi["relevance"])


def test_unrelated_stories_that_share_one_word_are_not_merged():
    events = [ev("a", "RBI penalises two cooperative banks for norm violations", tier="High"),
              ev("b", "RBI keeps repo rate unchanged at 5.5%", tier="Critical", origin="RBI", source="policy")]
    assert len(build(events)["items"]) == 2
    far = [ev("a", "RBI measures curb dollar demand rupee rally", hours_ago=1), ev("b", "RBI measures curb dollar demand rupee rally again", hours_ago=20)]
    assert len(d.merge_related([[far[0]], [far[1]]])) == 2                     # outside the six-hour window


def test_potential_contributor_cites_the_verified_variable_the_headline_names():
    e = ev("r2", "Rupee opens higher at 95.73 as dollar demand eases", origin="Business Standard", tier="Critical")
    it = build([e])["items"][0]
    assert it["evidence_label"] == "potential_contributor" and any("USD/INR lower" in r and "Timing alone" in r for r in it["relevance"])
