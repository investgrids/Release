"""
Server-side WebSocket subscription hub.

Manages the fan-out from ONE Fyers WebSocket connection to MANY
connected browser clients. Each browser opens a FastAPI WebSocket
at /ws/data/quotes — this hub routes incoming ticks to the right clients.

Architecture:
  Fyers WS ──▶ FyersWebSocketManager ──▶ FyersProvider._on_tick()
                                            │
                                     ServerWSHub._broadcast()
                                            │
                        ┌───────────────────┼────────────────────┐
                        ▼                   ▼                    ▼
                   browser client 1    browser client 2    browser client 3

No browser should create a direct connection to Fyers.
All consumers go through this hub via FastAPI WebSocket.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional

from fastapi import WebSocket, WebSocketDisconnect

log = logging.getLogger(__name__)


class ServerWSHub:
    """
    Tracks all connected browser WebSocket clients and routes incoming
    market ticks to the appropriate subscribers.
    """

    def __init__(self) -> None:
        # client_id → (WebSocket, set[symbols])
        self._clients: dict[int, tuple[WebSocket, set[str]]] = {}

    async def connect(self, ws: WebSocket, symbols: list[str]) -> None:
        """Accept the browser WebSocket and register symbol subscriptions."""
        await ws.accept()
        cid = id(ws)
        self._clients[cid] = (ws, set(s.upper() for s in symbols))
        log.info("ws_hub.client_connected", cid=cid, symbols=symbols)

    def disconnect(self, ws: WebSocket) -> None:
        cid = id(ws)
        self._clients.pop(cid, None)
        log.info("ws_hub.client_disconnected", cid=cid)

    async def broadcast_quote(self, quote) -> None:
        """Push a Quote to all clients that subscribed to its symbol."""
        if not self._clients:
            return

        payload = json.dumps({
            "type":   "quote",
            "data":   quote.to_dict(),
        })

        dead: list[int] = []
        for cid, (ws, symbols) in list(self._clients.items()):
            # Send to clients that want this symbol, or have subscribed to "*"
            if quote.symbol in symbols or "*" in symbols:
                try:
                    await ws.send_text(payload)
                except Exception:
                    dead.append(cid)

        for cid in dead:
            self._clients.pop(cid, None)

    async def broadcast_raw(self, payload: dict) -> None:
        """Push any dict payload to ALL connected clients (e.g. system messages)."""
        if not self._clients:
            return
        text = json.dumps(payload)
        dead: list[int] = []
        for cid, (ws, _) in list(self._clients.items()):
            try:
                await ws.send_text(text)
            except Exception:
                dead.append(cid)
        for cid in dead:
            self._clients.pop(cid, None)

    def client_count(self) -> int:
        return len(self._clients)

    def all_subscribed_symbols(self) -> set[str]:
        syms: set[str] = set()
        for _, (_, symbols) in self._clients.items():
            syms |= symbols
        return syms


# ── FastAPI WebSocket handler ─────────────────────────────────────────────────

async def handle_quote_ws(
    ws: WebSocket,
    hub: ServerWSHub,
    symbols: Optional[list[str]] = None,
) -> None:
    """
    Long-running handler for a single browser WebSocket connection.
    Attach to a FastAPI route via:

        @router.websocket("/ws/quotes")
        async def quotes_ws(ws: WebSocket):
            await handle_quote_ws(ws, ws_hub, symbols=["RELIANCE", "TCS"])
    """
    await hub.connect(ws, symbols or ["*"])
    try:
        while True:
            # Listen for client messages (subscribe / unsubscribe commands)
            try:
                data = await asyncio.wait_for(ws.receive_json(), timeout=30.0)
                if isinstance(data, dict):
                    cmd = data.get("cmd", "")
                    syms = [s.upper() for s in data.get("symbols", [])]
                    cid  = id(ws)
                    if cmd == "subscribe" and cid in hub._clients:
                        hub._clients[cid][1].update(syms)
                    elif cmd == "unsubscribe" and cid in hub._clients:
                        hub._clients[cid][1].difference_update(syms)
            except asyncio.TimeoutError:
                # Send heartbeat ping
                try:
                    await ws.send_json({"type": "ping"})
                except Exception:
                    break
            except WebSocketDisconnect:
                break
            except Exception:
                break
    finally:
        hub.disconnect(ws)


# ── Singleton ─────────────────────────────────────────────────────────────────
ws_hub = ServerWSHub()
