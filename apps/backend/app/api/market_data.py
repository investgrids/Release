"""
Market Data API — clean REST + WebSocket endpoints backed by MarketDataService.

All endpoints return normalized JSON (never raw provider data).
The frontend calls ONLY these endpoints — it never knows Fyers exists.

Prefix: /api/data
Routes:
  GET  /api/data/quote/{symbol}          — single live quote
  GET  /api/data/quotes?symbols=A,B,C    — batch quotes
  GET  /api/data/company/{symbol}        — company fundamentals
  GET  /api/data/history/{symbol}        — historical candles
  GET  /api/data/indices                 — all tracked indices
  GET  /api/data/movers                  — top gainers/losers/active
  GET  /api/data/sectors                 — sector performance
  GET  /api/data/status                  — market open/closed status
  GET  /api/data/provider               — which provider is active
  GET  /api/data/auth/fyers             — Fyers OAuth2 URL
  POST /api/data/auth/fyers/callback    — exchange auth_code for token
  WS   /api/data/ws/quotes              — live quote stream
"""
from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, Query, Request, WebSocket, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse

from app.services.market_data_service import (
    market_data_service,
    ws_hub,
    handle_quote_ws,
)

router = APIRouter()


# ── Health / provider info ────────────────────────────────────────────────────

@router.get("/provider")
async def get_provider_info():
    """Return which data provider is currently active."""
    return {
        "provider":           market_data_service.provider_name,
        "supports_websocket": market_data_service.supports_websocket,
        "ws_clients":         ws_hub.client_count(),
    }


# ── Market status ─────────────────────────────────────────────────────────────

@router.get("/status")
async def get_market_status():
    status = await market_data_service.get_market_status()
    return status.to_dict()


# ── Single quote ──────────────────────────────────────────────────────────────

@router.get("/quote/{symbol}")
async def get_quote(symbol: str):
    quote = await market_data_service.get_quote(symbol.upper())
    if not quote:
        raise HTTPException(status_code=404, detail=f"Quote unavailable for {symbol.upper()}")
    return quote.to_dict()


# ── Batch quotes ──────────────────────────────────────────────────────────────

@router.get("/quotes")
async def get_quotes(symbols: str = Query(..., description="Comma-separated NSE symbols")):
    syms = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    if not syms:
        raise HTTPException(status_code=400, detail="At least one symbol required")
    if len(syms) > 50:
        raise HTTPException(status_code=400, detail="Maximum 50 symbols per request")

    quotes = await market_data_service.get_quotes(syms)
    return {
        "count":  len(quotes),
        "quotes": [q.to_dict() for q in quotes],
    }


# ── Company fundamentals ──────────────────────────────────────────────────────

@router.get("/company/{symbol}")
async def get_company(symbol: str):
    company = await market_data_service.get_company(symbol.upper())
    if not company:
        raise HTTPException(status_code=404, detail=f"Company profile unavailable for {symbol.upper()}")
    return company.to_dict()


# ── Historical candles ────────────────────────────────────────────────────────

@router.get("/history/{symbol}")
async def get_history(
    symbol: str,
    period:   str = Query("6M", description="1D | 1W | 1M | 6M | 1Y | 3Y | 5Y"),
    interval: str = Query("1d", description="5m | 60m | 1d | 1wk | 1mo"),
):
    candles = await market_data_service.get_historical_candles(
        symbol.upper(), period=period, interval=interval
    )
    return {
        "symbol":  symbol.upper(),
        "period":  period,
        "count":   len(candles),
        "candles": [c.to_dict() for c in candles],
        # Convenience: chart-ready [{"label": ..., "value": close}]
        "chart": [
            {"label": c.timestamp[:10], "value": c.close}
            for c in candles
        ],
    }


# ── Market indices ────────────────────────────────────────────────────────────

@router.get("/indices")
async def get_indices():
    indices = await market_data_service.get_indices()
    return {
        "count":   len(indices),
        "indices": [i.to_dict() for i in indices],
    }


# ── Top movers ────────────────────────────────────────────────────────────────

@router.get("/movers")
async def get_movers():
    movers = await market_data_service.get_top_movers()
    return {
        "gainers": [m.to_dict() for m in movers.get("gainers", [])],
        "losers":  [m.to_dict() for m in movers.get("losers",  [])],
        "active":  [m.to_dict() for m in movers.get("active",  [])],
    }


# ── Sector performance ────────────────────────────────────────────────────────

@router.get("/sectors")
async def get_sectors():
    sectors = await market_data_service.get_sector_performance()
    return {
        "count":   len(sectors),
        "sectors": [s.to_dict() for s in sectors],
    }


# ── Fyers auth flow ───────────────────────────────────────────────────────────

@router.get("/auth/fyers/status")
async def fyers_auth_status():
    """Return current Fyers connection status and provider info."""
    from app.core.config import settings
    from app.services.market_data_service.providers.fyers.fyers_auth import FyersAuthManager

    client_id  = getattr(settings, "fyers_client_id",    "")
    secret_key = getattr(settings, "fyers_secret_key",   "")
    redirect_uri = getattr(settings, "fyers_redirect_uri", "")

    is_configured = bool(client_id)
    is_active     = market_data_service.provider_name == "Fyers"
    is_authed     = False

    if is_configured:
        try:
            auth = FyersAuthManager(
                client_id=client_id, secret_key=secret_key, redirect_uri=redirect_uri
            )
            is_authed = auth.is_authenticated()
        except Exception:
            pass

    return {
        "provider":       market_data_service.provider_name,
        "is_configured":  is_configured,
        "is_authenticated": is_authed,
        "is_active":      is_active,
        "supports_websocket": market_data_service.supports_websocket,
        "app_id":         client_id or None,
    }


@router.get("/auth/fyers/callback")
async def fyers_browser_callback(request: "Request"):
    """
    Browser GET redirect handler — Fyers sends the user here after login.
    Accepts any query parameters Fyers sends, extracts the auth code, exchanges it.
    """
    from fastapi.responses import HTMLResponse
    from app.core.config import settings
    from app.services.market_data_service.providers.fyers.fyers_auth import FyersAuthManager
    from app.services.market_data_service.providers.fyers import FyersProvider

    params = dict(request.query_params)
    client_id    = getattr(settings, "fyers_client_id",    "")
    secret_key   = getattr(settings, "fyers_secret_key",   "")
    redirect_uri = getattr(settings, "fyers_redirect_uri", "")

    def _html(ok: bool, message: str) -> HTMLResponse:
        color  = "#22c55e" if ok else "#ef4444"
        icon   = "✓" if ok else "✗"
        title  = "Fyers Connected" if ok else "Fyers Auth Failed"
        return HTMLResponse(f"""<!doctype html><html><head><title>{title}</title>
<style>body{{font-family:system-ui,sans-serif;display:flex;align-items:center;justify-content:center;
height:100vh;margin:0;background:#0f172a;color:#f8fafc}}
.card{{text-align:center;padding:48px;border-radius:16px;background:#1e293b;max-width:600px;width:90%}}
.icon{{font-size:64px;color:{color}}}h1{{margin:16px 0 8px;font-size:24px}}
p{{color:#94a3b8;margin:8px 0;word-break:break-all;font-size:13px}}</style></head>
<body><div class="card"><div class="icon">{icon}</div>
<h1>{title}</h1><p>{message}</p></div></body></html>""")

    # Fyers v3 sends auth_code; v2 sent code. Also grab s= status.
    actual_code = params.get("auth_code") or params.get("code")
    fyers_status = params.get("s", "")

    if not actual_code:
        # Show all params so we can diagnose exactly what Fyers sent
        params_display = " | ".join(f"{k}={v}" for k, v in params.items()) or "(none)"
        return _html(False, f"No auth code in callback. Fyers sent: {params_display}")

    if fyers_status and fyers_status != "ok":
        return _html(False, f"Fyers returned status={fyers_status}. Params: {params}")

    if not client_id:
        return _html(False, "FYERS_CLIENT_ID not configured on the server.")

    try:
        auth  = FyersAuthManager(client_id=client_id, secret_key=secret_key, redirect_uri=redirect_uri)
        token = auth.exchange_code(actual_code)

        new_provider = FyersProvider(
            client_id=client_id, access_token=token,
            secret_key=secret_key, redirect_uri=redirect_uri,
        )
        market_data_service.swap_provider(new_provider)
        return _html(True, "MarketRipple is now using live Fyers data. You can close this tab.")
    except Exception as exc:
        return _html(False, f"Error: {str(exc)[:200]}")


@router.get("/auth/fyers")
async def fyers_auth_url():
    """
    Returns the Fyers OAuth2 URL. Visit this in a browser to authorise.
    After login, Fyers redirects to redirect_uri with ?code=AUTH_CODE.
    Pass AUTH_CODE to POST /api/data/auth/fyers/callback.
    """
    try:
        from app.services.market_data_service.providers.fyers import FyersProvider
        from app.core.config import settings
        client_id  = getattr(settings, "fyers_client_id", "")
        secret_key = getattr(settings, "fyers_secret_key", "")
        if not client_id:
            return JSONResponse(
                status_code=503,
                content={"detail": "FYERS_CLIENT_ID not configured"}
            )
        from app.services.market_data_service.providers.fyers.fyers_auth import FyersAuthManager
        auth = FyersAuthManager(
            client_id    = client_id,
            secret_key   = secret_key,
            redirect_uri = getattr(settings, "fyers_redirect_uri", "https://127.0.0.1:8000/api/data/auth/callback"),
        )
        url = auth.get_auth_url()
        return {"auth_url": url, "instructions": "Visit auth_url in a browser to authorise Fyers."}
    except Exception as exc:
        return JSONResponse(status_code=500, content={"detail": str(exc)})


@router.post("/auth/fyers/callback")
async def fyers_auth_callback(auth_code: str = Query(...)):
    """
    Exchange the auth_code Fyers sent to your redirect_uri for an access_token.
    The token is stored in Redis and used by MarketDataService immediately.
    """
    try:
        from app.core.config import settings
        from app.services.market_data_service.providers.fyers.fyers_auth import FyersAuthManager
        from app.services.market_data_service.providers.fyers import FyersProvider

        client_id    = getattr(settings, "fyers_client_id",    "")
        secret_key   = getattr(settings, "fyers_secret_key",   "")
        redirect_uri = getattr(settings, "fyers_redirect_uri", "https://127.0.0.1:8000/api/data/auth/callback")

        if not client_id:
            raise HTTPException(status_code=503, detail="FYERS_CLIENT_ID not configured")

        auth  = FyersAuthManager(client_id=client_id, secret_key=secret_key, redirect_uri=redirect_uri)
        token = auth.exchange_code(auth_code)
        if not token:
            raise HTTPException(status_code=400, detail="Failed to exchange auth_code")

        # Hot-swap the market data service to use Fyers
        new_provider = FyersProvider(
            client_id    = client_id,
            access_token = token,
            secret_key   = secret_key,
            redirect_uri = redirect_uri,
        )
        market_data_service.swap_provider(new_provider)

        return {
            "status":   "authenticated",
            "provider": "Fyers",
            "message":  "Token stored. MarketDataService now using Fyers.",
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ── WebSocket live quotes ─────────────────────────────────────────────────────

@router.websocket("/ws/quotes")
async def quotes_websocket(
    ws:      WebSocket,
    symbols: str = Query("*", description="Comma-separated symbols or * for all"),
):
    """
    Browser WebSocket endpoint for live quote streaming.

    Connect: ws://localhost:8000/api/data/ws/quotes?symbols=RELIANCE,TCS
    Messages from server: {"type": "quote", "data": {...Quote...}}
    Messages from client: {"cmd": "subscribe", "symbols": ["HDFCBANK"]}
                          {"cmd": "unsubscribe", "symbols": ["TCS"]}

    If Fyers WebSocket is active, quotes arrive in near-real-time.
    Otherwise the endpoint accepts the connection but sends no quotes
    (the frontend should poll /api/data/quote/{symbol} instead).
    """
    sym_list = [s.strip().upper() for s in symbols.split(",") if s.strip()] or ["*"]

    # Start streaming from the service if WebSocket is supported
    if market_data_service.supports_websocket:
        await ws_hub.connect(ws, sym_list)
        stream = market_data_service.subscribe_quotes(sym_list)
        try:
            async for quote in stream:
                await ws_hub.broadcast_quote(quote)
        except Exception:
            pass
        finally:
            ws_hub.disconnect(ws)
    else:
        # Accept and hold open — browser can poll REST instead
        await handle_quote_ws(ws, ws_hub, sym_list)
