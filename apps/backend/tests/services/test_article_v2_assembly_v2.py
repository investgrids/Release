"""
Article V2 Assembly V2 — A1/A2/A3 tests (owner design, 2026-09-17).

Motivated by a real, non-production revalidation of the (still
undeployed) Deep Filing Evidence lineage against 4 real specimens
(ZODIAC, PRIMO, JUNIPER, MUTHOOTFIN): the evidence layer was proven to
supply real, provenance-backed TransactionFacts, but the assembly layer
didn't yet know they existed. JUNIPER was the clearest case -- a real,
authorized Rs 248 crore cash acquisition fact existed, yet the reader
got the headline "JUNIPER Limited — Acquisition" and a bare filing-title
restatement in What Happened.

Three bounded fixes, tested here per the owner's own instruction: test
fact inclusion, provenance, omission, and authorization -- never exact
prose strings.

  A1 -- What Happened gains one additional claim per real, POPULATED
        TransactionFact (composer.py::_compose_what_happened), each
        independently CD3-authorizable, and cleanly omits any field
        that was never extracted.

  A2 -- The deterministic headline fallback (the one guarantee a
        provider failure leaves behind) is now TransactionFact-aware
        (headline_engine.py::_build_deterministic_headline /
        _build_transaction_fact_topic), and the primary LLM path's
        prompt + numeric allow-list also include real transaction
        facts so an LLM-authored headline citing one isn't wrongly
        rejected as an unsupported number.

  A3 -- _should_attempt_why_it_matters() becomes eligible on
        transaction_facts alone, and a Why-It-Matters claim that cites
        a real transaction fact (`[FACT:tf_<field_code>]`) now carries
        a real transaction_fact proof dict so CD3 can actually
        authorize it -- eligibility is never treated as permission to
        invent significance; that boundary is CD3's job.

No DB needed -- VerifiedTransactionFact is a plain dataclass, and
compose_article's own established test convention (see
test_article_v2_composer.py) never requires the DB layer to prove
composition/authorization behavior.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

import app.services.article_v2.composer as composer_module
import app.services.article_v2.headline_engine as headline_engine_module
from app.db.models.transaction_fact import (
    CONSIDERATION_AMOUNT, CONSIDERATION_TYPE, STAKE_PERCENTAGE, TARGET_ENTITY_NAME,
)
from app.services.article_v2.claim_translation import TranslationContext, authorize_composed_claim
from app.services.article_v2.composer import compose_article
from app.services.article_v2.context_builder import AVAILABLE, ArticleContextBundle, NONE_STATUS
from app.services.article_v2.decision_engine import CREATE, FULL_ARTICLE, NONE_ACTION, ArticleDecision
from app.services.article_v2.evidence_set_builder import COHERENT, ArticleEvidenceSet
from app.services.article_v2.headline_engine import (
    HeadlineResult, ValidationOutcome, _build_deterministic_headline, generate_headline,
)
from app.services.article_v2.identity import CREATE_NEW, ArticleIdentity, PublicationResolution, compute_identity
from app.services.claim_authorization import Capability, Strength
from app.services.warehouse.read_service import LinkedEvidence, VerifiedTransactionFact


# ── Shared fixtures (mirrors test_article_v2_composer.py /
#    test_article_v2_headline_engine.py's own established convention) ──

def _evidence(title: str, raw_id: str | None = None) -> LinkedEvidence:
    return LinkedEvidence(
        raw_evidence_id=raw_id or str(uuid.uuid4()), title=title, source_type="nse",
        published_at=datetime.now(timezone.utc), source_url=None,
        relationship_type="subject", resolution_method="source_symbol", link_confidence=None,
    )


def _evidence_set(symbol: str, title: str, raw_id: str | None = None) -> ArticleEvidenceSet:
    return ArticleEvidenceSet(
        entity_id=f"cmp_{symbol.lower()}", symbol=symbol, event_id="evt", event_headline=title,
        status=COHERENT, primary_evidence=_evidence(title, raw_id), supporting_evidence=[],
        company_name=f"{symbol} Limited",
    )


def _decision(evidence_set: ArticleEvidenceSet, content_type: str = FULL_ARTICLE) -> ArticleDecision:
    return ArticleDecision(
        entity_id=evidence_set.entity_id, symbol=evidence_set.symbol, event_id=evidence_set.event_id,
        event_headline=evidence_set.event_headline, content_type=content_type, publication_action=CREATE,
    )


def _resolution(identity: ArticleIdentity) -> PublicationResolution:
    return PublicationResolution(
        identity=identity, publication_action=CREATE_NEW, matched_identity_key=None, matched_article_id=None, reason="test",
    )


def _headline(text: str = "Test Headline") -> HeadlineResult:
    return HeadlineResult(h1=text, seo_title=text, social_title=text, status=ValidationOutcome.OK, attempts=1)


def _mock_llm(monkeypatch, module, responses: list[str] | Exception):
    calls = {"n": 0}

    async def fake_call(prompt, system="", max_tokens=200, priority=None, **kwargs):
        if isinstance(responses, Exception):
            raise responses
        idx = min(calls["n"], len(responses) - 1)
        calls["n"] += 1
        return responses[idx]

    monkeypatch.setattr(module, "_call_with_fallback", fake_call)
    return calls


def _tf(
    field_code: str, *, raw_evidence_id: str, value_text: str | None = None, value_numeric: float | None = None,
    unit: str | None = None, source_document_id: str = "doc-1", page_number: int = 2,
    source_span_text: str = "real source span",
) -> VerifiedTransactionFact:
    field_names = {
        TARGET_ENTITY_NAME: "Name of the target entity",
        STAKE_PERCENTAGE: "Percentage of shareholding / control acquired",
        CONSIDERATION_TYPE: "Consideration -- cash / share swap / other",
        CONSIDERATION_AMOUNT: "Cost of acquisition / consideration amount",
    }
    return VerifiedTransactionFact(
        field_code=field_code, field_name=field_names[field_code], value_text=value_text, value_numeric=value_numeric,
        unit=unit, raw_evidence_id=raw_evidence_id, source_document_id=source_document_id, page_number=page_number,
        source_span_text=source_span_text, extraction_method="sebi_reg30_annexure_table", extraction_method_version="1.1",
    )


# ── A1: fact-aware "What Happened" ──────────────────────────────────────

@pytest.mark.asyncio
async def test_what_happened_gains_one_claim_per_real_transaction_fact():
    es = _evidence_set("JUNIPER", "Juniper Hotels Limited has informed the Exchange about Acquisition")
    identity = compute_identity(es)
    raw_id = es.primary_evidence.raw_evidence_id
    context = ArticleContextBundle(
        entity_id=es.entity_id, symbol=es.symbol, event_id=es.event_id, event_headline=es.event_headline,
        status=AVAILABLE,
        transaction_facts=[
            _tf(CONSIDERATION_TYPE, raw_evidence_id=raw_id, value_text="CASH"),
            _tf(CONSIDERATION_AMOUNT, raw_evidence_id=raw_id, value_numeric=2_480_000_000.0, unit="inr"),
        ],
    )
    article = await compose_article(_decision(es), es, context, identity, _resolution(identity), _headline())
    what_happened = next(s for s in article.sections if s.name == "what_happened")

    # Base restatement claim always present, unconditionally.
    assert len(what_happened.claims) == 3

    tf_claims = [c for c in what_happened.claims if c.transaction_fact]
    assert len(tf_claims) == 2
    field_codes = {c.transaction_fact["field_code"] for c in tf_claims}
    assert field_codes == {CONSIDERATION_TYPE, CONSIDERATION_AMOUNT}

    # The real Rs 248 crore fact must actually be readable in the composed
    # text -- the exact JUNIPER revalidation gap this fixes.
    amount_claim = next(c for c in tf_claims if c.transaction_fact["field_code"] == CONSIDERATION_AMOUNT)
    assert "248" in amount_claim.text and "crore" in amount_claim.text.lower()

    # Never a field that was NOT extracted -- no target/stake clause exists.
    assert not any(c.transaction_fact and c.transaction_fact["field_code"] in (TARGET_ENTITY_NAME, STAKE_PERCENTAGE) for c in what_happened.claims)


@pytest.mark.asyncio
async def test_what_happened_unchanged_when_no_transaction_facts_exist():
    """Every pre-A1 candidate (zero TransactionFacts) must get EXACTLY
    the prior behavior -- a single base claim, no transaction_fact key
    ever present."""
    es = _evidence_set("SAILIFE", "Sai Life Sciences has informed the Exchange regarding Information relating to 27th Annual General Meeting")
    identity = compute_identity(es)
    context = ArticleContextBundle(
        entity_id=es.entity_id, symbol=es.symbol, event_id=es.event_id, event_headline=es.event_headline,
        status=NONE_STATUS,
    )
    article = await compose_article(_decision(es), es, context, identity, _resolution(identity), _headline())
    what_happened = next(s for s in article.sections if s.name == "what_happened")
    assert len(what_happened.claims) == 1
    assert what_happened.claims[0].transaction_fact is None


@pytest.mark.asyncio
async def test_what_happened_transaction_fact_claims_authorize_via_cd3():
    """Each per-fact What Happened claim must independently survive CD3
    -- the same real capability an evidence_ids-backed claim gets, never
    a bypass of authorization just because it came from What Happened
    instead of Key Facts."""
    es = _evidence_set("ZODIAC", "Zodiac Energy Limited has informed the Exchange about Acquisition-Incorporation of Wholly Owned Subsidiary")
    identity = compute_identity(es)
    raw_id = es.primary_evidence.raw_evidence_id
    context = ArticleContextBundle(
        entity_id=es.entity_id, symbol=es.symbol, event_id=es.event_id, event_headline=es.event_headline,
        status=AVAILABLE,
        transaction_facts=[_tf(STAKE_PERCENTAGE, raw_evidence_id=raw_id, value_numeric=100.0, unit="pct")],
    )
    article = await compose_article(_decision(es), es, context, identity, _resolution(identity), _headline())
    what_happened = next(s for s in article.sections if s.name == "what_happened")
    tf_claim = next(c for c in what_happened.claims if c.transaction_fact)
    authorized = authorize_composed_claim(tf_claim, TranslationContext())
    assert authorized.capability == Capability.HISTORICAL_DESCRIPTION
    assert authorized.strength == Strength.AUTHORIZED


# ── A2: fact-aware deterministic headline fallback ──────────────────────

def _juniper_context(raw_id: str) -> ArticleContextBundle:
    return ArticleContextBundle(
        entity_id="cmp_juniper", symbol="JUNIPER", event_id="evt", event_headline="",
        status=AVAILABLE,
        transaction_facts=[
            _tf(CONSIDERATION_TYPE, raw_evidence_id=raw_id, value_text="CASH"),
            _tf(CONSIDERATION_AMOUNT, raw_evidence_id=raw_id, value_numeric=2_480_000_000.0, unit="inr"),
        ],
    )


def test_deterministic_fallback_surfaces_the_real_consideration_amount_not_a_bare_generic_word():
    """The direct JUNIPER regression check: the real revalidation showed
    a real, authorized Rs 248 crore fact existing while the deterministic
    fallback still produced the generic, uninformative "— Acquisition".
    This must no longer happen once a real consideration amount exists."""
    es = _evidence_set("JUNIPER", "Juniper Hotels Limited has informed the Exchange about Acquisition")
    identity = compute_identity(es)
    context = _juniper_context(es.primary_evidence.raw_evidence_id)
    headline = _build_deterministic_headline(es, identity, context)
    assert "248" in headline and "crore" in headline.lower()
    assert not headline.rstrip().endswith("— Acquisition")


def test_deterministic_fallback_with_no_transaction_facts_is_unchanged():
    """Zero TransactionFacts (the overwhelming majority of candidates,
    and every pre-A2 candidate) must produce EXACTLY the prior,
    title-derived fallback -- A2 must never regress the existing,
    already-shipped behavior."""
    es = _evidence_set("JUNIPER", "Juniper Hotels Limited has informed the Exchange about Acquisition")
    identity = compute_identity(es)
    with_context = _build_deterministic_headline(es, identity, None)
    without_context_arg = _build_deterministic_headline(es, identity)
    assert with_context == without_context_arg == "JUNIPER Limited — Acquisition"


def test_deterministic_fallback_omits_unextracted_fields():
    """PRIMO-shaped real case: target + stake are real, consideration was
    genuinely never found. The fallback must use only what was actually
    extracted -- never invent or imply a consideration."""
    es = _evidence_set("PRIMO", "Primo Chemicals Limited has informed the Exchange regarding acquisition of Balance 51% Equity Stake in Flow Tech Chemicals Private Limited.")
    identity = compute_identity(es)
    raw_id = es.primary_evidence.raw_evidence_id
    context = ArticleContextBundle(
        entity_id=es.entity_id, symbol=es.symbol, event_id=es.event_id, event_headline=es.event_headline,
        status=AVAILABLE,
        transaction_facts=[
            _tf(TARGET_ENTITY_NAME, raw_evidence_id=raw_id, value_text="Flow Tech Chemicals Private Limited"),
            _tf(STAKE_PERCENTAGE, raw_evidence_id=raw_id, value_numeric=51.0, unit="pct"),
        ],
    )
    headline = _build_deterministic_headline(es, identity, context)
    assert "51%" in headline
    assert "Flow Tech Chemicals Private Limited" in headline
    assert "cash" not in headline.lower() and "swap" not in headline.lower()


def test_deterministic_fallback_never_exceeds_topic_length_budget_even_with_a_long_target_name():
    """A pathologically long real target name + every other field
    present must still respect the shared topic length budget -- via
    dropping to a shorter real combination, never a mid-clause word cut
    that would misrepresent a fact as something shorter than it is."""
    es = _evidence_set("LONGCO", "Long Company Limited has informed the Exchange about Acquisition")
    identity = compute_identity(es)
    raw_id = es.primary_evidence.raw_evidence_id
    long_target = "A Genuinely Very Long Private Limited Target Entity Name That Goes On For Quite a While Indeed Private Limited"
    context = ArticleContextBundle(
        entity_id=es.entity_id, symbol=es.symbol, event_id=es.event_id, event_headline=es.event_headline,
        status=AVAILABLE,
        transaction_facts=[
            _tf(TARGET_ENTITY_NAME, raw_evidence_id=raw_id, value_text=long_target),
            _tf(STAKE_PERCENTAGE, raw_evidence_id=raw_id, value_numeric=100.0, unit="pct"),
            _tf(CONSIDERATION_TYPE, raw_evidence_id=raw_id, value_text="CASH"),
            _tf(CONSIDERATION_AMOUNT, raw_evidence_id=raw_id, value_numeric=2_480_000_000.0, unit="inr"),
        ],
    )
    headline = _build_deterministic_headline(es, identity, context)
    assert len(headline) <= 200  # the function's own hard cap
    assert "Acquisition" in headline  # never collapses to nothing


@pytest.mark.asyncio
async def test_llm_headline_citing_a_real_transaction_fact_is_not_wrongly_rejected(monkeypatch):
    """A2's numeric allow-list extension: an LLM-authored headline citing
    the real, already-authorized Rs 248 crore figure must pass numeric
    validation, not be treated as a fabricated number just because it
    came from a TransactionFact rather than a FinancialFact."""
    es = _evidence_set("JUNIPER", "Juniper Hotels Limited has informed the Exchange about Acquisition")
    identity = compute_identity(es)
    context = _juniper_context(es.primary_evidence.raw_evidence_id)
    _mock_llm(monkeypatch, headline_engine_module, ['{"headline": "Juniper Hotels acquires a hotel asset for Rs 248 crore in cash"}'])
    result = await generate_headline(es, context, identity, other_accepted_headlines={})
    assert result.status == ValidationOutcome.OK
    assert result.h1 == "Juniper Hotels acquires a hotel asset for Rs 248 crore in cash"


@pytest.mark.asyncio
async def test_llm_headline_citing_a_fabricated_amount_is_still_rejected_despite_real_transaction_facts(monkeypatch):
    """The A2 allow-list extension must not become a blanket pass -- a
    number that does NOT match any real transaction fact (or any other
    real allowed value) must still be rejected exactly as before."""
    es = _evidence_set("JUNIPER", "Juniper Hotels Limited has informed the Exchange about Acquisition")
    identity = compute_identity(es)
    context = _juniper_context(es.primary_evidence.raw_evidence_id)
    _mock_llm(monkeypatch, headline_engine_module, ['{"headline": "Juniper Hotels acquires a hotel asset for Rs 900 crore in cash"}'] * 2)
    result = await generate_headline(es, context, identity, other_accepted_headlines={})
    assert result.status == ValidationOutcome.FALLBACK
    assert any("unsupported number" in n for n in result.validation_notes)


# ── A3: transaction-aware Why It Matters eligibility + authorization ────

@pytest.mark.asyncio
async def test_why_it_matters_citing_a_real_transaction_fact_number_passes_numeric_validation(monkeypatch):
    """The exact gap a real live revalidation run surfaced: the LLM
    correctly wrote a Why It Matters sentence citing ZODIAC's real 100%
    stake and Rs 1.00 lakh consideration, and composer.py's own numeric
    validator rejected both as "unsupported" because
    build_allowed_values()'s financial_context path never learns about
    TransactionFacts. Unlike the other A3 tests in this file (which use
    a placeholder "why_it_matters" body precisely to isolate ref-parsing
    from numeric validation), this one uses REAL prose containing REAL
    transaction-fact numbers -- it must reach status "ok", never retry/
    omit on a false "unsupported number"."""
    calls = _mock_llm(monkeypatch, composer_module, [
        '{"why_it_matters": "The deal involves a 100% stake for Rs 1.00 lakh in cash.", '
        '"claims": ['
        '{"text": "The stake acquired is 100%.", "type": "FACT", "evidence_refs": ["FACT:tf_stake_percentage"]}, '
        '{"text": "The consideration is Rs 1.00 lakh.", "type": "FACT", "evidence_refs": ["FACT:tf_consideration_amount"]}'
        ']}'
    ])
    es = _evidence_set("ZODIAC", "Zodiac Energy Limited has informed the Exchange about Acquisition-Incorporation of Wholly Owned Subsidiary")
    identity = compute_identity(es)
    raw_id = es.primary_evidence.raw_evidence_id
    context = ArticleContextBundle(
        entity_id=es.entity_id, symbol=es.symbol, event_id=es.event_id, event_headline=es.event_headline,
        status=AVAILABLE,
        transaction_facts=[
            _tf(STAKE_PERCENTAGE, raw_evidence_id=raw_id, value_numeric=100.0, unit="pct"),
            _tf(CONSIDERATION_AMOUNT, raw_evidence_id=raw_id, value_numeric=100_000.0, unit="inr"),
        ],
    )
    article = await compose_article(_decision(es), es, context, identity, _resolution(identity), _headline())
    assert calls["n"] == 1  # accepted on the first attempt -- no retry forced by a false rejection
    assert article.llm_status == "ok"
    why_it_matters = next(s for s in article.sections if s.name == "why_it_matters")
    assert "100%" in why_it_matters.text and "1.00 lakh" in why_it_matters.text
    tf_claims = [c for c in why_it_matters.claims if c.transaction_fact]
    assert len(tf_claims) == 2
    field_codes = {c.transaction_fact["field_code"] for c in tf_claims}
    assert field_codes == {STAKE_PERCENTAGE, CONSIDERATION_AMOUNT}


@pytest.mark.asyncio
async def test_why_it_matters_becomes_eligible_on_transaction_facts_alone(monkeypatch):
    """Before A3, a candidate with ONLY transaction_facts (no financial
    context, no market reaction) would never even attempt Why It
    Matters. This is the eligibility half of A3."""
    calls = _mock_llm(monkeypatch, composer_module, [
        '{"why_it_matters": "This is a cash transaction.", '
        '"claims": [{"text": "This is a cash transaction.", "type": "FACT", "evidence_refs": ["FACT:tf_consideration_type"]}]}'
    ])
    es = _evidence_set("JUNIPER", "Juniper Hotels Limited has informed the Exchange about Acquisition")
    identity = compute_identity(es)
    raw_id = es.primary_evidence.raw_evidence_id
    context = ArticleContextBundle(
        entity_id=es.entity_id, symbol=es.symbol, event_id=es.event_id, event_headline=es.event_headline,
        status=AVAILABLE,
        transaction_facts=[_tf(CONSIDERATION_TYPE, raw_evidence_id=raw_id, value_text="CASH")],
    )
    article = await compose_article(_decision(es), es, context, identity, _resolution(identity), _headline())
    assert calls["n"] == 1  # the LLM call actually happened
    assert article.llm_status == "ok"
    assert any(s.name == "why_it_matters" for s in article.sections)


@pytest.mark.asyncio
async def test_why_it_matters_stays_omitted_with_zero_context_of_any_kind(monkeypatch):
    """No financial context, no market reaction, no transaction facts --
    Why It Matters must still never even be attempted. A3 only widens
    eligibility to a THIRD real source of grounding; it must not make
    the gate permissive in general."""
    calls = _mock_llm(monkeypatch, composer_module, ['{"why_it_matters": "should never be called", "claims": []}'])
    es = _evidence_set("SAILIFE", "Sai Life Sciences has informed the Exchange regarding Information relating to 27th Annual General Meeting")
    identity = compute_identity(es)
    context = ArticleContextBundle(
        entity_id=es.entity_id, symbol=es.symbol, event_id=es.event_id, event_headline=es.event_headline,
        status=NONE_STATUS,
    )
    article = await compose_article(_decision(es), es, context, identity, _resolution(identity), _headline())
    assert calls["n"] == 0
    assert not any(s.name == "why_it_matters" for s in article.sections)


@pytest.mark.asyncio
async def test_why_it_matters_claim_citing_a_transaction_fact_authorizes_via_cd3(monkeypatch):
    """The A3 wiring gap this session closed: a Why-It-Matters claim
    that cites [FACT:tf_<field_code>] must carry a real transaction_fact
    proof dict, or CD3 would silently drop it as UNAVAILABLE even though
    the underlying fact is completely real and already authorized
    elsewhere in the same article."""
    _mock_llm(monkeypatch, composer_module, [
        '{"why_it_matters": "x", "claims": [{"text": "The deal is valued at Rs 248 crore.", '
        '"type": "FACT", "evidence_refs": ["FACT:tf_consideration_amount"]}]}'
    ])
    es = _evidence_set("JUNIPER", "Juniper Hotels Limited has informed the Exchange about Acquisition")
    identity = compute_identity(es)
    raw_id = es.primary_evidence.raw_evidence_id
    context = ArticleContextBundle(
        entity_id=es.entity_id, symbol=es.symbol, event_id=es.event_id, event_headline=es.event_headline,
        status=AVAILABLE,
        transaction_facts=[_tf(CONSIDERATION_AMOUNT, raw_evidence_id=raw_id, value_numeric=2_480_000_000.0, unit="inr")],
    )
    article = await compose_article(_decision(es), es, context, identity, _resolution(identity), _headline())
    why_it_matters = next(s for s in article.sections if s.name == "why_it_matters")
    claim = why_it_matters.claims[0]
    assert claim.transaction_fact is not None
    assert claim.transaction_fact["field_code"] == CONSIDERATION_AMOUNT
    authorized = authorize_composed_claim(claim, TranslationContext())
    assert authorized.capability == Capability.HISTORICAL_DESCRIPTION
    assert authorized.strength == Strength.AUTHORIZED


@pytest.mark.asyncio
async def test_why_it_matters_claim_citing_an_unknown_transaction_fact_ref_is_never_fabricated(monkeypatch):
    """A citation to a tf_<field_code> that does NOT match any real,
    populated transaction fact in this context must never be treated as
    real -- no transaction_fact dict is attached, so it falls through
    to ordinary (unauthorized) claim handling exactly like any other
    ungrounded LLM claim, never silently trusted."""
    _mock_llm(monkeypatch, composer_module, [
        '{"why_it_matters": "x", "claims": [{"text": "The stake is 51%.", '
        '"type": "FACT", "evidence_refs": ["FACT:tf_stake_percentage"]}]}'
    ])
    es = _evidence_set("JUNIPER", "Juniper Hotels Limited has informed the Exchange about Acquisition")
    identity = compute_identity(es)
    raw_id = es.primary_evidence.raw_evidence_id
    # Only consideration_type/amount are real here -- stake_percentage was
    # never extracted for JUNIPER, matching the real revalidation data.
    context = ArticleContextBundle(
        entity_id=es.entity_id, symbol=es.symbol, event_id=es.event_id, event_headline=es.event_headline,
        status=AVAILABLE,
        transaction_facts=[_tf(CONSIDERATION_TYPE, raw_evidence_id=raw_id, value_text="CASH")],
    )
    article = await compose_article(_decision(es), es, context, identity, _resolution(identity), _headline())
    why_it_matters = next(s for s in article.sections if s.name == "why_it_matters")
    claim = why_it_matters.claims[0]
    assert claim.transaction_fact is None
