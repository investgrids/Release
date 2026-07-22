"""Protected operational endpoints — admin-key gated, not for end users.

Distinct from /api/publishing (ops dashboard, its own admin-gated endpoints
for content review) — this is infra/db status, for spotting misconfigurations
like an unmounted volume before they cause data loss.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.security import require_admin_key

router = APIRouter()


@router.get("/db-status", dependencies=[Depends(require_admin_key)])
async def db_status_endpoint():
    from app.db.session import engine
    from app.db.health import db_status
    return await db_status(engine)
