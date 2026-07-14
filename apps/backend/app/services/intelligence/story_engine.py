"""
StoryEngineWorker — runs every 5 min during market hours.
Generates a new narrative only when market context has materially changed.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import structlog
from datetime import datetime, timezone, timedelta
from uuid import uuid4

log = structlog.get_logger(__name__)

_IST = timezone(timedelta(hours=5, minutes=30))

_STORY_SYSTEM = """You are a senior Indian market strategist writing a live intraday brief.
Given live data, return a JSON object:
{
  "story": "2-3 sentences: what is the market doing and why",
  "mood": "Bullish" | "Cautious Bull" | "Uncertain" | "Sideways" | "Cautious Bear" | "Bearish" | "Panic",
  "pulse": "+" | "=" | "-",
  "sector_rotation": "one sentence on sector gains/losses",
  "direction": "up" | "down" | "sideways",
  "opportunity": "one sentence on best opportunity right now",
  "risk": "one sentence on primary risk",
  "trader_watch": "what intraday traders should watch (levels/catalysts)",
  "investor_watch": "what longer-term investors should monitor",
  "confidence": 0-100
}
Focus on NSE/BSE, Nifty, BankNifty, FII/DII, RBI. Return only valid JSON."""


def _is_market_hours() -> bool:
    now = datetime.now(_IST)
    h, m = now.hour, now.minute
    return (h == 9 and m >= 15) or (10 <= h <= 14) or (h == 15 and m <= 30)


async def _fetch_context() -> dict:
    try:
        from app.services.market_data import get_extended_indices, get_sector_changes
        indices, sectors = await asyncio.gather(
            get_extended_indices(), get_sector_changes(), return_exceptions=True
        )
        if isinstance(indices, Exception):
            indices = []
        if isinstance(sectors, Exception):
            sectors = []

        from app.db.session import AsyncSessionLocal
        from app.db.models.intelligence import EventTriage
        from sqlalchemy import select, desc

        since = datetime.now(timezone.utc) - timedelta(hours=2)
        async with AsyncSessionLocal() as db:
            rows = (await db.execute(
                select(EventTriage)
                .where(EventTriage.triaged_at >= since)
                .where(EventTriage.urgency >= 4)
                .order_by(desc(EventTriage.urgency))
                .limit(6)
            )).scalars().all()

        event_bullets = [
            f"[{e.urgency}/10] {e.one_liner or e.headline[:100]}"
            for e in rows
        ]

        nifty = next((i for i in indices if "NIFTY 50" in str(i.get("name", "")).upper()), {})
        bnk   = next((i for i in indices if "BANK" in str(i.get("name", "")).upper() and
                      "NIFTY" in str(i.get("name", "")).upper()), {})

        return {
            "nifty": nifty,
            "banknifty": bnk,
            "sectors": list(sectors)[:8],
            "recent_events": event_bullets,
        }
    except Exception as exc:
        log.warning("story_engine.context_error", error=str(exc))
        return {}


def _idx_price(idx: dict) -> float:
    """Extract numeric price from index dict (handles 'value' or 'price' field)."""
    raw = idx.get("value") or idx.get("price") or "0"
    try:
        return float(str(raw).replace(",", ""))
    except (ValueError, TypeError):
        return 0.0


def _idx_pct(idx: dict) -> float:
    """Extract change % from index dict (handles 'pct' or 'change_pct' field)."""
    raw = idx.get("pct") if idx.get("pct") is not None else idx.get("change_pct", 0)
    try:
        return round(float(raw), 2)
    except (ValueError, TypeError):
        return 0.0


def _sec_pct(sec: dict) -> float:
    """Extract change % from sector dict (handles 'change_pct' or 'pct' field)."""
    raw = sec.get("change_pct") if sec.get("change_pct") is not None else sec.get("pct", 0)
    try:
        return round(float(raw), 2)
    except (ValueError, TypeError):
        return 0.0


def _context_hash(ctx: dict) -> str:
    parts: list[str] = []
    nifty = ctx.get("nifty", {})
    if nifty:
        parts.append(f"n:{_idx_price(nifty):.0f}:{_idx_pct(nifty)}")
    for s in ctx.get("sectors", [])[:5]:
        parts.append(f"{s.get('name', '')}:{_sec_pct(s)}")
    parts.extend(ctx.get("recent_events", [])[:3])
    return hashlib.md5("|".join(parts).encode()).hexdigest()[:16]


async def _generate(ctx: dict) -> dict | None:
    from app.services.ai_service import _call_with_fallback  # noqa: PLC2701

    nifty = ctx.get("nifty", {})
    bnk   = ctx.get("banknifty", {})
    secs  = ctx.get("sectors", [])
    evts  = ctx.get("recent_events", [])

    prompt = (
        f"Live Market ({datetime.now(_IST).strftime('%H:%M IST')}):\n\n"
        f"NIFTY 50: {_idx_price(nifty) or 'N/A'} ({_idx_pct(nifty):+.2f}%)\n"
        f"BANK NIFTY: {_idx_price(bnk) or 'N/A'} ({_idx_pct(bnk):+.2f}%)\n\n"
        f"SECTORS:\n" +
        "\n".join(f"- {s.get('name', '')}: {_sec_pct(s):+.2f}%" for s in secs[:6]) +
        f"\n\nRECENT EVENTS (2h):\n" +
        ("\n".join(evts) if evts else "- None") +
        "\n\nGenerate the market narrative JSON."
    )

    raw = await _call_with_fallback(prompt, _STORY_SYSTEM, max_tokens=600)
    if not raw:
        return None
    try:
        text = raw.strip()
        if "```" in text:
            parts = text.split("```")
            text = parts[1] if len(parts) > 1 else text
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text.strip())
    except Exception as exc:
        log.warning("story_engine.parse_error", error=str(exc))
        return None


async def _save_story(data: dict, ctx: dict, prev_hash: str | None) -> str:
    from app.db.session import AsyncSessionLocal
    from app.db.models.intelligence import MarketStory

    story_hash = hashlib.md5(
        (data.get("story", "") + datetime.now(timezone.utc).isoformat()).encode()
    ).hexdigest()[:16]
    nifty = ctx.get("nifty", {})

    try:
        async with AsyncSessionLocal() as db:
            db.add(MarketStory(
                id=str(uuid4()),
                story=data.get("story", ""),
                mood=data.get("mood", "Uncertain"),
                pulse=data.get("pulse", "="),
                sector_rotation=data.get("sector_rotation"),
                direction=data.get("direction", "sideways"),
                opportunity=data.get("opportunity"),
                risk=data.get("risk"),
                trader_watch=data.get("trader_watch"),
                investor_watch=data.get("investor_watch"),
                confidence=int(data.get("confidence", 70)),
                events_included=ctx.get("recent_events", [])[:5],
                previous_story_hash=prev_hash,
                story_hash=story_hash,
                nifty_at=_idx_price(nifty) or None,
            ))
            await db.commit()
    except Exception as exc:
        log.error("story_engine.save_error", error=str(exc))

    try:
        from app.core.redis import cache_set
        await cache_set("market:story:latest", {**data, "story_hash": story_hash, "generated_at": datetime.now(timezone.utc).isoformat()}, 600)
    except Exception:
        pass

    return story_hash


class StoryEngineWorker:
    def __init__(self, interval_sec: int = 300) -> None:
        self._interval = interval_sec
        self._running = False
        self._task: asyncio.Task | None = None
        self._last_ctx_hash: str | None = None
        self._last_story_hash: str | None = None

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._run(), name="story-engine")
        log.info("story_engine.started")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _run(self) -> None:
        while self._running:
            try:
                await asyncio.sleep(self._interval)
                if not _is_market_hours():
                    continue

                ctx = await _fetch_context()
                if not ctx:
                    continue

                new_hash = _context_hash(ctx)
                if new_hash == self._last_ctx_hash:
                    log.debug("story_engine.no_change")
                    continue

                self._last_ctx_hash = new_hash
                data = await _generate(ctx)
                if not data:
                    continue

                self._last_story_hash = await _save_story(data, ctx, self._last_story_hash)
                log.info("story_engine.generated", mood=data.get("mood"), pulse=data.get("pulse"))

                # Broadcast a story-update event so SSE clients know to refresh
                if data.get("pulse") in ("+", "-"):
                    from app.services.intelligence.event_bus import get_broadcaster, TriagedEvent, RawEvent
                    fake = TriagedEvent(
                        raw=RawEvent(id="story-update", headline="Market Story Updated",
                                     summary=data.get("story", ""), source="story_engine"),
                        urgency=6, importance=7, confidence=80,
                        sentiment="neutral", horizon="intraday", market_impact="medium",
                        is_structural=False, direction=data.get("direction", "sideways"),
                        one_liner=data.get("story", "")[:200],
                        themes=[], sectors=[], tickers=[],
                        broadcast=True, refresh_homepage=False,
                    )
                    await get_broadcaster().broadcast(fake)

            except asyncio.CancelledError:
                break
            except Exception as exc:
                log.error("story_engine.loop_error", error=str(exc))
                await asyncio.sleep(30)


_engine: StoryEngineWorker | None = None


def get_story_engine() -> StoryEngineWorker:
    global _engine
    if _engine is None:
        _engine = StoryEngineWorker()
    return _engine
