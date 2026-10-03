"""
Directory-wide coverage (owner decision 2026-09-28): every company is in
exactly one public state, each with its own reason — never the generic
"Not available yet". Stale scores are "needs refresh" with their last
calculation date, never "not processed".
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from tests.services.data_quality_fixtures import FRESH_AS_OF, verified_inputs
from app.services.marketripple_score import coverage as c
from app.services.marketripple_score.refresh import _movement


def _snap(**kw):
    base = dict(publishable=True, score=62.0, rating="Positive", publication_block_reasons=[],
                calculated_at=datetime.now(timezone.utc), symbol="X",
                market_behaviour_coverage_pct=100.0, financial_data_as_of=FRESH_AS_OF,
                market_behaviour_inputs=verified_inputs("X"))
    base.update(kw)
    return SimpleNamespace(**base)


def test_banks_finance_insurance_and_no_sector_are_unsupported():
    for sector in ("Banking", "Finance", "Insurance"):
        state, msg = c.coverage_state(sector, None)
        assert state == c.STATE_UNSUPPORTED and msg
    state, msg = c.coverage_state(None, None)
    assert state == c.STATE_UNSUPPORTED and "sector" in msg


def test_supported_but_never_calculated_is_not_processed():
    state, msg = c.coverage_state("Technology", None)
    assert state == c.STATE_NOT_PROCESSED
    assert "hasn't been calculated" in msg


def test_expired_score_needs_refresh_with_its_date_not_not_processed():
    old = datetime(2026, 7, 1, tzinfo=timezone.utc)
    state, msg = c.coverage_state("Technology", _snap(calculated_at=old))
    assert state == c.STATE_NEEDS_REFRESH
    assert "01 Jul 2026" in msg


def test_fresh_published_score_is_scored():
    assert c.coverage_state("Technology", _snap()) == (c.STATE_SCORED, None)


def test_computed_but_blocked_is_insufficient_data_with_its_reason():
    state, msg = c.coverage_state("Technology", _snap(publishable=False, score=None,
                                                      publication_block_reasons=["INSUFFICIENT_FINANCIAL_METRICS"]))
    assert state == c.STATE_INSUFFICIENT_DATA
    assert "financial" in msg.lower()


def test_coverage_fields_carry_label_and_last_calculated_date():
    fields = c.coverage_fields("Technology", _snap(calculated_at=datetime.now(timezone.utc) - timedelta(days=1)))
    assert fields["coverage_state"] == c.STATE_SCORED
    assert fields["coverage_label"] == "Scored"
    assert fields["last_calculated_at"]


def test_score_movement_measures_previously_published_companies():
    before = {"A": (60.0, "Positive"), "B": (50.0, "Neutral"), "C": (70.0, "Positive")}

    def snap(sym, **kw):
        return _snap(symbol=sym, market_behaviour_inputs=verified_inputs(sym), **kw)

    built = [
        snap("A", score=63.0, rating="Positive"),
        snap("B", score=44.0, rating="Cautious"),
        snap("C", publishable=False, score=None),
        snap("NEW", score=55.0),  # no previous score: not compared
    ]
    m = _movement(before, built)
    assert m["compared"] == 2
    assert m["lost_public_score"] == 1 and m["lost_symbols"] == ["C"]
    assert m["max_abs_change"] == 6.0
    assert m["rating_band_changes"] == 1
    assert m["previously_public"] == 3 and m["public_after"] == 3
    # A was #2 of 3 (60 of 60/50/70), is now #1 of 3 (63 of 63/55/44): position moved
    assert m["max_rank_position_shift_pct"] is not None and m["max_rank_position_shift_pct"] > 0
