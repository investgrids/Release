"""Company intelligence: short cache (never for unavailable results) and the non-DB lookups overlapping the session's queries."""
import asyncio

import pytest

from app.services import company_intelligence as ci


async def test_available_result_is_cached_per_symbol_and_params_but_unavailable_is_not(monkeypatch):
    ci._INTEL_CACHE.clear()
    calls = []

    async def fake_build(db, symbol, gov, pos):
        calls.append((symbol, gov, pos))
        return {"available": symbol != "NOPE", "symbol": symbol}

    monkeypatch.setattr(ci, "_build_company_intelligence", fake_build)
    a = await ci.get_company_intelligence(None, "tcs", 30.0, True)
    b = await ci.get_company_intelligence(None, "TCS", 30.0, True)
    assert a is b and len(calls) == 1                                   # same symbol/params: served from cache
    await ci.get_company_intelligence(None, "TCS", 31.0, True)           # different params: built again
    await ci.get_company_intelligence(None, "NOPE")
    await ci.get_company_intelligence(None, "NOPE")
    assert len(calls) == 4                                              # unavailable is never cached
    ci._INTEL_CACHE.clear()


async def test_ripple_and_historical_run_alongside_the_session_queries(monkeypatch):
    ci._INTEL_CACHE.clear()
    from app.api import companies
    from app.services.ai_search import investment_watch as watch_mod
    monkeypatch.setattr(companies, "_NSE_UNIVERSE", [{"symbol": "TCS", "name": "Tata Consultancy", "sector": "Technology"}])
    order = []

    async def slow_ripple(symbol, sector):
        order.append("ripple_start"); await asyncio.sleep(0.05); order.append("ripple_end")
        return {"upstream": [], "company": symbol, "downstream": []}

    async def slow_hist(sector, name):
        order.append("hist_start"); await asyncio.sleep(0.05); order.append("hist_end")
        return None

    async def events(db, symbol, sector, limit=4):
        order.append("events"); await asyncio.sleep(0.02); return []

    async def opps(db, symbol, limit=3):
        order.append("opps"); return []

    async def watch(db, key, label):
        return None

    monkeypatch.setattr(ci, "get_ripple_position", slow_ripple)
    monkeypatch.setattr(ci, "get_historical", slow_hist)
    monkeypatch.setattr(ci, "get_active_events", events)
    monkeypatch.setattr(ci, "get_related_opportunities", opps)
    monkeypatch.setattr(watch_mod, "get_watch", watch)
    out = await ci.get_company_intelligence(None, "TCS")
    assert out["available"] is True
    # the DB-bound queries ran while the two independent lookups were still in flight
    assert order.index("events") < order.index("ripple_end") and order.index("opps") < order.index("hist_end")
    ci._INTEL_CACHE.clear()
