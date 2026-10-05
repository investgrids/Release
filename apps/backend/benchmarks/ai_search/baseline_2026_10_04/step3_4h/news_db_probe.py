import asyncio, json, re, sys, time
sys.path.insert(0, ".")
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import select, func
from app.db.session import AsyncSessionLocal
from app.db.models_legacy import NewsArticle

SNAP = Path("benchmarks/ai_search/baseline_2026_10_04/step3_4g1/live_news_snapshot.json")


def shape(s):
    s = (s or "")
    if re.match(r"^\d{4}-\d{2}-\d{2}", s):
        return "iso"
    if re.search(r"\bago\b", s, re.I):
        return "relative"
    return "other:" + s[:12]


async def main():
    async with AsyncSessionLocal() as db:
        total = (await db.execute(select(func.count()).select_from(NewsArticle))).scalar()
        rows = (await db.execute(select(NewsArticle.id, NewsArticle.headline, NewsArticle.published_at, NewsArticle.created_at, NewsArticle.source).order_by(NewsArticle.created_at.desc()).limit(3000))).all()
        print("total rows", total)
        now = datetime.now(timezone.utc)
        newest = rows[0].created_at if rows else None
        print("newest created_at", newest, "age_h", round((now - (newest.replace(tzinfo=timezone.utc) if newest.tzinfo is None else newest)).total_seconds() / 3600, 1) if newest else None)
        print("published_at shapes (latest 3000):", Counter(shape(r.published_at) for r in rows).most_common(6))
        last24 = [r for r in rows if r.created_at and (now - (r.created_at.replace(tzinfo=timezone.utc) if r.created_at.tzinfo is None else r.created_at)).total_seconds() < 86400]
        print("rows created in last 24h", len(last24), "sources", Counter(r.source for r in last24).most_common(8))
        heads = {re.sub(r"\W+", " ", (r.headline or "").lower()).strip() for r in rows}
        snap = json.loads(SNAP.read_text(encoding="utf-8")) if SNAP.exists() else []
        sn = snap if isinstance(snap, list) else snap.get("items", [])
        hit = sum(1 for a in sn if re.sub(r"\W+", " ", (a.get("headline") or "").lower()).strip() in heads)
        print("live snapshot items", len(sn), "also present in DB (latest 3000 by created_at):", hit)
        print("snapshot sources", Counter(a.get("source") for a in sn).most_common(8))
        print("db sources (3000)", Counter(r.source for r in rows).most_common(8))

asyncio.run(main())
