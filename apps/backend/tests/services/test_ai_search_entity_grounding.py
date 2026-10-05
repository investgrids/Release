"""
Step 2 entity grounding: each of the eight Step 1 baseline entity failures is pinned individually, next to positive controls proving valid company questions
that look similar still resolve. A broad stoplist ("India", "Indian") would break the controls; these tests are what keep the fixes narrow.
"""
from __future__ import annotations

import pytest

from app.services.ai_search import entities as E
from app.services.ai_search import session_context as S


def resolve(q: str) -> dict:
    e = E.extract_entities(q)
    return {
        "companies": e["companies"], "sectors": e["sectors"], "policies": e["policies"],
        "ambiguous": (S.check_ambiguous_group(q, e) or {}).get("term"),
        "unrecognized": E.looks_like_unrecognized_company(q, e),
        "matches": {m["symbol"]: m["match_type"] for m in e["company_matches"]},
    }


# ── The eight baseline failures, one test each ───────────────────────────────

def test_cr1_kotak_mahindra_bank_is_only_kotak_not_mahindra_and_mahindra():
    r = resolve("What is the outlook for Kotak Mahindra Bank?")
    assert r["companies"] == ["KOTAKBANK"]


def test_cr2_3m_india_is_3mindia_not_bank_of_india():
    r = resolve("How is 3M India doing as a business?")
    assert r["companies"] == ["3MINDIA"] and r["matches"]["3MINDIA"] == "exact"


def test_mp1_rbi_repo_rate_question_about_indian_banks_is_not_a_company_picker():
    r = resolve("What happens to Indian banks if the RBI cuts the repo rate?")
    assert r["ambiguous"] is None and r["companies"] == []
    assert "banking" in r["sectors"] and {"rbi", "repo rate"} <= set(r["policies"])


def test_mp2_crude_oil_is_not_oil_india():
    r = resolve("How would higher crude oil prices affect Indian markets?")
    assert r["companies"] == [] and r["ambiguous"] is None


def test_mp3_indian_it_exporters_is_the_it_sector_not_a_company_picker():
    r = resolve("How would a weaker rupee affect Indian IT exporters?")
    assert r["ambiguous"] is None and r["companies"] == [] and r["sectors"] == ["it"]


def test_ge1_pronoun_it_is_not_the_it_sector():
    r = resolve("What is a P/E ratio and how should I read it?")
    assert r["sectors"] == [] and r["companies"] == []


def test_ge2_indian_market_is_not_a_company_picker():
    r = resolve("What does FII selling mean for the Indian market?")
    assert r["ambiguous"] is None and r["companies"] == []


def test_ge3_marketripple_score_is_our_product_not_an_unlisted_company():
    r = resolve("How does the MarketRipple Score work?")
    assert r["unrecognized"] is False and r["companies"] == []


# ── Positive controls: valid questions must still resolve ───────────────────

@pytest.mark.parametrize("query,expected", [
    ("What is the outlook for Indian Hotels?", "INDHOTEL"),
    ("How is Indian Bank doing?", "INDIANB"),
    ("Indian Overseas Bank results", "IOB"),
    ("Indian Railway Finance Corporation outlook", "IRFC"),
    ("Tell me about Oil India", "OIL"),
    ("Tell me about Bank of India", "BANKINDIA"),
    ("Is 3M India overvalued?", "3MINDIA"),
    ("Outlook for HDFC Bank", "HDFCBANK"),
])
def test_valid_company_questions_still_resolve_to_that_company(query, expected):
    r = resolve(query)
    assert expected in r["companies"] and r["ambiguous"] is None and r["unrecognized"] is False


def test_oil_ticker_in_capitals_still_matches_but_crude_oil_does_not():
    assert "OIL" in resolve("What about OIL stock?")["companies"]
    assert "OIL" not in resolve("crude oil outlook for next quarter")["companies"]


@pytest.mark.parametrize("query,expected", [
    ("Compare Tech Mahindra and Mahindra & Mahindra", {"TECHM", "M&M"}),
    ("Mahindra Group and Tech Mahindra", {"TECHM", "M&M"}),
    ("Kotak Mahindra Bank vs Mahindra & Mahindra", {"KOTAKBANK", "M&M"}),
    ("Compare Indian Oil and ONGC", {"IOC", "ONGC"}),
])
def test_two_company_questions_keep_both_companies(query, expected):
    assert set(resolve(query)["companies"]) == expected


def test_bare_indian_with_no_noun_still_asks_which_company():
    assert resolve("Compare with Indian")["ambiguous"] == "Indian"


def test_bare_tata_still_asks_which_company():
    assert resolve("Compare with Tata")["ambiguous"] is not None


@pytest.mark.parametrize("query", ["How is the IT sector doing?", "how is the it sector doing", "outlook for IT services"])
def test_it_sector_is_still_detected_when_written_as_a_sector(query):
    assert "it" in resolve(query)["sectors"]


def test_a_company_alias_ending_in_ltd_is_matched_without_ltd():
    # "kotak mahindra bank" has no alias entry; it comes from the registered name minus "Ltd".
    names = E._company_aliases(next(c for c in E._universe() if c["symbol"] == "KOTAKBANK"))
    assert "kotak mahindra bank" in names


def test_fuzzy_pass_ignores_question_fragments_starting_with_a_function_word():
    assert "how india" not in [g.lower() for g in E._word_ngrams("How India doing", max_len=3)]
    # words under 3 letters ("of") are already dropped by the existing builder, so the company phrase is "Bank India"; the edge rule must not remove it
    assert "Bank India" in E._word_ngrams("Tell me about Bank of India", max_len=3)


def test_misspelled_company_names_still_resolve_by_fuzzy_match():
    assert "RELIANCE" in resolve("Relaince Industries overvalued?")["companies"]
    assert "INFY" in resolve("Is Infosis a good company?")["companies"]


# ── referential pronouns ────────────────────────────────────────────────────

def test_ge1_self_contained_explanation_is_not_a_follow_up():
    q = "What is a P/E ratio and how should I read it?"
    assert S.referential_has_antecedent(q) is True


@pytest.mark.parametrize("q", ["What is it?", "How does it work?", "What does this mean?", "What about its main competitor?", "Which is safer?"])
def test_true_follow_ups_without_an_antecedent_stay_referential(q):
    assert S.referential_has_antecedent(q) is False
