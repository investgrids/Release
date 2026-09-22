"""
postprocess.build_confidence_contract — the ONE place the AEV2-approved
confidence formula's arithmetic lives (2026-09-21 AI Answer UI work,
review correction: a first frontend build had reimplemented this same
weighted sum in React, creating a second scoring path that could drift
from aev2/confidence.py's own copy). These tests pin the contract shape
and the missing-component behavior aev2/confidence.py's own docstring
already specifies, since both now share this one implementation.
"""
from __future__ import annotations

from app.services.ai_search.postprocess import build_confidence_contract


def test_full_breakdown_produces_scored_status_and_all_four_components():
    contract = build_confidence_contract({
        "evidence_quality": 80.0, "market_confirmation": 60.0,
        "historical_similarity": 40.0, "data_freshness": 100.0,
        "reasoning_confidence": 999.0,  # never part of this contract
    })
    assert contract["status"] == "scored"
    assert contract["score"] == round(0.35 * 80 + 0.25 * 60 + 0.25 * 40 + 0.15 * 100, 1)
    assert contract["components"] == {
        "evidence_quality": 80.0, "market_confirmation": 60.0,
        "historical_similarity": 40.0, "data_freshness": 100.0,
    }
    assert "reasoning_confidence" not in contract["components"]


def test_missing_component_contributes_zero_never_renormalized():
    contract = build_confidence_contract({"evidence_quality": 100.0})
    assert contract["status"] == "scored"
    assert contract["score"] == 35.0  # 0.35 * 100, NOT 100.0
    assert contract["components"]["market_confirmation"] is None


def test_all_components_missing_is_unscored_not_zero():
    contract = build_confidence_contract({})
    assert contract["status"] == "unscored"
    assert contract["score"] is None
    assert all(v is None for v in contract["components"].values())


def test_none_breakdown_is_unscored():
    contract = build_confidence_contract(None)
    assert contract["status"] == "unscored"
    assert contract["score"] is None


def test_score_is_rounded_to_one_decimal():
    contract = build_confidence_contract({
        "evidence_quality": 71.0, "market_confirmation": 61.0,
        "historical_similarity": 58.0, "data_freshness": 66.0,
    })
    raw = 0.35 * 71 + 0.25 * 61 + 0.25 * 58 + 0.15 * 66
    assert contract["score"] == round(raw, 1)
    assert contract["score"] == round(contract["score"], 1)
