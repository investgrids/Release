"""Step 6: the landing page's example questions follow the live market, with no model call, and never offer a question the resolver does not recognise."""
from datetime import datetime, timezone

from app.services.ai_search import suggestions as sg

NOW = datetime(2026, 10, 5, 4, 0, tzinfo=timezone.utc)
SECTORS = [
    {"name": "Banking", "value": "-1.2%"},
    {"name": "IT", "value": "+0.9%"},
    {"name": "Pharma", "value": "+0.1%"},  # below the 0.3% threshold
]


def test_sector_moves_become_questions_with_a_live_note():
    out = sg.build_suggestions(SECTORS, [], now=NOW)
    by_q = {i["query"]: i for i in out["items"]}
    assert "What is driving the Banking sector today?" in by_q
    assert by_q["What is driving the Banking sector today?"]["note"] == "Banking -1.2% today"
    assert "What is driving the IT sector today?" in by_q
    assert not any("Pharma" in q for q in by_q)
    assert out["live_count"] >= 2


def test_macro_questions_only_when_headlines_say_so():
    quiet = sg.build_suggestions([], [{"headline": "Sensex ends flat", "companies": []}], now=NOW)
    assert not any("rupee" in i["query"] or "crude" in i["query"] for i in quiet["items"])
    live = sg.build_suggestions([], [{"headline": "Rupee slips to record low against dollar", "companies": []}], now=NOW)
    assert any(i["kind"] == "macro" and "rupee" in i["query"] for i in live["items"])


def test_thin_data_is_topped_up_with_marked_evergreen_questions():
    out = sg.build_suggestions([], [], now=NOW)
    assert out["live_count"] == 0
    assert out["items"] and all(i["kind"] == "evergreen" and i["note"] is None for i in out["items"])


def test_limit_and_no_duplicates():
    out = sg.build_suggestions(SECTORS, [], now=NOW, limit=3)
    qs = [i["query"] for i in out["items"]]
    assert len(qs) == 3 and len(set(qs)) == 3


def test_double_encoded_headlines_are_repaired_in_the_note():
    broken = "Wipro results: hereâ\u0080\u0099s what to watch"
    assert sg._clean(broken) == "Wipro results: here’s what to watch"
    assert sg._clean("plain  text") == "plain text"
