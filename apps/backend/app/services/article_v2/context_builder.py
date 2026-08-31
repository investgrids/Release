"""
Article V2 Phase C3 — Event-aware Context Builder (owner design,
2026-08-31). Answers: "given this specific development and its C2-
accepted evidence, what verified context is actually relevant enough to
help explain its significance?" This is the direct fix for the
confirmed Phase B weakness: select_relevant_financial_facts() injected
the same fixed CET1/NPA/ROA metric set into every Banking article
regardless of what the triggering event was actually about (5/5 real
non-financial Banking events all got the identical metric set — see
artifacts/ai_article_v2_phase_a_evidence_grounding.md's follow-up
probe). C3 makes financial-context selection event-aware instead of
company-aware: context must be relevant to THIS development, never
merely available for this company.

Takes a real ArticleEvidenceSet (C2's own output) as input, not just a
symbol — C3 is explicitly downstream of C2, per the owner's own pipeline
framing, and only ever considers the primary/supporting evidence C2
already accepted, never anything C2 excluded.

Produces an ArticleContextBundle: event-aware financial context (with
real prior-period trend comparison, not just the latest value), market
reaction (temporal, explicitly not causal, omitted when the timing
window isn't meaningful), and an AVAILABLE/PARTIAL/NONE status. No
history-by-keyword-similarity search — the owner explicitly warned
against "vaguely similar old news just to make the bundle richer";
the one historical comparison this module makes (this period's metric
vs. the immediately preceding period, same entity, same metric) is a
real, directly comparable, deterministic fact, not a fuzzy retrieval.

Event-family classification, deliberately small and evidence-driven —
built from the families actually observed in the real C1.1/C2 shadow
cohort, not a speculative taxonomy:
  RESULTS         — "financial results"/"quarterly results"/"annual
                     results" — the full real metric picture is relevant.
  FUNDRAISING      — "fund raising"/"fundraising"/"rights issue"/"qip"/
                     "preferential allotment" — capital-adequacy metrics
                     are relevant (why a bank raises capital), plus real
                     balance-sheet scale.
  CREDIT_RATING     — "credit rating"/"rating action" — the metrics a
                     rating agency actually scrutinizes.
  ORDER_CONTRACT     — "order worth"/"order from"/"wins order"/"wins
                     contract"/"bagging of order" (deliberately NOT a
                     bare "order" substring -- found live via the C3
                     shadow run: NEWGEN's real evidence text "...in
                     order to ensure that investors..." false-matched a
                     bare "order" substring, nothing to do with a real
                     order win; the phrase list was tightened to
                     multi-word patterns after finding this) — real
                     balance-sheet scale only, for size-relative framing;
                     rarely fires today since FinancialFact is Banking-
                     only and most real order-win events are non-bank.
Anything unrecognized (AGM, board-meeting-general/other-business,
dividend/record date, ESOP, governance/resignation/appointment,
newspaper publication, ESG/BRSR, web link letter, media release) maps to
NO allowed metrics, deliberately — the owner's own explicit examples
("a management resignation should not suddenly receive a paragraph
about P/E or quarterly NII"; "a dividend/record-date development should
not inherit arbitrary profitability metrics") are the default, not an
edge case, for any event this small taxonomy doesn't specifically
recognize. Real FinancialFact coverage is Banking-sector only today
(BANKING_V1 scope, confirmed via the actual production backfill) — for
every non-bank company this correctly, honestly returns NONE regardless
of event family, not a gap in this module's own logic.

Financial-fact quality filtering reuses read_service.py's own
_FINANCIAL_EXCLUDED_QUALITY constant verbatim (never re-derives its own
notion of "quality-passed") and get_verified_financial_context() for
the latest-value path — this module adds ONLY the event-aware
allowlist filter and the prior-period trend lookup on top, it does not
reimplement quality filtering.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.financial_fact import EXTRACTION_POPULATED, FinancialFact
from app.services.article_v2.evidence_set_builder import ArticleEvidenceSet
from app.services.warehouse.article_evidence_bundle import build_article_evidence_bundle
from app.services.warehouse.read_service import _FINANCIAL_EXCLUDED_QUALITY, get_verified_financial_context

AVAILABLE = "AVAILABLE"
PARTIAL = "PARTIAL"
NONE_STATUS = "NONE"

# A same-real-trading-day-or-close window -- outside this, "today's price
# move" is not a meaningful reaction window for an older development, and
# must be omitted rather than misleadingly attached.
_MARKET_REACTION_MAX_AGE_DAYS = 2

_EVENT_FAMILY_PHRASES: dict[str, list[str]] = {
    "RESULTS": ["financial results", "quarterly results", "annual results"],
    "FUNDRAISING": ["fund raising", "fundraising", "rights issue", "qip", "preferential allotment", "capital raise"],
    "CREDIT_RATING": ["credit rating", "rating action"],
    "ORDER_CONTRACT": [
        "order worth", "order from", "order for", "wins order", "wins contract",
        "contract worth", "contract from", "bagging of order", "bagging/receiving of order",
    ],
}

_FAMILY_METRIC_ALLOWLIST: dict[str, set[str]] = {
    "RESULTS": {
        "gross_npa_pct", "net_npa_pct", "gross_npa_amount", "net_npa_amount", "cet1_ratio",
        "additional_tier1_ratio", "roa", "interest_earned", "interest_expended",
        "advances", "deposits", "borrowings", "casa_ratio",
    },
    "FUNDRAISING": {"cet1_ratio", "additional_tier1_ratio", "advances", "deposits"},
    "CREDIT_RATING": {"cet1_ratio", "gross_npa_pct", "net_npa_pct"},
    "ORDER_CONTRACT": {"advances", "deposits"},
}


@dataclass(frozen=True)
class ContextFinancialFact:
    metric_code: str
    metric_name: str
    value: float
    unit: str
    fiscal_year: int
    fiscal_quarter: int | None
    quality_status: str
    source_document_url: str | None
    matched_family: str
    prior_period_value: float | None = None
    prior_period_label: str | None = None


@dataclass(frozen=True)
class MarketReaction:
    price_move_pct: float
    note: str  # always states "temporal, not causal" explicitly


@dataclass(frozen=True)
class ArticleContextBundle:
    entity_id: str | None
    symbol: str | None
    event_id: str | None
    event_headline: str
    status: str
    matched_event_families: list[str] = field(default_factory=list)
    financial_context: list[ContextFinancialFact] = field(default_factory=list)
    market_reaction: MarketReaction | None = None
    omitted_reasons: list[str] = field(default_factory=list)


def _classify_event_families(evidence_set: ArticleEvidenceSet) -> list[str]:
    """Classified from the C2-ACCEPTED evidence only (primary +
    supporting) -- never from excluded evidence, and never from the raw
    triggering headline alone, since C2 already established which text
    genuinely belongs to this development."""
    texts = []
    if evidence_set.primary_evidence and evidence_set.primary_evidence.title:
        texts.append(evidence_set.primary_evidence.title.lower())
    texts += [e.title.lower() for e in evidence_set.supporting_evidence if e.title]

    matched = []
    for family, phrases in _EVENT_FAMILY_PHRASES.items():
        if any(phrase in text for phrase in phrases for text in texts):
            matched.append(family)
    return matched


async def _prior_period_value(
    db: AsyncSession, *, symbol: str, metric_code: str, before_fy: int, before_fq: int | None,
) -> tuple[float | None, str | None]:
    """The real, quality-passed value for this exact metric in the period
    immediately preceding the one get_verified_financial_context()
    already surfaced -- reuses the SAME quality exclusion this module
    imports from read_service.py, never a second, independently-derived
    notion of what counts as trustworthy."""
    rows = (await db.execute(
        select(FinancialFact.value, FinancialFact.fiscal_year, FinancialFact.fiscal_quarter, FinancialFact.quality_status)
        .where(
            FinancialFact.symbol == symbol.upper(), FinancialFact.metric_code == metric_code,
            FinancialFact.consolidation_scope == "Non-Consolidated",
            FinancialFact.extraction_status == EXTRACTION_POPULATED,
        )
    )).all()
    fq_key = before_fq or 0
    candidates = [
        (v, fy, fq) for v, fy, fq, qs in rows
        if v is not None and qs not in _FINANCIAL_EXCLUDED_QUALITY and (fy, fq or 0) < (before_fy, fq_key)
    ]
    if not candidates:
        return None, None
    v, fy, fq = max(candidates, key=lambda c: (c[1], c[2] or 0))
    label = f"FY{fy}Q{fq}" if fq else f"FY{fy}"
    return v, label


async def build_context(db: AsyncSession, evidence_set: ArticleEvidenceSet) -> ArticleContextBundle:
    """The one real entry point. Only ever called for a C2-usable
    evidence set (primary_evidence is not None) -- an INSUFFICIENT C2
    set has nothing for C3 to build context around, by design; the
    owner's own instruction is explicit that C3 must not rescue an
    evidence-insufficient development by finding generic company
    context, so this function does not even attempt to run for one."""
    omitted: list[str] = []

    if evidence_set.primary_evidence is None or evidence_set.symbol is None:
        return ArticleContextBundle(
            entity_id=evidence_set.entity_id, symbol=evidence_set.symbol, event_id=evidence_set.event_id,
            event_headline=evidence_set.event_headline, status=NONE_STATUS,
            omitted_reasons=["no C2 primary evidence -- C3 does not run for an INSUFFICIENT evidence set"],
        )

    families = _classify_event_families(evidence_set)

    # -- Financial context, event-aware --
    financial_context: list[ContextFinancialFact] = []
    if not families:
        omitted.append(
            "no recognized event family matched the accepted evidence -- no FinancialFact metric is "
            "considered relevant by default (administrative/governance events get no financial context)"
        )
    else:
        allowed_metrics: set[str] = set()
        for f in families:
            allowed_metrics |= _FAMILY_METRIC_ALLOWLIST[f]

        verified = await get_verified_financial_context(db, evidence_set.symbol)
        if not verified.has_real_facts:
            omitted.append(
                f"event family {families} matched, but this company has zero quality-passed FinancialFact "
                f"rows at all (FinancialFact coverage is Banking-sector only today, BANKING_V1 scope)"
            )
        else:
            relevant = [fact for fact in verified.facts if fact.metric_code in allowed_metrics]
            irrelevant = [fact for fact in verified.facts if fact.metric_code not in allowed_metrics]
            if irrelevant:
                omitted.append(
                    f"{len(irrelevant)} real quality-passed fact(s) existed but were NOT selected -- not "
                    f"relevant to event family {families}: {[f.metric_code for f in irrelevant]}"
                )
            if not relevant:
                omitted.append(
                    f"event family {families} matched and real facts exist for this company, but none of "
                    f"its available metrics ({[f.metric_code for f in verified.facts]}) are in the allowed "
                    f"set for this family"
                )
            for fact in relevant:
                which_family = next(
                    (fam for fam in families if fact.metric_code in _FAMILY_METRIC_ALLOWLIST[fam]), families[0],
                )
                prior_value, prior_label = await _prior_period_value(
                    db, symbol=evidence_set.symbol, metric_code=fact.metric_code,
                    before_fy=fact.fiscal_year, before_fq=fact.fiscal_quarter,
                )
                financial_context.append(ContextFinancialFact(
                    metric_code=fact.metric_code, metric_name=fact.metric_name, value=fact.value, unit=fact.unit,
                    fiscal_year=fact.fiscal_year, fiscal_quarter=fact.fiscal_quarter,
                    quality_status=fact.quality_status, source_document_url=fact.source_document_url,
                    matched_family=which_family, prior_period_value=prior_value, prior_period_label=prior_label,
                ))

    # -- Market reaction, temporal not causal, timing-gated --
    market_reaction: MarketReaction | None = None
    published_at = evidence_set.primary_evidence.published_at
    if published_at is None:
        omitted.append("primary evidence has no real published_at -- cannot establish an event window")
    else:
        now = datetime.now(timezone.utc)
        pub = published_at if published_at.tzinfo else published_at.replace(tzinfo=timezone.utc)
        age = now - pub
        if age > timedelta(days=_MARKET_REACTION_MAX_AGE_DAYS):
            omitted.append(
                f"primary evidence is {age.days} day(s) old -- outside the "
                f"{_MARKET_REACTION_MAX_AGE_DAYS}-day window for a meaningful same-event price reaction"
            )
        else:
            bundle = await build_article_evidence_bundle(
                db, evidence_set.symbol, include_historical=False,
                include_price_move=True, include_financial_context=False,
            )
            if bundle.price_move_pct is None:
                omitted.append("no real price observation available for this symbol")
            else:
                market_reaction = MarketReaction(
                    price_move_pct=bundle.price_move_pct,
                    note=(
                        "temporal correlation only: the stock moved this much on the day this development "
                        "was reported -- this is NOT a claim that the development caused the move"
                    ),
                )

    if financial_context and market_reaction is not None:
        status = AVAILABLE
    elif financial_context or market_reaction is not None:
        status = PARTIAL
    else:
        status = NONE_STATUS

    return ArticleContextBundle(
        entity_id=evidence_set.entity_id, symbol=evidence_set.symbol, event_id=evidence_set.event_id,
        event_headline=evidence_set.event_headline, status=status,
        matched_event_families=families, financial_context=financial_context,
        market_reaction=market_reaction, omitted_reasons=omitted,
    )
