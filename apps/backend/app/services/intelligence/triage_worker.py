"""
TriageWorker — consumes RawEvents from the bus, calls AI to score each one,
then routes by urgency:
  >= 7  → SSE broadcast + DB store
  4–6   → DB store (enriched later)
  < 4   → DB store only
"""
from __future__ import annotations

import asyncio
import json
import structlog
from datetime import datetime, timezone
from uuid import uuid4

from app.services.intelligence.event_bus import (
    get_event_bus, get_broadcaster, RawEvent, TriagedEvent,
)

log = structlog.get_logger(__name__)

_TRIAGE_SYSTEM = """You are an AI market event classifier for Indian stock markets.
Given a market event, return a JSON object with exactly these fields:
{
  "urgency": 0-10,
  "importance": 0-10,
  "confidence": 0-10,
  "sentiment": "bullish" | "bearish" | "neutral",
  "horizon": "intraday" | "short" | "long",
  "market_impact": "high" | "medium" | "low",
  "is_structural": true | false,
  "direction": "up" | "down" | "sideways",
  "one_liner": "one sentence: what this means for Indian markets right now",
  "themes": ["theme1"],
  "sectors": ["sector1"],
  "tickers": ["NSE_SYMBOL"]
}
Urgency guide: 10=war/circuit breaker, 8-9=RBI rate decision/major miss,
6-7=sector catalyst/large deal, 4-5=earnings/policy update, 1-3=routine news.
Return only valid JSON."""


def _rule_based_fallback(headline: str) -> dict:
    h = headline.lower()
    urgency = 3
    if any(w in h for w in ["rbi", "rate cut", "rate hike", "emergency", "circuit"]):
        urgency = 8
    elif any(w in h for w in ["results", "earnings", "quarterly", "q4", "q3"]):
        urgency = 6
    elif any(w in h for w in ["crash", "surge", "rally", "sell-off", "collapse"]):
        urgency = 7
    elif any(w in h for w in ["merger", "acquisition", "deal", "order"]):
        urgency = 6
    return {
        "urgency": urgency, "importance": 5, "confidence": 4,
        "sentiment": "neutral", "horizon": "short", "market_impact": "medium",
        "is_structural": False, "direction": "sideways",
        "one_liner": headline[:200], "themes": [], "sectors": [], "tickers": [],
    }


async def _ai_triage(headline: str, summary: str) -> dict:
    from app.services.ai_service import _call_with_fallback  # noqa: PLC2701
    prompt = f"Headline: {headline}\n\nSummary: {summary[:500]}"
    try:
        raw = await _call_with_fallback(prompt, _TRIAGE_SYSTEM, max_tokens=400)
        if not raw:
            return _rule_based_fallback(headline)
        text = raw.strip()
        if "```" in text:
            parts = text.split("```")
            text = parts[1] if len(parts) > 1 else text
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text.strip())
    except Exception:
        return _rule_based_fallback(headline)


async def _store_triage(triage: TriagedEvent) -> None:
    from app.db.session import AsyncSessionLocal
    from app.db.models.intelligence import EventTriage

    triage_id = str(uuid4())[:16]
    try:
        async with AsyncSessionLocal() as db:
            db.add(EventTriage(
                id=triage_id,
                event_id=triage.raw.id,
                source=triage.raw.source,
                headline=triage.raw.headline[:512],
                urgency=triage.urgency,
                importance=triage.importance,
                confidence=triage.confidence,
                sentiment=triage.sentiment,
                horizon=triage.horizon,
                market_impact=triage.market_impact,
                is_structural=triage.is_structural,
                direction=triage.direction,
                one_liner=triage.one_liner,
                themes=triage.themes,
                sectors=triage.sectors,
                tickers=triage.tickers,
                broadcast=triage.broadcast,
                refresh_homepage=triage.refresh_homepage,
            ))
            await db.commit()
    except Exception as exc:
        log.error("triage.store_failed", error=str(exc))


class TriageWorker:
    def __init__(self) -> None:
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._run(), name="triage-worker")
        log.info("triage_worker.started")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        log.info("triage_worker.stopped")

    async def _run(self) -> None:
        bus = get_event_bus()
        broadcaster = get_broadcaster()

        while self._running:
            try:
                raw = await asyncio.wait_for(bus.consume(), timeout=5.0)
            except asyncio.TimeoutError:
                continue
            except Exception as exc:
                log.error("triage_worker.consume_error", error=str(exc))
                await asyncio.sleep(1)
                continue

            try:
                scores = await _ai_triage(raw.headline, raw.summary)
                urgency = min(10, max(0, int(scores.get("urgency", 3))))

                triage = TriagedEvent(
                    raw=raw,
                    urgency=urgency,
                    importance=min(10, max(0, int(scores.get("importance", 5)))),
                    confidence=min(10, max(0, int(scores.get("confidence", 5)))),
                    sentiment=str(scores.get("sentiment", "neutral")),
                    horizon=str(scores.get("horizon", "short")),
                    market_impact=str(scores.get("market_impact", "medium")),
                    is_structural=bool(scores.get("is_structural", False)),
                    direction=str(scores.get("direction", "sideways")),
                    one_liner=str(scores.get("one_liner", raw.headline))[:500],
                    themes=list(scores.get("themes", []))[:8],
                    sectors=list(scores.get("sectors", []))[:6],
                    tickers=list(scores.get("tickers", []))[:10],
                    broadcast=urgency >= 7,
                    refresh_homepage=urgency >= 8,
                )

                await _store_triage(triage)

                # Store prediction for the learning engine (urgency ≥ 7 = confident enough)
                if urgency >= 7:
                    try:
                        from app.services.prediction_service import store_prediction, SECTOR_TICKERS
                        _t_dir    = str(scores.get("direction", "sideways"))
                        if _t_dir not in ("up", "down", "sideways"): _t_dir = "sideways"
                        _t_horiz  = {"intraday": 1, "short": 3, "long": 7}.get(str(triage.horizon), 7)
                        _t_ents   = []
                        for _sym in (triage.tickers or [])[:2]:
                            _t_ents.append({"type": "company", "symbol": _sym, "name": _sym, "ticker": _sym})
                        for _sec in (triage.sectors or [])[:1]:
                            _sec_lower = _sec.lower()
                            _sec_tick  = next((v for k, v in SECTOR_TICKERS.items() if k in _sec_lower), None)
                            if _sec_tick:
                                _t_ents.append({"type": "sector", "name": _sec, "baseline_ticker": _sec_tick})
                        if _t_ents:
                            asyncio.create_task(store_prediction(
                                source="triage",
                                prediction_text=triage.one_liner[:400],
                                direction=_t_dir,
                                prediction_type="overall",
                                target_entities=_t_ents,
                                confidence_score=float(triage.confidence) * 10,
                                confidence_level=(
                                    "Very High" if triage.confidence >= 9 else
                                    "High"      if triage.confidence >= 7 else
                                    "Medium"    if triage.confidence >= 5 else "Low"
                                ),
                                horizon_days=_t_horiz,
                                headline=raw.headline[:400],
                            ), name="triage-prediction-store")
                    except Exception:
                        pass

                # Auto-harvest high-urgency events into Historical Market Memory
                if urgency >= 8:
                    try:
                        from app.services.historical_memory_service import store_event as _store_hist
                        asyncio.create_task(_store_hist({
                            "event_title":   raw.headline[:200],
                            "event_date":    datetime.now(timezone.utc),
                            "category":      (triage.themes[0] if triage.themes else "General"),
                            "sentiment":     triage.sentiment,
                            "sectors":       triage.sectors,
                            "companies":     triage.tickers,
                            "tags":          triage.themes,
                            "source":        "auto_triage",
                            "what_happened": triage.one_liner,
                            "confidence":    float(triage.confidence) * 10,
                        }), name="historical-harvest")
                    except Exception:
                        pass

                # Auto-update the Market Intelligence Graph with new entities
                if urgency >= 6:
                    try:
                        from app.services.intelligence_graph_service import update_from_event
                        asyncio.create_task(update_from_event({
                            "id":       raw.id,
                            "headline": raw.headline,
                            "sectors":  triage.sectors,
                            "companies": [{"symbol": t} for t in triage.tickers],
                            "sentiment": triage.sentiment,
                            "urgency":   urgency,
                        }), name="graph-auto-update")
                    except Exception:
                        pass

                if urgency >= 7:
                    await broadcaster.broadcast(triage)
                    log.info(
                        "triage.broadcast",
                        headline=raw.headline[:60],
                        urgency=urgency,
                        subscribers=broadcaster.subscriber_count,
                    )

                bus.task_done()
                await asyncio.sleep(0.5)

            except Exception as exc:
                log.error("triage_worker.process_error", error=str(exc))
                bus.task_done()
                await asyncio.sleep(1)


_worker: TriageWorker | None = None


def get_triage_worker() -> TriageWorker:
    global _worker
    if _worker is None:
        _worker = TriageWorker()
    return _worker
