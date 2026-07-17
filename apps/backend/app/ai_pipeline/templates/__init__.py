"""Importing this package registers every template module as a side effect."""
from __future__ import annotations

from app.ai_pipeline.templates import (  # noqa: F401
    briefing_template,
    education_template,
    exploratory_template,
    impact_template,
    profile_template,
    verdict_template,
)
