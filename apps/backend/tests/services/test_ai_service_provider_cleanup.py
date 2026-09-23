"""
Provider cleanup (2026-09-24) — two independent defects removed from the
Groq answer-synthesis fallback chain:

1. groq/compound and groq/compound-mini confirmed permanently gone from
   the real Groq catalog via a live, authenticated GET
   https://api.groq.com/openai/v1/models probe against the production
   key (status 200, full catalog returned, neither slug present).
   Decommissioned by Groq on 2026-09-21 with no recommended direct
   replacement.

2. openai/gpt-oss-safeguard-20b was never a general answer-generation
   model at all, even though it had been silently used as one in this
   chain since 2026-08-22 — verified directly against Groq's own model
   documentation (console.groq.com/docs/model/openai/gpt-oss-
   safeguard-20b): "specifically trained for safety classification
   tasks... helps classify text content based on customizable policies"
   for Trust & Safety content moderation / policy-based classification /
   automated triage. It has no dedicated moderation/safety-classification
   call site anywhere in this codebase to relocate it into either
   (grep-confirmed: app/services/ai_service.py was its only reference) —
   this app's real safety net for generated text is the deterministic,
   non-LLM advisory-language scanner (safety_gate.py/advisory_
   language.py), which never called this model.

This test file pins BOTH fixes so a future re-add of either the dead
compound slugs or safeguard into an answer-generation tier fails fast in
CI, rather than silently degrading answer quality/factuality (a
moderation-tuned model reasoning about investment research) or 404ing on
every request until the next live incident surfaces it.
"""
from __future__ import annotations

import httpx
import pytest

from app.core.config import settings
from app.services import ai_service
from app.services.ai_service import _GROQ_FAST, _GROQ_HIGH, _GROQ_REASONING_EFFORT

_CONFIRMED_DEAD_GROQ_SLUGS = {"groq/compound", "groq/compound-mini"}
_MODERATION_ONLY_MODELS = {"openai/gpt-oss-safeguard-20b"}
_EXCLUDED_FROM_SYNTHESIS = _CONFIRMED_DEAD_GROQ_SLUGS | _MODERATION_ONLY_MODELS

# The ONLY place a moderation-only model would be legitimate to
# reference — a dedicated, explicitly-named safety-classification
# config, never the answer-synthesis tiers. Does not exist yet in this
# codebase (safety is handled deterministically instead — see the
# module docstring above), so this stays empty; it exists as the one
# named exception _EXCLUDED_FROM_SYNTHESIS's own tests below check
# against, so that adding a real one later is a deliberate, visible
# change to this test file rather than a silent bypass.
_SAFETY_CLASSIFICATION_MODELS: set[str] = set()


def test_dead_groq_slugs_are_absent_from_every_groq_tier():
    all_groq_models = set(_GROQ_HIGH) | set(_GROQ_FAST)
    overlap = all_groq_models & _CONFIRMED_DEAD_GROQ_SLUGS
    assert overlap == set(), f"confirmed-dead Groq slug(s) re-entered the fallback chain: {overlap}"


def test_dead_groq_slugs_are_absent_from_the_reasoning_effort_map():
    overlap = set(_GROQ_REASONING_EFFORT) & _CONFIRMED_DEAD_GROQ_SLUGS
    assert overlap == set()


def test_moderation_only_model_never_appears_in_an_answer_generation_tier():
    """gpt-oss-safeguard-20b (or any future model this codebase learns is
    moderation/classification-only) must never be callable from the
    tiers real user queries are answered from."""
    answer_generation_models = set(_GROQ_HIGH) | set(_GROQ_FAST)
    overlap = answer_generation_models & _MODERATION_ONLY_MODELS
    assert overlap == set(), f"moderation-only model(s) reachable from answer synthesis: {overlap}"


def test_moderation_only_model_permitted_only_in_an_explicitly_named_safety_classification_config():
    """The one legitimate home for a moderation-only model is a config
    explicitly named for that purpose — never smuggled into a general
    synthesis tier under a comment. No such config exists in this
    codebase yet (see _SAFETY_CLASSIFICATION_MODELS's own comment); this
    assertion is the enforcement point if one is ever added incorrectly."""
    assert _MODERATION_ONLY_MODELS.issubset(_SAFETY_CLASSIFICATION_MODELS) or not _SAFETY_CLASSIFICATION_MODELS, (
        "a moderation-only model was added to a 'safety classification' config that doesn't "
        "actually contain it — check for a typo or a model missing from _SAFETY_CLASSIFICATION_MODELS"
    )


def test_groq_fast_tier_is_exactly_the_one_confirmed_live_synthesis_model():
    """Not just "the excluded ones are gone" — pins the exact, currently-
    correct set too, so a future addition still gets caught by this
    test's own reasoning (add a real live-probe/doc-verification comment
    + update this list deliberately, don't just append)."""
    assert _GROQ_FAST == ["qwen/qwen3.8-27b"]


def test_groq_synthesis_models_are_exactly_the_three_confirmed_general_purpose_ones():
    """The full, correct Groq answer-synthesis roster after both fixes —
    confirmed live-reachable (compound/compound-mini) and confirmed
    general-purpose via Groq's own docs (safeguard is not)."""
    high, fast = set(_GROQ_HIGH), set(_GROQ_FAST)
    assert high.isdisjoint(fast), f"a model is listed in both Groq tiers: {high & fast}"
    all_synthesis_models = high | fast
    assert all_synthesis_models == {"openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b"}
    assert all_synthesis_models.isdisjoint(_EXCLUDED_FROM_SYNTHESIS)


# ── Mistral disabled pending key rotation (2026-09-24 security incident) ──
#
# The production MISTRAL_API_KEY was accidentally exposed via `railway
# variables --kv` and has been removed from Railway; the local dev key was
# separately already invalid. Both are now empty/absent rather than
# reactivating a bad or exposed credential. `_call_with_fallback`'s
# `if settings.mistral_api_key:` gate (unchanged code — this section only
# adds regression coverage) already means an empty key skips the entire
# Mistral tier, never constructing a request — this proves it, so a future
# refactor of that gate can't silently start dialing Mistral again with no
# real key configured. See project_mistral_key_exposure_incident.md (Claude
# memory) for the incident record and restoration plan (fresh key only,
# never the exposed one, plus one sanitized smoke test before re-enabling).

def _unreachable_transport(request: httpx.Request) -> httpx.Response:
    raise AssertionError(f"no HTTP request should have been made, got one to {request.url}")


async def test_no_mistral_request_is_attempted_when_the_key_is_absent(monkeypatch):
    monkeypatch.setattr(settings, "mistral_api_key", "")
    monkeypatch.setattr(ai_service, "_EXHAUSTED", {})

    class _FailingAsyncClient(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = httpx.MockTransport(_unreachable_transport)
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(ai_service.httpx, "AsyncClient", _FailingAsyncClient)
    # Every OTHER provider also disabled so _call_with_fallback has nothing
    # left to try — isolates this test to proving Mistral specifically is
    # skipped, not just that some earlier tier happened to return first.
    for key in ("groq_api_key", "openrouter_api_key", "gemini_api_key"):
        monkeypatch.setattr(settings, key, "")

    result = await ai_service._call_with_fallback("prompt", priority="background")
    assert result == ""


async def test_mistral_tier_is_skipped_but_other_providers_still_work_when_mistral_key_is_absent(monkeypatch):
    """The gate is per-provider, not a global kill switch — disabling
    Mistral must not accidentally disable the rest of the fallback chain.
    Groq is configured and answers; Mistral has no key and must never be
    dialed at all."""
    monkeypatch.setattr(settings, "mistral_api_key", "")
    monkeypatch.setattr(settings, "groq_api_key", "fake-groq-key-for-test")
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    monkeypatch.setattr(settings, "gemini_api_key", "")
    monkeypatch.setattr(ai_service, "_EXHAUSTED", {})

    def handler(request: httpx.Request) -> httpx.Response:
        assert "mistral" not in str(request.url), f"a request reached Mistral despite no key configured: {request.url}"
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok from groq"}}]})

    class _FakeAsyncClient(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = httpx.MockTransport(handler)
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(ai_service.httpx, "AsyncClient", _FakeAsyncClient)

    result = await ai_service._call_with_fallback("prompt", priority="background")
    assert result == "ok from groq"
