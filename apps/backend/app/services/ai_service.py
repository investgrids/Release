"""
AI service — multi-provider free-tier AI with automatic fallback.

Provider chain (empirically-reliable-first, auto-skips exhausted providers —
see _call_with_fallback for the 2026-07-26 reordering rationale):
  1. Groq high-quality — gpt-oss-120b/20b, 1,000 req/day each
  2. Cerebras          — gpt-oss-120b, no-op until billing is set up (402)
  3. Groq fast         — qwen3.6-27b/compound/compound-mini/gpt-oss-safeguard-20b
  4. OpenRouter large  — 550B, 120B, 31B, 20B free models (account-wide cap:
                         1,000 req/day once $10+ in credits is on file, tight
                         free-tier daily cap otherwise — NOT per-model, see
                         the P0.5 capacity writeup)
  5. Mistral           — mistral-small/open-mistral-nemo, La Plateforme free
                         "Experiment" tier: 2 RPM account-wide (verified —
                         this is the tightest real ceiling in the whole chain).
                         2026-08-22: MISTRAL_API_KEY is currently invalid
                         (confirmed via live probe — Mistral's own API
                         returns 401 "Invalid API Key" on every model) — this
                         tier is a hard no-op until the key is rotated in
                         Mistral's La Plateforme console and updated in
                         Railway's env vars. Not fixable from this code.
  6. Gemini            — 2026-08-22: gemini-2.5-flash/-flash-lite were BOTH
                         retired ("no longer available to new users" per
                         Google's own error body) — replaced with the
                         current live models (gemini-3.6-flash /
                         gemini-3.5-flash-lite), confirmed via live probe.
  7. OpenRouter small  — remaining free models (same account-wide cap as #4)
  8. Cloudflare Workers AI — glm-4.7-flash, separate free account (10,000
                         neurons/day pool), added 2026-08-05

  2026-08-22 live-probe audit (every tier tested directly against its own
  provider with the real production keys, not inferred from app-level
  errors): llama-3.3-70b-versatile and llama-3.1-8b-instant no longer exist
  on this Groq account at all ("model_not_found" — Groq's account-level
  model catalog no longer includes either, confirmed via GET /models);
  poolside/laguna-m.1:free no longer exists on OpenRouter ("No endpoints
  found"); OpenRouter's remaining free models are fine, just genuinely
  exhausted on the account-wide free-models-per-day quota right now (429,
  self-heals on their own daily reset — not a code bug); Gemini's key is
  valid but both configured models were retired (see #6 above); Mistral's
  key itself is invalid (see #5 above). This is what was silently forcing
  every caller (commodities insights, opening-prediction's AI layer, the
  event-classification pipeline, etc.) onto their generic canned fallback
  text on nearly every request.

Each model that returns HTTP 429 (rate-limited) is remembered in _EXHAUSTED
and skipped on future calls for a cooldown window (_EXHAUSTED_COOLDOWN_S) —
long enough to ride out a per-minute throttle without hammering it, short
enough that a model isn't permanently dead for the rest of the process from
one transient 429.
"""
import asyncio
import re
import time
import httpx
import structlog
from collections import deque
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal
from app.core.config import settings
from app.core.redis import cache_get, cache_set

Priority = Literal["interactive", "background"]

log = structlog.get_logger(__name__)

# ── Provider endpoints ────────────────────────────────────────────────────────
_OR_URL       = "https://openrouter.ai/api/v1/chat/completions"
_GROQ_URL     = "https://api.groq.com/openai/v1/chat/completions"
_CEREBRAS_URL = "https://api.cerebras.ai/v1/chat/completions"
_GEMINI_URL   = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
_MISTRAL_URL  = "https://api.mistral.ai/v1/chat/completions"
_NVIDIA_PATH  = "/chat/completions"   # appended to settings.nvidia_base_url
# Cloudflare Workers AI — free tier, 10,000 neurons/day shared pool, account
# ID baked into the URL path (fixed per deployment, not per-call).
_CLOUDFLARE_URL = f"https://api.cloudflare.com/client/v4/accounts/{settings.cloudflare_account_id}/ai/v1/chat/completions"

# Models that have returned 429 — skipped for a cooldown window, not forever.
# A generic 429 doesn't distinguish "hit today's real daily quota" from "briefly
# tripped a per-minute rate limit" — a permanent-until-restart blacklist (the
# original design) meant a short burst of per-minute throttling on a handful of
# models could permanently starve the whole fallback chain for the rest of the
# process. Verified live: running the AI Search benchmark at a steady ~9
# requests/min (well within every provider's stated daily quota) exhausted 18
# of ~24 configured models within 5 minutes of a fresh restart, and every
# subsequent query silently fell back to the generic degraded template. A
# short cooldown lets a model that was only briefly throttled recover within
# the same process; a model that's genuinely out for the day just keeps
# getting retried (and re-429'd) every cooldown window, which costs one
# wasted round-trip per model per window — negligible next to the alternative
# of the whole chain going dark.
_EXHAUSTED: dict[str, float] = {}   # model -> monotonic time it was marked exhausted
_EXHAUSTED_COOLDOWN_S = 120.0


def _is_exhausted(model: str) -> bool:
    marked_at = _EXHAUSTED.get(model)
    if marked_at is None:
        return False
    if time.monotonic() - marked_at >= _EXHAUSTED_COOLDOWN_S:
        _EXHAUSTED.pop(model, None)
        return False
    return True


# ── Per-tier priority-aware concurrency control ─────────────────────────────
#
# _EXHAUSTED (above) tracks WHICH models are rate-limited; this tracks HOW
# MANY concurrent attempts each tier allows, and who gets the next free slot
# when both an interactive (a human is waiting) and a background (nothing
# user-facing is blocked) caller want the same tier at once. Sits in front
# of _is_exhausted, doesn't replace it — a genuinely rate-limited model is
# still skipped for everyone regardless of who's asking.
#
# P0 fix (2026-08): before this, 25 call sites across the backend — AI
# Search plus 4 other live API routes plus TriageWorker/StoryEngine/AIPE's
# scheduled cycles — all shared the same 7 provider tiers with zero
# concurrency control. Verified live: 4 concurrent AI Search requests alone
# pushed 11/14 into the hardcoded degraded-boilerplate fallback, with
# TriageWorker's own calls interleaved in the same rate-limit/cooldown
# window. This limiter bounds concurrent attempts per tier (so no burst,
# from any source, can single-handedly exhaust it) and lets a live request
# jump ahead of a queued background one for whichever slot frees up next.
class PriorityTierLimiter:
    """Bounded per-tier concurrency gate with two-level priority.

    Interactive waiters are always granted a freed slot before background
    waiters, regardless of arrival order — a background call that's been
    queued longer never blocks a human who's actively waiting.
    """

    def __init__(self, name: str, capacity: int):
        self.name = name
        self.capacity = capacity
        self._in_flight = 0
        self._interactive_waiters: deque[asyncio.Future] = deque()
        self._background_waiters: deque[asyncio.Future] = deque()
        # Wall-clock entry time for every currently-queued background
        # waiter, oldest first — lets us log how long the longest-waiting
        # background call has been stuck, without adding a periodic
        # sampler. See oldest_background_wait_s().
        self._background_enqueued_at: deque[float] = deque()

    def oldest_background_wait_s(self) -> float:
        """Age in seconds of the longest-waiting queued background call for
        this tier, or 0.0 if none are waiting. Cheap — just reads the front
        of a deque. Logged on every acquire so a sustained starvation
        pattern (e.g. TriageWorker going quiet on a busy trading day because
        interactive traffic keeps winning every slot) shows up in logs
        before it shows up as "why hasn't triage processed anything in 20
        minutes" — see the P0 task file's Step 2 condition on not adding a
        reserved-floor guarantee until this metric actually shows the
        problem happening."""
        if not self._background_enqueued_at:
            return 0.0
        return time.monotonic() - self._background_enqueued_at[0]

    async def acquire(self, priority: Priority) -> None:
        # Fast path: this check-then-increment is only safe because nothing
        # `await`s between them — Python/asyncio only switches tasks at an
        # `await` point (or a handful of other explicit yield points), so
        # this whole branch runs as one atomic step from every other task's
        # perspective, even though PriorityTierLimiter itself is never
        # touched from more than one OS thread. If this ever gets "cleaned
        # up" to call something async (a cache lookup, a log call that
        # awaits, etc.) before `self._in_flight += 1`, that guarantee breaks
        # silently — two tasks could both read `_in_flight < capacity` as
        # true and both proceed, over-subscribing the tier. Keep this
        # branch synchronous.
        if self._in_flight < self.capacity:
            self._in_flight += 1
            return

        loop = asyncio.get_event_loop()
        fut: asyncio.Future = loop.create_future()
        if priority == "interactive":
            self._interactive_waiters.append(fut)
        else:
            self._background_waiters.append(fut)
            self._background_enqueued_at.append(time.monotonic())
        await fut

    def release(self) -> None:
        # Hand the freed slot straight to the oldest interactive waiter if
        # one exists; only fall through to background waiters when none do.
        # _in_flight is intentionally left unchanged on a handoff — one
        # release + one grant cancel out, so the occupancy count stays
        # correct without a separate decrement/increment pair.
        if self._interactive_waiters:
            fut = self._interactive_waiters.popleft()
            if not fut.done():
                fut.set_result(None)
                return
        while self._background_waiters:
            fut = self._background_waiters.popleft()
            self._background_enqueued_at.popleft()
            if not fut.done():
                fut.set_result(None)
                return
        self._in_flight -= 1


# Starting caps: 4 for the two highest-real-quota Groq tiers, 3 for the
# rest — reasoned proposals from the P0 task file, not measured values.
# Tune after real traffic data; don't treat these as final.
_TIER_LIMITERS: dict[str, PriorityTierLimiter] = {
    "groq-hq":          PriorityTierLimiter("groq-hq", capacity=4),
    "cerebras":         PriorityTierLimiter("cerebras", capacity=4),
    "groq-fast":        PriorityTierLimiter("groq-fast", capacity=4),
    "openrouter-hq":    PriorityTierLimiter("openrouter-hq", capacity=3),
    # Corrected from capacity=3 (a reasoned guess) to 2 after real quota
    # research: Mistral's free "Experiment" tier is rate-limited to 2 RPM
    # account-wide, not per-model — a cap of 3 guaranteed self-inflicted 429s
    # any time 3 interactive calls landed on this tier together, which is
    # exactly the contention hotspot the P0.5 load test surfaced.
    "mistral":          PriorityTierLimiter("mistral", capacity=2),
    "gemini":           PriorityTierLimiter("gemini", capacity=3),
    "openrouter-small": PriorityTierLimiter("openrouter-small", capacity=3),
    # Cloudflare Workers AI — separate free account/quota (10,000 neurons/day
    # pool), no official concurrency limit published; capacity=2 is a
    # conservative starting guess like the original 7, not a measured value.
    "cloudflare-workers-ai": PriorityTierLimiter("cloudflare-workers-ai", capacity=2),
}

# How long a caller will wait for a tier's semaphore before moving on to the
# next tier in the chain — short for interactive (a human is waiting, try
# the next tier fast), long for background (nothing user-facing depends on
# it, and waiting longer here means less pressure on the lower tiers an
# interactive fallback would otherwise land on).
_INTERACTIVE_TIER_WAIT_S = 1.5
_BACKGROUND_TIER_WAIT_S = 25.0


@asynccontextmanager
async def _tier_slot(tier: str, priority: Priority):
    """`async with _tier_slot(tier, priority) as acquired:` — `acquired` is
    False if the wait budget (short for interactive, long for background)
    elapsed before a slot freed up, in which case the caller should move on
    to the next tier without ever having held one. When True, the slot is
    guaranteed released on exit — including on exception — so a failed or
    cancelled provider call can never leak a permanently-held slot.

    A plain bool return from a non-context-managed helper would put the
    burden of "always release, even on exception" on every one of the 7
    tier loops in _call_with_fallback; doing it here means that's only
    ever written once.

    Always logs the wait so Step 4 verification (interactive-blocked-
    behind-background, per-tier wait times) has real data instead of an
    assumption that the design works."""
    limiter = _TIER_LIMITERS[tier]
    timeout = _INTERACTIVE_TIER_WAIT_S if priority == "interactive" else _BACKGROUND_TIER_WAIT_S
    t0 = time.monotonic()
    try:
        await asyncio.wait_for(limiter.acquire(priority), timeout=timeout)
    except asyncio.TimeoutError:
        log.info("ai.tier_slot_timeout", tier=tier, priority=priority, waited_s=round(time.monotonic() - t0, 2))
        yield False
        return

    waited = time.monotonic() - t0
    if waited > 0.05:  # only log when there was real contention, not the near-zero fast path
        log.info(
            "ai.tier_slot_wait", tier=tier, priority=priority, waited_s=round(waited, 2),
            oldest_background_wait_s=round(limiter.oldest_background_wait_s(), 2),
        )
    try:
        yield True
    finally:
        limiter.release()

# Lightweight in-process AI usage counters for the Ops Dashboard — same
# "resets on deploy, not a DB table" pattern as publisher.py's _STATS.
# Populated at the single choke-point every AI call passes through
# (_call_provider), so it covers every caller in the app, not just AIPE.
_AI_USAGE: dict = {
    "calls_total": 0, "calls_success": 0, "calls_failed": 0, "fallback_invocations": 0,
    "tokens_total": 0, "latency_ms_total": 0.0, "cache_hits": 0, "cache_misses": 0,
    "timeouts": 0, "last_call_at": None, "last_success_at": None,
    "last_error_at": None, "last_error": None, "last_provider": None,
}


def get_ai_usage_stats() -> dict:
    total = _AI_USAGE["calls_total"] or 1
    cache_total = (_AI_USAGE["cache_hits"] + _AI_USAGE["cache_misses"]) or 1
    # A "retry" is any provider call beyond the first attempt within one
    # logical _call_with_fallback() invocation — i.e. the fallback chain
    # had to move to a second/third/... model to get an answer.
    retries = max(0, int(_AI_USAGE["calls_total"] - _AI_USAGE["fallback_invocations"]))
    success_rate = round(_AI_USAGE["calls_success"] / total * 100, 1) if _AI_USAGE["calls_total"] else None
    return {
        "llm_calls":        int(_AI_USAGE["calls_total"]),
        "tokens_used":      int(_AI_USAGE["tokens_total"]),
        "avg_response_ms":  round(_AI_USAGE["latency_ms_total"] / total, 0),
        "cache_hit_rate":   round(_AI_USAGE["cache_hits"] / cache_total * 100, 1),
        "failures":         int(_AI_USAGE["calls_failed"]),
        "timeouts":         int(_AI_USAGE["timeouts"]),
        "retries":          retries,
        "success_rate":     success_rate,
        "last_call_at":     _AI_USAGE["last_call_at"],
        "last_success_at":  _AI_USAGE["last_success_at"],
        "last_error_at":    _AI_USAGE["last_error_at"],
        "last_error":       _AI_USAGE["last_error"],
        "last_provider":    _AI_USAGE["last_provider"],
        # All providers in the fallback chain (Gemini/Groq/OpenRouter free
        # tier/Cerebras free tier) are free-tier — real spend is $0, not an
        # estimate to fabricate.
        "cost_usd":         0.0,
    }


# ── NVIDIA "best effort" resilience layer ───────────────────────────────────
#
# NVIDIA is the *preferred* reasoning model, never a *required* one. A user
# must never wait on it: every call is bounded by a hard timeout, and a
# circuit breaker stops even attempting NVIDIA for a cooldown period after
# it's been failing repeatedly, so a degraded NVIDIA backend can't add
# latency to every single request. All of this is internal — the provider
# that actually answered a query is never surfaced to the API response, only
# to server-side logs/metrics.

_NVIDIA_TIMEOUT_S = 2.5              # hard cap — never keep a user waiting on this
_CIRCUIT_FAILURE_THRESHOLD = 3        # consecutive failures before the circuit opens
_CIRCUIT_COOLDOWN_S = 60.0            # how long the circuit stays open before a trial call


@dataclass
class _NvidiaMetrics:
    """In-process counters. Per-worker (like _EXHAUSTED) — resets on restart."""
    attempts: int = 0
    successes: int = 0
    timeouts: int = 0
    rate_limited: int = 0     # 429
    server_errors: int = 0    # 5xx
    other_failures: int = 0
    fallbacks: int = 0        # every time a caller had to use the existing chain instead
    circuit_opens: int = 0
    _latencies_ms: list = field(default_factory=list)   # rolling window, capped

    def record_latency(self, ms: float) -> None:
        self._latencies_ms.append(ms)
        if len(self._latencies_ms) > 200:
            self._latencies_ms.pop(0)

    def avg_latency_ms(self) -> float | None:
        return sum(self._latencies_ms) / len(self._latencies_ms) if self._latencies_ms else None

    def snapshot(self) -> dict:
        avg = self.avg_latency_ms()
        return {
            "attempts": self.attempts,
            "successes": self.successes,
            "timeouts": self.timeouts,
            "rate_limited": self.rate_limited,
            "server_errors": self.server_errors,
            "other_failures": self.other_failures,
            "fallbacks": self.fallbacks,
            "circuit_opens": self.circuit_opens,
            "avg_latency_ms": round(avg, 1) if avg is not None else None,
            "success_rate": round(self.successes / self.attempts, 3) if self.attempts else None,
        }


_nvidia_metrics = _NvidiaMetrics()


class _CircuitState:
    CLOSED = "closed"        # normal — calls go through
    OPEN = "open"             # tripped — skip NVIDIA entirely until cooldown elapses
    HALF_OPEN = "half_open"   # cooldown elapsed — allow exactly one trial call


@dataclass
class _CircuitBreaker:
    failure_threshold: int
    cooldown_s: float
    state: str = _CircuitState.CLOSED
    consecutive_failures: int = 0
    opened_at: float = 0.0

    def allow_request(self) -> bool:
        if self.state == _CircuitState.CLOSED:
            return True
        if self.state == _CircuitState.OPEN:
            if time.monotonic() - self.opened_at >= self.cooldown_s:
                self.state = _CircuitState.HALF_OPEN
                return True
            return False
        return True   # HALF_OPEN: let the trial call through

    def record_success(self) -> None:
        self.state = _CircuitState.CLOSED
        self.consecutive_failures = 0

    def record_failure(self) -> None:
        self.consecutive_failures += 1
        should_open = self.state == _CircuitState.HALF_OPEN or self.consecutive_failures >= self.failure_threshold
        if should_open:
            if self.state != _CircuitState.OPEN:
                _nvidia_metrics.circuit_opens += 1
            self.state = _CircuitState.OPEN
            self.opened_at = time.monotonic()


_nvidia_circuit = _CircuitBreaker(
    failure_threshold=_CIRCUIT_FAILURE_THRESHOLD,
    cooldown_s=_CIRCUIT_COOLDOWN_S,
)


def get_nvidia_metrics() -> dict:
    """Snapshot for a future /health or /debug endpoint."""
    return {**_nvidia_metrics.snapshot(), "circuit_state": _nvidia_circuit.state}

# ── Tier 1: OpenRouter HIGH-QUALITY large free models (best reasoning, tried first)
#
# 2026-07-22: verified live against OpenRouter directly. Several entries here
# were returning HTTP 404 "unavailable for free" / "no endpoints found" on
# every single call — OpenRouter had quietly moved them to paid-only or
# removed them, and every AIPE cycle was burning ~9 wasted round-trips on
# this tier alone before ever reaching a model that actually answers. Only
# currently-live free slugs are listed; re-verify before adding more.
_OR_HIGH_QUALITY = [
    "nvidia/nemotron-3-ultra-550b-a55b:free",       # 550B — largest free model
    "nvidia/nemotron-3-super-120b-a12b:free",        # 120B — NVIDIA quality
    "google/gemma-4-31b-it:free",                   # 31B  — Google quality
    "openai/gpt-oss-20b:free",                      # 20B  — GPT OSS mid
]

# ── Tier 1.5: Mistral La Plateforme — verified live 2026-07-22
_MISTRAL_MODELS = [
    "mistral-small-latest",
    "open-mistral-nemo",
]

# ── Tier 2: Gemini
#
# 2026-07-22: gemini-1.5-flash confirmed 404 (deprecated on Google's side).
# 2026-08-05: gemini-2.0-flash was ALSO retired by Google (March 2026) —
# every call through this tier has been silently failing on a dead model
# name on top of the missing key below. Replaced with the (then-)current
# free 2.5 models.
#
# 2026-08-22: gemini-2.5-flash and gemini-2.5-flash-lite are BOTH now
# retired too — live probe against the real production key gets back
# Google's own explicit error: "This model models/gemini-2.5-flash is no
# longer available to new users. Please update your code to use
# models/gemini-3.6-flash." (and models/gemini-3.5-flash-lite for the lite
# variant). GEMINI_API_KEY itself is valid (confirmed via GET /v1beta/
# openai/models) — the earlier "key is empty" note above is stale; this
# tier was failing purely on dead model names. Replaced with the current
# live models, each confirmed 200 via a real chat completion.
_GEMINI_MODELS = [
    "gemini-3.6-flash",
    "gemini-3.5-flash-lite",
]

# ── Tier 3: Groq HIGH-QUALITY (best Groq models, 1,000 req/day each)
#
# 2026-07-22: qwen/qwen3-32b and the llama-4-scout slug both verified 404
# ("model does not exist") against Groq directly — deprecated/renamed on
# Groq's side. Removed rather than left to fail every cycle.
#
# 2026-08-22: llama-3.3-70b-versatile ALSO confirmed gone — live probe
# against GET https://api.groq.com/openai/v1/models on the real production
# key shows this account's entire catalog no longer includes any llama-*
# chat model at all (just openai/gpt-oss-*, qwen/qwen3.6-27b, groq/compound*,
# allam-2-7b, prompt-guard, and whisper). Removed; no direct replacement
# exists in this account's catalog, so the tier is just the two real models.
_GROQ_HIGH = [
    "openai/gpt-oss-120b",                       # 1,000 req/day — highest quality on Groq
    "openai/gpt-oss-20b",                        # 1,000 req/day — solid mid-tier
]

# ── Tier 4: Groq FAST (14,400 req/day — high volume workhorse when quality tiers exhaust)
#
# 2026-08-22: llama-3.1-8b-instant confirmed gone the same way as
# llama-3.3-70b-versatile above (same live probe). Replaced the lost volume
# backstop with gpt-oss-safeguard-20b (confirmed real and working via live
# probe) — a safety-tuned reasoning variant. See _GROQ_REASONING_EFFORT
# below for how its (and qwen3.6-27b's) reasoning overhead is tamed.
_GROQ_FAST = [
    "qwen/qwen3.6-27b",           # 1,000 req/day — mid quality
    "groq/compound-mini",         # 250 req/day   — Groq native
    "groq/compound",              # 250 req/day   — Groq native larger
    "openai/gpt-oss-safeguard-20b", # reasoning model — see _GROQ_REASONING_EFFORT
]

# `reasoning_effort` handling for Groq's reasoning-tuned models — NOT one
# universal value. Live-probed per model on 2026-08-22 (every combination
# actually POSTed to Groq, not guessed from docs):
#   - openai/gpt-oss-* (Harmony format): reasoning lives in a SEPARATE
#     `reasoning` field, never leaks into `content` — but still spends
#     hidden reasoning_tokens out of the same max_tokens budget as the
#     visible answer, and only accepts "low"/"medium"/"high" ("none" is a
#     400 "must be one of low, medium, or high"). Confirmed: a 1100
#     max_tokens call to gpt-oss-safeguard-20b returned only 353 chars,
#     truncated mid-string, with default effort; the identical call with
#     "low" finished naturally (finish_reason="stop", reasoning_tokens=36
#     of 1100) with a complete, valid answer.
#   - qwen/qwen3.6-27b: the opposite problem — its reasoning is NOT
#     separated, it's inlined directly in `content` as a literal
#     <think>...</think> block (see _strip_reasoning above, which handles
#     this defensively regardless), and it only accepts "none"/"default"
#     ("low" is a 400 "must be one of none or default"). "none" suppresses
#     the <think> block at the source — confirmed: content="OK" directly,
#     vs. "default" reproducing the exact <think> leak.
#   - groq/compound / groq/compound-mini: do NOT support this parameter at
#     all — sending it in ANY value is a 400 "reasoning_effort is not
#     supported with this model". Deliberately absent from this dict; the
#     conditional below only sets the param for keys present here.
_GROQ_REASONING_EFFORT: dict[str, str] = {
    "openai/gpt-oss-120b": "low",
    "openai/gpt-oss-20b": "low",
    "openai/gpt-oss-safeguard-20b": "low",
    "qwen/qwen3.6-27b": "none",
}

# ── Tier 5: Cerebras (10,000 req/day — ultra-fast inference)
# 2026-07-26: llama3.1-70b/llama3.1-8b confirmed 404 "model does not exist"
# via direct live probe against Cerebras's own API — deprecated on their
# side. gpt-oss-120b is confirmed a real, current model name (probed 402
# Payment Required, not 404) but 402 means this specific API key's account
# needs billing/plan setup on cloud.cerebras.ai before it's actually usable —
# a real account-level step, not something fixable from this code. Kept in
# the list since _call_provider already treats any non-2xx as "try the next
# model" gracefully; this tier is effectively a no-op until billing is set up.
_CEREBRAS_MODELS = [
    "gpt-oss-120b",
]

# ── Tier 6: OpenRouter smaller free models (final fallback)
#
# 2026-07-22: same live-verification pass as Tier 1 — laguna-xs.2, the
# llama-3.2-3b slug, dolphin-mistral, and both liquid/lfm-2.5 entries all
# 404'd (deprecated / no endpoints). Removed.
#
# 2026-08-22: poolside/laguna-m.1:free ALSO confirmed dead ("No endpoints
# found for poolside/laguna-m.1:free", live probe) — removed. The rest of
# this tier is fine model-name-wise; every one of them was independently
# confirmed to just be hitting OpenRouter's real account-wide
# free-models-per-day quota (429 "Add 10 credits to unlock 1000 free model
# requests per day") — a genuine capacity ceiling that self-heals on
# OpenRouter's own daily reset, not a dead model to remove.
_OR_SMALL = [
    "nvidia/nemotron-3-nano-30b-a3b:free",
    "nvidia/nemotron-nano-12b-v2-vl:free",
    "nvidia/nemotron-nano-9b-v2:free",
    "google/gemma-4-26b-a4b-it:free",
    "cohere/north-mini-code:free",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
]

# ── Tier 8: Cloudflare Workers AI (free tier, 10,000 neurons/day shared pool
# across every model on the account — a completely separate quota from all
# 7 tiers above, not additional load on any of them). glm-4.7-flash is a
# reasoning model — it emits thinking tokens via `reasoning_content` before
# the final answer, so max_tokens needs enough headroom to clear the
# reasoning phase or `content` comes back null (see _call_provider, which
# already treats null content as "" — same as any other empty response,
# just falls through to the next tier).
_CLOUDFLARE_MODELS = [
    "@cf/zai-org/glm-4.7-flash",
]

async def _cached_async(key: str, ttl: int = 900) -> str | None:
    return await cache_get(key)


async def _store_async(key: str, value: str, ttl: int = 900) -> None:
    await cache_set(key, value, ttl)


_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def _strip_reasoning(content: str) -> str:
    """Some reasoning-tuned free models (confirmed live 2026-08-22 on
    Groq's qwen/qwen3.6-27b) inline their entire chain-of-thought directly
    in `content` as a literal <think>...</think> block instead of a
    separate reasoning/reasoning_content field — unlike Cloudflare's
    glm-4.7-flash (see _CLOUDFLARE_MODELS above), which already keeps them
    apart. Every caller of _call_with_fallback expects the answer, never
    the scratchpad — a caller doing json.loads() on '<think>\\nOkay, the
    user wants...' fails every time, silently degrading that caller to
    its own generic fallback text (this is what was happening to
    commodities' AI insights even after the model-id fixes above got a
    real model responding). A dangling, unclosed <think> (ran out of
    max_tokens mid-thought, before any real answer was ever emitted) is
    treated as no real answer at all, not as literal scratchpad text to
    return — _call_with_fallback's `if result:` check then correctly
    falls through to the next model instead of returning empty prose."""
    if "<think>" not in content.lower():
        return content
    stripped = _THINK_BLOCK_RE.sub("", content).strip()
    if "<think" in stripped.lower():
        return ""
    return stripped


async def _call_provider(
    base_url: str,
    api_key: str,
    model: str,
    prompt: str,
    system: str = "",
    max_tokens: int = 200,
    extra_headers: dict | None = None,
    failure_log: list[dict] | None = None,
) -> str:
    """Generic OpenAI-compatible call. Returns '' on any failure or rate-limit.
    Marks the model as exhausted in _EXHAUSTED on HTTP 429 so future calls skip
    it until the cooldown window elapses (see _EXHAUSTED_COOLDOWN_S above).

    failure_log is optional and additive — when a caller passes a list, every
    skipped/failed attempt appends a structured {model, reason} record to it;
    every existing caller that doesn't pass one gets identical behavior to
    before. Built for triage_worker.py's fallback-visibility logging (see
    that module's docstring) without touching this function's actual
    fallback/retry behavior."""
    _PROVIDER_BY_URL_EARLY = {
        _OR_URL: "openrouter", _GROQ_URL: "groq",
        _CEREBRAS_URL: "cerebras", _GEMINI_URL: "gemini",
        _MISTRAL_URL: "mistral", _CLOUDFLARE_URL: "cloudflare-workers-ai",
    }
    if _is_exhausted(model):
        if failure_log is not None:
            failure_log.append({"model": model, "provider": _PROVIDER_BY_URL_EARLY.get(base_url, "unknown"), "reason": "already_exhausted"})
        return ""

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    headers = {"Content-Type": "application/json", **(extra_headers or {})}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.4,
    }
    if base_url == _GROQ_URL and model in _GROQ_REASONING_EFFORT:
        payload["reasoning_effort"] = _GROQ_REASONING_EFFORT[model]
    _PROVIDER_BY_URL = {
        _OR_URL: "openrouter", _GROQ_URL: "groq",
        _CEREBRAS_URL: "cerebras", _GEMINI_URL: "gemini",
        _MISTRAL_URL: "mistral", _CLOUDFLARE_URL: "cloudflare-workers-ai",
    }
    provider_name = _PROVIDER_BY_URL.get(base_url, "unknown")

    _AI_USAGE["calls_total"] += 1
    _AI_USAGE["last_call_at"] = datetime.now(timezone.utc).isoformat()
    _t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(base_url, json=payload, headers=headers)
            if r.status_code == 429:
                _EXHAUSTED[model] = time.monotonic()
                log.warning("ai.exhausted", model=model, status=429, cooldown_s=_EXHAUSTED_COOLDOWN_S)
                _AI_USAGE["calls_failed"] += 1
                if failure_log is not None:
                    failure_log.append({"model": model, "provider": provider_name, "reason": "429"})
                return ""
            if r.status_code in (402, 503, 529):
                log.warning("ai.rate_limited", model=model, status=r.status_code)
                _AI_USAGE["calls_failed"] += 1
                if failure_log is not None:
                    failure_log.append({"model": model, "provider": provider_name, "reason": f"rate_limited_{r.status_code}"})
                return ""
            r.raise_for_status()
            data = r.json()
            if "error" in data:
                log.warning("ai.api_error", model=model, err=str(data["error"])[:120])
                _AI_USAGE["calls_failed"] += 1
                if failure_log is not None:
                    failure_log.append({"model": model, "provider": provider_name, "reason": "api_error"})
                return ""
            content = data["choices"][0]["message"]["content"]
            _AI_USAGE["latency_ms_total"] += (time.monotonic() - _t0) * 1000
            _AI_USAGE["calls_success"] += 1
            _AI_USAGE["last_success_at"] = datetime.now(timezone.utc).isoformat()
            _AI_USAGE["last_provider"] = provider_name
            usage = data.get("usage") or {}
            if usage.get("total_tokens"):
                _AI_USAGE["tokens_total"] += usage["total_tokens"]
            return _strip_reasoning(content.strip()) if content else ""
    except Exception as exc:
        log.warning("ai.exception", model=model, exc=str(exc)[:120])
        _AI_USAGE["calls_failed"] += 1
        _AI_USAGE["last_error_at"] = datetime.now(timezone.utc).isoformat()
        _AI_USAGE["last_error"] = str(exc)[:200]
        is_timeout = isinstance(exc, httpx.TimeoutException) or "timeout" in str(exc).lower()
        if is_timeout:
            _AI_USAGE["timeouts"] += 1
        if failure_log is not None:
            failure_log.append({"model": model, "provider": provider_name, "reason": "timeout" if is_timeout else "other"})
        return ""


async def _call_nvidia_raw(prompt: str, system: str, max_tokens: int) -> tuple[str, str | None]:
    """
    Low-level NVIDIA call, bounded by `_NVIDIA_TIMEOUT_S`. Returns
    (text, failure_kind) — failure_kind is None on success, else one of
    "timeout" | "rate_limited" | "server_error" | "other". Never raises.
    """
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.nvidia_api_key}",
    }
    payload = {
        "model": settings.nvidia_model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.4,
    }
    url = settings.nvidia_base_url.rstrip("/") + _NVIDIA_PATH
    try:
        async with httpx.AsyncClient(timeout=_NVIDIA_TIMEOUT_S) as client:
            r = await client.post(url, json=payload, headers=headers)
            if r.status_code == 429:
                return "", "rate_limited"
            if r.status_code >= 500:
                return "", "server_error"
            if r.status_code >= 400:
                return "", "other"
            data = r.json()
            if "error" in data:
                return "", "other"
            content = data["choices"][0]["message"]["content"]
            content = _strip_reasoning(content.strip()) if content else ""
            return (content, None) if content else ("", "other")
    except httpx.TimeoutException:
        return "", "timeout"
    except Exception:
        return "", "other"


async def _call_nvidia(prompt: str, system: str = "", max_tokens: int = 900) -> str:
    """
    NVIDIA NIM — the "best reasoning" tier, called on a best-effort basis
    only. A hard `_NVIDIA_TIMEOUT_S` cap and a circuit breaker (see above)
    mean this never adds more than ~2.5s of latency to a request, even when
    NVIDIA is degraded or unreachable — callers always fall back to
    `_call_with_fallback` on an empty result, exactly like every other tier.
    Never raises. Which provider actually answered is logged server-side
    only (`ai.success` / `ai.nvidia.failed`) and never returned to the API
    caller.
    """
    if not settings.nvidia_api_key:
        return ""

    if not _nvidia_circuit.allow_request():
        _nvidia_metrics.fallbacks += 1
        log.info("ai.nvidia.circuit_open_skip")
        return ""

    _nvidia_metrics.attempts += 1
    t0 = time.monotonic()
    text, failure_kind = await _call_nvidia_raw(prompt, system, max_tokens)
    elapsed_ms = (time.monotonic() - t0) * 1000
    _nvidia_metrics.record_latency(elapsed_ms)

    if failure_kind is None:
        _nvidia_metrics.successes += 1
        _nvidia_circuit.record_success()
        log.info("ai.success", provider="nvidia", model=settings.nvidia_model, latency_ms=round(elapsed_ms))
        return text

    if failure_kind == "timeout":
        _nvidia_metrics.timeouts += 1
    elif failure_kind == "rate_limited":
        _nvidia_metrics.rate_limited += 1
    elif failure_kind == "server_error":
        _nvidia_metrics.server_errors += 1
    else:
        _nvidia_metrics.other_failures += 1

    _nvidia_circuit.record_failure()
    _nvidia_metrics.fallbacks += 1
    log.warning(
        "ai.nvidia.failed",
        reason=failure_kind,
        latency_ms=round(elapsed_ms),
        circuit_state=_nvidia_circuit.state,
        consecutive_failures=_nvidia_circuit.consecutive_failures,
    )
    return ""


async def _call_with_fallback(
    prompt: str,
    system: str = "",
    max_tokens: int = 200,
    failure_log: list[dict] | None = None,
    *,
    priority: Priority,
) -> str:
    """
    Try providers in *empirical reliability* order until one returns a
    non-empty response — not just nominal "quality", but what's actually been
    observed to work. Models that recently returned 429 are skipped instantly
    until their cooldown window elapses (see _EXHAUSTED_COOLDOWN_S).

    Chain (reordered 2026-07-26 after live benchmark testing showed OpenRouter's
    free models 429 almost immediately under any sustained load, while Groq
    consistently succeeded — Groq and Cerebras now go first since they're the
    tiers with real, working, high-quota keys; OpenRouter/Mistral/Gemini are
    kept as later-tier headroom):
      1. Groq high-quality models      — 120B, 70B, 32B (1,000 req/day each) — most reliable in testing
      2. Cerebras                      — 10,000 req/day, ultra-fast
      3. Groq fast models              — 8B (14,400 req/day, high-volume workhorse)
      4. OpenRouter large free models  — 550B, 405B, 120B, 70B (best nominal quality, ~50/day each, but 429s fast)
      5. Mistral La Plateforme
      6. Gemini 2.0-flash              — 1,500 req/day (currently a no-op — see Gemini tier comment)
      7. OpenRouter smaller models     — final fallback

    failure_log is optional and purely additive (see _call_provider's
    docstring) — every caller that doesn't pass one sees identical behavior
    to before this parameter existed.
    """
    _AI_USAGE["fallback_invocations"] += 1
    or_headers = {
        "HTTP-Referer": settings.frontend_url or "https://investgrids.com",
        "X-Title": "InvestGrids Market Intelligence",
    }

    # ── Tier 1: Groq high-quality (70B+, 1,000 req/day each) ─────────────────
    if settings.groq_api_key:
        async with _tier_slot("groq-hq", priority) as acquired:
            if acquired:
                for model in _GROQ_HIGH:
                    if _is_exhausted(model):
                        if failure_log is not None:
                            failure_log.append({"model": model, "provider": "groq-hq", "reason": "already_exhausted"})
                        continue
                    result = await _call_provider(_GROQ_URL, settings.groq_api_key, model, prompt, system, max_tokens, failure_log=failure_log)
                    if result:
                        log.info("ai.success", provider="groq-hq", model=model)
                        return result

    # ── Tier 2: Cerebras — ultra-fast, 10,000 req/day ────────────────────────
    if settings.cerebras_api_key:
        async with _tier_slot("cerebras", priority) as acquired:
            if acquired:
                for model in _CEREBRAS_MODELS:
                    if _is_exhausted(model):
                        if failure_log is not None:
                            failure_log.append({"model": model, "provider": "cerebras", "reason": "already_exhausted"})
                        continue
                    result = await _call_provider(_CEREBRAS_URL, settings.cerebras_api_key, model, prompt, system, max_tokens, failure_log=failure_log)
                    if result:
                        log.info("ai.success", provider="cerebras", model=model)
                        return result

    # ── Tier 3: Groq fast (8B, 14,400 req/day — high-volume backstop) ────────
    if settings.groq_api_key:
        async with _tier_slot("groq-fast", priority) as acquired:
            if acquired:
                for model in _GROQ_FAST:
                    if _is_exhausted(model):
                        if failure_log is not None:
                            failure_log.append({"model": model, "provider": "groq-fast", "reason": "already_exhausted"})
                        continue
                    result = await _call_provider(_GROQ_URL, settings.groq_api_key, model, prompt, system, max_tokens, failure_log=failure_log)
                    if result:
                        log.info("ai.success", provider="groq-fast", model=model)
                        return result

    # ── Tier 4: OpenRouter large high-quality models ──────────────────────────
    if settings.openrouter_api_key:
        async with _tier_slot("openrouter-hq", priority) as acquired:
            if acquired:
                for model in _OR_HIGH_QUALITY:
                    if _is_exhausted(model):
                        if failure_log is not None:
                            failure_log.append({"model": model, "provider": "openrouter-hq", "reason": "already_exhausted"})
                        continue
                    result = await _call_provider(_OR_URL, settings.openrouter_api_key, model, prompt, system, max_tokens, or_headers, failure_log=failure_log)
                    if result:
                        log.info("ai.success", provider="openrouter-hq", model=model)
                        return result

    # ── Tier 5: Mistral La Plateforme ──────────────────────────────────────
    if settings.mistral_api_key:
        async with _tier_slot("mistral", priority) as acquired:
            if acquired:
                for model in _MISTRAL_MODELS:
                    if _is_exhausted(model):
                        if failure_log is not None:
                            failure_log.append({"model": model, "provider": "mistral", "reason": "already_exhausted"})
                        continue
                    result = await _call_provider(_MISTRAL_URL, settings.mistral_api_key, model, prompt, system, max_tokens, failure_log=failure_log)
                    if result:
                        log.info("ai.success", provider="mistral", model=model)
                        return result

    # ── Tier 6: Gemini — reliable, 1,500 req/day ─────────────────────────────
    if settings.gemini_api_key:
        async with _tier_slot("gemini", priority) as acquired:
            if acquired:
                for model in _GEMINI_MODELS:
                    if _is_exhausted(model):
                        if failure_log is not None:
                            failure_log.append({"model": model, "provider": "gemini", "reason": "already_exhausted"})
                        continue
                    result = await _call_provider(_GEMINI_URL, settings.gemini_api_key, model, prompt, system, max_tokens, failure_log=failure_log)
                    if result:
                        log.info("ai.success", provider="gemini", model=model)
                        return result

    # ── Tier 7: OpenRouter smaller free models — final fallback ──────────────
    if settings.openrouter_api_key:
        async with _tier_slot("openrouter-small", priority) as acquired:
            if acquired:
                for model in _OR_SMALL:
                    if _is_exhausted(model):
                        if failure_log is not None:
                            failure_log.append({"model": model, "provider": "openrouter-small", "reason": "already_exhausted"})
                        continue
                    result = await _call_provider(_OR_URL, settings.openrouter_api_key, model, prompt, system, max_tokens, or_headers, failure_log=failure_log)
                    if result:
                        log.info("ai.success", provider="openrouter-small", model=model)
                        return result

    # ── Tier 8: Cloudflare Workers AI (glm-4.7-flash) — separate free
    # account/quota from every tier above, added 2026-08-05 during the P0.5
    # capacity investigation. Placed last (unverified under real load) rather
    # than reordered ahead of the known-weak Mistral tier — revisit once this
    # tier has real traffic data behind it, same as the original 7.
    if settings.cloudflare_account_id and settings.cloudflare_api_token:
        async with _tier_slot("cloudflare-workers-ai", priority) as acquired:
            if acquired:
                for model in _CLOUDFLARE_MODELS:
                    if _is_exhausted(model):
                        if failure_log is not None:
                            failure_log.append({"model": model, "provider": "cloudflare-workers-ai", "reason": "already_exhausted"})
                        continue
                    result = await _call_provider(_CLOUDFLARE_URL, settings.cloudflare_api_token, model, prompt, system, max_tokens, failure_log=failure_log)
                    if result:
                        log.info("ai.success", provider="cloudflare-workers-ai", model=model)
                        return result

    log.error("ai.all_providers_failed", exhausted_count=len(_EXHAUSTED))
    return ""


async def get_market_summary(indices: list[dict], events: list[dict], *, priority: Priority) -> str:
    """
    Generate a 2-sentence live market summary for the dashboard.
    Cached for 15 minutes.
    """
    cache_key = "dashboard:ai_summary"
    hit = await _cached_async(cache_key, 900)
    if hit:
        return hit

    index_lines = [
        f"{idx.get('title', idx.get('name', ''))} {idx.get('value', '')} ({idx.get('change', '')})"
        for idx in (indices or [])[:4]
    ]
    event_lines = [
        f"- {e.get('title', '')} [score {int(e.get('impact_score', 0))}]"
        for e in (events or [])[:4]
    ]

    prompt = (
        "Summarize the current Indian stock market in exactly 2 sentences (max 60 words). "
        "Be factual, concise, and forward-looking. Mention index direction, key sector trends, "
        "and one macro factor.\n\n"
        f"Indices:\n{chr(10).join(index_lines) or 'Data unavailable'}\n\n"
        f"Trending events:\n{chr(10).join(event_lines) or 'None'}"
    )
    system = "You are a professional Indian equity market analyst. Respond only with the 2-sentence summary."

    result = await _call_with_fallback(prompt, system, max_tokens=120, priority=priority)

    if not result:
        result = (
            "Indian markets are showing mixed momentum across major indices. "
            "Monitor key sector developments and macro policy signals for near-term direction."
        )

    await _store_async(cache_key, result)
    return result


async def generate_ripple_graph(
    title: str,
    summary: str,
    event_type: str = "macro",
    impact_score: float = 7.0,
    companies: list | None = None,
    sectors: list | None = None,
    *,
    priority: Priority,
) -> dict:
    """
    Generate a comprehensive ripple effect dependency graph for a market event.
    Returns {nodes, edges, insights} dict or {} on failure.
    Cached 1 hour — ripple graphs are stable between refreshes.
    """
    cache_key = f"ripple_graph:{hash(title[:100])}"
    hit = await _cached_async(cache_key, 3600)
    if hit:
        return hit

    companies_str = ", ".join([
        c.get("symbol", c.get("name", "")) for c in (companies or [])[:10]
        if c.get("symbol") or c.get("name")
    ]) or "N/A"
    sectors_str = ", ".join([
        s.get("sector", "") for s in (sectors or [])[:8] if s.get("sector")
    ]) or "N/A"

    system = (
        "You are a senior Indian equity market analyst specializing in dependency and ripple effect analysis. "
        "Generate precise, factual JSON ripple graphs focused on the Indian stock market. "
        "Return ONLY valid JSON, no markdown, no explanation text."
    )

    prompt = (
        f"Analyze this market event and generate a complete ripple dependency graph.\n\n"
        f"Event: {title}\n"
        f"Summary: {summary[:400]}\n"
        f"Type: {event_type}\n"
        f"Impact Score: {impact_score:.1f}/10\n"
        f"Related Companies: {companies_str}\n"
        f"Related Sectors: {sectors_str}\n\n"
        "Return ONLY valid JSON with this structure:\n"
        "{\n"
        '  "nodes": [\n'
        '    {"id":"event_center","label":"<event title truncated>","type":"event","impact":"mixed",'
        f'"impact_strength":{impact_score/10:.1f},"depth":0,"icon":"event","change_direction":"neutral","subtitle":"Impact {impact_score:.0f}/10"}},\n'
        '    {"id":"unique_id","label":"Display Name","type":"commodity","impact":"positive",'
        '"impact_strength":0.85,"depth":1,"icon":"oil","change_direction":"up","subtitle":"+6.2%"}\n'
        "    // 18-24 more nodes across depths 1-4\n"
        "  ],\n"
        '  "edges": [\n'
        '    {"source":"event_center","target":"node_id","relationship":"causes",'
        '"impact_strength":0.9,"confidence":0.92,"explanation":"one sentence","time_horizon":"immediate"}\n'
        "    // 22-32 more edges\n"
        "  ],\n"
        '  "insights": {\n'
        '    "summary":"2-3 sentence executive summary",\n'
        '    "key_drivers":["driver1","driver2","driver3"],\n'
        '    "ripple_strength":{"direct":"High","indirect":"Medium","long_term":"Medium"},\n'
        '    "market_volatility":"High","inflation_risk":"Elevated","growth_impact":"Negative",\n'
        '    "beneficiaries":[{"name":"...","ticker":"NSE_SYMBOL","confidence":0.92,"impact":"Very Positive","reason":"..."}],\n'
        '    "losers":[{"name":"...","ticker":"NSE_SYMBOL","confidence":0.88,"impact":"Very Negative","reason":"..."}],\n'
        '    "impacted_commodities":[{"name":"...","current_price":"...","change_pct":6.21,"positive":true}],\n'
        '    "impacted_sectors":[{"name":"...","strength":"Very High","positive":true}],\n'
        '    "ripple_timeline":[\n'
        '      {"period":"0-7 Days","description":"..."},\n'
        '      {"period":"1-4 Weeks","description":"..."},\n'
        '      {"period":"1-3 Months","description":"..."},\n'
        '      {"period":"3-6 Months","description":"..."}\n'
        "    ]\n"
        "  }\n"
        "}\n\n"
        "Node types: event, commodity, currency, sector, company, policy, indicator\n"
        "Relationships: causes, hurts, benefits, influences, supports, risk, opportunity\n"
        "Time horizons: immediate, short_term, medium_term, long_term\n"
        "Depths: 0=event_center, 1=direct(0-7d), 2=secondary(1-4w), 3=tertiary(1-3m), 4=long-term(3-6m)\n"
        "Generate 20-25 nodes and 25-35 edges. Focus on Indian market context and NSE-listed companies.\n\n"
        "If the triggering event originates OUTSIDE India (a US Federal Reserve/ECB/BoJ decision, China "
        "macro data, a foreign election or conflict), you MUST model the actual India transmission "
        "mechanism explicitly — never leave a global event as a dead-end with no India-specific chain. "
        "For a global rate/monetary event specifically, the primary channel is USD/INR: model both sides "
        "of the currency move — IT and pharma exporters typically benefit from rupee weakness (USD-"
        "denominated revenue), while the oil import bill and import-heavy manufacturers are hurt by it. "
        "Do not present a global event as uniformly positive or negative for India when the real "
        "transmission is two-sided like this."
    )

    raw = await _call_with_fallback(prompt, system, max_tokens=4000, priority=priority)
    if not raw:
        return {}

    try:
        import json, re
        clean = raw.strip()
        if clean.startswith("```"):
            clean = re.sub(r"^```(?:json)?\s*", "", clean)
            clean = re.sub(r"\s*```$", "", clean).strip()
        # Remove JS-style comments before parsing
        clean = re.sub(r"\s*//[^\n]*", "", clean)
        result = _validate_ripple_companies(json.loads(clean))
        await _store_async(cache_key, result)
        return result
    except Exception:
        import json, re
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            try:
                clean2 = re.sub(r"\s*//[^\n]*", "", m.group())
                result = _validate_ripple_companies(json.loads(clean2))
                await _store_async(cache_key, result)
                return result
            except Exception:
                pass
        log.warning("ripple.ai.parse_failed", raw_len=len(raw))
        return {}


def _validate_ripple_companies(result: dict) -> dict:
    """
    Stopgap validation for generate_ripple_graph()'s raw LLM output — there
    was NONE before this (confirmed live, via the real production DB): of
    the 4 real ai_generated ripple graphs stored, one padded a single-
    company "Initiation of Forensic Audit" event with 18 unrelated large-
    caps (MRF, Asian Paints, Bharti Airtel, ONGC...) with no plausible
    connection to the event, and listed "Mindtree" and "LTI" as two
    separate companies years after they merged into LTIM; another invented
    "Energy Efficiency Services" / ticker ENERJEN, which matches no real
    NSE-listed entity in this platform's universe.

    What this DOES fix: drops company-type nodes (and any edge touching
    them) that don't resolve to a real symbol/name/alias in _NSE_UNIVERSE —
    catches both pure inventions (ENERJEN) and stale/pre-merger entities
    (Mindtree, LTI — "mindtree" is now only a valid alias of LTIM, not a
    standalone company, so it correctly fails to resolve on its own).

    What this does NOT fix, on purpose — not solved by this pass, still
    open, tracked as its own follow-up: a real company padded into an
    event it has no real relevance to (the 18-large-caps case) still
    passes, since every one of those tickers IS real; so do fabricated
    confidence/impact_strength scores attached to an otherwise-real
    company. This makes the graph's company nodes real, not necessarily
    relevant or accurately scored — do not read "validated" as "trustworthy."

    Also drops real companies that are simply outside _NSE_UNIVERSE's
    coverage (confirmed live: "NCL Industries Limited," "Capillary
    Technologies India Limited," and "Renew Power" all got dropped from
    real sampled graphs for this reason, not because they're fake) — this
    is a curated ~500-symbol list, not the full NSE. Fail-closed is the
    intended tradeoff for a fabrication stopgap: a real-but-uncovered
    company being dropped is preferable to a fabricated one being kept.

    Matches by id/label/ticker THROUGH aliases, not by ticker alone: the
    prompt asks the model for a "ticker" field, but every real sampled
    response had it null — matching on ticker alone would have validated
    nothing. Exact match first, then a word-boundary-safe substring
    fallback — needed because the exact pass alone produced a real false
    positive on this exact sampled data: the model wrote "Power Grid
    Corporation," but this platform's real entry is named "Power Grid
    Corporation of India" with alias "power grid" — an exact-only match
    would have wrongly dropped a genuinely real company. Same word-
    boundary-substring approach entities.py's own _match_companies already
    uses, not a new pattern.

    The substring fallback only fires for MULTI-WORD aliases (containing a
    space) — found live, against this same sampled data: allowing
    single-word aliases into the substring pass let "Larsen & Toubro
    Infotech Limited" (LTI, merged into LTIM years ago, no longer a
    standalone company) wrongly resolve to LT — the unrelated PARENT
    conglomerate — because LT's own registered aliases include the bare
    surnames "larsen" and "toubro" individually, and both happen to appear
    inside LTI's full name too. A single generic word is common enough to
    coincidentally appear inside an unrelated company's name; a multi-word
    phrase like "power grid" is specific enough that it doesn't. Restricting
    the fallback to phrases keeps the Power Grid fix while dropping LTI
    exactly like the exact-match-only version already correctly did for
    bare "LTI"/"Mindtree" as standalone entities.
    """
    import re

    nodes = result.get("nodes")
    if not isinstance(nodes, list):
        return result

    from app.api.companies import _NSE_UNIVERSE
    alias_to_symbol: dict[str, str] = {}
    for co in _NSE_UNIVERSE:
        for key in [co.get("symbol"), co.get("name"), *(co.get("aliases") or [])]:
            if key:
                alias_to_symbol[key.strip().lower()] = co["symbol"]

    def _resolve(candidates: tuple) -> str | None:
        norm_candidates = [str(c).strip().lower() for c in candidates if c]
        for c in norm_candidates:
            if c in alias_to_symbol:
                return alias_to_symbol[c]
        # Substring fallback, word-boundary-safe, restricted to multi-word
        # aliases only — a single generic word (e.g. "larsen") can
        # coincidentally appear inside an unrelated company's full name;
        # a multi-word phrase (e.g. "power grid") is specific enough that
        # it doesn't. See docstring for the real false positive this caught.
        for c in norm_candidates:
            for alias, symbol in alias_to_symbol.items():
                if " " in alias and len(alias) >= 4 and re.search(rf"\b{re.escape(alias)}\b", c):
                    return symbol
        return None

    valid_ids: set[str] = set()
    kept_nodes: list = []
    dropped: list = []
    for n in nodes:
        if not isinstance(n, dict):
            continue
        if n.get("type") != "company":
            kept_nodes.append(n)
            if n.get("id"):
                valid_ids.add(n["id"])
            continue
        resolved = _resolve((n.get("id"), n.get("label"), n.get("ticker")))
        if resolved:
            kept_nodes.append(n)
            if n.get("id"):
                valid_ids.add(n["id"])
        else:
            dropped.append(n.get("label") or n.get("id"))

    if dropped:
        log.warning("ripple.ai.company_validation_dropped", dropped=dropped[:10])

    result["nodes"] = kept_nodes
    edges = result.get("edges")
    if isinstance(edges, list):
        result["edges"] = [
            e for e in edges
            if isinstance(e, dict) and e.get("source") in valid_ids and e.get("target") in valid_ids
        ]
    return result


async def get_event_ai_summary(title: str, description: str, *, priority: Priority) -> dict:
    """
    Generate AI bullets for a market event.
    Returns {summary, why_it_matters, key_bullets, risk_factors, opportunities}
    """
    cache_key = f"event_ai:{hash(title)}"
    hit = await _cached_async(cache_key, 3600)  # 1-hour cache
    if hit:
        return hit

    prompt = (
        f"Analyze this Indian market event:\nTitle: {title}\nDescription: {description[:500]}\n\n"
        "Return a JSON object with these keys:\n"
        '- "summary": one-sentence plain English summary\n'
        '- "why_it_matters": one sentence on market significance\n'
        '- "key_bullets": list of 3 short bullet strings\n'
        '- "risk_factors": list of 2 risk strings\n'
        '- "opportunities": list of 2 opportunity strings\n'
        "Respond with valid JSON only, no markdown fences."
    )

    raw = await _call_with_fallback(prompt, max_tokens=600, priority=priority)
    if not raw:
        return {}

    try:
        import json, re
        clean = raw.strip()
        if clean.startswith("```"):
            clean = re.sub(r"^```(?:json)?\s*", "", clean)
            clean = re.sub(r"\s*```$", "", clean).strip()
        result = json.loads(clean)
        await _store_async(cache_key, result)
        return result
    except Exception:
        # Try extracting first JSON object from response
        import json, re
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except Exception:
                pass


async def generate_investment_thesis(
    entity_type: str,
    entity_id: str,
    title: str = "",
    description: str = "",
    sector: str = "",
    *,
    priority: Priority,
) -> dict:
    """
    Generate a structured investment thesis for any entity type.
    entity_type: event | company | story | opportunity | ripple | search
    Cached 60 minutes per entity.
    """
    import json, re
    from datetime import datetime, timezone

    cache_key = f"thesis:{entity_type}:{entity_id}"
    hit = await cache_get(cache_key)
    if hit and isinstance(hit, dict) and hit.get("executive_summary"):
        _AI_USAGE["cache_hits"] += 1
        return hit
    _AI_USAGE["cache_misses"] += 1

    system = (
        "You are a senior Indian equity market investment analyst. "
        "Generate structured investment thesis JSON. "
        "Return ONLY valid JSON — no markdown fences, no explanation text."
    )

    entity_label = {
        "event":       "market event",
        "company":     "listed company",
        "story":       "investment theme / market story",
        "opportunity": "investment opportunity",
        "ripple":      "ripple analysis",
        "search":      "market intelligence query",
    }.get(entity_type, "market entity")

    prompt = (
        f"Generate a comprehensive investment thesis for this {entity_label}.\n\n"
        f"Name: {title or entity_id}\n"
        f"Context: {description[:500] if description else 'No additional context.'}\n"
        f"Sector: {sector or 'Diversified'}\n\n"
        "Return ONLY this JSON:\n"
        "{\n"
        '  "executive_summary": "2-3 sentence thesis. Clear, specific, investment-grade language.",\n'
        '  "why_it_matters": "1-2 sentences on why an Indian equity investor must pay attention.",\n'
        '  "business_impact": "1-2 sentences on the near-term business or sector impact.",\n'
        '  "revenue_growth_impact": "1-2 sentences on revenue, margins, or earnings implications.",\n'
        '  "supporting_evidence": [\n'
        '    "Specific data point or event supporting the thesis",\n'
        '    "Sector trend or policy tailwind",\n'
        '    "Historical precedent or analogue"\n'
        "  ],\n"
        '  "competitive_advantages": [\n'
        '    "Key structural moat or advantage",\n'
        '    "Differentiated position in the market"\n'
        "  ],\n"
        '  "key_drivers": [\n'
        '    "Primary catalyst",\n'
        '    "Secondary driver",\n'
        '    "Structural tailwind"\n'
        "  ],\n"
        '  "key_risks": [\n'
        '    "Principal risk that could invalidate the thesis",\n'
        '    "Macro or policy risk",\n'
        '    "Execution or sector-specific risk"\n'
        "  ],\n"
        '  "thesis_strength": 72,\n'
        '  "time_horizon": "Medium-term (6–18 months)"\n'
        "}"
    )

    raw = await _call_with_fallback(prompt, system, max_tokens=700, priority=priority)

    result: dict = {}
    if raw:
        clean = raw.strip()
        if clean.startswith("```"):
            clean = re.sub(r"^```(?:json)?\s*", "", clean)
            clean = re.sub(r"\s*```$", "", clean).strip()
        try:
            result = json.loads(clean)
        except Exception:
            m = re.search(r"\{.*\}", clean, re.DOTALL)
            if m:
                try:
                    result = json.loads(m.group())
                except Exception:
                    pass

    if not result or not result.get("executive_summary"):
        result = {
            "executive_summary": (
                f"{title or entity_id} represents a significant market intelligence signal "
                f"in the Indian equity space, warranting close monitoring by investors "
                f"with exposure to the {sector or 'relevant'} sector."
            ),
            "why_it_matters": (
                "This entity can reveal material investment opportunities or risks "
                "in related sectors and companies. Monitoring it helps position "
                "ahead of broader market re-rating."
            ),
            "business_impact": (
                "Near-term business impact depends on macro conditions and "
                "sector-specific catalysts. Management execution and policy support "
                "are key determinants."
            ),
            "revenue_growth_impact": (
                "Revenue and earnings implications will materialise over the "
                "identified time horizon, driven by operational leverage and "
                "sector tailwinds."
            ),
            "supporting_evidence": [
                "Strong domestic institutional flows supporting sector resilience",
                "Government policy and capex alignment with sector growth drivers",
                "Historical precedent shows similar setups led to meaningful re-rating",
            ],
            "competitive_advantages": [
                "Structural market position with high barriers to entry",
                "Policy and regulatory tailwinds providing a durable competitive moat",
            ],
            "key_drivers": [
                "Macro environment and RBI policy stance",
                "Government capital expenditure and sector-specific policy",
                "Institutional and retail investor demand dynamics",
            ],
            "key_risks": [
                "Global macro tightening pressure on emerging market valuations",
                "Regulatory or policy reversal affecting sector economics",
                "Execution delays or adverse sector-specific developments",
            ],
            "thesis_strength": 65,
            "time_horizon": "Medium-term (6–18 months)",
        }

    result["last_updated"] = datetime.now(timezone.utc).isoformat()
    await cache_set(cache_key, result, 3600)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Monitoring Checklist
# ─────────────────────────────────────────────────────────────────────────────

async def generate_monitoring_checklist(
    entity_type: str,
    entity_id: str,
    title: str = "",
    description: str = "",
    sector: str = "",
    *,
    priority: Priority,
) -> dict:
    """
    Generate a structured monitoring checklist for any entity.
    Cached 6 hours per entity.
    """
    import json, re
    from datetime import datetime, timezone

    cache_key = f"checklist:{entity_type}:{entity_id}"
    hit = await cache_get(cache_key)
    if hit and isinstance(hit, dict) and hit.get("items"):
        _AI_USAGE["cache_hits"] += 1
        return hit
    _AI_USAGE["cache_misses"] += 1

    system = (
        "You are a senior Indian equity market analyst. "
        "Generate a practical monitoring checklist JSON for investors. "
        "Return ONLY valid JSON — no markdown fences, no explanation."
    )

    entity_label = {
        "event": "market event", "company": "listed company",
        "story": "investment theme", "opportunity": "investment opportunity",
        "ripple": "ripple analysis", "search": "market intelligence query",
    }.get(entity_type, "market entity")

    prompt = (
        f"Generate a monitoring checklist for this {entity_label}.\n\n"
        f"Name: {title or entity_id}\n"
        f"Context: {description[:400] if description else 'No additional context.'}\n"
        f"Sector: {sector or 'Diversified'}\n\n"
        "Return ONLY this JSON with 8-12 checklist items:\n"
        "{\n"
        '  "items": [\n'
        "    {\n"
        '      "label": "Quarterly Results",\n'
        '      "status": "pending",\n'
        '      "importance": "critical",\n'
        '      "why_it_matters": "Revenue and earnings trajectory validation.",\n'
        '      "frequency": "Every 3 months"\n'
        "    }\n"
        "  ]\n"
        "}\n\n"
        "importance must be one of: critical | high | medium\n"
        "status must be one of: pending | watch | ok\n"
        "Include items relevant to: earnings, FII/DII activity, sector policy, "
        "commodity prices, interest rates, management guidance, promoter holding, "
        "debt levels, order book, capacity expansion, regulatory changes."
    )

    raw = await _call_with_fallback(prompt, system, max_tokens=600, priority=priority)

    result: dict = {}
    if raw:
        clean = raw.strip()
        if clean.startswith("```"):
            clean = re.sub(r"^```(?:json)?\s*", "", clean)
            clean = re.sub(r"\s*```$", "", clean).strip()
        try:
            result = json.loads(clean)
        except Exception:
            m = re.search(r"\{.*\}", clean, re.DOTALL)
            if m:
                try:
                    result = json.loads(m.group())
                except Exception:
                    pass

    ai_generated = bool(result and result.get("items"))
    if not ai_generated:
        result = {
            "degraded": True,  # generic template, not real analysis — caller must not present this as personalized
            "items": [
                {"label": "Quarterly Earnings vs Consensus", "status": "pending", "importance": "critical", "why_it_matters": "Validates revenue and earnings trajectory.", "frequency": "Every 3 months"},
                {"label": "Revenue Growth Trajectory", "status": "pending", "importance": "critical", "why_it_matters": "Confirms topline momentum and pricing power.", "frequency": "Quarterly"},
                {"label": "Margin Trend", "status": "pending", "importance": "high", "why_it_matters": "Profitability sustainability under cost pressures.", "frequency": "Quarterly"},
                {"label": "FII/DII Activity", "status": "pending", "importance": "high", "why_it_matters": "Institutional flows signal conviction and sector rotation.", "frequency": "Monthly"},
                {"label": "Interest Rate Outlook (RBI)", "status": "pending", "importance": "high", "why_it_matters": "Rate cycle affects valuations and borrowing costs.", "frequency": "Bi-monthly"},
                {"label": "Dollar Index (DXY)", "status": "pending", "importance": "medium", "why_it_matters": "INR strength impacts import costs and FII flows.", "frequency": "Weekly"},
                {"label": "Promoter Holding Changes", "status": "pending", "importance": "high", "why_it_matters": "Insider conviction in their own business.", "frequency": "Quarterly"},
                {"label": "Debt Reduction Progress", "status": "pending", "importance": "medium", "why_it_matters": "Balance sheet health affects credit rating and growth capacity.", "frequency": "Quarterly"},
                {"label": "Sector Rotation Signals", "status": "pending", "importance": "medium", "why_it_matters": "Money flow into/out of sector affects near-term performance.", "frequency": "Monthly"},
                {"label": "Government Policy & Capex", "status": "pending", "importance": "high", "why_it_matters": "Regulatory tailwinds or headwinds shape sector trajectory.", "frequency": "As announced"},
            ]
        }

    result["last_updated"] = datetime.now(timezone.utc).isoformat()
    if ai_generated:
        await cache_set(cache_key, result, 21600)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Scenario Analysis
# ─────────────────────────────────────────────────────────────────────────────

async def generate_scenario_analysis(
    entity_type: str,
    entity_id: str,
    title: str = "",
    description: str = "",
    sector: str = "",
    *,
    priority: Priority,
) -> dict:
    """
    Generate Bull / Base / Bear scenario analysis for any entity.
    Cached 2 hours per entity.
    """
    import json, re
    from datetime import datetime, timezone

    cache_key = f"scenario:{entity_type}:{entity_id}"
    hit = await cache_get(cache_key)
    if hit and isinstance(hit, dict) and hit.get("bull"):
        _AI_USAGE["cache_hits"] += 1
        return hit
    _AI_USAGE["cache_misses"] += 1

    system = (
        "You are a senior Indian equity market analyst. "
        "Generate balanced scenario analysis JSON with probabilities summing to 100. "
        "Return ONLY valid JSON — no markdown fences, no explanation."
    )

    entity_label = {
        "event": "market event", "company": "listed company",
        "story": "investment theme", "opportunity": "investment opportunity",
        "ripple": "ripple analysis", "search": "market intelligence query",
    }.get(entity_type, "market entity")

    prompt = (
        f"Generate a scenario analysis for this {entity_label}.\n\n"
        f"Name: {title or entity_id}\n"
        f"Context: {description[:400] if description else 'No additional context.'}\n"
        f"Sector: {sector or 'Diversified'}\n\n"
        "Return ONLY this JSON (probabilities must sum to 100):\n"
        "{\n"
        '  "bull": {\n'
        '    "probability": 30,\n'
        '    "outcome": "Strong outperformance driven by ...",\n'
        '    "key_drivers": ["Catalyst 1", "Catalyst 2"],\n'
        '    "supporting_evidence": "Specific data or historical precedent.",\n'
        '    "major_catalysts": ["Event that could trigger this"],\n'
        '    "expected_evolution": "How this scenario unfolds over time.",\n'
        '    "confidence": 65\n'
        "  },\n"
        '  "base": {\n'
        '    "probability": 50,\n'
        '    "outcome": "Meets consensus expectations with ...",\n'
        '    "key_drivers": ["Driver 1", "Driver 2"],\n'
        '    "supporting_evidence": "Current trend and analyst consensus.",\n'
        '    "major_catalysts": ["Event that sustains base case"],\n'
        '    "expected_evolution": "Gradual unfolding of the base scenario.",\n'
        '    "confidence": 70\n'
        "  },\n"
        '  "bear": {\n'
        '    "probability": 20,\n'
        '    "outcome": "Underperformance due to ...",\n'
        '    "key_drivers": ["Risk 1", "Risk 2"],\n'
        '    "supporting_evidence": "Historical precedent for downside.",\n'
        '    "major_catalysts": ["Trigger that could cause bear case"],\n'
        '    "expected_evolution": "How the bear scenario would unfold.",\n'
        '    "confidence": 60\n'
        "  }\n"
        "}"
    )

    raw = await _call_with_fallback(prompt, system, max_tokens=700, priority=priority)

    result: dict = {}
    if raw:
        clean = raw.strip()
        if clean.startswith("```"):
            clean = re.sub(r"^```(?:json)?\s*", "", clean)
            clean = re.sub(r"\s*```$", "", clean).strip()
        try:
            result = json.loads(clean)
        except Exception:
            m = re.search(r"\{.*\}", clean, re.DOTALL)
            if m:
                try:
                    result = json.loads(m.group())
                except Exception:
                    pass

    ai_generated = bool(result and result.get("bull"))
    if not ai_generated:
        result = {
            "degraded": True,  # generic template, not real analysis — caller must not present this as personalized
            "bull": {
                "probability": 30,
                "outcome": f"Strong performance for {title or entity_id} driven by favourable macro conditions, sector tailwinds, and above-consensus delivery.",
                "key_drivers": ["Policy tailwinds accelerate sector growth", "Earnings beat consensus by 15–20%"],
                "supporting_evidence": "Historical setups with similar macro alignment have produced 25–40% returns over 12 months.",
                "major_catalysts": ["Positive policy announcement", "Strong quarterly earnings"],
                "expected_evolution": "Bull case builds gradually over 2–3 quarters as earnings upgrades attract institutional interest.",
                "confidence": 60,
            },
            "base": {
                "probability": 50,
                "outcome": f"In-line performance for {title or entity_id}, meeting consensus estimates with stable sector dynamics.",
                "key_drivers": ["Steady macro environment supports baseline growth", "Management delivers on stated guidance"],
                "supporting_evidence": "Analyst consensus and current business momentum support base case delivery.",
                "major_catalysts": ["Stable RBI policy", "Consistent quarterly execution"],
                "expected_evolution": "Base case plays out steadily; investors price in forward earnings growth over 6–12 months.",
                "confidence": 70,
            },
            "bear": {
                "probability": 20,
                "outcome": f"Underperformance for {title or entity_id} due to macro headwinds, earnings miss, or adverse policy changes.",
                "key_drivers": ["Global risk-off sentiment pressures valuation multiples", "Earnings miss or guidance cut"],
                "supporting_evidence": "Similar macro deterioration historically caused 15–25% drawdowns in comparable setups.",
                "major_catalysts": ["Unexpected rate hike", "Earnings disappointment"],
                "expected_evolution": "Bear case materialises quickly if a catalyst triggers institutional selling; recovery takes 2–4 quarters.",
                "confidence": 55,
            },
        }

    result["last_updated"] = datetime.now(timezone.utc).isoformat()
    if ai_generated:
        # Don't cache the generic fallback template — a provider recovering a
        # minute later should regenerate real analysis, not serve the same
        # boilerplate "Strong performance for X..." text for 2 more hours.
        await cache_set(cache_key, result, 7200)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Pattern Intelligence
# ─────────────────────────────────────────────────────────────────────────────

async def generate_pattern_intelligence(
    entity_type: str,
    entity_id: str,
    title: str = "",
    description: str = "",
    sector: str = "",
    *,
    priority: Priority,
) -> dict:
    """
    AI-driven historical pattern matching for any entity.
    Cached 6 hours per entity.
    """
    import json, re
    from datetime import datetime, timezone

    cache_key = f"pattern:{entity_type}:{entity_id}"
    hit = await cache_get(cache_key)
    if hit and isinstance(hit, dict) and hit.get("patterns"):
        _AI_USAGE["cache_hits"] += 1
        return hit
    _AI_USAGE["cache_misses"] += 1

    system = (
        "You are a senior Indian equity market historian and analyst. "
        "Match this entity to historical market patterns and precedents. "
        "Return ONLY valid JSON — no markdown fences, no explanation."
    )

    entity_label = {
        "event": "market event", "company": "listed company",
        "story": "investment theme", "opportunity": "investment opportunity",
        "ripple": "ripple analysis", "search": "market intelligence query",
    }.get(entity_type, "market entity")

    prompt = (
        f"Identify historical market patterns similar to this {entity_label}.\n\n"
        f"Name: {title or entity_id}\n"
        f"Context: {description[:400] if description else 'No additional context.'}\n"
        f"Sector: {sector or 'Diversified'}\n\n"
        "Return ONLY this JSON with 2-4 historical patterns:\n"
        "{\n"
        '  "patterns": [\n'
        "    {\n"
        '      "historical_match": "Name of historical event/period/company",\n'
        '      "similarity_score": 78,\n'
        '      "historical_outcome": "What happened — specific return or outcome",\n'
        '      "average_duration": "6-12 months",\n'
        '      "success_rate": 72,\n'
        '      "key_differences": "What is different this time vs historical",\n'
        '      "lessons_learned": "Key takeaway from historical precedent",\n'
        '      "confidence": 70\n'
        "    }\n"
        "  ],\n"
        '  "typical_winners": ["Sector or company type that benefited"],\n'
        '  "typical_losers": ["Sector or company type that suffered"],\n'
        '  "average_timeline": "6-18 months for full pattern to play out",\n'
        '  "overall_confidence": 68\n'
        "}\n\n"
        "Focus on Indian market history (Nifty, BSE Sensex) where possible. "
        "Include global analogues only when highly relevant."
    )

    raw = await _call_with_fallback(prompt, system, max_tokens=800, priority=priority)

    result: dict = {}
    if raw:
        clean = raw.strip()
        if clean.startswith("```"):
            clean = re.sub(r"^```(?:json)?\s*", "", clean)
            clean = re.sub(r"\s*```$", "", clean).strip()
        try:
            result = json.loads(clean)
        except Exception:
            m = re.search(r"\{.*\}", clean, re.DOTALL)
            if m:
                try:
                    result = json.loads(m.group())
                except Exception:
                    pass

    ai_generated = bool(result and result.get("patterns"))
    if not ai_generated:
        result = {
            "degraded": True,  # generic template, not real analysis — caller must not present this as personalized
            "patterns": [
                {
                    "historical_match": "Indian Infrastructure Capex Cycle (2003–2008)",
                    "similarity_score": 68,
                    "historical_outcome": "Nifty delivered 500%+ returns; infrastructure stocks led with 800–1200% gains over 5 years.",
                    "average_duration": "3–5 years",
                    "success_rate": 75,
                    "key_differences": "Current cycle is more domestically driven with lower external debt dependency.",
                    "lessons_learned": "Early-cycle entry with quality management is critical; valuations expand significantly before plateau.",
                    "confidence": 65,
                },
                {
                    "historical_match": "Post-COVID Recovery Rally (2020–2021)",
                    "similarity_score": 55,
                    "historical_outcome": "Nifty doubled in 12 months; midcap index tripled. Sectors with digital tailwinds led.",
                    "average_duration": "12–18 months",
                    "success_rate": 70,
                    "key_differences": "Liquidity-driven rally differs from fundamentally driven cycles; sustainability depends on earnings catch-up.",
                    "lessons_learned": "Sentiment can drive markets well beyond fundamental fair value in recovery cycles.",
                    "confidence": 60,
                },
            ],
            "typical_winners": [
                "Capital goods and infrastructure companies",
                "Domestic consumption-oriented businesses",
                "Banks and NBFCs with strong retail franchises",
            ],
            "typical_losers": [
                "Import-dependent businesses with INR exposure",
                "Highly leveraged companies with variable-rate debt",
            ],
            "average_timeline": "12–24 months for the full pattern to play out",
            "overall_confidence": 62,
        }

    result["last_updated"] = datetime.now(timezone.utc).isoformat()
    if ai_generated:
        await cache_set(cache_key, result, 21600)
    return result
