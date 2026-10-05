"""
Conclusion scope for comparison answers (Step 3.4D-2).

The live CC1 answer (Step 3.4C/3.4D-1) compared TCS and Infosys on valuation multiples only, then published a "Selectively Constructive / bullish" verdict as if it answered "which is stronger?".
Gate A correctly allowed generation (valuation exists for both), but "enough evidence to generate" is not "enough evidence for the conclusion the question asks for".

This module answers a different, deterministic question: which CONCLUSION does the question request, and which conclusion does the evidence actually authorize?

  requested  overall_strength   a broad comparison ("which is stronger / better / worth buying?")
             valuation          the question is itself about valuation ("which is cheaper?", "compare P/E")
  coverage   per company: valuation (P/E or P/B present) and operating (a substantive, non-administrative item about results, earnings, revenue, profit, margins, orders or guidance)
  authorized overall_strength   every compared company has operating evidence
             valuation_comparison  valuation for every compared company, operating evidence missing for at least one
             not_applicable  not a comparison

Valuation-only evidence therefore authorizes a valuation comparison and never an overall company-strength conclusion. Partial analysis is preserved: the valuation comparison stays; a prose sentence that
states an overall winner without a valuation qualifier is not authorized (see `overreach`). Pure functions, no I/O, no model.
"""
from __future__ import annotations

import re

from app.services.ai_search import evidence_scope as scope
from app.services.ai_search.claim_sources import _sentences, answer_pieces

OVERALL = "overall_strength"
VALUATION = "valuation"
VALUATION_COMPARISON = "valuation_comparison"
NOT_APPLICABLE = "not_applicable"

_VALUATION_QUERY = re.compile(r"(?<![a-z])(?:valuation|valuations|cheaper|cheapest|expensive|overvalued|undervalued|p\s*/\s*e|p\s*/\s*b|pe ratio|pb ratio|multiples?|price[- ]to)(?![a-z])", re.IGNORECASE)
# A substantive operating item: results/earnings/revenue/profit/margin/order book/guidance. Administrative items never count (evidence_scope.is_administrative).
_OPERATING = re.compile(r"(?<![a-z])(?:financial\s+results?|quarterly\s+results?|annual\s+results?|results?\s+for|q[1-4]\s*(?:fy)?\s*\d*\s*results?|earnings|revenue|net\s+profit|profit|ebitda|margins?|order\s+(?:book|inflow|win)s?|orders?\s+worth|guidance|outcome\s+of\s+board\s+meeting)(?![a-z])", re.IGNORECASE)

# Prose that states an overall winner/preference, and what makes such a sentence acceptable.
_WINNER = re.compile(r"(?<![a-z])(?:stronger|strongest|better|superior|outperform\w*|winner|more\s+attractive|preferred|prefers?|favou?rs?|favou?rite|top\s+pick|best\s+(?:company|stock|pick|choice|business|option|bet)|leads?)(?![a-z])", re.IGNORECASE)
_QUALIFIER = re.compile(r"(?<![a-z])(?:valuation|valuations|multiples?|p\s*/\s*e|p\s*/\s*b|price[- ]to|cheaper|cheapest|priced|52[- ]week)(?![a-z])", re.IGNORECASE)
_HEDGE = re.compile(r"(?<![a-z])(?:not|cannot|can't|insufficient|unable|lacks?|lacking|without|unresolved|unavailable|until|rather\s+than|no\s+(?:such|comparable))(?![a-z])", re.IGNORECASE)


def _is_valuation_only_question(query: str) -> bool:
    return bool(_VALUATION_QUERY.search(query or ""))


def _items(evidence) -> list[dict]:
    out: list[dict] = []
    for kind, rows in (("event", evidence.events), ("news", evidence.news), ("announcement", evidence.announcements or [])):
        for r in rows:
            it = scope.normalize(kind, r)
            it["symbol"] = r.get("symbol") if isinstance(r, dict) else None
            out.append(it)
    return out


def _has_valuation(evidence, symbol: str) -> bool:
    v = (evidence.valuation or {}).get(symbol) or {}
    return v.get("pe") is not None or v.get("pb") is not None


def _has_operating(items: list[dict], symbol: str, universe: list[dict]) -> bool:
    """Company-specific operating evidence: the operating term must be in the item's TITLE (a forward-looking mention inside a market-wrap summary, or a sector item that talks about "revenue" in general,
    is not evidence about this company), and the item must be about this company (announcement tied to its symbol, or the company named in the title)."""
    terms = scope.company_terms(symbol, universe)
    for it in items:
        if scope.is_tips_article(it["title"], it["summary"]) or scope.is_administrative(it["title"], it["summary"]):
            continue
        about = (it.get("symbol") == symbol) if it["kind"] == "announcement" else scope.names_company(it["title"], terms)
        if about and _OPERATING.search(it["title"]):
            return True
    return False


def assess(query: str, intent_data: dict | None, entities: dict, evidence, universe: list[dict]) -> dict:
    companies = [c for c in (entities.get("companies") or []) if c]
    if getattr(evidence, "plan_kind", None) != "comparison" or len(companies) < 2:
        return {"requested": NOT_APPLICABLE, "authorized": NOT_APPLICABLE, "missing": [], "coverage": {}, "reason": None, "partial": False}
    items = _items(evidence)
    coverage = {s: {"valuation": _has_valuation(evidence, s), "operating": _has_operating(items, s, universe)} for s in companies[:3]}
    requested = VALUATION if _is_valuation_only_question(query) else OVERALL
    all_operating = all(c["operating"] for c in coverage.values())
    all_valuation = all(c["valuation"] for c in coverage.values())
    if requested == VALUATION:
        authorized = VALUATION_COMPARISON if all_valuation else NOT_APPLICABLE
    else:
        authorized = OVERALL if all_operating else (VALUATION_COMPARISON if all_valuation else NOT_APPLICABLE)
    missing = [f"operating_evidence_{s}" for s, c in coverage.items() if not c["operating"]] if requested == OVERALL and authorized != OVERALL else []
    partial = requested == OVERALL and authorized != OVERALL
    return {"requested": requested, "authorized": authorized, "missing": missing, "coverage": coverage, "partial": partial,
            "reason": "overall_strength_needs_operating_evidence_for_every_company" if partial else None}


def overreach(ai: dict, scope_result: dict) -> list[str]:
    """Prose sentences that state an overall winner/preference when only a narrower conclusion is authorized. Deterministic keyword rule: a sentence naming a winner/preference word with no valuation
    qualifier and no hedge is an overall-strength conclusion. Empty when the full conclusion is authorized or the question is not a comparison."""
    if not scope_result.get("partial"):
        return []
    found: list[str] = []
    for piece in answer_pieces(ai):
        for s in _sentences(piece):
            if _WINNER.search(s) and not _QUALIFIER.search(s) and not _HEDGE.search(s):
                found.append(s)
    return list(dict.fromkeys(found))


def public_summary(scope_result: dict) -> dict:
    return {k: scope_result.get(k) for k in ("requested", "authorized", "partial", "missing", "reason", "coverage")}


def partial_note(scope_result: dict, names: dict[str, str] | None = None) -> str | None:
    """One honest line for the response when the conclusion is narrower than the question."""
    if not scope_result.get("partial"):
        return None
    who = " and ".join((names or {}).get(m.replace("operating_evidence_", ""), m.replace("operating_evidence_", "")) for m in scope_result.get("missing", [])) or "one or more of the companies"
    return (f"This is a valuation comparison only. MarketRipple doesn't have current operating evidence (results, growth, margins, orders) for {who}, "
            "so it doesn't conclude which company is stronger overall.")
