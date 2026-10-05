"""
ui_mode classification — a minimal, additive projection from the
EXISTING classification signals (decision_intent.py's 12 labels, Market
Pulse detection, pipeline.py::_route_specialist's specialist_kind,
entities.py's policy/sector matches) onto one of this codebase's known
UI modes.

This is deliberately NOT the full "one explicit IntentResolution
contract" the 2026-09-21 intent audit's Phase 2 remediation calls for
(that consolidation replaces the 4 competing classifiers themselves,
end to end) — this module is a thin, isolated projection over their
CURRENT outputs, so the frontend can start rendering intent-aware UI
now without waiting for that larger backend refactor. Its public
contract (the ui_mode string values below) is designed to survive that
later migration unchanged; only this module's internals would be
replaced by the real IntentResolution classifier.

Priority order (2026-09-22, intent-coverage audit — REORDERED from the
original "sector specialist checked first" version, which let a bare
sector-trigger WORD silently outrank an explicit, more specific intent
classification; see this module's own docstring history in git blame
for the exact finding: "Banking sector just reported stronger credit
growth" used to lose news_reaction and land on sector_theme_research
purely because "sector" appears in the text):

    1. comparison/switch semantics (specialist_kind == "comparison")
    2. explicit news_reaction
    3. explicit policy intent
    4. explicit unsupported intent (entry_timing/list_picks/
       portfolio_review/earnings_preview — each a REAL, NAMED
       classification this codebase recognizes but cannot yet answer,
       distinct from the coarse "no signal at all" fallback below)
    5. factual lookup
    6. generic specialist (sector) — only once nothing more specific
       matched
    7. default company research

Steps 1 and 2-4 can never collide in practice: pipeline.py's own
_route_specialist already excludes list_picks/portfolio_review/
news_reaction/earnings_preview/entry_timing from ever reaching
specialist_kind == "comparison" in the first place — this module's own
ordering doesn't rely on that exclusion holding (each check is still
independently correct if it didn't), it just documents why the two
groups are already mutually exclusive today.

Known limitation, inherited from the classifiers this reads (not
introduced here — see the audit): sector detection requires the literal
word "sector"/"industry" in the query, so a query like "why are banking
stocks down today?" resolves to company_specialist (not sector) and
therefore direct_company_research here, not sector_theme_research. This
is exactly the "expanded sector/policy entity vocabulary" gap the
audit's Phase 3 names as separate follow-up work.
"""
from __future__ import annotations

import re

from app.services.ai_search.macro_drivers import macro_driver

UI_MODES = (
    "direct_company_research",
    "switch_analysis",
    "company_comparison",
    "factual_lookup",
    "policy_macro_impact",
    "market_pulse",
    "event_impact",
    "sector_theme_research",
    # ── 2026-09-22, intent-coverage audit — explicit recognized-but-
    # unsupported modes. Each has its own real reason (see
    # _UNSUPPORTED_INTENT_UI_MODE below and the frontend's
    # UnsupportedUIMode registry) — never collapsed into a single
    # generic "unavailable" bucket the way an unwired-but-eventually-
    # real mode is.
    "technical_timing",
    "company_discovery",
    "portfolio_review",
    "earnings_preview",
    "multi_company_comparison",
)

# Decision-intent labels (decision_intent.py) that read as a personal
# holding decision rather than a neutral side-by-side comparison, when
# BOTH a holding and a target were actually resolved. Public (2026-09-22):
# aev2/switch_analysis.py imports this SAME set to decide whether a
# 2-company comparison query is switch-shaped before assembling a
# "current holding vs proposed alternative" object — the one real
# distinguishing signal between switch_analysis and a neutral
# comparison, never duplicated as a second literal set there.
SWITCH_LIKE_INTENTS = {"switch", "hold", "sell", "buy", "decision"}

# Decision-intent labels this codebase recognizes explicitly but cannot
# yet answer with real, non-fabricated content — each maps to its own
# ui_mode (2026-09-22, intent-coverage audit findings 2-4 + the
# earnings-preview gap found alongside them). _route_specialist already
# keeps every one of these OUT of comparison routing regardless of
# whether the query text also happens to look comparison-shaped (e.g.
# "top gainers vs top losers" stays list_picks-shaped, never hijacks the
# comparison specialist) — see that function's own exclusion tuple.
# earnings_preview status: unsupported_pending_data_foundation (2026-
# 09-22, earnings-preview feasibility audit closed BLOCKED — no company-
# earnings-date calendar and no consensus-estimate source exist in this
# codebase; the dormant banking-only XBRL FinancialFact pipeline is a
# real future input but not sufficient on its own). This mapping does
# not change until Data Foundation ships a real calendar + licensed
# estimates.
_UNSUPPORTED_INTENT_UI_MODE: dict[str, str] = {
    "entry_timing": "technical_timing",
    "list_picks": "company_discovery",
    "portfolio_review": "portfolio_review",
    "earnings_preview": "earnings_preview",
}

# A recognizable metric/value noun — the thing that actually
# distinguishes "what is X's revenue?" (a lookup) from "what is
# happening with X?" (a research question that also happens to start
# with "what is"). 2026-09-22 fix: the original "what is/was/were/are
# ... ?" alternative below matched ANY question shaped that way,
# regardless of content — "What is happening with HDFC Bank?" and "What
# is the outlook for HDFC Bank?" both silently became factual_lookup
# purely off sentence shape, a real misrouting the six-mode integration
# audit's own preflight caught live. Metric words only — a bare "results"
# is deliberately excluded (too generic: "What are HDFC Bank's latest
# results?" reads as research-shaped, unlike "Q2 profit" or "market cap"
# which are single, specific values).
_METRIC_TERMS = (
    r"revenue|profit|earnings|eps|market\s+cap(?:italization)?|"
    r"net\s+income|ebitda|turnover|dividend|npa|book\s+value|sales"
)

_FACTUAL_RE = re.compile(
    r"^\s*what\s+(?:was|is|were|are)\b(?=.{0,80}?\b(?:" + _METRIC_TERMS + r")\b).{0,80}\?\s*$|"
    r"\bhow\s+much\b|\bhow\s+many\b|"
    r"\bq[1-4]\s+(?:revenue|profit|earnings|results)\b|"
    r"\b(?:revenue|profit|eps|market\s+cap)\s+(?:of|for)\b",
    re.IGNORECASE,
)


def _looks_factual(query: str) -> bool:
    """Deliberately conservative — a heuristic, not a classifier. False
    negatives fall back to direct_company_research (a safe default: that
    layout still shows the real answer text, just without factual_
    lookup's more compact framing), never a crash or a wrong-shaped
    schema requirement.

    The "what is/was/were/are ... ?" shape alone is NOT sufficient (see
    _METRIC_TERMS above) — it must also name a recognizable metric, so a
    generic research question phrased as a question ("what is happening
    with X", "what is the outlook for X", "what are the latest
    developments at X") stays direct_company_research rather than
    silently downgrading to the more compact factual_lookup framing."""
    return bool(_FACTUAL_RE.search(query or ""))


def classify_ui_mode(
    *, specialist_kind: str | None, intent_data: dict | None, entities: dict | None, query: str,
) -> str:
    """Pure function — no I/O, no new classification signal beyond what
    the caller already computed. Called once, in pipeline.py's
    _assemble_response, after intent_data/entities/specialist_kind are
    already resolved; never re-derives them. See this module's own
    docstring for the exact priority order and why it changed."""
    intent_data = intent_data or {}
    entities = entities or {}
    intent = intent_data.get("intent", "general")
    holding = intent_data.get("holding")
    target = intent_data.get("target")

    # 1. Comparison/switch semantics.
    if specialist_kind == "comparison":
        # A genuine 3+-company comparison-shaped query (decision_intent.py's
        # own 3-way regex only ever threads 2 of the N resolved names
        # through as holding/target — see intent.py's resolve_comparison —
        # but entities.company_matches still carries the full resolved
        # set). Routed to its own explicit "not supported yet" mode
        # rather than silently entering company_comparison and failing
        # only inside that assembler's own len(core.companies) != 2 check
        # (2026-09-22, intent-coverage audit).
        company_count = len(entities.get("company_matches") or [])
        if company_count >= 3:
            return "multi_company_comparison"
        if holding and target and intent in SWITCH_LIKE_INTENTS:
            return "switch_analysis"
        return "company_comparison"

    # 2. Explicit news_reaction — must win over the generic sector
    # heuristic (step 6): a sector word inside an event-shaped question
    # ("Banking sector just reported stronger credit growth — what is
    # the impact?") is still a news-reaction query, not a sector-theme
    # one, regardless of which literal words it also contains.
    if intent == "news_reaction":
        return "event_impact"

    # 3. Explicit policy intent.
    if entities.get("policies"):
        return "policy_macro_impact"
    # 3b. Step 4A: a macro DRIVER (crude oil, the rupee) whose effect is asked about is a macro question even with no policy entity. Never when a company is resolved: a company question
    # stays a company question (policy_macro_impact would also unlock the market-wide engine verdict, which must not appear next to a company answer).
    if not entities.get("companies") and macro_driver(query):
        return "policy_macro_impact"

    # 4. Explicit unsupported intent — a real, named classification,
    # not a coarse fallback.
    if intent in _UNSUPPORTED_INTENT_UI_MODE:
        return _UNSUPPORTED_INTENT_UI_MODE[intent]

    # 5. Factual lookup.
    if _looks_factual(query):
        return "factual_lookup"

    # 6. Generic specialist (sector) — only reached once nothing more
    # specific above matched.
    if specialist_kind == "sector":
        return "sector_theme_research"

    # 7. Default.
    return "direct_company_research"
