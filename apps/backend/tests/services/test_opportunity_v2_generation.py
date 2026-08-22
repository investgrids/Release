"""
opportunity_v2/generation.py's fail-closed validation — the direct
regression test for V1's confirmed bug (28/121 real rows truncated to an
8-word raw-headline slice, 6x duplicate generic "{Sector} Investment
Opportunity" titles). Every case here must resolve to None, never a
fabricated substitute -- _parse_and_validate is pure, no network call.
"""
from __future__ import annotations

import json

from app.services.opportunity_v2.generation import NarrativeResult, _parse_and_validate

_VALID = {
    "title": "Private Banks Positioned to Benefit From Rate Cuts",
    "summary": "A summary sentence. Another one.",
    "matters": "This matters because real reasons.",
    "benefits": "HDFCBANK and ICICIBANK benefit through margin expansion.",
    "risks": ["Execution delays", "Policy reversal"],
    "invalidate": "A sustained rate hike would invalidate this.",
    "why_bullets": ["Real bullet one", "Real bullet two"],
}


def test_valid_response_parses_into_a_narrative_result():
    result = _parse_and_validate(json.dumps(_VALID))
    assert isinstance(result, NarrativeResult)
    assert result.title == _VALID["title"]
    assert result.risks == _VALID["risks"]


def test_strips_markdown_code_fences():
    raw = "```json\n" + json.dumps(_VALID) + "\n```"
    result = _parse_and_validate(raw)
    assert result is not None


def test_unparseable_text_returns_none_not_a_fabricated_result():
    assert _parse_and_validate("This is not JSON at all, sorry.") is None


def test_missing_required_field_returns_none():
    for field in ["title", "summary", "matters", "benefits", "risks", "invalidate", "why_bullets"]:
        data = dict(_VALID)
        del data[field]
        assert _parse_and_validate(json.dumps(data)) is None, f"missing {field} should fail closed"


def test_the_literal_v1_regression_a_raw_8_word_headline_slice_is_rejected():
    """V1's actual confirmed fallback shape: the first ~8 words of a real
    headline, often ending mid-clause on a comma. If an LLM ever produces
    exactly this shape, it must still be rejected on the trailing-comma
    check -- title validation isn't just "did an LLM say it"."""
    data = dict(_VALID)
    data["title"] = "Aditya Birla Capital to enter gold loan market,"
    assert _parse_and_validate(json.dumps(data)) is None


def test_the_literal_v1_regression_a_generic_duplicate_title_is_too_short():
    data = dict(_VALID)
    data["title"] = "Defence Investment Opportunity"
    assert _parse_and_validate(json.dumps(data)) is None


def test_title_that_is_too_long_is_rejected():
    data = dict(_VALID)
    data["title"] = " ".join(["word"] * 25)
    assert _parse_and_validate(json.dumps(data)) is None


def test_title_ending_in_a_dangling_conjunction_is_rejected():
    data = dict(_VALID)
    data["title"] = "Banking sector poised for growth and"
    assert _parse_and_validate(json.dumps(data)) is None


def test_empty_risks_list_returns_none():
    data = dict(_VALID)
    data["risks"] = []
    assert _parse_and_validate(json.dumps(data)) is None


def test_risks_as_a_string_instead_of_a_list_returns_none():
    data = dict(_VALID)
    data["risks"] = "not a list"
    assert _parse_and_validate(json.dumps(data)) is None


def test_empty_why_bullets_returns_none():
    data = dict(_VALID)
    data["why_bullets"] = []
    assert _parse_and_validate(json.dumps(data)) is None
