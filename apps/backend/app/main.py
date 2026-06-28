from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.db.session import engine
from app.db.base import Base


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create all tables on startup (idempotent)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Seed initial content data if tables are empty
    from app.db.session import AsyncSessionLocal
    from app.db.seed import seed
    async with AsyncSessionLocal() as db:
        await seed(db)

    yield

    await engine.dispose()


app = FastAPI(
    title="IG Market Intelligence API",
    description="Backend API for event-driven market intelligence",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.backend_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.api import dashboard, events, news, stories, radar, calendar, stocks, sectors, indices

app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(events.router, prefix="/api/events", tags=["events"])
app.include_router(news.router, prefix="/api/news", tags=["news"])
app.include_router(stories.router, prefix="/api/stories", tags=["stories"])
app.include_router(radar.router, prefix="/api/radar", tags=["radar"])
app.include_router(calendar.router, prefix="/api/calendar", tags=["calendar"])
app.include_router(stocks.router, prefix="/api/stocks", tags=["stocks"])
app.include_router(sectors.router, prefix="/api/sectors", tags=["sectors"])
app.include_router(indices.router, prefix="/api/indices", tags=["indices"])


@app.get("/health")
def health_check():
    return {"status": "ok"}
