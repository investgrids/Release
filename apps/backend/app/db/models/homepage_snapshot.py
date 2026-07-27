import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, JSON, String, UniqueConstraint

from app.db.base import Base


def _now():
    return datetime.now(timezone.utc)


def _today():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


class HomepageDailySnapshot(Base):
    """One row per day — the persistence layer behind Homepage Intelligence's
    "What Changed Since Yesterday". Sourced from the SAME single source of
    truth the rest of the homepage's AI narrative already uses (the real
    AIPE morning_intelligence article's own sectors_affected field — see
    page.tsx's AIMarketBriefCard docstring: "Deliberately not blending in
    MIE or any other pipeline here"). Never a second, competing signal.

    Written lazily (first homepage-intelligence request of the day) rather
    than on a schedule — simplest correct approach, same reasoning as
    Investment Watch's verdict snapshots.
    """
    __tablename__ = "homepage_daily_snapshots"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    snapshot_date = Column(String(10), nullable=False, index=True)  # YYYY-MM-DD, UTC
    article_id = Column(String(64), nullable=True)
    # [{"name": "Banking", "impact": "positive", "magnitude": "medium", "score": 1}]
    sectors = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime(timezone=True), default=_now)

    __table_args__ = (
        UniqueConstraint("snapshot_date", name="uq_homepage_snapshot_date"),
    )
