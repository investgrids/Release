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

    if parsed:
        return flatten_nested(parsed), False
    return degraded_response(query), True


def degraded_response(query: str) -> dict:
    """Same generic fallback shape as V2 (ai_search_service.py:2202-2233),
    already in the flat internal shape (this path never goes through
    flatten_nested — it's a synthetic default, not LLM output to translate)."""
    return {
        "degraded": True,
        "summary": f"Market intelligence analysis for: {query}. Analysis based on real-time database events and news.",
        "bottom_line": (
            f"There isn't enough freshly generated analysis to answer “{query}” with confidence right now "
            "— the underlying event and news data is available below, but the synthesis step didn't complete. "
            "Try rephrasing the question or checking back shortly."
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
    "1. Get \"investment\", \"decision\", and \"evidence\" right first — these are the actual "
    "answer to the user's question. A sharp, specific, well-reasoned investment conclusion "
    "matters more than any other field in this schema.\n"
    "2. \"companies\" and \"sectors\" come next — the concrete entities backing the conclusion.\n"
    "3. \"timeline\" and \"risks\" matter, but briefly and specifically beats exhaustively.\n"
    "4. \"extras\" (insights/scenarios/monitoring/follow_up_questions) is the LOWEST priority. "
    "If you are running low on reasoning budget, abbreviate or thin out \"extras\" first — "
    "NEVER sacrifice the quality of \"investment\"/\"decision\"/\"evidence\" to fit \"extras\" in.\n"
)

# Shared instruction footer every specialist appends — the research-framing
# rule is load-bearing (V2 has real regression history here: never let the
# model say Buy/Sell/Hold) so it's centralized rather than copy-pasted 3x.
# References the NESTED field paths since that's the shape the model
# actually generates (flatten_nested renames these on the way out).
def research_framing_rules(outlook_labels: list[str]) -> str:
    return (
        f'- "investment.rating" MUST be exactly one of these values, nothing else: '
        f'{", ".join(f'"{l}"' for l in outlook_labels)}. '
        "This is a RESEARCH platform, not an advisory one — never say Buy, Sell, Hold, "
        "Strong Buy, Strong Sell, Accumulate, or Reduce anywhere in any field.\n"
        '- "decision.investor_action_note" must be phrased as what to watch for or '
        "consider — never a direct instruction to buy/sell/hold.\n"
        '- "investment.verdict_scale" and "decision.current_view" must agree in '
        "direction with \"investment.direction\" — do not produce a bullish verdict_scale "
        "alongside a bearish direction, or vice versa.\n"
        '- "extras.scenarios" probabilities (bull + base + bear) must sum to exactly 100.\n'
        '- "companies" must ONLY include real, listed NSE equities with a direct, specific, '
        "mechanistic connection to this exact query — never a government body, ministry, "
        "or unlisted entity."
    )
