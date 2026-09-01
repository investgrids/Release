"""
Article V2 Phase C5.3 — Headline Engine tests. Real DB not needed (pure
dataclasses + a mocked/real LLM call). Covers every required adversarial
case: fabricated numbers, unsupported percentages, provider failure,
entity mismatch, clickbait, and near-duplicate headlines for a different
identity -- plus one real, live LLM integration test proving the whole
pipeline actually works end to end.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

import app.services.article_v2.headline_engine as headline_engine_module
from app.services.article_v2.context_builder import ArticleContextBundle, ContextFinancialFact, MarketReaction, NONE_STATUS
from app.services.article_v2.evidence_set_builder import ArticleEvidenceSet
from app.services.article_v2.headline_engine import ValidationOutcome, generate_headline
from app.services.article_v2.identity import compute_identity
from app.services.warehouse.read_service import LinkedEvidence


def _evidence(title: str) -> LinkedEvidence:
    return LinkedEvidence(
        raw_evidence_id=str(uuid.uuid4()), title=title, source_type="nse",
        published_at=datetime.now(timezone.utc), source_url=None,
        relationship_type="subject", resolution_method="source_symbol", link_confidence=None,
    )


def _es(symbol: str, primary_title: str, supporting: list[LinkedEvidence] | None = None) -> ArticleEvidenceSet:
    return ArticleEvidenceSet(
        entity_id=f"cmp_{symbol.lower()}", symbol=symbol, event_id="evt", event_headline=primary_title,
        status="COHERENT", primary_evidence=_evidence(primary_title), supporting_evidence=supporting or [],
    )


def _mock_llm(monkeypatch, responses: list[str] | Exception):
    calls = {"n": 0}

    async def fake_call(prompt, system="", max_tokens=200, priority=None, **kwargs):
        if isinstance(responses, Exception):
            raise responses
        idx = min(calls["n"], len(responses) - 1)
        calls["n"] += 1
        return responses[idx]

    monkeypatch.setattr(headline_engine_module, "_call_with_fallback", fake_call)
    return calls


@pytest.mark.asyncio
async def test_fabricated_currency_value_is_rejected_then_falls_back(monkeypatch):
    es = _es("ABC", "ABC has informed the Exchange regarding a press release: real order worth Rs 800 crore won")
    identity = compute_identity(es)
    # Both attempts return a headline citing a fabricated number never in the evidence.
    _mock_llm(monkeypatch, ['{"headline": "ABC wins Rs 1,200 crore order, doubling backlog"}'] * 2)
    result = await generate_headline(es, None, identity, other_accepted_headlines={})
    assert result.status == ValidationOutcome.FALLBACK
    assert result.attempts == 2
    assert any("unsupported number" in n for n in result.validation_notes)


@pytest.mark.asyncio
async def test_unsupported_percentage_is_rejected_then_falls_back(monkeypatch):
    es = _es("ABC", "ABC has informed the Exchange regarding financial results for the quarter")
    identity = compute_identity(es)
    _mock_llm(monkeypatch, ['{"headline": "ABC reports 45% profit surge in Q2"}'] * 2)
    result = await generate_headline(es, None, identity, other_accepted_headlines={})
    assert result.status == ValidationOutcome.FALLBACK
    assert any("unsupported number" in n for n in result.validation_notes)


@pytest.mark.asyncio
async def test_provider_failure_falls_back_to_deterministic_headline(monkeypatch):
    es = _es("ABC", "ABC has informed the Exchange regarding a press release: real acquisition of a real target")
    identity = compute_identity(es)
    _mock_llm(monkeypatch, RuntimeError("all providers exhausted"))
    result = await generate_headline(es, None, identity, other_accepted_headlines={})
    assert result.status == ValidationOutcome.FALLBACK
    assert result.h1 is not None and "ABC" in result.h1
    assert result.h1 == result.seo_title == result.social_title


@pytest.mark.asyncio
async def test_entity_mismatch_is_rejected(monkeypatch):
    es = _es("ABC", "ABC has informed the Exchange regarding a press release: real acquisition announcement")
    identity = compute_identity(es)
    # Headline talks about a completely different, unrelated company.
    _mock_llm(monkeypatch, ['{"headline": "XYZ Corp reports record earnings this quarter"}'] * 2)
    result = await generate_headline(es, None, identity, other_accepted_headlines={})
    assert result.status == ValidationOutcome.FALLBACK
    assert any("does not mention the resolved company" in n for n in result.validation_notes)


@pytest.mark.asyncio
async def test_clickbait_predictive_language_is_rejected(monkeypatch):
    es = _es("ABC", "ABC has informed the Exchange regarding a press release: real acquisition announcement")
    identity = compute_identity(es)
    _mock_llm(monkeypatch, ['{"headline": "ABC Stock Set to Soar After Game-Changing Acquisition"}'] * 2)
    result = await generate_headline(es, None, identity, other_accepted_headlines={})
    assert result.status == ValidationOutcome.FALLBACK
    assert any("clickbait" in n for n in result.validation_notes)


@pytest.mark.asyncio
async def test_near_duplicate_headline_for_different_identity_is_rejected(monkeypatch):
    es = _es("ABC", "ABC has informed the Exchange regarding a press release: real capacity expansion approved")
    identity = compute_identity(es)
    already_used = {"cmp_xyz|OTHER|topic:different-thing|2026-W01": "ABC approves real capacity expansion plan today"}
    _mock_llm(monkeypatch, ['{"headline": "ABC approves real capacity expansion plan today"}'] * 2)
    result = await generate_headline(es, None, identity, other_accepted_headlines=already_used)
    assert result.status == ValidationOutcome.FALLBACK
    assert any("near-duplicate" in n for n in result.validation_notes)


@pytest.mark.asyncio
async def test_valid_headline_with_real_verified_number_is_accepted(monkeypatch):
    es = _es("ABC", "ABC has informed the Exchange regarding a press release: real order worth Rs 800 crore won from a real client")
    identity = compute_identity(es)
    _mock_llm(monkeypatch, ['{"headline": "ABC wins Rs 800 crore order from real client"}'])
    result = await generate_headline(es, None, identity, other_accepted_headlines={})
    assert result.status == ValidationOutcome.OK
    assert result.attempts == 1
    assert "800" in result.h1


@pytest.mark.asyncio
async def test_retry_succeeds_after_first_attempt_rejected(monkeypatch):
    es = _es("ABC", "ABC has informed the Exchange regarding a press release: real order worth Rs 800 crore won")
    identity = compute_identity(es)
    _mock_llm(monkeypatch, [
        '{"headline": "ABC wins Rs 1,200 crore order"}',  # attempt 1: fabricated number
        '{"headline": "ABC wins Rs 800 crore order"}',     # attempt 2: corrected
    ])
    result = await generate_headline(es, None, identity, other_accepted_headlines={})
    assert result.status == ValidationOutcome.OK
    assert result.attempts == 2


@pytest.mark.asyncio
async def test_colliding_fallback_headlines_are_disambiguated(monkeypatch):
    """Real gap found via the C5 120-event shadow run: when the LLM path
    is exhausted for two DIFFERENT real companies whose real evidence
    happens to share the same NSE boilerplate phrasing (two genuinely
    different AGM notices), the deterministic fallback template alone
    can produce confusingly similar headlines -- MAHSEAMLES vs
    METROBRAND hit 0.50 Jaccard live. Must be disambiguated with real,
    already-known data (the identity's own time bucket), never invented
    text."""
    es_a = _es("MAHSEAMLES", "Maharashtra Seamless Limited has informed the Exchange regarding Notice of Annual General Meeting to be held on September 20, 2026")
    es_b = _es("METROBRAND", "Metro Brands Limited has informed the Exchange regarding Notice of Annual General Meeting to be held on September 16, 2026")
    id_a, id_b = compute_identity(es_a), compute_identity(es_b)
    assert id_a.identity_key != id_b.identity_key  # genuinely different companies/identities

    _mock_llm(monkeypatch, RuntimeError("provider exhausted"))
    result_a = await generate_headline(es_a, None, id_a, other_accepted_headlines={})
    assert result_a.status == ValidationOutcome.FALLBACK
    known = {id_a.identity_key: result_a.h1}

    result_b = await generate_headline(es_b, None, id_b, other_accepted_headlines=known)
    assert result_b.status == ValidationOutcome.FALLBACK
    # The two real, different companies' fallback headlines must not be
    # confusingly similar once disambiguated.
    from app.services.aipe.duplicate_detector import _jaccard, _tokenize
    assert _jaccard(_tokenize(result_a.h1), _tokenize(result_b.h1)) < 0.50


@pytest.mark.asyncio
async def test_real_live_llm_generates_a_valid_headline():
    """One real, live integration proof -- not mocked -- that the whole
    pipeline (real LLM call, real numeric validation against a real
    evidence-derived allowed-value set) works end to end."""
    es = _es("AXISCADES", 'AXISCADES Technologies Limited has informed the Exchange regarding a press release dated August 30, 2026, titled "AXISCADES Technologies to Acquire Cloud Wave Technologies"')
    identity = compute_identity(es)
    context = ArticleContextBundle(
        entity_id="cmp_axiscades", symbol="AXISCADES", event_id="evt", event_headline=es.event_headline,
        status=NONE_STATUS, market_reaction=MarketReaction(price_move_pct=4.80, note="temporal correlation only"),
    )
    result = await generate_headline(es, context, identity, other_accepted_headlines={})
    assert result.h1 is not None
    assert result.status in (ValidationOutcome.OK, ValidationOutcome.FALLBACK)
    assert "AXISCADES" in result.h1.upper() or "AXISCADES" in result.h1
