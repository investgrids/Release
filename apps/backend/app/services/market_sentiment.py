"""Market sentiment scores computed from the data they claim to describe. Pure functions.

Replaces two formulas that carried no information: /api/market/overview counted India VIX and unchanged indices as 'positive'
(a falling market with a rising VIX still scored well), and /api/market/insights derived everything from len(gainers), a list
sliced to a constant four, so it always returned Bullish / 87 / 90.
"""
from __future__ import annotations

_SCORE_MIN, _SCORE_MAX = 20, 90


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _pct(q: dict) -> float | None:
    if q.get("value") in (None, "", "—"):
        return None
    p = q.get("pct")
    return float(p) if isinstance(p, (int, float)) else None


def index_sentiment_score(indices: list[dict]) -> int | None:
    """0-100 style score from the average move of the equity indices, nudged by India VIX (inverse: rising VIX lowers it).
    Flat indices contribute zero. None when no index has a usable quote."""
    moves, vix_move = [], None
    for q in indices or []:
        p = _pct(q)
        if p is None:
            continue
        if "VIX" in (q.get("name") or "").upper():
            vix_move = p
        else:
            moves.append(p)
    if not moves:
        return None
    mean = sum(moves) / len(moves)
    score = 50 + _clamp(mean / 1.5, -1, 1) * 35
    if vix_move is not None:
        score -= _clamp(vix_move / 10, -1, 1) * 5
    return int(round(_clamp(score, _SCORE_MIN, _SCORE_MAX)))


def breadth_sentiment(advancing: int | None, declining: int | None) -> dict | None:
    """Sentiment from the advancing/declining split of the tracked stocks. confidence is the strength of the split
    (50 = evenly split, 95 = nearly one-sided), not a probability. None when there is no sample."""
    if not isinstance(advancing, int) or not isinstance(declining, int) or advancing + declining <= 0:
        return None
    r = advancing / (advancing + declining)
    return {
        "sentiment": "Bullish" if r >= 0.6 else "Bearish" if r <= 0.4 else "Neutral",
        "fear_greed": int(round(_clamp(20 + r * 70, _SCORE_MIN, _SCORE_MAX))),
        "confidence": int(round(min(95, 50 + abs(r - 0.5) * 2 * 45))),
        "advancing": advancing, "declining": declining,
    }
