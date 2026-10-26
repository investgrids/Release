"""AI usage cost layer (additive on trunk's ai_usage): pricing version/currency
metadata in usage_report, the honesty fix in get_ai_usage_stats, and the
daily_brief operation tag. Self-contained (own in-memory DB; no shared
fixtures)."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from app.services import ai_usage
from app.services import ai_service


# ── pricing metadata constants ──────────────────────────────────────────────

def test_prices_version_and_currency_are_declared():
    assert isinstance(ai_usage.PRICES_VERSION, str) and ai_usage.PRICES_VERSION
    assert ai_usage.CURRENCY == "USD"


# ── get_ai_usage_stats honesty fix ──────────────────────────────────────────

def test_ops_stats_no_longer_fabricate_cost():
    stats = ai_service.get_ai_usage_stats()
    # The misleading hard-coded cost_usd: 0.0 is gone from the in-process stats.
    assert "cost_usd" not in stats
    # ...and it points at the DB-backed report instead.
    assert stats.get("cost_source") == "not_priced_in_process"
    assert "usage_report" in stats.get("cost_report", "")


# ── usage_report exposes pricing metadata + honest gaps ─────────────────────

def test_usage_report_exposes_pricing_metadata_and_zero_free_tier_cost():
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from app.db.models.ai_usage import AIUsageAttempt, AISearchRequestLog

    async def run():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(lambda c: AIUsageAttempt.__table__.create(c))
            await conn.run_sync(lambda c: AISearchRequestLog.__table__.create(c))
        Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with Session() as db:
            db.add(AIUsageAttempt(
                ts=datetime.now(timezone.utc).replace(tzinfo=None),
                operation="ai_search", call_id="c1", provider="groq",
                model="llama-x", outcome="success", latency_ms=100,
                input_tokens=100, output_tokens=50, usage_source="provider", n=1,
            ))
            await db.commit()
            rep = await ai_usage.usage_report(db, hours=24)
        await engine.dispose()
        return rep

    rep = asyncio.run(run())
    pricing = rep["pricing"]
    assert pricing["version"] == ai_usage.PRICES_VERSION
    assert pricing["currency"] == ai_usage.CURRENCY
    assert "infrastructure" in pricing["scope"].lower()
    assert any("estimate" in g.lower() and "infrastructure" in g.lower() for g in rep["gaps"])
    # free-tier groq: priced at 0, covered (not unpriced)
    f = rep["features"]["ai_search"]
    assert f["cost_usd"] == 0.0
    assert f["cost_covered_attempts"] == 1
    assert f["cost_unpriced_attempts"] == 0


# ── daily_brief operation tag ───────────────────────────────────────────────

def test_daily_brief_handler_tags_operation(monkeypatch):
    """The /intelligence handler must run its body inside
    ai_usage.operation("daily_brief") so nested LLM attempts are attributed to
    the brief journey."""
    from app.api import daily_brief_intelligence as mod

    seen = {}

    async def _stub():
        seen["op"] = ai_usage._operation.get()
        return {"ok": True}

    monkeypatch.setattr(mod, "_get_daily_brief_intelligence", _stub)
    out = asyncio.run(mod.get_daily_brief_intelligence())
    assert out == {"ok": True}
    assert seen["op"] == "daily_brief"
    # and it resets afterwards (no leak)
    assert ai_usage._operation.get() != "daily_brief"
