"""
S5-C — the one real read path a Company page (or its API) should use.
Resolves the requested symbol through the real Company Identity resolver
first (so an alias/historical symbol always lands on the same canonical
score record a current-symbol request would — never a second, separate
score identity for the same real company), then reads
get_latest_snapshot() — no live computation, no yfinance/NSE calls.

Per-bank UI state (score card vs. "unavailable" card) is driven by
publication_block_reasons (BANKING_V1_P1's real, per-bank verdict), NOT
by the standing `publishable` phase lock — that flag is a whole-feature,
deployment-level kill switch (this feature is simply not wired into the
real production Company page yet), not a per-request redaction rule.
`publishable` is still returned, for transparency/debugging, but a
caller should gate what it SHOWS on `eligible` (== not block reasons),
matching the real S5-C acceptance-test profiles (ICICIBANK/KOTAKBANK
render a real score; YESBANK/INDUSINDBK render the unavailable state).

Reason-code -> user-facing copy mapping is deterministic and
priority-ordered (never string concatenation of raw codes) — a data-
quality failure (missing pillar, no eligible period, too few real
metrics) is presented before a pure evidence-thinness failure (overall
coverage), since they mean materially different things to a reader.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.marketripple_score.eligibility import (
    REASON_INSUFFICIENT_FINANCIAL_METRICS, REASON_INSUFFICIENT_OVERALL_COVERAGE,
    REASON_MISSING_REQUIRED_PILLAR, REASON_NO_ELIGIBLE_FINANCIAL_PERIOD, REASON_STALE_FINANCIAL_DATA,
)

# Priority order (most severe/fundamental first) + the exact public copy
# for each reason code. A bank with multiple real reasons shows only the
# highest-priority one as its headline message — never a concatenation.
_REASON_PRIORITY: list[str] = [
    REASON_MISSING_REQUIRED_PILLAR,
    REASON_NO_ELIGIBLE_FINANCIAL_PERIOD,
    REASON_INSUFFICIENT_FINANCIAL_METRICS,
    REASON_STALE_FINANCIAL_DATA,
    REASON_INSUFFICIENT_OVERALL_COVERAGE,
]

_REASON_COPY: dict[str, tuple[str, str]] = {
    REASON_MISSING_REQUIRED_PILLAR: (
        "Insufficient verified data",
        "MarketRipple does not have enough verified data to publish a score for this company yet.",
    ),
    REASON_NO_ELIGIBLE_FINANCIAL_PERIOD: (
        "Insufficient verified financial data",
        "Some financial evidence could not be verified, so MarketRipple is not publishing a score for this company yet.",
    ),
    REASON_INSUFFICIENT_FINANCIAL_METRICS: (
        "Insufficient verified financial data",
        "Some financial evidence could not be verified, so MarketRipple is not publishing a score for this company yet.",
    ),
    REASON_STALE_FINANCIAL_DATA: (
        "Financial data awaiting update",
        "MarketRipple's financial data for this company is due for a refresh.",
    ),
    REASON_INSUFFICIENT_OVERALL_COVERAGE: (
        "Evidence still building",
        "MarketRipple does not yet have enough current evidence to publish a reliable overall score for this company.",
    ),
}


def _public_block_message(reasons: list[str]) -> tuple[str, str] | None:
    for code in _REASON_PRIORITY:
        if code in reasons:
            return _REASON_COPY[code]
    return None


async def get_marketripple_score_projection(db: AsyncSession, raw_symbol: str) -> dict:
    """Returns the real public-contract shape. `resolved: False` when the
    symbol doesn't resolve to a real CompanyEntity at all (never a guess).
    `resolved: True, snapshot: False` when the company is real but no
    snapshot has ever been computed for it. Otherwise the full real
    projection, with `eligible` driving which UI state to render."""
    from app.services.company_identity.qualification import resolve_entity_by_any_symbol
    from app.services.marketripple_score.snapshot import get_latest_snapshot

    entity = await resolve_entity_by_any_symbol(db, raw_symbol)
    if entity is None:
        return {"resolved": False, "symbol": raw_symbol.upper()}

    # Always the real, canonical, current symbol — an alias/historical
    # request lands on the exact same record a current-symbol request
    # would, never a second score identity for the same real company.
    snap = await get_latest_snapshot(db, entity.symbol)
    if snap is None:
        return {"resolved": True, "symbol": entity.symbol, "entity_id": entity.entity_id, "snapshot": False}

    reasons = snap.publication_block_reasons or []
    eligible = len(reasons) == 0
    block = _public_block_message(reasons) if not eligible else None

    # Publication safety fix — Company Page release audit, 2026-08-31.
    # `publishable` was previously returned "for transparency/debugging"
    # alongside the real score/rating/pillars regardless of its value —
    # safe while this was a shadow-only, never-called-by-anything-public
    # endpoint, but a real pre-deploy audit confirmed the merged Company
    # page DOES call this endpoint client-side and render it. A real,
    # unauthenticated request for an eligible-but-locked bank (e.g.
    # ICICIBANK: eligible=True, publishable=False) returned its real
    # score/rating/pillars in full — a genuine leak of an internal,
    # not-yet-publication-ready number, discoverable via this API alone
    # even if a UI never rendered it.
    #
    # `publishable` is now a hard trust boundary at this layer: whenever
    # it's False, the numeric payload (score/rating/pillars/evidence
    # coverage/financial_data_as_of) is never included in the response,
    # regardless of `eligible`. This does NOT change eligibility
    # calculation — `eligible` above is untouched and still reflects the
    # real per-bank BANKING_V1_P1 verdict, still returned for callers
    # that need it — only what numeric payload this projection is
    # allowed to expose once the whole-feature lock is on. The existing
    # frontend UI gate (`data.score != null`) already renders its own
    # honest "Unavailable" / "Not available yet" state whenever score is
    # null, so no frontend change is required for this fix to take
    # effect — an eligible-but-locked bank now correctly shows the same
    # honest empty state a genuinely-ineligible bank already did.
    publishable = bool(snap.publishable)

    return {
        "resolved": True,
        "snapshot": True,
        "symbol": snap.symbol,
        "entity_id": snap.entity_id,
        "methodology_version": snap.methodology_version,
        "publication_policy_version": snap.publication_policy_version,
        "publishable": publishable,   # whole-feature phase lock — now also the real API trust boundary
        "eligible": eligible,         # the real per-bank BANKING_V1_P1 verdict — unchanged calculation
        "score": snap.score if publishable else None,
        "rating": snap.rating if publishable else None,
        "pillars": {
            "financial_strength": snap.financial_strength if publishable else None,
            "valuation": snap.valuation if publishable else None,
            "market_behaviour": snap.market_behaviour if publishable else None,
            "current_intelligence": snap.current_intelligence if publishable else None,
        },
        "evidence_coverage_pct": snap.coverage_pct if publishable else None,
        "financial_data_as_of": snap.financial_data_as_of if publishable else None,
        "calculated_at": snap.calculated_at.isoformat() if snap.calculated_at else None,
        "block_reason_codes": reasons,
        "block_headline": block[0] if block else None,
        "block_message": block[1] if block else None,
    }
