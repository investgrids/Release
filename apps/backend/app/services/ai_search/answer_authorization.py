"""
Gate B: post-model answer authorization.

Model generation is not an authorized answer. The live CR2 answer (Step 3.3b) returned `claim_sources: []` while stating 17 factual-looking claims plus invented dates and figures, and
nothing stopped it from being shown. This gate promotes the claim-source validator from a diagnostic to a publication check, for generated research answers:

  * factual sentences exist but the model returned no usable claim_sources            -> claim_sources_missing
  * any claim with no source / an unknown ID / sources that cannot support its scope   -> no_source, unknown_source, ineligible_sources
  * a claim restating an event premise that no evidence established                    -> premise_unsupported
  * a claim the model listed that is not in its answer                                 -> claim_not_in_answer
  * a factual sentence no claim covers                                                 -> uncovered_factual_sentences
  * a date or figure anywhere in the public text (timeline, scenarios, insights...)
    that neither the evidence nor the question contains                                -> unsupported_figures

Any reason means the generation is NOT shown. It is not repaired by another model, not stripped sentence by sentence, and no citation is invented. The caller returns a deterministic
response and the rejected generation is retained internally (REJECTED_GENERATIONS, and an internal field the finalizer strips) for diagnostics.

Not applied to educational/explanation questions: they carry no company evidence by design and need their own contract (a separate step).
"""
from __future__ import annotations

import json
import time
from collections import deque

import structlog

from app.services.ai_search import claim_sources as CS
from app.services.ai_search import figures as figures_mod

log = structlog.get_logger(__name__)

# In-process ring buffer of the most recent rejected generations: {response_id, query, reasons, generation, evidence_index, at}. Diagnostics only; never serialized to a client.
REJECTED_GENERATIONS: deque = deque(maxlen=50)


def evidence_corpus(evidence) -> str:
    """The text a generated figure or date may be grounded in. When the pipeline has told the bundle which prompt it was rendered into (prompt_kind), this is EXACTLY the model-visible
    evidence (EvidenceBundle.visible_text): nothing the model was not shown, such as hidden ranked items, summaries or item dates the prompt omits, can authorize a claim.
    A bundle with no prompt_kind (tests, offline tools) keeps the legacy everything-internal corpus."""
    if getattr(evidence, "prompt_kind", None):
        return evidence.visible_text()
    parts: list[str] = list(evidence.context_lines or [])
    for e in evidence.events:
        parts += [str(e.get("title") or ""), str(e.get("summary") or ""), str(e.get("event_date") or ""), str(e.get("published_at") or ""), str(e.get("date") or "")]
    for n in evidence.news:
        parts += [str(n.get("headline") or ""), str(n.get("summary") or ""), str(n.get("published_at") or "")]
    for a in evidence.announcements or []:
        parts += [str(a.get("subject") or ""), str(a.get("category") or ""), str(a.get("announcement_date") or "")]
    for p in evidence.policies:
        parts += [str(p.get("title") or ""), str(p.get("summary") or "")]
    for h in evidence.similar_historical or []:
        parts += [str(h.get("title") or h.get("event") or ""), str(h.get("date") or "")]
    parts += [json.dumps(evidence.valuation, default=str), json.dumps(evidence.sector_rows, default=str), json.dumps(evidence.macro_indices, default=str), str(evidence.vix_level)]
    return " ".join(parts)


def authorize(ai: dict, evidence, entities: dict, universe: list[dict], query: str) -> dict:
    plan = getattr(evidence, "plan_kind", None)
    if plan in (None, "explanation"):
        return {"applicable": False, "authorized": True, "reasons": [], "claim_validation": None, "unsupported_figures": []}
    index = evidence.index()
    cv = CS.validate_claim_sources(ai.get("claim_sources"), index, ai, entities, universe, getattr(evidence, "premise", None))
    facts = CS.factual_sentences(ai)
    figures = figures_mod.unsupported_figures(ai, evidence_corpus(evidence), query)
    reasons: list[str] = []
    if cv["status"] == "not_provided":
        if facts:
            reasons.append("claim_sources_missing")
    elif cv["status"] == "problems":
        seen: list[str] = []
        for c in cv["claims"]:
            for p in c.get("problems", []):
                code = p.split(":")[0].strip()
                if code == "malformed entry (needs a claim string and a sources list)":
                    code = "malformed_claim_source"
                if code not in seen:
                    seen.append(code)
        reasons += seen
        if cv.get("uncovered"):
            reasons.append("uncovered_factual_sentences")
    if figures:
        reasons.append("unsupported_figures")
    return {"applicable": True, "authorized": not reasons, "reasons": reasons, "claim_validation": {"status": cv["status"], "summary": cv["summary"]},
            "factual_sentences": len(facts), "unsupported_figures": figures}


def public_summary(auth: dict) -> dict:
    """What the response may carry publicly about a decision: the outcome and reason CODES with counts, never the withheld content."""
    return {"applicable": auth.get("applicable", False), "authorized": auth["authorized"], "reasons": list(auth["reasons"]),
            "unsupported_figure_count": len(auth.get("unsupported_figures") or []), "factual_sentences": auth.get("factual_sentences")}


def rejection_message(auth: dict) -> tuple[str, str]:
    """(title, body) shown instead of a rejected generation. Neutral wording: no verdict, no recommendation language, no content of the withheld answer."""
    return ("This analysis couldn't be verified",
            "The analysis that was generated included statements MarketRipple's retrieved evidence doesn't support, such as specific figures or dates, or company facts without a "
            "traceable source, so it isn't being shown. The evidence that was found is listed below.")


def remember(response_id: str, query: str, auth: dict, generation: dict, evidence_index: list[dict]) -> None:
    REJECTED_GENERATIONS.append({"response_id": response_id, "query": query, "reasons": list(auth["reasons"]), "generation": generation, "evidence_index": evidence_index, "at": time.time()})
    log.warning("ai_search_v3.answer_not_authorized", response_id=response_id, query=query[:80], reasons=auth["reasons"], factual_sentences=auth.get("factual_sentences"),
                unsupported_figures=len(auth.get("unsupported_figures") or []))
