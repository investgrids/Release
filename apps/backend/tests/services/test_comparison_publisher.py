"""
Regression suite — comparison_publisher's companies_affected/key_takeaway
derivation, offline (no DB/network/LLM).

Built after a live production bug was reported: every comparison article's
"30-Second Answer" showed just the bare stance word ("Neutral") and both
companies' "Why" reason showed the generic placeholder "Comparison
subject" — even though the article's own already-generated decision
intelligence (holding_analysis.thesis, target_analysis.thesis,
decision_summary, comparison[].advantage) carried real, specific content
that was simply never wired into the article's stored fields.
"""
from __future__ import annotations

from app.services.aipe.comparison_publisher import _build_companies_affected


def _di(comparison_advantages, holding_thesis="Holding thesis.", target_thesis="Target thesis."):
    return {
        "holding_analysis": {"thesis": holding_thesis},
        "target_analysis": {"thesis": target_thesis},
        "comparison": [{"dimension": f"D{i}", "advantage": a} for i, a in enumerate(comparison_advantages)],
    }


# ── Real reasons, not the generic placeholder ────────────────────────────────

def test_real_thesis_used_as_reason_not_placeholder():
    di = _di(["neutral"], holding_thesis="ACC's high debt makes it riskier.", target_thesis="UltraTech's balance sheet is stronger.")
    result = _build_companies_affected(di, "ACC Ltd", "ACC", "UltraTech Cement Ltd", "ULTRATECH")
    assert result[0]["reason"] == "ACC's high debt makes it riskier."
    assert result[1]["reason"] == "UltraTech's balance sheet is stronger."
    assert "Comparison subject" not in (result[0]["reason"], result[1]["reason"])


def test_missing_thesis_falls_back_to_placeholder_not_blank():
    di = {"holding_analysis": {}, "target_analysis": {}, "comparison": []}
    result = _build_companies_affected(di, "A", "A", "B", "B")
    assert result[0]["reason"] == "Comparison subject"
    assert result[1]["reason"] == "Comparison subject"


# ── Impact derived from the real dimension-by-dimension table ───────────────

def test_clear_target_lean_flips_impact():
    # 5 dimensions favor target (UltraTech), 0 favor holding (ACC), 1 neutral
    # — the exact real production shape from acc-vs-ultracemco.
    di = _di(["target", "target", "target", "target", "target", "neutral"])
    result = _build_companies_affected(di, "ACC", "ACC", "UltraTech", "ULTRATECH")
    assert result[0]["impact"] == "negative"  # holding (ACC) loses
    assert result[1]["impact"] == "positive"  # target (UltraTech) wins


def test_clear_holding_lean_flips_impact_the_other_way():
    di = _di(["holding", "holding", "holding", "neutral"])
    result = _build_companies_affected(di, "A", "A", "B", "B")
    assert result[0]["impact"] == "positive"
    assert result[1]["impact"] == "negative"


def test_close_comparison_stays_neutral_for_both():
    # A single-dimension edge on a multi-dimension comparison isn't a real
    # signal — must not force a winner from noise.
    di = _di(["target", "holding", "neutral", "neutral"])
    result = _build_companies_affected(di, "A", "A", "B", "B")
    assert result[0]["impact"] == "neutral"
    assert result[1]["impact"] == "neutral"


def test_no_comparison_data_stays_neutral():
    di = {"holding_analysis": {}, "target_analysis": {}, "comparison": []}
    result = _build_companies_affected(di, "A", "A", "B", "B")
    assert result[0]["impact"] == "neutral"
    assert result[1]["impact"] == "neutral"


def test_symbol_and_name_passed_through_unchanged():
    di = _di(["neutral"])
    result = _build_companies_affected(di, "Reliance Industries", "RELIANCE", "TCS Ltd", "TCS")
    assert result[0]["name"] == "Reliance Industries"
    assert result[0]["symbol"] == "RELIANCE"
    assert result[1]["name"] == "TCS Ltd"
    assert result[1]["symbol"] == "TCS"
