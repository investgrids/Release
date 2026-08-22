"""
Async hero-image worker — the "Queue -> Worker -> Generate -> Save" half of
the pipeline. Runs on its own schedule (scheduler.py), completely decoupled
from AIPE's publish flow: create_media_job() only ever does one cheap DB
insert at publish time, never waits on this.
"""
from __future__ import annotations

from datetime import datetime, timezone

import structlog
from sqlalchemy import select

from app.core.config import settings
from app.db.models.generated_media import GeneratedMedia
from app.db.models.intelligence_article import IntelligenceArticle
from app.db.session import AsyncSessionLocal
from app.services.media.pollinations_client import generate_image
from app.services.media.prompt_builder import build_prompt
from app.services.media.storage import save_image

log = structlog.get_logger(__name__)

_MAX_ATTEMPTS = 3
_BATCH_SIZE = 3  # this provider is slow (up to ~45s/image under load) — a
                  # 60s worker tick shouldn't try to drain a large backlog


async def create_media_job(article_id: str, media_type: str = "hero") -> None:
    """Called from publisher.py right after a successful publish. One cheap
    insert, no external calls — the actual generation happens later, on the
    worker's own schedule, so this can never delay or block publication."""
    import uuid
    async with AsyncSessionLocal() as db:
        db.add(GeneratedMedia(
            id=str(uuid.uuid4()),
            article_id=article_id,
            media_type=media_type,
            status="pending",
        ))
        await db.commit()


async def _notify_frontend(slug: str) -> None:
    """On-demand ISR revalidation — so the real image replaces the gradient
    fallback immediately, without waiting for the page's normal cache
    window or a redeploy. Best-effort: a missed revalidation just means the
    page catches up at its next natural revalidate, not a broken state."""
    if not settings.frontend_url or not settings.revalidate_secret:
        return
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                f"{settings.frontend_url}/api/revalidate",
                json={"slug": slug, "secret": settings.revalidate_secret},
            )
    except Exception as exc:
        log.debug("media.revalidate_notify_failed", slug=slug, error=str(exc)[:150])


async def run_image_generation_cycle() -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(GeneratedMedia)
            .where(GeneratedMedia.status.in_(["pending", "failed"]))
            .where(GeneratedMedia.attempts < _MAX_ATTEMPTS)
            .order_by(GeneratedMedia.created_at.asc())
            .limit(_BATCH_SIZE)
        )
        jobs = result.scalars().all()
        if not jobs:
            return

        for job in jobs:
            job.status = "generating"
            job.attempts += 1
        await db.commit()
        job_ids = [j.id for j in jobs]

    for job_id in job_ids:
        try:
            await _process_job(job_id)
        except Exception as exc:
            # A crash here used to abort the whole batch (the remaining
            # job_ids in this tick were simply never processed) AND
            # permanently strand this one job — it was already flipped to
            # "generating" above, which the pending/failed query filter at
            # the top of this function never re-selects, so it would sit
            # forever with no image and no further retry attempts.
            log.error("media.process_job_crashed", job_id=job_id, error=str(exc)[:200])
            async with AsyncSessionLocal() as db:
                job = (await db.execute(select(GeneratedMedia).where(GeneratedMedia.id == job_id))).scalar_one_or_none()
                if job and job.status == "generating":
                    job.error = f"crashed: {str(exc)[:200]}"
                    job.status = "fallback" if job.attempts >= _MAX_ATTEMPTS else "failed"
                    await db.commit()


async def _process_job(job_id: str) -> None:
    async with AsyncSessionLocal() as db:
        job = (await db.execute(select(GeneratedMedia).where(GeneratedMedia.id == job_id))).scalar_one_or_none()
        if not job:
            return
        article = (await db.execute(
            select(IntelligenceArticle).where(IntelligenceArticle.id == job.article_id)
        )).scalar_one_or_none()
        if not article:
            job.status = "failed"
            job.error = "source article no longer exists"
            await db.commit()
            return

        sectors = [s.get("name") for s in (article.sectors_affected or []) if isinstance(s, dict) and s.get("name")]
        prompt, prompt_version, style, seed = build_prompt(article.headline or "", article.article_type, sectors, article.id)
        job.prompt = prompt
        job.prompt_version = prompt_version
        job.style = style
        job.provider = "pollinations"
        await db.commit()

        log.info("media.generation.start", article_id=article.id, slug=article.slug, attempt=job.attempts, seed=seed)
        content = await generate_image(prompt, seed=seed)

        if content:
            try:
                url = save_image(job.id, content)
            except Exception as exc:
                # save_image writes atomically (temp file + rename) so a
                # disk-full/permission failure here can never leave a
                # truncated/corrupt file at the served URL — but the
                # exception itself still needs to mark this job retryable
                # instead of crashing this job's processing unhandled.
                job.error = f"save failed: {str(exc)[:200]}"
                job.status = "fallback" if job.attempts >= _MAX_ATTEMPTS else "failed"
                await db.commit()
                log.warning("media.save_failed", article_id=article.id, error=str(exc)[:200])
                return
            job.status = "generated"
            job.url = url
            job.generated_at = datetime.now(timezone.utc)
            job.error = None
            await db.commit()
            log.info("media.generation.success", article_id=article.id, slug=article.slug)
            await _notify_frontend(article.slug)
        else:
            job.error = "provider returned no image"
            job.status = "fallback" if job.attempts >= _MAX_ATTEMPTS else "failed"
            await db.commit()
            log.warning("media.generation.failed", article_id=article.id, attempt=job.attempts, terminal=job.status == "fallback")
