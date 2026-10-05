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
