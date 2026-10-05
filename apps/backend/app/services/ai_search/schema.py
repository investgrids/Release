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

import re

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


def _present(block: dict) -> dict:
    """Keep only the entries the model actually supplied; an all-empty block becomes {}."""
    return {k: v for k, v in block.items() if v not in (None, "", [], {})}


def _obs_key(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9%.]+", " ", text.lower()).split())


def render_observations(observations, legacy_what_happened, other_claims):
    """Step 3.4G.6: factual observations are generated ONCE ({"text", "sources"}); code renders them into the public factual prose (`what_happened`) and into `claim_sources`, so a claim can never be
    listed-but-unwritten or written-but-unlisted. Nothing is validated, repaired or dropped here beyond exact-duplicate merging: an observation with a wrong figure, an unknown source or no source
    flows through unchanged and is rejected by Gate B exactly as before. `other_claims` are the model's claim_sources for factual sentences in OTHER fields; an entry that repeats an observation is merged
    into it. Without an `observations` list (an older-shape response) the legacy `what_happened` prose and `claim_sources` pass through untouched."""
    if not isinstance(observations, list):
        return (legacy_what_happened if isinstance(legacy_what_happened, str) else ""), other_claims
    merged: dict[str, dict] = {}
    for o in observations:
        text = o.get("text") if isinstance(o, dict) else None
        if not isinstance(text, str) or not text.strip():
            continue                                                  # carries no claim: nothing to render or list
        src = o.get("sources")
        src = [str(s) for s in src] if isinstance(src, list) else ([str(src)] if src else [])
        k = _obs_key(text)
        if k in merged:
            merged[k]["sources"] += [s for s in src if s not in merged[k]["sources"]]
        else:
            merged[k] = {"claim": text.strip(), "sources": list(src)}
    obs_claims = list(merged.values())
    extra = [c for c in (other_claims if isinstance(other_claims, list) else []) if not (isinstance(c, dict) and isinstance(c.get("claim"), str) and _obs_key(c["claim"]) in merged)]
    return " ".join(c["claim"] for c in obs_claims), obs_claims + extra


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

    what_happened, claim_sources = render_observations(evd.get("observations"), evd.get("what_happened"), nested.get("claim_sources", []))

    flat = {
        "summary": inv.get("summary", ""),
        "bottom_line": inv.get("bottom_line", inv.get("summary", "")),
        # Step 3.4D-3: the model is no longer asked for confidence, self-rating or sentiment, so an absent value is None (an unauthorized claim is never defaulted into a neutral one).
        "confidence": inv.get("confidence"),
        "confidence_self_rating": inv.get("confidence_self_rating"),
        "sentiment": inv.get("sentiment"),
        "what_happened": what_happened,
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
            "rating": inv.get("rating"),
            "direction": inv.get("direction"),
            "confidence": inv.get("confidence"),
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
        # claim-level source IDs the model attached to its factual sentences (see CLAIM_SOURCES_GROUP); validated against the evidence index in claim_sources.py
        "claim_sources": claim_sources,
        "timeline": tl.get("milestones", []),
        "insights": ext.get("insights", []),
        "scenarios": ext.get("scenarios", {}),
        "monitoring": ext.get("monitoring", {"items": []}),
        # Step 3.4D-3: these blocks are no longer part of the model contract. A block is present only if the model actually wrote something into it, otherwise it is {} (never a shell of empty
        # strings that would look like a generated claim).
        "decision_engine_v2": _present({
            "verdict_scale": inv.get("verdict_scale"),
            "why": inv.get("why"),
            "what_changes_the_view": dec.get("what_changes_the_view"),
            "what_invalidates_the_thesis": dec.get("what_invalidates_the_thesis"),
            "explain_why_not": dec.get("explain_why_not"),
        }),
        "timeline_intelligence": _present({
            "immediate": tl.get("immediate"),
            "one_week": tl.get("one_week"),
            "one_to_three_months": tl.get("one_to_three_months"),
            "six_to_twelve_months": tl.get("six_to_twelve_months"),
            "one_to_three_years": tl.get("one_to_three_years"),
        }),
        "opportunity_risk_matrix": _present({
            "opportunity": rsk.get("opportunity_matrix"),
            "risk": rsk.get("risk_matrix"),
        }),
        "ai_conclusion": _present({
            "current_view": dec.get("current_view"),
            "reason": dec.get("reason"),
            "biggest_opportunity": dec.get("biggest_opportunity"),
            "biggest_risk": dec.get("biggest_risk"),
            "investor_action_note": dec.get("investor_action_note"),
        }),
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
# Step 3.4D-3: the V2 model output contract carries only what the model has authority to publish (sourced prose). It is NOT asked for a rating, direction, sentiment, confidence, verdict scale,
# scenarios/probabilities, impact or outlook scores, a winner/preference, decision blocks, matrices or an AI conclusion: those are produced by code or not published (structured_authorization.py).
INVESTMENT_GROUP = """  "investment": {
    "summary": "SYNTHESIS: 1-2 hedged sentences saying what the observations in evidence.what_happened collectively suggest. No new figures, dates or events; no verdict or recommendation.",
    "bottom_line": "MAX 80 WORDS. Answers ONLY this exact question from those observations, limited to what the evidence supports, and says plainly where it is mixed or incomplete. No verdict, rating, direction or recommendation."
  },"""

DECISION_GROUP = ""      # removed from the model contract in Step 3.4D-3 (current view, action note, explain-why-not, view-changers are conclusions the model has no authority to publish)

DECISION_GROUP_EXPLAIN_WHY_NOT = """,
    "explain_why_not": {"alternative": "the non-winning entity's name", "reason_rejected": "1-2 sentences, specific"}"""


# Claim-level source IDs. The evidence lists in the prompt tag every item (E events, N news, P policies, A announcements, C context lines); the model must attach those IDs to
# each factual sentence so a claim can be traced to the item that supports it and checked for eligibility.
CLAIM_SOURCES_GROUP = """  "claim_sources": [
    {"claim": "one factual sentence copied EXACTLY from a field of your answer other than the observations", "sources": ["E1", "N2"]}
  ],"""

CLAIM_SOURCES_RULES = (
    '- "claim_sources": every sentence in your answer text outside "evidence.observations" (summary, bottom_line, why_it_happened, key_drivers explanations, risks, opportunities, companies reasons) that states a '
    "fact, number, date, order, announcement, result or comparison of figures needs ONE entry: copy the sentence EXACTLY (character for character) and list the evidence IDs "
    "(E = event, N = news, P = policy, A = announcement, C = context line) from the lists above that support it. Use only IDs that appear above and never invent one. "
    "CANONICAL CLAIMS: state each fact once. If you need it in more than one field, repeat the IDENTICAL sentence word for word; never restate it in different words, and never combine two claims "
    "or add a clause to a claimed sentence. Other fields may point back to it without new numbers or dates (for example: 'the valuation gap noted above'). "
    "A sentence that only says something is missing or not established (for example: 'recent operating results are not in the current evidence') is a limitation, not a fact: write it plainly, "
    "without the words announced, disclosed or filed. If no listed item supports a fact, do not state it. "
    "SCOPE: conclude only what the evidence covers. If it holds only valuation multiples for the compared companies, compare valuation and say plainly that operating results are not in the evidence; "
    "do not say which company is stronger, better or preferred overall. A stock-tips article, a filing by a different company, or a brand name inside another firm's name does not support a claim "
    "about the company or the sector."
)


# Step 3.4G.5: composition contract. SR2 showed the model can have the strongest evidence in front of it and still answer generically ("cannot be established"). This makes evidence utilization part of the
# contract: observations first (chosen from what is visible, by informativeness for THIS question), synthesis second (built only from those observations, hedged), prose and claims consistent in both
# directions. It names no expected fact: the model chooses from the visible evidence ids, so it keeps working when live evidence changes.
COMPOSITION_RULES = (
    '- COMPOSITION, observations first, synthesis second. '
    '(1) OBSERVATIONS: in "evidence.observations" list the most decision-relevant facts that the evidence lists above actually state, as separate entries: usually 3 to 5, fewer when the '
    "evidence holds fewer informative facts, none when it holds none. Each entry is one factual sentence reporting one fact from one or two listed items (a headline's reported fact, a live figure, a filing) "
    'with the ids of those items; the system publishes your observations as the factual part of the answer, so write each one only once and do not repeat it elsewhere. Choose by how informative an item is for THIS question: prefer concrete, quantified, dated or directional items over generic market commentary, and when items '
    "point in different directions include both. The lists are ordered by relevance. Do not pad, do not repeat a fact in different words, and do not state something because it is typical of the topic. "
    '(2) SYNTHESIS: "investment.summary" and "investment.bottom_line" answer the question using only those observations: one or two hedged sentences on what they collectively suggest (for example that '
    "the evidence is mixed or incomplete), with no new figure, date or event and no verdict, forecast, winner or recommendation. Refer to observations in words (for example "
    "'the earlier fall' or 'the positive external read-through'), not by repeating numbers. "
    '(3) CONSISTENCY: every factual sentence anywhere in your answer must be an observation or be listed in "claim_sources"; never put a new fact in the summary or bottom line, or in any other field, '
    "that is not an observation. "
    "(4) LIMITS: in a comparison describe each side only as far as the evidence covers it and never name a winner; for a single company report what the evidence says, not an outlook it does not state; "
    "for a macro question state a causal link only if a listed item states it; if the evidence cannot answer the question, say so briefly instead of filling space with unrelated facts."
)


def render_investment_group() -> str:
    return INVESTMENT_GROUP.replace("__VERDICT_SCALE_OPTIONS__", " | ".join(VERDICT_SCALE))


def render_decision_group(is_comparison: bool = False) -> str:
    return ""       # Step 3.4D-3: no decision group in the model contract

EVIDENCE_GROUP = """  "evidence": {
    "observations": [
      {"text": "one factual sentence stating one fact from the listed evidence", "sources": ["E1"]}
    ],
    "why_it_happened": "1 sentence tied to the evidence, or empty",
    "key_drivers": [
      {"icon": "valuation", "title": "2-4 word driver name", "explanation": "1 sentence grounded in the evidence; no new numbers or dates"}
    ]
  },"""

TIMELINE_GROUP = """  "timeline": {
    "milestones": []
  },"""      # milestones only for dated events that appear in the evidence; otherwise leave empty. Horizon narratives (timeline intelligence) are not part of the contract.

RISKS_GROUP = """  "risks": {
    "risks": ["grounded risk or evidence limitation, 1 sentence each (0-3)"],
    "opportunities": ["grounded opportunity, 1 sentence each (0-2)"]
  },"""

# EXTRAS — explicitly the lowest-priority group; see PRIORITY_INSTRUCTIONS
# in specialists/base.py for the prompt text that tells the model it's fine
# to abbreviate this group under time/token pressure.
EXTRAS_GROUP = """  "extras": {
    "monitoring": {"items": [{"label": "Quarterly Results", "importance": "critical", "why_it_matters": "...", "frequency": "Every 3 months"}]},
    "follow_up_questions": ["Specific follow-up 1?", "Specific follow-up 2?"]
  }"""

MONITORING_COUNT_NOTE = (
    '- "extras.monitoring.items": at most 3 items, each a thing to watch (what data would settle an open question in the evidence). No numbers, dates or forecasts that are not in the evidence.'
)
