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


def has_valid_admin_key(x_admin_key: str | None) -> bool:
    """Non-raising sibling of require_admin_key — for a caller that must
    keep serving the rest of its response regardless of the key (e.g.
    AEV2's canary mode: the endpoint stays public, only one optional
    field is gated), not a whole-endpoint lockout. Same comparison, same
    fail-closed posture (no key configured -> never valid), just no
    HTTPException."""
    if not settings.admin_api_key or not x_admin_key:
        return False
    return hmac.compare_digest(x_admin_key, settings.admin_api_key)
