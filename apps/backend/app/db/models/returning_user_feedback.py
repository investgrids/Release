import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime, Integer, JSON
from app.db.base import Base


def _now():
    return datetime.now(timezone.utc)


class ReturningUserFeedback(Base):
    """Feedback captured from the returning-user popup (why they came back,
    what would make the product more useful). Deliberately separate from
    FeedbackSubmission (contact-form messages) — different shape (multi-
    select arrays), though it now optionally collects name/email too (an
    explicit product decision to let a returning user identify themselves
    if they want a reply, without requiring it)."""
    __tablename__ = "returning_user_feedback"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(128), nullable=True)
    email = Column(String(320), nullable=True)
    reasons = Column(JSON, nullable=False, default=list)
    improvements = Column(JSON, nullable=False, default=list)
    other_reason = Column(String(280), nullable=True)
    other_improvement = Column(String(280), nullable=True)
    additional_feedback = Column(Text, nullable=True)
    visit_count = Column(Integer, nullable=True)
    page = Column(String(500), nullable=True)
    device_category = Column(String(32), nullable=True)
    referrer = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now, index=True)
