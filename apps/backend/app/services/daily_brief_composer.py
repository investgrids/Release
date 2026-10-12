"""Deterministic, session-aware composition for the Daily Brief. Pure functions: no network, no DB, no LLM.

Everything here is derived from numbers the page already has (index quotes, breadth, sectors, movers, facts, events). Wording
is chosen from the canonical session state (market_session_state), so a completed session is reported as what happened and a
forecast is only ever shown, labelled as such, before the open.
"""
from __future__ import annotations

import re
from datetime import date

from app.services.market_session_state import AFTER_CLOSE, HOLIDAY, OPEN, PRE_OPEN, WEEKEND, MarketSession

FLAT_PCT = 0.25          # |Nifty move| below this is described as flat/little changed
NEAR_FLAT_PCT = 0.1      # facts moving less than this are neither catalyst nor risk
BREADTH_SKEW = 1.5       # decliners (or advancers) at least this many times the other side = broad move

_NUM = re.compile(r"[-+]?\d+(?:\.\d+)?")


def parse_pct(text) -> float | None:
    """'-0.70%', '+1.2%', '▼ 0.7%' (sign from the arrow) or a number -> float percent; None if there is no figure."""
    if text is None:
        return None
    if isinstance(text, (int, float)):
        return float(text)
    s = str(text).replace("−", "-").replace(",", "")
    m = _NUM.search(s)
    if not m:
        return None
    val = float(m.group(0))
    if "▼" in s and val > 0:
        val = -val
    return val


def clean_quote(q: dict | None) -> dict | None:
    """An index quote usable for narrative, or None when the provider returned the '—' placeholder."""
    if not q or q.get("value") in (None, "", "—"):
        return None
    pct = q.get("pct")
    pct = float(pct) if isinstance(pct, (int, float)) else parse_pct(q.get("change"))
    if pct is None:
        return None
    return {"name": q.get("name"), "value": q.get("value"), "pct": pct, "change": q.get("change")}


def _fmt_date(d: date) -> str:
    return f"{d.strftime('%a')} {d.day} {d.strftime('%b %Y')}"


def _move(pct: float) -> str:
    if abs(pct) < NEAR_FLAT_PCT:
        return "little changed"
    return f"{abs(pct):.2f}% {'higher' if pct > 0 else 'lower'}"


def _verb(session: MarketSession) -> str:
    return "is trading" if session.state == OPEN else "closed"


def session_block(session: MarketSession) -> dict:
    ref = _fmt_date(session.reference_session_date)
    labels = {
        PRE_OPEN: ("Pre-Market Outlook", f"Opening outlook for {_fmt_date(session.forecast_target_date)}"),
        OPEN: ("Live Session", f"Live session, {ref}"),
        AFTER_CLOSE: ("Market Wrap", f"Market wrap, {ref}"),
        WEEKEND: ("Weekend Review", f"Markets are closed for the weekend. Last session: {ref}"),
        HOLIDAY: ("Market Holiday", f"Markets are closed for an exchange holiday. Last session: {ref}"),
    }
    label, subtitle = labels[session.state]
    return {**session.as_dict(), "label": label, "subtitle": subtitle, "reference_label": ref}


def breadth_counts(breadth: dict | None) -> tuple[int, int, int] | None:
    if not breadth:
        return None
    adv, dec, unch = breadth.get("advances"), breadth.get("declines"), breadth.get("unchanged") or 0
    if not isinstance(adv, int) or not isinstance(dec, int) or adv + dec <= 0:
        return None
    return adv, dec, int(unch)


def breadth_tone(breadth: dict | None) -> str | None:
    """'broad_decline' | 'broad_advance' | 'mixed' | None (no usable breadth)."""
    c = breadth_counts(breadth)
    if not c:
        return None
    adv, dec, _ = c
    if dec >= BREADTH_SKEW * max(adv, 1):
        return "broad_decline"
    if adv >= BREADTH_SKEW * max(dec, 1):
        return "broad_advance"
    return "mixed"


def _sector_moves(sectors: list[dict] | None) -> list[tuple[str, float]]:
    out = []
    for s in sectors or []:
        pct = parse_pct(s.get("value"))
        if s.get("name") and pct is not None:
            out.append((s["name"], pct))
    return out


def realized_verdict(session: MarketSession, snapshot: dict, generated_at: str | None) -> dict:
    """What the market did in the reference session, from index quotes + breadth. Never a forecast, never AI."""
    nifty, sensex = clean_quote(snapshot.get("nifty")), clean_quote(snapshot.get("sensex"))
    base = {
        "kind": "realized", "confidence": None, "primary_drivers": [], "risks": [],
        "expected_range": {"low": None, "high": None}, "ai_generated": False, "generated_at": generated_at,
        "session_state": session.state, "session_date": session.reference_session_date.isoformat(),
        "target_date": None, "forecast": None, "direction_check": None,
    }
    if not nifty:
        return {**base, "kind": "unavailable", "direction": None, "headline": "Index data unavailable", "unavailable": True,
                "reasoning": "Index levels are unavailable right now, so this page does not describe the session until they return."}

    pct = nifty["pct"]
    direction = "Positive" if pct >= FLAT_PCT else "Negative" if pct <= -FLAT_PCT else "Neutral"
    verb = _verb(session)
    where = f" in the {_fmt_date(session.reference_session_date)} session" if session.state in (WEEKEND, HOLIDAY) else ""
    headline = {
        "Positive": "Higher close" if verb == "closed" else "Trading higher",
        "Negative": "Lower close" if verb == "closed" else "Trading lower",
        "Neutral": "Flat close" if verb == "closed" else "Trading flat",
    }[direction]

    sentences = [f"Nifty 50 {verb} {_move(pct)} at {nifty['value']}{where}"]
    if sensex:
        sentences[0] += f", and the Sensex {_move(sensex['pct'])} at {sensex['value']}"
        if (nifty["pct"] >= FLAT_PCT and sensex["pct"] <= -FLAT_PCT) or (nifty["pct"] <= -FLAT_PCT and sensex["pct"] >= FLAT_PCT):
            sentences[0] += ", so the two benchmarks moved in opposite directions"
    sentences[0] += "."

    counts = breadth_counts(snapshot.get("breadth"))
    if counts:
        adv, dec, unch = counts
        sentences.append(f"Among the {adv + dec + unch} large-cap stocks MarketRipple tracks, {dec} declined and {adv} advanced.")
        tone = breadth_tone(snapshot.get("breadth"))
        if pct >= FLAT_PCT and tone == "broad_decline":
            sentences.append("The index gain was narrow: most tracked stocks fell.")
        elif pct <= -FLAT_PCT and tone == "broad_advance":
            sentences.append("The index fell on a narrow set of heavyweights: most tracked stocks rose.")

    return {**base, "direction": direction, "headline": headline, "reasoning": " ".join(sentences)}
