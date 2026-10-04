"""Investment Watch: sector-relevant indicators, honest flat/rising/falling wording, verdict age, and a next trigger that is never another company's results."""
from datetime import datetime, timedelta, timezone

from app.services.ai_search import investment_watch as iw


def test_an_it_company_watches_the_rupee_and_us_tech_not_crude_oil():
    labels = [s[0] for s in iw.watch_specs("Technology")]
    assert "US dollar / rupee" in labels and "Nasdaq" in labels and "Crude oil (Brent)" not in labels
    assert [s[0] for s in iw.watch_specs("AUTOMOTIVE")][0] == "Crude oil (Brent)"          # case-insensitive; an input cost for autos
    assert [s[0] for s in iw.watch_specs("Unknown sector")] == ["Nifty 50", "Crude oil (Brent)"]
    assert [s[0] for s in iw.watch_specs(None)] == ["Nifty 50", "Crude oil (Brent)"]


def test_quote_rows_use_real_quotes_only_and_call_a_tiny_move_flat():
    inr = iw.watch_specs("Technology")[0]
    assert iw.quote_trigger(inr, None) is None
    up = iw.quote_trigger(inr, {"price": 88.234, "pct": 0.42})
    assert up["status"] == "rising" and up["detail"] == "₹88.23 per US$ (+0.4%)" and up["scope"] == "sector" and up["why"].endswith(".")
    flat = iw.quote_trigger(inr, {"price": 88.0, "pct": 0.0})                                # the old panel printed "rising ... (+0.0%)"
    assert flat["status"] == "flat" and iw.quote_trigger(inr, {"price": 88.0, "pct": -0.31})["status"] == "falling"
    assert iw.quote_trigger(inr, {"price": 96.3, "pct": -0.01})["detail"] == "₹96.30 per US$ (0.0%)"      # not "-0.0%"


def _row(category, title, days):
    return {"category": category, "title": title, "date": "Oct 20, 2026", "description": "d", "days_until": days}


def test_next_trigger_is_the_companys_own_event_else_a_market_wide_one_never_another_companys_results():
    mine = [_row("Results", "TCS Q2 results", 12)]
    allrows = [_row("Results", "HDFC Bank Q2 results", 3), _row("RBI", "RBI policy decision", 5)]
    assert iw.pick_next_trigger(mine, allrows)["scope"] == "company"
    market = iw.pick_next_trigger([], allrows)
    assert market["label"] == "RBI policy decision" and market["scope"] == "market"
    assert iw.pick_next_trigger([], [_row("Results", "HDFC Bank Q2 results", 3)]) is None


def test_verdict_age_in_whole_days_and_none_for_a_bad_date():
    today = datetime.now(timezone.utc).date()
    assert iw._age_days((today - timedelta(days=46)).isoformat()) == 46
    assert iw._age_days(today.isoformat()) == 0 and iw._age_days("not a date") is None and iw._age_days(None) is None


def test_names_other_company_flags_comparison_text():
    from app.services.ai_search.investment_watch import names_other_company
    uni = [{"symbol": "TCS", "name": "Tata Consultancy Services Ltd"}, {"symbol": "INFY", "name": "Infosys Limited"}]
    assert names_other_company("Infosys's deal pipeline is thinning while TCS wins deals.", "TCS", uni[0]["name"], uni)
    assert not names_other_company("TCS continues to win AI and cloud deals.", "TCS", uni[0]["name"], uni)
    assert not names_other_company(None, "TCS", uni[0]["name"], uni)


def test_record_snapshot_does_not_store_comparison_why(monkeypatch):
    import asyncio
    from types import SimpleNamespace
    from app.services.ai_search import investment_watch as iw
    monkeypatch.setattr("app.api.companies._NSE_UNIVERSE", [{"symbol": "TCS", "name": "Tata Consultancy Services Ltd"}, {"symbol": "INFY", "name": "Infosys Limited"}])
    added = []

    class DB:
        async def execute(self, *_a, **_k):
            return SimpleNamespace(scalar_one_or_none=lambda: None)
        def add(self, row): added.append(row)
        async def commit(self): pass

    subject = {"subject_key": "company:TCS", "subject_type": "company", "subject_label": "TCS", "company_name": "Tata Consultancy Services Ltd"}
    asyncio.run(iw.record_snapshot(DB(), subject, "q", "r1", "Cautious", None, 50, "Infosys pipeline is thinning while TCS wins deals."))
    asyncio.run(iw.record_snapshot(DB(), subject, "q", "r2", "Cautious", None, 50, "TCS keeps winning AI deals."))
    assert added[0].why is None and added[0].verdict_scale == "Cautious"
    assert added[1].why == "TCS keeps winning AI deals."
