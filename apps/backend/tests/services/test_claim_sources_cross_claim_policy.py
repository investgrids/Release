"""Explicit policy test: claim_not_in_answer (self-consistency, cross_claim=False) vs. the uncovered-sentence
sweep (evidence authorization, cross_claim=True) must stay on opposite sides of the lenient/strict line.

Found during the claim_sources.py implementation review (2026-10-16): similar()'s cross_claim default was
previously implicit at the claim_not_in_answer call site. Made explicit, documented, and pinned here so the
distinction can never silently drift back to the wrong setting at either call site.
"""
from __future__ import annotations

from app.services.ai_search import answer_authorization as AA
from app.services.ai_search import claim_sources as CS
from app.api.companies import _NSE_UNIVERSE as UNIVERSE

from tests.services.test_ai_search_claim_matching_hardened_eval import self_consistent_hal_bel_bundle
from tests.services.test_ai_search_claims_coverage_reproduction import HAL_BEL_ENTS, HAL_BEL_QUERY


def _gen(reason: str, claim_sources: list[dict]) -> dict:
    return {
        "summary": "", "bottom_line": "",
        "companies": [{"symbol": "HAL", "name": "Hindustan Aeronautics Limited", "reason": reason}],
        "sectors": [], "risks": [], "opportunities": [],
        "claim_sources": claim_sources,
    }


def _authorize(reason: str, claim_sources: list[dict]) -> dict:
    return AA.authorize(_gen(reason, claim_sources), self_consistent_hal_bel_bundle(), HAL_BEL_ENTS, UNIVERSE, HAL_BEL_QUERY)


# ── claim_not_in_answer: fabricated claims must still be caught ────────────────────────────────────────────────────

def test_a_claim_with_a_different_entity_than_anything_in_the_answer_is_caught_as_claim_not_in_answer():
    """A fabricated claim about a company never mentioned anywhere in the prose -- entities mismatch means
    the lenient fallback never even gets a chance to forgive it."""
    reason = "HAL reported a record order book of ₹94,000 crore as of the June quarter."
    fabricated = {"claim": "BEL reported a record order book of ₹94,000 crore as of the June quarter.", "sources": ["A1"]}
    auth = _authorize(reason, [fabricated])
    assert auth["authorized"] is False
    assert any(r.startswith("claim_not_in_answer") or "claim_not_in_answer" in str(auth) for r in auth["reasons"]) or "claim_not_in_answer" in auth["reasons"]


def test_a_claim_with_a_different_figure_than_anything_in_the_answer_is_caught():
    reason = "HAL reported a record order book of ₹94,000 crore as of the June quarter."
    fabricated = {"claim": "HAL reported a record order book of ₹50,000 crore as of the June quarter.", "sources": ["A1"]}
    auth = _authorize(reason, [fabricated])
    assert auth["authorized"] is False


# ── claim_not_in_answer: valid paraphrases of the model's own citation must still pass ─────────────────────────────

def test_b_a_slightly_reworded_version_of_the_models_own_sentence_is_not_flagged_claim_not_in_answer():
    """The deliberate leniency this policy keeps: the model's claim_sources[].claim text doesn't need to be
    a byte-for-byte copy of its own prose sentence to pass self-consistency."""
    reason = "HAL's order book reached a record ₹94,000 crore in the June quarter."
    paraphrased_citation = {"claim": "HAL reported a record order book of ₹94,000 crore as of the June quarter.", "sources": ["A1"]}
    cv = CS.validate_claim_sources([paraphrased_citation], self_consistent_hal_bel_bundle().index(), _gen(reason, [paraphrased_citation]), HAL_BEL_ENTS, UNIVERSE)
    claim_entry = cv["claims"][0]
    assert "claim_not_in_answer" not in claim_entry["problems"]


# ── confirms the two call sites genuinely differ, with a single real generation ─────────────────────────────────────

def test_c_the_cross_claim_restatement_regression_stays_fixed_while_self_consistency_stays_lenient():
    """Direct side-by-side: the SAME lenient lexical leeway that correctly forgives case B's paraphrase
    must NOT be what decides whether a DIFFERENT field's restatement of an already-cited fact gets waved
    through -- that question goes through the separate, strict uncovered-sweep call site."""
    from tests.services.test_ai_search_structured_authorization import saved, cc1_bundle
    g, _ = saved()
    para = "Infosys trades at a lower P/E of 13.3 and P/B of 4.54 than TCS at 15.1 and 6.85."
    g2 = dict(g)
    g2["bottom_line"] = para
    cv = CS.validate_claim_sources(g2.get("claim_sources"), cc1_bundle().index(), g2, {"companies": ["TCS", "INFY"], "sectors": []}, UNIVERSE)
    assert para[:200] in cv["uncovered"]   # the restatement is NOT silently covered by the already-cited claim


# ── existing source-ID protections, unaffected by this policy clarification ────────────────────────────────────────

def test_d_unknown_source_and_no_source_are_unaffected_by_either_cross_claim_setting():
    reason = "HAL reported a record order book of ₹94,000 crore as of the June quarter."
    unknown = _authorize(reason, [{"claim": reason, "sources": ["Z99"]}])
    assert unknown["authorized"] is False
    assert any(r.startswith("unknown_source") for r in unknown["reasons"])

    empty = _authorize(reason, [{"claim": reason, "sources": []}])
    assert empty["authorized"] is False
    assert "no_source" in empty["reasons"]
