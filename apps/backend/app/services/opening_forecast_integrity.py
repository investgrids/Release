"""Integrity checks for the opening forecast. Pure functions: no network, no DB, no LLM.

The forecast's AI direction used to be taken at face value, even when the deterministic signals (GIFT Nifty, FII flow, US futures,
global breadth) pointed the other way. This module compares them. When they genuinely conflict the direction is WITHHELD (None):
nothing is substituted, no confidence or range is invented, and the disagreement is stated instead.
"""
from __future__ import annotations

import re

VALID_DIRECTIONS = ("Positive", "Negative", "Neutral")
_OPPOSITE = {"Positive": "Negative", "Negative": "Positive"}

_BULL_WORDS = ("gap-up", "gap up", "upside", "bullish", "positive open", "premium", "buying", "supportive", "higher open")
_BEAR_WORDS = ("gap-down", "gap down", "downside", "bearish", "pressure", "discount", "selling", "cautious open", "lower open")


def signal_counts(rows: list[dict]) -> tuple[int, int]:
    """(positive, negative) over the directional rows of the signal breakdown. 'contextual' (VIX) and 'neutral' rows are not
    directional and are ignored."""
    pos = sum(1 for r in rows if r.get("direction") == "positive")
    neg = sum(1 for r in rows if r.get("direction") == "negative")
    return pos, neg


def _hits(text: str, words: tuple[str, ...]) -> int:
    t = (text or "").lower()
    return sum(len(re.findall(re.escape(w), t)) for w in words)


def explanation_leans(text: str) -> str | None:
    """'Positive' or 'Negative' when the explanation clearly argues one way (>=2 cue words and none the other way), else None."""
    bull, bear = _hits(text, _BULL_WORDS), _hits(text, _BEAR_WORDS)
    if bull >= 2 and bear == 0:
        return "Positive"
    if bear >= 2 and bull == 0:
        return "Negative"
    return None


def assess_direction(ai_direction: str | None, deterministic_direction: str | None, rows: list[dict], reasoning: str | None) -> dict:
    pos, neg = signal_counts(rows)
    total = pos + neg
    base = {
        "ai_direction": ai_direction, "deterministic_direction": deterministic_direction,
        "signals_positive": pos, "signals_negative": neg, "explanation_leans": explanation_leans(reasoning or ""),
        "status": "aligned", "withheld": False, "message": None,
    }
    if ai_direction not in ("Positive", "Negative"):
        if ai_direction == "Neutral" and deterministic_direction in _OPPOSITE:
            base.update(status="partial", message=f"The model reads Neutral while the signal model reads {deterministic_direction}.")
        return base

    support = pos if ai_direction == "Positive" else neg
    against = neg if ai_direction == "Positive" else pos
    opposite_det = deterministic_direction == _OPPOSITE[ai_direction]
    strong_against = (against >= 2 and support == 0) or (against >= 3 and against >= 2 * support)
    leans = base["explanation_leans"]
    explanation_mismatch = leans is not None and leans != ai_direction

    if opposite_det or strong_against:
        base.update(
            status="conflict", withheld=True,
            message=(f"Signals disagree, so no opening direction is shown. The model read {ai_direction.lower()}, the signal model reads "
                     f"{(deterministic_direction or 'unclear').lower()}, and {against} of {total} directional signals point the other way."),
        )
    elif deterministic_direction == "Neutral" or against > support or explanation_mismatch:
        why = ("its own explanation argues the other way" if explanation_mismatch
               else f"{against} of {total} directional signals point the other way" if against > support
               else "the signal model reads Neutral")
        base.update(status="partial", message=f"Mixed evidence: the model read {ai_direction.lower()}, but {why}.")
    return base


def apply_integrity(prediction: dict, deterministic_direction: str | None, rows: list[dict]) -> dict:
    """Returns a copy of prediction carrying direction_check; on a conflict the direction, confidence, range and the AI's
    supporting prose are removed from the returned object."""
    out = dict(prediction)
    check = assess_direction(out.get("direction"), deterministic_direction, rows, out.get("reasoning"))
    out["direction_check"] = check
    if check["withheld"]:
        # The suppressed AI direction and its supporting prose are NOT kept in the returned object (it is cached and served to
        # every consumer); only the neutral disagreement summary remains. The caller logs the audit details.
        out.update(direction=None, confidence=None, range_low=None, range_high=None, primary_drivers=[], reasoning=check["message"],
                   historical_note=None, conflicting_signals=[])
    return out


def build_forecast_meta(*, target_date: str, session_state: str, generated_at: str, ai_generated: bool, signals: dict,
                        rows: list[dict], weekend_snapshot_id: str | None) -> dict:
    gift = signals.get("gift_nifty") or {}
    return {
        "target_date": target_date,
        "target_session": "opening",
        "session_state": session_state,
        "generated_at": generated_at,
        "method": "ai_validated_against_signals" if ai_generated else "deterministic_signals",
        "signals": [{"label": r.get("label"), "direction": r.get("direction"), "detail": r.get("detail")} for r in rows],
        "gift_nifty_status": gift.get("status"),
        "gift_nifty_source_timestamp": gift.get("source_timestamp"),
        "weekend_snapshot_id": weekend_snapshot_id,
    }
