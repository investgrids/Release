"""
Article V2 Phase C5.1/C5.2 — Article Identity + Publication Uniqueness
(owner design, 2026-08-31). "Identity first, headline second" -- before
generating any wording, establish what real-world development a URL
would represent, so a headline is never the primary way MarketRipple
decides whether two things are the same story.

## Identity

`ArticleIdentity` = canonical entity + development type + a development-
specific anchor + a coarse time bucket. Deliberately NOT title
similarity -- the owner's own real examples make this concrete:

  "ABC wins Rs 800 crore railway order"
  "ABC receives LoA for Rs 800 crore railway project"
  "ABC confirms Rs 800 crore order in exchange filing"
    -> same entity, same development_type (ORDER_CONTRACT), same real
       numeric anchor (Rs 800 crore, extracted via
       numeric_validation.extract_numeric_claims -- never re-parsed by
       hand), same time bucket -> SAME identity.

  "ABC wins another Rs 450 crore defence order two months later"
    -> same entity, same development_type, but a DIFFERENT anchor (450
       not 800) AND a different time bucket -> DIFFERENT identity, even
       though "wins ... order" is lexically almost identical to the
       first three headlines. This is exactly why anchor+time, not
       headline text, carries the real distinguishing weight.

development_type reuses evidence_ranking.py's own real HIGH/LOW
substantiveness phrase lists (never a second, independently-invented
classification) plus the small set of additional real families C3
already established (FUNDRAISING/ORDER_CONTRACT), extended only as far
as the real observed cohort requires -- same "don't build a giant
taxonomy speculatively" discipline as C3.

The anchor is the single largest real numeric claim (by absolute value)
extracted from the accepted evidence's own text (primary + supporting) --
"the deal size" is what genuinely distinguishes one order/result/
fundraise from another of the same type for the same company. When no
real number exists (a governance change, an AGM notice, an ESG
disclosure), the anchor falls back to a short, normalized keyword
fragment of the primary evidence's own subject text -- imperfect, but
combined with entity+type+time_bucket, real and stable enough to
distinguish genuinely separate administrative events for the real
cohort this was built against.

## Publication uniqueness

C4 already produces a publication_action (CREATE/UPDATE_EXISTING/NONE),
using C1's own real duplicate-detection (trigger_event_id match, then
headline Jaccard against published articles). C5.2 does not replace
that -- it adds one more real, independent check the coarser headline-
based mechanism can miss: TWO DIFFERENT triggering events in the SAME
processing batch resolving to the SAME real ArticleIdentity (the
owner's own hard rule: "one underlying development should not produce
multiple canonical URLs merely because new evidence or a differently
worded headline arrived"). When that happens, only the first-seen
identity gets CREATE_NEW; every later collision in the same batch
becomes NO_PUBLICATION (not a silent duplicate, not a second URL) --
explained via a real reason, not guessed.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.services.article_v2.evidence_set_builder import ArticleEvidenceSet
from app.services.warehouse.evidence_ranking import _HIGH_SUBSTANTIVENESS, _LOW_SUBSTANTIVENESS
from app.services.warehouse.numeric_validation import extract_numeric_claims

CREATE_NEW = "CREATE_NEW"
UPDATE_EXISTING = "UPDATE_EXISTING"
NO_PUBLICATION = "NO_PUBLICATION"

# Real families actually observed across the C1.1/C2/C3 shadow cohorts,
# same discipline C3 already established -- extended only as far as
# distinguishing real developments in that data required. Reuses
# evidence_ranking.py's own HIGH list directly for RESULTS/CREDIT_RATING/
# ACQUISITION_MERGER/GOVERNANCE (those exact phrases already live there);
# only FUNDRAISING/ORDER_CONTRACT/ESG_DISCLOSURE are new, small, and
# grounded in real evidence text seen in the cohort (CANBK's real
# "Fund raising", the C3 ORDER_CONTRACT fix, BLS/FIRSTCRY's real BRSR
# filings).
_DEVELOPMENT_TYPE_PHRASES: dict[str, list[str]] = {
    "RESULTS": ["financial results", "quarterly results", "annual results"],
    "ACQUISITION_MERGER": ["acquisition", "merger", "amalgamation"],
    "CREDIT_RATING": ["credit rating", "rating action"],
    "GOVERNANCE": ["resignation", "appointment of"],
    "FUNDRAISING": ["fund raising", "fundraising", "rights issue", "qip", "preferential allotment", "capital raise"],
    "ORDER_CONTRACT": [
        "order worth", "order from", "order for", "wins order", "wins contract",
        "contract worth", "contract from", "bagging of order", "bagging/receiving of order",
    ],
    "ESG_DISCLOSURE": ["business responsibility", "sustainability report", "brsr"],
    "CORPORATE_ACTION": [p for p in _LOW_SUBSTANTIVENESS],  # AGM/dividend/ESOP/record date/newspaper publication/etc -- reused verbatim, never redefined
}

_BOILERPLATE_STRIP = [
    "has informed the exchange", "has informed the exchange about", "has informed the exchange regarding",
    "has submitted to the exchange", "informs the exchange", "the company has informed the exchange",
]

# ISO-week-based bucket -- coarse enough that a real multi-filing cluster
# about the same development (a few days apart) shares a bucket, fine
# enough that "two months later" always lands in a different one.


@dataclass(frozen=True)
class ArticleIdentity:
    entity_id: str
    symbol: str
    development_type: str
    anchor: str
    time_bucket: str
    identity_key: str


def _classify_development_type(texts: list[str]) -> str:
    joined = " ".join(t.lower() for t in texts if t)
    for family, phrases in _DEVELOPMENT_TYPE_PHRASES.items():
        if any(phrase in joined for phrase in phrases):
            return family
    return "OTHER"


def _dominant_numeric_anchor(texts: list[str]) -> str | None:
    best_value = None
    best_repr = None
    for t in texts:
        if not t:
            continue
        for claim in extract_numeric_claims(t):
            if claim.kind not in ("currency_inr", "currency_usd", "currency_generic"):
                continue
            if best_value is None or abs(claim.value) > abs(best_value):
                best_value = claim.value
                best_repr = f"{claim.kind}:{round(claim.value, 2)}"
    return best_repr


def _keyword_anchor(title: str | None) -> str:
    if not title:
        return "no-title"
    t = title.lower()
    for phrase in _BOILERPLATE_STRIP:
        t = t.replace(phrase, " ")
    tokens = re.findall(r"[a-z0-9]+", t)
    stop = {"the", "a", "an", "of", "to", "for", "and", "in", "on", "at", "is", "be", "this", "that", "with", "under", "regarding", "about", "limited", "ltd"}
    significant = [tok for tok in tokens if tok not in stop and len(tok) > 2][:6]
    return "-".join(significant) if significant else "no-topic"


def _time_bucket(published_at: datetime | None) -> str:
    if published_at is None:
        return "unknown-time"
    dt = published_at if published_at.tzinfo else published_at.replace(tzinfo=timezone.utc)
    iso = dt.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def compute_identity(evidence_set: ArticleEvidenceSet) -> ArticleIdentity:
    """The one real entry point. Requires a usable C2 evidence set
    (primary_evidence present) -- callers should not call this for an
    INSUFFICIENT set (nothing to build an identity around)."""
    if evidence_set.primary_evidence is None or evidence_set.entity_id is None:
        raise ValueError("compute_identity requires a usable evidence set with a resolved entity")

    all_evidence = [evidence_set.primary_evidence] + list(evidence_set.supporting_evidence)
    texts = [e.title for e in all_evidence if e.title]

    development_type = _classify_development_type(texts)
    anchor = _dominant_numeric_anchor(texts) or f"topic:{_keyword_anchor(evidence_set.primary_evidence.title)}"
    time_bucket = _time_bucket(evidence_set.primary_evidence.published_at)

    identity_key = f"{evidence_set.entity_id}|{development_type}|{anchor}|{time_bucket}"
    return ArticleIdentity(
        entity_id=evidence_set.entity_id, symbol=evidence_set.symbol or "",
        development_type=development_type, anchor=anchor, time_bucket=time_bucket,
        identity_key=identity_key,
    )


@dataclass(frozen=True)
class PublicationResolution:
    identity: ArticleIdentity
    publication_action: str
    matched_identity_key: str | None
    matched_article_id: str | None
    reason: str


def resolve_uniqueness(
    identity: ArticleIdentity, *, c4_publication_action: str, c4_matched_article_id: str | None,
    known_identities: dict[str, str],
) -> PublicationResolution:
    """`known_identities` maps identity_key -> the article_id or batch
    symbol that already claimed it (already-processed candidates in the
    current batch, first-seen order). Pure function -- the caller is
    responsible for updating `known_identities` with this call's own
    result before processing the next candidate, so collisions across
    an ordered batch are caught deterministically."""
    if c4_publication_action == "UPDATE_EXISTING" and c4_matched_article_id:
        return PublicationResolution(
            identity=identity, publication_action=UPDATE_EXISTING,
            matched_identity_key=None, matched_article_id=c4_matched_article_id,
            reason=f"C1/C4 already resolved this to existing article {c4_matched_article_id}; C5 preserves that canonical URL.",
        )

    if c4_publication_action != "CREATE":
        return PublicationResolution(
            identity=identity, publication_action=NO_PUBLICATION,
            matched_identity_key=None, matched_article_id=None,
            reason="C4 did not authorize a new article for this development.",
        )

    existing = known_identities.get(identity.identity_key)
    if existing is not None:
        return PublicationResolution(
            identity=identity, publication_action=NO_PUBLICATION,
            matched_identity_key=identity.identity_key, matched_article_id=existing,
            reason=(
                f"identity {identity.identity_key!r} was already claimed by {existing!r} earlier in this batch -- "
                f"same entity, same development type, same anchor, same time window. Not a second URL for the "
                f"same underlying development."
            ),
        )

    return PublicationResolution(
        identity=identity, publication_action=CREATE_NEW,
        matched_identity_key=None, matched_article_id=None,
        reason="genuinely new identity, no collision in this batch or with existing coverage.",
    )
