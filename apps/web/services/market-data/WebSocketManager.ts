/**
 * WebSocketManager — client-side live quote stream.
 *
 * Manages ONE persistent WebSocket connection to /api/data/ws/quotes.
 * Multiple components subscribe to symbols; the manager fans out ticks
 * to the right subscribers without opening duplicate connections.
 *
 * Usage:
 *   const ws = WebSocketManager.getInstance();
 *   const unsub = ws.subscribe(["RELIANCE", "TCS"], (quote) => {
 *     console.log(quote.price_str);
 *   });
 *   // Later:
 *   unsub();
 */

import type { Quote, WSMessage, WSSubscribeCmd } from "./types";

type QuoteHandler = (quote: Quote) => void;

const RECONNECT_BASE_MS = 2_000;
const RECONNECT_MAX_MS  = 30_000;
const HEARTBEAT_TIMEOUT = 45_000; // 45 s without any message → reconnect

class WebSocketManager {
  private static _instance: WebSocketManager | null = null;

  private ws: WebSocket | null = null;
  private subscriptions = new Map<string, Set<QuoteHandler>>();  // symbol → handlers
  private reconnectDelay = RECONNECT_BASE_MS;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private heartbeatTimer: ReturnType<typeof setTimeout> | null = null;
  private _connected = false;
  private _destroyed = false;

  private constructor(private readonly baseUrl: string) {}

  static getInstance(baseUrl?: string): WebSocketManager {
    const url = baseUrl ?? (
      typeof window !== "undefined"
        ? `${window.location.protocol === "https:" ? "wss" : "ws"}://${window.location.hostname}:8000`
        : "ws://localhost:8000"
    );
    if (!WebSocketManager._instance) {
      WebSocketManager._instance = new WebSocketManager(url);
    }
    return WebSocketManager._instance;
  }

  // ── Public API ──────────────────────────────────────────────────────────────

  subscribe(symbols: string[], handler: QuoteHandler): () => void {
    const upperSyms = symbols.map((s) => s.toUpperCase());

    for (const sym of upperSyms) {
      if (!this.subscriptions.has(sym)) {
        this.subscriptions.set(sym, new Set());
      }
      this.subscriptions.get(sym)!.add(handler);
    }

    this._ensureConnected();

    if (this._connected && this.ws?.readyState === WebSocket.OPEN) {
      this._sendCmd({ cmd: "subscribe", symbols: upperSyms });
    }

    return () => this.unsubscribe(upperSyms, handler);
  }

  unsubscribe(symbols: string[], handler: QuoteHandler): void {
    const toRemove: string[] = [];
    for (const sym of symbols) {
      const handlers = this.subscriptions.get(sym.toUpperCase());
      if (handlers) {
        handlers.delete(handler);
        if (handlers.size === 0) {
          this.subscriptions.delete(sym.toUpperCase());
          toRemove.push(sym.toUpperCase());
        }
      }
    }
    if (toRemove.length && this._connected) {
      this._sendCmd({ cmd: "unsubscribe", symbols: toRemove });
    }
    // Close connection when no more subscribers
    if (this.subscriptions.size === 0) {
      this._close();
    }
  }

  get connected(): boolean {
    return this._connected;
  }

  destroy(): void {
    this._destroyed = true;
    this._close();
    WebSocketManager._instance = null;
  }

  // ── Internal ────────────────────────────────────────────────────────────────

  private _ensureConnected(): void {
    if (this._destroyed) return;
    if (this.ws && this.ws.readyState === WebSocket.OPEN) return;
    if (this.ws && this.ws.readyState === WebSocket.CONNECTING) return;
    this._connect();
  }

  private _connect(): void {
    if (this._destroyed) return;
    const allSyms = Array.from(this.subscriptions.keys());
    const symParam = allSyms.length ? allSyms.join(",") : "*";
    const url = `${this.baseUrl}/api/data/ws/quotes?symbols=${encodeURIComponent(symParam)}`;

    try {
      this.ws = new WebSocket(url);
      this.ws.onopen    = this._onOpen.bind(this);
      this.ws.onclose   = this._onClose.bind(this);
      this.ws.onerror   = this._onError.bind(this);
      this.ws.onmessage = this._onMessage.bind(this);
    } catch {
      this._scheduleReconnect();
    }
  }

  private _onOpen(): void {
    this._connected      = true;
    this.reconnectDelay  = RECONNECT_BASE_MS;
    this._resetHeartbeat();

    // Re-subscribe all tracked symbols
    const allSyms = Array.from(this.subscriptions.keys());
    if (allSyms.length) {
      this._sendCmd({ cmd: "subscribe", symbols: allSyms });
    }
  }

  private _onClose(): void {
    this._connected = false;
    this._clearHeartbeat();
    this._scheduleReconnect();
  }

  private _onError(): void {
    this.ws?.close();
  }

  private _onMessage(event: MessageEvent): void {
    this._resetHeartbeat();
    try {
      const msg: WSMessage = JSON.parse(event.data as string);
      if (msg.type === "quote") {
        this._dispatch(msg.data);
      }
      // ping — no action needed, heartbeat already reset
    } catch {
      // ignore malformed messages
    }
  }

  private _dispatch(quote: Quote): void {
    const handlers = this.subscriptions.get(quote.symbol)
                  ?? this.subscriptions.get("*");
    if (!handlers) return;
    for (const h of handlers) {
      try { h(quote); } catch { /* swallow handler errors */ }
    }
  }

  private _sendCmd(cmd: WSSubscribeCmd): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(cmd));
    }
  }

  private _scheduleReconnect(): void {
    if (this._destroyed || this.reconnectTimer) return;
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this._connect();
    }, this.reconnectDelay);
    this.reconnectDelay = Math.min(this.reconnectDelay * 2, RECONNECT_MAX_MS);
  }

  private _resetHeartbeat(): void {
    this._clearHeartbeat();
    this.heartbeatTimer = setTimeout(() => {
      // No message for 45 s → reconnect
      this._close();
      this._scheduleReconnect();
    }, HEARTBEAT_TIMEOUT);
  }

  private _clearHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearTimeout(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  private _close(): void {
    this._clearHeartbeat();
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this._connected = false;
    this.ws?.close();
    this.ws = null;
  }
}

export default WebSocketManager;
