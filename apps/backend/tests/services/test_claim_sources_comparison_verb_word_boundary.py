"""Regression test: _comparison_relation()'s verb matching must use word boundaries.

Found during the claim_sources.py implementation review (2026-10-16): the comparison-verb regex matched
bare substrings with no word boundaries, so "led" (one of the five recognized verbs) matched inside
unrelated words like "settled," causing _comparison_direction_conflict to misfire on ordinary, non-
comparative paraphrases. Fixed by compiling _COMPARISON_VERB_RE with \\b boundaries. This file pins the
exact regression plus a sweep of other substring-collision risks for the remaining verb words, so the same
bug class doesn't silently return if the word list changes.
"""
from __future__ import annotations

import pytest

from app.services.ai_search import claim_sources as CS

UNIVERSE = [
    {"symbol": "HAL", "name": "Hindustan Aeronautics Limited"},
    {"symbol": "BEL", "name": "Bharat Electronics Limited"},
]
ENTITIES = {"companies": ["HAL", "BEL"]}


def test_the_exact_confirmed_regression_settled_containing_led():
    a = "HAL settled its dispute with BEL this quarter."
    b = "BEL settled its dispute with HAL this quarter."
    assert CS._comparison_relation(a, ["HAL", "BEL"], UNIVERSE) is None
    assert CS._comparison_relation(b, ["HAL", "BEL"], UNIVERSE) is None
    assert CS.similar(a, b, UNIVERSE, ENTITIES) is True


# Other words containing one of the five verb tokens as a bare substring -- each should NOT trigger a
# comparison-relation match on its own.
SUBSTRING_COLLISION_WORDS = [
    ("led", "settled"),
    ("led", "concluded"),
    ("led", "exceeded"),
    ("beat", "heartbeat"),
    ("beat", "beaten"),
]


@pytest.mark.parametrize("verb,colliding_word", SUBSTRING_COLLISION_WORDS, ids=lambda *a: "-".join(a) if isinstance(a, tuple) else a)
def test_substring_collision_words_do_not_trigger_a_false_comparison_relation(verb, colliding_word):
    text = f"HAL and BEL both had a {colliding_word} event mentioned in the filing this quarter."
    relation = CS._comparison_relation(text, ["HAL", "BEL"], UNIVERSE)
    assert relation is None, f"'{colliding_word}' (contains '{verb}') incorrectly triggered a comparison relation: {relation}"


def test_genuine_comparison_verbs_still_match_correctly():
    """Confirms the fix didn't overcorrect into missing real comparison verbs."""
    cases = [
        "HAL outperformed BEL this quarter.",
        "HAL underperformed BEL this quarter.",
        "HAL beat BEL on order execution this quarter.",
        "HAL lagged behind BEL this quarter.",
        "HAL led BEL on order execution this quarter.",
    ]
    for text in cases:
        relation = CS._comparison_relation(text, ["HAL", "BEL"], UNIVERSE)
        assert relation is not None, f"genuine comparison verb was not detected: {text!r}"
        assert relation[0] == "HAL" and relation[2] == "BEL"


def test_genuine_comparison_direction_reversal_is_still_correctly_rejected():
    """Confirms the fix preserves the real protection the mechanism exists for."""
    a = "HAL outperformed BEL this quarter."
    b = "BEL outperformed HAL this quarter."
    assert CS.similar(a, b, UNIVERSE, ENTITIES) is False
