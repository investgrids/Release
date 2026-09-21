"""
AEV2 foundation tests (2026-09-21) — mode resolution, additive schema,
cache-safe assembly, the deterministic recommendation-language gate, and
the X-Admin-Key-never-in-client-code guard.

Foundation slice only: only `direct_conclusion` carries real content in
this slice (a fail-closed pass-through of answer.bottom_line). Every
other field's honest-empty-default shape is asserted here; real field
population (companies_affected attribution, evidence[] citations,
related_intelligence) is the next slice's own test coverage, not this
file's.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.core.security import has_valid_admin_key
from app.services.ai_search.aev2 import language_gate, schema
from app.services.ai_search.aev2.assemble import assemble_aev2
from app.services.ai_search.aev2.mode import (
    AEV2Mode,
    get_aev2_mode,
    should_assemble,
    should_emit_telemetry,
    should_return_to_client,
)


# ── Mode resolution — fail-closed, never a stronger mode than configured ────

@pytest.mark.parametrize("raw,expected", [
    ("off", AEV2Mode.OFF), ("OFF", AEV2Mode.OFF), (" off ", AEV2Mode.OFF),
    ("shadow", AEV2Mode.SHADOW), ("canary", AEV2Mode.CANARY), ("public", AEV2Mode.PUBLIC),
])
def test_get_aev2_mode_recognizes_the_4_valid_strings(monkeypatch, raw, expected):
    from app.core.config import settings
    monkeypatch.setattr(settings, "ai_search_aev2_mode", raw)
    assert get_aev2_mode() == expected


@pytest.mark.parametrize("raw", ["", "shaddow", "v2", "true", "1", "canary_v2"])
def test_get_aev2_mode_fails_closed_to_off_on_anything_unrecognized(monkeypatch, raw):
    from app.core.config import settings
    monkeypatch.setattr(settings, "ai_search_aev2_mode", raw)
    assert get_aev2_mode() == AEV2Mode.OFF


def test_default_mode_is_off():
    from app.core.config import Settings
    assert Settings().ai_search_aev2_mode == "off"


def test_should_assemble_true_for_every_mode_except_off():
    assert should_assemble(AEV2Mode.OFF) is False
    for m in (AEV2Mode.SHADOW, AEV2Mode.CANARY, AEV2Mode.PUBLIC):
        assert should_assemble(m) is True


def test_should_return_to_client_matrix():
    # off: never assembled, so never returned (should_assemble already False)
    assert should_return_to_client(AEV2Mode.OFF, has_valid_admin_key=True) is False
    # shadow: never returned, regardless of admin key
    assert should_return_to_client(AEV2Mode.SHADOW, has_valid_admin_key=True) is False
    assert should_return_to_client(AEV2Mode.SHADOW, has_valid_admin_key=False) is False
    # canary: returned only with a valid admin key
    assert should_return_to_client(AEV2Mode.CANARY, has_valid_admin_key=True) is True
    assert should_return_to_client(AEV2Mode.CANARY, has_valid_admin_key=False) is False
    # public: always returned
    assert should_return_to_client(AEV2Mode.PUBLIC, has_valid_admin_key=False) is True


def test_should_emit_telemetry_false_only_for_off():
    assert should_emit_telemetry(AEV2Mode.OFF) is False
    for m in (AEV2Mode.SHADOW, AEV2Mode.CANARY, AEV2Mode.PUBLIC):
        assert should_emit_telemetry(m) is True


# ── Additive schema — the full shape, honest-empty defaults ────────────────

def test_build_response_default_shape_is_fully_honest_empty():
    r = schema.build_response()
    assert r["direct_conclusion"] == {"text": "", "evidence_refs": []}
    assert r["what_happened"] == {"summary": "", "evidence_refs": [], "items": []}
    assert r["why_it_matters"] == {"text": "", "evidence_refs": [], "is_fallback": False}
    assert r["companies_affected"] == {"currently_higher": [], "currently_lower": [], "omitted_unattributed": []}
    assert r["time_horizon"] == {"primary_horizon": None, "timeline_phases": []}
    assert r["risks_and_invalidation"] == {"kind": "analysis", "risks": [], "invalidates_if": [], "watch_for": []}
    assert r["evidence"] == []
    assert r["related_intelligence"] == {"opportunities": [], "events": [], "ripple": None}
    assert r["follow_up_groups"] == []
    assert r["confidence"] == {"score": None, "level": "unscored", "components_available": []}
    assert r["schema_version"] == "aev2.1"


def test_build_response_never_carries_verdict_shaped_fields():
    r = schema.build_response()
    forbidden = {"rating", "direction", "top_picks", "catalysts", "scenarios", "horizon", "opportunity_score"}
    assert forbidden.isdisjoint(r.keys())
    assert "rating" not in r["risks_and_invalidation"]


def test_build_response_accepts_a_real_direct_conclusion_and_leaves_the_rest_empty():
    r = schema.build_response(direct_conclusion={"text": "real text", "evidence_refs": [1]})
    assert r["direct_conclusion"] == {"text": "real text", "evidence_refs": [1]}
    assert r["confidence"] == schema.empty_confidence()  # untouched


# ── Recommendation-language gate — fail-closed, no regeneration ────────────

def test_gate_passes_clean_text_through_unchanged():
    result = language_gate.gate("direct_conclusion", "HDFC Bank reported a 12% rise in net interest income.")
    assert result.had_violation is False
    assert result.text == "HDFC Bank reported a 12% rise in net interest income."


@pytest.mark.parametrize("text", [
    "HDFC Bank remains a solid buy candidate given its strong fundamentals.",
    "Investors should buy this stock before the results.",
    "This looks like a good entry point for long-term investors.",
    "We recommend investors hold their existing position.",
    "Consider a stop-loss near the recent support level.",
])
def test_gate_fails_closed_on_real_advisory_language(text):
    result = language_gate.gate("direct_conclusion", text)
    assert result.had_violation is True
    assert result.text == language_gate.FALLBACK_TEXT["direct_conclusion"]
    assert result.text != text  # original claim never survives


def test_gate_never_regenerates_or_partially_rewrites_the_claim():
    """The gate has exactly one behavior on violation: wholesale
    replacement with the fixed fallback string. It must never try to
    strip/reword just the offending phrase and keep the rest."""
    text = "HDFC Bank is a buy, with strong asset quality and a clean balance sheet."
    result = language_gate.gate("direct_conclusion", text)
    assert result.had_violation is True
    assert "asset quality" not in result.text  # no partial salvage of the surrounding sentence
    assert result.text == language_gate.FALLBACK_TEXT["direct_conclusion"]


# ── The exact adversarial cases the errata named ────────────────────────────

def test_adversarial_buy_vs_buyback():
    assert language_gate.scan("The stock is a buy at current levels.") != []
    assert language_gate.scan("The company announced a share buyback of ₹500 crore.") == []
    assert language_gate.scan("This was executed as a buy-back, not a fresh purchase.") == []


def test_adversarial_hold_vs_shareholding():
    assert language_gate.scan("We recommend investors hold the stock for now.") != []
    assert language_gate.scan("Promoter shareholding increased to 62% this quarter.") == []
    assert language_gate.scan("The trust's shareholding in the company remains unchanged.") == []


def test_adversarial_short_vs_short_term():
    assert language_gate.scan("Consider shorting the stock ahead of results.") != []
    assert language_gate.scan("This is a short-term headwind, not a structural one.") == []
    assert language_gate.scan("Short term revenue growth may moderate next quarter.") == []


def test_gate_is_only_ever_invoked_on_generated_prose_fields_not_evidence():
    """Documents the field-scoping rule at the call-site level: a source
    evidence title containing a third party's own words (e.g. an
    analyst's real "Buy" call, quoted verbatim in a headline) is a fact
    about what was published, not this platform's own advisory language,
    and must never be run through this gate. assemble.py must never call
    the gate with a field_kind that implies scanning an immutable source
    title."""
    import inspect
    import re
    from app.services.ai_search.aev2 import assemble as assemble_mod

    source = inspect.getsource(assemble_mod)
    calls = re.findall(r'language_gate\.gate\(\s*"([^"]+)"', source)
    assert calls, "expected at least one language_gate.gate(...) call in assemble.py"
    assert all(kind not in ("evidence", "source_title") for kind in calls)


# ── Cache-safe assembly ──────────────────────────────────────────────────────

def test_assemble_aev2_returns_none_when_mode_is_off():
    v3_response = {"answer": {"bottom_line": "some real conclusion"}, "response_id": "r1"}
    assert assemble_aev2("q", v3_response, mode=AEV2Mode.OFF) is None


def test_assemble_aev2_never_mutates_the_input_v3_response():
    v3_response = {"answer": {"bottom_line": "HDFC Bank reported strong results."}, "response_id": "r1"}
    before = dict(v3_response)  # shallow snapshot for comparison
    assemble_aev2("q", v3_response, mode=AEV2Mode.PUBLIC)
    assert v3_response == before
    assert "answer_experience_v2" not in v3_response


def test_assemble_aev2_direct_conclusion_passes_through_clean_bottom_line():
    v3_response = {"answer": {"bottom_line": "HDFC Bank reported strong results."}, "response_id": "r1"}
    result = assemble_aev2("q", v3_response, mode=AEV2Mode.PUBLIC)
    assert result["direct_conclusion"]["text"] == "HDFC Bank reported strong results."


def test_assemble_aev2_direct_conclusion_fails_closed_on_advisory_language():
    v3_response = {"answer": {"bottom_line": "HDFC Bank remains a solid buy candidate."}, "response_id": "r1"}
    result = assemble_aev2("q", v3_response, mode=AEV2Mode.PUBLIC)
    assert result["direct_conclusion"]["text"] == language_gate.FALLBACK_TEXT["direct_conclusion"]


def test_a_simulated_cache_hit_never_gains_answer_experience_v2_on_the_cached_object():
    """Simulates the real integration: a dict cached BEFORE any AEV2
    assembly (exactly how cache_mod.set_response is called deep inside
    the V3 pipeline, upstream of where assembly happens in the API
    route) must never have answer_experience_v2 attached to the same
    object on a later cache hit — only a freshly-built copy may carry it."""
    cached_v3_core = {"answer": {"bottom_line": "Real V3 conclusion."}, "response_id": "cached-1"}
    fake_cache_store = {"q": cached_v3_core}  # mirrors cache_mod._CACHE's role

    # First "request" — cache hit, mode PUBLIC, should get a copy with AEV2 attached.
    result = fake_cache_store["q"]
    aev2_value = assemble_aev2("q", result, mode=AEV2Mode.PUBLIC)
    response_1 = {**result, "answer_experience_v2": aev2_value}
    assert "answer_experience_v2" in response_1

    # The object actually sitting in the cache must be untouched.
    assert "answer_experience_v2" not in fake_cache_store["q"]
    assert fake_cache_store["q"] is cached_v3_core

    # A second "request" against the SAME cached object, mode OFF this
    # time (simulating a flag flip) — must not see AEV2 leak through
    # from the previous request just because it's the same cached dict.
    result_2 = fake_cache_store["q"]
    aev2_value_2 = assemble_aev2("q", result_2, mode=AEV2Mode.OFF)
    assert aev2_value_2 is None
    assert "answer_experience_v2" not in result_2


# ── Security: X-Admin-Key gating, and never present in client-side code ────

def test_has_valid_admin_key_true_only_for_the_exact_configured_key(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "admin_api_key", "real-secret")
    assert has_valid_admin_key("real-secret") is True
    assert has_valid_admin_key("wrong") is False
    assert has_valid_admin_key(None) is False


def test_has_valid_admin_key_false_when_no_key_configured(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "admin_api_key", "")
    assert has_valid_admin_key("anything") is False


def test_x_admin_key_never_appears_anywhere_under_apps_web():
    """Regression tripwire (errata's non-negotiable safeguard): the AEV2
    canary mechanism reuses the existing X-Admin-Key header gate, which
    must stay a backend-only, server-side concern. This scans the actual
    frontend source tree (excluding build output and dependencies) for
    the literal header name — it must never appear there. The moment a
    future change adds it to any frontend file, even one that looks
    server-only, this test fails and forces a deliberate review."""
    web_root = Path(__file__).resolve().parents[3] / "web"
    if not web_root.exists():
        pytest.skip(f"frontend directory not found at {web_root} in this checkout")

    hits: list[str] = []
    skip_dirs = {"node_modules", ".next", ".git", "dist", "build"}
    for path in web_root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in skip_dirs for part in path.parts):
            continue
        if path.suffix not in {".ts", ".tsx", ".js", ".jsx", ".mjs", ".json"}:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if "X-Admin-Key" in text or "x-admin-key" in text.lower():
            hits.append(str(path.relative_to(web_root)))

    assert hits == [], f"X-Admin-Key must never appear in frontend source; found in: {hits}"
