"""
Evidence ranking — AI Article V2 Phase A.1 (owner decision, 2026-08-29).
Real, deterministic, explainable ranking of a company's linked evidence —
never an LLM judgment call ("which filing looks most important?"), never
an arbitrary hand-assigned importance score.

Motivating real case (Phase A demo, artifacts/ai_article_v2_phase_a_evidence_grounding.md):
TCS's grounded "What Happened" picked a generic "Bagging/Receiving of
orders/contracts" filing over a more newsworthy same-minute Porsche
AI-partnership press release, because both were real NSE filings from the
same day and the bundle builder simply took the most recent by
`published_at`. "Newest" is not "most substantive."

Two real, code-based signals combine into one explainable score — no
third signal is invented just to fill a formula:

1. **Subject substantiveness** — NSE filings follow a real, recognizable
   subject-line convention ("has informed the Exchange about/regarding
   X"). The X values cluster into a small, real, finite taxonomy this
   module classifies directly from the literal text — not learned, not
   guessed, just pattern-matched against phrases NSE itself uses.
2. **Query relevance** — when a query/trigger context is supplied (e.g.
   the headline of the event that triggered article generation), real
   title-token-overlap (Jaccard) against that context, reusing the exact
   same tokenizer/similarity function `duplicate_detector.py` already
   uses and this audit already found to be a solid, real mechanism —
   never reimplemented.

Recency is a tie-breaker only, never the primary signal, and every
ranked result carries its own real `reasons` list so a human (or a log)
can see exactly why one item outranked another — matching the owner's
explicit "selection reason available for debugging" requirement.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.services.aipe.duplicate_detector import _jaccard, _tokenize
from app.services.warehouse.read_service import LinkedEvidence

# Real, observed NSE subject-line phrases (S5-C/Warehouse trace corpus,
# 2026-08-24 ICICIBANK/TCS filings) classified by real substantiveness —
# does this filing, on its own text, describe a genuine business event a
# reader would want an article about, vs. a routine/administrative
# disclosure. Deliberately conservative: an unrecognized subject line
# scores as UNKNOWN (mid-range), never silently HIGH or LOW.
# "bagging/receiving of orders" is deliberately NOT in this list — it's a
# real NSE category, but a bare instance of it (no counterparty, no
# amount, no further detail beyond the category label itself) carries no
# more real information than the label "this happened," which is exactly
# the real Phase A case that motivated this module: a bare
# "Bagging/Receiving of orders/contracts" filing must not outrank a real
# press release with a specific, named, quoted title. A filing that
# combines this category with real specific content (a quoted title, a
# named counterparty) will still score HIGH via the "press release"/named
# phrases below — this list scores the DECLARED SUBJECT, not the category
# alone.
_HIGH_SUBSTANTIVENESS = [
    "acquisition", "press release", "merger", "amalgamation",
    "credit rating", "rating action", "board approv", "resignation",
    "appointment of", "financial results", "dividend declar",
]
_LOW_SUBSTANTIVENESS = [
    "allotment of", "employee stock option", "esop", "disclosure under regulation 30 read with para a of schedule iii",
    "loss of share certificate", "change in address", "record date",
    "closure of trading window", "newspaper publication",
]

_SCORE_HIGH, _SCORE_UNKNOWN, _SCORE_LOW = 1.0, 0.5, 0.2
_WEIGHT_SUBSTANTIVENESS = 0.6
_WEIGHT_RELEVANCE = 0.4


def _subject_substantiveness(title: str | None) -> tuple[float, str]:
    if not title:
        return _SCORE_UNKNOWN, "no title text to classify"
    t = title.lower()
    for phrase in _LOW_SUBSTANTIVENESS:
        if phrase in t:
            return _SCORE_LOW, f"matched low-substantiveness phrase {phrase!r}"
    for phrase in _HIGH_SUBSTANTIVENESS:
        if phrase in t:
            return _SCORE_HIGH, f"matched high-substantiveness phrase {phrase!r}"
    return _SCORE_UNKNOWN, "no recognized subject phrase — scored neutral, not guessed"


@dataclass(frozen=True)
class RankedEvidence:
    evidence: LinkedEvidence
    score: float
    reasons: list[str] = field(default_factory=list)


def rank_evidence(evidence: list[LinkedEvidence], query_context: str | None = None) -> list[RankedEvidence]:
    """Real, explainable ranking — highest score first. Ties broken by
    recency only (a real, defensible tie-breaker, never the primary
    signal). `query_context` is typically the triggering event's own
    headline/summary text, when one exists."""
    query_tokens = _tokenize(query_context) if query_context else set()

    ranked: list[RankedEvidence] = []
    for e in evidence:
        sub_score, sub_reason = _subject_substantiveness(e.title)
        reasons = [sub_reason]

        rel_score = 0.0
        if query_tokens and e.title:
            rel_score = _jaccard(query_tokens, _tokenize(e.title))
            reasons.append(f"title/query token overlap (Jaccard) = {rel_score:.2f}")
            total = sub_score * _WEIGHT_SUBSTANTIVENESS + rel_score * _WEIGHT_RELEVANCE
        else:
            # No query context supplied — substantiveness is the whole
            # score; never invent a relevance number with nothing to
            # compare against.
            total = sub_score
            reasons.append("no query context supplied — ranked on substantiveness alone")

        ranked.append(RankedEvidence(evidence=e, score=round(total, 4), reasons=reasons))

    ranked.sort(key=lambda r: (r.score, r.evidence.published_at or datetime.min.replace(tzinfo=timezone.utc)), reverse=True)
    return ranked
