"""
TriageWorker — consumes RawEvents from the bus, calls AI to score each one,
then routes by urgency:
  >= 7  → SSE broadcast + DB store
  4–6   → DB store (enriched later)
  < 4   → DB store only

Observability note: when the AI scoring call fails outright (every provider
in _call_with_fallback's chain exhausted/erroring), urgency silently
degrades to _rule_based_fallback's keyword heuristic — which defaults to
urgency=3 (below the >=6 publish threshold) for anything not matching a
narrow keyword list. _ai_triage logs a structured "triage.fallback_to_
rule_based" event every time this happens (headline, which providers
failed and why, the fallback-assigned urgency, and which keyword category
if any matched) plus "triage.ai_scored_low_urgency" whenever the AI *did*
respond but scored below 6 — the second gives a baseline to compare
against, so a burst of fallback events can be judged against how often the
AI itself would have scored the same headlines low anyway. Pure
visibility — this doesn't change retry/fallback behavior.
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


_FALLBACK_KEYWORD_CATEGORIES: list[tuple[str, int, list[str]]] = [
    ("rate_or_emergency", 8, ["rbi", "rate cut", "rate hike", "emergency", "circuit"]),
    ("crash_or_rally", 7, ["crash", "surge", "rally", "sell-off", "collapse"]),
    ("earnings", 6, ["results", "earnings", "quarterly", "q4", "q3"]),
    ("deal", 6, ["merger", "acquisition", "deal", "order"]),
]


def _rule_based_fallback(headline: str) -> dict:
    h = headline.lower()
    urgency = 3
    matched_category = None
    matched_keyword = None
    for category, score, keywords in _FALLBACK_KEYWORD_CATEGORIES:
        hit = next((kw for kw in keywords if kw in h), None)
        if hit:
            urgency = score
            matched_category = category
            matched_keyword = hit
            break
    return {
        "urgency": urgency, "importance": 5, "confidence": 4,
        "sentiment": "neutral", "horizon": "short", "market_impact": "medium",
        "is_structural": False, "direction": "sideways",
        "one_liner": headline[:200], "themes": [], "sectors": [], "tickers": [],
        # Not part of the TriagedEvent schema — popped by _ai_triage before
        # the dict is used, only carried this far so the fallback-visibility
        # log line below can include which keyword (if any) fired, e.g. to
        # manually audit "results" matching something unrelated to earnings.
        "_fallback_matched_category": matched_category,
        "_fallback_matched_keyword": matched_keyword,
    }


async def _ai_triage(headline: str, summary: str) -> dict:
    from app.services.ai_service import _call_with_fallback  # noqa: PLC2701
    prompt = f"Headline: {headline}\n\nSummary: {summary[:500]}"
    failure_log: list[dict] = []
    try:
        raw = await _call_with_fallback(prompt, _TRIAGE_SYSTEM, max_tokens=400, failure_log=failure_log, priority="background")
        if not raw:
            fallback = _rule_based_fallback(headline)
            # Pure observability — no behavior change. See this module's
            # docstring update: the goal is to find out how often (and
            # under what conditions) triage silently degrades to keyword
            # matching before deciding whether that's worth fixing.
            log.warning(
                "triage.fallback_to_rule_based",
                headline=headline[:300],
                providers_failed=failure_log,
                fallback_urgency=fallback["urgency"],
                fallback_matched_category=fallback["_fallback_matched_category"],
                fallback_matched_keyword=fallback["_fallback_matched_keyword"],
            )
            fallback.pop("_fallback_matched_category", None)
            fallback.pop("_fallback_matched_keyword", None)
            return fallback
        text = raw.strip()
        if "```" in text:
            parts = text.split("```")
            text = parts[1] if len(parts) > 1 else text
            if text.startswith("json"):
                text = text[4:]
        scores = json.loads(text.strip())
        # Baseline for comparison against the fallback path above — without
        # this, there's no way to tell whether a fallback urgency=3 is
        # "probably right" (the AI would've said the same) or "we don't
        # actually know" (the AI never got to weigh in).
        ai_urgency = scores.get("urgency")
        if isinstance(ai_urgency, (int, float)) and ai_urgency < 6:
            log.info("triage.ai_scored_low_urgency", headline=headline[:300], ai_urgency=ai_urgency)
        return scores
    except Exception:
        fallback = _rule_based_fallback(headline)
        log.warning(
            "triage.fallback_to_rule_based",
            headline=headline[:300],
            providers_failed=failure_log,
            fallback_urgency=fallback["urgency"],
            fallback_matched_category=fallback["_fallback_matched_category"],
            fallback_matched_keyword=fallback["_fallback_matched_keyword"],
            exception=True,
        )
        fallback.pop("_fallback_matched_category", None)
        fallback.pop("_fallback_matched_keyword", None)
        return fallback


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
