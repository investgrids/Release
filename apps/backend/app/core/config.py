from __future__ import annotations

import os
from typing import List
from pydantic_settings import BaseSettings


def _default_cors() -> List[str]:
    origins = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        # release-web (apps/web) — the actual production Vercel project.
        # marketripple.in isn't purchased yet, so release-web-pi.vercel.app
        # is the real, currently-used prod URL; kept alongside the other
        # stable aliases (railway alias ls) and the future custom domain so
        # this doesn't regress again once the domain is bought.
        "https://marketripple.in",
        "https://www.marketripple.in",
        "https://release-web-pi.vercel.app",
        "https://release-web-investgrids-3322s-projects.vercel.app",
        "https://release-web-investgrids-3322-investgrids-3322s-projects.vercel.app",
        "https://release-web-git-main-investgrids-3322s-projects.vercel.app",
    ]
    # Allow any Vercel preview/production deployment automatically
    vercel_url = os.environ.get("VERCEL_URL", "")
    frontend_url = os.environ.get("FRONTEND_URL", "")
    if vercel_url:
        origins.append(f"https://{vercel_url}")
    if frontend_url:
        origins.append(frontend_url)
    return origins


class Settings(BaseSettings):
    app_name: str = "IG Market Intelligence"
    backend_cors_origins: List[str] = []
    # Set on Railway — MUST be the real production domain (https://www.marketripple.in),
    # never a Vercel preview subdomain. Used to build canonical_url/mainEntityOfPage
    # for every AIPE-published article (see aipe/publisher.py) — a stale preview
    # domain here silently tells Google to canonicalize every article to a
    # non-production URL (confirmed live in the SEO/Growth audit's Critical
    # Finding #2: FRONTEND_URL was still release-web-pi.vercel.app long after
    # marketripple.in went live).
    frontend_url: str = ""
    log_level: str = "INFO"
    json_logs: bool = False          # True in production for structured JSON

    # ── Admin / internal endpoints ───────────────────────────────────────────
    # Shared secret for write/ops endpoints (graph mutations, publishing
    # retry, etc). Set on Railway; unset locally disables those endpoints
    # rather than leaving them open.
    admin_api_key: str = ""

    # Shared secret for the media worker -> frontend on-demand revalidation
    # webhook (POST /api/revalidate). Same "unset locally disables it"
    # posture as admin_api_key — a missed revalidation just means the page
    # catches up at its next natural cache window, not a broken state.
    revalidate_secret: str = ""

    # ── Database ──────────────────────────────────────────────────────────────
    # On Railway: set DATABASE_URL to sqlite+aiosqlite:////data/ig.db
    # (note 4 slashes = absolute path /data/ig.db on the mounted volume)
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

    # Mistral — La Plateforme (console.mistral.ai)
    mistral_api_key: str = ""

    # OpenRouter — free tier fallback (openrouter.ai)
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "meta-llama/llama-3.3-70b-instruct:free"

    # Cloudflare Workers AI — free tier: 10,000 neurons/day shared pool across
    # all models on the account (dash.cloudflare.com -> Workers AI). Used for
    # the glm-4.7-flash tier in ai_service.py's fallback chain.
    cloudflare_account_id: str = ""
    cloudflare_api_token: str = ""

    # Z.ai direct (open.bigmodel.cn) — glm-4.7-flash free tier. Endpoint/auth
    # confirmed correct but the account is currently 429'ing on every request;
    # not wired into ai_service.py's fallback chain until that's resolved.
    zai_api_key: str = ""

    # NVIDIA NIM — "best reasoning" model tier for the AI pipeline's Decision
    # Intelligence explanation stage (integrate.api.nvidia.com, OpenAI-compatible).
    nvidia_api_key: str = ""
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    nvidia_model: str = "nvidia/nemotron-3-ultra-550b-a55b"

    # Legacy single-provider pipeline (app/pipeline/event_pipeline.py) — always
    # routes through OpenRouter's free tier, matching every other AI call in
    # this codebase. Do not point this at a paid provider.
    ai_provider: str = "openrouter"

    # Legacy providers (kept for future use)
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-chat"
    openai_api_key: str = ""

    # ── Outbound email (transactional notifications, e.g. feedback delivery) ──
    # Set on Railway to enable. Unset locally disables it — email_service.py
    # logs a warning and no-ops rather than failing the request that
    # triggered it (matches admin_api_key's "unset = feature off" posture).
    # Hostinger Mail API (bearer token) — support@marketripple.in's real
    # mailboxResourceId, from GET /api/v1/me with the token below.
    hostinger_mail_api_token: str = ""
    hostinger_mailbox_resource_id: str = ""
    feedback_notify_email: str = "support@marketripple.in"

    # ── Finnhub ───────────────────────────────────────────────────────────────
    finnhub_api_key: str = ""

    # ── Fyers (primary market data provider) ──────────────────────────────────
    # Get credentials at https://myapi.fyers.in/dashboard
    # App-level connection — no per-user auth needed.
    # Token is auto-refreshed daily via TOTP if login_id/pin/totp_key are set.
    fyers_client_id:    str = ""   # e.g. "XXXXXXXXXX-100"
    fyers_secret_key:   str = ""   # app secret from Fyers dashboard
    fyers_access_token: str = ""   # optional: inject pre-generated token
    fyers_redirect_uri: str = "https://127.0.0.1:8000/api/data/auth/callback"

    # TOTP-based automated daily login (no browser / user interaction needed)
    # Set these on Railway to enable fully automated token refresh at 5:30 AM IST
    fyers_login_id:  str = ""   # your Fyers account login ID (e.g. "XY12345")
    fyers_pin:       str = ""   # your Fyers 4/6-digit PIN
    fyers_totp_key:  str = ""   # TOTP secret from Fyers security settings

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

    # ── Fact Grounding (AI Article Pipeline fix, 2026-08-10) ─────────────────
    # Shadow/log-only by default: validate_fact_grounding() always RUNS and
    # logs every violation (see publisher.py), but only actually blocks
    # publish when this is true. Deliberately starting False — per the
    # explicit rollout plan — to observe real production behavior first
    # (violation rate, and how often fetch_price_moves() hits a total
    # failure) before turning this into a hard gate. Flip to true on Railway
    # once a day or two of shadow logs look clean.
    fact_grounding_enforce: bool = False

    # ── Opportunity V2 promotion (V2-B, 2026-08-24) ──────────────────────────
    # The one switch that moves the whole system's public posture at once —
    # per the original remediation plan's Batch E design ("one config change
    # later moves every consumer atomically. Do not flip the default in this
    # batch — that's the actual cutover"). "v1" (default) is today's real,
    # unchanged behavior: job_daily_opportunities keeps writing, V1 pages
    # stay indexed, the sitemap keeps listing V1 numeric URLs, and every V1
    # read consumer (related.py, sectors.py, weekend_intelligence.py,
    # ai_search/pipeline.py, live_intelligence.py, company_intelligence.py,
    # intelligence/engine.py — see V2-B's own audit) is untouched. "v2" is
    # the promoted state: V1's generation job stops (see scheduler.py),
    # run_shadow_pass becomes the sole writer, V1 pages get noindex,follow
    # (V1 code/tables/reads are NOT deleted — this is promotion, not
    # retirement), and the sitemap emits V2 canonical slugs. Flipping this
    # to "v2" is the actual cutover decision and is explicitly NOT done by
    # this settings default — a human decides when, after the observation
    # window the owner specified.
    opportunity_read_source: str = "v1"  # "v1" | "v2"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # silently skip any unrecognised env vars

    @property
    def opportunity_v2_promoted(self) -> bool:
        return self.opportunity_read_source == "v2"

    @property
    def is_production(self) -> bool:
        """True on Railway prod (JSON_LOGS=true is already the existing
        prod/dev signal, set in .env.example and used by main.py's startup
        log). Reused here to gate anything that must never run against real
        users: placeholder/demo data endpoints and destructive or
        fabricated-content seed operations."""
        return self.json_logs


settings = Settings()
