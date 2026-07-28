"""
Homepage Intelligence (Phase 3, Priority 1) — the "Good Morning" daily
brief hero. Deliberately reuses the SAME single source of truth the
homepage's existing AI Market Brief card already uses (the real AIPE
morning_intelligence article — see apps/web/app/page.tsx's
AIMarketBriefCard docstring: "Deliberately not blending in MIE or any
other pipeline here"). This module adds exactly two things that article
doesn't already carry:
  - "What Changed Since Yesterday" — needs a real day-over-day comparison,
    which requires persisting a snapshot (HomepageDailySnapshot) since no
    existing table tracked this. Sourced from the SAME article's
    sectors_affected field, not a second signal.
  - A one-line AI Prediction — deterministically derived from the
    article's own sectors_affected (the sector with the strongest positive
    stance), never a new LLM call (the article's own opportunities[0]/
    risks[0] already carry the real narrative reasoning).
Everything else (headline, confidence, companies_affected, ripple_effect,
opportunities, risks) is already on the article and rendered directly by
the frontend from the existing /api/insights/{slug} response — this
module doesn't duplicate it.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.homepage_snapshot import HomepageDailySnapshot

# Categorical -> numeric, only for day-over-day comparison purposes — the
# article itself never expresses a number here, so this scale is this
# module's own derived view, not a value pulled from anywhere else.
_MAGNITUDE_WEIGHT = {"low": 1, "medium": 2, "high": 3}


def _sector_score(impact: str, magnitude: str) -> int:
    w = _MAGNITUDE_WEIGHT.get((magnitude or "").lower(), 1)
    sign = 1 if impact == "positive" else -1 if impact == "negative" else 0
    return sign * w


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


async def record_snapshot_if_missing(db: AsyncSession, article) -> None:
    """Writes today's sector snapshot from the article, once per day. Never
    overwrites an existing row for today — the FIRST article of the day
    (usually the 06:00-11:59 IST run) sets today's baseline; a same-day
    regeneration shouldn't silently move the goalposts for tomorrow's diff."""
    today = _today()
    existing = (await db.execute(
        select(HomepageDailySnapshot).where(HomepageDailySnapshot.snapshot_date == today)
    )).scalar_one_or_none()
    if existing:
        return
    sectors = [
        {
            "name": s.get("name"), "impact": s.get("impact"), "magnitude": s.get("magnitude"),
            "score": _sector_score(s.get("impact", ""), s.get("magnitude", "")),
        }
        for s in (article.sectors_affected or []) if s.get("name")
    ]
    db.add(HomepageDailySnapshot(snapshot_date=today, article_id=article.id, sectors=sectors))
    await db.commit()


async def get_yesterday_changes(db: AsyncSession, article) -> list[dict]:
    """Real day-over-day sector deltas — [] until at least 2 days of
    snapshots exist (same "never fabricate, just show nothing yet"
    stance as Investment Watch's last_change). Compares today's LIVE
    article sectors (not today's stored snapshot, which may be a few
    hours stale) against the most recent snapshot from a PRIOR day.

    A prior snapshot existing is NOT the same as there being an overlapping
    sector to diff — the daily narrative can move to an entirely different
    set of sectors day to day (confirmed live: Jul 27 was Defence/IT,
    Jul 28 was Banking/PSU Bank/Auto/Infra, zero name overlap). Sectors
    with no prior-day match still carry real information — they're newly
    in focus today — so they're surfaced as `is_new` entries with today's
    own score standing in for the "delta", rather than silently dropped
    and misreported as "not enough history" alongside the genuine
    no-prior-snapshot-at-all case above."""
    today = _today()
    prior = (await db.execute(
        select(HomepageDailySnapshot)
        .where(HomepageDailySnapshot.snapshot_date < today)
        .order_by(HomepageDailySnapshot.snapshot_date.desc())
        .limit(1)
    )).scalar_one_or_none()
    if not prior:
        return []

    prior_by_name = {s.get("name"): s.get("score", 0) for s in (prior.sectors or [])}
    today_sectors = [
        {"name": s.get("name"), "score": _sector_score(s.get("impact", ""), s.get("magnitude", ""))}
        for s in (article.sectors_affected or []) if s.get("name")
    ]

    changes = []
    for s in today_sectors:
        name = s["name"]
        if name in prior_by_name:
            delta = s["score"] - prior_by_name[name]
            if delta != 0:
                changes.append({"name": name, "delta": delta, "direction": "up" if delta > 0 else "down", "is_new": False})
        elif s["score"] != 0:
            changes.append({"name": name, "delta": s["score"], "direction": "up" if s["score"] > 0 else "down", "is_new": True})
    changes.sort(key=lambda c: abs(c["delta"]), reverse=True)
    return changes[:4]


def get_ai_prediction(article) -> str | None:
    """One deterministic sentence — the strongest real positive-impact
    sector from the article's own sectors_affected, never invented and
    never a new LLM call. None when nothing qualifies (e.g. an all-neutral
    day) rather than forcing a hollow sentence."""
    sectors = article.sectors_affected or []
    positive = [s for s in sectors if s.get("impact") == "positive"]
    if not positive:
        return None
    best = max(positive, key=lambda s: _MAGNITUDE_WEIGHT.get((s.get("magnitude") or "").lower(), 0))
    return f"Today's market will likely be led by {best['name']}."
