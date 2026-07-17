"""Importing this package registers every intent module as a side effect."""
from __future__ import annotations

from app.ai_pipeline.intent import (  # noqa: F401
    company_analysis,
    company_comparison,
    economic_analysis,
    event_impact,
    general_education,
    historical_analysis,
    investment_decision,
    market_outlook,
    news_intelligence,
    policy_analysis,
    portfolio,
    risk_analysis,
    ripple_analysis,
    sector_analysis,
    theme_discovery,
)
