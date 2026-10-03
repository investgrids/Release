import random

from app.services.financial_facts import filing_shadow_score as fss
from app.services.marketripple_score.valuation import _percentile_rank as live_percentile_rank


def test_without_ties_it_equals_the_live_formula():
    vals = {"A": 10.0, "B": 25.0, "C": 3.0, "D": 18.0, "E": 7.5}
    for hib in (True, False):
        for s in vals:
            assert fss.percentile_rank(vals, s, cheaper_is_better=not hib) == live_percentile_rank(vals, s, cheaper_is_better=not hib)


def test_tied_values_get_the_same_percentile_whatever_the_peer_order():
    base = [("A", 10.0), ("B", 20.0), ("C", 20.0), ("D", 20.0), ("E", 30.0), ("F", 5.0)]
    expected = None
    for seed in range(25):
        items = base[:]
        random.Random(seed).shuffle(items)
        d = dict(items)
        p = {s: fss.percentile_rank(d, s) for s in d}
        assert p["B"] == p["C"] == p["D"]
        if expected is None:
            expected = p
        assert p == expected  # identical for every ordering of the peers
    # three tied middle values occupy ranks 1..3 (0-based, higher is better) => average rank 2 => (6-1-2)/(6-1)*100 = 60.0
    assert expected["B"] == 60.0 and expected["E"] == 100.0 and expected["F"] == 0.0 and expected["A"] == 20.0


def test_the_live_function_is_order_dependent_on_ties_which_is_why_it_is_replaced():
    d1 = {"A": 5.0, "B": 5.0, "C": 9.0}
    d2 = {"B": 5.0, "A": 5.0, "C": 9.0}
    assert live_percentile_rank(d1, "A") != live_percentile_rank(d2, "A")
    assert fss.percentile_rank(d1, "A") == fss.percentile_rank(d2, "A") == 25.0


def test_missing_or_single_peer_gives_none():
    assert fss.percentile_rank({"A": 1.0}, "A") is None
    assert fss.percentile_rank({"A": 1.0, "B": 2.0}, "C") is None
    assert fss.percentile_rank({"A": None, "B": 2.0}, "A") is None


def _fm(metrics, pe, pb, status="ok"):
    return {"status": status, "metrics": metrics, "valuation": {"pe": pe, "pb": pb}}


def test_group_scoring_is_peer_only_needs_both_components_and_is_order_independent():
    mk = lambda i: {"revenue_growth": 5 + i, "profit_growth": 3 + i, "roe": 10 + i, "roce": 8 + i, "debt_to_equity": 1.0 - i / 20, "interest_coverage": 3 + i}
    fm = {f"S{i}": _fm(mk(i), pe=10 + i, pb=1 + i / 10) for i in range(6)}
    fm["PBONLY"] = _fm(mk(2), pe=None, pb=1.2)
    fm["GAIN"] = _fm(mk(3), pe=None, pb=1.0, status="EXCEPTIONAL_GAIN_REVIEW")
    mb = {s: 50.0 for s in fm}
    members = list(fm)
    a = fss.score_group(members, fm, mb)
    shuffled = members[:]
    random.Random(7).shuffle(shuffled)
    b = fss.score_group(shuffled, {k: fm[k] for k in shuffled}, mb)
    assert {k: a[k] for k in a} == {k: b[k] for k in b}  # same results for any peer order
    assert a["PBONLY"]["state"] == "withheld" and a["PBONLY"]["reason"] == "VALUATION_NEEDS_TWO_COMPONENTS (PB_ONLY)"
    assert a["GAIN"]["state"] == "withheld" and a["GAIN"]["reason"] == "EXCEPTIONAL_GAIN_REVIEW"
    assert a["S5"]["state"] == "scored" and "own_history" not in a["S5"] and a["S5"]["val_parts"] == ["pe", "pb"]
    # cheapest P/E and P/B (S0) gets the top valuation percentile, valuation is the plain mean of the two peer percentiles
    assert a["S0"]["val"] == 100.0 and a["S5"]["val"] == 0.0 or a["S0"]["val"] > a["S5"]["val"]
    # headline = 8/15 FS + 4/15 valuation + 3/15 MB
    r = a["S2"]
    assert abs(r["score"] - (r["fs"] * 8 / 15 + r["val"] * 4 / 15 + 50.0 * 3 / 15)) < 0.06
    assert fss.SCORING_VERSION == "NSE_FILING_SCORE_V2"
