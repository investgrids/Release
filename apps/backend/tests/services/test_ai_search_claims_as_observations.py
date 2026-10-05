"""
Step 3.4G.6: claims-as-observations. The model writes each factual observation ONCE ({"text", "sources"}); code renders `what_happened` and the observation entries of `claim_sources` from that list
(schema.render_observations, applied in flatten_nested). Representation drift (listed-but-unwritten / written-but-unlisted) becomes impossible by construction. Gate B is unchanged and still validates the rendered
answer: nothing here authorizes anything. Model-free.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.api.companies import _NSE_UNIVERSE as UNIVERSE
from app.services.ai_search import answer_authorization as AA
from app.services.ai_search import claim_sources as CS
from app.services.ai_search import schema as S
from tests.services.test_ai_search_composition_contract import sr2_prompt_and_bundle
from tests.services.test_ai_search_detector_closure import ENTS, rebuild

ART_G5 = Path(__file__).resolve().parents[2] / "benchmarks/ai_search/baseline_2026_10_04/step3_4c/openai_sr2_g5.json"


def ids(b):
    idx = {i["id"]: i for i in b.index()}
    return (next(i for i, it in idx.items() if it["kind"] == "event" and "11%" in it["title"]),
            next(i for i, it in idx.items() if it["kind"] == "event" and "Accenture" in it["title"] and "22%" in it["title"]),
            next(i for i, it in idx.items() if it["kind"] == "news" and "divided" in it["title"].lower()))


def nested(observations, summary="The visible evidence is mixed rather than clearly positive or negative.", bottom="A clear forward outlook is not established by the visible evidence.", claims=None, **evd):
    return {"investment": {"summary": summary, "bottom_line": bottom},
            "evidence": {"observations": observations, "key_drivers": [], **evd},
            "claim_sources": claims or [], "risks": {"risks": [], "opportunities": []}, "companies": [], "sectors": []}


def good_obs(b):
    e_fall, e_acn, n_div = ids(b)
    return [{"text": "Nifty IT crashed 11% in September, with TCS, Infosys and Wipro among the top losers.", "sources": [e_fall]},
            {"text": "Accenture shares jumped a record 22% on an earnings boost, lifting Infosys and Wipro ADRs.", "sources": [e_acn]},
            {"text": "Coverage describes the Street as divided on the fortunes of Indian IT after Accenture's growth beat.", "sources": [n_div]}]


def run(b, n, query):
    flat = S.flatten_nested(n)
    return flat, AA.authorize(flat, b, ENTS, UNIVERSE, query)


# ── structure: rendered once, listed once, impossible states impossible ──────────────────────────────────────────────────────────

def test_every_observation_appears_in_public_prose_with_the_same_sources_in_claim_sources():
    _g, _ev, r, b, _p = sr2_prompt_and_bundle()
    obs = good_obs(b)
    flat, a = run(b, nested(obs), r["query"])
    for o in obs:
        assert o["text"] in flat["what_happened"]
        assert {"claim": o["text"], "sources": o["sources"]} in flat["claim_sources"]
    assert [c["claim"] for c in flat["claim_sources"]] == [o["text"] for o in obs]
    assert a["authorized"] is True, a


def test_a_model_written_what_happened_is_not_a_second_factual_representation():
    _g, _ev, r, b, _p = sr2_prompt_and_bundle()
    obs = good_obs(b)
    flat = S.flatten_nested(nested(obs, what_happened="Nifty IT jumped 2% intraday on the first of October."))
    assert "jumped 2%" not in flat["what_happened"] and flat["what_happened"] == " ".join(o["text"] for o in obs)


@pytest.mark.parametrize("n_obs", [0, 1, 2, 3, 5])
def test_listed_but_not_written_and_written_but_not_listed_cannot_be_produced(n_obs):
    _g, _ev, r, b, _p = sr2_prompt_and_bundle()
    pool = good_obs(b) + [{"text": "IT was flat at +0.0% over one day.", "sources": ["C2"]}, {"text": "The weekly wrap reported IT indices down 4%.", "sources": ["N4"]}]
    obs = pool[:n_obs]
    flat = S.flatten_nested(nested(obs))
    listed = [c["claim"] for c in flat["claim_sources"]]
    assert len(listed) == n_obs
    assert all(c in flat["what_happened"] for c in listed)                                         # no listed-but-unwritten claim
    assert flat["what_happened"] == " ".join(listed)                                               # nothing written that is not listed


def test_duplicate_observations_do_not_duplicate_public_prose_and_their_sources_merge():
    _g, _ev, r, b, _p = sr2_prompt_and_bundle()
    e_fall, e_acn, _ = ids(b)
    t = "Nifty IT crashed 11% in September, with TCS, Infosys and Wipro among the top losers."
    flat = S.flatten_nested(nested([{"text": t, "sources": [e_fall]}, {"text": t.upper(), "sources": [e_acn]}]))
    assert flat["what_happened"] == t and flat["claim_sources"] == [{"claim": t, "sources": [e_fall, e_acn]}]


def test_empty_observations_produce_an_honest_limited_answer_not_filler():
    _g, _ev, r, b, _p = sr2_prompt_and_bundle()
    flat = S.flatten_nested(nested([], summary="The listed evidence does not establish an answer to this question."))
    assert flat["what_happened"] == "" and flat["claim_sources"] == []
    a = AA.authorize(flat, b, ENTS, UNIVERSE, r["query"])
    assert a["authorized"] is True, a                                                              # nothing fabricated, nothing claimed


def test_observations_without_text_carry_no_claim_and_are_not_rendered():
    _g, _ev, r, b, _p = sr2_prompt_and_bundle()
    first = good_obs(b)[0]
    flat = S.flatten_nested(nested([{"text": "", "sources": ["E1"]}, {"sources": ["E1"]}, "stray string", first]))
    assert len(flat["claim_sources"]) == 1 and flat["what_happened"] == first["text"]


def test_claims_for_other_fields_are_kept_and_an_observation_repeat_is_merged_not_doubled():
    _g, _ev, r, b, _p = sr2_prompt_and_bundle()
    obs = good_obs(b)
    other = {"claim": "Infosys and Wipro ADRs rose after the report.", "sources": [obs[1]["sources"][0]]}
    flat = S.flatten_nested(nested(obs, claims=[{"claim": obs[0]["text"], "sources": ["E9"]}, other]))
    assert [c["claim"] for c in flat["claim_sources"]] == [o["text"] for o in obs] + [other["claim"]]


def test_an_older_shape_response_without_observations_passes_through_untouched():
    n = nested(None)
    n["evidence"].pop("observations")
    n["evidence"]["what_happened"] = "Legacy sentence."
    n["claim_sources"] = [{"claim": "Legacy sentence.", "sources": ["E1"]}]
    flat = S.flatten_nested(n)
    assert flat["what_happened"] == "Legacy sentence." and flat["claim_sources"] == n["claim_sources"]


# ── Gate B still decides: rendering is not authorization ──────────────────────────────────────────────────────────────────────────

def test_an_unsupported_figure_in_an_observation_still_fails_gate_b():
    _g, _ev, r, b, _p = sr2_prompt_and_bundle()
    obs = good_obs(b)
    obs[0] = {"text": "Nifty IT rose 20% in September.", "sources": obs[0]["sources"]}
    _f, a = run(b, nested(obs), r["query"])
    assert a["authorized"] is False and a["reasons"], a


def test_a_wrong_source_still_fails():
    _g, _ev, r, b, _p = sr2_prompt_and_bundle()
    obs = good_obs(b)
    obs[0] = {"text": obs[0]["text"], "sources": ["E99"]}
    _f, a = run(b, nested(obs), r["query"])
    assert a["authorized"] is False and "unknown_source" in a["reasons"], a


def test_an_observation_with_no_source_still_fails():
    _g, _ev, r, b, _p = sr2_prompt_and_bundle()
    obs = good_obs(b)
    obs[0] = {"text": obs[0]["text"], "sources": []}
    _f, a = run(b, nested(obs), r["query"])
    assert a["authorized"] is False, a


def test_hidden_evidence_still_cannot_authorize():
    _g, _ev, r, b, _p = sr2_prompt_and_bundle()
    obs = good_obs(b) + [{"text": "The Q2 results season begins on 8 October 2026 with TCS reporting first.", "sources": ["E2"]}]
    _f, a = run(b, nested(obs), r["query"])
    assert a["authorized"] is False and "unsupported_figures" in a["reasons"], a


def test_a_new_factual_assertion_in_the_synthesis_not_represented_by_an_observation_is_still_caught():
    _g, _ev, r, b, _p = sr2_prompt_and_bundle()
    _f, a = run(b, nested(good_obs(b), bottom="IT will rally 15% by year end as Accenture's beat flows through to Indian exporters."), r["query"])
    assert a["authorized"] is False and ({"uncovered_factual_sentences", "unsupported_figures"} & set(a["reasons"])), a


def test_a_factual_sentence_in_another_field_without_a_claim_entry_is_still_caught():
    _g, _ev, r, b, _p = sr2_prompt_and_bundle()
    _f, a = run(b, nested(good_obs(b), why_it_happened="Infosys announced a 5% buyback on 3 October 2026."), r["query"])
    assert a["authorized"] is False, a


# ── replay of the saved SR2 live generation ──────────────────────────────────────────────────────────────────────────────────────

def test_replaying_the_saved_sr2_generation_through_the_assembler_removes_the_mismatch_and_keeps_the_claims():
    saved = json.loads(ART_G5.read_text(encoding="utf-8"))["results"]["SR2"]
    gen = saved["rejected_generation"][0]["generation"]
    b = rebuild(saved["evidence"])                                                                 # the evidence of THAT live call
    r = saved
    old = AA.authorize(gen, b, ENTS, UNIVERSE, r["query"])
    assert old["reasons"] == ["claim_not_in_answer"]                                               # the saved structural failure
    obs = [{"text": c["claim"], "sources": c["sources"]} for c in gen["claim_sources"]]            # the model's facts, now emitted once
    flat = S.flatten_nested(nested(obs, summary=gen["summary"], bottom=gen["bottom_line"]))
    assert [c["claim"] for c in flat["claim_sources"]] == [c["claim"] for c in gen["claim_sources"]]       # the evidence claims are unchanged
    assert all(c["claim"] in flat["what_happened"] for c in flat["claim_sources"])                 # none is unwritten any more
    new = AA.authorize(flat, b, ENTS, UNIVERSE, r["query"])
    assert "claim_not_in_answer" not in new["reasons"], new
    print("REPLAY", new["authorized"], new["reasons"])
