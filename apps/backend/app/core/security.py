"""Minimal admin-key auth for internal/write endpoints.

The app has no user auth system (read-only public product), but a handful
of endpoints mutate shared state or trigger paid AI runs and must not be
reachable by anonymous callers. This is intentionally simple: one shared
secret, checked via a header, for the ops surfaces only — not a general
auth system.
"""
from __future__ import annotations

import hmac

from fastapi import Header, HTTPException

from app.core.config import settings


async def require_admin_key(x_admin_key: str | None = Header(default=None)) -> None:
    if not settings.admin_api_key:
        # No key configured (e.g. local dev) — fail closed in that case only
        # if the endpoint is reachable from a non-loopback origin would be
        # nicer, but the simplest safe default is: no key configured means
        # the endpoint is disabled, not silently open.
        raise HTTPException(status_code=503, detail="Admin endpoint not configured")
    if not x_admin_key or not hmac.compare_digest(x_admin_key, settings.admin_api_key):
        raise HTTPException(status_code=401, detail="Missing or invalid X-Admin-Key")
