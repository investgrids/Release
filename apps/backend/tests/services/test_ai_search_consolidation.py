"""
Enforcement tests for the "one canonical AI-answer pipeline" architecture
decision (2026-09-21): AEV2 must be a deterministic PRESENTER over one
immutable CoreAnswer, never a second reasoning pipeline, and the
unconditional recommendation-language safety gate must protect every
real serving route regardless of AI_SEARCH_AEV2_MODE.

Covers, concretely:
  - CoreAnswer is a pure, frozen projection (never mutates, never re-runs
    entity resolution / evidence retrieval / a provider call).
  - Both presenters in finalize_v3_response derive from the SAME
    CoreAnswer instance for a given request.
  - The safety gate protects public V3 even with AEV2 fully off (the
    literal defect the 2026-09-21 review named).
  - The gate is field-scoped: it never scans evidence/news/event titles,
    only the platform's own generated conclusion-shaped text.
  - The gate logs only a field name and a fixed code, never raw text.
  - pipeline.py and safety_gate.py's two degraded responses share one
    skeleton (degraded_shape.build_degraded_shape) — same key set.
  - AEV2 package modules never import provider/evidence/entity-resolution
    functions (static import scan — the actual guarantee "AEV2 can't call
    an LLM or retrieve evidence" rests on, not just documentation).
  - Canary admin-key gating end-to-end through finalize_v3_response
    (missing / wrong / correct key), not only the unit-level
    has_valid_admin_key check.
  - The legacy ai_search_service.run_ai_search() function has zero real
    call sites in app/ — the "one canonical pipeline" claim, as a
    regression guard against a new caller silently reappearing.
  - A missing telemetry HMAC key suppresses AEV2 telemetry emission
    entirely, rather than emitting it with a useless shared placeholder
    that would make shadow mode LOOK operational while being unusable.

See test_ai_search_single_pipeline_runtime.py for the runtime (not just
static call-site) proof of the one-call-per-stage invariants, and for
the prediction-recording gating this file doesn't cover (that requires
driving a real run_ai_search_v3 call, not just finalize_v3_response in
isolation).
"""
from __future__ import annotations

import ast
import copy
import re
from pathlib import Path

import pytest
import structlog.testing

from app.services.ai_search import pipeline, safety_gate
from app.services.ai_search.core_answer import CoreAnswer, from_v3_response
from app.services.ai_search.degraded_shape import build_degraded_shape
from app.services.ai_search.response_finalize import finalize_v3_response

BACKEND_ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = BACKEND_ROOT / "app"


# ── CoreAnswer: pure, frozen projection ─────────────────────────────────────

def test_core_answer_is_frozen():
    import dataclasses
    core = from_v3_response({"answer": {"bottom_line": "x"}})
    with __import__("pytest").raises(dataclasses.FrozenInstanceError):
        core.bottom_line = "mutated"


def test_from_v3_response_never_mutates_its_input():
    v3_response = {"answer": {"bottom_line": "HDFC Bank reported strong results."}, "response_id": "r1"}
    before = dict(v3_response)
    from_v3_response(v3_response)
    assert v3_response == before


def test_core_answer_does_not_alias_the_original_response_nested_dicts():
    """A frozen dataclass only blocks reassigning a FIELD — it does
    nothing to stop code from reaching into a nested dict a tuple field
    holds and mutating that dict in place. from_v3_response must
    deep-copy, not just tuple()-wrap, or a mutation on the original
    v3_response's companies list (which the V3 presenter itself still
    holds and returns to the caller) would silently reach the "immutable"
    CoreAnswer too, and vice versa."""
    v3_response = {
        "answer": {"bottom_line": "x"},
        "companies": [{"symbol": "RELIANCE", "impact_score": 80}],
    }
    core = from_v3_response(v3_response)

    # Mutate the ORIGINAL dict's nested company entry after projection.
    v3_response["companies"][0]["impact_score"] = 999
    assert core.companies[0]["impact_score"] == 80, "CoreAnswer aliased the original response's nested dict"

    # And the reverse: mutating CoreAnswer's own nested dict must not
    # reach back into the original v3_response either.
    core.companies[0]["impact_score"] = -1
    assert v3_response["companies"][0]["impact_score"] == 999, "mutating CoreAnswer's nested dict leaked back to the original response"


def test_assemble_aev2_never_mutates_any_nested_dict_inside_core_answer():
    """Snapshot-compare (deep copy) before and after a presenter runs —
    proves the presenter didn't reach past the frozen dataclass shell and
    mutate a nested dict in place, which a shallow equality check on
    `core == before` would not by itself rule out for two dicts that
    happen to still be equal in value but were touched in between."""
    import copy
    from app.services.ai_search.aev2.assemble import assemble_aev2
    from app.services.ai_search.aev2.mode import AEV2Mode

    v3_response = {
        "answer": {"bottom_line": "HDFC Bank reported strong results."},
        "companies": [{"symbol": "HDFCBANK", "impact_score": 80, "reason": "steady growth"}],
        "related_events": [{"id": "e1", "title": "HDFC Bank Q2 results announced"}],
    }
    core = from_v3_response(v3_response)
    snapshot = copy.deepcopy(core)

    assemble_aev2(core, mode=AEV2Mode.PUBLIC)

    assert core == snapshot
    assert core.companies[0]["impact_score"] == 80
    assert core.related_events[0]["title"] == "HDFC Bank Q2 results announced"


def test_from_v3_response_is_pure_same_input_same_output():
    v3_response = {"answer": {"bottom_line": "x", "summary": "y"}, "response_id": "r1", "companies": [{"symbol": "A"}]}
    assert from_v3_response(v3_response) == from_v3_response(dict(v3_response))


def test_core_answer_module_imports_nothing_from_provider_evidence_or_entities():
    """CoreAnswer is a read-only projection over an already-computed V3
    dict — it must never import the machinery that produced that dict in
    the first place (that would make it capable of re-running reasoning,
    not just presenting it)."""
    source = (APP_ROOT / "services" / "ai_search" / "core_answer.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imported_modules.add(alias.name)
    forbidden_substrings = ("ai_service", "evidence", "entities", "specialists", "ai_search.pipeline")
    for mod in imported_modules:
        assert not any(f in mod for f in forbidden_substrings), f"core_answer.py must not import {mod}"


# ── Both presenters derive from the same CoreAnswer instance ───────────────

def test_finalize_builds_aev2_from_a_core_answer_matching_the_returned_v3_dict(monkeypatch):
    """Proves the CoreAnswer passed to the AEV2 presenter is the same
    projection that would be derived from the exact `result` dict this
    function returns for the V3 presenter — not a second, potentially
    divergent read."""
    from app.core.config import settings
    from app.services.ai_search.aev2 import mode as mode_mod

    monkeypatch.setattr(settings, "ai_search_aev2_mode", "public")
    monkeypatch.setattr(mode_mod, "AEV2_BUILD_COMPLETE", True)

    captured: dict = {}
    real_assemble = __import__(
        "app.services.ai_search.aev2.assemble", fromlist=["assemble_aev2"],
    ).assemble_aev2

    def spy_assemble(core, *, mode):
        captured["core"] = core
        return real_assemble(core, mode=mode)

    monkeypatch.setattr("app.services.ai_search.response_finalize.assemble_aev2", spy_assemble)

    # Companies must be resolved for "HDFC Bank" to pass entity
    # validation post-2026-09-21-review (no vacuous pass when nothing is
    # resolved).
    v3_response = {
        "answer": {"bottom_line": "HDFC Bank reported strong results."}, "response_id": "r1",
        "companies": [{"symbol": "HDFCBANK", "name": "HDFC Bank Ltd"}],
    }
    result = finalize_v3_response("q", dict(v3_response), was_cached=True)

    assert captured["core"] == from_v3_response(v3_response)
    assert result["answer_experience_v2"]["direct_conclusion"]["text"] == "HDFC Bank reported strong results."


# ── The safety gate protects public V3 unconditionally ─────────────────────

def test_finalize_v3_response_degrades_advisory_bottom_line_even_with_aev2_fully_off(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "ai_search_aev2_mode", "off")

    v3_response = {
        "answer": {"bottom_line": "HDFC Bank remains a solid buy candidate.", "summary": "ok"},
        "response_id": "r1", "companies": [{"symbol": "HDFCBANK"}],
    }
    result = finalize_v3_response("Should I invest in HDFC Bank?", v3_response)

    assert result["synthesis_incomplete"] is True
    assert result["degraded_reason"] == "recommendation_language_violation"
    assert "answer_experience_v2" not in result


def test_finalize_v3_response_never_mutates_the_input_dict(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "ai_search_aev2_mode", "off")

    v3_response = {
        "answer": {"bottom_line": "HDFC Bank remains a solid buy candidate.", "summary": "ok"},
        "response_id": "r1", "companies": [{"symbol": "HDFCBANK"}],
    }
    before = {k: (dict(v) if isinstance(v, dict) else list(v) if isinstance(v, list) else v)
              for k, v in v3_response.items()}
    finalize_v3_response("q", v3_response)
    assert v3_response["answer"]["bottom_line"] == before["answer"]["bottom_line"]
    assert v3_response["companies"] == before["companies"]
    assert "degraded_reason" not in v3_response


def test_clean_response_passes_through_finalize_unmodified(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "ai_search_aev2_mode", "off")

    v3_response = {"answer": {"bottom_line": "HDFC Bank reported strong quarterly results."}, "response_id": "r1"}
    result = finalize_v3_response("q", v3_response, was_cached=True)
    assert result.get("synthesis_incomplete") is not True
    assert result["answer"]["bottom_line"] == "HDFC Bank reported strong quarterly results."


# ── Field-scoping: never scans evidence/source titles ───────────────────────

def test_safety_gate_never_flags_an_immutable_event_title_containing_advisory_words():
    """A real analyst's own headline ("Brokerage X says Buy") is a fact
    about what was published, not this platform's own advisory language —
    find_v3_safety_violation only scans _SAFETY_FIELDS, never
    related_events/news/policies text."""
    result = {
        "answer": {"bottom_line": "HDFC Bank reported quarterly results in line with estimates."},
        "related_events": [{"id": "e1", "title": "Brokerage XYZ maintains Buy rating on HDFC Bank"}],
        "news": [{"id": "n1", "headline": "Analyst says short the stock ahead of results"}],
    }
    assert safety_gate.find_v3_safety_violation(result) is None


def test_safety_gate_field_scope_excludes_evidence_and_source_titles_by_construction():
    paths = [p for p, _ in safety_gate._SAFETY_FIELDS]
    flat = {seg for path in paths for seg in path}
    assert "related_events" not in flat
    assert "news" not in flat
    assert "policies" not in flat
    assert "title" not in flat
    assert "headline" not in flat


# ── Logging: field + code only, never raw matched text ──────────────────────

def test_safety_gate_logs_only_field_and_code_never_the_offending_text():
    result = {"answer": {"bottom_line": "HDFC Bank remains a solid buy candidate."}}
    with structlog.testing.capture_logs() as logs:
        violated = safety_gate.find_v3_safety_violation(result)
        assert violated == "bottom_line"
        safety_gate.build_v3_safety_degraded_response(result, violated)

    violation_logs = [e for e in logs if e.get("event") == "ai_search_v3.recommendation_language_violation"]
    assert len(violation_logs) == 1
    entry = violation_logs[0]
    assert entry["field"] == "bottom_line"
    assert entry["violation_code"] == "recommendation_language_pattern_match"
    serialized = repr(entry)
    assert "solid buy candidate" not in serialized
    assert "HDFC Bank remains" not in serialized


# ── One shared degraded-response skeleton ───────────────────────────────────

def test_pipeline_and_safety_gate_degraded_responses_share_one_key_skeleton():
    pipeline_shape = build_degraded_shape(
        query="q", response_id="r1", schema_version="v3.1", specialist_kind="company",
        degraded_reason="parse_failure", summary="s",
    )
    safety_shape = safety_gate.build_v3_safety_degraded_response(
        {"answer": {"bottom_line": "solid buy candidate", "sources_count": 2}, "response_id": "r1"},
        "bottom_line",
    )
    assert set(pipeline_shape.keys()) == set(safety_shape.keys())
    assert set(pipeline_shape["answer"].keys()) == set(safety_shape["answer"].keys())


def test_pipeline_build_degraded_response_uses_the_shared_builder():
    source = (APP_ROOT / "services" / "ai_search" / "pipeline.py").read_text(encoding="utf-8")
    assert "build_degraded_shape(" in source
    assert "from app.services.ai_search.degraded_shape import build_degraded_shape" in source


def test_safety_gate_uses_the_shared_builder():
    source = (APP_ROOT / "services" / "ai_search" / "safety_gate.py").read_text(encoding="utf-8")
    assert "build_degraded_shape(" in source
    assert "from app.services.ai_search.degraded_shape import build_degraded_shape" in source


# ── AEV2 modules cannot import provider/fallback/retrieval machinery ───────

def test_aev2_package_never_imports_provider_evidence_or_entity_resolution():
    aev2_dir = APP_ROOT / "services" / "ai_search" / "aev2"
    forbidden_substrings = (
        "ai_service", "aipe.candidate", "evidence", "entities",
        "specialists", "ai_search.pipeline",
    )
    offenders = []
    for py_file in aev2_dir.glob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            mods = []
            if isinstance(node, ast.ImportFrom) and node.module:
                mods.append(node.module)
            elif isinstance(node, ast.Import):
                mods.extend(a.name for a in node.names)
            for mod in mods:
                if any(f in mod for f in forbidden_substrings):
                    offenders.append((py_file.name, mod))
    assert offenders == [], f"AEV2 modules must not import reasoning-pipeline machinery: {offenders}"


def test_aev2_assemble_never_calls_run_ai_search_v3_or_a_provider():
    source = (APP_ROOT / "services" / "ai_search" / "aev2" / "assemble.py").read_text(encoding="utf-8")
    assert "run_ai_search_v3" not in source
    assert "_call_with_fallback" not in source
    assert "_call_provider" not in source


# ── Canary admin-key gating, exercised through the real finalize logic ─────

def test_finalize_canary_mode_missing_admin_key_never_returns_aev2(monkeypatch):
    from app.core.config import settings
    from app.services.ai_search.aev2 import mode as mode_mod

    monkeypatch.setattr(settings, "ai_search_aev2_mode", "canary")
    monkeypatch.setattr(settings, "admin_api_key", "real-secret")
    monkeypatch.setattr(mode_mod, "AEV2_BUILD_COMPLETE", True)

    result = finalize_v3_response(
        "q", {"answer": {"bottom_line": "clean text"}, "response_id": "r1"}, x_admin_key=None, was_cached=True,
    )
    assert "answer_experience_v2" not in result


def test_finalize_canary_mode_wrong_admin_key_never_returns_aev2(monkeypatch):
    from app.core.config import settings
    from app.services.ai_search.aev2 import mode as mode_mod

    monkeypatch.setattr(settings, "ai_search_aev2_mode", "canary")
    monkeypatch.setattr(settings, "admin_api_key", "real-secret")
    monkeypatch.setattr(mode_mod, "AEV2_BUILD_COMPLETE", True)

    result = finalize_v3_response(
        "q", {"answer": {"bottom_line": "clean text"}, "response_id": "r1"}, x_admin_key="wrong-key", was_cached=True,
    )
    assert "answer_experience_v2" not in result


def test_finalize_canary_mode_correct_admin_key_returns_aev2(monkeypatch):
    from app.core.config import settings
    from app.services.ai_search.aev2 import mode as mode_mod

    monkeypatch.setattr(settings, "ai_search_aev2_mode", "canary")
    monkeypatch.setattr(settings, "admin_api_key", "real-secret")
    monkeypatch.setattr(mode_mod, "AEV2_BUILD_COMPLETE", True)

    result = finalize_v3_response(
        "q", {"answer": {"bottom_line": "clean text"}, "response_id": "r1"}, x_admin_key="real-secret", was_cached=True,
    )
    assert "answer_experience_v2" in result
    assert result["answer_experience_v2"]["direct_conclusion"]["text"] == "clean text"


def test_finalize_canary_mode_now_returns_with_correct_key_now_that_the_build_is_complete(monkeypatch):
    """AEV2_BUILD_COMPLETE defaults to True in the real codebase now
    (2026-09-22, isolated readiness-latch commit) — this test does NOT
    monkeypatch it, proving canary mode's own admin-key gate is now the
    only thing standing between a correctly-keyed request and the
    payload. AI_SEARCH_AEV2_MODE itself still defaults to "off" in real,
    unconfigured production (app/core/config.py) — this test only
    proves what happens once something upstream DOES select canary."""
    from app.core.config import settings
    from app.services.ai_search.aev2.mode import AEV2_BUILD_COMPLETE

    assert AEV2_BUILD_COMPLETE is True, "if this now reads False, the readiness-latch commit was reverted — update this test to match"
    monkeypatch.setattr(settings, "ai_search_aev2_mode", "canary")
    monkeypatch.setattr(settings, "admin_api_key", "real-secret")

    result = finalize_v3_response(
        "q", {"answer": {"bottom_line": "clean text"}, "response_id": "r1"}, x_admin_key="real-secret", was_cached=True,
    )
    assert "answer_experience_v2" in result


def test_finalize_canary_mode_still_stays_off_if_the_readiness_latch_were_ever_flipped_back(monkeypatch):
    """The mirror-image proof: the readiness latch, not just the admin-
    key check, is still what gates canary/public — flips
    AEV2_BUILD_COMPLETE back to False (the pre-2026-09-22 default) to
    confirm a correctly-keyed canary request would still be blocked if
    that ever needed to happen again (e.g. an emergency rollback)."""
    from app.core.config import settings
    from app.services.ai_search.aev2 import mode as mode_mod

    monkeypatch.setattr(mode_mod, "AEV2_BUILD_COMPLETE", False)
    monkeypatch.setattr(settings, "ai_search_aev2_mode", "canary")
    monkeypatch.setattr(settings, "admin_api_key", "real-secret")

    result = finalize_v3_response(
        "q", {"answer": {"bottom_line": "clean text"}, "response_id": "r1"}, x_admin_key="real-secret", was_cached=True,
    )
    assert "answer_experience_v2" not in result


# ── Legacy pipeline: zero real callers, as a regression guard ──────────────

def test_legacy_run_ai_search_has_zero_real_call_sites_in_app():
    """2026-09-21 audit finding: app.services.ai_search_service.run_ai_search
    (V2's original orchestration function) has no real callers anywhere in
    app/ — every route already delegates to the one canonical
    run_ai_search_v3 pipeline (see api/ai_search.py's own "6G Cutover
    Gate" comment). This test guards against a new caller of the legacy
    function silently reappearing, which would reintroduce a second
    reasoning pipeline."""
    # "run_ai_search(" (literal '(' right after) never matches
    # "run_ai_search_v3(" — the '_v3' segment sits between the name and
    # the paren, so this pattern already excludes the canonical pipeline.
    call_pattern = re.compile(r"\brun_ai_search\(")
    real_offenders = []
    for py_file in APP_ROOT.rglob("*.py"):
        text = py_file.read_text(encoding="utf-8", errors="ignore")
        for line in text.splitlines():
            if call_pattern.search(line) and "def run_ai_search(" not in line:
                real_offenders.append((str(py_file.relative_to(APP_ROOT)), line.strip()))
    assert real_offenders == [], f"unexpected legacy run_ai_search() call sites: {real_offenders}"


# ── Exactly one provider call per specialist (structural guard) ────────────

def test_each_specialist_has_exactly_one_provider_call_site():
    """Each of company/sector/refine's own docstring already claims
    "Single _call_with_fallback call" — this makes that claim an enforced
    invariant instead of a comment: a second call site appearing in any
    of these files (e.g. a retry loop added later, or an accidental
    second specialist reasoning pass) would silently turn "one provider
    call per request" into two, and this test catches that at review
    time rather than in production capacity metrics.

    comparison.py is intentionally excluded from the ==1 assertion below:
    it has 2 call sites by design — run() (the primary attempt) and
    _run_multi_compare_compact_retry() (a documented, format-only retry
    path taken only when run()'s own JSON parse fails) — a single
    specialist's own internal retry-on-parse-failure, not a second
    reasoning pipeline. It's checked separately to guard against a THIRD
    call site appearing instead."""
    specialists_dir = APP_ROOT / "services" / "ai_search" / "specialists"
    call_pattern = re.compile(r"_call_with_fallback\(")
    for name in ("company.py", "sector.py", "refine.py"):
        source = (specialists_dir / name).read_text(encoding="utf-8")
        call_sites = call_pattern.findall(source)
        assert len(call_sites) == 1, f"{name} has {len(call_sites)} _call_with_fallback call sites, expected exactly 1"

    comparison_source = (specialists_dir / "comparison.py").read_text(encoding="utf-8")
    assert len(call_pattern.findall(comparison_source)) == 2, (
        "comparison.py's call-site count changed — verify it's still exactly "
        "run() + the documented compact-retry path, not a new third call site"
    )


def test_legacy_search_route_delegates_to_the_canonical_v3_pipeline():
    source = (APP_ROOT / "api" / "ai_search.py").read_text(encoding="utf-8")
    assert "run_ai_search_v3" in source
    assert "from app.services.ai_search_service import run_ai_search" not in source
    assert "ai_search_service.run_ai_search(" not in source


# ── Missing telemetry key suppresses emission, never a usable-looking
#    placeholder ───────────────────────────────────────────────────────────

def test_missing_telemetry_key_suppresses_emission_entirely(monkeypatch):
    from app.core.config import settings
    from app.services.ai_search.aev2 import telemetry as telemetry_mod

    monkeypatch.setattr(settings, "aev2_telemetry_key", "")
    monkeypatch.setattr(telemetry_mod, "_warned_unconfigured", False)

    with structlog.testing.capture_logs() as logs:
        telemetry_mod.emit_assembly_success(
            query="Should I invest in HDFC Bank?", mode="shadow", response_id="r1",
            had_language_violation=False, is_fallback=False, stage_ms={},
        )
        telemetry_mod.emit_assembly_failed(query="q2", mode="shadow", failure_reason="x", stage_ms={})
        telemetry_mod.emit_confidence_computed(query="q3", aev2_score=50.0, components_available=[], llm_self_rating=None)

    assembly_events = [e for e in logs if e.get("event", "").startswith("ai_search.aev2_")
                        and e["event"] != "ai_search.aev2_telemetry_key_unconfigured"]
    assert assembly_events == [], f"expected zero telemetry events with no key configured, got {assembly_events}"

    warn_events = [e for e in logs if e.get("event") == "ai_search.aev2_telemetry_key_unconfigured"]
    assert len(warn_events) == 1, "should warn once, not once per emit call"


def test_configured_telemetry_key_emits_normally_with_a_real_hash(monkeypatch):
    from app.core.config import settings
    from app.services.ai_search.aev2 import telemetry as telemetry_mod

    monkeypatch.setattr(settings, "aev2_telemetry_key", "real-telemetry-secret")

    with structlog.testing.capture_logs() as logs:
        telemetry_mod.emit_assembly_success(
            query="Should I invest in HDFC Bank?", mode="shadow", response_id="r1",
            had_language_violation=False, is_fallback=False, stage_ms={},
        )

    events = [e for e in logs if e.get("event") == "ai_search.aev2_assembly"]
    assert len(events) == 1
    assert events[0]["query_hash"] not in ("", "telemetry-key-unconfigured")
    assert len(events[0]["query_hash"]) == 16


# ── Internal-only attribution plumbing never reaches a public caller ──────
# (review, 2026-09-21: "announcements" — surfaced into the V3 response dict
# purely so CoreAnswer/AEV2's citation validator can attribute claims to
# CompanyAnnouncement rows — was never part of V3's public contract before
# AEV2 existed, and must not become part of it now, on ANY route, cached or
# fresh, regardless of AEV2 mode.)

def _v3_response_with_announcements(**overrides) -> dict:
    base = {
        "answer": {"bottom_line": "Reliance Industries reported strong results.", "summary": "ok"},
        "response_id": "r1", "companies": [{"symbol": "RELIANCE", "name": "Reliance Industries Ltd"}],
        "related_events": [], "news": [], "policies": [],
        "announcements": [{"id": "a1", "symbol": "RELIANCE", "subject": "Board approves capex plan"}],
    }
    base.update(overrides)
    return base


@pytest.mark.parametrize("mode", ["off", "shadow", "canary", "public"])
def test_finalize_strips_announcements_for_every_aev2_mode(monkeypatch, mode):
    from app.core.config import settings
    from app.services.ai_search.aev2 import mode as mode_mod

    monkeypatch.setattr(settings, "ai_search_aev2_mode", mode)
    monkeypatch.setattr(mode_mod, "AEV2_BUILD_COMPLETE", True)
    monkeypatch.setattr(settings, "admin_api_key", "real-secret")

    result = finalize_v3_response(
        "q", _v3_response_with_announcements(), x_admin_key="real-secret", was_cached=True,
    )
    assert "announcements" not in result
    if "answer_experience_v2" in result:
        assert "announcements" not in result["answer_experience_v2"]


def test_finalize_strips_announcements_on_a_cache_hit():
    """was_cached=True must not change the stripping behavior — the
    cached object itself may carry internal fields; the response handed
    back to THIS caller must never carry them regardless."""
    result = finalize_v3_response("q", _v3_response_with_announcements(), was_cached=True)
    assert "announcements" not in result


def test_finalize_never_mutates_the_cached_object_while_stripping():
    """The dict sitting in cache_mod._CACHE must still carry
    announcements after finalize_v3_response runs on it — stripping
    builds a new dict for the OUTGOING response, it never edits the
    cached one in place."""
    cached = _v3_response_with_announcements()
    before = copy.deepcopy(cached)
    finalize_v3_response("q", cached, was_cached=True)
    assert cached == before
    assert "announcements" in cached


def test_core_answer_still_receives_announcements_despite_stripping(monkeypatch):
    """The whole point of putting announcements in the internal dict at
    all — CoreAnswer, and therefore AEV2's citation validator, must still
    see them even though the public result never does."""
    from app.core.config import settings
    from app.services.ai_search.aev2 import mode as mode_mod

    monkeypatch.setattr(settings, "ai_search_aev2_mode", "public")
    monkeypatch.setattr(mode_mod, "AEV2_BUILD_COMPLETE", True)

    captured: dict = {}
    real_assemble = __import__(
        "app.services.ai_search.aev2.assemble", fromlist=["assemble_aev2"],
    ).assemble_aev2

    def spy_assemble(core, *, mode):
        captured["core"] = core
        return real_assemble(core, mode=mode)

    monkeypatch.setattr("app.services.ai_search.response_finalize.assemble_aev2", spy_assemble)

    result = finalize_v3_response("q", _v3_response_with_announcements(), was_cached=True)

    assert captured["core"].announcements == ({"id": "a1", "symbol": "RELIANCE", "subject": "Board approves capex plan"},)
    assert "announcements" not in result


def test_aev2_off_public_result_unaffected_by_internal_announcement_plumbing():
    """The exact regression this review named: AEV2=off must return
    byte-identical output to what V3's public contract looked like
    before announcements existed at all — i.e. the same dict with
    exactly the internal-only key removed, plus the one intentional
    2026-09-23 addition (answer_availability — see
    test_answer_availability.py for its own dedicated coverage),
    nothing else different."""
    v3_response = _v3_response_with_announcements()
    prior_public_shape = {k: v for k, v in v3_response.items() if k != "announcements"}
    prior_public_shape["answer_availability"] = {
        "state": "available", "evidence_retrieval_completed": True, "evidence_count": 0, "reason": None, "basis": "retrieved_evidence",      # reason/basis: additive, Step 4C
        "kind": "research", "scope": "full", "conclusion_authorized": False,                                          # kind/scope/conclusion_authorized: additive, Step 5
    }

    result = finalize_v3_response("q", dict(v3_response), was_cached=True)
    assert result == prior_public_shape
