import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String, Text

from app.db.base import Base


def _now():
    return datetime.now(timezone.utc)


class AISearchFollowupClick(Base):
    """Real click events on Follow-up Intelligence suggestions (Phase 1.6) —
    the data-capture half of the spec's "Learning System (Future-ready)":
    which category/item actually gets clicked, from which position, from
    which original answer. Deliberately just the capture, not the ranking
    algorithm — the spec calls the ranking itself future work; this table
    is what that future work would train on."""
    __tablename__ = "ai_search_followup_clicks"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    response_id = Column(String(64), nullable=False, index=True)
    category = Column(String(32), nullable=False, index=True)  # risks | compare | portfolio | deeper | macro | horizon | ripple
    item_text = Column(Text, nullable=False)
    item_query = Column(Text, nullable=False)
    position = Column(Integer, nullable=True)  # index within its category, 0-based
    created_at = Column(DateTime(timezone=True), default=_now, index=True)
