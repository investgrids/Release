"""
The Phase 1 consolidated specialist JSON contract.

Design note (2026-07-26, post-benchmark iteration): the LLM-facing schema is
NESTED (investment / decision / evidence / companies / sectors / timeline /
risks / extras) per the approved Phase 1C fix — a flat ~25-key object proved
less reliable to generate correctly than a handful of grouped sub-objects
(verified live: malformed JSON spread across many categories in the first
Golden 200 v3 run, not concentrated in one weak prompt). Everything
DOWNSTREAM of parsing (pipeline.py, validation.py, postprocess.py) is
UNCHANGED and still operates on the original flat shape — `flatten_nested`
below is the one seam that translates nested LLM output back into that flat
shape immediately after parsing, so the reliability experiment is contained
to "what we ask the model to produce," not a rewrite of already-tested
downstream code.

`evidence_score` and `confidence_breakdown` are deliberately NOT part of this
schema — they're computed server-side in postprocess.py from the real
EvidenceBundle and confidence_service.py, never trusted from raw LLM output.
"""
from __future__ import annotations

# 6-point Decision Engine v2 verdict scale (distinct from investment_verdict's
# existing 8-label research-framed enum, which stays unchanged — see plan's
# Open Risks §1 on the decision_engine_v2 vs decision_engine.py naming note).
VERDICT_SCALE = [
    "Strong Positive", "Positive", "Neutral", "Cautious", "Negative", "Strong Negative",
]

# Required top-level keys on the FLATTENED shape (post-flatten_nested) that
# every specialist response must have before it's considered parseable —
# anything missing routes to the same graceful degraded-template fallback
# V2 already uses (ai_search_service.py:2200-2219).
REQUIRED_KEYS = (
    "summary", "bottom_line", "confidence", "sentiment",
    "companies", "sectors", "investment_verdict",
)

SCHEMA_VERSION = "v3.0"


def is_well_formed(parsed: dict) -> bool:
    """Structural check only — does this look like a specialist response at
    all? Field-level correctness (probabilities summing to 100, no
    fabricated tickers, etc.) is validation.py's job, run after this."""
    return isinstance(parsed, dict) and all(k in parsed for k in REQUIRED_KEYS)


def flatten_nested(nested: dict) -> dict:
    """Translates the nested LLM-facing schema back into the flat internal
    shape pipeline.py/validation.py/postprocess.py already expect — the one
    seam of this redesign, so nothing downstream of a specialist's run()
    needed to change. Missing groups/fields degrade to safe defaults rather
    than raising, since a partially-malformed nested response should still
    salvage whatever groups DID parse correctly."""
    inv = nested.get("investment") or {}
    dec = nested.get("decision") or {}
    evd = nested.get("evidence") or {}
    tl = nested.get("timeline") or {}
    rsk = nested.get("risks") or {}
    ext = nested.get("extras") or {}

    flat = {
        "summary": inv.get("summary", ""),
        "bottom_line": inv.get("bottom_line", inv.get("summary", "")),
        "confidence": inv.get("confidence", 50),
        "confidence_self_rating": inv.get("confidence_self_rating", 5),
        "sentiment": inv.get("sentiment", "neutral"),
        "what_happened": evd.get("what_happened", ""),
        "why_it_happened": evd.get("why_it_happened", ""),
        "immediate_impact": evd.get("immediate_impact", ""),
        "medium_term": evd.get("medium_term", ""),
        "long_term": evd.get("long_term", ""),
        "what_priced_in": evd.get("what_priced_in", ""),
        "key_drivers": evd.get("key_drivers", []),
        "risks": rsk.get("risks", []),
        "opportunities": rsk.get("opportunities", []),
        "companies": nested.get("companies", []),
        "sectors": nested.get("sectors", []),
        "investment_verdict": {
            "rating": inv.get("rating", "Neutral"),
            "direction": inv.get("direction", "neutral"),
            "confidence": inv.get("confidence", 50),
            # P5 Stage 3: no hardcoded fallback here anymore — None when the
            # LLM didn't state one is the honest intermediate value; a real
            # deterministic horizon gets computed and injected in
            # pipeline.py's _assemble_response, which has the evidence/VIX/
            # historical signals this flattening step doesn't.
            "horizon": inv.get("horizon"),
            "top_picks": ext.get("top_picks", []),
            "risks": rsk.get("risks", [])[:2],
            "catalysts": dec.get("what_changes_the_view", [])[:2],
            # P5 Stage 3: was `inv.get("confidence", 50)` — silently aliased
            # to the confidence field, never independently computed. Real
            # value (or None when no live Opportunity Radar match exists)
            # computed and injected in pipeline.py's _assemble_response.
            "opportunity_score": None,
        },
        "follow_up_questions": ext.get("follow_up_questions", []),
        "timeline": tl.get("milestones", []),
        "insights": ext.get("insights", []),
        "scenarios": ext.get("scenarios", {}),
        "monitoring": ext.get("monitoring", {"items": []}),
        "decision_engine_v2": {
            "verdict_scale": inv.get("verdict_scale", "Neutral"),
            "why": inv.get("why", ""),
            "what_changes_the_view": dec.get("what_changes_the_view", []),
            "what_invalidates_the_thesis": dec.get("what_invalidates_the_thesis", []),
            "explain_why_not": dec.get("explain_why_not"),
        },
        "timeline_intelligence": {
            "immediate": tl.get("immediate", ""),
            "one_week": tl.get("one_week", ""),
            "one_to_three_months": tl.get("one_to_three_months", ""),
            "six_to_twelve_months": tl.get("six_to_twelve_months", ""),
            "one_to_three_years": tl.get("one_to_three_years", ""),
        },
        "opportunity_risk_matrix": {
            "opportunity": rsk.get("opportunity_matrix", {}),
            "risk": rsk.get("risk_matrix", {}),
        },
        "ai_conclusion": {
            "current_view": dec.get("current_view", ""),
            "reason": dec.get("reason", ""),
            "biggest_opportunity": dec.get("biggest_opportunity", ""),
            "biggest_risk": dec.get("biggest_risk", ""),
            "investor_action_note": dec.get("investor_action_note", ""),
        },
    }
    # decision_intelligence (comparison specialist only) is already a
    # reasonably-nested, proven-since-V2 structure — pass through unchanged
    # rather than folding it into the new grouping.
    if "decision_intelligence" in nested:
        flat["decision_intelligence"] = nested["decision_intelligence"]
    return flat


# ── Shared JSON schema fragments (nested, nest-group building blocks) ───────
# CORE groups (investment/decision/evidence/companies/sectors) are what the
# model must get right; EXTRAS is explicitly framed as lower-priority in the
# prompt text itself (see specialists/base.py's PRIORITY_INSTRUCTIONS) —
# this is the Phase 1D fix: ask for the investment conclusion first,
# everything else is secondary.

# NOTE: these fragments use a literal __TOKEN__ placeholder + .replace(), not
# str.format() — the strings are full of literal JSON braces, and mixing
# those with .format()'s own {..} placeholder syntax is a real footgun (a
# lone "{" anywhere in the template raises at format-time). .replace() with
# an unambiguous token sidesteps that entirely.
INVESTMENT_GROUP = """  "investment": {
    "summary": "2-3 sentence executive summary specific to the query",
    "bottom_line": "MAX 120 WORDS. ONE paragraph answering ONLY this exact question, directly and specifically.",
    "confidence": 78,
    "confidence_self_rating": 7,
    "sentiment": "bullish",
    "rating": "<one of the 8 rating labels listed in the rules below>",
    "direction": "bullish",
    "horizon": "12-18 months",
    "verdict_scale": "<EXACTLY one of these 6 words/phrases, a SEPARATE scale from 'rating' above: __VERDICT_SCALE_OPTIONS__>",
    "why": "1-2 sentences — the core reasoning behind verdict_scale"
  },"""

DECISION_GROUP = """  "decision": {
    "what_changes_the_view": ["specific event/data point 1", "specific event/data point 2"],
    "what_invalidates_the_thesis": ["specific condition 1", "specific condition 2"],
    "current_view": "1 phrase, mirrors investment.verdict_scale",
    "reason": "1 sentence",
    "biggest_opportunity": "1 sentence, specific",
    "biggest_risk": "1 sentence, specific",
    "investor_action_note": "1 sentence, framed as what to watch for/consider — never 'Buy'/'Sell'/'Hold'"__EXPLAIN_WHY_NOT__
  },"""

DECISION_GROUP_EXPLAIN_WHY_NOT = """,
    "explain_why_not": {"alternative": "the non-winning entity's name", "reason_rejected": "1-2 sentences, specific"}"""


def render_investment_group() -> str:
    return INVESTMENT_GROUP.replace("__VERDICT_SCALE_OPTIONS__", " | ".join(VERDICT_SCALE))


def render_decision_group(is_comparison: bool = False) -> str:
    extra = DECISION_GROUP_EXPLAIN_WHY_NOT if is_comparison else ""
    return DECISION_GROUP.replace("__EXPLAIN_WHY_NOT__", extra)

EVIDENCE_GROUP = """  "evidence": {
    "what_happened": "1 factual sentence",
    "why_it_happened": "1 contextual sentence",
    "immediate_impact": "1 sentence on near-term market effect",
    "medium_term": "1 sentence on 3-12 month outlook",
    "long_term": "1 sentence on structural implications",
    "what_priced_in": "1-2 sentences: has the market already priced this in?",
    "key_drivers": [
      {"icon": "procurement", "title": "2-4 word driver name", "explanation": "1 sentence mechanism", "confidence": 92},
      {"icon": "policy", "title": "2-4 word driver name", "explanation": "1 sentence mechanism", "confidence": 87}
    ]
  },"""

TIMELINE_GROUP = """  "timeline": {
    "milestones": [
      {"date": "Near-term date", "title": "First milestone", "description": "What happens"},
      {"date": "Later date", "title": "Second milestone", "description": "What happens next"}
    ],
    "immediate": "1 sentence — right now / today",
    "one_week": "1 sentence — this week",
    "one_to_three_months": "1 sentence",
    "six_to_twelve_months": "1 sentence",
    "one_to_three_years": "1 sentence"
  },"""

RISKS_GROUP = """  "risks": {
    "risks": ["specific risk 1", "specific risk 2", "specific risk 3"],
    "opportunities": ["specific opportunity 1", "specific opportunity 2"],
    "opportunity_matrix": {"high": ["item"], "medium": ["item"], "low": ["item"]},
    "risk_matrix": {"high": ["item"], "medium": ["item"], "low": ["item"]}
  },"""

# EXTRAS — explicitly the lowest-priority group; see PRIORITY_INSTRUCTIONS
# in specialists/base.py for the prompt text that tells the model it's fine
# to abbreviate this group under time/token pressure.
EXTRAS_GROUP = """  "extras": {
    "insights": [
      {"icon": "<single emoji>", "title": "4-6 words", "summary": "max 20 words"},
      {"icon": "<single emoji>", "title": "4-6 words", "summary": "max 20 words"}
    ],
    "scenarios": {
      "bull": {"probability": 30, "outcome": "...", "key_drivers": ["..."], "confidence": 65},
      "base": {"probability": 50, "outcome": "...", "key_drivers": ["..."], "confidence": 70},
      "bear": {"probability": 20, "outcome": "...", "key_drivers": ["..."], "confidence": 60}
    },
    "monitoring": {"items": [{"label": "Quarterly Results", "importance": "critical", "why_it_matters": "...", "frequency": "Every 3 months"}]},
    "follow_up_questions": ["Specific follow-up 1?", "Specific follow-up 2?"],
    "top_picks": ["SYMBOL1", "SYMBOL2"]
  }"""

MONITORING_COUNT_NOTE = (
    '- "extras.monitoring.items": 5-8 items when you have token budget to spare — cover earnings, '
    "FII/DII activity, sector policy, commodity prices, interest rates, promoter holding, debt "
    "levels, order book as relevant. This is an EXTRAS field — never sacrifice the investment/"
    "decision/evidence groups to pad this one out."
)
