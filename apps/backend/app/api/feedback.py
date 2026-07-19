"""
Feedback API — receives submissions from the /contact page form.

POST /api/feedback/  -> store a new feedback/support/query submission
"""
from __future__ import annotations

import re

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.limiter import limiter
from app.db.models.feedback import FeedbackSubmission
from app.db.session import get_db

log = structlog.get_logger(__name__)
router = APIRouter()

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_VALID_CATEGORIES = {
    "general", "support", "feedback", "business", "partnership", "media", "bug", "pro_interest",
}


class FeedbackIn(BaseModel):
    name: str | None = None
    email: str
    category: str = "general"
    message: str
    page_url: str | None = None

    @field_validator("email")
    @classmethod
    def _valid_email(cls, v: str) -> str:
        v = v.strip()
        if not _EMAIL_RE.match(v):
            raise ValueError("Enter a valid email address")
        return v

    @field_validator("message")
    @classmethod
    def _valid_message(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 10:
            raise ValueError("Message must be at least 10 characters")
        if len(v) > 5000:
            v = v[:5000]
        return v

    @field_validator("category")
    @classmethod
    def _valid_category(cls, v: str) -> str:
        return v if v in _VALID_CATEGORIES else "general"

    @field_validator("name")
    @classmethod
    def _clean_name(cls, v: str | None) -> str | None:
        return v.strip()[:128] if v else None


@router.post("/")
@limiter.limit("5/minute")
async def submit_feedback(request: Request, body: FeedbackIn, db: AsyncSession = Depends(get_db)):
    submission = FeedbackSubmission(
        name=body.name,
        email=body.email,
        category=body.category,
        message=body.message,
        page_url=(body.page_url or "")[:500] or None,
    )
    db.add(submission)
    try:
        await db.commit()
    except Exception as exc:
        await db.rollback()
        log.error("feedback.submit_failed", error=str(exc))
        raise HTTPException(status_code=500, detail="Could not save your message. Please try again.")

    log.info("feedback.submitted", category=body.category, id=submission.id)
    return {"ok": True, "id": submission.id}
