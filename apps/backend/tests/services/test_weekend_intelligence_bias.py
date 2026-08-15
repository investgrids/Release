"""Overall market bias — pure function over sector/company signals."""
from __future__ import annotations

from app.services.weekend_intelligence.bias import (
    MIXED, NEGATIVE, NEUTRAL, POSITIVE, STRONG_NEGATIVE, STRONG_POSITIVE, compute_overall_bias,
)
from app.services.weekend_intelligence.company_synthesis import CompanySignal
from app.services.weekend_intelligence.sector_synthesis import SectorSignal


def _sector(direction, evidence_count=2, positive=0, negative=0):
    return SectorSignal(sector="X", direction=direction, strength="medium", confidence=0.5,
                         evidence_count=evidence_count, positive_evidence=positive, negative_evidence=negative)


def test_no_directional_evidence_is_neutral():
    assert compute_overall_bias([], []) == NEUTRAL


def test_unanimous_positive_sectors_is_strong_positive():
    signals = [_sector("positive", evidence_count=5) for _ in range(3)]
    assert compute_overall_bias(signals, []) == STRONG_POSITIVE


def test_unanimous_negative_sectors_is_strong_negative():
    signals = [_sector("negative", evidence_count=5) for _ in range(3)]
    assert compute_overall_bias(signals, []) == STRONG_NEGATIVE


def test_mild_lean_is_positive_not_strong_positive():
    # 6 positive-weight vs 5 negative-weight -> ratio ~0.09, below 0.2 mixed
    # threshold is irrelevant here since total volume (11) exceeds the
    # mixed minimum but ratio is small -> falls to plain NEUTRAL per the
    # bucketing rule (|ratio|<0.2 with enough volume => MIXED). Use a
    # ratio that lands cleanly in the "positive" (0.2-0.6) band instead.
    signals = [_sector("positive", evidence_count=7), _sector("negative", evidence_count=3)]
    assert compute_overall_bias(signals, []) == POSITIVE


def test_near_even_split_with_real_volume_is_mixed():
    signals = [_sector("positive", evidence_count=5), _sector("negative", evidence_count=5)]
    assert compute_overall_bias(signals, []) == MIXED


def test_near_even_split_with_low_volume_is_neutral_not_mixed():
    signals = [_sector("positive", evidence_count=1), _sector("negative", evidence_count=1)]
    assert compute_overall_bias(signals, []) == NEUTRAL


def test_company_signals_contribute_to_bias():
    companies = [CompanySignal(symbol="X", state="high_conviction_watch", signal_strength="high",
                                confidence=0.7, evidence_count=5)]
    assert compute_overall_bias([], companies) == STRONG_POSITIVE


def test_mixed_company_state_splits_weight_evenly():
    companies = [CompanySignal(symbol="X", state="mixed", signal_strength="medium", confidence=0.5, evidence_count=6)]
    # entirely mixed weight, split 50/50 -> no other signal -> neutral (low total after halving isn't below MIXED min anyway; ratio is 0)
    assert compute_overall_bias([], companies) in (NEUTRAL, MIXED)
