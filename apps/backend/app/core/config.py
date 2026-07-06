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

    # ── AI Providers (multi-provider fallback chain) ──────────────────────────
    # OmniRoute — self-hosted local router, routes to free providers automatically
    # Set to http://omniroute:20128/v1 when running via docker-compose
    omniroute_url: str = ""

    # Groq — free tier: 14,400 req/day for fast 8B models (console.groq.com)
    groq_api_key: str = ""

    # Cerebras — free tier: 10,000 req/day, fastest inference (cloud.cerebras.ai)
    cerebras_api_key: str = ""

    # Gemini — free tier: 1,500 req/day, 4M tokens/day (aistudio.google.com)
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"

    # OpenRouter — free tier fallback (openrouter.ai)
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "meta-llama/llama-3.3-70b-instruct:free"

    # Legacy providers (kept for future use)
    deepseek_api_key: str = ""
    openai_api_key: str = ""

    # ── Finnhub ───────────────────────────────────────────────────────────────
    finnhub_api_key: str = ""

    # ── Fyers (primary market data provider) ──────────────────────────────────
    # Get credentials at https://myapi.fyers.in/dashboard
    # app_id format: "XXXXXXXXXX-100" (your client_id)
    # Generate access_token once per day via /api/data/auth/fyers flow
    fyers_client_id:    str = ""   # e.g. "XXXXXXXXXX-100"
    fyers_secret_key:   str = ""   # app secret from Fyers dashboard
    fyers_access_token: str = ""   # daily access token (inject via env or /auth flow)
    fyers_redirect_uri: str = "https://127.0.0.1:8000/api/data/auth/callback"

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
        extra = "ignore"  # silently skip any unrecognised env vars


settings = Settings()
