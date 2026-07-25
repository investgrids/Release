"""
GeneratedMedia — generic, reusable media-asset pipeline, not a single
`hero_image_url` column on IntelligenceArticle.

Why a separate table: one article eventually needs several distinct
generated assets (hero image, Open Graph image, social share image, mobile
thumbnail, square thumbnail, search-result thumbnail) — a growing set of
flat columns doesn't scale to that, and can't hold per-asset generation
history (provider, exact prompt, prompt version) needed to regenerate an
asset later after the style guide improves. One row per asset, keyed by
(article_id, media_type), keeps that open-ended without a schema change
each time a new asset type is added.

Lifecycle: pending -> generating -> generated | failed (retried) | fallback
(retries exhausted — frontend uses the built-in gradient/icon art forever).
Never blocks article publication — a row here is created at publish time,
generation happens later on its own schedule (see app/services/media/).
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text

from app.db.base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class GeneratedMedia(Base):
    __tablename__ = "generated_media"

    id         = Column(String, primary_key=True, index=True)
    article_id = Column(String, ForeignKey("intelligence_articles.id", ondelete="CASCADE"), nullable=False, index=True)

    # hero | og | social | thumbnail_mobile | thumbnail_square | thumbnail_search
    media_type = Column(String(32), nullable=False, default="hero", index=True)

    # pending | generating | generated | failed | fallback
    status     = Column(String(16), nullable=False, default="pending", index=True)

    provider   = Column(String(32), nullable=True)   # e.g. "pollinations"
    prompt     = Column(Text, nullable=True)          # exact prompt sent to the provider
    prompt_version = Column(String(16), nullable=True) # style-guide version, e.g. "v1"
    style      = Column(String(64), nullable=True)     # named style preset, e.g. "editorial-navy"

    url        = Column(Text, nullable=True)           # served path once generated
    error      = Column(Text, nullable=True)            # last failure reason, if any
    attempts   = Column(Integer, nullable=False, default=0)

    created_at    = Column(DateTime, nullable=False, default=_now)
    generated_at  = Column(DateTime, nullable=True)
