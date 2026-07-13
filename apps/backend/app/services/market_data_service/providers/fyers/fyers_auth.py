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

    def auto_authenticate(self, login_id: str, pin: str, totp_key: str) -> Optional[str]:
        """
        Fully automated Fyers login using TOTP — no browser required.

        Uses Fyers' programmatic login API:
          1. send_login_otp   → get request_key
          2. verify_otp       → verify TOTP, get new request_key
          3. verify_pin       → verify PIN hash, get user session token
          4. /api/v3/token    → exchange for auth_code
          5. generate_token() → exchange auth_code for 24h access_token

        Returns the access_token string on success, None on any failure.
        """
        try:
            import hashlib, base64
            import requests as _req
            import pyotp
        except ImportError as e:
            log.error("fyers_auth.auto_login_missing_deps deps=%s", str(e))
            return None

        try:
            app_id = self._client_id.split("-")[0]
            s      = _req.Session()
            s.headers.update({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "en-US,en;q=0.9",
                "Content-Type": "application/json",
                "Origin": "https://app.fyers.in",
                "Referer": "https://app.fyers.in/",
            })

            # Step 1 — fy_id is plain string (not base64)
            r1 = s.post(
                "https://api-t2.fyers.in/vagator/v2/send_login_otp",
                json={"fy_id": login_id, "app_id": "2"},
                timeout=10,
            )
            d1 = r1.json()
            if d1.get("s") != "ok":
                log.error("fyers_auth.auto_step1_failed response=%s", d1)
                return None
            request_key = d1["request_key"]

            # Step 2 — Verify TOTP
            totp = pyotp.TOTP(totp_key).now()
            r2 = s.post(
                "https://api-t2.fyers.in/vagator/v2/verify_otp",
                json={"request_key": request_key, "otp": totp},
                timeout=10,
            )
            d2 = r2.json()
            if d2.get("s") != "ok":
                log.error("fyers_auth.auto_step2_failed response=%s", d2)
                return None
            request_key = d2["request_key"]

            # Step 3 — Verify PIN (plain text; Fyers changed API — no longer SHA256)
            # Response now returns access_token directly in data (not a session token for OAuth)
            r3 = s.post(
                "https://api-t2.fyers.in/vagator/v2/verify_pin",
                json={"request_key": request_key, "identity_type": "pin", "identifier": pin},
                timeout=10,
            )
            d3 = r3.json()
            if d3.get("s") != "ok":
                log.error("fyers_auth.auto_step3_failed response=%s", d3)
                return None

            # Fyers v3 vagator returns the full access_token directly from verify_pin
            raw_token = d3["data"].get("access_token") or d3["data"].get("token")
            if not raw_token:
                log.error("fyers_auth.auto_no_token_in_verify_pin data=%s", d3["data"])
                return None

            # FyersProvider expects token in "{client_id}:{jwt}" format
            token = f"{self._client_id}:{raw_token}"
            self._set_token(token)
            log.info("fyers_auth.auto_login_success token_prefix=%s", token[:12])
            return token

        except Exception as exc:
            log.error("fyers_auth.auto_login_error error=%s", str(exc))
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
