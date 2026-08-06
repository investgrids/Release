"""
Live-price enrichment, valuation/VIX/chart fetches, and deterministic
sector/ripple-position classification — shared by both AI Search pipelines
(V2: ai_search_service.py, V3: this package) — extracted verbatim from
ai_search_service.py during P5 Stage 1 (2026-08-06), zero behavior change.
"""
from __future__ import annotations

import re

from app.services.ai_search.regexes import _COMMODITY_NAMES, _COMMODITY_TICKERS


def _enrich_sync(companies: list[dict]) -> list[dict]:
    """Add live prices synchronously (runs in executor)."""
    from app.services.market_data import _fetch_quote, _fmt_price, _fetch_history
    enriched = []
    for c in companies:
        sym = c.get("symbol", "")
        # Strip exchange suffix if AI already included it (e.g. HDFCBANK.NS → HDFCBANK)
        sym_base = re.sub(r'\.(NS|BO|BSE|NSE)$', '', sym.strip().upper())
        try:
            q = _fetch_quote(f"{sym_base}.NS")
            if q:
                c["price"]    = _fmt_price(q["price"])
                c["change"]   = f"{'+' if q['positive'] else ''}{q['pct']:.2f}%"
                c["positive"] = q["positive"]
                # Tiny sparkline (5d daily)
                hist = _fetch_history(f"{sym_base}.NS", "5d", "1d")
                c["chart"] = [h["value"] for h in (hist or [])][-5:]
            else:
                c["price"] = "—"; c["change"] = "—"; c["positive"] = True; c["chart"] = []
        except Exception:
            c["price"] = "—"; c["change"] = "—"; c["positive"] = True; c["chart"] = []
        enriched.append(c)
    return enriched


# ── Valuation data fetch ──────────────────────────────────────────────────────
def _fetch_valuation_sync(symbols: list[str]) -> dict:
    """Fetch P/E, P/B, 52W range from yfinance for valuation-sensitive queries."""
    import yfinance as yf
    result: dict = {}
    for sym in symbols[:3]:
        try:
            info = yf.Ticker(f"{sym}.NS").info or {}
            pe  = info.get("trailingPE") or info.get("forwardPE")
            pb  = info.get("priceToBook")
            hi  = info.get("fiftyTwoWeekHigh")
            lo  = info.get("fiftyTwoWeekLow")
            result[sym] = {
                k: v for k, v in {
                    "pe": round(float(pe), 1) if pe else None,
                    "pb": round(float(pb), 2) if pb else None,
                    "52w_high": round(float(hi), 1) if hi else None,
                    "52w_low":  round(float(lo), 1) if lo else None,
                }.items() if v is not None
            }
        except Exception:
            pass
    return result


def _fetch_vix_sync() -> float | None:
    """Fetch current India VIX level."""
    import yfinance as yf
    try:
        hist = yf.download("^INDIAVIX", period="1d", interval="1d", progress=False, auto_adjust=True, timeout=10)
        if not hist.empty:
            close = hist["Close"].iloc[-1]
            v = float(close.iloc[0] if hasattr(close, "iloc") else close)
            return round(v, 2)
    except Exception:
        pass
    return None


# ── Market chart ──────────────────────────────────────────────────────────────
def _fetch_chart_sync(tickers: list) -> dict:
    """Fetch 1D intraday chart. Uses company tickers when provided, else indices."""
    import yfinance as yf
    import math

    def _series(ticker: str):
        try:
            hist = yf.download(ticker, period="1d", interval="60m",
                               progress=False, auto_adjust=True, timeout=10)
            if hist.empty:
                return [], []
            labels, vals = [], []
            for idx, row in hist.iterrows():
                try:
                    close = row["Close"]
                    v = float(close.iloc[0] if hasattr(close, "iloc") else close)
                    if math.isnan(v) or math.isinf(v):
                        continue
                    labels.append(idx.strftime("%H:%M"))
                    vals.append(v)
                except Exception:
                    continue
            return labels, vals
        except Exception:
            return [], []

    def _norm(vals: list) -> list:
        if not vals:
            return []
        base = vals[0] or 1
        return [round((v / base - 1) * 100, 3) for v in vals]

    # Company-specific chart when companies were identified in the query
    if tickers:
        series, labels = [], []
        for name, ticker, color in tickers[:4]:
            lbls, vals = _series(ticker)
            if vals:
                if len(lbls) > len(labels):
                    labels = lbls
                series.append({"name": name, "data": _norm(vals), "color": color})
        if series:
            return {"labels": labels, "series": series}

    # Fallback: generic market indices
    n_l, n_v = _series("^NSEI")
    _, b_v   = _series("^NSEBANK")
    _, it_v  = _series("^CNXIT")
    return {
        "labels": n_l,
        "series": [
            {"name": "Nifty 50",   "data": _norm(n_v),  "color": "#818cf8"},
            {"name": "Bank Nifty", "data": _norm(b_v),  "color": "#34d399"},
            {"name": "Nifty IT",   "data": _norm(it_v), "color": "#fb923c"},
        ],
    }


def _sector_status(positive: bool, score: float) -> str:
    s = score or 0
    if positive:
        if s >= 85:
            return "Structural Tailwind"
        if s >= 65:
            return "Beneficiary"
        return "Indirect Benefit"
    if s <= 35:
        return "Structural Headwind"
    return "Headwind"


def _sector_time_horizon(status: str) -> str:
    return {
        "Structural Tailwind": "3-5 Years", "Structural Headwind": "3-5 Years",
        "Beneficiary": "2-3 Years", "Headwind": "2-3 Years",
        "Indirect Benefit": "1-2 Years",
    }.get(status, "1-2 Years")


def _classify_ripple_position(companies: list[dict]) -> None:
    """
    Mutates `companies` in place, adding `ripple_position`. Deterministic,
    based on sort rank within each impact_type group — not left entirely to
    the AI, so labeling is consistent regardless of prompt compliance.
    """
    beneficiaries = [c for c in companies if (c.get("impact_type") or "").lower() == "beneficiary"]
    at_risk       = [c for c in companies if (c.get("impact_type") or "").lower() == "at_risk"]
    for i, c in enumerate(beneficiaries):
        c["ripple_position"] = "Primary Beneficiary" if i < 2 else "Secondary Beneficiary"
    for i, c in enumerate(at_risk):
        c["ripple_position"] = "Primary Pressure" if i < 2 else "Secondary Pressure"
    for c in companies:
        c.setdefault("ripple_position", "Indirect Exposure")


def _commodity_safety_note(query: str) -> str:
    """
    The symbol-safety guidance that stops the model from inventing a fake
    equity ticker for a commodity/currency/index used to only exist inside
    the two-entity decision prompt (_build_decision_prompt's symbol_hint()).
    A bare single-entity query like "Should I invest in gold?" got no such
    guidance and went through the general schema, which expects a real NSE
    equity symbol for every companies[] entry. This extends the same real
    ETF-proxy mapping (_COMMODITY_TICKERS) to the general prompt whenever a
    commodity/currency/index name is detected in the query text.
    """
    q = query.lower()
    hit = next((name for name in _COMMODITY_NAMES if name in q), None)
    if not hit:
        return ""
    ticker = _COMMODITY_TICKERS.get(hit)
    ticker_note = f' A real ETF proxy exists for "{hit}": {ticker}.' if ticker else ""
    return (
        f'\n- The query mentions "{hit}", which is a commodity/currency/index/asset class, not a single '
        f"listed equity. Do NOT invent a fake equity ticker for it in \"companies\". Either omit it from "
        f'"companies" entirely, or if a real ETF/index-fund proxy exists, use that proxy\'s real NSE symbol '
        f"instead.{ticker_note}"
    )


def _intent_overlay(intent_data: dict | None, extra_context: str = "") -> str:
    """Return an intent-specific instruction block appended to the main prompt."""
    if not intent_data:
        return f"\n\nADDITIONAL CONTEXT:\n{extra_context}" if extra_context else ""

    intent     = intent_data.get("intent", "general")
    budget     = intent_data.get("budget") or ""
    pick_count = intent_data.get("pick_count") or 3
    portfolio  = intent_data.get("portfolio") or []
    horizon    = intent_data.get("horizon") or "medium-term"
    budget_note = f"\n- User has {budget} to invest — calibrate sizing accordingly." if budget else ""
    portfolio_note = f"\n- Portfolio holdings: {', '.join(portfolio)}" if portfolio else ""

    overlays: dict[str, str] = {
        "list_picks": f"""

INTENT: LIST PICKS — User wants a ranked stock list, not an essay.
- Return exactly {pick_count} companies in "companies" array, ranked by conviction (highest first).
- "investment_verdict.rating" must be "Top {pick_count} Picks Identified".
- "investment_verdict.top_picks" must contain the top 3 NSE symbols.
- Each company "reason" must be a specific 1-sentence thesis (not generic).
- "follow_up_questions" must address: position sizing, entry triggers, stop-loss, time horizon.{budget_note}""",

        "news_reaction": f"""

INTENT: NEWS REACTION — A recent event just happened; user wants immediate guidance.
- "summary" must be exactly what this news means for investors RIGHT NOW (2 sentences).
- "immediate_impact" must name specific sectors/stocks and expected directional move.
- "medium_term" must describe the thesis window (days/weeks, not months).
- "follow_up_questions" must include: price level where thesis breaks, add/reduce decision, key upcoming catalyst.
- Prioritize recency — today's news beats older context.{budget_note}""",

        "earnings_preview": f"""

INTENT: EARNINGS PREVIEW — User is positioning ahead of results.
- "summary" must cover: consensus expectations, key metrics to watch, beat vs miss thresholds.
- "risks" must list miss scenarios with expected stock reactions (e.g. "-5% if revenue misses by 2%").
- "opportunities" must list beat scenarios with upside estimates.
- "key_drivers" should reference the company's recent earnings reaction pattern where relevant.
- "follow_up_questions" must address: historical move range, key metric focus, risk/reward ratio.
- "timeline" must show: results date, pre-result window, post-result action.{budget_note}""",

        "entry_timing": f"""

INTENT: ENTRY TIMING — User wants to know if now is a good entry point.
- "summary" must assess: current price vs historical range, risk/reward at today's level.
- "immediate_impact" must state the current technical setup (near 52W high/low, recent trend).
- "opportunities" must list: entry triggers and what confirms the setup.
- "risks" must list: why this level could be a trap (overhead resistance, near-term catalysts).
- "follow_up_questions" must include: stop-loss level, scale-in strategy, what invalidates the thesis.
- HORIZON: {horizon}.{budget_note}""",

        "portfolio_review": f"""

INTENT: PORTFOLIO REVIEW — User wants portfolio-level analysis.
- "summary" must cover: sector concentration, single-factor exposure, missing diversifiers.
- "sectors" must list all sectors covered AND key missing ones (label missing ones "Underweight").
- "risks" must include portfolio-level risks: concentration, correlation, liquidity.
- "opportunities" must include: diversification adds, rebalancing actions.
- "follow_up_questions" must address: rebalancing triggers, missing asset classes, hedging options, tax implications.{portfolio_note}{budget_note}""",

        "sell": f"""

INTENT: SELL / EXIT ANALYSIS — User is evaluating whether to exit a position.
- "summary" must weigh: exit thesis strength vs opportunity cost of remaining.
- "investment_verdict.direction" should be "bearish" if exit is recommended, "neutral" otherwise.
- "risks" must include: what happens if the bearish thesis is wrong (false exit risk).
- "opportunities" must include: where to redeploy capital after exiting.
- "follow_up_questions" must include: tax implications, redeployment options, what would reverse the sell thesis.{budget_note}""",
    }

    overlay = overlays.get(intent, "")
    ctx_block = f"\n\nADDITIONAL CONTEXT:\n{extra_context}" if extra_context else ""
    return overlay + ctx_block
