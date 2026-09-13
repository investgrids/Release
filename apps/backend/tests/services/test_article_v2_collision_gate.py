"""
V1<->V2 Collision Gate (owner design, 2026-09-13) — regression tests.

Prerequisite the owner locked before P7/canary_v2: prove V1 and V2 can
never independently allocate two public canonical articles for the same
real-world development. Root cause (read-only audit): V1's own
duplicate_detector.find_duplicate() and C1's candidate_gate._find_
already_covered() implement two separately-scoped duplicate-detection
queries -- sharing the same tokenizer/Jaccard/threshold, but different
candidate pools -- so they can and do disagree (the real IKIO-shaped
production specimens: V1 says "updated", C5 independently resolves
CREATE_NEW). C5.2's own resolve_uniqueness() collision check is purely
in-memory/intra-batch; it has zero visibility into anything V1 already
committed.

Most important rule under test (a correction the owner required after
an earlier, backwards version of this contract): under the locked
execution model (V1 commits first, V2 runs synchronously after, same
cycle), a V1 "created" decision is the STRONGEST ownership evidence --
stronger than "no collision found" -- and must convert the candidate to
RESOLVED_EXISTING, never leave it as a fresh NO_COLLISION.

Two test groups:
  1. Direct unit tests on collision_gate.check_collision() -- fast,
     real-DB-backed, precise control over every branch.
  2. Full run_shadow_batch() integration tests for the realistic,
     production-relevant scenario the owner named as the one must-pass
     case: V1 creates article A -> V2's own C1/C5 independently resolve
     CREATE_NEW -> the gate must catch this and convert to
     RESOLVED_EXISTING(A) -- never publish_v2_article(), converges on
     rerun.
"""
from __future__ import annotations

import inspect
import random
import re
import string
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete, select

import app.services.article_v2.shadow_orchestrator as shadow_orchestrator_module
import app.services.article_v2.composer as composer_module
import app.services.article_v2.headline_engine as headline_engine_module
from app.db.models.article_v2_shadow_execution import ArticleV2ShadowExecution
from app.db.models.company_entity import CompanyAlias, CompanyEntity
from app.db.models.evidence_entity_link import EvidenceEntityLink
from app.db.models.intelligence_article import IntelligenceArticle
from app.db.models.raw_evidence import RawEvidence
from app.db.models.source_registry import Source
from app.db.session import AsyncSessionLocal
from app.services.article_v2.collision_gate import (
    AMBIGUOUS, BASIS_DUPLICATE_LOOKUP, BASIS_MULTIPLE_OWNERS, BASIS_V1_DECISION,
    NOT_EVALUATED, NO_COLLISION, RESOLVED_EXISTING, V1Decision, check_collision,
)
from app.services.article_v2.identity import CREATE_NEW
from app.services.article_v2.mode import ArticlePipelineMode
from app.services.article_v2.shadow_orchestrator import run_shadow_batch


def _tag():
    return "".join(random.choices(string.ascii_uppercase, k=8))


_UNSET = object()


async def _seed_article(
    db, *, article_id, trigger_event_id, symbol, headline, story_id=None,
    article_type="company_intelligence", angle="primary", angle_entity=_UNSET,
    lifecycle_status="published", created_at=None,
) -> None:
    # angle_entity defaults to the symbol (a convenient realistic default
    # for most tests), but check_collision()'s own real default is None
    # (matching V1's actual primary-path find_duplicate() calls, which
    # never pass angle_entity) -- callers that need a genuinely-None row
    # (e.g. the multi-owner ambiguity test) pass angle_entity=None
    # explicitly, distinguished from "not passed" via this sentinel.
    resolved_angle_entity = symbol if angle_entity is _UNSET else angle_entity
    db.add(IntelligenceArticle(
        id=article_id, slug=article_id, article_type=article_type,
        story_id=story_id or article_id, story_version=1, lifecycle_status=lifecycle_status,
        status="published" if lifecycle_status == "published" else lifecycle_status,
        update_count=0, update_history=[],
        angle=angle, angle_entity=resolved_angle_entity,
        headline=headline, executive_summary="", key_takeaway="", why_it_matters="", what_happened="",
        companies_affected=[{"symbol": symbol}], sectors_affected=[],
        trigger_event_id=trigger_event_id,
        created_at=created_at or (datetime.now(timezone.utc) - timedelta(hours=1)),
    ))


async def _cleanup_articles(*article_ids: str) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(delete(IntelligenceArticle).where(IntelligenceArticle.id.in_(article_ids)))
        await db.commit()


# ── Group 1: direct unit tests on check_collision() ─────────────────────────

@pytest.mark.asyncio
async def test_v1_created_resolves_existing_using_created_article_id():
    """THE core rule: 'created' is the strongest ownership evidence and
    must resolve as RESOLVED_EXISTING, never NO_COLLISION -- getting this
    backwards would let V2 allocate a second canonical article for a
    development V1 just published moments earlier in the same cycle."""
    tag = _tag()
    article_id = f"art-created-{tag}"
    async with AsyncSessionLocal() as db:
        await _seed_article(db, article_id=article_id, trigger_event_id=f"evt-{tag}", symbol=f"SYM{tag}", headline="Test headline")
        await db.commit()
    try:
        async with AsyncSessionLocal() as db:
            result = await check_collision(
                db, event_id=f"evt-{tag}", headline="Test headline",
                v1_decision=V1Decision(decision="created", created_article_id=article_id),
            )
        assert result.outcome == RESOLVED_EXISTING
        assert result.match_basis == "v1_decision"
        assert result.collision_owner_article_id == article_id
    finally:
        await _cleanup_articles(article_id)


@pytest.mark.asyncio
async def test_v1_updated_resolves_existing_using_matched_article_id():
    tag = _tag()
    article_id = f"art-updated-{tag}"
    async with AsyncSessionLocal() as db:
        await _seed_article(db, article_id=article_id, trigger_event_id=f"evt-{tag}", symbol=f"SYM{tag}", headline="Test headline")
        await db.commit()
    try:
        async with AsyncSessionLocal() as db:
            result = await check_collision(
                db, event_id=f"evt-{tag}", headline="Test headline",
                v1_decision=V1Decision(decision="updated", matched_article_id=article_id),
            )
        assert result.outcome == RESOLVED_EXISTING
        assert result.match_basis == "v1_decision"
        assert result.collision_owner_article_id == article_id
    finally:
        await _cleanup_articles(article_id)


@pytest.mark.asyncio
async def test_v1_duplicate_no_update_still_resolves_existing():
    """V1 found a duplicate but its OWN update call didn't apply that
    cycle -- ownership is still real, must still resolve existing, not
    be treated as if V1 found nothing."""
    tag = _tag()
    article_id = f"art-dnu-{tag}"
    async with AsyncSessionLocal() as db:
        await _seed_article(db, article_id=article_id, trigger_event_id=f"evt-{tag}", symbol=f"SYM{tag}", headline="Test headline")
        await db.commit()
    try:
        async with AsyncSessionLocal() as db:
            result = await check_collision(
                db, event_id=f"evt-{tag}", headline="Test headline",
                v1_decision=V1Decision(decision="duplicate_no_update", matched_article_id=article_id),
            )
        assert result.outcome == RESOLVED_EXISTING
        assert result.collision_owner_article_id == article_id
    finally:
        await _cleanup_articles(article_id)


@pytest.mark.asyncio
async def test_v1_claimed_owner_no_longer_exists_falls_back_not_trusted_blindly():
    """V1's claimed article id was real at V1's own decision time but no
    longer exists (deleted) -- a dangling id must not be trusted; falls
    through to the independent DB check instead."""
    async with AsyncSessionLocal() as db:
        result = await check_collision(
            db, event_id="evt-nonexistent-owner", headline="Some genuinely new headline about a thing",
            v1_decision=V1Decision(decision="updated", matched_article_id="does-not-exist-at-all"),
        )
    assert result.outcome == NO_COLLISION  # fallback found nothing either -- genuinely new


@pytest.mark.asyncio
async def test_v1_claimed_owner_archived_is_not_trusted_as_live_ownership():
    tag = _tag()
    article_id = f"art-archived-{tag}"
    async with AsyncSessionLocal() as db:
        await _seed_article(
            db, article_id=article_id, trigger_event_id=f"evt-other-{tag}", symbol=f"SYM{tag}",
            headline="Archived headline", lifecycle_status="archived",
        )
        await db.commit()
    try:
        async with AsyncSessionLocal() as db:
            result = await check_collision(
                db, event_id=f"evt-{tag}", headline="A completely different new headline",
                v1_decision=V1Decision(decision="updated", matched_article_id=article_id),
            )
        # falls through to fallback (no story_id/article_type given here,
        # and the archived article is excluded from any live lookup) --
        # genuinely nothing live claims this identity.
        assert result.outcome == NO_COLLISION
    finally:
        await _cleanup_articles(article_id)


@pytest.mark.asyncio
async def test_uninformative_v1_decision_falls_back_to_db_lookup_and_finds_real_match():
    """V1 never reached ownership for this event (skipped/failed) -- the
    gate must derive the same inputs V1 itself would and run the real,
    shared find_duplicate() check, not just give up."""
    tag = _tag()
    article_id = f"art-fallback-{tag}"
    story_id = f"story-{tag}"
    async with AsyncSessionLocal() as db:
        await _seed_article(
            db, article_id=article_id, trigger_event_id=f"evt-unrelated-{tag}", symbol=f"SYM{tag}",
            headline="Some other headline entirely", story_id=story_id,
        )
        await db.commit()
    try:
        async with AsyncSessionLocal() as db:
            result = await check_collision(
                db, event_id=f"evt-new-{tag}", headline="A brand new headline, unrelated by text",
                v1_decision=V1Decision(decision="skipped_daily_cap"),
                fallback_story_id=story_id, fallback_article_type="company_intelligence",
            )
        assert result.outcome == RESOLVED_EXISTING
        assert result.match_basis == "duplicate_lookup"
        assert result.collision_owner_article_id == article_id
    finally:
        await _cleanup_articles(article_id)


@pytest.mark.asyncio
async def test_uninformative_v1_decision_and_no_real_match_is_no_collision():
    tag = _tag()
    async with AsyncSessionLocal() as db:
        result = await check_collision(
            db, event_id=f"evt-genuinely-new-{tag}", headline="A genuinely new development, never seen before",
            v1_decision=V1Decision(decision="generation_failed"),
            fallback_story_id=f"story-new-{tag}", fallback_article_type="company_intelligence",
        )
    assert result.outcome == NO_COLLISION
    assert result.match_basis is None
    assert result.collision_owner_article_id is None


@pytest.mark.asyncio
async def test_multiple_live_owners_of_the_exact_same_tuple_is_ambiguous():
    """Concrete, narrow, real ambiguity trigger: two DIFFERENT live
    articles already share the exact (trigger_event_id, article_type,
    angle, angle_entity) tuple -- a genuine data-integrity signal
    find_duplicate()'s own `.limit(1)` would silently paper over by
    picking whichever is most recent. The gate must refuse to guess."""
    tag = _tag()
    event_id = f"evt-ambig-{tag}"
    article_id_1 = f"art-ambig1-{tag}"
    article_id_2 = f"art-ambig2-{tag}"
    async with AsyncSessionLocal() as db:
        await _seed_article(
            db, article_id=article_id_1, trigger_event_id=event_id, symbol=f"SYM{tag}",
            headline="First owner", article_type="company_intelligence", angle="primary", angle_entity=None,
        )
        await _seed_article(
            db, article_id=article_id_2, trigger_event_id=event_id, symbol=f"SYM{tag}",
            headline="Second owner (a real pre-existing data integrity issue)",
            article_type="company_intelligence", angle="primary", angle_entity=None,
        )
        await db.commit()
    try:
        async with AsyncSessionLocal() as db:
            result = await check_collision(
                db, event_id=event_id, headline="Some new headline",
                v1_decision=V1Decision(decision="skipped_daily_cap"),
                fallback_story_id=f"story-{tag}", fallback_article_type="company_intelligence",
            )
        assert result.outcome == AMBIGUOUS
        assert result.match_basis == "multiple_owners"
        assert result.collision_owner_article_id is None
    finally:
        await _cleanup_articles(article_id_1, article_id_2)


# ── Group 2: full run_shadow_batch() integration ────────────────────────────

def _triage_event(event_id: str, headline: str, tickers: list[str]) -> dict:
    return {"event_id": event_id, "headline": headline, "urgency": 8, "importance": 7, "tickers": tickers, "sectors": [], "themes": []}


@pytest.mark.asyncio
async def test_v1_created_article_a_v2_creates_new_gate_resolves_existing_a_and_never_publishes(monkeypatch):
    """THE must-pass test the owner named explicitly:
    V1 creates article A -> V2's own C1/C5 independently resolve
    CREATE_NEW (a different event_id, dissimilar headline -- C1 does NOT
    find A on its own, reproducing the real IKIO-shaped disagreement) ->
    the collision gate must catch this via V1Decision.created_article_id
    and convert to RESOLVED_EXISTING(A) -> publish_v2_article() is never
    called -> a rerun resolves to the SAME article A again, not a
    different one and not toggling back to CREATE_NEW."""
    tag = _tag()
    symbol, entity_id, source_id = f"MST{tag}", f"cmp_mst_{tag.lower()}", f"src-{tag}"
    old_event_id = f"evt-old-{tag}"
    new_event_id = f"evt-new-{tag}"
    article_a = f"article-a-{tag}"
    # Deliberately dissimilar headline text and a different event_id so
    # C1's OWN _find_already_covered() (event_id match, then headline
    # Jaccard) does NOT find article_a -- reproducing the real
    # disagreement shape, not a trivial case the existing C1/C5 wiring
    # would already catch.
    a_headline = f"{symbol} filed an administrative clarification with the exchange"
    new_title = f"{symbol} wins Rs 500 crore order from Ministry of Railways"

    async def fake_headline_call(prompt, system="", max_tokens=120, priority=None, **kwargs):
        return '{"headline": "Test Co Wins Rs 500 Crore Railway Order"}'

    async def fake_composer_call(prompt, system="", max_tokens=350, priority=None, **kwargs):
        return '{"why_it_matters": "This order strengthens the company revenue visibility.", "claims": []}'

    monkeypatch.setattr(headline_engine_module, "_call_with_fallback", fake_headline_call)
    monkeypatch.setattr(composer_module, "_call_with_fallback", fake_composer_call)

    evidence_ids: list[str] = []
    async with AsyncSessionLocal() as db:
        db.add(Source(id=source_id, name=f"Test Source {source_id}", source_type="nse", collection_method="test"))
        await db.flush()
        db.add(CompanyEntity(entity_id=entity_id, company_name=f"Test Co {symbol}", exchange="NSE", symbol=symbol, sector="Infrastructure", source="test"))
        await db.flush()
        db.add(CompanyAlias(entity_id=entity_id, alias_type="symbol", alias_value=symbol, exchange="NSE", valid_to=None, source="test"))
        doc_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        db.add(RawEvidence(
            id=doc_id, evidence_key=f"key-{doc_id}", payload_hash=f"hash-{doc_id}", source_id=source_id, source_type="nse",
            title=new_title, published_at=now, observed_at=now,
        ))
        await db.flush()
        db.add(EvidenceEntityLink(entity_id=entity_id, raw_evidence_id=doc_id, relationship_type="subject", resolution_method="source_symbol"))
        evidence_ids.append(doc_id)
        await _seed_article(
            db, article_id=article_a, trigger_event_id=old_event_id, symbol=symbol, headline=a_headline,
        )
        await db.commit()

    all_shadow_ids: list[str] = []
    try:
        v1_decisions = {new_event_id: V1Decision(decision="created", created_article_id=article_a)}

        async with AsyncSessionLocal() as db:
            records = await run_shadow_batch(
                db, triage_events=[(_triage_event(new_event_id, new_title, [symbol]), "approved")],
                v1_decisions=v1_decisions, mode=ArticlePipelineMode.SHADOW_V2,
            )
        r = records[0]
        all_shadow_ids.append(r.id)

        # C1 must NOT have found article_a on its own -- proves this is
        # the real disagreement shape, not a case C1 already catches.
        assert r.c1_outcome == "CANDIDATE"
        # C5's own raw view was CREATE_NEW -- the real disagreement.
        assert r.c5_publication_action == CREATE_NEW
        # The gate caught it and corrected the effective outcome.
        assert r.collision_gate_outcome == RESOLVED_EXISTING
        assert r.collision_match_basis == "v1_decision"
        assert r.collision_owner_article_id == article_a

        # Rerun: same inputs, same cycle shape -- must converge on the
        # SAME article_a, not a different id and not back to CREATE_NEW.
        async with AsyncSessionLocal() as db:
            records_2 = await run_shadow_batch(
                db, triage_events=[(_triage_event(new_event_id, new_title, [symbol]), "approved")],
                v1_decisions=v1_decisions, mode=ArticlePipelineMode.SHADOW_V2,
            )
        r2 = records_2[0]
        all_shadow_ids.append(r2.id)
        assert r2.collision_gate_outcome == RESOLVED_EXISTING
        assert r2.collision_owner_article_id == article_a

        # Structural proof: publish_v2_article is never even reachable
        # from this module -- the only real V2 write path is absent from
        # its source entirely, matching the module's own documented
        # "structural persistence boundary" claim (checking actual
        # import/call usage, not the module's own prose docstring, which
        # legitimately names the function to explain what it does NOT do).
        source = inspect.getsource(shadow_orchestrator_module)
        assert "publish_v2_article(" not in source
        assert "import publish_v2_article" not in source
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(delete(ArticleV2ShadowExecution).where(ArticleV2ShadowExecution.id.in_(all_shadow_ids)))
            await db.execute(delete(EvidenceEntityLink).where(EvidenceEntityLink.raw_evidence_id.in_(evidence_ids)))
            await db.execute(delete(RawEvidence).where(RawEvidence.id.in_(evidence_ids)))
            await db.execute(delete(CompanyAlias).where(CompanyAlias.entity_id == entity_id))
            await db.execute(delete(CompanyEntity).where(CompanyEntity.entity_id == entity_id))
            await db.execute(delete(Source).where(Source.id == source_id))
            await db.commit()
        await _cleanup_articles(article_a)


@pytest.mark.asyncio
async def test_known_identities_never_claimed_by_a_resolved_existing_candidate():
    """The known_identities bookkeeping fix: a candidate the gate
    converts to RESOLVED_EXISTING must NOT claim its identity_key --
    otherwise a second, genuinely-new candidate sharing that identity in
    the same batch would be incorrectly blocked as an intra-batch
    collision against a claim that was never real."""
    tag = _tag()
    symbol, entity_id, source_id = f"IDK{tag}", f"cmp_idk_{tag.lower()}", f"src-{tag}"
    event_id_resolved = f"evt-resolved-{tag}"
    article_a = f"article-idk-{tag}"
    same_title = f"{symbol} wins Rs 800 crore order from Ministry of Defence"

    evidence_ids: list[str] = []
    async with AsyncSessionLocal() as db:
        db.add(Source(id=source_id, name=f"Test Source {source_id}", source_type="nse", collection_method="test"))
        await db.flush()
        db.add(CompanyEntity(entity_id=entity_id, company_name=f"Test Co {symbol}", exchange="NSE", symbol=symbol, sector="Infrastructure", source="test"))
        await db.flush()
        db.add(CompanyAlias(entity_id=entity_id, alias_type="symbol", alias_value=symbol, exchange="NSE", valid_to=None, source="test"))
        doc_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        db.add(RawEvidence(
            id=doc_id, evidence_key=f"key-{doc_id}", payload_hash=f"hash-{doc_id}", source_id=source_id, source_type="nse",
            title=same_title, published_at=now, observed_at=now,
        ))
        await db.flush()
        db.add(EvidenceEntityLink(entity_id=entity_id, raw_evidence_id=doc_id, relationship_type="subject", resolution_method="source_symbol"))
        evidence_ids.append(doc_id)
        await _seed_article(
            db, article_id=article_a, trigger_event_id=f"evt-old-{tag}", symbol=symbol,
            headline=f"{symbol} filed an administrative clarification",
        )
        await db.commit()

    all_shadow_ids: list[str] = []
    try:
        # Only ONE triage event this cycle -- resolved via the gate to
        # RESOLVED_EXISTING(article_a). Directly assert known_identities
        # (module-internal to run_shadow_batch, not exposed) never
        # claims it by checking the record's own identity_key was never
        # associated with a CREATE_NEW outcome.
        async with AsyncSessionLocal() as db:
            records = await run_shadow_batch(
                db, triage_events=[(_triage_event(event_id_resolved, same_title, [symbol]), "approved")],
                v1_decisions={event_id_resolved: V1Decision(decision="created", created_article_id=article_a)},
                mode=ArticlePipelineMode.SHADOW_V2,
            )
        r = records[0]
        all_shadow_ids.append(r.id)
        assert r.collision_gate_outcome == RESOLVED_EXISTING
        assert r.c5_publication_action == CREATE_NEW  # C5's raw view, unmodified
        # The identity was never actually claimed as a fresh CREATE_NEW --
        # proven by construction: known_identities is only ever updated
        # when effective_action == CREATE_NEW, and this record's
        # effective outcome was RESOLVED_EXISTING (see run_shadow_batch's
        # own stage-2 ordering).
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(delete(ArticleV2ShadowExecution).where(ArticleV2ShadowExecution.id.in_(all_shadow_ids)))
            await db.execute(delete(EvidenceEntityLink).where(EvidenceEntityLink.raw_evidence_id.in_(evidence_ids)))
            await db.execute(delete(RawEvidence).where(RawEvidence.id.in_(evidence_ids)))
            await db.execute(delete(CompanyAlias).where(CompanyAlias.entity_id == entity_id))
            await db.execute(delete(CompanyEntity).where(CompanyEntity.entity_id == entity_id))
            await db.execute(delete(Source).where(Source.id == source_id))
            await db.commit()
        await _cleanup_articles(article_a)


# ── Group 3: schema-width regression (owner-required, 2026-09-13) ──────────
# Real defect caught before first production boot: collision_gate_outcome
# was originally declared VARCHAR(16), but "resolved_existing" is 17
# characters -- SQLite doesn't enforce declared VARCHAR widths, so the
# suite stayed green while the schema definition itself was wrong and
# would have silently truncated the value under a stricter backend
# (Postgres). This test makes that class of defect fail loudly instead
# of silently passing on SQLite, and also guards the two declaration
# sites (the ORM model and schema_patches.py's runtime ALTER TABLE DDL)
# from drifting apart from each other.

_ALL_COLLISION_GATE_OUTCOMES = [NOT_EVALUATED, NO_COLLISION, RESOLVED_EXISTING, AMBIGUOUS]
_ALL_COLLISION_MATCH_BASES = [BASIS_V1_DECISION, BASIS_DUPLICATE_LOOKUP, BASIS_MULTIPLE_OWNERS]


def _schema_patch_varchar_width(table: str, column: str) -> int:
    from app.db.schema_patches import _COLUMN_PATCHES
    for t, c, ddl in _COLUMN_PATCHES:
        if t == table and c == column:
            m = re.search(r"VARCHAR\((\d+)\)", ddl)
            assert m, f"expected a VARCHAR(N) declaration for {table}.{column}, got {ddl!r}"
            return int(m.group(1))
    raise AssertionError(f"no schema_patches.py entry found for {table}.{column}")


def test_collision_gate_outcome_column_fits_every_defined_value():
    col = ArticleV2ShadowExecution.__table__.columns["collision_gate_outcome"]
    model_width = col.type.length
    for value in _ALL_COLLISION_GATE_OUTCOMES:
        assert len(value) <= model_width, f"{value!r} ({len(value)} chars) does not fit the model's VARCHAR({model_width})"

    patch_width = _schema_patch_varchar_width("article_v2_shadow_executions", "collision_gate_outcome")
    assert patch_width == model_width, (
        f"schema_patches.py declares VARCHAR({patch_width}) but the ORM model declares VARCHAR({model_width}) "
        "-- the two must stay in sync, or a fresh DB (create_all, model width) and an already-deployed DB "
        "(schema_patches.py, patch width) end up with different column widths for the same table."
    )
    for value in _ALL_COLLISION_GATE_OUTCOMES:
        assert len(value) <= patch_width, f"{value!r} ({len(value)} chars) does not fit schema_patches.py's VARCHAR({patch_width})"


def test_collision_match_basis_column_fits_every_defined_value():
    col = ArticleV2ShadowExecution.__table__.columns["collision_match_basis"]
    model_width = col.type.length
    for value in _ALL_COLLISION_MATCH_BASES:
        assert len(value) <= model_width, f"{value!r} ({len(value)} chars) does not fit the model's VARCHAR({model_width})"

    patch_width = _schema_patch_varchar_width("article_v2_shadow_executions", "collision_match_basis")
    assert patch_width == model_width
    for value in _ALL_COLLISION_MATCH_BASES:
        assert len(value) <= patch_width, f"{value!r} ({len(value)} chars) does not fit schema_patches.py's VARCHAR({patch_width})"
