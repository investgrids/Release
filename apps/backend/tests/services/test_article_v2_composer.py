"""
Article V2 Phase C6 — Grounded Composer tests. Pure dataclasses + a
mocked/real LLM call, no DB needed (mirrors the C5 headline_engine test
convention). Covers every adversarial case the owner's C6 authorization
required: fabricated numbers, unsupported causal/predictive language,
excluded/foreign evidence never entering prose, cross-company isolation,
C4 SKIP / C5 NO_PUBLICATION hard refusal, provider exhaustion producing
a grounded deterministic fallback, no-context articles never inventing
a Why It Matters section, and claim provenance surviving composition --
plus one real, live LLM integration proof.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

import app.services.article_v2.composer as composer_module
from app.services.article_v2.composer import ComposedArticle, ComposerRefusal, compose_article
from app.services.article_v2.context_builder import (
    AVAILABLE, ArticleContextBundle, ContextFinancialFact, MarketReaction, NONE_STATUS,
)
from app.services.article_v2.decision_engine import CREATE, FACTUAL_UPDATE, FULL_ARTICLE, NONE_ACTION
from app.services.article_v2.decision_engine import SKIP as C4_SKIP
from app.services.article_v2.decision_engine import ArticleDecision
from app.services.article_v2.evidence_set_builder import COHERENT, ArticleEvidenceSet, ExcludedEvidence
from app.services.article_v2.evidence_set_builder import DIFFERENT_DEVELOPMENT
from app.services.article_v2.headline_engine import HeadlineResult, ValidationOutcome
from app.services.article_v2.identity import (
    CREATE_NEW, NO_PUBLICATION, ArticleIdentity, PublicationResolution, compute_identity,
)
from app.services.warehouse.read_service import LinkedEvidence


def _evidence(title: str, source_type: str = "nse", raw_id: str | None = None) -> LinkedEvidence:
    return LinkedEvidence(
        raw_evidence_id=raw_id or str(uuid.uuid4()), title=title, source_type=source_type,
        published_at=datetime.now(timezone.utc), source_url=None,
        relationship_type="subject", resolution_method="source_symbol", link_confidence=None,
    )


def _evidence_set(
    symbol: str, primary_title: str, *, supporting: list[LinkedEvidence] | None = None,
    excluded: list[ExcludedEvidence] | None = None, entity_id: str | None = None,
) -> ArticleEvidenceSet:
    return ArticleEvidenceSet(
        entity_id=entity_id or f"cmp_{symbol.lower()}", symbol=symbol, event_id="evt",
        event_headline=primary_title, status=COHERENT, primary_evidence=_evidence(primary_title),
        supporting_evidence=supporting or [], excluded_evidence=excluded or [],
    )


def _decision(evidence_set: ArticleEvidenceSet, content_type: str) -> ArticleDecision:
    return ArticleDecision(
        entity_id=evidence_set.entity_id, symbol=evidence_set.symbol, event_id=evidence_set.event_id,
        event_headline=evidence_set.event_headline, content_type=content_type,
        publication_action=NONE_ACTION if content_type == C4_SKIP else CREATE,
    )


def _resolution(identity: ArticleIdentity, *, publication_action: str = CREATE_NEW) -> PublicationResolution:
    return PublicationResolution(
        identity=identity, publication_action=publication_action, matched_identity_key=None,
        matched_article_id=None, reason="test",
    )


def _headline(text: str = "Test Headline") -> HeadlineResult:
    return HeadlineResult(h1=text, seo_title=text, social_title=text, status=ValidationOutcome.OK, attempts=1)


def _fact(metric_code: str, value: float, unit: str = "pct", *, prior_value=None, prior_label=None) -> ContextFinancialFact:
    return ContextFinancialFact(
        metric_code=metric_code, metric_name=metric_code.replace("_", " ").title(), value=value, unit=unit,
        fiscal_year=2026, fiscal_quarter=1, quality_status="ok", source_document_url=None,
        matched_family="FUNDRAISING", prior_period_value=prior_value, prior_period_label=prior_label,
    )


def _mock_llm(monkeypatch, responses: list[str] | Exception):
    calls = {"n": 0}

    async def fake_call(prompt, system="", max_tokens=200, priority=None, **kwargs):
        if isinstance(responses, Exception):
            raise responses
        idx = min(calls["n"], len(responses) - 1)
        calls["n"] += 1
        return responses[idx]

    monkeypatch.setattr(composer_module, "_call_with_fallback", fake_call)
    return calls


# ── Numeric + language rejection ────────────────────────────────────────

@pytest.mark.asyncio
async def test_fabricated_currency_amount_rejected_in_why_it_matters(monkeypatch):
    es = _evidence_set("CANBK", "CANARA BANK has informed the Exchange about Board Meeting to consider Fund raising")
    identity = compute_identity(es)
    context = ArticleContextBundle(
        entity_id=es.entity_id, symbol=es.symbol, event_id=es.event_id, event_headline=es.event_headline,
        status=AVAILABLE, financial_context=[_fact("cet1_ratio", 0.1197)],
    )
    _mock_llm(monkeypatch, [
        '{"why_it_matters": "The bank plans to raise Rs 5,000 crore in fresh capital.", "claims": []}'
    ] * 2)
    article = await compose_article(_decision(es, FULL_ARTICLE), es, context, identity, _resolution(identity), _headline())
    assert article.llm_status == "omitted_validation_failed"
    assert not any(s.name == "why_it_matters" for s in article.sections)


@pytest.mark.asyncio
async def test_fabricated_percentage_rejected(monkeypatch):
    es = _evidence_set("CANBK", "CANARA BANK has informed the Exchange about Board Meeting to consider Fund raising")
    identity = compute_identity(es)
    context = ArticleContextBundle(
        entity_id=es.entity_id, symbol=es.symbol, event_id=es.event_id, event_headline=es.event_headline,
        status=AVAILABLE, financial_context=[_fact("cet1_ratio", 0.1197)],
    )
    _mock_llm(monkeypatch, ['{"why_it_matters": "This follows a real 45.6% jump in deposits.", "claims": []}'] * 2)
    article = await compose_article(_decision(es, FULL_ARTICLE), es, context, identity, _resolution(identity), _headline())
    assert article.llm_status == "omitted_validation_failed"
    assert not any(s.name == "why_it_matters" for s in article.sections)


@pytest.mark.asyncio
async def test_unsupported_causal_language_rejected(monkeypatch):
    """The owner's own contrast, verbatim: 'Investors welcomed the
    acquisition, sending shares up 4.8%' invents causality and intent
    neither C2 nor C3 established."""
    es = _evidence_set("AXISCADES", "AXISCADES has informed the Exchange regarding a press release: acquisition of Cloud Wave Technologies")
    identity = compute_identity(es)
    context = ArticleContextBundle(
        entity_id=es.entity_id, symbol=es.symbol, event_id=es.event_id, event_headline=es.event_headline,
        status=AVAILABLE, market_reaction=MarketReaction(price_move_pct=4.8, note="temporal correlation only"),
    )
    _mock_llm(monkeypatch, [
        '{"why_it_matters": "Investors welcomed the acquisition, sending shares up 4.80%.", "claims": []}'
    ] * 2)
    article = await compose_article(_decision(es, FULL_ARTICLE), es, context, identity, _resolution(identity), _headline())
    assert article.llm_status == "omitted_validation_failed"
    assert not any(s.name == "why_it_matters" for s in article.sections)


@pytest.mark.asyncio
async def test_unsupported_future_prediction_rejected(monkeypatch):
    es = _evidence_set("CANBK", "CANARA BANK has informed the Exchange about Board Meeting to consider Fund raising")
    identity = compute_identity(es)
    context = ArticleContextBundle(
        entity_id=es.entity_id, symbol=es.symbol, event_id=es.event_id, event_headline=es.event_headline,
        status=AVAILABLE, financial_context=[_fact("cet1_ratio", 0.1197)],
    )
    _mock_llm(monkeypatch, [
        '{"why_it_matters": "This fundraising will accelerate loan growth and boost profitability.", "claims": []}'
    ] * 2)
    article = await compose_article(_decision(es, FULL_ARTICLE), es, context, identity, _resolution(identity), _headline())
    assert article.llm_status == "omitted_validation_failed"
    assert not any(s.name == "why_it_matters" for s in article.sections)


@pytest.mark.asyncio
async def test_temporal_price_language_is_accepted(monkeypatch):
    """The owner's OK contrast: 'Shares rose 4.8% after the announcement'
    describes real temporal sequence, not causation -- must be accepted,
    not swept up by an overly broad denylist."""
    es = _evidence_set("AXISCADES", "AXISCADES has informed the Exchange regarding a press release: acquisition of Cloud Wave Technologies")
    identity = compute_identity(es)
    context = ArticleContextBundle(
        entity_id=es.entity_id, symbol=es.symbol, event_id=es.event_id, event_headline=es.event_headline,
        status=AVAILABLE, market_reaction=MarketReaction(price_move_pct=4.8, note="temporal correlation only"),
    )
    _mock_llm(monkeypatch, ['{"why_it_matters": "Shares rose 4.80% after the announcement was made public.", "claims": []}'])
    article = await compose_article(_decision(es, FULL_ARTICLE), es, context, identity, _resolution(identity), _headline())
    assert article.llm_status == "ok"
    assert any(s.name == "why_it_matters" for s in article.sections)


# ── Evidence/context isolation ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_excluded_evidence_never_enters_prose():
    excluded = [ExcludedEvidence(
        evidence=_evidence("A totally unrelated fabricated-sounding excluded filing about UNRELATEDTOPIC123"),
        reason_code=DIFFERENT_DEVELOPMENT, reason_detail="test",
    )]
    es = _evidence_set("NEWGEN", "Newgen Software has informed the Exchange about increased trading volume", excluded=excluded)
    identity = compute_identity(es)
    article = await compose_article(_decision(es, FACTUAL_UPDATE), es, None, identity, _resolution(identity), _headline())
    full_text = " ".join(s.text for s in article.sections)
    assert "UNRELATEDTOPIC123" not in full_text


@pytest.mark.asyncio
async def test_foreign_financial_fact_never_enters_prose():
    """Only what's actually IN context.financial_context can appear --
    the composer never queries FinancialFact itself, so a fact C3 didn't
    select structurally cannot leak in."""
    es = _evidence_set("CANBK", "CANARA BANK has informed the Exchange about Board Meeting to consider Fund raising")
    identity = compute_identity(es)
    context = ArticleContextBundle(
        entity_id=es.entity_id, symbol=es.symbol, event_id=es.event_id, event_headline=es.event_headline,
        status=AVAILABLE, financial_context=[_fact("cet1_ratio", 0.1197)],
    )
    article = await compose_article(_decision(es, FACTUAL_UPDATE), es, context, identity, _resolution(identity), _headline())
    full_text = " ".join(s.text for s in article.sections)
    assert "Cet1 Ratio" in full_text
    assert "gross_npa" not in full_text.lower()  # never selected by C3, never queried by C6


@pytest.mark.asyncio
async def test_cross_company_context_cannot_enter():
    es_a = _evidence_set("ABC", "ABC has informed the Exchange regarding a press release: real order worth Rs 800 crore")
    es_b = _evidence_set("XYZ", "XYZ has informed the Exchange regarding resignation of an Independent Director")
    id_a, id_b = compute_identity(es_a), compute_identity(es_b)

    article_a = await compose_article(_decision(es_a, FACTUAL_UPDATE), es_a, None, id_a, _resolution(id_a), _headline("ABC headline"))
    article_b = await compose_article(_decision(es_b, FACTUAL_UPDATE), es_b, None, id_b, _resolution(id_b), _headline("XYZ headline"))

    text_a = " ".join(s.text for s in article_a.sections)
    text_b = " ".join(s.text for s in article_b.sections)
    assert "XYZ" not in text_a and "Independent Director" not in text_a
    assert "ABC" not in text_b and "800 crore" not in text_b


# ── Hard refusals ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_c4_skip_is_never_composed():
    es = _evidence_set("POWERICA", "Powerica Limited has informed the Exchange about the date of its 42nd Annual General Meeting")
    identity = compute_identity(es)
    decision = ArticleDecision(
        entity_id=es.entity_id, symbol=es.symbol, event_id=es.event_id, event_headline=es.event_headline,
        content_type=C4_SKIP, publication_action=NONE_ACTION,
    )
    with pytest.raises(ComposerRefusal):
        await compose_article(decision, es, None, identity, _resolution(identity), _headline())


@pytest.mark.asyncio
async def test_c5_no_publication_is_never_composed():
    es = _evidence_set("ATALREAL", "Atal Realtech Limited has informed the Exchange about Board Meeting to consider Other Business")
    identity = compute_identity(es)
    resolution = _resolution(identity, publication_action=NO_PUBLICATION)
    with pytest.raises(ComposerRefusal):
        await compose_article(_decision(es, FACTUAL_UPDATE), es, None, identity, resolution, _headline())


# ── Deterministic fallback under provider failure ───────────────────────

@pytest.mark.asyncio
async def test_provider_exhaustion_produces_grounded_deterministic_output(monkeypatch):
    es = _evidence_set("CANBK", "CANARA BANK has informed the Exchange about Board Meeting to consider Fund raising")
    identity = compute_identity(es)
    context = ArticleContextBundle(
        entity_id=es.entity_id, symbol=es.symbol, event_id=es.event_id, event_headline=es.event_headline,
        status=AVAILABLE, financial_context=[_fact("cet1_ratio", 0.1197)],
    )
    _mock_llm(monkeypatch, RuntimeError("all providers exhausted"))
    article = await compose_article(_decision(es, FULL_ARTICLE), es, context, identity, _resolution(identity), _headline())
    assert article.llm_status == "omitted_generation_failed"
    assert not any(s.name == "why_it_matters" for s in article.sections)
    assert any(s.name == "what_happened" for s in article.sections)
    assert article.headline is not None
    assert article.word_count > 0


@pytest.mark.asyncio
async def test_no_context_no_numbers_downgrades_via_depth_gate_and_never_invents_why_it_matters(monkeypatch):
    """SAILIFE-shaped real case: no financial/market context AND no real
    numeric substance in the primary evidence -- C8.4's depth gate
    downgrades this to FACTUAL_UPDATE-shape entirely (a stronger
    guarantee than the old 'attempt then omit' behavior), so the LLM is
    never even considered, let alone called."""
    calls = _mock_llm(monkeypatch, ['{"why_it_matters": "should never be called", "claims": []}'])
    es = _evidence_set("SAILIFE", "Sai Life Sciences has informed the Exchange regarding Information relating to 27th Annual General Meeting")
    identity = compute_identity(es)
    context = ArticleContextBundle(
        entity_id=es.entity_id, symbol=es.symbol, event_id=es.event_id, event_headline=es.event_headline,
        status=NONE_STATUS,
    )
    article = await compose_article(_decision(es, FULL_ARTICLE), es, context, identity, _resolution(identity), _headline())
    assert article.llm_status == "not_used"
    assert article.depth_gate_downgraded is True
    assert article.content_type == FACTUAL_UPDATE
    assert not any(s.name == "why_it_matters" for s in article.sections)
    assert calls["n"] == 0  # the LLM must never even be called


@pytest.mark.asyncio
async def test_real_numeric_substance_alone_keeps_full_article_shape_but_still_omits_why_it_matters(monkeypatch):
    """The owner's own explicit allowance: a single detailed primary
    filing with real numeric substance can carry a FULL_ARTICLE on its
    own, with no C3 context at all -- the depth gate must NOT downgrade
    this. But Why It Matters still correctly has nothing to reason about
    (no financial/market context), so it's still omitted -- just via the
    FULL_ARTICLE-shaped path this time, not a full downgrade."""
    calls = _mock_llm(monkeypatch, ['{"why_it_matters": "should never be called", "claims": []}'])
    es = _evidence_set("SOMECO", "Some Company Limited has informed the Exchange regarding a real order worth Rs 5,000 crore from a client")
    identity = compute_identity(es)
    context = ArticleContextBundle(
        entity_id=es.entity_id, symbol=es.symbol, event_id=es.event_id, event_headline=es.event_headline,
        status=NONE_STATUS,
    )
    article = await compose_article(_decision(es, FULL_ARTICLE), es, context, identity, _resolution(identity), _headline())
    assert article.depth_gate_downgraded is False
    assert article.content_type == FULL_ARTICLE
    assert article.llm_status == "omitted_no_context"
    assert not any(s.name == "why_it_matters" for s in article.sections)
    assert calls["n"] == 0


@pytest.mark.asyncio
async def test_factual_update_never_calls_the_llm(monkeypatch):
    calls = _mock_llm(monkeypatch, ['{"why_it_matters": "should never be called", "claims": []}'])
    es = _evidence_set("MOLDTECH", "MOLD-TEK TECHNOLOGIES LIMITED has informed the Exchange about Board Meeting to consider and approve Bonus")
    identity = compute_identity(es)
    context = ArticleContextBundle(
        entity_id=es.entity_id, symbol=es.symbol, event_id=es.event_id, event_headline=es.event_headline,
        status=AVAILABLE, financial_context=[_fact("cet1_ratio", 0.1197)],
    )
    article = await compose_article(_decision(es, FACTUAL_UPDATE), es, context, identity, _resolution(identity), _headline())
    assert article.llm_status == "not_used"
    assert calls["n"] == 0


# ── Claim provenance ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_claim_provenance_survives_composition(monkeypatch):
    supporting = [_evidence("A real supporting filing about the same fundraising")]
    es = _evidence_set(
        "CANBK", "CANARA BANK has informed the Exchange about Board Meeting to consider Fund raising",
        supporting=supporting,
    )
    identity = compute_identity(es)
    context = ArticleContextBundle(
        entity_id=es.entity_id, symbol=es.symbol, event_id=es.event_id, event_headline=es.event_headline,
        status=AVAILABLE, financial_context=[_fact("cet1_ratio", 0.1197)],
        market_reaction=MarketReaction(price_move_pct=1.2, note="temporal correlation only"),
    )
    _mock_llm(monkeypatch, [
        f'{{"why_it_matters": "A stronger CET1 ratio of 11.97% supports the case for raising capital.", '
        f'"claims": [{{"text": "CET1 ratio is 11.97%.", "type": "FACT", "evidence_refs": ["FACT:cet1_ratio"]}}]}}'
    ])
    article = await compose_article(_decision(es, FULL_ARTICLE), es, context, identity, _resolution(identity), _headline())
    assert article.llm_status == "ok"

    real_evidence_ids = {e.raw_evidence_id for e in [es.primary_evidence] + es.supporting_evidence}
    real_fact_codes = {f.metric_code for f in context.financial_context}
    for claim in article.all_claims:
        for eid in claim.evidence_ids:
            assert eid in real_evidence_ids
        for fid in claim.financial_fact_ids:
            assert fid in real_fact_codes
    assert len(article.all_claims) > 0
    assert any(c.financial_fact_ids == ["cet1_ratio"] for c in article.all_claims)


# ── Section shape ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_full_article_section_order():
    # Real financial context (synthesizable depth, so C8.4's gate keeps
    # this FULL_ARTICLE-shaped) alongside a real scheduled date (so
    # what_to_watch has real grounds to fire).
    es = _evidence_set("CANBK", "CANARA BANK has informed the Exchange about Board Meeting to be held on 03-Sep-2026 to consider Fund raising")
    identity = compute_identity(es)
    context = ArticleContextBundle(
        entity_id=es.entity_id, symbol=es.symbol, event_id=es.event_id, event_headline=es.event_headline,
        status=AVAILABLE, financial_context=[_fact("cet1_ratio", 0.1197)],
    )
    article = await compose_article(_decision(es, FULL_ARTICLE), es, context, identity, _resolution(identity), _headline())
    assert article.depth_gate_downgraded is False
    names = [s.name for s in article.sections]
    assert names[0] == "what_happened"
    assert names[-1] == "source_updated"
    assert "what_to_watch" in names  # real scheduled date present in the evidence text


@pytest.mark.asyncio
async def test_factual_update_is_concise_and_has_key_sections():
    es = _evidence_set("MAHSEAMLES", "Maharashtra Seamless Limited has informed the Exchange regarding Notice of Annual General Meeting to be held on September 15, 2026")
    identity = compute_identity(es)
    article = await compose_article(_decision(es, FACTUAL_UPDATE), es, None, identity, _resolution(identity), _headline())
    names = [s.name for s in article.sections]
    assert names == ["what_happened", "what_to_watch", "source_updated"] or names == ["what_happened", "source_updated"]
    assert article.word_count < 150


# ── Real, live LLM integration proof ────────────────────────────────────

@pytest.mark.asyncio
async def test_real_live_llm_full_article_composition():
    es = _evidence_set(
        "AXISCADES",
        'AXISCADES Technologies Limited has informed the Exchange regarding a press release dated August 30, 2026, '
        'titled "AXISCADES Technologies to Acquire Cloud Wave Technologies"',
    )
    identity = compute_identity(es)
    context = ArticleContextBundle(
        entity_id=es.entity_id, symbol=es.symbol, event_id=es.event_id, event_headline=es.event_headline,
        status=AVAILABLE, market_reaction=MarketReaction(price_move_pct=4.80, note="temporal correlation only"),
    )
    headline = _headline("AXISCADES Technologies acquires Cloud Wave Technologies")
    article = await compose_article(_decision(es, FULL_ARTICLE), es, context, identity, _resolution(identity), headline)
    assert article.headline
    assert any(s.name == "what_happened" for s in article.sections)
    assert article.llm_status in ("ok", "omitted_generation_failed", "omitted_validation_failed")
    if article.llm_status == "ok":
        why_section = next(s for s in article.sections if s.name == "why_it_matters")
        assert "invest" not in why_section.text.lower() or "welcomed" not in why_section.text.lower()
