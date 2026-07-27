"""
Follow-up Intelligence (Phase 1.6) — builds grouped, contextual follow-up
suggestions from the response's own STRUCTURED evidence (companies,
sectors, decision gaps, risks, events, policies, ripple graph) rather than
asking the LLM to invent them (per the approved spec: "Do not ask the LLM
to invent follow-ups from scratch if the structured data already provides
the needed context"). Pure Python over data the pipeline already produced
— zero added latency, zero added LLM cost per response.

Every generated item carries two strings:
  - "text":  short label shown on the button (what the spec's mockups show)
  - "query": the SELF-CONTAINED question actually run as a fresh search —
    must name the company/sector explicitly, since a follow-up search has
    no access to this conversation's context beyond its own query text
    (see ai_search_service._detect_decision_intent / entity extraction,
    both operate on the query string alone).

Never generates a follow-up that just repeats the original query, and never
shows an empty category — a group with zero real items is omitted entirely
rather than padded with generic filler.
"""
from __future__ import annotations

import re

_MACRO_RE = re.compile(
    r"\brbi\b|repo rate|interest rate|inflation|crude|oil price|\bfii\b|\bdii\b|"
    r"monetary policy|fiscal policy|\bbudget\b|current account|forex reserves",
    re.IGNORECASE,
)
_ORDER_BOOK_SECTORS = {"Defence", "Infrastructure", "Infra", "Power", "Cement"}
_RATE_SENSITIVE_SECTORS = {"Banking", "Finance", "NBFC", "Real Estate", "Insurance", "Broking"}
_OIL_SENSITIVE_SECTORS = {"Energy", "Aviation", "Chemicals"}

_GROUP_META = {
    "risks":     {"label": "Risks", "icon": "risk"},
    "compare":   {"label": "Compare Further", "icon": "compare"},
    "portfolio": {"label": "Portfolio Decisions", "icon": "portfolio"},
    "deeper":    {"label": "Go Deeper", "icon": "deeper"},
    "macro":     {"label": "Macro Impact", "icon": "macro"},
    "horizon":   {"label": "Different Horizons", "icon": "horizon"},
    "ripple":    {"label": "Explore Ripple", "icon": "ripple"},
}
# Generation + fill priority — matches the spec's stated priority (decision
# gaps > risks > companies > events/policies > historical > sector intel),
# and doubles as the truncation order once the per-query budget is applied.
_GROUP_ORDER = ["risks", "compare", "portfolio", "deeper", "macro", "horizon", "ripple"]
_PER_GROUP_CAP = 3


def _item(text: str, query: str, difficulty: str) -> dict:
    return {"text": text, "query": query, "difficulty": difficulty}


def _company_row(symbol: str) -> dict | None:
    from app.api.companies import _NSE_UNIVERSE
    return next((co for co in _NSE_UNIVERSE if co["symbol"] == symbol), None)


def _sector_for(symbol: str) -> str | None:
    row = _company_row(symbol)
    return row["sector"] if row else None


def _same_sector_peers(sector: str, primary_industry: str | None, exclude: set[str], limit: int = 2) -> list[dict]:
    """Same coarse sector isn't enough on its own — this data's "Defence"
    bucket, for one, lumps genuine defence manufacturers (HAL, BEL, BDL)
    together with railway PSUs (RVNL, IRCON) that just happen to share the
    label. Require the candidate's own "industry" string to share a real
    word with the primary company's industry too, so "Compare BEL vs RVNL"
    (defence electronics vs railway infrastructure — not a comparison any
    real investor asked for) doesn't get suggested just because the sector
    column matches."""
    from app.api.companies import _NSE_UNIVERSE
    primary_words = {w.lower() for w in (primary_industry or "").split() if len(w) > 3}
    out = []
    for co in _NSE_UNIVERSE:
        if co["sector"] != sector or co["symbol"] in exclude:
            continue
        if primary_words:
            candidate_words = {w.lower() for w in (co.get("industry") or "").split() if len(w) > 3}
            if not (primary_words & candidate_words):
                continue
        out.append(co)
        if len(out) >= limit:
            break
    return out


def _budget(specialist_kind: str, has_macro_signal: bool) -> int:
    if specialist_kind == "comparison":
        return 8
    if specialist_kind == "sector":
        return 12 if has_macro_signal else 10
    return 6  # company (and anything else)


def _gen_risks(decision_engine_v2: dict, answer_risks: list[str], subject: str) -> list[dict]:
    items = []
    if decision_engine_v2.get("what_invalidates_the_thesis"):
        items.append(_item(
            "What could invalidate this thesis?",
            f"What could invalidate the investment thesis for {subject}?",
            "advanced",
        ))
    if answer_risks:
        items.append(_item(
            "What is the biggest downside risk?",
            f"What is the biggest downside risk for {subject} right now?",
            "beginner",
        ))
    if decision_engine_v2.get("what_changes_the_view"):
        items.append(_item(
            "Which upcoming event could change this verdict?",
            f"Which upcoming event could change the investment verdict on {subject}?",
            "intermediate",
        ))
    return items


def _gen_compare(companies: list[dict], specialist_kind: str, subject: str) -> list[dict]:
    if not companies:
        return []
    primary = companies[0]
    sym, name = primary.get("symbol"), primary.get("name")
    if not sym:
        return []
    primary_row = _company_row(sym)
    sector = primary_row["sector"] if primary_row else None
    if not sector:
        return []
    excl = {c.get("symbol") for c in companies if c.get("symbol")}
    peers = _same_sector_peers(sector, primary_row.get("industry"), excl, limit=2)
    items = [
        _item(f"Compare {sym} vs {peer['symbol']}", f"Compare {name} vs {peer['name']}", "intermediate")
        for peer in peers
    ]
    if specialist_kind == "comparison" or peers:
        items.append(_item(
            f"Which {sector.lower()} stock has the best valuation?",
            f"Which {sector} stock has the best valuation right now?",
            "advanced",
        ))
        if sector in _ORDER_BOOK_SECTORS:
            items.append(_item(
                f"Which {sector.lower()} company has the strongest order book?",
                f"Which {sector} company has the strongest order book right now?",
                "advanced",
            ))
    return items


def _gen_portfolio(companies: list[dict], specialist_kind: str) -> list[dict]:
    if not companies:
        return []
    items = []
    if specialist_kind == "comparison" and len(companies) >= 2:
        a, b = companies[0], companies[1]
        items.append(_item(
            f"Should I switch {a.get('symbol')} to {b.get('symbol')}?",
            f"Should I switch from {a.get('name')} to {b.get('name')}?",
            "beginner",
        ))
    primary = companies[0]
    name = primary.get("name")
    if name:
        items.append(_item(f"Should I add {primary.get('symbol')} to my portfolio?", f"Should I add {name} to my portfolio?", "beginner"))
        items.append(_item(f"Should I book profits on {primary.get('symbol')}?", f"Should I book profits on {name} right now?", "intermediate"))
    return items


def _gen_deeper(companies: list[dict]) -> list[dict]:
    if not companies:
        return []
    name = companies[0].get("name")
    sym = companies[0].get("symbol")
    if not name:
        return []
    templates = [
        ("Show quarterly earnings trend", f"Show {name}'s quarterly earnings trend", "intermediate"),
        ("Explain valuation", f"Explain {name}'s current valuation", "intermediate"),
        ("Analyze competitive advantage", f"Analyze {name}'s competitive advantage", "advanced"),
        ("Show promoter holding changes", f"Show recent promoter holding changes for {name}", "advanced"),
    ]
    return [_item(t, q, d) for t, q, d in templates[:3]]


def _gen_macro(policies: list[dict], sectors: list[dict], companies: list[dict], evidence_context: str, subject: str) -> list[dict]:
    signal = bool(policies) or bool(_MACRO_RE.search(evidence_context or ""))
    if not signal:
        return []
    items = [_item("What if RBI cuts rates again?", f"What if RBI cuts rates again — how would that affect {subject}?", "advanced")]
    sector_names = {s.get("name") for s in sectors if s.get("name")}
    for c in companies:
        sec = _sector_for(c.get("symbol", ""))
        if sec:
            sector_names.add(sec)
    if sector_names & _RATE_SENSITIVE_SECTORS:
        items.append(_item("How sensitive is this to interest rates?", f"How sensitive is {subject} to interest rate changes?", "advanced"))
    if sector_names & _OIL_SENSITIVE_SECTORS:
        items.append(_item("What happens if crude reaches $100?", f"What happens to {subject} if crude oil reaches $100 a barrel?", "advanced"))
    items.append(_item("Which sectors benefit most?", "Which sectors benefit most from the current policy environment?", "intermediate"))
    return items[:3]


def _gen_horizon(subject: str, subject_short: str, is_comparison: bool) -> list[dict]:
    # subject_short (symbols, e.g. "HAL vs BEL") keeps the button label
    # readable — subject (full names) still grounds the actual search query,
    # since entity resolution is more reliable against full company names.
    windows = [("1 Month", "1 month"), ("6 Months", "6 months"), ("3 Years", "3 years")]
    items = [_item(f"{subject_short} for {label}", f"{subject} for {phrase}", "beginner") for label, phrase in windows]
    if not is_comparison:
        items.append(_item(f"{subject_short} after next earnings", f"{subject} after next earnings", "intermediate"))
    return items


def _gen_ripple(graph: dict, exclude_labels: set[str]) -> list[dict]:
    items = []
    for node in (graph.get("nodes") or []):
        if node.get("type") == "query" or node.get("label") in exclude_labels:
            continue
        label = node.get("label")
        if not label:
            continue
        items.append(_item(f"Explore {label}", f"What is the impact of {label}?", "intermediate"))
        if len(items) >= 3:
            break
    return items


def generate(response: dict, specialist_kind: str, query: str, evidence_context: str) -> list[dict]:
    """Returns the ordered, capped, non-empty list of {"key","label","icon","items"}
    groups ready for the frontend — already trimmed to this query's dynamic
    budget (see _budget) so the caller doesn't need to re-truncate."""
    companies = response.get("companies") or []
    sectors = response.get("sectors") or []
    decision_engine_v2 = response.get("decision_engine_v2") or {}
    answer_risks = (response.get("answer") or {}).get("risks") or []
    policies = response.get("policies") or []
    graph = response.get("graph") or {}
    is_comparison = specialist_kind == "comparison"

    if is_comparison and len(companies) >= 2:
        subject = f"{companies[0].get('name')} vs {companies[1].get('name')}"
        subject_short = f"{companies[0].get('symbol')} vs {companies[1].get('symbol')}"
    elif companies:
        subject = companies[0].get("name") or companies[0].get("symbol") or query
        subject_short = companies[0].get("symbol") or subject
    elif sectors:
        subject = f"the {sectors[0].get('name')} sector"
        subject_short = sectors[0].get("name") or subject
    else:
        subject = query
        subject_short = query

    # Graph company nodes are labeled by SYMBOL, not full name (see
    # pipeline._build_graph) — exclude both forms, or "Explore BEL" shows up
    # as a "ripple" suggestion for a company that's already the subject.
    exclude_labels = (
        {c.get("name") for c in companies} | {c.get("symbol") for c in companies} | {s.get("name") for s in sectors}
    )

    raw_groups: dict[str, list[dict]] = {
        "risks": _gen_risks(decision_engine_v2, answer_risks, subject),
        "compare": _gen_compare(companies, specialist_kind, subject),
        "portfolio": _gen_portfolio(companies, specialist_kind),
        "deeper": _gen_deeper(companies),
        "macro": _gen_macro(policies, sectors, companies, evidence_context, subject),
        "horizon": _gen_horizon(subject, subject_short, is_comparison),
        "ripple": _gen_ripple(graph, exclude_labels),
    }

    has_macro_signal = bool(raw_groups["macro"])
    budget = _budget(specialist_kind, has_macro_signal)

    # Two-pass fill: guarantee every non-empty category gets AT LEAST one
    # slot (in priority order) before any category gets a second — a flat
    # priority-order truncation would let the top 2 categories eat the
    # whole budget on a small query, defeating the point of having 7
    # categories at all. Second pass tops up remaining budget, still in
    # priority order, capped per category.
    non_empty = [k for k in _GROUP_ORDER if raw_groups[k]]
    picked: dict[str, list[dict]] = {k: [] for k in non_empty}
    remaining = budget

    for key in non_empty:
        if remaining <= 0:
            break
        picked[key].append(raw_groups[key][0])
        remaining -= 1

    changed = True
    while remaining > 0 and changed:
        changed = False
        for key in non_empty:
            if remaining <= 0:
                break
            have = len(picked[key])
            if have < _PER_GROUP_CAP and have < len(raw_groups[key]):
                picked[key].append(raw_groups[key][have])
                remaining -= 1
                changed = True

    groups = [
        {"key": key, "label": _GROUP_META[key]["label"], "icon": _GROUP_META[key]["icon"], "items": picked[key]}
        for key in _GROUP_ORDER if picked.get(key)
    ]
    return groups
