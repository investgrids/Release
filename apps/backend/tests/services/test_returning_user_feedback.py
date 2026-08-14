"""
Regression suite — the optional name/email fields added to the returning-
user feedback popup (ReturningUserFeedbackModal.tsx + ReturningUserFeedback
model). Covers Pydantic validation (format-checked but never required) and
a real DB round-trip.
"""
from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError
from sqlalchemy import delete, select

from app.api.feedback import ReturningUserFeedbackIn
from app.db.session import AsyncSessionLocal
from app.db.models.returning_user_feedback import ReturningUserFeedback


def test_name_and_email_default_to_none():
    body = ReturningUserFeedbackIn()
    assert body.name is None
    assert body.email is None


def test_blank_strings_normalize_to_none():
    body = ReturningUserFeedbackIn(name="   ", email="   ")
    assert body.name is None
    assert body.email is None


def test_valid_email_accepted():
    body = ReturningUserFeedbackIn(email="visitor@example.com")
    assert body.email == "visitor@example.com"


def test_invalid_email_rejected():
    with pytest.raises(ValidationError):
        ReturningUserFeedbackIn(email="not-an-email")


def test_name_trimmed_and_length_capped():
    body = ReturningUserFeedbackIn(name="  " + ("x" * 200) + "  ")
    assert body.name is not None
    assert len(body.name) == 128
    assert not body.name.startswith(" ")


@pytest.mark.asyncio
async def test_returning_user_feedback_persists_name_and_email():
    test_id = f"pytest-rufb-{uuid.uuid4().hex[:8]}"
    async with AsyncSessionLocal() as db:
        await db.execute(delete(ReturningUserFeedback).where(ReturningUserFeedback.id == test_id))
        await db.commit()
    try:
        async with AsyncSessionLocal() as db:
            db.add(ReturningUserFeedback(
                id=test_id, name="Test User", email="test@example.com",
                reasons=["research_company"], improvements=[],
            ))
            await db.commit()

            row = (await db.execute(
                select(ReturningUserFeedback).where(ReturningUserFeedback.id == test_id)
            )).scalar_one()
            assert row.name == "Test User"
            assert row.email == "test@example.com"
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(delete(ReturningUserFeedback).where(ReturningUserFeedback.id == test_id))
            await db.commit()


@pytest.mark.asyncio
async def test_returning_user_feedback_allows_null_name_and_email():
    # The whole point of making these optional — a submission with neither
    # must still save cleanly, not be coerced into an empty string.
    test_id = f"pytest-rufb-null-{uuid.uuid4().hex[:8]}"
    async with AsyncSessionLocal() as db:
        await db.execute(delete(ReturningUserFeedback).where(ReturningUserFeedback.id == test_id))
        await db.commit()
    try:
        async with AsyncSessionLocal() as db:
            db.add(ReturningUserFeedback(id=test_id, reasons=[], improvements=[]))
            await db.commit()

            row = (await db.execute(
                select(ReturningUserFeedback).where(ReturningUserFeedback.id == test_id)
            )).scalar_one()
            assert row.name is None
            assert row.email is None
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(delete(ReturningUserFeedback).where(ReturningUserFeedback.id == test_id))
            await db.commit()
