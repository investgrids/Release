"""
Opportunity Worker â€” runs daily.

Pipeline:
  1. Pull recent unprocessed news_articles from DB
  2. Classify each article
  3. Group articles by dominant sector/theme
  4. Generate one Opportunity per group via opportunity_generator
  5. Also run a daily seed on first startup if opportunities table is empty
"""
from __future__ import annotations

import asyncio
import structlog
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func

from app.db.session import AsyncSessionLocal
from app.pipeline.classifier import classify_text
from app.pipeline.opportunity_generator import generate_opportunity_from_events

logger = structlog.get_logger(__name__)

# Minimum articles per group to trigger opportunity generation
_MIN_GROUP_SIZE = 3


async def _recent_articles(db, hours: int = 24) -> list[dict]:
    """Fetch articles from the last N hours."""
    from app.db.models_legacy import NewsArticle  # type: ignore[attr-defined]
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    result = await db.execute(
        select(NewsArticle)
        .where(NewsArticle.created_at >= cutoff)
        .order_by(NewsArticle.impact_score.desc())
        .limit(200)
    )
    rows = result.scalars().all()
    return [
        {
            "id":           r.id,
            "title":        r.headline,
            "summary":      r.summary,
            "published_at": r.published_at,
            "category":     "General",
            "companies":    r.companies or [],
        }
        for r in rows
    ]


def _group_by_sector(articles: list[dict]) -> dict[str, list[dict]]:
    """Classify and bucket articles by primary sector."""
    groups: dict[str, list[dict]] = {}
    for art in articles:
        text = f"{art['title']} {art['summary']}"
        result = classify_text(text)
        sector = result["sectors"][0] if result["sectors"] else "General"
        groups.setdefault(sector, []).append(art)
    return groups


async def _opportunities_exist(db) -> bool:
    from app.db.models.opportunity import Opportunity
    result = await db.execute(select(func.count()).select_from(Opportunity))
    return (result.scalar_one() or 0) > 0


async def _seed_static_opportunities(db) -> None:
    """
    Seed the DB with the 6 static radar opportunities on first run.
    This ensures the page works immediately without waiting for the
    daily pipeline to accumulate real articles.
    """
    from app.pipeline.opportunity_generator import generate_opportunity_from_events

    STATIC_SEEDS = [
        {
            "theme": "AI Infrastructure Boom",
            "sectors": ["Infrastructure", "Technology"],
            "events": [
                {"id": "seed-ai-1", "title": "India AI Mission ₹10,372 Cr approved",         "summary": "Government of India approved the India AI Mission with ₹10,372 crore allocation to build AI data centers and compute infrastructure across the country.", "published_at": "2024-05-22", "category": "Government"},
                {"id": "seed-ai-2", "title": "Data center capacity to triple by 2027",         "summary": "India's data center capacity is expected to grow 3X by 2027, driven by hyperscaler investments from AWS, Google, and Microsoft expanding India footprint.", "published_at": "2024-05-15", "category": "Corporate"},
                {"id": "seed-ai-3", "title": "PLI scheme for IT hardware servers approved",    "summary": "PLI incentives announced for servers, storage, and networking hardware manufacturing in India, aimed at reducing import dependence.", "published_at": "2024-05-01", "category": "Policy"},
                {"id": "seed-ai-4", "title": "NTPC Power capacity for data centers",           "summary": "NTPC announces new power projects specifically to support growing data center demand in India.", "published_at": "2024-04-25", "category": "Infrastructure"},
            ],
        },
        {
            "theme": "Railway Modernization",
            "sectors": ["Railways", "Infrastructure"],
            "events": [
                {"id": "seed-rail-1", "title": "Railway capex hits record ₹2.65 lakh crore FY25", "summary": "Union Budget allocated record ₹2.65 lakh crore for railways, focused on new lines, electrification, Kavach signaling, and station redevelopment.", "published_at": "2024-05-20", "category": "Government"},
                {"id": "seed-rail-2", "title": "BEML bags ₹18,000 Cr Vande Bharat coach order",   "summary": "BEML wins massive order to manufacture Vande Bharat train coaches, as the government targets 400 trains by 2026.", "published_at": "2024-05-12", "category": "Corporate"},
                {"id": "seed-rail-3", "title": "Kavach safety rollout to 10,000 km tracks",        "summary": "Phase 3 of Kavach anti-collision system rollout announced covering 10,000 km of railway tracks for enhanced safety.", "published_at": "2024-05-08", "category": "Government"},
                {"id": "seed-rail-4", "title": "L&T wins ₹6,200 Cr DFC Phase-2 contract",          "summary": "Larsen and Toubro wins major Dedicated Freight Corridor Phase-2 contract worth ₹6,200 crore.", "published_at": "2024-05-05", "category": "Corporate"},
            ],
        },
        {
            "theme": "Green Energy Transition",
            "sectors": ["Energy", "Infrastructure"],
            "events": [
                {"id": "seed-green-1", "title": "India targets 500 GW renewable energy by 2030",   "summary": "Government reaffirms 500 GW renewable energy target with ₹19,100 Cr green energy corridor investment.", "published_at": "2024-05-18", "category": "Government"},
                {"id": "seed-green-2", "title": "NTPC Green Energy IPO plans announced",            "summary": "NTPC Green Energy, the renewable arm, files for IPO to raise funds for solar and wind capacity expansion.", "published_at": "2024-05-10", "category": "Corporate"},
                {"id": "seed-green-3", "title": "Green hydrogen mission ₹19,744 Cr allocation",     "summary": "National Green Hydrogen Mission receives ₹19,744 crore to build India's green hydrogen ecosystem.", "published_at": "2024-04-28", "category": "Policy"},
            ],
        },
        {
            "theme": "Defence Manufacturing Indigenisation",
            "sectors": ["Defence", "Manufacturing"],
            "events": [
                {"id": "seed-def-1", "title": "India defence export target $5 billion by 2025",    "summary": "India sets ambitious ₹40,000 Cr defence export target for 2025 with HAL, BEL as primary export vehicles.", "published_at": "2024-05-16", "category": "Government"},
                {"id": "seed-def-2", "title": "HAL LCA Tejas Mk2 order for 97 aircraft",           "summary": "HAL receives 97-aircraft Tejas Mk2 order worth ₹67,000 Cr from Indian Air Force, largest ever domestic defence order.", "published_at": "2024-05-09", "category": "Corporate"},
                {"id": "seed-def-3", "title": "Defence indigenisation list blocks 4,000+ imports",  "summary": "Ministry of Defence expands positive indigenisation list to block imports of 4,000+ items, benefiting domestic manufacturers.", "published_at": "2024-04-22", "category": "Policy"},
            ],
        },
        {
            "theme": "Digital Banking Transformation",
            "sectors": ["Banking", "Technology"],
            "events": [
                {"id": "seed-bank-1", "title": "UPI transactions hit 14 billion monthly record",   "summary": "UPI transactions cross 14 billion monthly milestone, cementing India as global leader in digital payments.", "published_at": "2024-05-14", "category": "Corporate"},
                {"id": "seed-bank-2", "title": "RBI Digital Rupee pilot expands to 13 cities",    "summary": "RBI expands CBDC digital rupee pilot to 13 cities with 1 million users, paving way for nationwide rollout.", "published_at": "2024-05-07", "category": "Policy"},
                {"id": "seed-bank-3", "title": "HDFC Bank credit card market share hits 30%",     "summary": "HDFC Bank captures 30% of India's credit card market as digital lending accelerates post-COVID.", "published_at": "2024-04-29", "category": "Corporate"},
            ],
        },
        {
            "theme": "EV Supply Chain Build-out",
            "sectors": ["Automotive", "Manufacturing"],
            "events": [
                {"id": "seed-ev-1", "title": "India EV sales cross 1.5 million units FY24",      "summary": "Electric vehicle sales surged past 1.5 million units in FY24, driven by 2-wheelers and commercial vehicles.", "published_at": "2024-05-11", "category": "Corporate"},
                {"id": "seed-ev-2", "title": "FAME III scheme ₹25,000 Cr EV subsidy approved",   "summary": "Cabinet approves FAME III scheme with ₹25,000 crore EV subsidies to accelerate EV adoption across segments.", "published_at": "2024-05-03", "category": "Government"},
                {"id": "seed-ev-3", "title": "Tata Motors EV plant ₹15,000 Cr investment",       "summary": "Tata Motors announces ₹15,000 crore dedicated EV manufacturing facility targeting 2 lakh EVs annually by 2026.", "published_at": "2024-04-18", "category": "Corporate"},
            ],
        },
    ]

    for seed in STATIC_SEEDS:
        try:
            opp = await generate_opportunity_from_events(db, seed["events"])
            if opp:
                logger.info("Seeded opportunity: %s (id=%s)", seed["theme"], opp.id)
        except Exception as exc:
            logger.error("Seed failed for %s: %s", seed["theme"], exc)


async def run_opportunity_worker(seed_on_empty: bool = False) -> None:
    """Daily AI pipeline â€” groups recent news into opportunities."""
    logger.info("Opportunity worker started (seed_on_empty=%s)", seed_on_empty)

    first_run = True
    while True:
        try:
            async with AsyncSessionLocal() as db:
                if first_run and seed_on_empty:
                    exists = await _opportunities_exist(db)
                    if not exists:
                        logger.info("Opportunities table empty â€” seeding static data")
                        await _seed_static_opportunities(db)
                    first_run = False

                articles = await _recent_articles(db, hours=26)
                logger.info("Opportunity worker: processing %d recent articles", len(articles))

                if len(articles) >= _MIN_GROUP_SIZE:
                    groups = _group_by_sector(articles)
                    for sector, group_arts in groups.items():
                        if len(group_arts) < _MIN_GROUP_SIZE:
                            continue
                        logger.info("Generating opportunity for sector=%s (%d articles)", sector, len(group_arts))
                        await generate_opportunity_from_events(db, group_arts[:10])

        except Exception as exc:
            logger.error("Opportunity worker error: %s", exc, exc_info=True)

        await asyncio.sleep(86400)  # 24 hours
