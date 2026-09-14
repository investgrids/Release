"""
Article V2 — P7 Real-Write / Canary Activation (owner design,
2026-09-14) — regression tests.

Locked contract under test: canary_publisher.py is the ONLY module
allowed to call publish_v2_article() for a real IntelligenceArticle. It
re-verifies every eligibility predicate against a fresh rerun rather
than trusting the earlier withhold decision; ownership transfers only
at the article's own commit; everything after that (coverage, the
withhold row's own outcome/published_article_id) is best-effort
bookkeeping; reconciliation after a crash looks for a deterministic
(trigger_type="article_v2_pipeline", trigger_event_id) match, never
infers from shadow-execution lineage; and the lifetime budget of
exactly one is enforced by a DB-level partial unique index, not merely
an application check-then-write query.
"""
from __future__ import annotations

import random
import string
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from app.db.models.article_v2_canary_withhold import ArticleV2CanaryWithhold
from app.db.models.event_coverage import EventCoverage
from app.db.models.intelligence_article import IntelligenceArticle
from app.db.session import AsyncSessionLocal
from app.services.article_v2 import canary_publisher as cp
from app.services.article_v2.candidate_gate import SKIP as C1_SKIP
from app.services.article_v2.collision_gate import AMBIGUOUS, NO_COLLISION, RESOLVED_EXISTING
from app.services.article_v2.composer import ComposerRefusal
from app.services.article_v2.decision_engine import CREATE, FACTUAL_UPDATE
from app.services.article_v2.evidence_set_builder import COHERENT
from app.services.article_v2.identity import CREATE_NEW, UPDATE_EXISTING
from app.services.article_v2.publication_tier import EVENT_ONLY
from app.services.article_v2.publisher import PublicationRefusal
import app.services.article_v2.composer as composer_module
import app.services.article_v2.headline_engine as headline_engine_module
from app.db.models.company_entity import CompanyAlias, CompanyEntity
from app.db.models.evidence_entity_link import EvidenceEntityLink
from app.db.models.raw_evidence import RawEvidence
from app.db.models.source_registry import Source


def _tag():
    return "".join(random.choices(string.ascii_uppercase, k=8))


def _triage_event(event_id: str, symbol: str, headline: str) -> dict:
    return {"event_id": event_id, "headline": headline, "urgency": 9, "importance": 8, "tickers": [symbol]}


async def _seed_withhold(*, event_id: str, outcome=None) -> None:
    async with AsyncSessionLocal() as db:
        db.add(ArticleV2CanaryWithhold(
            id=f"withhold-{uuid.uuid4()}", triage_event_id=event_id,
            prior_shadow_execution_id=f"shadow-{uuid.uuid4()}", reason_predicates={},
            outcome=outcome,
        ))
        await db.commit()


async def _cleanup(*, event_ids=(), article_ids=()):
    async with AsyncSessionLocal() as db:
        await db.execute(delete(ArticleV2CanaryWithhold).where(ArticleV2CanaryWithhold.triage_event_id.in_(event_ids)))
        await db.execute(delete(EventCoverage).where(EventCoverage.event_id.in_(event_ids)))
        await db.execute(delete(IntelligenceArticle).where(IntelligenceArticle.id.in_(article_ids)))
        await db.commit()


# ── Fakes for a fully-succeeding rerun, overridden per test ────────────────

@dataclass
class _FakeCandidate:
    outcome: str = "CANDIDATE"
    reason_code: str = ""
    reason_detail: str = ""
    entity_id: str = "cmp_fake"
    matched_article_id: str | None = None


@dataclass
class _FakeEvidenceSet:
    primary_evidence: object = "present"
    event_id: str = "evt"
    symbol: str = "FAKE"


@dataclass
class _FakeContext:
    status: str = COHERENT


@dataclass
class _FakeDecision:
    content_type: str = FACTUAL_UPDATE
    publication_action: str = CREATE
    event_id: str = "evt"


@dataclass
class _FakeIdentity:
    identity_key: str = "cmp_fake|KEY"


@dataclass
class _FakeResolution:
    publication_action: str = CREATE_NEW
    matched_article_id: str | None = None
    reason: str = "fresh CREATE_NEW"


@dataclass
class _FakeCollision:
    outcome: str = NO_COLLISION
    match_basis: str | None = None
    collision_owner_article_id: str | None = None


@dataclass
class _FakeTierResult:
    tier: str = "ARTICLE"
    reason_codes: list = None


@dataclass
class _FakeHeadlineResult:
    h1: str = "Fake Headline"


class _FakeComposed:
    headline = "Fake Headline"


def _patch_all_succeeding(monkeypatch, *, article_id="article-final-id"):
    """Every stage returns a fresh, eligible result. Individual tests
    override exactly one of these to force a specific decline path."""
    monkeypatch.setattr(cp, "evaluate_candidate", AsyncMock(return_value=_FakeCandidate()))
    monkeypatch.setattr(cp, "build_evidence_set", AsyncMock(return_value=_FakeEvidenceSet()))
    monkeypatch.setattr(cp, "build_context", AsyncMock(return_value=_FakeContext()))
    monkeypatch.setattr(cp, "decide", lambda candidate, es, ctx: _FakeDecision())
    monkeypatch.setattr(cp, "compute_identity", lambda es: _FakeIdentity())
    monkeypatch.setattr(cp, "resolve_uniqueness", lambda *a, **k: _FakeResolution())
    monkeypatch.setattr(cp, "check_collision", AsyncMock(return_value=_FakeCollision()))
    monkeypatch.setattr(cp, "classify_publication_tier", lambda *a, **k: _FakeTierResult())
    monkeypatch.setattr(cp, "generate_headline", AsyncMock(return_value=_FakeHeadlineResult()))
    monkeypatch.setattr(cp, "compose_article", AsyncMock(return_value=_FakeComposed()))

    def _fake_select_article_type(stub, mie_context):
        return "company_intelligence", "story-fake", 1

    monkeypatch.setattr("app.services.aipe.content_planner.select_article_type", _fake_select_article_type)

    publish_mock = AsyncMock(return_value=IntelligenceArticle(id=article_id, headline="x", trigger_event_id="evt"))
    monkeypatch.setattr(cp, "publish_v2_article", publish_mock)
    monkeypatch.setattr(cp, "coverage_mark_published", AsyncMock())
    return publish_mock


# ── Re-verification / precondition tests ───────────────────────────────────

@pytest.mark.asyncio
async def test_no_withhold_row_at_all_declines_without_touching_anything(monkeypatch):
    event_id = f"evt-{_tag()}"
    publish_mock = _patch_all_succeeding(monkeypatch)
    async with AsyncSessionLocal() as db:
        result = await cp.attempt_canary_publish(
            db, triage_event=_triage_event(event_id, "FAKE1", "headline"), ev_tier="High", mie_context={},
        )
    assert result.published is False
    assert "no fresh, unattempted withhold row" in result.reason
    publish_mock.assert_not_called()


@pytest.mark.asyncio
async def test_already_attempted_withhold_declines():
    event_id = f"evt-{_tag()}"
    await _seed_withhold(event_id=event_id, outcome="shadow_not_qualified")
    try:
        async with AsyncSessionLocal() as db:
            result = await cp.attempt_canary_publish(
                db, triage_event=_triage_event(event_id, "FAKE2", "headline"), ev_tier="High", mie_context={},
            )
        assert result.published is False
        assert "no fresh, unattempted withhold row" in result.reason
    finally:
        await _cleanup(event_ids=[event_id])


@pytest.mark.asyncio
async def test_critical_tier_is_never_eligible_even_with_a_fresh_withhold(monkeypatch):
    event_id = f"evt-{_tag()}"
    await _seed_withhold(event_id=event_id)
    publish_mock = _patch_all_succeeding(monkeypatch)
    try:
        async with AsyncSessionLocal() as db:
            result = await cp.attempt_canary_publish(
                db, triage_event=_triage_event(event_id, "FAKE3", "headline"), ev_tier="Critical", mie_context={},
            )
        assert result.published is False
        assert "not High" in result.reason
        publish_mock.assert_not_called()
        async with AsyncSessionLocal() as db:
            row = (await db.execute(select(ArticleV2CanaryWithhold).where(ArticleV2CanaryWithhold.triage_event_id == event_id))).scalar_one()
            assert row.outcome == "shadow_not_qualified"
    finally:
        await _cleanup(event_ids=[event_id])


@pytest.mark.asyncio
async def test_lifetime_budget_already_consumed_declines_before_any_rerun(monkeypatch):
    event_id = f"evt-{_tag()}"
    consumed_event_id = f"evt-{_tag()}"
    await _seed_withhold(event_id=event_id)
    await _seed_withhold(event_id=consumed_event_id, outcome="published_v2")
    publish_mock = _patch_all_succeeding(monkeypatch)
    try:
        async with AsyncSessionLocal() as db:
            result = await cp.attempt_canary_publish(
                db, triage_event=_triage_event(event_id, "FAKE4", "headline"), ev_tier="High", mie_context={},
            )
        assert result.published is False
        assert "budget already consumed" in result.reason
        publish_mock.assert_not_called()
    finally:
        await _cleanup(event_ids=[event_id, consumed_event_id])


@pytest.mark.asyncio
async def test_a_declined_candidate_still_consumes_the_attempt_budget(monkeypatch):
    """The exact gap this correction closes: candidate A's fresh rerun
    declines pre-commit (never gets near the publish-budget index at
    all), but that must STILL permanently close the real canary path --
    candidate B must be declined immediately, without running a single
    pipeline stage, regardless of what happened to A."""
    event_a = f"evt-{_tag()}"
    event_b = f"evt-{_tag()}"
    await _seed_withhold(event_id=event_a)
    await _seed_withhold(event_id=event_b)
    publish_mock = _patch_all_succeeding(monkeypatch)
    monkeypatch.setattr(cp, "evaluate_candidate", AsyncMock(return_value=_FakeCandidate(outcome=C1_SKIP, reason_detail="entity vanished")))
    try:
        async with AsyncSessionLocal() as db:
            result_a = await cp.attempt_canary_publish(
                db, triage_event=_triage_event(event_a, "FAKEA", "headline"), ev_tier="High", mie_context={},
            )
        assert result_a.published is False
        assert "C1 SKIP" in result_a.reason  # A genuinely declined, never published

        async with AsyncSessionLocal() as db:
            row_a = (await db.execute(select(ArticleV2CanaryWithhold).where(ArticleV2CanaryWithhold.triage_event_id == event_a))).scalar_one()
            assert row_a.attempted is True, "A's decline must still have claimed the attempt budget"
            assert row_a.outcome == "shadow_not_qualified"

        evaluate_candidate_calls_before_b = cp.evaluate_candidate.await_count
        async with AsyncSessionLocal() as db:
            result_b = await cp.attempt_canary_publish(
                db, triage_event=_triage_event(event_b, "FAKEB", "headline"), ev_tier="High", mie_context={},
            )
        assert result_b.published is False
        assert "attempt budget already consumed" in result_b.reason
        assert cp.evaluate_candidate.await_count == evaluate_candidate_calls_before_b, \
            "B must be declined before even C1 runs -- the attempt budget check must be the very first gate"
        publish_mock.assert_not_called()

        async with AsyncSessionLocal() as db:
            row_b = (await db.execute(select(ArticleV2CanaryWithhold).where(ArticleV2CanaryWithhold.triage_event_id == event_b))).scalar_one()
            assert row_b.attempted is False, "B never claimed the budget -- A already held it"
            assert row_b.outcome is None
    finally:
        await _cleanup(event_ids=[event_a, event_b])


@pytest.mark.asyncio
async def test_racing_attempt_claims_share_one_atomic_commit_before_the_rerun():
    """The attempt-budget analog of the publish-budget race test:
    constructs the race deterministically (two sessions each stage the
    attempted=True claim, committed in controlled order) rather than
    relying on real SQLite concurrency timing. Proves the loser's claim
    is rejected at the DB level, independent of anything about outcome
    or published_article_id."""
    event_a = f"evt-{_tag()}"
    event_b = f"evt-{_tag()}"
    await _seed_withhold(event_id=event_a)
    await _seed_withhold(event_id=event_b)
    try:
        async with AsyncSessionLocal() as db:
            row_a = (await db.execute(select(ArticleV2CanaryWithhold).where(ArticleV2CanaryWithhold.triage_event_id == event_a))).scalar_one()
            row_a.attempted = True
            db.add(row_a)
            await db.commit()

        async with AsyncSessionLocal() as db:
            row_b = (await db.execute(select(ArticleV2CanaryWithhold).where(ArticleV2CanaryWithhold.triage_event_id == event_b))).scalar_one()
            row_b.attempted = True
            db.add(row_b)
            with pytest.raises(IntegrityError):
                await db.commit()
            await db.rollback()

        async with AsyncSessionLocal() as db:
            fresh_a = (await db.execute(select(ArticleV2CanaryWithhold).where(ArticleV2CanaryWithhold.triage_event_id == event_a))).scalar_one()
            fresh_b = (await db.execute(select(ArticleV2CanaryWithhold).where(ArticleV2CanaryWithhold.triage_event_id == event_b))).scalar_one()
            assert fresh_a.attempted is True
            assert fresh_b.attempted is False, "the loser's claim must not have persisted"
    finally:
        await _cleanup(event_ids=[event_a, event_b])


@pytest.mark.asyncio
async def test_attempt_budget_consumed_reflects_the_real_invariant():
    event_id = f"evt-{_tag()}"
    await _seed_withhold(event_id=event_id)
    try:
        async with AsyncSessionLocal() as db:
            assert await cp._attempt_budget_consumed(db) is False
        async with AsyncSessionLocal() as db:
            row = (await db.execute(select(ArticleV2CanaryWithhold).where(ArticleV2CanaryWithhold.triage_event_id == event_id))).scalar_one()
            row.attempted = True
            db.add(row)
            await db.commit()
        async with AsyncSessionLocal() as db:
            assert await cp._attempt_budget_consumed(db) is True
    finally:
        await _cleanup(event_ids=[event_id])


@pytest.mark.asyncio
async def test_no_ticker_declines(monkeypatch):
    event_id = f"evt-{_tag()}"
    await _seed_withhold(event_id=event_id)
    publish_mock = _patch_all_succeeding(monkeypatch)
    try:
        triage_event = {"event_id": event_id, "headline": "headline", "tickers": []}
        async with AsyncSessionLocal() as db:
            result = await cp.attempt_canary_publish(db, triage_event=triage_event, ev_tier="High", mie_context={})
        assert result.published is False
        assert "no ticker" in result.reason
        publish_mock.assert_not_called()
    finally:
        await _cleanup(event_ids=[event_id])


@pytest.mark.asyncio
async def test_c1_skip_on_fresh_rerun_declines(monkeypatch):
    event_id = f"evt-{_tag()}"
    await _seed_withhold(event_id=event_id)
    publish_mock = _patch_all_succeeding(monkeypatch)
    monkeypatch.setattr(cp, "evaluate_candidate", AsyncMock(return_value=_FakeCandidate(outcome=C1_SKIP, reason_detail="entity vanished")))
    try:
        async with AsyncSessionLocal() as db:
            result = await cp.attempt_canary_publish(
                db, triage_event=_triage_event(event_id, "FAKE5", "headline"), ev_tier="High", mie_context={},
            )
        assert result.published is False
        assert "C1 SKIP" in result.reason
        publish_mock.assert_not_called()
    finally:
        await _cleanup(event_ids=[event_id])


@pytest.mark.asyncio
async def test_c2_no_primary_evidence_declines(monkeypatch):
    event_id = f"evt-{_tag()}"
    await _seed_withhold(event_id=event_id)
    publish_mock = _patch_all_succeeding(monkeypatch)
    monkeypatch.setattr(cp, "build_evidence_set", AsyncMock(return_value=_FakeEvidenceSet(primary_evidence=None)))
    try:
        async with AsyncSessionLocal() as db:
            result = await cp.attempt_canary_publish(
                db, triage_event=_triage_event(event_id, "FAKE6", "headline"), ev_tier="High", mie_context={},
            )
        assert result.published is False
        assert "C2" in result.reason
        publish_mock.assert_not_called()
    finally:
        await _cleanup(event_ids=[event_id])


@pytest.mark.asyncio
async def test_c4_wrong_content_type_declines(monkeypatch):
    event_id = f"evt-{_tag()}"
    await _seed_withhold(event_id=event_id)
    publish_mock = _patch_all_succeeding(monkeypatch)
    monkeypatch.setattr(cp, "decide", lambda candidate, es, ctx: _FakeDecision(content_type=EVENT_ONLY))
    try:
        async with AsyncSessionLocal() as db:
            result = await cp.attempt_canary_publish(
                db, triage_event=_triage_event(event_id, "FAKE7", "headline"), ev_tier="High", mie_context={},
            )
        assert result.published is False
        assert "C4" in result.reason
        publish_mock.assert_not_called()
    finally:
        await _cleanup(event_ids=[event_id])


@pytest.mark.asyncio
async def test_c5_resolves_update_existing_not_create_new_declines(monkeypatch):
    """The exact production-observed shape ownership_arbitration.py's own
    tests guard against, rechecked here on the FRESH rerun: if fresh
    evidence now resolves UPDATE_EXISTING, V2 no longer wants a new
    article -- must never publish."""
    event_id = f"evt-{_tag()}"
    await _seed_withhold(event_id=event_id)
    publish_mock = _patch_all_succeeding(monkeypatch)
    monkeypatch.setattr(cp, "resolve_uniqueness", lambda *a, **k: _FakeResolution(publication_action=UPDATE_EXISTING))
    try:
        async with AsyncSessionLocal() as db:
            result = await cp.attempt_canary_publish(
                db, triage_event=_triage_event(event_id, "FAKE8", "headline"), ev_tier="High", mie_context={},
            )
        assert result.published is False
        assert "C5" in result.reason
        publish_mock.assert_not_called()
    finally:
        await _cleanup(event_ids=[event_id])


@pytest.mark.asyncio
async def test_collision_gate_resolved_existing_declines(monkeypatch):
    event_id = f"evt-{_tag()}"
    await _seed_withhold(event_id=event_id)
    publish_mock = _patch_all_succeeding(monkeypatch)
    monkeypatch.setattr(cp, "check_collision", AsyncMock(return_value=_FakeCollision(outcome=RESOLVED_EXISTING, collision_owner_article_id="art-x")))
    try:
        async with AsyncSessionLocal() as db:
            result = await cp.attempt_canary_publish(
                db, triage_event=_triage_event(event_id, "FAKE9", "headline"), ev_tier="High", mie_context={},
            )
        assert result.published is False
        assert "resolved_existing" in result.reason
        publish_mock.assert_not_called()
    finally:
        await _cleanup(event_ids=[event_id])


@pytest.mark.asyncio
async def test_collision_gate_ambiguous_declines(monkeypatch):
    event_id = f"evt-{_tag()}"
    await _seed_withhold(event_id=event_id)
    publish_mock = _patch_all_succeeding(monkeypatch)
    monkeypatch.setattr(cp, "check_collision", AsyncMock(return_value=_FakeCollision(outcome=AMBIGUOUS)))
    try:
        async with AsyncSessionLocal() as db:
            result = await cp.attempt_canary_publish(
                db, triage_event=_triage_event(event_id, "FAKE10", "headline"), ev_tier="High", mie_context={},
            )
        assert result.published is False
        assert "ambiguous" in result.reason
        publish_mock.assert_not_called()
    finally:
        await _cleanup(event_ids=[event_id])


@pytest.mark.asyncio
async def test_c8_tier_not_article_declines(monkeypatch):
    event_id = f"evt-{_tag()}"
    await _seed_withhold(event_id=event_id)
    publish_mock = _patch_all_succeeding(monkeypatch)
    monkeypatch.setattr(cp, "classify_publication_tier", lambda *a, **k: _FakeTierResult(tier=EVENT_ONLY))
    try:
        async with AsyncSessionLocal() as db:
            result = await cp.attempt_canary_publish(
                db, triage_event=_triage_event(event_id, "FAKE11", "headline"), ev_tier="High", mie_context={},
            )
        assert result.published is False
        assert "C8 tier" in result.reason
        publish_mock.assert_not_called()
    finally:
        await _cleanup(event_ids=[event_id])


@pytest.mark.asyncio
async def test_composer_refusal_declines(monkeypatch):
    event_id = f"evt-{_tag()}"
    await _seed_withhold(event_id=event_id)
    publish_mock = _patch_all_succeeding(monkeypatch)
    monkeypatch.setattr(cp, "compose_article", AsyncMock(side_effect=ComposerRefusal("no real claims survived")))
    try:
        async with AsyncSessionLocal() as db:
            result = await cp.attempt_canary_publish(
                db, triage_event=_triage_event(event_id, "FAKE12", "headline"), ev_tier="High", mie_context={},
            )
        assert result.published is False
        assert "ComposerRefusal" in result.reason
        publish_mock.assert_not_called()
    finally:
        await _cleanup(event_ids=[event_id])


@pytest.mark.asyncio
async def test_publication_refusal_declines_and_rolls_back(monkeypatch):
    event_id = f"evt-{_tag()}"
    await _seed_withhold(event_id=event_id)
    _patch_all_succeeding(monkeypatch)
    monkeypatch.setattr(cp, "publish_v2_article", AsyncMock(side_effect=PublicationRefusal("no usable headline")))
    try:
        async with AsyncSessionLocal() as db:
            result = await cp.attempt_canary_publish(
                db, triage_event=_triage_event(event_id, "FAKE13", "headline"), ev_tier="High", mie_context={},
            )
        assert result.published is False
        assert "PublicationRefusal" in result.reason
        async with AsyncSessionLocal() as db:
            row = (await db.execute(select(ArticleV2CanaryWithhold).where(ArticleV2CanaryWithhold.triage_event_id == event_id))).scalar_one()
            assert row.outcome == "shadow_not_qualified"
    finally:
        await _cleanup(event_ids=[event_id])


# ── Happy path ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_happy_path_publishes_updates_coverage_and_withhold_outcome(monkeypatch):
    event_id = f"evt-{_tag()}"
    article_id = f"canary-art-{uuid.uuid4()}"
    await _seed_withhold(event_id=event_id)
    publish_mock = _patch_all_succeeding(monkeypatch, article_id=article_id)

    published_article = IntelligenceArticle(id=article_id, headline="x", trigger_event_id=event_id, trigger_type="article_v2_pipeline")
    publish_mock.return_value = published_article
    # Unlike every other test here, this one verifies the REAL coverage
    # DB effect end-to-end -- use the real coverage_engine function, not
    # the mock _patch_all_succeeding installs for the other tests.
    from app.services.coverage_engine import mark_published as _real_mark_published
    monkeypatch.setattr(cp, "coverage_mark_published", _real_mark_published)

    try:
        async with AsyncSessionLocal() as db:
            db.add(EventCoverage(
                id=str(uuid.uuid4()), event_id=event_id, priority="High", priority_score=50,
                detected_at=datetime.now(timezone.utc), event_title="t", sectors=[], companies=[],
                article_required=True, coverage_status="DETECTED", last_checked_at=datetime.now(timezone.utc),
            ))
            await db.commit()

        async with AsyncSessionLocal() as db:
            result = await cp.attempt_canary_publish(
                db, triage_event=_triage_event(event_id, "FAKE14", "headline"), ev_tier="High", mie_context={},
            )
        assert result.published is True
        assert result.article_id == article_id
        publish_mock.assert_awaited_once()
        _, call_kwargs = publish_mock.call_args
        assert call_kwargs["field_overrides"]["status"] == "published"
        assert call_kwargs["field_overrides"]["lifecycle_status"] == "published"
        assert "published_at" in call_kwargs["field_overrides"]

        async with AsyncSessionLocal() as db:
            row = (await db.execute(select(ArticleV2CanaryWithhold).where(ArticleV2CanaryWithhold.triage_event_id == event_id))).scalar_one()
            assert row.outcome == "published_v2"
            assert row.published_article_id == article_id
            coverage = (await db.execute(select(EventCoverage).where(EventCoverage.event_id == event_id))).scalar_one()
            assert coverage.coverage_status == "PUBLISHED"
            assert coverage.article_id == article_id
    finally:
        await _cleanup(event_ids=[event_id], article_ids=[article_id])


# ── One genuine end-to-end run through the REAL pipeline (not mocked
#    stages) -- proves canary_publisher.py's own call signatures actually
#    match the real C1-C8.5+P1/P2/P4 functions, which the mocked-stage
#    tests above cannot catch on their own. ──────────────────────────────

async def _seed_source(db, source_id: str):
    db.add(Source(id=source_id, name=f"Test Source {source_id}", source_type="nse", collection_method="test"))
    await db.flush()


async def _seed_entity(db, symbol: str, entity_id: str):
    db.add(CompanyEntity(entity_id=entity_id, company_name=f"Test Co {symbol}", exchange="NSE", symbol=symbol, sector="Infrastructure", source="test"))
    await db.flush()
    db.add(CompanyAlias(entity_id=entity_id, alias_type="symbol", alias_value=symbol, exchange="NSE", valid_to=None, source="test"))


async def _seed_evidence(db, *, entity_id: str, source_id: str, title: str) -> str:
    doc_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    db.add(RawEvidence(
        id=doc_id, evidence_key=f"key-{doc_id}", payload_hash=f"hash-{doc_id}", source_id=source_id, source_type="nse",
        title=title, published_at=now, observed_at=now,
    ))
    await db.flush()
    db.add(EvidenceEntityLink(entity_id=entity_id, raw_evidence_id=doc_id, relationship_type="subject", resolution_method="source_symbol"))
    return doc_id


@pytest.mark.asyncio
async def test_real_pipeline_end_to_end_reaches_a_real_committed_public_article(monkeypatch):
    tag = _tag()
    symbol, entity_id, source_id = f"CNRY{tag}", f"cmp_cnry_{tag.lower()}", f"src-{tag}"
    event_id = f"evt-{tag}"
    title = f"{symbol} wins Rs 500 crore order from Ministry of Railways"

    async def fake_headline_call(prompt, system="", max_tokens=120, priority=None, **kwargs):
        return '{"headline": "Test Co Wins Rs 500 Crore Railway Order"}'

    async def fake_composer_call(prompt, system="", max_tokens=350, priority=None, **kwargs):
        return '{"why_it_matters": "This order strengthens the company revenue visibility.", "claims": []}'

    monkeypatch.setattr(headline_engine_module, "_call_with_fallback", fake_headline_call)
    monkeypatch.setattr(composer_module, "_call_with_fallback", fake_composer_call)

    evidence_ids: list[str] = []
    article_id: str | None = None
    await _seed_withhold(event_id=event_id)
    async with AsyncSessionLocal() as db:
        await _seed_source(db, source_id)
        await _seed_entity(db, symbol, entity_id)
        evidence_ids.append(await _seed_evidence(db, entity_id=entity_id, source_id=source_id, title=title))
        await db.commit()

    try:
        async with AsyncSessionLocal() as db:
            result = await cp.attempt_canary_publish(
                db, triage_event=_triage_event(event_id, symbol, title), ev_tier="High", mie_context={},
            )
        assert result.published is True, result.reason
        article_id = result.article_id

        async with AsyncSessionLocal() as db:
            article = (await db.execute(select(IntelligenceArticle).where(IntelligenceArticle.id == article_id))).scalar_one()
            assert article.status == "published"
            assert article.lifecycle_status == "published"
            assert article.published_at is not None
            assert article.trigger_type == "article_v2_pipeline"
            assert article.trigger_event_id == event_id

            row = (await db.execute(select(ArticleV2CanaryWithhold).where(ArticleV2CanaryWithhold.triage_event_id == event_id))).scalar_one()
            assert row.outcome == "published_v2"
            assert row.published_article_id == article_id
    finally:
        cleanup_ids = [article_id] if article_id else []
        await _cleanup(event_ids=[event_id], article_ids=cleanup_ids)
        async with AsyncSessionLocal() as db:
            await db.execute(delete(EvidenceEntityLink).where(EvidenceEntityLink.raw_evidence_id.in_(evidence_ids)))
            await db.execute(delete(RawEvidence).where(RawEvidence.id.in_(evidence_ids)))
            await db.execute(delete(CompanyAlias).where(CompanyAlias.entity_id == entity_id))
            await db.execute(delete(CompanyEntity).where(CompanyEntity.entity_id == entity_id))
            await db.execute(delete(Source).where(Source.id == source_id))
            await db.commit()


# ── Reconciliation ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_reconcile_zero_matches_leaves_row_untouched():
    event_id = f"evt-{_tag()}"
    await _seed_withhold(event_id=event_id)
    try:
        async with AsyncSessionLocal() as db:
            await cp.reconcile_stale_canary_withholds(db)
        async with AsyncSessionLocal() as db:
            row = (await db.execute(select(ArticleV2CanaryWithhold).where(ArticleV2CanaryWithhold.triage_event_id == event_id))).scalar_one()
            assert row.outcome is None
    finally:
        await _cleanup(event_ids=[event_id])


@pytest.mark.asyncio
async def test_reconcile_one_match_backfills_outcome_coverage_and_article_id():
    event_id = f"evt-{_tag()}"
    article_id = f"orphan-art-{uuid.uuid4()}"
    await _seed_withhold(event_id=event_id)
    try:
        async with AsyncSessionLocal() as db:
            db.add(IntelligenceArticle(
                id=article_id, headline="Orphaned canary article", trigger_type="article_v2_pipeline",
                trigger_event_id=event_id, status="published", lifecycle_status="published",
            ))
            db.add(EventCoverage(
                id=str(uuid.uuid4()), event_id=event_id, priority="High", priority_score=50,
                detected_at=datetime.now(timezone.utc), event_title="t", sectors=[], companies=[],
                article_required=True, coverage_status="DETECTED", last_checked_at=datetime.now(timezone.utc),
            ))
            await db.commit()

        async with AsyncSessionLocal() as db:
            await cp.reconcile_stale_canary_withholds(db)

        async with AsyncSessionLocal() as db:
            row = (await db.execute(select(ArticleV2CanaryWithhold).where(ArticleV2CanaryWithhold.triage_event_id == event_id))).scalar_one()
            assert row.outcome == "published_v2"
            assert row.published_article_id == article_id
            coverage = (await db.execute(select(EventCoverage).where(EventCoverage.event_id == event_id))).scalar_one()
            assert coverage.coverage_status == "PUBLISHED"
    finally:
        await _cleanup(event_ids=[event_id], article_ids=[article_id])


@pytest.mark.asyncio
async def test_reconcile_multiple_matches_fails_closed_never_guesses():
    event_id = f"evt-{_tag()}"
    article_id_1 = f"ambig-art-{uuid.uuid4()}"
    article_id_2 = f"ambig-art-{uuid.uuid4()}"
    await _seed_withhold(event_id=event_id)
    try:
        async with AsyncSessionLocal() as db:
            db.add(IntelligenceArticle(id=article_id_1, headline="A", trigger_type="article_v2_pipeline", trigger_event_id=event_id, status="published"))
            db.add(IntelligenceArticle(id=article_id_2, headline="B", trigger_type="article_v2_pipeline", trigger_event_id=event_id, status="published"))
            await db.commit()

        async with AsyncSessionLocal() as db:
            await cp.reconcile_stale_canary_withholds(db)

        async with AsyncSessionLocal() as db:
            row = (await db.execute(select(ArticleV2CanaryWithhold).where(ArticleV2CanaryWithhold.triage_event_id == event_id))).scalar_one()
            assert row.outcome is None, "ambiguous multi-match must never be auto-resolved"
            assert row.published_article_id is None
    finally:
        await _cleanup(event_ids=[event_id], article_ids=[article_id_1, article_id_2])


# ── DB-level lifetime budget invariant ──────────────────────────────────

@pytest.mark.asyncio
async def test_partial_unique_index_enforces_at_most_one_published_v2_ever():
    event_id_1 = f"evt-{_tag()}"
    event_id_2 = f"evt-{_tag()}"
    await _seed_withhold(event_id=event_id_1)
    await _seed_withhold(event_id=event_id_2)
    try:
        async with AsyncSessionLocal() as db:
            row1 = (await db.execute(select(ArticleV2CanaryWithhold).where(ArticleV2CanaryWithhold.triage_event_id == event_id_1))).scalar_one()
            row1.outcome = "published_v2"
            db.add(row1)
            await db.commit()

        async with AsyncSessionLocal() as db:
            row2 = (await db.execute(select(ArticleV2CanaryWithhold).where(ArticleV2CanaryWithhold.triage_event_id == event_id_2))).scalar_one()
            row2.outcome = "published_v2"
            db.add(row2)
            with pytest.raises(IntegrityError):
                await db.commit()
    finally:
        await _cleanup(event_ids=[event_id_1, event_id_2])


@pytest.mark.asyncio
async def test_racing_article_commits_share_one_atomic_transaction_with_the_budget_claim():
    """The exact gap an earlier draft had: the article commit and the
    withhold budget-claim commit were two SEPARATE transactions, so two
    racing workers could each commit a real article before either
    claimed the budget -- the partial unique index would then only stop
    the second TELEMETRY row, too late to stop the second ARTICLE.

    This constructs the race explicitly rather than relying on true
    concurrency (which on SQLite risks flaky lock-timing rather than
    exercising the invariant deterministically): two sessions each build
    their own real article row AND stage the budget claim on their own
    withhold row, in the SAME transaction canary_publisher.py itself now
    uses. The first session commits and wins the budget. The second
    session's commit must raise IntegrityError -- and because the
    article insert is IN that same transaction, rolling back must
    discard the article too, not just the withhold update."""
    event_id_1 = f"evt-{_tag()}"
    event_id_2 = f"evt-{_tag()}"
    article_id_1 = f"race-art-{uuid.uuid4()}"
    article_id_2 = f"race-art-{uuid.uuid4()}"
    await _seed_withhold(event_id=event_id_1)
    await _seed_withhold(event_id=event_id_2)
    try:
        # Winner: article insert + budget claim committed together.
        async with AsyncSessionLocal() as db:
            db.add(IntelligenceArticle(
                id=article_id_1, headline="Winner", trigger_type="article_v2_pipeline",
                trigger_event_id=event_id_1, status="published", lifecycle_status="published",
            ))
            row1 = (await db.execute(select(ArticleV2CanaryWithhold).where(ArticleV2CanaryWithhold.triage_event_id == event_id_1))).scalar_one()
            row1.outcome = "published_v2"
            row1.published_article_id = article_id_1
            db.add(row1)
            await db.commit()

        # Loser: built exactly like the winner, but the budget slot is
        # already taken -- the SAME transaction must fail and roll back
        # both the withhold update AND the article insert together.
        async with AsyncSessionLocal() as db:
            db.add(IntelligenceArticle(
                id=article_id_2, headline="Loser", trigger_type="article_v2_pipeline",
                trigger_event_id=event_id_2, status="published", lifecycle_status="published",
            ))
            row2 = (await db.execute(select(ArticleV2CanaryWithhold).where(ArticleV2CanaryWithhold.triage_event_id == event_id_2))).scalar_one()
            row2.outcome = "published_v2"
            row2.published_article_id = article_id_2
            db.add(row2)
            with pytest.raises(IntegrityError):
                await db.commit()
            await db.rollback()

        # Prove it against fresh sessions, not the (now-invalid) ones above.
        async with AsyncSessionLocal() as db:
            articles = (await db.execute(
                select(IntelligenceArticle).where(IntelligenceArticle.id.in_([article_id_1, article_id_2]))
            )).scalars().all()
            assert [a.id for a in articles] == [article_id_1], \
                "exactly one canary V2 article must exist -- the loser's article must have rolled back with its withhold update"

            loser_row = (await db.execute(select(ArticleV2CanaryWithhold).where(ArticleV2CanaryWithhold.triage_event_id == event_id_2))).scalar_one()
            assert loser_row.outcome is None, "the losing withhold must not be marked published_v2"
            assert loser_row.published_article_id is None, "the losing withhold must have no durable article pointer"

            winner_row = (await db.execute(select(ArticleV2CanaryWithhold).where(ArticleV2CanaryWithhold.triage_event_id == event_id_1))).scalar_one()
            assert winner_row.outcome == "published_v2"
            assert winner_row.published_article_id == article_id_1
    finally:
        await _cleanup(event_ids=[event_id_1, event_id_2], article_ids=[article_id_1, article_id_2])


@pytest.mark.asyncio
async def test_lifetime_budget_consumed_reflects_the_real_invariant():
    event_id = f"evt-{_tag()}"
    await _seed_withhold(event_id=event_id)
    try:
        async with AsyncSessionLocal() as db:
            assert await cp._lifetime_budget_consumed(db) is False
        async with AsyncSessionLocal() as db:
            row = (await db.execute(select(ArticleV2CanaryWithhold).where(ArticleV2CanaryWithhold.triage_event_id == event_id))).scalar_one()
            row.outcome = "published_v2"
            db.add(row)
            await db.commit()
        async with AsyncSessionLocal() as db:
            assert await cp._lifetime_budget_consumed(db) is True
    finally:
        await _cleanup(event_ids=[event_id])
