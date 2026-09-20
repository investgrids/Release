"""Shared on-demand ISR revalidation notifier — one call site for every
backend action that changes what a Next.js page renders faster than that
page's own fetch-level `revalidate` window would otherwise catch up.

Originally only the media worker's hero-image swap (image_worker.py)
needed this; opportunity-v2-canary-promote/-revert now do too, after a
real production finding (2026-09-20): reverting a canary flipped
public_status back to shadow and the backend API correctly 404'd
immediately, but the opportunity-radar detail page kept serving its old
content for well past its own 300s revalidate window, with no
self-clearing observed even across a fresh frontend deployment.

Best-effort and silent on failure by design, matching the frontend
route's own docstring: a missed call just means the page catches up at
its next natural revalidation, not a broken state — this must never be
allowed to fail (or block/rollback) the database transaction that
triggered it.
"""
from __future__ import annotations

import structlog

from app.core.config import settings

log = structlog.get_logger(__name__)


async def notify_frontend_revalidate(slug: str, kind: str) -> None:
    if not settings.frontend_url or not settings.revalidate_secret:
        return
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                f"{settings.frontend_url}/api/revalidate",
                json={"slug": slug, "kind": kind},
                headers={"X-Revalidate-Secret": settings.revalidate_secret},
            )
    except Exception as exc:
        log.debug("frontend_revalidate.notify_failed", slug=slug, kind=kind, error=str(exc)[:150])
