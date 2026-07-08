"""
Fyers authentication manager.

Handles:
  1. Generating the OAuth2 authorization URL (user visits once per day)
  2. Exchanging the auth_code for an access_token
  3. Storing/retrieving the token from Redis with a 23-hour TTL
  4. Providing is_authenticated() for other modules to check before calling the API

The access_token is also readable from the FYERS_ACCESS_TOKEN env var so
a pre-generated token can be injected without going through the web flow.
"""
from __future__ import annotations

import logging
import time
from typing import Optional

log = logging.getLogger(__name__)

_FYERS_TOKEN_REDIS_KEY = "fyers:access_token"
_TOKEN_TTL_SECONDS     = 23 * 3600  # 23 hours (Fyers token valid 24h)


class FyersAuthManager:
    """
    Central token authority for FyersProvider.
    All callers ask this object for the current access_token.
    """

    def __init__(self, client_id: str, secret_key: str, redirect_uri: str) -> None:
        self._client_id    = client_id
        self._secret_key   = secret_key
        self._redirect_uri = redirect_uri
        self._token_cache: Optional[str] = None
        self._token_ts:    float         = 0.0

    # ── Public interface ──────────────────────────────────────────────────────

    def get_auth_url(self) -> str:
        """Return the Fyers OAuth2 URL the user must visit to authorise the app."""
        try:
            from fyers_apiv3 import fyersModel
            session = fyersModel.SessionModel(
                client_id    = self._client_id,
                secret_key   = self._secret_key,
                redirect_uri = self._redirect_uri,
                response_type= "code",
                grant_type   = "authorization_code",
            )
            return session.generate_authcode()
        except ImportError:
            log.warning("fyers_auth.sdk_missing — install fyers-apiv3")
            return ""
        except Exception as exc:
            log.error("fyers_auth.url_error error=%s", str(exc))
            return ""

    def exchange_code(self, auth_code: str) -> str:
        """
        Exchange an auth_code for an access_token.
        Raises RuntimeError with Fyers error details on failure.
        Returns the access_token string on success.
        """
        try:
            from fyers_apiv3 import fyersModel
        except ImportError:
            raise RuntimeError("fyers-apiv3 package not installed on server")

        session = fyersModel.SessionModel(
            client_id    = self._client_id,
            secret_key   = self._secret_key,
            redirect_uri = self._redirect_uri,
            response_type= "code",
            grant_type   = "authorization_code",
        )
        session.set_token(auth_code)
        resp = session.generate_token()
        log.info("fyers_auth.exchange_response: %s", resp)

        if not isinstance(resp, dict):
            raise RuntimeError(f"Unexpected response type from Fyers: {resp!r}")

        token = resp.get("access_token")
        if not token:
            # Surface the actual Fyers error code + message
            code = resp.get("code", "?")
            msg  = resp.get("message") or resp.get("msg") or resp.get("error_message") or str(resp)
            raise RuntimeError(f"Fyers error {code}: {msg}")

        self._set_token(token)
        return token

    def set_token_direct(self, token: str) -> None:
        """Inject a pre-generated access token (e.g. from env var or cron)."""
        self._set_token(token)

    def get_token(self) -> Optional[str]:
        """Return the current access_token or None if not authenticated."""
        # Memory cache is still valid (within 23h since set)
        if self._token_cache and time.time() - self._token_ts < _TOKEN_TTL_SECONDS:
            return self._token_cache

        # Try Redis (async path: call get_token_async instead in async contexts)
        try:
            import redis as _redis
            from app.core.config import settings
            r = _redis.Redis.from_url(settings.redis_url, decode_responses=True)
            token = r.get(_FYERS_TOKEN_REDIS_KEY)
            if token:
                self._token_cache = token
                self._token_ts    = time.time()
                return token
        except Exception:
            pass

        return None

    async def get_token_async(self) -> Optional[str]:
        """Async version of get_token() — uses aioredis."""
        if self._token_cache and time.time() - self._token_ts < _TOKEN_TTL_SECONDS:
            return self._token_cache
        try:
            from app.core.redis import get_redis
            r = await get_redis()
            if r:
                token = await r.get(_FYERS_TOKEN_REDIS_KEY)
                if token:
                    self._token_cache = token
                    self._token_ts    = time.time()
                    return token
        except Exception:
            pass
        return None

    def is_authenticated(self) -> bool:
        return bool(self.get_token())

    # ── Private ───────────────────────────────────────────────────────────────

    def _set_token(self, token: str) -> None:
        self._token_cache = token
        self._token_ts    = time.time()
        # Best-effort write to Redis
        try:
            import redis as _redis
            from app.core.config import settings
            r = _redis.Redis.from_url(settings.redis_url, decode_responses=True)
            r.setex(_FYERS_TOKEN_REDIS_KEY, _TOKEN_TTL_SECONDS, token)
        except Exception:
            pass
