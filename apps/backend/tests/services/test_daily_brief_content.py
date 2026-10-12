"""Daily Brief V2, Phase 2: catalyst/risk classification with evidence-backed explanations, honest sentiment scores, session-aware
non-repeating FAQs, de-duplicated evidence and consistent structured content. No network, no DB, no LLM."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

import app.api.daily_brief_intelligence as brief
import app.services.ai_service as ai
from app.services import daily_brief_composer as composer
from app.services import daily_brief_content as content
from app.services import market_sentiment as sent
from app.services.market_session_state import classify_session

IST = ZoneInfo("Asia/Kolkata")


def at(y, m, d, hh, mm):
    return datetime(y, m, d, hh, mm, tzinfo=IST)


def fact(key, name, etype="market_index", direction=None, pct=None, value="1", **kw):
    return {"fact_key": f"market:{key}:2026-10-12", "entity_type": etype, "entity_key": key, "name": name, "value": value,
            "direction": direction, "change_pct": pct, "numeric_value": pct, "source": "feed", "evidence": kw.pop("evidence", {}),
            "claim": kw.pop("claim", f"{name} claim."), "affected_sectors": kw.pop("sectors", []), "affected_companies": kw.pop("companies", []),
            "confidence": None, "observed_at": "2026-10-12T11:00:00Z", **kw}


# ── catalysts and risks ──────────────────────────────────────────────────────────────────────────────────────────────

def test_rising_vix_is_a_risk_with_an_explanation_and_falling_vix_a_catalyst():
    up = content.catalysts_and_risks([fact("INDIA_VIX", "INDIA VIX", direction="up", pct=4.2, value="15.8")])
    assert up["risks"] == ["INDIA VIX"] and up["catalysts"] == []
    assert "rose to 15.8 (+4.20%)" in up["risk_details"][0]["explanation"] and "volatility is higher" in up["risk_details"][0]["explanation"]
    down = content.catalysts_and_risks([fact("INDIA_VIX", "INDIA VIX", direction="down", pct=-3.0, value="13.1")])
    assert down["catalysts"] == ["INDIA VIX"] and down["risks"] == [] and "eased" in down["catalyst_details"][0]["explanation"]


def test_crude_and_rupee_rising_are_risks_falling_are_catalysts():
    out = content.catalysts_and_risks([
        fact("BRENT_CRUDE", "Brent Crude Oil", "commodity", "rising", value="71.3"),
        fact("USD_INR", "USD/INR", "forex", "up", value="88.1"),
    ])
    assert out["risks"] == ["Brent Crude Oil", "USD/INR"]
    out = content.catalysts_and_risks([fact("BRENT_CRUDE", "Brent Crude Oil", "commodity", "falling", value="68")])
    assert out["catalysts"] == ["Brent Crude Oil"]


def test_index_outcomes_and_flat_moves_are_not_listed_as_drivers():
    out = content.catalysts_and_risks([
        fact("NIFTY_50", "NIFTY 50", direction="down", pct=-0.7), fact("SENSEX", "SENSEX", direction="down", pct=-0.76),
        fact("INDIA_VIX", "INDIA VIX", direction="up", pct=0.04),
    ])
    assert out["catalysts"] == [] and out["risks"] == []


def test_event_sentiment_classification_carries_the_claim_as_explanation():
    out = content.catalysts_and_risks([
        fact("e1", "Order win", "event", claim="Company X won a large order.", evidence={"sentiment": "bullish"}),
        fact("e2", "Probe", "event", claim="Regulator opened a probe.", evidence={"sentiment": "bearish"}),
        fact("e3", "Neutral item", "event", evidence={"sentiment": None}),
    ])
    assert out["catalyst_details"][0]["explanation"] == "Company X won a large order." and out["risk_details"][0]["explanation"] == "Regulator opened a probe."
    assert out["catalysts"] == ["Order win"] and out["risks"] == ["Probe"]


def test_company_impact_is_never_claimed():
    rows = content.why_today_matters([
        fact("BRENT_CRUDE", "Brent Crude Oil", "commodity", "rising", claim="Brent is rising.", sectors=["Aviation", "Paints"], companies=["INDIGO"]),
        fact("e1", "Order win", "event", claim="Company X won an order.", sectors=["Power"], companies=["adanient.ns"]),
    ])
    assert rows[0]["companies_named"] == [] and rows[0]["affected"] == ["Aviation", "Paints"] and rows[0]["affected_label"] == "Typically sensitive sectors"
    assert rows[1]["companies_named"] == ["ADANIENT"] and rows[1]["affected_label"] == "Sectors tagged"


# ── sentiment ──────────────────────────────────────────────────────────────────────────────────────────────────────

def q(name, pct, value="1"):
    return {"name": name, "value": value, "pct": pct}


def test_sentiment_score_moves_with_the_market_and_vix_counts_against():
    falling = sent.index_sentiment_score([q("NIFTY 50", -0.7), q("SENSEX", -0.76), q("BANK NIFTY", -0.9), q("INDIA VIX", 5.0)])
    rising = sent.index_sentiment_score([q("NIFTY 50", 0.8), q("SENSEX", 0.9), q("BANK NIFTY", 1.0), q("INDIA VIX", -4.0)])
    flat = sent.index_sentiment_score([q("NIFTY 50", 0.0), q("SENSEX", 0.0), q("INDIA VIX", 0.0)])
    assert falling < flat < rising and falling < 50 and rising > 50 and flat == 50
    old_style_vix_only_rise = sent.index_sentiment_score([q("NIFTY 50", -0.7), q("INDIA VIX", 5.0)])
    assert old_style_vix_only_rise < 50                       # a rising VIX no longer counts as a 'positive' index


def test_sentiment_is_none_without_data_and_ignores_placeholders():
    assert sent.index_sentiment_score([]) is None
    assert sent.index_sentiment_score([{"name": "NIFTY 50", "value": "—", "pct": 0.0}]) is None


def test_insights_are_not_constant_any_more():
    a = sent.breadth_sentiment(18, 30)
    b = sent.breadth_sentiment(40, 6)
    assert a["sentiment"] == "Bearish" and b["sentiment"] == "Bullish" and a["fear_greed"] < 50 < b["fear_greed"]
    assert sent.breadth_sentiment(24, 24)["sentiment"] == "Neutral" and sent.breadth_sentiment(24, 24)["confidence"] == 50
    assert sent.breadth_sentiment(0, 0) is None and sent.breadth_sentiment(None, 3) is None


# ── whole payload ────────────────────────────────────────────────────────────────────────────────────────────────────

SNAP = {
    "nifty": {"name": "NIFTY 50", "value": "22,363.35", "change": "-0.70%", "pct": -0.70},
    "sensex": {"name": "SENSEX", "value": "71,924.68", "change": "-0.76%", "pct": -0.76},
    "banknifty": {"name": "BANK NIFTY", "value": "48,100", "change": "-0.90%", "pct": -0.90},
    "vix": {"name": "INDIA VIX", "value": "15.8", "change": "+4.20%", "pct": 4.2},
    "breadth": {"advances": 18, "declines": 30, "unchanged": 1},
    "sectors": [{"id": "it", "name": "IT", "value": "-1.8%", "positive": False}, {"id": "bank", "name": "Banking", "value": "-0.9%", "positive": False},
                {"id": "fmcg", "name": "FMCG", "value": "+0.4%", "positive": True}, {"id": "pharma", "name": "Pharma", "value": "+0.1%", "positive": True}],
    "movers": {"gainers": [{"symbol": "ITC", "value": "+1.2%"}], "losers": [{"symbol": "TCS", "value": "-2.4%"}]},
    "sentiment_score": 38, "market_status": {}, "unavailable": False,
}
EVENT = {"id": "e1", "headline": "RBI keeps repo rate unchanged", "one_liner": "RBI held the repo rate and kept its stance.", "priority_tier": "Critical",
         "priority_score": 90, "sectors": ["Banking"], "tickers": ["HDFCBANK"], "sentiment": "bullish", "origin": "RBI"}
FACTS = [
    fact("NIFTY_50", "NIFTY 50", direction="down", pct=-0.7, value="22,363.35", claim="NIFTY 50 closed at 22,363.35 (-0.70%) in the Mon 12 Oct 2026 session."),
    fact("INDIA_VIX", "INDIA VIX", direction="up", pct=4.2, value="15.8"),
    fact("BRENT_CRUDE", "Brent Crude Oil", "commodity", "rising", value="71.3", claim="Brent crude is rising at 71.3 (+1.0%).", sectors=["Aviation", "Paints"]),
    fact("e1", "RBI keeps repo rate unchanged", "event", claim=EVENT["one_liner"], evidence={"sentiment": "bullish"}, sectors=["Banking"], companies=["HDFCBANK"]),
]


@pytest.fixture
def payload(monkeypatch):
    async def snapshot(session):
        return {**SNAP, "market_status": brief._status_for(session)}

    async def events():
        return [EVENT]

    async def facts(session):
        return [dict(f) for f in FACTS]

    async def historical(events):
        return {"available": False, "message": "n/a"}

    async def watch():
        return [{"date": "Oct 14, 2026", "category": "Macro", "title": "CPI inflation data", "description": None}]

    async def no_llm(*a, **k):
        raise AssertionError("an LLM call was made while composing the brief")

    monkeypatch.setattr(brief, "_get_snapshot", snapshot)
    monkeypatch.setattr(brief, "_read_raw_events", events)
    monkeypatch.setattr(brief, "_get_facts", facts)
    monkeypatch.setattr(brief, "_get_historical_context", historical)
    monkeypatch.setattr(brief, "_get_watch_next", watch)
    monkeypatch.setattr(ai, "_call_with_fallback", no_llm)
    monkeypatch.setattr(ai, "_call_provider", no_llm)
    monkeypatch.setattr(brief, "classify_session", lambda: classify_session(at(2026, 10, 12, 17, 0)))
    import asyncio
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(brief.get_daily_brief_intelligence())


def test_after_close_payload_is_a_negative_session_with_no_bullish_language(payload):
    v = payload["market_verdict"]
    assert v["kind"] == "realized" and v["direction"] == "Negative" and v["headline"] == "Lower close"
    blob = " ".join([payload["summary"], v["reasoning"]] + [x["answer"] for x in payload["questions"]]).lower()
    for bad in ("bullish", "upside", "gap-up", "opening outlook", "tomorrow"):
        assert bad not in blob


def test_vix_is_a_risk_in_the_payload(payload):
    assert "INDIA VIX" in payload["risks"] and "INDIA VIX" not in payload["catalysts"]
    assert any("volatility is higher" in d["explanation"] for d in payload["risk_details"])


def test_faqs_are_distinct_session_aware_and_do_not_repeat_the_verdict(payload):
    qs = payload["questions"]
    assert 3 <= len(qs) <= 5
    questions = [x["question"] for x in qs]
    answers = [content.normalise(x["answer"]) for x in qs]
    assert len(set(questions)) == len(questions) and len(set(answers)) == len(answers)
    verdict_sentences = {content.normalise(s) for s in content.sentences_of(payload["market_verdict"]["reasoning"])}
    summary_sentences = {content.normalise(s) for s in content.sentences_of(payload["summary"])}
    for x in qs:
        for s in content.sentences_of(x["answer"]):
            assert content.normalise(s) not in verdict_sentences | summary_sentences
    assert any("sectors" in t.lower() for t in questions) and any("index levels" in t.lower() for t in questions)


def test_summary_adds_driver_and_risk_without_repeating_the_verdict_card(payload):
    assert payload["summary"].startswith("Lower close on Mon 12 Oct 2026.")
    assert "Main risk:" in payload["summary"]
    assert "30 declined" not in payload["summary"] and "0.70% lower" not in payload["summary"]


def test_evidence_has_no_repeated_claims(payload):
    claims = [content.normalise(e["claim"]) for e in payload["evidence"]]
    assert len(claims) == len(set(claims)) and claims


def test_metadata_sources_are_consistent(payload):
    # The page builds its FAQ JSON-LD from payload["questions"] and its description from payload["summary"]: one source each.
    assert all(x["question"].endswith("?") and x["answer"].strip() for x in payload["questions"])
    assert payload["session"]["state"] == "after_close" and payload["market_verdict"]["session_date"] == payload["session"]["reference_session_date"]


def test_stocks_to_watch_are_labelled_as_named_not_assessed(payload):
    assert payload["stocks_to_watch"] and all(s["basis"] == "named_in_event" for s in payload["stocks_to_watch"])
    assert all(r["companies_named"] != [] or r["affected"] for r in payload["why_today_matters"])


# ── missing / stale / contradictory inputs ───────────────────────────────────────────────────────────────────────────

def test_ledger_drops_repeated_sentences_and_questions():
    ledger = content.Ledger()
    ledger.add("Nifty fell. Banks led the fall.")
    assert ledger.is_duplicate("Banks led the fall.") and not ledger.is_duplicate("Banks led the fall. IT also fell.")
    assert ledger.fresh_sentences("Nifty fell. IT also fell.") == ["IT also fell."]


def test_questions_with_no_data_are_not_invented():
    s = classify_session(at(2026, 10, 12, 17, 0))
    out = content.build_questions(s, {"kind": "unavailable"}, {}, [], [], [], [], content.Ledger())
    assert out == []


def test_forecast_session_faq_uses_signal_inputs_not_the_realized_wording():
    s = classify_session(at(2026, 10, 12, 8, 30))
    verdict = {"kind": "forecast", "forecast": {"signals": [{"label": "GIFT Nifty", "direction": "negative", "detail": "Overnight GIFT City signal"}]}}
    out = content.build_questions(s, verdict, {}, [], [], [], [], content.Ledger())
    assert out and "opening outlook for Mon 12 Oct 2026" in out[0]["question"] and "GIFT Nifty: negative" in out[0]["answer"]


def test_sector_answer_does_not_call_a_falling_sector_a_leader():
    s = classify_session(at(2026, 10, 12, 17, 0))
    snap = {"sectors": [{"name": "IT", "value": "-1.8%"}, {"name": "Pharma", "value": "-0.1%"}, {"name": "Auto", "value": "+0.5%"}]}
    out = content.build_questions(s, {"kind": "realized"}, snap, [], [], [], [], content.Ledger())
    ans = next(x["answer"] for x in out if "sectors" in x["question"].lower())
    assert "Led: Auto +0.50%." in ans and "Pharma" in ans.split("Lagged:")[1] and "Led: Auto +0.50%, Pharma" not in ans
    all_down = {"sectors": [{"name": "IT", "value": "-1.8%"}, {"name": "Auto", "value": "-0.5%"}]}
    ans = next(x["answer"] for x in content.build_questions(s, {"kind": "realized"}, all_down, [], [], [], [], content.Ledger()))
    assert ans.startswith("No tracked sector gained.")
