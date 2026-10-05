"""Step 7 follow-up: companies carry a structured snapshot of figures the model already had (P/E, P/B, 52-week range), and nothing else."""
from app.services.ai_search.pipeline import attach_snapshots


def test_snapshot_exposes_only_the_valuation_figures_already_in_evidence():
    cos = [{"symbol": "HDFCBANK"}, {"symbol": "ICICIBANK"}, {"symbol": "TCS"}]
    val = {"HDFCBANK": {"pe": 15.6, "pb": 1.81, "52w_high": 1020.5, "52w_low": 681.9}, "ICICIBANK": {"pe": 17.0}}
    attach_snapshots(cos, val)
    assert cos[0]["snapshot"] == {"pe": 15.6, "pb": 1.81, "week52_low": 681.9, "week52_high": 1020.5}
    assert cos[1]["snapshot"] == {"pe": 17.0}          # partial figures stay partial, never padded
    assert "snapshot" not in cos[2]                     # no valuation evidence -> no snapshot, no placeholder


def test_no_valuation_evidence_adds_nothing():
    cos = [{"symbol": "WIPRO"}]
    attach_snapshots(cos, {})
    attach_snapshots(cos, None)
    assert cos == [{"symbol": "WIPRO"}]


def test_symbol_match_is_case_insensitive_and_does_not_touch_the_evidence():
    val = {"TCS": {"pe": 24.1, "52w_high": 4200.0}}
    before = {k: dict(v) for k, v in val.items()}
    cos = [{"symbol": "tcs"}]
    attach_snapshots(cos, val)
    assert cos[0]["snapshot"] == {"pe": 24.1, "week52_high": 4200.0}
    assert val == before


def test_profile_figures_are_display_only_and_merge_into_the_snapshot():
    cos = [{"symbol": "HDFCBANK"}, {"symbol": "TCS"}]
    prof = {"HDFCBANK": {"market_cap_cr": 1380000.5, "sector": "Financial Services"}}.get
    attach_snapshots(cos, {"HDFCBANK": {"pe": 15.6}}, profile=lambda s: prof(s, {}))
    assert cos[0]["snapshot"] == {"pe": 15.6, "market_cap_cr": 1380000.5, "sector": "Financial Services"}
    assert "snapshot" not in cos[1]


def test_profile_never_enters_the_evidence_valuation_dict():
    from app.services.ai_search import enrichment as E
    E._PROFILES["TESTSYM"] = {"market_cap_cr": 10.0, "sector": "X", "_at": __import__("time").time()}
    assert E.profile_for("testsym") == {"market_cap_cr": 10.0, "sector": "X"}
    val = {"TESTSYM": {"pe": 1.0}}
    cos = [{"symbol": "TESTSYM"}]
    attach_snapshots(cos, val, profile=E.profile_for)
    assert val == {"TESTSYM": {"pe": 1.0}}                      # the corpus-feeding dict is untouched
    E._PROFILES["TESTSYM"]["_at"] = 0
    assert E.profile_for("TESTSYM") == {}                       # a stale profile is not shown
