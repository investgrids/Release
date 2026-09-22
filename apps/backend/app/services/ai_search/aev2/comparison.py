"""
Deterministic standard two-company comparison assembly for AEV2
(aev2.3, 2026-09-22) — the neutral, no-holding-relationship counterpart
to switch_analysis.py. Reuses pair_comparison.py's shared dimension
builder verbatim (approved spec: "Do not copy switch_analysis.py —
extract the common deterministic work"), so the two assemblers can
never silently compute recent_developments/price_reaction/evidence_
freshness differently.

Runs independently of switch_analysis.py and does NOT check
core.intent — a switch-shaped query ("should I switch BEL to HAL")
still resolves the SAME 2 companies via the SAME comparison specialist,
so this module still builds a neutral comparison object for it too
(cheap: pure reformatting, no new retrieval or LLM call). Which ONE the
frontend actually renders is decided by ui_mode alone (classify_ui_mode
already returns exactly "switch_analysis" XOR "company_comparison" for
any given query) — never by this module refusing to run.

Multi-company comparisons ("Compare the top five banks") are explicitly
out of scope for this phase-one contract — a query resolving any company
count other than exactly 2 returns None (the honest "not applicable"
state), not a degraded 2-of-5 comparison. A separate multi-entity matrix
contract would be needed for that case.

Preserves the user's own entity order — CoreAnswer.companies[0]/[1] are
whatever order V3's entity resolution already produced (first-mentioned
first, per intent.py's own resolve_comparison docstring), never
re-sorted alphabetically or by any other criterion here.

Deliberately excludes every switch-specific concept: no current_company/
alternative_company framing, no conditions_favoring_*, no switch_
holding/switch_target read. This schema only ever has left_company/
right_company, a validated+cited direct_comparison claim, and the same
3 comparison dimensions switch_analysis.py uses — "only compares
evidence," per the approved spec's semantic-differences table.
"""
from __future__ import annotations

from app.services.ai_search.aev2 import language_gate
from app.services.ai_search.aev2.citation_validator import validate_claim
from app.services.ai_search.aev2.pair_comparison import build_pair_comparison_dimensions, company_ref
from app.services.ai_search.aev2.schema import build_validated_claim
from app.services.ai_search.core_answer import CoreAnswer


def assemble_comparison(
    core: CoreAnswer,
    *,
    catalog_ids: set[str],
    claim_refs: list[str],
    claim_supporting_text: str,
    recognized_symbols: set[str],
    name_tokens: set[str],
) -> dict | None:
    """None for any comparison specialist call that didn't resolve
    exactly 2 distinct companies — a genuinely different company count
    (1, 3+) is out of scope for this phase-one contract entirely, not a
    rejection to render degraded (see module docstring). A resolving
    2-company comparison always gets a full object back — the FRONTEND
    eligibility gate decides whether it's good enough to render (same
    division of responsibility as switch_analysis/direct_company_
    research)."""
    if core.specialist != "comparison":
        return None
    if len(core.companies) != 2:
        return None
    left, right = core.companies[0], core.companies[1]
    if (left.get("symbol") or "").upper() == (right.get("symbol") or "").upper():
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

    dimensions = build_pair_comparison_dimensions(core, left, right)

    return {
        "relationship": "comparison",
        "left_company": company_ref(left),
        "right_company": company_ref(right),
        "direct_comparison": direct_comparison,
        "dimensions": dimensions,
    }
