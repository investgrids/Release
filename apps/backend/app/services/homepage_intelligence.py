"""
Homepage Intelligence (Phase 3, Priority 1) — the "Good Morning" daily
brief hero. Deliberately reuses the SAME single source of truth the
homepage's existing AI Market Brief card already uses (the real AIPE
morning_intelligence article — see apps/web/app/page.tsx's
AIMarketBriefCard docstring: "Deliberately not blending in MIE or any
other pipeline here"). This module adds exactly one more thing that
article doesn't already carry:
  - "What Changed Since Yesterday" — needs a real day-over-day comparison,
    which requires persisting a snapshot (HomepageDailySnapshot) since no
    existing table tracked this. Sourced from the SAME article's
    sectors_affected field, not a second signal.
Everything else (headline, confidence, companies_affected, ripple_effect,
opportunities, risks) is already on the article and rendered directly by
the frontend from the existing /api/insights/{slug} response — this
module doesn't duplicate it.

CD3-D (D5): this module used to also derive a one-line "AI Prediction"
("Today's market will likely be led by {sector}.") from the article's
strongest positive sector. Removed entirely — a real FORECAST clause
with zero legitimate producer in the pipeline (see
app.services.claim_authorization.FORECAST_UNAVAILABLE), and the fact
that it was a deterministic template rather than LLM prose made it
structurally invisible to both recommendation_language.py and
historical_forecast_guard.py, which only scan generated text fields.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.homepage_snapshot import HomepageDailySnapshot
from app.db.session import AsyncSessionLocal

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


async def _explain_change(db: AsyncSession, sector_name: str, direction: str, max_reasons: int = 3) -> list[str]:
    """Real evidence for why a sector's score moved (2026-08 homepage
    redesign, "Since Previous Session -> why"). Sourced from Development
    Memory ONLY — never an LLM call, never invented. A development only
    counts as an explanation when its own direction agrees with the
    delta's direction: a sector "improving" should be explained by
    positive-leaning developments, not any development merely tagged to
    that sector (which could just as easily be a negative one). Returns
    [] when nothing qualifies — the caller shows an honest "no verified
    driver" state rather than a forced explanation."""
    from app.services.development_memory.read import list_active_developments
    wanted_direction = "positive" if direction == "up" else "negative"
    devs = await list_active_developments(db, sectors=[sector_name], limit=8)
    matching = [d for d in devs if d.get("direction") == wanted_direction]
    return [d["title"] for d in matching[:max_reasons] if d.get("title")]


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
    top_changes = changes[:4]

    # "Since Previous Session -> why" (2026-08 homepage redesign): real
    # evidence per change, not the bare +5-style delta as the primary
    # user-facing message. Parallelized — each is an independent
    # Development Memory lookup, and this whole endpoint runs under a
    # 6s client timeout (see page.tsx's getHomepageExtras).
    #
    # 2026-08-31 concurrency fix: each concurrent branch gets its OWN
    # AsyncSession rather than sharing the request-scoped `db`. AsyncSession
    # isn't safe for concurrent use across coroutines — is_graph_worthy()
    # (graph_link.py) commits after every read as a deliberate SQLite
    # lock-release discipline, and two of those commits racing on one
    # shared session raised a real, recurring production
    # IllegalStateChangeError. The isolated session is scoped to exactly
    # this one gathered call, same pattern api/market.py already uses for
    # this same list_active_developments() path.
    async def _explain_change_isolated(sector_name: str, direction: str) -> list[str]:
        async with AsyncSessionLocal() as isolated_db:
            return await _explain_change(isolated_db, sector_name, direction)

    reasons_lists = await asyncio.gather(
        *[_explain_change_isolated(c["name"], c["direction"]) for c in top_changes]
    )
    for c, reasons in zip(top_changes, reasons_lists):
        c["reasons"] = reasons

    return top_changes
