"""
Refine Analysis — regenerates ONLY the decision layer (investment verdict +
decision engine + AI conclusion) when the user adjusts personal parameters
(horizon, risk tolerance, goal, portfolio size, ...) on an answer they
already have, instead of asking the question over again from scratch.

Deliberately reuses the REAL evidence context already gathered for the
original answer (see cache.py's set_snapshot/get_snapshot) rather than
re-running entity extraction, evidence collection, or enrichment — the
facts haven't changed, only how they should be weighed for this investor.
One small LLM call (investment + decision groups only, no companies/
sectors/timeline/risks/extras), so a refine is meant to be visibly faster
than a fresh search, not just conceptually "smaller."
"""
from __future__ import annotations

from app.services.ai_search.schema import VERDICT_SCALE, render_decision_group, render_investment_group
from app.services.ai_search.specialists.base import degraded_response, parse_specialist_json, research_framing_rules

REFINE_SYSTEM = (
    "You are MarketRipple's Refine Analysis engine. The user already received a full research "
    "answer and is now adjusting their personal investment parameters — re-derive ONLY the "
    "investment conclusion and decision reasoning for these NEW parameters, grounded strictly "
    "in the evidence already gathered below. Do not invent facts, companies, or events beyond "
    "what's given. Respond with valid JSON only. No markdown fences. No commentary."
)

MAX_TOKENS = 1800

# Keys the frontend may send; every value is optional — an unset parameter
# means "use a balanced default for that dimension," not "invalid request."
_PARAM_LABELS = {
    "horizon": "Investment horizon",
    "risk_tolerance": "Risk tolerance",
    "investment_goal": "Investment goal",
    "portfolio_size": "Portfolio size",
    "style": "Preference",
    "entry_mode": "Entry mode",
    "holder_status": "Position status",
}


def _humanize_params(params: dict) -> str:
    lines = [f"{label}: {params[key]}" for key, label in _PARAM_LABELS.items() if params.get(key)]
    return "\n".join(lines) if lines else "No specific preferences given — use balanced, general-investor defaults."


def build_prompt(original_query: str, evidence_context: str, companies: list[dict], is_comparison: bool, params: dict) -> str:
    from app.services.ai_search.regexes import _OUTLOOK_LABELS

    co_names = ", ".join(f"{c.get('symbol')} ({c.get('name')})" for c in companies[:5] if c.get("symbol")) or "none identified"
    investment_group = render_investment_group()
    decision_group = render_decision_group(is_comparison=is_comparison)

    return f"""Original research question: "{original_query}"
Companies already identified for this question: {co_names}

Real evidence already gathered for this question — ground your answer ONLY in this, do not
introduce anything beyond it:
{evidence_context[:6000] or "No additional evidence context was captured."}

The user has now specified these personal investment parameters and wants the conclusion
re-derived specifically for them:
{_humanize_params(params)}

Return ONLY this JSON (no fences, no extra keys):
{{
{investment_group}
{decision_group}
}}

CRITICAL RULES:
{research_framing_rules(_OUTLOOK_LABELS)}
- Every field must reflect the user's stated parameters above — e.g. a short horizon changes
  "investment.horizon" and the reasoning even if the underlying evidence is unchanged; a
  conservative risk tolerance should show up in "decision.what_invalidates_the_thesis" and
  "decision.investor_action_note", not just be acknowledged and ignored.
- "investment.verdict_scale" must be exactly one of: {" | ".join(VERDICT_SCALE)}.
- If the user specified a horizon above, "investment.horizon" MUST reflect THAT stated horizon,
  not a generic estimate independent of it — a user who said "Long-term (3+ years)" should see
  "3+ years" (or equivalent) in this field, not whatever horizon fits the evidence in isolation."""


async def run(
    original_query: str, evidence_context: str, companies: list[dict], is_comparison: bool, params: dict,
) -> tuple[dict, bool]:
    """Returns (flat_decision_dict, was_degraded) — same flat shape a full
    specialist's run() returns, just with only the investment_verdict /
    decision_engine_v2 / ai_conclusion fields meaningfully populated
    (flatten_nested defaults everything else to empty, which callers here
    are expected to ignore in favor of the original response's values)."""
    from app.services.ai_service import _call_with_fallback

    prompt = build_prompt(original_query, evidence_context, companies, is_comparison, params)
    raw = await _call_with_fallback(prompt, REFINE_SYSTEM, max_tokens=MAX_TOKENS, priority="interactive")
    return parse_specialist_json(raw, original_query)
