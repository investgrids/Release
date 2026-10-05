"""Step 6: Page Intelligence never invents a confidence level or score. Missing confidence is unscored (null), not "Medium / 60"."""
import asyncio

from app.services import page_intelligence_service as svc


def test_search_intelligence_without_confidence_is_unscored(monkeypatch):
    raw = {
        "answer": {"summary": "s", "immediate_impact": "i", "opportunities": ["an opportunity"], "risks": ["a risk"]},
        "companies": [{"symbol": "TCS", "name": "TCS", "reason": "r"}],
        "sectors": [{"name": "IT", "positive": True}],
        # no confidence_data: the public contract no longer carries answer confidence
    }

    async def fake_v3(q, db):
        return raw, False

    class _Ctx:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, *a):
            return False

    import app.services.ai_search.pipeline as pipeline
    import app.db.session as session

    monkeypatch.setattr(pipeline, "run_ai_search_v3", fake_v3)
    monkeypatch.setattr(session, "AsyncSessionLocal", lambda: _Ctx())
    svc.invalidate("search", "unscored probe query")
    out = asyncio.run(svc.get_search_intelligence("unscored probe query"))

    assert out["confidence"]["level"] == "unscored"
    assert out["confidence"]["score"] is None
    assert out["companies"][0]["confidence"] is None
    assert out["sectors"][0]["score"] is None
    assert out["opportunities"][0]["confidence"] is None


def test_generic_fallback_is_unscored():
    out = svc._fallback("search", "x")
    assert out["confidence"]["level"] == "unscored" and out["confidence"]["score"] is None
