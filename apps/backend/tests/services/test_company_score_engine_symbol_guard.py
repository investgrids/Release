"""
Name<->symbol extraction guard (2026-08-25) — real cases from the cross-
sector companies_affected extraction audit (artifacts/company_signal_
cross_sector_audit.md). Validates the deterministic guard both as pure
functions and end-to-end through extract_company_signals(), confirming
it corrects the 3 real defects the audit found, leaves genuinely
unresolvable/brand-name cases untouched (never destroys valid evidence
on a guess), and now also enforces _is_real_symbol()'s real-symbol check
at write time instead of only downstream.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import delete

from app.db.models.company_signal import AICompanySignal
from app.db.models.intelligence_article import IntelligenceArticle
from app.db.session import AsyncSessionLocal
from app.services.aipe import company_score_engine as engine


def _tag():
    return uuid.uuid4().hex[:8]


@pytest.mark.parametrize("symbol,name,expected", [
    ("PNB", "PNB Housing Finance", "PNBHOUSING"),         # real audit defect #4
    ("HDFCBANK", "HDB Financial Services", "HDBFS"),      # real defect found validating the guard
    ("SRF", "Shriram Finance", "SHRIRAMFIN"),             # real defect found validating the guard
    ("SBIN", "SBI", "SBIN"),                              # standard initialism, must not be flagged
    ("SBIN", "State Bank of India", "SBIN"),              # exact real name
    ("PNB", "PNB", "PNB"),                                # signal_publisher.py's name==symbol placeholder pattern
    ("BSE", "Bombay Stock Exchange", "BSE"),              # real name is itself already the acronym form
    ("NYKAA", "Nykaa Retail Limited", "NYKAA"),           # real brand-vs-legal-name difference, must stay unchanged
    ("RHIM", "Reliance Home Finance", "RHIM"),            # unresolvable in current universe, must stay unchanged not dropped
    ("ICICIBANK", "ICICIBANK.NS", "ICICIBANK"),           # suffix noise, must stay unchanged
    ("NIFTY_IT", "Nifty IT Index", None),                 # not a real company at all
    ("ICICIBANK, KOTAKBANK", "ICICI Bank", None),         # malformed unsplit multi-symbol string
])
def test_validated_symbol_real_cases(symbol, name, expected):
    assert engine._validated_symbol(symbol, name) == expected


@pytest.mark.asyncio
async def test_extract_company_signals_applies_symbol_guard():
    tag = _tag()
    article_id = f"pytest-guard-{tag}"
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        db.add(IntelligenceArticle(
            id=article_id, headline=f"Test symbol-guard article {tag}",
            article_type="policy_intelligence", status="published",
            lifecycle_status="published", is_evergreen=False, created_at=now,
            published_at=now, event_score=50.0, confidence_score=0.8, quality_score=0.9,
            companies_affected=[
                {"name": "PNB Housing Finance", "symbol": "PNB", "impact": "negative", "reason": "guard test — should correct to PNBHOUSING"},
                {"name": "ICICI Bank Ltd", "symbol": "ICICIBANK", "impact": "positive", "reason": "guard test — should pass through unchanged"},
                {"name": "Nifty IT Index", "symbol": "NIFTY_IT", "impact": "neutral", "reason": "guard test — not a real company, should be dropped"},
            ],
        ))
        await db.commit()

        created = await engine.extract_company_signals(db, await db.get(IntelligenceArticle, article_id))
        assert created == 2  # the NIFTY_IT entry is dropped, not written

        from sqlalchemy import select
        rows = (await db.execute(
            select(AICompanySignal.symbol).where(AICompanySignal.source_id == article_id)
        )).scalars().all()
        symbols = sorted(rows)
        assert symbols == ["ICICIBANK", "PNBHOUSING"]  # PNB was corrected to PNBHOUSING; NIFTY_IT never got written

        await db.execute(delete(AICompanySignal).where(AICompanySignal.source_id == article_id))
        await db.execute(delete(IntelligenceArticle).where(IntelligenceArticle.id == article_id))
        await db.commit()
