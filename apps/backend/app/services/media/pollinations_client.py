"""
Pollinations.ai client — free, no-API-key image generation.

Verified live before wiring in: good, consistent editorial-illustration
quality, but the free/unauthenticated tier queues under load (~1.5s for a
single request, 18-45s for back-to-back requests in testing). That's why
this is never called from the request/publish path — only from the
scheduled worker (image_worker.py), which is built to tolerate exactly
this kind of latency.
"""
from __future__ import annotations

from urllib.parse import quote

import httpx
import structlog

log = structlog.get_logger(__name__)

_BASE_URL = "https://image.pollinations.ai/prompt"
_TIMEOUT_S = 55.0  # generous — this provider is known to be slow, not just occasionally


async def generate_image(prompt: str, width: int = 800, height: int = 450) -> bytes | None:
    """Returns raw image bytes, or None on any failure/timeout. Never raises."""
    url = f"{_BASE_URL}/{quote(prompt)}?width={width}&height={height}&nologo=true"
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
            r = await client.get(url)
            if r.status_code == 200 and r.content:
                return r.content
            log.warning("pollinations.non_200", status=r.status_code)
            return None
    except httpx.TimeoutException:
        log.warning("pollinations.timeout")
        return None
    except Exception as exc:
        log.warning("pollinations.error", error=str(exc)[:200])
        return None
