"""
Gate A: pre-model evidence sufficiency.

Principle: no evidence capable of supporting the requested analysis means no analytical model call. CR2 ("How is 3M India doing as a business?") reached the model with an empty bundle and
got a confident, invented analysis back (Step 3.3b). The pipeline already knew, before any model call, that nothing could support it.

Sufficiency is NOT a count. It is whether the evidence covers what THIS kind of question requires:

  company assessment   current company-specific evidence that is not just routine administration (a newspaper-publication notice is not evidence of how a business is doing)
  event impact         evidence that establishes the event the question asserts (the premise check)
  comparison           usable evidence for EACH entity: one company's evidence never stands in for the other's
  sector assessment    sector-level evidence: a sector-wide item (never a single company's filing) or the live row for that sector
  macro transmission   evidence of the stated macro condition, plus sector exposure evidence when a sector is named
  sector scan          the live sector rows
  explanation          not gated here (an educational contract is a separate step)

Ten irrelevant articles are zero usable evidence; the bundle has already had tips articles, single-company filings (in sector bundles) and brand-only mentions removed by evidence_filter.

The result keeps WHY: required / satisfied / missing / reason, plus the verified context that does exist, so it can be shown separately and labelled as context. Pure functions, no I/O, no model.
"""
from __future__ import annotations

import re

from app.services.ai_search import evidence_scope as scope
from app.services.ai_search.evidence_filter import _MACRO_VOCAB, _SECTOR_TERMS, mentions, topic_search_terms

SUFFICIENT = "SUFFICIENT"
INSUFFICIENT = "INSUFFICIENT"


def _items(evidence) -> list[dict]:
    out: list[dict] = []
    for kind, rows in (("event", evidence.events), ("news", evidence.news), ("announcement", evidence.announcements or []), ("policy", evidence.policies)):
        for r in rows:
            it = scope.normalize(kind, r)
            it["symbol"] = r.get("symbol") if isinstance(r, dict) else None
            out.append(it)
    return out


def _company_items(items: list[dict], symbol: str, universe: list[dict]) -> list[dict]:
    """Substantive evidence about this company: not a tips article, not routine administration, and eligible for the company (announcements are fetched per symbol)."""
    out = []
    for it in items:
        if it["kind"] == "policy" or scope.is_tips_article(it["title"], it["summary"]) or scope.is_administrative(it["title"], it["summary"]):
            continue
        if it["kind"] == "announcement":
            if it.get("symbol") == symbol or scope.eligible_for_company(it, symbol, universe)[0]:
                out.append(it)
        elif scope.eligible_for_company(it, symbol, universe)[0]:
            out.append(it)
    return out


def _has_valuation(evidence, symbol: str) -> bool:
    v = (evidence.valuation or {}).get(symbol) or {}
    return v.get("pe") is not None or v.get("pb") is not None


def _sector_evidence(items: list[dict], evidence, sector: str) -> list[str]:
    terms = _SECTOR_TERMS.get(sector.lower(), [sector])
    hits = [it["title"][:90] for it in items if it["kind"] != "announcement" and scope.eligible_for_sector(it)[0] and mentions(f"{it['title']} {it['summary']}", terms)]
    rows = [f"sector row: {r.get('name')}" for r in (evidence.sector_rows or []) if sector.lower() in str(r.get("name", "")).lower() or str(r.get("name", "")).lower() in sector.lower()]
    return hits + rows


def _macro_terms(query: str, entities: dict) -> list[str]:
    return topic_search_terms(query, {"sectors": [], "policies": entities.get("policies") or []})


def _macro_evidence(items: list[dict], terms: list[str]) -> list[str]:
    return [it["title"][:90] for it in items if scope.eligible_for_sector(it)[0] and it["kind"] != "announcement" and mentions(f"{it['title']} {it['summary']}", terms)]


def _name(symbol: str, entities: dict, universe: list[dict]) -> str:
    for m in entities.get("company_matches") or []:
        if m.get("symbol") == symbol and m.get("name"):
            return re.sub(r"\s+(?:ltd\.?|limited)$", "", m["name"], flags=re.IGNORECASE)
    co = next((c for c in universe if c["symbol"] == symbol), None)
    return re.sub(r"\s+(?:ltd\.?|limited)$", "", co["name"], flags=re.IGNORECASE) if co else symbol


def assess(query: str, intent_data: dict, entities: dict, evidence, universe: list[dict]) -> dict:
    """Decide whether the bundle can support the analysis this question asks for. Never raises; an unknown shape is reported as not gated."""
    plan = getattr(evidence, "plan_kind", None)
    companies = [c for c in (entities.get("companies") or []) if c]
    sectors = entities.get("sectors") or []
    premise = getattr(evidence, "premise", None) or {}
    items = _items(evidence)
    result: dict = {"status": SUFFICIENT, "kind": "not_gated", "required": [], "satisfied": [], "missing": [], "reason": None, "missing_entities": [], "context": []}

    def finish(kind, required, satisfied, missing, reason=None, missing_entities=None, context=None):
        result.update({"kind": kind, "required": required, "satisfied": satisfied, "missing": missing, "reason": reason if missing else None,
                       "status": INSUFFICIENT if missing else SUFFICIENT, "missing_entities": missing_entities or [], "context": (context or [])[:5]})
        return result

    if plan == "company" and companies:
        sym = companies[0]
        mine = _company_items(items, sym, universe)
        ctx = [it["title"][:100] for it in mine]
        if premise.get("required"):
            ok = bool(premise.get("supported"))
            return finish("event_impact", ["event_verification"], ["event_verification"] if ok else [], [] if ok else ["event_verification"], "event_premise_not_established",
                          [] if ok else [sym], ctx)
        ok = bool(mine)
        return finish("company_assessment", ["current_company_evidence"], ["current_company_evidence"] if ok else [], [] if ok else ["current_company_evidence"],
                      "no_recent_company_evidence", [] if ok else [sym], ctx)

    if plan == "comparison" and len(companies) >= 2:
        required, satisfied, missing_e = [], [], []
        ctx: list[str] = []
        for sym in companies[:3]:
            mine = _company_items(items, sym, universe)
            required.append(f"evidence_for_{sym}")
            if mine or _has_valuation(evidence, sym):
                satisfied.append(f"evidence_for_{sym}")
                ctx += [f"{sym}: {it['title'][:80]}" for it in mine[:2]] + ([f"{sym}: valuation data"] if _has_valuation(evidence, sym) else [])
            else:
                missing_e.append(sym)
        return finish("comparison", required, satisfied, [f"evidence_for_{s}" for s in missing_e], "evidence_missing_for_at_least_one_company", missing_e, ctx)

    if plan == "topic":
        macro_terms = _macro_terms(query, entities)
        macro_asked = bool(entities.get("policies")) or any(k in set(re.findall(r"[a-z0-9&]+", query.lower())) for k in _MACRO_VOCAB)
        required, satisfied, missing, ctx = [], [], [], []
        if macro_asked:
            hits = _macro_evidence(items, macro_terms)
            required.append("macro_condition_evidence")
            (satisfied if hits else missing).append("macro_condition_evidence")
            ctx += hits[:3]
        if sectors:
            for s in sectors:
                hits = _sector_evidence(items, evidence, s)
                required.append(f"sector_evidence_{s}")
                (satisfied if hits else missing).append(f"sector_evidence_{s}")
                ctx += hits[:3]
        if not macro_asked and not sectors:
            if re.search(r"(?<![a-z])sectors?(?![a-z])", query.lower()):
                required.append("live_sector_rows")
                ok = bool(evidence.sector_rows)
                (satisfied if ok else missing).append("live_sector_rows")
                ctx += [f"{r.get('name')} {r.get('value')}" for r in (evidence.sector_rows or [])[:3]]
            else:
                ok = any(scope.eligible_for_sector(it)[0] and not scope.is_tips_article(it["title"], it["summary"]) for it in items)
                required.append("topic_evidence")
                (satisfied if ok else missing).append("topic_evidence")
        kind = "macro_transmission" if macro_asked else ("sector_assessment" if sectors else "sector_scan")
        return finish(kind, required, satisfied, missing, "no_evidence_for_the_stated_condition_or_sector", [], ctx)

    return result


_MESSAGES = {
    "company_assessment": ("Not enough recent evidence",
                           "MarketRipple doesn't currently have enough recent, company-specific evidence to assess {name}'s business performance reliably. "
                           "It won't infer current financial strength, valuation, margins or outlook without supporting evidence."),
    "event_impact": ("I couldn't verify the stated event",
                     "MarketRipple's available recent evidence doesn't confirm the development described in the question ({what}) for {name}, so its impact can't be assessed as a confirmed development."),
    "comparison": ("Not enough evidence for both companies",
                   "MarketRipple doesn't have enough recent evidence for {missing} to compare them reliably. It won't substitute evidence about one company for the other."),
    "sector_assessment": ("Not enough sector evidence",
                          "MarketRipple doesn't currently have enough recent sector-level evidence to assess this sector reliably, and it won't infer sector conditions from individual company filings."),
    "macro_transmission": ("Not enough evidence on the stated condition",
                           "MarketRipple doesn't currently have enough recent evidence on the condition described in the question, or on the exposure it would work through, to assess the effect reliably."),
    "sector_scan": ("Sector data unavailable", "MarketRipple doesn't currently have live sector data to answer this."),
}


def public_message(suff: dict, entities: dict, universe: list[dict], premise: dict | None = None) -> tuple[str, str]:
    """(title, body) for an INSUFFICIENT result, stating exactly what cannot be established. Neutral wording: no verdict, no recommendation language."""
    title, body = _MESSAGES.get(suff["kind"], ("Not enough evidence", "MarketRipple doesn't currently have enough evidence to answer this reliably."))
    companies = [c for c in (entities.get("companies") or []) if c]
    name = _name(companies[0], entities, universe) if companies else "this company"
    terms = (premise or {}).get("terms") or []
    what = ("a " + " / ".join(terms)) if terms else "the event"
    missing = " and ".join(_name(s, entities, universe) for s in suff.get("missing_entities") or []) or "at least one of the companies"
    return title, body.format(name=name, what=what, missing=missing)
