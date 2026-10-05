"""
The final public answer contract (Step 5). One place that says what a user may receive, applied last, in the finalizer, to every research and educational response (fresh, cached, any route).

What a response must make explicit (all in `answer_availability`, no parallel state):
  state                   available | limited_evidence | no_verified_evidence | temporarily_unavailable            (Step 4C, unchanged)
  kind                    research | partial_research | education | product_information | unavailable | temporarily_unavailable
  basis                   retrieved_evidence | market_data | education | none                                      (Step 4C)
  conclusion_authorized   True only when an authorized structured investment conclusion (a real rating) is present
  evidence_count          evidence items listed in the response                                                    (Step 4C)
  reason                  why it is limited or unavailable, a short public code                                    (Step 4C)
  scope                   full | partial | none: what was actually answered (partial = narrowed research, or a product question asking for detail the methodology does not publish)

Rules enforced here:
  * No public answer confidence exists. Every confidence field is null / "unscored" (the source also returns it unscored; this makes cached or saved responses obey the same rule).
  * No authorized conclusion means no verdict fields: rating "Not Applicable", direction null, confidence null, and no horizon or opportunity score that would imply one.
  * Internal diagnostics are not part of the public contract (see INTERNAL_DIAGNOSTICS).
"""
from __future__ import annotations

ANSWER_KINDS = ("research", "partial_research", "education", "product_information", "unavailable", "temporarily_unavailable")

# Gate, validation and timing details that exist for operations, tests and debugging, not for a user. None is read by the client. They stay on the internal pipeline result (and in logs) and are removed from
# the public serialization by the finalizer. `evidence_sufficiency` and `premise_check` explain a refusal in gate vocabulary; the public wording for the same refusal is `public_title` and `answer.summary`.
INTERNAL_DIAGNOSTICS = frozenset({
    "answer_authorization", "claim_validation", "structured_authorization", "timing", "evidence_sufficiency", "premise_check",
})
# Fields inside evidence_score that count rows or clusters in a universe the user cannot see (they include unlisted exchange filings).
INTERNAL_EVIDENCE_SCORE_KEYS = ("development_count", "corroborating_source_count")


def has_authorized_conclusion(result: dict) -> bool:
    """Mirrors the client's `hasAuthorizedVerdict`: a real rating, not "" or "Not Applicable"."""
    rating = ((result.get("investment_verdict") or {}).get("rating") or "").strip()
    return rating != "" and rating != "Not Applicable"


def answer_kind(result: dict, availability: dict) -> str:
    edu = result.get("education")
    if isinstance(edu, dict):
        return "product_information" if edu.get("kind") == "product_knowledge" else "education"
    state = availability.get("state")
    if state == "temporarily_unavailable":
        return "temporarily_unavailable"
    if state in ("no_verified_evidence", "limited_evidence"):
        return "unavailable"
    return "partial_research" if (result.get("conclusion_scope") or {}).get("partial") is True else "research"


def answer_scope(result: dict, kind: str) -> str:
    if kind in ("unavailable", "temporarily_unavailable"):
        return "none"
    if kind == "partial_research":
        return "partial"
    if kind in ("education", "product_information") and (result.get("education") or {}).get("beyond_published_detail"):
        return "partial"
    return "full"


_UNSCORED_BREAKDOWN = {"final_confidence": None, "level": "unscored"}
_UNSCORED_CONTRACT = {"status": "unscored", "score": None, "components": {"evidence_quality": None, "market_confirmation": None, "historical_similarity": None, "data_freshness": None}}


def project_result(result: dict) -> dict:
    """The result-level rules, applied BEFORE the canonical core is built so every presenter (the V3 dict, AEV2) derives from the same public-contract-conformant answer. Pure and idempotent. Only fields the
    response already carries are touched: nothing is added to a response that lacks them."""
    out = dict(result)
    if isinstance(out.get("answer"), dict) and ("confidence" in out["answer"] or "confidence_level" in out["answer"]):
        out["answer"] = {**out["answer"], "confidence": None, "confidence_level": "unscored"}
    if isinstance(out.get("confidence_data"), dict):
        out["confidence_data"] = {**out["confidence_data"], "level": "unscored", "score": None, "reasons": [], "breakdown": {}}
    if "confidence_breakdown" in out:
        out["confidence_breakdown"] = dict(_UNSCORED_BREAKDOWN)
    if "confidence" in out:
        out["confidence"] = {**_UNSCORED_CONTRACT, "components": dict(_UNSCORED_CONTRACT["components"])}
    if isinstance(out.get("investment_verdict"), dict):
        verdict = {**out["investment_verdict"], "confidence": None}
        if not has_authorized_conclusion(out):
            verdict.update(rating="Not Applicable", direction=None, horizon=None, opportunity_score=None)
        out["investment_verdict"] = verdict
    if isinstance(out.get("evidence_score"), dict):
        out["evidence_score"] = {k: v for k, v in out["evidence_score"].items() if k not in INTERNAL_EVIDENCE_SCORE_KEYS}
    return out


def enrich_availability(result: dict, availability: dict) -> dict:
    """answer_availability with the final contract's kind, scope and conclusion_authorized (see the module docstring)."""
    kind = answer_kind(result, availability)
    return {**availability, "kind": kind, "scope": answer_scope(result, kind), "conclusion_authorized": has_authorized_conclusion(result)}
