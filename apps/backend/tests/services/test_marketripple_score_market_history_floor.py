"""Market-behaviour publication floor (owner decision 2026-10-03, HEG):
>=50% coverage, >=64 completed closes, and a NIFTY- or sector-relative
comparison — checked on fresh pillars and on stored snapshots."""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from tests.services.data_quality_fixtures import FRESH_AS_OF, verified_inputs
from app.services.marketripple_score.contracts import PillarScore, PillarStatus
from app.services.marketripple_score.market_behaviour import (
    pillar_has_sufficient_market_history, snapshot_lacks_market_history,
)
from app.services.marketripple_score.public_projection import is_publicly_published


def _pillar(coverage, metrics):
    return PillarScore(name="market_behaviour", score=50.0, coverage_pct=coverage, status=PillarStatus.PARTIAL,
                       metrics_used=metrics, metrics_missing=[], sources=["t"], as_of=datetime.now(timezone.utc))


def test_rsi_only_fails():  # HEG's shape
    assert not pillar_has_sufficient_market_history(_pillar(25.0, ["rsi_14"]))


def test_two_components_without_any_relative_comparison_fails():
    assert not pillar_has_sufficient_market_history(_pillar(50.0, ["200_dma_position", "rsi_14"]))


def test_half_coverage_with_a_nifty_comparison_passes():
    assert pillar_has_sufficient_market_history(_pillar(50.0, ["relative_return_vs_nifty50", "rsi_14"]))


def test_sector_relative_comparison_alone_counts_as_the_comparison():
    assert pillar_has_sufficient_market_history(
        _pillar(75.0, ["200_dma_position", "relative_return_vs_sector_etf (^CNXIT)", "rsi_14"]))


def test_missing_pillar_fails():
    assert not pillar_has_sufficient_market_history(None)


def _snap(**kw):
    base = dict(publishable=True, score=60.0, publication_block_reasons=[], market_behaviour_coverage_pct=100.0,
                symbol="X", financial_data_as_of=FRESH_AS_OF, market_behaviour_inputs=verified_inputs("X"))
    base.update(kw)
    return SimpleNamespace(**base)


def test_stored_snapshot_below_half_coverage_is_hidden():
    assert snapshot_lacks_market_history(_snap(market_behaviour_coverage_pct=25.0))
    assert not is_publicly_published(_snap(market_behaviour_coverage_pct=25.0))


def test_stored_snapshot_with_the_new_reason_is_hidden():
    assert not is_publicly_published(_snap(publication_block_reasons=["INSUFFICIENT_MARKET_HISTORY"]))


def test_stored_snapshot_with_full_market_history_stays_public():
    assert is_publicly_published(_snap(market_behaviour_coverage_pct=75.0))
    assert is_publicly_published(_snap(market_behaviour_coverage_pct=100.0))


def test_unpublished_snapshot_never_becomes_public():
    assert not is_publicly_published(_snap(publishable=False))
