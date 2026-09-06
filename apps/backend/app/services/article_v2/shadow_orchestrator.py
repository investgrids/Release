"""
Article V2 Phase P5 — Shadow/canary entry-point orchestration (owner
design, 2026-09-06). The one place that runs the real C1-C8.5+P1+P2+P4
path for the Event-triggered AIPE flow, for every triage event in one
`run_aipe_cycle()` batch, and records durable P6 telemetry for each.

Reuses the exact real pipeline sequence already validated across two
independent 500-event shadow cohorts (see `scripts/article_v2_c8_shadow_run.py`,
Article V2 Phase C7/C8) -- this module does not reimplement that
sequence, it extracts it into a reusable, per-batch function so P5 can
call the SAME validated logic against real, live production candidates
instead of a historical replay.

## Structural persistence boundary (owner's own explicit requirement)

This module imports `build_and_validate` (pure -- computes and validates
the fields a publish WOULD use) but never `publish_v2_article` (the only
function that actually calls `db.add()`/`db.flush()` for a real
`IntelligenceArticle`). There is no code path in this file that can
write a public row -- not "protected by a flag," structurally absent.
`canary_v2`/`v2` real public persistence is P7's job; when that's built,
it will live in a different function than this one, not a branch added
here.

## Two-phase batch structure (mirrors C8's own real batch discipline)

C5.2's cross-event-in-the-same-batch identity collision and C8.3's
batch-wide headline-uniqueness closure both need every candidate's
stage-1 result gathered BEFORE any of them are finalized. This module
runs C1->C2->C3->C4->C5->C8.1(tier) per triage event first, generates
headlines for ARTICLE-tier survivors, runs C8.3's real
`finalize_batch_uniqueness()` over them, then composes+translates+
authorizes+validates whatever survives that closure. Every triage
event -- including ones that stopped at C1, or were downgraded by
C8.3 -- gets its own durable `ArticleV2ShadowExecution` row.

## A real, honest limitation worth knowing before reading P6's results

`known_identities`/`known_headlines` are scoped to ONE cycle's small
batch (`run_aipe_cycle`'s own `max_per_cycle=3`), not persisted across
cycles -- because shadow mode never writes a public `IntelligenceArticle`
row, there is nothing durable for a LATER cycle's C1/C5 duplicate/
identity checks to find. This means shadow telemetry can under-detect
cross-cycle duplicates/identity collisions that a real `v2`/`canary_v2`
cutover (writing real rows) would not have. Worth accounting for when
reading P6's cohort analysis, not something this module can fix on its
own -- fixing it would mean querying `ArticleV2ShadowExecution` itself
as a stand-in "as if published" history, which is a real design choice
for a LATER phase, not silently done here.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.article_v2_shadow_execution import ArticleV2ShadowExecution
from app.services.article_v2.candidate_gate import SKIP as C1_SKIP
from app.services.article_v2.candidate_gate import evaluate_candidate
from app.services.article_v2.composer import ComposerRefusal, compose_article
from app.services.article_v2.context_builder import build_context
from app.services.article_v2.decision_engine import FACTUAL_UPDATE, FULL_ARTICLE, decide
from app.services.article_v2.evidence_set_builder import build_evidence_set
from app.services.article_v2.headline_engine import finalize_batch_uniqueness, generate_headline
from app.services.article_v2.identity import CREATE_NEW, UPDATE_EXISTING, compute_identity, resolve_uniqueness
from app.services.article_v2.mode import ArticlePipelineMode
from app.services.article_v2.publication_tier import ARTICLE, classify_publication_tier
from app.services.article_v2.publisher import PublicationRefusal, build_and_validate

log = structlog.get_logger(__name__)


@dataclass
class _PendingCandidate:
    """Everything gathered in stage 1, carried into stage 2 (headline +
    C8.3 closure + compose+P1+P2+P4). Mutable -- this is a working
    accumulator local to one batch run, not a public dataclass."""
    triage_event_id: str | None
    symbol: str | None
    v1_decision: str
    record: ArticleV2ShadowExecution
    start_time: float
    decision: object = None
    evidence_set: object = None
    context: object = None
    identity: object = None
    resolution: object = None


def _new_record(*, triage_event_id: str | None, symbol: str | None, mode: ArticlePipelineMode) -> ArticleV2ShadowExecution:
    return ArticleV2ShadowExecution(
        id=f"shadow-{uuid.uuid4()}", triage_event_id=triage_event_id, symbol=symbol,
        pipeline_mode=mode.value, would_publish=False, evidence_ids=[],
    )


async def _run_stage_one(
    db: AsyncSession, *, symbol: str, event_headline: str, event_id: str | None,
    v1_decision: str, mode: ArticlePipelineMode, start_time: float,
) -> _PendingCandidate:
    """C1 -> C2 -> C3 -> C4 -> C5 -> C8.1 tier, for one triage event.
    Stops and finalizes the record the moment any stage says no."""
    record = _new_record(triage_event_id=event_id, symbol=symbol, mode=mode)
    record.v1_publication_decision = v1_decision
    record.stage_reached = "C1"

    candidate = await evaluate_candidate(db, symbol=symbol, event_headline=event_headline, event_id=event_id)
    record.canonical_entity_id = candidate.entity_id
    record.c1_outcome = candidate.outcome
    record.c1_reason_code = candidate.reason_code
    if candidate.outcome == C1_SKIP:
        record.rejection_reason = f"C1 SKIP: {candidate.reason_detail}"
        record.execution_time_ms = (time.monotonic() - start_time) * 1000
        return _PendingCandidate(event_id, symbol, v1_decision, record, start_time)

    es = await build_evidence_set(db, symbol=symbol, event_headline=event_headline, event_id=event_id)
    record.stage_reached = "C2"
    record.evidence_ids = [e.raw_evidence_id for e in ([es.primary_evidence] if es.primary_evidence else []) + list(es.supporting_evidence)]
    record.evidence_count = es.raw_evidence_count
    if es.primary_evidence is None:
        record.rejection_reason = "C2: no usable primary evidence"
        record.execution_time_ms = (time.monotonic() - start_time) * 1000
        return _PendingCandidate(event_id, symbol, v1_decision, record, start_time)

    ctx = await build_context(db, es)
    record.stage_reached = "C3"
    record.c3_context_status = ctx.status

    decision = decide(candidate, es, ctx)
    record.stage_reached = "C4"
    record.c4_content_type = decision.content_type
    record.c4_publication_action = decision.publication_action
    if decision.content_type not in (FULL_ARTICLE, FACTUAL_UPDATE):
        record.rejection_reason = f"C4: content_type={decision.content_type}"
        record.execution_time_ms = (time.monotonic() - start_time) * 1000
        return _PendingCandidate(event_id, symbol, v1_decision, record, start_time)

    identity = compute_identity(es)
    record.stage_reached = "C5"
    record.identity_key = identity.identity_key

    return _PendingCandidate(
        event_id, symbol, v1_decision, record, start_time,
        decision=decision, evidence_set=es, context=ctx, identity=identity,
    )


async def run_shadow_batch(
    db: AsyncSession, *, triage_events: list[dict], v1_decisions: dict[str, str], mode: ArticlePipelineMode,
) -> list[ArticleV2ShadowExecution]:
    """The one real entry point. `triage_events` is the SAME `approved`
    list `run_aipe_cycle()` already computed for this cycle -- shadow
    telemetry always describes the identical candidates V1 is looking at
    in this same cycle, never a separately-sampled batch.
    `v1_decisions` maps `event_id -> "created"|"updated"|"duplicate_no_update"|
    "skipped_<reason>"`, filled in by the caller's own existing V1 loop
    (this module never re-derives what V1 did -- it trusts the caller's
    real, already-known outcome). Persists (adds + commits) one
    `ArticleV2ShadowExecution` row per triage event and returns them.
    """
    known_identities: dict[str, str] = {}
    known_headlines: dict[str, str] = {}
    pending: list[_PendingCandidate] = []

    for triage_event, _filter_reason in triage_events:
        tickers = triage_event.get("tickers") or []
        event_id = triage_event.get("event_id")
        headline = triage_event.get("headline") or ""
        v1_decision = v1_decisions.get(event_id, "unknown")
        start_time = time.monotonic()

        if not tickers:
            record = _new_record(triage_event_id=event_id, symbol=None, mode=mode)
            record.v1_publication_decision = v1_decision
            record.stage_reached = "C1"
            record.rejection_reason = "no tickers on this triage event -- V2 requires a real symbol"
            record.execution_time_ms = (time.monotonic() - start_time) * 1000
            pending.append(_PendingCandidate(event_id, None, v1_decision, record, start_time))
            continue

        symbol = tickers[0]
        pc = await _run_stage_one(
            db, symbol=symbol, event_headline=headline, event_id=event_id,
            v1_decision=v1_decision, mode=mode, start_time=start_time,
        )
        pending.append(pc)

    # Stage 2: tier classification + headline generation for whatever
    # survived C1-C4-C5, ARTICLE-tier only reaches headline generation
    # (EVENT_ONLY/REJECT never do, per the same architectural decision
    # the real C1-C8.5 pipeline already enforces).
    tier_survivors: list[_PendingCandidate] = []
    for pc in pending:
        if pc.decision is None:
            continue  # already finalized (stopped at C1/C2/C4) in stage 1
        resolution = resolve_uniqueness(
            pc.identity, c4_publication_action=pc.decision.publication_action,
            c4_matched_article_id=None, known_identities=known_identities,
        )
        pc.resolution = resolution
        pc.record.c5_publication_action = resolution.publication_action
        if resolution.publication_action == CREATE_NEW:
            known_identities[pc.identity.identity_key] = pc.record.id
        if resolution.publication_action not in (CREATE_NEW, UPDATE_EXISTING):
            pc.record.stage_reached = "C5"
            pc.record.rejection_reason = f"C5: {resolution.reason}"
            pc.record.execution_time_ms = (time.monotonic() - pc.start_time) * 1000
            continue

        tier_result = classify_publication_tier(pc.decision, pc.evidence_set, pc.context)
        pc.record.c8_tier = tier_result.tier
        if tier_result.tier != ARTICLE:
            pc.record.stage_reached = "C8_TIER"
            pc.record.rejection_reason = f"C8 tier={tier_result.tier}: {tier_result.reason_codes}"
            pc.record.execution_time_ms = (time.monotonic() - pc.start_time) * 1000
            continue

        headline_result = await generate_headline(
            pc.evidence_set, pc.context, pc.identity, other_accepted_headlines=known_headlines,
        )
        pc.record.stage_reached = "HEADLINE"
        pc.record.headline = headline_result.h1
        if headline_result.h1:
            known_headlines[pc.identity.identity_key] = headline_result.h1
        pc.__dict__["headline_result"] = headline_result
        tier_survivors.append(pc)

    # C8.3: batch-wide final uniqueness closure over ARTICLE-tier survivors only.
    ordered_pairs = [(pc.identity, pc.__dict__["headline_result"].h1) for pc in tier_survivors]
    batch_result = finalize_batch_uniqueness(ordered_pairs) if ordered_pairs else {}

    for pc in tier_survivors:
        br = batch_result.get(pc.identity.identity_key)
        if br is not None and not br.kept:
            pc.record.rejection_reason = (
                f"C8.3: headline still collides with {br.collided_with!r} after batch uniqueness closure"
            )
            pc.record.execution_time_ms = (time.monotonic() - pc.start_time) * 1000
            continue

        headline_result = pc.__dict__["headline_result"]
        try:
            composed = await compose_article(
                pc.decision, pc.evidence_set, pc.context, pc.identity, pc.resolution, headline_result,
            )
        except ComposerRefusal as exc:
            pc.record.stage_reached = "COMPOSE"
            pc.record.rejection_reason = f"ComposerRefusal: {exc}"
            pc.record.execution_time_ms = (time.monotonic() - pc.start_time) * 1000
            continue
        pc.record.stage_reached = "COMPOSE"

        try:
            build_and_validate(
                article_id=pc.record.id, decision=pc.decision, evidence_set=pc.evidence_set,
                identity=pc.identity, resolution=pc.resolution, headline_result=headline_result,
                composed=composed,
            )
            pc.record.stage_reached = "P4"
            pc.record.p1_translation_status = "ok"
            pc.record.p4_validation_result = "would_publish"
            pc.record.would_publish = True
        except PublicationRefusal as exc:
            pc.record.stage_reached = "P4"
            pc.record.p4_validation_result = "refused"
            pc.record.rejection_reason = f"PublicationRefusal: {exc}"
        pc.record.execution_time_ms = (time.monotonic() - pc.start_time) * 1000

    records = [pc.record for pc in pending]
    for record in records:
        db.add(record)
    await db.commit()

    log.info(
        "article_v2.shadow_batch_complete", mode=mode.value, total=len(records),
        would_publish=sum(1 for r in records if r.would_publish),
    )
    return records
