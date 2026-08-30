"""
CandidateRun / candidate_lifecycle.py — real DB-backed tests for the
durable lifecycle record scheduled/synthetic article candidates get
(morning_intelligence, market_wrap, educational_intelligence,
historical_intelligence). Closes a real 2026-08-30 incident: these
candidates had no EventTriage/EventCoverage row, so a generation failure
used to leave zero database trace (artifacts/ai_provider_reliability_
audit.md, 22 real occurrences in one log window).

Also covers generate_intelligence_article's new failure_log threading
(the mechanism that gives a CandidateRun real provider-attempt detail,
not a synthetic summary).
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import delete, select

from app.db.models.candidate_run import (
    TERMINAL_INTERNAL_ERROR, TERMINAL_PROVIDER_FAILED, TERMINAL_PUBLISHED,
    TERMINAL_VALIDATION_FAILED, CandidateRun,
)
from app.db.session import AsyncSessionLocal
from app.services.aipe.candidate_lifecycle import complete_candidate_run, start_candidate_run


async def _cleanup(candidate_id: str):
    async with AsyncSessionLocal() as db:
        await db.execute(delete(CandidateRun).where(CandidateRun.candidate_id == candidate_id))
        await db.commit()


@pytest.mark.asyncio
async def test_start_candidate_run_persists_immediately():
    candidate_id = "test-morning-2026-08-30"
    try:
        async with AsyncSessionLocal() as db:
            run = await start_candidate_run(db, candidate_id, "morning_intelligence")
            assert run.id is not None
            assert run.generation_started_at is not None
            assert run.terminal_status is None  # not yet complete

        # Real, separate session -- proves it was actually committed, not
        # just held in the first session's identity map.
        async with AsyncSessionLocal() as db:
            row = (await db.execute(select(CandidateRun).where(CandidateRun.candidate_id == candidate_id))).scalar_one()
            assert row.candidate_type == "morning_intelligence"
            assert row.trigger_type == "scheduled_cron"
    finally:
        await _cleanup(candidate_id)


@pytest.mark.asyncio
async def test_generation_failure_now_leaves_a_real_terminal_record():
    """The exact incident this closes: a candidate whose generation fails
    completely (no IntelligenceArticle ever created) must still resolve to
    a real, queryable terminal record -- never silently vanish."""
    candidate_id = "test-wrap-generation-failed"
    try:
        async with AsyncSessionLocal() as db:
            run = await start_candidate_run(db, candidate_id, "market_wrap")
            await complete_candidate_run(
                db, run, terminal_status=TERMINAL_PROVIDER_FAILED,
                failure_reason="generation_failed",
                provider_attempts=[{"model": "openai/gpt-oss-120b", "provider": "groq-hq", "reason": "429"}],
            )

        async with AsyncSessionLocal() as db:
            row = (await db.execute(select(CandidateRun).where(CandidateRun.candidate_id == candidate_id))).scalar_one()
            assert row.terminal_status == TERMINAL_PROVIDER_FAILED
            assert row.failure_reason == "generation_failed"
            assert row.article_id is None
            assert row.completed_at is not None
            assert len(row.provider_attempts) == 1
    finally:
        await _cleanup(candidate_id)


@pytest.mark.asyncio
async def test_published_run_records_the_real_article_id():
    candidate_id = "test-evergreen-published"
    try:
        async with AsyncSessionLocal() as db:
            run = await start_candidate_run(db, candidate_id, "educational_intelligence")
            await complete_candidate_run(db, run, terminal_status=TERMINAL_PUBLISHED, article_id="real-article-id-123")

        async with AsyncSessionLocal() as db:
            row = (await db.execute(select(CandidateRun).where(CandidateRun.candidate_id == candidate_id))).scalar_one()
            assert row.terminal_status == TERMINAL_PUBLISHED
            assert row.article_id == "real-article-id-123"
            assert row.failure_reason is None
    finally:
        await _cleanup(candidate_id)


@pytest.mark.asyncio
async def test_validation_failure_records_article_id_and_reason():
    """A validation failure DOES create a real IntelligenceArticle row
    (status='failed') separately -- CandidateRun still records it for a
    single, consistent place to look up any scheduled candidate's fate."""
    candidate_id = "test-historical-validation-failed"
    try:
        async with AsyncSessionLocal() as db:
            run = await start_candidate_run(db, candidate_id, "historical_intelligence")
            await complete_candidate_run(
                db, run, terminal_status=TERMINAL_VALIDATION_FAILED,
                article_id="failed-article-id-456", failure_reason="validation_failed",
            )

        async with AsyncSessionLocal() as db:
            row = (await db.execute(select(CandidateRun).where(CandidateRun.candidate_id == candidate_id))).scalar_one()
            assert row.terminal_status == TERMINAL_VALIDATION_FAILED
            assert row.article_id == "failed-article-id-456"
            assert row.failure_reason == "validation_failed"
    finally:
        await _cleanup(candidate_id)


@pytest.mark.asyncio
async def test_internal_error_terminal_state():
    candidate_id = "test-internal-error"
    try:
        async with AsyncSessionLocal() as db:
            run = await start_candidate_run(db, candidate_id, "morning_intelligence")
            await complete_candidate_run(
                db, run, terminal_status=TERMINAL_INTERNAL_ERROR,
                failure_reason="ConnectionError: db pool exhausted",
            )

        async with AsyncSessionLocal() as db:
            row = (await db.execute(select(CandidateRun).where(CandidateRun.candidate_id == candidate_id))).scalar_one()
            assert row.terminal_status == TERMINAL_INTERNAL_ERROR
            assert "ConnectionError" in row.failure_reason
    finally:
        await _cleanup(candidate_id)


# ── generate_intelligence_article's failure_log threading ───────────────────

@pytest.mark.asyncio
async def test_failure_log_populated_on_provider_exception():
    from app.services.aipe.article_generator import generate_intelligence_article

    with patch(
        "app.services.aipe.article_generator._call_with_fallback",
        new_callable=AsyncMock, side_effect=RuntimeError("all providers down"),
    ):
        failure_log: list[dict] = []
        result = await generate_intelligence_article(
            article_type="market_wrap", event={"headline": "test"}, mie_context={}, historical=[],
            failure_log=failure_log,
        )
        assert result is None
        assert len(failure_log) == 1
        assert "all providers down" in failure_log[0]["reason"]


@pytest.mark.asyncio
async def test_failure_log_omitted_is_backward_compatible():
    """Every existing caller that doesn't pass failure_log must see
    identical behavior to before this parameter existed -- no crash, no
    forced tracking."""
    from app.services.aipe.article_generator import generate_intelligence_article

    with patch(
        "app.services.aipe.article_generator._call_with_fallback",
        new_callable=AsyncMock, return_value="",
    ):
        result = await generate_intelligence_article(
            article_type="market_wrap", event={"headline": "test"}, mie_context={}, historical=[],
        )
        assert result is None  # empty response -> None, same as always
