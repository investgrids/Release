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
    REASON_INSUFFICIENT_MARKET_HISTORY, REASON_MARKET_INPUTS_UNVERIFIED, REASON_MISSING_REQUIRED_PILLAR,
    REASON_MARKET_SERIES_INVALID, REASON_NO_MATCHING_PEER_GROUP, REASON_PEER_GROUP_UNDER_REVIEW,
    REASON_NO_ELIGIBLE_FINANCIAL_PERIOD, REASON_STALE_FINANCIAL_DATA,
)

# Priority order (most severe/fundamental first) + the exact public copy
# for each reason code. A bank with multiple real reasons shows only the
# highest-priority one as its headline message — never a concatenation.
_REASON_PRIORITY: list[str] = [
    REASON_MISSING_REQUIRED_PILLAR,
    REASON_NO_ELIGIBLE_FINANCIAL_PERIOD,
    REASON_INSUFFICIENT_FINANCIAL_METRICS,
    REASON_NO_MATCHING_PEER_GROUP,
    REASON_PEER_GROUP_UNDER_REVIEW,
    REASON_MARKET_SERIES_INVALID,
    REASON_STALE_FINANCIAL_DATA,
    REASON_MARKET_INPUTS_UNVERIFIED,
    REASON_INSUFFICIENT_MARKET_HISTORY,
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
    REASON_INSUFFICIENT_MARKET_HISTORY: (
        "Insufficient data",
        "MarketRipple doesn't have enough completed price history and market comparison data to publish a score for this company yet.",
    ),
    REASON_STALE_FINANCIAL_DATA: (
        "Financial data awaiting update",
        "The latest financial statements MarketRipple has for this company are more than 15 months old, so its score is on hold until they are refreshed.",
    ),
    REASON_MARKET_SERIES_INVALID: (
        "Price history under review",
        "This company's recent price history has a break or hasn't traded normally, so its market-behaviour inputs can't be trusted. The score returns once the price data is verified.",
    ),
    REASON_PEER_GROUP_UNDER_REVIEW: (
        "Peer group under review",
        "MarketRipple is correcting the peer group this company is ranked against. Its score will return once the corrected group has been calculated and reviewed.",
    ),
    REASON_NO_MATCHING_PEER_GROUP: (
        "No matching peer group",
        "MarketRipple has no comparable peer group for this company's business, so it isn't scored rather than compared with the wrong companies.",
    ),
    REASON_MARKET_INPUTS_UNVERIFIED: (
        "Score being refreshed",
        "MarketRipple is recalculating this score from the last completed trading session. It will reappear once the new calculation passes the publication checks.",
    ),
    REASON_INSUFFICIENT_OVERALL_COVERAGE: (
        "Evidence still building",
        "MarketRipple does not yet have enough current evidence to publish a reliable overall score for this company.",
    ),
}


def is_publicly_published(snap) -> bool:
    """The one check every public surface uses before showing a number:
    the stored publishable flag AND the market-behaviour floor (which also
    hides snapshots published before that floor existed)."""
    from app.services.marketripple_score.corporate_action_holds import score_hold_for
    from app.services.marketripple_score.data_quality import snapshot_data_quality_reasons
    from app.services.marketripple_score.market_behaviour import snapshot_lacks_market_history

    return (
        bool(snap.publishable)
        and not snapshot_lacks_market_history(snap)
        and score_hold_for(getattr(snap, "symbol", None)) is None
        and not snapshot_data_quality_reasons(snap)
    )


def public_block_reasons(snap) -> list[str]:
    """Stored block reasons plus the shared public gates (data quality, market
    history, corporate-action hold) — exactly what the Company page applies,
    so Rankings can never disagree with it."""
    from app.services.marketripple_score.corporate_action_holds import REASON_CORPORATE_ACTION_HOLD, score_hold_for
    from app.services.marketripple_score.data_quality import snapshot_data_quality_reasons
    from app.services.marketripple_score.market_behaviour import snapshot_lacks_market_history

    reasons = list(snap.publication_block_reasons or [])
    if snap.publishable:
        reasons += [r for r in snapshot_data_quality_reasons(snap) if r not in reasons]
        if snapshot_lacks_market_history(snap) and REASON_INSUFFICIENT_MARKET_HISTORY not in reasons:
            reasons.append(REASON_INSUFFICIENT_MARKET_HISTORY)
    if score_hold_for(getattr(snap, "symbol", None)) is not None and REASON_CORPORATE_ACTION_HOLD not in reasons:
        reasons.append(REASON_CORPORATE_ACTION_HOLD)
    return reasons


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

    from app.services.marketripple_score.coverage import coverage_fields, score_sector_for

    entity = await resolve_entity_by_any_symbol(db, raw_symbol)
    if entity is None:
        return {"resolved": False, "symbol": raw_symbol.upper(), **coverage_fields(score_sector_for(raw_symbol), None, raw_symbol)}
    sector = score_sector_for(entity.symbol)

    # Always the real, canonical, current symbol — an alias/historical
    # request lands on the exact same record a current-symbol request
    # would, never a second score identity for the same real company.
    from app.services.marketripple_score.corporate_action_holds import REASON_CORPORATE_ACTION_HOLD, score_hold_for

    hold = score_hold_for(entity.symbol)
    snap = await get_latest_snapshot(db, entity.symbol)
    if snap is None:
        base = {"resolved": True, "symbol": entity.symbol, "entity_id": entity.entity_id, "snapshot": False,
                **coverage_fields(sector, None, entity.symbol)}
        if hold is not None:
            return {**base, "publishable": False, "eligible": False, "score": None, "rating": None,
                    "block_reason_codes": [REASON_CORPORATE_ACTION_HOLD],
                    "block_headline": hold.headline, "block_message": hold.message,
                    "coverage_state": "score_hold", "coverage_label": "Score on hold",
                    "coverage_message": hold.message}
        return base

    from app.services.marketripple_score.market_behaviour import snapshot_lacks_market_history

    reasons = list(snap.publication_block_reasons or [])
    # Only when the floor is what blocks a published score — a snapshot already
    # unpublished for another reason keeps that reason's own message.
    if snap.publishable and snapshot_lacks_market_history(snap) and REASON_INSUFFICIENT_MARKET_HISTORY not in reasons:
        reasons.append(REASON_INSUFFICIENT_MARKET_HISTORY)
    if snap.publishable:
        from app.services.marketripple_score.data_quality import snapshot_data_quality_reasons

        reasons += [r for r in snapshot_data_quality_reasons(snap) if r not in reasons]
    if hold is not None and REASON_CORPORATE_ACTION_HOLD not in reasons:
        reasons.append(REASON_CORPORATE_ACTION_HOLD)
    eligible = len(reasons) == 0
    block = (hold.headline, hold.message) if hold is not None else (_public_block_message(reasons) if not eligible else None)

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
    publishable = is_publicly_published(snap)

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
        # Comparability interim rule (2026-09-26) — gated alongside the rest
        # of the numeric payload, same trust boundary as `score` above: a
        # caller shouldn't learn "this would be a partial-coverage score"
        # any more than it should learn the withheld number itself.
        "pillar_coverage_status": snap.pillar_coverage_status if publishable else None,
        "pillar_coverage_message": snap.pillar_coverage_message if publishable else None,
        "calculated_at": snap.calculated_at.isoformat() if snap.calculated_at else None,
        "block_reason_codes": reasons,
        "block_headline": block[0] if block else None,
        "block_message": block[1] if block else None,
        **coverage_fields(sector, snap, entity.symbol),
    }
