"""
GovernmentPolicyRepository â€” DB reads/writes for the government_policies table.
"""
from __future__ import annotations

import structlog
from typing import Optional

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.event import GovernmentPolicy

logger = structlog.get_logger(__name__)


class GovernmentPolicyRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(self, policy_id: int) -> Optional[GovernmentPolicy]:
        result = await self._db.execute(
            select(GovernmentPolicy).where(GovernmentPolicy.id == policy_id)
        )
        return result.scalar_one_or_none()

    async def get_by_external_id(self, external_id: str) -> Optional[GovernmentPolicy]:
        result = await self._db.execute(
            select(GovernmentPolicy).where(GovernmentPolicy.external_id == external_id)
        )
        return result.scalar_one_or_none()

    async def get_by_ids(self, ids: list[int]) -> list[GovernmentPolicy]:
        if not ids:
            return []
        result = await self._db.execute(
            select(GovernmentPolicy).where(GovernmentPolicy.id.in_(ids))
        )
        return list(result.scalars().all())

    async def search_by_keywords(
        self, keywords: list[str], limit: int = 5
    ) -> list[GovernmentPolicy]:
        if not keywords:
            return []
        conditions = [
            GovernmentPolicy.title.ilike(f"%{kw}%") for kw in keywords
        ]
        result = await self._db.execute(
            select(GovernmentPolicy)
            .where(or_(*conditions))
            .order_by(GovernmentPolicy.announcement_date.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def upsert(self, data: dict) -> GovernmentPolicy:
        existing = await self.get_by_external_id(data["external_id"])
        if existing:
            for k, v in data.items():
                setattr(existing, k, v)
            await self._db.flush()
            return existing
        policy = GovernmentPolicy(**data)
        self._db.add(policy)
        await self._db.flush()
        return policy

