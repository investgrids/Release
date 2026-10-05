"""
Deterministic switch-comparison assembly for AEV2 (aev2.2, 2026-09-22;
refactored 2026-09-22 to extract shared dimension math into
pair_comparison.py once comparison.py needed the same computation).

Same architecture rule as the rest of aev2/assemble.py: a PRESENTER over
CoreAnswer, never a second pipeline — the actual dimension math
(recent_developments/price_reaction/evidence_freshness) lives in
pair_comparison.py's build_pair_comparison_dimensions, shared verbatim
with comparison.py; this module only relabels that shared output onto
its own current_company/alternative_company-shaped schema and adds the
switch-specific concepts a neutral comparison doesn't have: role
resolution from decision_intent.py's holding/target, and conditions_
favoring_current/alternative.

Intent gate (2026-09-22 correction): a query resolves `switch_holding`/
`switch_target` from decision_intent.py's extraction for ANY 2-company
comparison-shaped query, including a neutral "Compare Infosys and TCS"
— that extraction doesn't itself distinguish switch phrasing from plain
comparison phrasing. Without checking `core.intent` against ui_mode.py's
own SWITCH_LIKE_INTENTS, this module would have labeled a plain
comparison as a "switch" with a "current holding" — exactly the
mislabeling the approved spec's semantic-differences table warns
against. Reuses that SAME set (never a second literal copy) so
switch_analysis and ui_mode.py's own classify_ui_mode can never
disagree about what counts as switch-shaped.

conditions_favoring_current/alternative and what_changes_the_comparison
are derived ONLY from the comparable dimensions above (never a new
judgment) — see _build_conditions. what_changes_the_comparison has no
deterministic CoreAnswer source yet (forward-looking monitoring
conditions would require either LLM generation or invented heuristics,
both excluded) — left honestly empty, matching risks_and_invalidation.
invalidates_if/watch_for's own precedent in the direct-company schema.
"""
from __future__ import annotations

from app.services.ai_search.aev2 import language_gate
from app.services.ai_search.aev2.citation_validator import validate_claim
from app.services.ai_search.aev2.pair_comparison import build_pair_comparison_dimensions, company_ref
from app.services.ai_search.aev2.schema import build_validated_claim
from app.services.ai_search.core_answer import CoreAnswer
from app.services.ai_search.ui_mode import SWITCH_LIKE_INTENTS


def _lookup_company(companies: tuple[dict, ...], name_or_symbol: str | None) -> dict | None:
    """Resolves a decision_intent.py holding/target NAME (or, from V2's
    own extraction, possibly already a symbol) against CoreAnswer's own
    resolved companies — symbol match first (exact), then case-
    insensitive name match. Never a fuzzy/similarity match; a switch
    role that doesn't resolve to one of CoreAnswer's own companies is
    None, not a guess."""
    if not name_or_symbol:
        return None
    needle = name_or_symbol.strip().upper()
    for c in companies:
        if (c.get("symbol") or "").upper() == needle:
            return c
    for c in companies:
        if (c.get("name") or "").strip().upper() == needle:
            return c
    return None


def _relabel_to_switch_roles(dimensions: list[dict]) -> list[dict]:
    """pair_comparison.py returns generic left_company/right_company keys
    — switch_analysis.py's own schema (unchanged from before the
    extraction) uses current_company/alternative_company instead."""
    relabeled = []
    for dim in dimensions:
        new_dim = dict(dim)
        new_dim["current_company"] = new_dim.pop("left_company")
        new_dim["alternative_company"] = new_dim.pop("right_company")
        relabeled.append(new_dim)
    return relabeled


def _build_conditions(dimensions: list[dict]) -> tuple[list[dict], list[dict]]:
    """Derived ONLY from the comparable dimensions above — never a new
    judgment, never phrased as a disadvantage for the side with less
    data (a `comparable: false` dimension contributes NOTHING here,
    favoring neither side). Switch-specific: a neutral comparison has no
    "favoring" concept at all (see comparison.py's own schema)."""
    favoring_current: list[dict] = []
    favoring_alternative: list[dict] = []
    for dim in dimensions:
        if not dim["comparable"]:
            continue
        cur_val, alt_val = dim["current_company"], dim["alternative_company"]
        if dim["key"] == "recent_developments":
            cur_count = int((cur_val["display"] or "0").split(" ", 1)[0])
            alt_count = int((alt_val["display"] or "0").split(" ", 1)[0])
            if cur_count > alt_count:
                favoring_current.append({"text": f"More recently disclosed company-specific developments ({cur_count} vs {alt_count})", "evidence_refs": cur_val["evidence_refs"]})
            elif alt_count > cur_count:
                favoring_alternative.append({"text": f"More recently disclosed company-specific developments ({alt_count} vs {cur_count})", "evidence_refs": alt_val["evidence_refs"]})
        elif dim["key"] == "evidence_freshness":
            if cur_val["display"] > alt_val["display"]:
                favoring_current.append({"text": "More recent evidence available", "evidence_refs": []})
            elif alt_val["display"] > cur_val["display"]:
                favoring_alternative.append({"text": "More recent evidence available", "evidence_refs": []})
    return favoring_current, favoring_alternative


def assemble_switch_analysis(
    core: CoreAnswer,
    *,
    catalog_ids: set[str],
    claim_refs: list[str],
    claim_supporting_text: str,
    recognized_symbols: set[str],
    name_tokens: set[str],
) -> dict | None:
    """Returns None for any non-switch query — not a comparison
    specialist call, holding/target didn't resolve to two distinct real
    companies, OR (2026-09-22 correction) the query's own decision_
    intent isn't switch-shaped (SWITCH_LIKE_INTENTS) even though 2
    companies resolved — that is the honest "not applicable" state, not
    a rejection; see schema.py's build_response docstring. A resolving
    switch query always gets a full object back — the FRONTEND decides
    whether it's good enough to render (same division of responsibility
    as direct_company_research's eligibility gate)."""
    if core.specialist != "comparison":
        return None
    if core.intent not in SWITCH_LIKE_INTENTS:
        return None
    current = _lookup_company(core.companies, core.switch_holding)
    alternative = _lookup_company(core.companies, core.switch_target)
    if not current or not alternative:
        return None
    if (current.get("symbol") or "").upper() == (alternative.get("symbol") or "").upper():
        return None

    gated = language_gate.gate("direct_comparison", core.bottom_line)
    if gated.had_violation:
        direct_comparison = build_validated_claim(gated.text, [], had_violation=True)
    elif not core.bottom_line:
        direct_comparison = build_validated_claim("", [], had_violation=False)
    else:
        claim = validate_claim(core.bottom_line, claim_refs, catalog_ids, recognized_symbols, claim_supporting_text, name_tokens)
        if not claim.valid:
            fallback = language_gate.FALLBACK_TEXT["direct_comparison"]
            direct_comparison = build_validated_claim(fallback, [], had_violation=True)
        else:
            direct_comparison = build_validated_claim(core.bottom_line, claim_refs, had_violation=False)

    dimensions = _relabel_to_switch_roles(build_pair_comparison_dimensions(core, current, alternative))
    favoring_current, favoring_alternative = _build_conditions(dimensions)

    return {
        "relationship": "switch",
        "current_company": company_ref(current),
        "alternative_company": company_ref(alternative),
        "direct_comparison": direct_comparison,
        "dimensions": dimensions,
        "conditions_favoring_current": favoring_current,
        "conditions_favoring_alternative": favoring_alternative,
        # No deterministic CoreAnswer source yet — see module docstring.
        "what_changes_the_comparison": [],
    }
