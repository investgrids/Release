from __future__ import annotations

from typing import List
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "IG Market Intelligence"
    backend_cors_origins: List[str] = ["http://localhost:3000"]
    log_level: str = "INFO"
    json_logs: bool = False          # True in production for structured JSON

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str = "sqlite+aiosqlite:///./ig_dev.db"
    db_pool_size: int = 10
    db_max_overflow: int = 20

    # ── Redis ─────────────────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"
    redis_ttl_default: int = 300          # 5 min
    redis_ttl_dashboard: int = 900        # 15 min
    redis_ttl_opportunity: int = 900      # 15 min
    redis_ttl_event: int = 900            # 15 min
    redis_ttl_market: int = 60            # 1 min for live prices
    redis_ttl_news: int = 600             # 10 min

    # ── AI Provider ───────────────────────────────────────────────────────────
    ai_provider: str = "openrouter"

    # DeepSeek
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-chat"

    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # Gemini
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"

    # OpenRouter (default — free tier)
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "deepseek/deepseek-chat-v3-0324:free"

    # ── Finnhub ───────────────────────────────────────────────────────────────
    finnhub_api_key: str = ""

    # ── Scheduler ─────────────────────────────────────────────────────────────
    # Ingest intervals (seconds)
    ingest_news_interval_sec: int = 900       # 15 min — NSE/BSE/RSS
    ingest_policy_interval_sec: int = 3600    # 1 hr  — RBI/PIB/SEBI

    # Daily precompute windows (IST = UTC+5:30)
    daily_generate_hour_ist: int = 6          # 6:00 AM — generate intelligence
    daily_precompute_hour_ist: int = 7        # 7:00 AM — write to Redis

    # Legacy worker intervals (kept for backward compat — APScheduler now drives timing)
    news_worker_interval_sec: int = 900
    announce_worker_interval_sec: int = 3600
    opportunity_worker_interval_sec: int = 86400
    event_enrichment_interval_sec: int = 300

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
