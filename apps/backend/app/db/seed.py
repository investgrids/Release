"""
Populate the database with initial content data.
Only inserts rows that don't already exist (idempotent).
"""
from datetime import datetime, timedelta, timezone

from app.db import models_legacy as models


def _dt(y: int, m: int, d: int, h: int = 9, mi: int = 30) -> datetime:
    return datetime(y, m, d, h, mi, tzinfo=timezone.utc)


# CalendarEvent.date is a display string ("Jul 21, 2026"), not a real
# datetime column — computed relative to whenever this module is first
# imported (once per process start, same as every other module-level
# constant here) so a freshly-seeded dev DB always shows genuinely
# upcoming demo dates instead of a fixed calendar date that goes stale
# the moment real time passes it.
def _cal_date(days_from_now: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days_from_now)).strftime("%b %d, %Y")


EVENTS = [
    models.Event(
        id="evt-rbi-june-2026",
        title="RBI holds repo rate at 6.5% for seventh consecutive meeting",
        summary="The Monetary Policy Committee unanimously kept the repo rate unchanged, citing stable inflation near the 4% target and continued support for growth. Governor flagged external risks from global commodity prices.",
        impact_score=8.7,
        confidence=0.93,
        sectors=["Financials", "Consumer Staples", "Real Estate"],
        companies=[
            {"symbol": "HDFCBANK", "name": "HDFC Bank", "impact": "Positive"},
            {"symbol": "ICICIBANK", "name": "ICICI Bank", "impact": "Positive"},
            {"symbol": "SBIN", "name": "SBI", "impact": "Neutral"},
        ],
        category="Macro",
        published_at=_dt(2026, 6, 18),
    ),
    models.Event(
        id="evt-defence-budget-2026",
        title="Defence capital expenditure raised by Rs. 45,000 Cr in revised estimates",
        summary="The revised budget allocation boosts indigenous defence procurement, benefiting domestic manufacturers under the Make-in-India initiative. Order books at BEL, HAL and Bharat Forge are expected to expand significantly.",
        impact_score=9.1,
        confidence=0.89,
        sectors=["Defence", "Aerospace", "Manufacturing"],
        companies=[
            {"symbol": "BEL", "name": "Bharat Electronics", "impact": "Positive"},
            {"symbol": "HAL", "name": "Hindustan Aeronautics", "impact": "Positive"},
            {"symbol": "BHARATFORG", "name": "Bharat Forge", "impact": "Positive"},
        ],
        category="Government",
        published_at=_dt(2026, 7, 8),
    ),
    models.Event(
        id="evt-solar-capacity-2026",
        title="India surpasses 100 GW solar capacity milestone",
        summary="India crossed 100 GW of installed solar capacity, triggered accelerated renewable procurement targets for utilities. Analysts expect large-scale order inflows for module manufacturers and project developers.",
        impact_score=8.3,
        confidence=0.85,
        sectors=["Energy", "Utilities", "Manufacturing"],
        companies=[
            {"symbol": "ADANIGREEN", "name": "Adani Green Energy", "impact": "Positive"},
            {"symbol": "TATAPOWER", "name": "Tata Power", "impact": "Positive"},
            {"symbol": "SUZLON", "name": "Suzlon Energy", "impact": "Positive"},
        ],
        category="Policy",
        published_at=_dt(2026, 7, 14),
    ),
    models.Event(
        id="evt-it-deal-slowdown-2026",
        title="US enterprise IT spending contracts for second consecutive quarter",
        summary="CIO surveys and enterprise software vendors report discretionary IT budget freezes. Indian IT majors with high US revenue exposure face near-term demand headwinds, though management guidance remains cautious.",
        impact_score=7.4,
        confidence=0.80,
        sectors=["IT", "Technology"],
        companies=[
            {"symbol": "TCS", "name": "Tata Consultancy Services", "impact": "Negative"},
            {"symbol": "INFY", "name": "Infosys", "impact": "Negative"},
            {"symbol": "WIPRO", "name": "Wipro", "impact": "Negative"},
        ],
        category="Global",
        published_at=_dt(2026, 7, 10),
    ),
    models.Event(
        id="evt-semiconductor-plc-2026",
        title="India Semiconductor Mission approves Rs. 76,000 Cr fab incentive",
        summary="The government approved production-linked incentives for three semiconductor fabrication units. The scheme covers 50% capital subsidy for advanced nodes, signalling long-term domestic chip manufacturing ambitions.",
        impact_score=9.4,
        confidence=0.91,
        sectors=["Technology", "Electronics", "Manufacturing"],
        companies=[
            {"symbol": "DIXON", "name": "Dixon Technologies", "impact": "Positive"},
            {"symbol": "KAYNES", "name": "Kaynes Technology", "impact": "Positive"},
        ],
        category="Policy",
        published_at=_dt(2026, 6, 25),
    ),
]

NEWS = [
    models.NewsArticle(
        id="news-defence-2026",
        headline="Defence supplier sees demand surge after revised budget allocation",
        summary="BEL and HAL order books expand sharply after the defence capital expenditure revision. Analysts upgrade target prices, citing multi-year revenue visibility from domestic procurement mandates.",
        source="Economic Times",
        published_at="2h ago",
        companies=["Bharat Electronics", "HAL", "Bharat Forge"],
        impact_score=8.6,
    ),
    models.NewsArticle(
        id="news-solar-2026",
        headline="Solar project approvals accelerate renewable capital flows",
        summary="New MNRE approvals for 15 GW of utility-scale solar projects point to expanded capacity additions through 2028. Utility developers and module suppliers rally on the news.",
        source="Business Standard",
        published_at="4h ago",
        companies=["Adani Green", "Tata Power", "Waaree Energies"],
        impact_score=7.9,
    ),
    models.NewsArticle(
        id="news-rbi-2026",
        headline="RBI rate hold boosts banking sector outlook; NIMs to stay stable",
        summary="Net interest margins for major private banks are expected to remain stable after the RBI's hold decision. The benign rate environment supports loan growth without margin compression pressure.",
        source="Mint",
        published_at="6h ago",
        companies=["HDFC Bank", "ICICI Bank", "Axis Bank"],
        impact_score=7.5,
    ),
    models.NewsArticle(
        id="news-it-2026",
        headline="IT sector faces headwinds as US spending tightens further",
        summary="CIO surveys show a second consecutive quarter of discretionary IT budget freezes. Revenue growth guidance from Indian IT majors is expected to be conservative in upcoming earnings.",
        source="Financial Times",
        published_at="1d ago",
        companies=["TCS", "Infosys", "Wipro"],
        impact_score=6.8,
    ),
]

CALENDAR = [
    models.CalendarEvent(
        id="cal-wpi-jul-2026",
        category="Macro",
        title="June WPI Inflation Data Release",
        date=_cal_date(4),
        description="Wholesale Price Index reading for June - key input for RBI's inflation assessment and rate outlook.",
    ),
    models.CalendarEvent(
        id="cal-tcs-q1-2026",
        category="Results",
        title="TCS Q1 FY27 Earnings Result",
        date=_cal_date(4),
        description="Tata Consultancy Services quarterly result - bellwether for India's IT sector and US demand outlook.",
    ),
    models.CalendarEvent(
        id="cal-rbi-aug-2026",
        category="RBI",
        title="Monetary Policy Committee Meeting",
        date=_cal_date(18),
        description="Key repo rate decision and forward guidance on growth-inflation balance.",
    ),
    models.CalendarEvent(
        id="cal-q1-results-2026",
        category="Results",
        title="Q1 FY27 Earnings Season Begins",
        date=_cal_date(25),
        description="Major banks, IT majors and FMCG companies start reporting Q1 FY27 earnings.",
    ),
    models.CalendarEvent(
        id="cal-cpi-jul-2026",
        category="Macro",
        title="June CPI Inflation Data Release",
        date=_cal_date(2),
        description="Consumer Price Index reading - critical for RBI's inflation trajectory.",
    ),
    models.CalendarEvent(
        id="cal-iip-jun-2026",
        category="Macro",
        title="May Industrial Production (IIP)",
        date=_cal_date(3),
        description="Industrial output data reflects manufacturing momentum ahead of earnings.",
    ),
    models.CalendarEvent(
        id="cal-budget-session-2026",
        category="Government",
        title="Parliament Budget Session Resumes",
        date=_cal_date(7),
        description="Key policy bills and supplementary demands for grants to be tabled.",
    ),
    models.CalendarEvent(
        id="cal-hcltech-q1-2026",
        category="Results",
        title="HCL Technologies Q1 FY27 Results",
        date=_cal_date(5),
        description="HCL Tech quarterly earnings - second major IT result of the season, key for sector sentiment.",
    ),
    models.CalendarEvent(
        id="cal-uswpi-jul-2026",
        category="Global",
        title="US Producer Price Index (PPI)",
        date=_cal_date(6),
        description="US producer inflation data - impacts Fed rate expectations and USD/INR pair.",
    ),
    models.CalendarEvent(
        id="cal-infy-q1-2026",
        category="Results",
        title="Infosys Q1 FY27 Earnings & Guidance",
        date=_cal_date(9),
        description="Infosys Q1 result and FY27 revenue guidance revision - closely tracked for US tech demand signals.",
    ),
]

RADAR = [
    models.RadarOpportunity(
        id="radar-defence-2026",
        theme="India Defence Ecosystem",
        score=95,
        reason="Budget capex up Rs. 45,000 Cr. Multi-year order pipelines at BEL, HAL and MFSL. Indigenous procurement mandates reduce import dependency.",
        confidence=0.91,
        beneficiaries=["Bharat Electronics", "HAL", "Bharat Forge", "MFSL"],
    ),
    models.RadarOpportunity(
        id="radar-green-energy-2026",
        theme="Green Energy Transition",
        score=92,
        reason="100 GW solar milestone crossed. MNRE accelerating new approvals. Capex cycle and earnings revisions strongly positive for developers and equipment makers.",
        confidence=0.88,
        beneficiaries=["Adani Green", "Tata Power", "Suzlon", "Waaree Energies"],
    ),
    models.RadarOpportunity(
        id="radar-semiconductor-2026",
        theme="India Semiconductor & Electronics",
        score=89,
        reason="PLI incentives for fab units approved. Rising domestic chip demand from EVs and consumer electronics. 10-year structural theme.",
        confidence=0.84,
        beneficiaries=["Dixon Technologies", "Kaynes Technology", "Syrma SGS"],
    ),
    models.RadarOpportunity(
        id="radar-digital-infra-2026",
        theme="Digital Infrastructure",
        score=85,
        reason="5G rollout driving data consumption. AI inference demand boosting data center capex. Fibre-to-home expansion accelerating.",
        confidence=0.82,
        beneficiaries=["Bharti Airtel", "Tata Communications", "HFCL"],
    ),
    models.RadarOpportunity(
        id="radar-banking-2026",
        theme="Private Banking & Credit Growth",
        score=78,
        reason="Credit growth 13-15% YoY. Rate hold preserves NIMs. Asset quality stable. Valuations attractive vs. historic averages.",
        confidence=0.79,
        beneficiaries=["HDFC Bank", "ICICI Bank", "Axis Bank", "Kotak Bank"],
    ),
]

STORIES = [
    models.Story(
        id="story-defence-2026",
        title="India's Defence Boom",
        description="How a decade of policy shifts, rising capex, and Make in India mandates are building a world-class indigenous defence ecosystem - and which companies are at the center of it.",
        theme="Macro + Government",
        image="https://images.unsplash.com/photo-1578662996442-48f60103fc96?auto=format&fit=crop&w=1200&q=80",
    ),
    models.Story(
        id="story-ai-infra-2026",
        title="AI Infrastructure Rush",
        description="The data center and networking companies positioning themselves to power India's enterprise AI wave - from hyperscale cloud to private inference clusters.",
        theme="Technology",
        image="https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=1200&q=80",
    ),
    models.Story(
        id="story-green-energy-2026",
        title="The Solar Superpower Story",
        description="India's race to 500 GW of renewable energy by 2030 is creating a multi-decade investment cycle. Here's who benefits most across the entire value chain.",
        theme="Energy + Policy",
        image="https://images.unsplash.com/photo-1509391366360-2e959784a276?auto=format&fit=crop&w=1200&q=80",
    ),
    models.Story(
        id="story-semiconductor-2026",
        title="Chips on the Table",
        description="India's semiconductor ambitions just got Rs 76,000 Cr of backing. What it means for the electronics manufacturing ecosystem and the companies that stand to gain.",
        theme="Technology + Policy",
        image="https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=1200&q=80",
    ),
    models.Story(
        id="story-railway-2026",
        title="Railway Modernization Wave",
        description="India's railways are undergoing a generational transformation - record capex, Vande Bharat expansion, dedicated freight corridors, and Kavach safety rollout. Which companies are positioned to build tomorrow's rail network.",
        theme="Infrastructure + Government",
        image="https://images.unsplash.com/photo-1474487548417-781cb71495f3?auto=format&fit=crop&w=1200&q=80",
    ),
    models.Story(
        id="story-ev-2026",
        title="Electric Vehicles Ecosystem",
        description="India's EV transition is accelerating with the PM e-Drive scheme, falling battery costs, and surging two-wheeler adoption. The entire value chain - from OEMs to battery makers to charging infra - is in play.",
        theme="Auto + Technology",
        image="https://images.unsplash.com/photo-1593941707882-a5bba14938c7?auto=format&fit=crop&w=1200&q=80",
    ),
]

SECTORS = [
    models.SectorData(id="it",        name="IT",           value="-0.9%", positive=False),
    models.SectorData(id="banking",   name="Banking",      value="+1.2%", positive=True),
    models.SectorData(id="pharma",    name="Pharma",       value="+0.6%", positive=True),
    models.SectorData(id="auto",      name="Auto",         value="+1.8%", positive=True),
    models.SectorData(id="energy",    name="Energy",       value="+2.4%", positive=True),
    models.SectorData(id="fmcg",      name="FMCG",         value="-0.3%", positive=False),
    models.SectorData(id="infra",     name="Infra",        value="+3.1%", positive=True),
    models.SectorData(id="metal",     name="Metal",        value="+0.7%", positive=True),
    models.SectorData(id="realty",    name="Realty",       value="+1.5%", positive=True),
    models.SectorData(id="psu-bank",  name="PSU Bank",     value="+0.4%", positive=True),
    models.SectorData(id="pvt-bank",  name="Pvt Bank",     value="+1.1%", positive=True),
    models.SectorData(id="media",     name="Media",        value="-1.2%", positive=False),
]


async def seed(db):
    """Insert initial rows into all tables if they're empty."""
    from app.db.crud import count_rows, bulk_insert

    for model_cls, records in [
        (models.Event, EVENTS),
        (models.NewsArticle, NEWS),
        (models.CalendarEvent, CALENDAR),
        (models.RadarOpportunity, RADAR),
        (models.Story, STORIES),
        (models.SectorData, SECTORS),
    ]:
        count = await count_rows(db, model_cls)
        if count == 0:
            await bulk_insert(db, records)


async def seed_missing_stories(db):
    """Upsert any STORIES entries that are missing - safe to run on an already-seeded DB."""
    from sqlalchemy import select
    for story in STORIES:
        existing = (await db.execute(select(models.Story).where(models.Story.id == story.id))).scalar_one_or_none()
        if not existing:
            db.add(models.Story(
                id=story.id,
                title=story.title,
                description=story.description,
                theme=story.theme,
                image=story.image,
            ))
    await db.commit()


async def seed_missing_calendar(db):
    """Upsert any CALENDAR entries that are missing - safe to run on an already-seeded DB."""
    from sqlalchemy import select
    for event in CALENDAR:
        existing = (await db.execute(select(models.CalendarEvent).where(models.CalendarEvent.id == event.id))).scalar_one_or_none()
        if not existing:
            db.add(models.CalendarEvent(
                id=event.id,
                category=event.category,
                title=event.title,
                date=event.date,
                description=event.description,
            ))
    await db.commit()


async def seed_missing_events(db):
    """Upsert EVENTS entries, restoring authoritative scores that the pipeline may overwrite."""
    from sqlalchemy import select
    for event in EVENTS:
        existing = (await db.execute(select(models.Event).where(models.Event.id == event.id))).scalar_one_or_none()
        if existing:
            # Restore curated scores the pipeline overwrites. Deliberately does NOT
            # touch published_at anymore — it used to get bumped to datetime.now()
            # on every single server restart, which stamped every seed event with
            # the exact same microsecond-precision "just now" timestamp instead of
            # its real curated date (see EVENTS list above), making the Events page
            # show garbled dates and collapsing the 7-day impact trend onto one day.
            existing.impact_score = event.impact_score
            existing.confidence   = event.confidence
            existing.category     = event.category
            if event.sectors:
                existing.sectors = event.sectors
            if event.companies:
                existing.companies = event.companies
        else:
            db.add(models.Event(
                id=event.id,
                title=event.title,
                summary=event.summary,
                impact_score=event.impact_score,
                confidence=event.confidence,
                sectors=event.sectors,
                companies=event.companies,
                category=event.category,
                published_at=event.published_at,
            ))
    await db.commit()
