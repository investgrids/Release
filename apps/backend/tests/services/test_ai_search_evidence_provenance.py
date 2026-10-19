"""
Provenance contract, Stage B (2026-10-19) -- app/ai_pipeline/templates/base.py
is where Evidence objects get flattened into the JSON facts block the AI
Search LLM actually reads. Real data showed fallback-sourced events can be
74-88% of the currently-eligible evidence pool in the live windows, so the
chosen policy is label-not-exclude: a "provenance" key, set ONLY when the
producing retriever actually tracks it (never defaulted to "ai" for a
source that has no concept of triage provenance -- most retrievers don't).
"""
from __future__ import annotations

from app.ai_pipeline.contracts import DecisionResult, Evidence
from app.ai_pipeline.templates.base import build_prompt, decision_facts_json
from app.services.confidence_service import ConfidenceResult


def _decision() -> DecisionResult:
    return DecisionResult(
        verdict="Neutral", confidence=ConfidenceResult(50.0, "Medium", [], "", {}),
        risk_level="medium", horizon="short", mood="sideways", drivers=[],
        opportunities=[], risks=[], historical_probability=None, ripple_reach=None,
        beneficiaries=[], losers=[], missing_data=[],
    )


def _evidence(raw: dict | None = None) -> Evidence:
    return Evidence(
        id="intelligence_publishing:event:x", source="intelligence_publishing", entity=None,
        claim="Some claim text", polarity="neutral", magnitude=0.8, confidence=0.4,
        raw=raw or {},
    )


def test_provenance_key_present_only_when_the_retriever_tracked_it():
    facts = decision_facts_json(_decision(), [
        _evidence({"triage_source": "rule_based_fallback"}),
        _evidence({"triage_source": "ai"}),
        _evidence({}),  # e.g. a news/market retriever item with no triage concept at all
    ])
    import json
    parsed = json.loads(facts)
    items = parsed["supporting_evidence"]
    assert items[0]["provenance"] == "rule_based_fallback"
    assert items[1]["provenance"] == "ai"
    assert "provenance" not in items[2], "must never fabricate a default for a source with no triage concept"


def test_prompt_instructs_the_model_on_rule_based_fallback_provenance():
    # build_prompt needs a real AnswerTemplate; construct a minimal stand-in
    # rather than importing a concrete template module, to keep this test
    # scoped to base.py's own instruction text, not any one template's content.
    from app.ai_pipeline.templates.base import AnswerTemplate
    template = AnswerTemplate(
        key="t", label="t", required_sections=("summary",), llm_sections=("summary",),
        system_prompt="", deterministic_sections=lambda d, e: {},
    )
    prompt = build_prompt(template, "test query", _decision(), [_evidence({"triage_source": "rule_based_fallback"})])
    assert "rule_based_fallback" in prompt
    assert "not an analyst-verified conclusion" in prompt
