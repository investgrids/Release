"""
Fyers WebSocket manager for live quote streaming.

Responsibilities:
  - Maintains ONE persistent connection to Fyers Data WebSocket
  - Tracks active symbol subscriptions
  - Reconnects automatically on disconnect (exponential back-off)
  - Broadcasts incoming ticks to all registered callbacks
  - Heartbeat monitoring to detect stale connections

No page or router should create WebSocket connections directly.
All consumers subscribe via FyersProvider.subscribe_quotes().
"""
from __future__ import annotations

import asyncio
import logging
import threading
import time
from typing import Callable, Optional

log = logging.getLogger(__name__)

_RECONNECT_BASE_DELAY = 2.0    # seconds
_RECONNECT_MAX_DELAY  = 60.0
_HEARTBEAT_INTERVAL   = 30.0   # seconds
_DATA_TYPE_QUOTE      = "SymbolUpdate"


class FyersWebSocketManager:
    """
    Singleton WebSocket connection to Fyers live data feed.
    Thread-safe subscription management with asyncio callback dispatch.
    """

    def __init__(self, client_id: str, access_token: str) -> None:
        self._client_id    = client_id
        self._access_token = access_token
        self._socket       = None
        self._connected    = False
        self._subscriptions: set[str]              = set()
        self._callbacks:     list[Callable]        = []
        self._lock         = threading.RLock()
        self._reconnect_delay = _RECONNECT_BASE_DELAY
        self._last_tick       = 0.0
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._ws_thread: Optional[threading.Thread]     = None

    # ── Public API ────────────────────────────────────────────────────────────

    def add_callback(self, cb: Callable) -> None:
        """Register a callback that receives each raw tick dict."""
        with self._lock:
            if cb not in self._callbacks:
                self._callbacks.append(cb)

    def remove_callback(self, cb: Callable) -> None:
        with self._lock:
            self._callbacks = [c for c in self._callbacks if c is not cb]

    def subscribe(self, symbols: list[str]) -> None:
        """Add symbols to the live feed. Connects if not already connected."""
        fyers_syms = [self._to_fyers_sym(s) for s in symbols]
        with self._lock:
            new_syms = [s for s in fyers_syms if s not in self._subscriptions]
            if not new_syms:
                return
            self._subscriptions.update(new_syms)

        if not self._connected:
            self._connect()
        elif self._socket and new_syms:
            try:
                self._socket.subscribe(symbols=new_syms, data_type=_DATA_TYPE_QUOTE)
            except Exception as exc:
                log.warning("fyers_ws.subscribe_error error=%s", str(exc))

    def unsubscribe(self, symbols: list[str]) -> None:
        fyers_syms = [self._to_fyers_sym(s) for s in symbols]
        with self._lock:
            self._subscriptions -= set(fyers_syms)
        if self._socket and fyers_syms:
            try:
                self._socket.unsubscribe(symbols=fyers_syms)
            except Exception:
                pass

    def disconnect(self) -> None:
        """Cleanly close the WebSocket connection."""
        self._connected = False
        if self._socket:
            try:
                self._socket.close_connection()
            except Exception:
                pass
            self._socket = None
        log.info("fyers_ws.disconnected")

    def is_connected(self) -> bool:
        return self._connected and time.time() - self._last_tick < 120  # stale after 2 min

    # ── Internal ──────────────────────────────────────────────────────────────

    def _to_fyers_sym(self, symbol: str) -> str:
        s = symbol.upper()
        if ":" in s:
            return s
        return f"NSE:{s}-EQ"

    def _connect(self) -> None:
        """Start the WebSocket in a daemon thread."""
        if self._ws_thread and self._ws_thread.is_alive():
            return
        self._ws_thread = threading.Thread(
            target=self._run_socket, daemon=True, name="fyers-ws"
        )
        self._ws_thread.start()

    def _run_socket(self) -> None:
        """Blocking WebSocket loop — runs in a daemon thread."""
        while True:
            try:
                self._start_socket()
            except Exception as exc:
                log.error("fyers_ws.run_error error=%s", str(exc))
            if not self._connected:
                break  # disconnect() was called
            log.info("fyers_ws.reconnecting delay=%s", self._reconnect_delay)
            time.sleep(self._reconnect_delay)
            self._reconnect_delay = min(self._reconnect_delay * 2, _RECONNECT_MAX_DELAY)

    def _start_socket(self) -> None:
        try:
            from fyers_apiv3.DataWebSocket import FyersDataSocket

            fs = FyersDataSocket(
                access_token      = f"{self._client_id}:{self._access_token}",
                log_path          = "",
                litemode          = False,
                write_to_file     = False,
                reconnect         = False,   # we handle reconnect manually
                on_connect        = self._on_connect,
                on_close          = self._on_close,
                on_error          = self._on_error,
                on_message        = self._on_message,
            )
            self._socket = fs
            with self._lock:
                syms = list(self._subscriptions)
            if syms:
                fs.subscribe(symbols=syms, data_type=_DATA_TYPE_QUOTE)
            fs.connect()  # blocks until closed
        except ImportError:
            log.warning("fyers_ws.sdk_missing — install fyers-apiv3")
            self._connected = False
        except Exception as exc:
            log.error("fyers_ws.start_error error=%s", str(exc))
            self._connected = False

    def _on_connect(self) -> None:
        self._connected      = True
        self._reconnect_delay = _RECONNECT_BASE_DELAY
        self._last_tick       = time.time()
        log.info("fyers_ws.connected")

    def _on_close(self) -> None:
        self._connected = False
        log.info("fyers_ws.closed")

    def _on_error(self, message: str) -> None:
        log.error("fyers_ws.error message=%s", message)

    def _on_message(self, message: dict) -> None:
        self._last_tick = time.time()
        with self._lock:
            callbacks = list(self._callbacks)
        for cb in callbacks:
            try:
                cb(message)
            except Exception as exc:
                log.warning("fyers_ws.callback_error error=%s", str(exc))
