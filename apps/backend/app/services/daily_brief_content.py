"""Phase 2 content helpers for the Daily Brief: evidence-backed catalysts/risks, sentence ledger for de-duplication, and
session-aware FAQ construction. Pure functions: no network, no DB, no LLM."""
from __future__ import annotations

import re

from app.services.daily_brief_composer import NEAR_FLAT_PCT


def normalise(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def sentences_of(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"(?<=[.!?])\s+", text or "") if p.strip()]


class Ledger:
    """Remembers what each surface already says so a later surface does not repeat it."""

    def __init__(self) -> None:
        self._seen: set[str] = set()

    def add(self, text: str) -> None:
        for s in sentences_of(text):
            self._seen.add(normalise(s))

    def fresh_sentences(self, text: str) -> list[str]:
        return [s for s in sentences_of(text) if normalise(s) not in self._seen]

    def is_duplicate(self, text: str) -> bool:
        parts = sentences_of(text)
        return bool(parts) and all(normalise(s) in self._seen for s in parts)


# ── catalysts / risks ───────────────────────────────────────────────────────────────────────────────────────────────

# Rising is BAD for Indian equities for these (import cost, rupee weakness, volatility); rising is good for none of them.
_RISE_IS_RISK = {"BRENT_CRUDE", "USD_INR", "INDIA_VIX"}
_OUTCOME_INDICES = {"NIFTY_50", "BANK_NIFTY", "SENSEX"}   # outcomes of the session, not drivers of it


def _explain_signal(f: dict, rising: bool) -> tuple[str, str]:
    """(kind, explanation) for a market signal fact, built only from the fact's own value/change."""
    key, name, value = f.get("entity_key"), f.get("name"), f.get("value")
    pct = f.get("change_pct")
    if pct is None:
        pct = f.get("numeric_value") if f.get("entity_type") == "market_index" else None
    move = f" ({pct:+.2f}%)" if isinstance(pct, (int, float)) else ""
    if key == "INDIA_VIX":
        return ("risk", f"India VIX {'rose' if rising else 'fell'} to {value}{move}: "
                        + ("expected volatility is higher, which usually goes with a more cautious market."
                           if rising else "expected volatility eased, which usually goes with a calmer market."))
    if key == "BRENT_CRUDE":
        return ("risk" if rising else "catalyst",
                f"Brent crude is {'rising' if rising else 'falling'} at {value}: "
                + ("higher import costs pressure oil-importing sectors and the rupee." if rising
                   else "lower crude eases import costs for oil-importing sectors."))
    if key == "USD_INR":
        return ("risk" if rising else "catalyst",
                f"USD/INR is {'higher' if rising else 'lower'} at {value}: "
                + ("a weaker rupee raises import costs but helps exporters." if rising
                   else "a firmer rupee lowers import costs but squeezes exporters."))
    return ("risk" if not rising else "catalyst", f"{name} {'rose' if rising else 'fell'}{move}.")


def catalysts_and_risks(facts: list[dict]) -> dict:
    """Names (backward compatible) plus evidence-backed explanations. Returns
    {catalysts, risks, catalyst_details, risk_details}; every detail carries the fact it came from."""
    cats: list[dict] = []
    risks: list[dict] = []
    for f in facts:
        etype, key, name = f.get("entity_type"), f.get("entity_key"), f.get("name")
        if etype == "macro" or key in _OUTCOME_INDICES:
            continue
        if etype == "event":
            sentiment = (f.get("evidence") or {}).get("sentiment")
            if sentiment not in ("bullish", "bearish"):
                continue
            item = {"name": name, "explanation": (f.get("claim") or name or "").strip(),
                    "source": f.get("source"), "fact_key": f.get("fact_key")}
            (cats if sentiment == "bullish" else risks).append(item)
            continue
        direction = (f.get("direction") or "").lower()
        if direction not in ("up", "down", "rising", "falling"):
            continue
        pct = f.get("change_pct") if f.get("change_pct") is not None else (f.get("numeric_value") if etype == "market_index" else None)
        if isinstance(pct, (int, float)) and abs(pct) < NEAR_FLAT_PCT:
            continue
        rising = direction in ("up", "rising")
        kind, why = _explain_signal(f, rising)
        if key in _RISE_IS_RISK:
            kind = "risk" if rising else "catalyst"
        item = {"name": name, "explanation": why, "source": f.get("source"), "fact_key": f.get("fact_key")}
        (risks if kind == "risk" else cats).append(item)
    cats, risks = cats[:4], risks[:4]
    return {"catalysts": [c["name"] for c in cats], "risks": [r["name"] for r in risks],
            "catalyst_details": cats, "risk_details": risks}
