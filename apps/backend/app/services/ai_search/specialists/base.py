"""
Shared building blocks for the 3 Phase 1 specialists (company, sector,
comparison). Each specialist builds its own prompt (nested schema — see
schema.py's module docstring for why) and calls `parse_specialist_json` on
the raw LLM response — identical JSON-fence-stripping + regex-salvage +
graceful-degrade pattern V2 already uses (ai_search_service.py:2180-2234),
reused verbatim so a truncated/malformed response degrades exactly the way
V2's does today, not a new failure mode. `parse_specialist_json` also
flattens a successfully-parsed nested response back to the internal flat
shape immediately — every caller downstream of a specialist's run() only
ever sees the flat shape, nested or not.
"""
from __future__ import annotations

import json
import re

import structlog

from app.services.ai_search.date_context import current_date_context
from app.services.ai_search.schema import flatten_nested

log = structlog.get_logger(__name__)


def parse_specialist_json(raw: str, query: str) -> tuple[dict, bool]:
    """Returns (parsed_dict, was_degraded) — parsed_dict is always the FLAT
    shape (flatten_nested applied), regardless of whether the LLM's raw JSON
    was the new nested groups or (via the degraded path) the flat fallback."""
    parsed: dict = {}
    if raw:
        try:
            clean = raw.strip()
            if clean.startswith("```"):
                clean = re.sub(r"^```(?:json)?\s*", "", clean)
                clean = re.sub(r"\s*```$", "", clean).strip()
            parsed = json.loads(clean)
        except json.JSONDecodeError:
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            if m:
                try:
                    parsed = json.loads(m.group())
                except Exception:
                    pass
            if not parsed:
                # ASCII-safe slice for the log line — structlog's default
                # renderer inherits the host's stdout encoding, which is
                # cp1252 (not UTF-8) in a plain Windows console; a raw rupee
                # sign or other non-Latin-1 character here would otherwise
                # crash the *logging call itself* while handling a parse
                # failure, masking the real error under a UnicodeEncodeError.
                log.warning("ai_search_v3.json_parse_fail", raw=raw[:300].encode("ascii", "replace").decode())
    else:
        # P5 Stage 4 — mirrors V2's ai_search.degraded_capacity distinction
        # (ai_search_service.py). Previously this branch was silent and
        # indistinguishable from a parse failure: `raw` empty means every
        # provider tier was exhausted before any text came back (a capacity
        # problem), not "got text back, couldn't parse it as JSON" — found
        # live during P5 Stage 3's regression run (ai.all_providers_failed
        # followed by a response mislabeled degraded_reason=parse_failure).
        log.warning("ai_search_v3.degraded_capacity", query=query[:120])

    if parsed:
        return flatten_nested(parsed), False
    degraded = degraded_response(query)
    # P5 Stage 4: carries the real cause through to pipeline.py's
    # _assemble_response, which previously hardcoded "parse_failure"
    # regardless of whether the LLM ever returned any text at all.
    degraded["_degraded_reason"] = "capacity" if not raw else "parse_failure"
    return degraded, True


def degraded_response(query: str) -> dict:
    """Same generic fallback shape as V2 (ai_search_service.py:2202-2233),
    already in the flat internal shape (this path never goes through
    flatten_nested — it's a synthetic default, not LLM output to translate)."""
    return {
        "degraded": True,
        # 2026-09-23 fix: previously interpolated the raw query verbatim
        # into both of these fields. Both are scanned by safety_gate.py's
        # advisory-language check (they're the two "answer"-shaped
        # _SAFETY_FIELDS), which has no way to distinguish an echoed USER
        # question from generated assistant analysis — a query merely
        # containing an advisory-shaped phrase ("...continue holding BEL
        # or switch to HAL?") tripped the scanner on the user's own words,
        # not anything this system generated, and silently overwrote the
        # real degraded_reason ("capacity") with "recommendation_language_
        # violation" (see response_finalize.py's now-immutable-original-
        # reason fix for the other half of this incident). The query is
        # already shown verbatim in the page's own heading, so repeating
        # it here added nothing besides this risk.
        "summary": "Market intelligence analysis for this question. Analysis based on real-time database events and news.",
        "bottom_line": (
            "There isn't enough freshly generated analysis to answer this question with confidence right now "
            "— the synthesis step didn't complete. Try rephrasing the question or checking back shortly."
        ),
        "what_happened": "A significant market development has been identified related to the queried topic.",
        "why_it_happened": "Multiple macro, policy, and sector-specific factors are driving this development.",
        "immediate_impact": "Near-term markets are reacting to this development with sector-specific movement.",
        "medium_term": "The 3-12 month outlook depends on policy execution and global macro environment.",
        "long_term": "Structural implications are broadly positive for India's capital markets.",
        "what_priced_in": "Insufficient data to assess current positioning — treat any near-term move as unconfirmed.",
        "risks": ["Execution risk", "Global headwinds", "Regulatory uncertainty"],
        "opportunities": ["Sector rotation", "Infrastructure capex", "Export growth"],
        "key_drivers": [],
        "confidence": 40, "sentiment": "neutral",
        "insights": [
            {"icon": "\U0001F4CA", "title": "Market Overview", "summary": "Current market conditions reflect mixed global and domestic signals with selective sector strength."},
            {"icon": "\U0001F3DB️", "title": "Policy Framework", "summary": "Government policy remains focused on infrastructure, manufacturing, and economic growth enablement."},
            {"icon": "\U0001F3C6", "title": "Sector Leaders", "summary": "Infrastructure and defence sectors are well positioned to outperform peers in this environment."},
            {"icon": "⚠️", "title": "Risk Watch", "summary": "Monitor global commodity prices, currency movements, and domestic fiscal deficit trajectory."},
        ],
        "companies": [], "sectors": [], "timeline": [],
        "follow_up_questions": ["Which sectors benefit most?", "What is the timeline?", "Key risks?", "Historical precedents?"],
        "investment_verdict": {
            "rating": "Neutral", "direction": "neutral", "confidence": 40,
            "horizon": "6-12 months", "top_picks": [],
            "risks": ["Macro uncertainty"], "catalysts": ["Policy clarity"],
            "opportunity_score": 50,
        },
        "scenarios": {}, "monitoring": {"items": []},
        "decision_engine_v2": {
            "verdict_scale": "Neutral", "why": "Synthesis step did not complete.",
            "what_changes_the_view": [], "what_invalidates_the_thesis": [],
        },
        "timeline_intelligence": {}, "opportunity_risk_matrix": {}, "ai_conclusion": {},
    }


# Phase 1D fix: prioritize the investment conclusion, frame everything else
# as secondary. Appended to every specialist prompt right before the JSON
# schema itself, so it's the model's last instruction before it starts
# generating — the position most likely to actually shape output order/effort.
PRIORITY_INSTRUCTIONS = (
    "PRIORITY ORDER — read before generating the JSON below:\n"
    "1. \"investment\" and \"evidence\" are the answer: sourced, specific, limited to what the evidence supports.\n"
    "2. \"claim_sources\" is part of the answer, not an extra: every factual sentence needs its verbatim entry.\n"
    "3. \"companies\" and \"sectors\" name the entities and say, in one grounded sentence each, how they relate to the question.\n"
    "4. \"risks\", \"timeline\" and \"extras\" stay short. Leave a field empty rather than fill it with anything the evidence does not support.\n"
)

# Shared instruction footer every specialist appends — the research-framing
# rule is load-bearing (V2 has real regression history here: never let the
# model say Buy/Sell/Hold) so it's centralized rather than copy-pasted 3x.
# References the NESTED field paths since that's the shape the model
# actually generates (flatten_nested renames these on the way out).
def research_framing_rules(outlook_labels: list[str] | None = None) -> str:
    """Framing rules for every specialist prompt. `outlook_labels` is kept for call-site compatibility: since Step 3.4D-3 the model is not asked for a rating, so no label list is shown."""
    return (
        f'- {current_date_context()}\n'
        "- This is a RESEARCH platform, not an advisory one. Never say Buy, Sell, Hold, Strong Buy, Strong Sell, Accumulate or Reduce anywhere, and do not give a verdict, rating, direction, "
        "sentiment, confidence, probability, score, scenario, winner, preference or recommendation: those are not part of your output.\n"
        '- "companies" must ONLY include real, listed NSE equities with a direct, specific connection to this exact query, never a government body, ministry or unlisted entity. '
        'Each entry has only "symbol", "name" and a one-sentence "reason" grounded in the evidence.\n'
        '- Every company named in "investment.summary"/"investment.bottom_line" must also appear in the "companies" list, and vice versa.\n'
        + _claim_rules()
    )


def premise_note(evidence) -> str:
    """The unverified-event notice for the prompt, tolerant of an evidence object that predates the premise check (tests use minimal stand-ins)."""
    fn = getattr(evidence, "premise_notice", None)
    return fn() if callable(fn) else ""


GROUNDING_RULES = (
    "- GROUNDING: use ONLY facts, numbers, dates and events that appear in the evidence lists and context above. Do not use outside knowledge to supply company facts, financial figures, "
    "dates, events, forecasts, peer comparisons or market conditions. If the supplied evidence cannot support a requested factual conclusion, state plainly that it cannot be established "
    "from the available MarketRipple evidence instead of answering from memory. Never invent earnings dates or scenario figures. This is defense in depth: an answer whose factual "
    "claims cannot be traced to the evidence is withheld."
)


def _claim_rules() -> str:
    from app.services.ai_search.schema import CLAIM_SOURCES_RULES, COMPOSITION_RULES
    return GROUNDING_RULES + "\n" + COMPOSITION_RULES + "\n" + CLAIM_SOURCES_RULES
