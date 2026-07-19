import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime, Boolean
from app.db.base import Base


def _now():
    return datetime.now(timezone.utc)


class FeedbackSubmission(Base):
    """User-submitted feedback/support/query messages from the /contact page."""
    __tablename__ = "feedback_submissions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(128), nullable=True)
    email = Column(String(256), nullable=False, index=True)
    category = Column(String(32), nullable=False, default="general")
    # general | support | feedback | business | partnership | media | bug | pro_interest
    message = Column(Text, nullable=False)
    page_url = Column(Text, nullable=True)
    status = Column(String(16), nullable=False, default="new", index=True)
    # new | read | resolved
    created_at = Column(DateTime(timezone=True), default=_now, index=True)
