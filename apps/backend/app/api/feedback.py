"""
Feedback API — receives submissions from the /contact page form, and from
the returning-user feedback popup (see ReturningUserFeedbackModal.tsx).

POST /api/feedback/                 -> store a new feedback/support/query submission
POST /api/feedback/returning-user   -> store returning-user product feedback + email it
"""
from __future__ import annotations

import re

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.limiter import limiter
from app.db.models.feedback import FeedbackSubmission
from app.db.models.returning_user_feedback import ReturningUserFeedback
from app.db.session import get_db
from app.services.email_service import send_email

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


def _build_contact_email_body(body: FeedbackIn) -> str:
    lines = [
        f"Category: {body.category}",
        f"From: {body.name or '(no name given)'} <{body.email}>",
    ]
    if body.page_url:
        lines.append(f"Page: {body.page_url}")
    lines += ["", "Message:", body.message]
    return "\n".join(lines)


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

    # Same best-effort posture as the returning-user popup below: the DB
    # row is the durable record, email is a notification on top of it that
    # never fails the request (see email_service.py's docstring). This
    # endpoint never had a notification wired up at all before now — a
    # contact-form submission with no one ever notified isn't a working
    # contact form, just a write-only log.
    sent = await send_email(
        to=settings.feedback_notify_email,
        subject=f"Market Ripple — Contact Form ({body.category})",
        body=_build_contact_email_body(body),
    )
    log.info("feedback.submitted", category=body.category, id=submission.id, emailed=sent)
    return {"ok": True, "id": submission.id}


# ── Returning-user feedback popup ───────────────────────────────────────────

def _clean_list(v: list[str] | None, max_items: int = 10, max_len: int = 120) -> list[str]:
    if not v:
        return []
    return [s.strip()[:max_len] for s in v if isinstance(s, str) and s.strip()][:max_items]


class ReturningUserFeedbackIn(BaseModel):
    name: str | None = None
    email: str | None = None
    reasons: list[str] = []
    improvements: list[str] = []
    other_reason: str | None = None
    other_improvement: str | None = None
    additional_feedback: str | None = None
    visit_count: int | None = None
    page: str | None = None
    device_category: str | None = None
    referrer: str | None = None

    @field_validator("name")
    @classmethod
    def _clean_name(cls, v: str | None) -> str | None:
        return v.strip()[:128] or None if v else None

    # Optional here (unlike the /contact form's required email) — this
    # popup is a passive product-feedback prompt, not a support request
    # expecting a reply, so identifying yourself is opt-in. Still validated
    # as a real email shape when the visitor does provide one, same regex
    # as FeedbackIn above, so a malformed value doesn't silently save.
    @field_validator("email")
    @classmethod
    def _valid_optional_email(cls, v: str | None) -> str | None:
        if not v or not v.strip():
            return None
        v = v.strip()
        if not _EMAIL_RE.match(v):
            raise ValueError("Enter a valid email address")
        return v

    @field_validator("reasons", "improvements")
    @classmethod
    def _clean_reasons(cls, v: list[str]) -> list[str]:
        return _clean_list(v)

    @field_validator("other_reason", "other_improvement")
    @classmethod
    def _clean_other(cls, v: str | None) -> str | None:
        return v.strip()[:280] or None if v else None

    @field_validator("additional_feedback")
    @classmethod
    def _clean_additional(cls, v: str | None) -> str | None:
        return v.strip()[:3000] or None if v else None

    @field_validator("page", "referrer")
    @classmethod
    def _clean_url(cls, v: str | None) -> str | None:
        return v.strip()[:500] or None if v else None

    @field_validator("device_category")
    @classmethod
    def _clean_device(cls, v: str | None) -> str | None:
        return v.strip()[:32] or None if v else None

    @field_validator("visit_count")
    @classmethod
    def _clean_visit_count(cls, v: int | None) -> int | None:
        if v is None:
            return None
        return max(0, min(v, 100_000))


def _format_bullets(items: list[str]) -> str:
    return "\n".join(f"• {i}" for i in items)


def _build_email_body(body: "ReturningUserFeedbackIn") -> str:
    sections = ["RETURNING USER FEEDBACK", ""]

    reasons = list(body.reasons) + ([body.other_reason] if body.other_reason else [])
    if reasons:
        sections += ["Why they returned:", _format_bullets(reasons), ""]

    improvements = list(body.improvements) + ([body.other_improvement] if body.other_improvement else [])
    if improvements:
        sections += ["What would make Market Ripple more useful:", _format_bullets(improvements), ""]

    if body.additional_feedback:
        sections += ["Additional feedback:", f'"{body.additional_feedback}"', ""]

    context_lines = []
    if body.name:
        context_lines.append(f"Name: {body.name}")
    if body.email:
        context_lines.append(f"Email: {body.email}")
    if body.visit_count is not None:
        context_lines.append(f"Visit count: {body.visit_count}")
    if body.page:
        context_lines.append(f"Current page: {body.page}")
    if body.device_category:
        context_lines.append(f"Device: {body.device_category}")
    if body.referrer:
        context_lines.append(f"Referrer: {body.referrer}")
    from datetime import datetime, timezone
    context_lines.append(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    sections += ["Context:", "\n".join(context_lines)]

    return "\n".join(sections)


@router.post("/returning-user")
@limiter.limit("5/minute")
async def submit_returning_user_feedback(
    request: Request, body: ReturningUserFeedbackIn, db: AsyncSession = Depends(get_db)
):
    submission = ReturningUserFeedback(
        name=body.name,
        email=body.email,
        reasons=body.reasons,
        improvements=body.improvements,
        other_reason=body.other_reason,
        other_improvement=body.other_improvement,
        additional_feedback=body.additional_feedback,
        visit_count=body.visit_count,
        page=body.page,
        device_category=body.device_category,
        referrer=body.referrer,
    )
    db.add(submission)
    try:
        await db.commit()
    except Exception as exc:
        await db.rollback()
        log.error("returning_user_feedback.save_failed", error=str(exc))
        raise HTTPException(status_code=500, detail="Could not save your feedback. Please try again.")

    # The DB row is the durable record; email is a best-effort notification
    # on top of it — a failed send doesn't fail the request or lose the
    # feedback (see email_service.py's docstring).
    sent = await send_email(
        to=settings.feedback_notify_email,
        subject="Market Ripple — Returning User Feedback",
        body=_build_email_body(body),
    )
    log.info("returning_user_feedback.submitted", id=submission.id, emailed=sent)
    return {"ok": True, "id": submission.id}
