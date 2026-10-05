"""
Structured public claims: default-deny authorization (Step 3.4D-2).

Gate B (answer_authorization.py) checks the answer's PROSE. The saved CC1 generation shows what it does not read: a "Selectively Constructive" rating, "bullish" direction, confidence 69, scenario
probabilities 30/50/20, impact scores 58/50, key-driver confidences, an `ai_conclusion.current_view` of "Positive" and a whole `decision_intelligence` block, none derived from any evidence item and
sitting next to prose that says the evidence cannot support a strength ranking.

Rule: an analytical claim that is a rating, direction, sentiment, confidence, probability, score, expected range, winner/preference or recommendation is public only if a DETERMINISTIC producer made it
(for example confidence from the evidence-grounded confidence breakdown, the engine verdict and the pairwise decision engine, both computed in code from market data). A value the LLM generated is never
public by itself. No producer authorizes the LLM's own versions yet, so they are withheld, and the response says they are unavailable. They are NOT converted into Neutral / Cautious / "No clear edge":
those are conclusions too, so the withheld fields hold an explicit unavailable state (None / empty / "Not Applicable").

`sanitize` runs on the generated answer after prose authorization and before assembly, returning a copy and the list of what was withheld. Prose fields are untouched here: they are covered by Gate B and
by the conclusion-scope check. Pure function, no I/O, no model.
"""
from __future__ import annotations

import copy

WITHHELD_STATE = "unavailable"

# Whole blocks that consist of LLM-generated analytical conclusions and have no deterministic producer.
_DROP_TO_EMPTY = {
    "scenarios": {},                # outcomes with probabilities / expected moves
    "decision_intelligence": {},    # comparative winner/preference block (the deterministic engine recommendation is attached later, in code, only when its conclusion is authorized)
    "decision_engine_v2": {},       # verdict scale, "why", action
    "opportunity_risk_matrix": {},  # scored opportunities and risks
    "ai_conclusion": {},            # current_view and investor_action_note
    "timeline_intelligence": {},    # inferred timing and stage claims
}
_VERDICT_BLANK = {"rating": "Not Applicable", "direction": None, "confidence": None, "horizon": "", "top_picks": [], "risks": [], "catalysts": [], "opportunity_score": None, "risk_level": "", "suitable_for": ""}
_COMPANY_KEEP = ("symbol", "name", "reason", "why_it_matters")
_SECTOR_KEEP = ("name", "explanation")
_DRIVER_KEEP = ("icon", "title", "explanation")


def sanitize(ai: dict) -> tuple[dict, list[str]]:
    """Return (a copy of `ai` with every LLM-generated structured analytical claim replaced by an explicit unavailable state, names of the fields that carried one)."""
    out = copy.deepcopy(ai)
    withheld: list[str] = []

    def note(name: str):
        if name not in withheld:
            withheld.append(name)

    for k, empty in _DROP_TO_EMPTY.items():
        if out.get(k) not in (None, "", [], {}):
            note(k)
        out[k] = copy.deepcopy(empty)

    v = out.get("investment_verdict")
    if isinstance(v, dict) and any(v.get(f) not in (None, "", [], {}, "Not Applicable") for f in ("rating", "direction", "confidence", "top_picks", "opportunity_score", "catalysts")):
        note("investment_verdict")
    out["investment_verdict"] = copy.deepcopy(_VERDICT_BLANK)

    for f in ("confidence", "confidence_self_rating", "sentiment"):
        if out.get(f) not in (None, ""):
            note(f)
        out[f] = None

    cos = []
    for c in out.get("companies") or []:
        if isinstance(c, dict):
            if any(c.get(f) not in (None, "") for f in ("impact_type", "impact_score", "confidence")):
                note("companies.impact")
            cos.append({k: c[k] for k in _COMPANY_KEEP if k in c} | {"impact_type": None, "impact_score": None, "confidence": None})
    out["companies"] = cos

    secs = []
    for s in out.get("sectors") or []:
        if isinstance(s, dict):
            if any(s.get(f) not in (None, "") for f in ("score", "outlook", "positive", "confidence")):
                note("sectors.outlook")
            secs.append({k: s[k] for k in _SECTOR_KEEP if k in s} | {"score": None, "outlook": None, "positive": None, "confidence": None})
    out["sectors"] = secs

    drivers = []
    for d in out.get("key_drivers") or []:
        if isinstance(d, dict):
            if d.get("confidence") not in (None, ""):
                note("key_drivers.confidence")
            drivers.append({k: d[k] for k in _DRIVER_KEEP if k in d} | {"confidence": None})
    out["key_drivers"] = drivers
    return out, withheld


def public_summary(withheld: list[str]) -> dict:
    return {"policy": "llm_structured_claims_withheld_unless_deterministically_authorized", "withheld": list(withheld), "state": WITHHELD_STATE if withheld else "none_generated"}
