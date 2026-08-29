"""
S5-B — real 27-bank publication eligibility audit. Reads the real S5-A
snapshots already persisted (zero new network calls) plus a cheap DB-only
quarantine check, and evaluates 3 candidate policies side by side.
Deliberately does NOT choose or implement a final threshold, does NOT
touch BANKING_V1 scoring, does NOT expose an API/UI, does NOT flip
`publishable` on any real snapshot row — pure analysis output.
"""
from __future__ import annotations

import asyncio
import collections
import sys

sys.path.insert(0, ".")

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.db.models.financial_fact import FinancialFact, QUALITY_IMPLAUSIBLE_SCALE, QUALITY_SOURCE_DOCUMENT_QUARANTINED
from app.db.models.marketripple_score_snapshot import MarketRippleScoreSnapshot
from app.services.marketripple_score.banking_universe import ALL_ELIGIBLE_NSE_BANKS
from app.services.marketripple_score.eligibility import EligibilityPolicy, evaluate_eligibility

POLICIES = [
    EligibilityPolicy(name="A (>=4/7, >=60% overall)", min_financial_metrics_used=4, min_overall_coverage_pct=60.0),
    EligibilityPolicy(name="B (>=5/7, >=65% overall)", min_financial_metrics_used=5, min_overall_coverage_pct=65.0),
    EligibilityPolicy(name="C (>=6/7, >=70% overall)", min_financial_metrics_used=6, min_overall_coverage_pct=70.0),
]


async def _has_quarantined_or_implausible_facts(db, symbol: str) -> bool:
    row = (await db.execute(
        select(FinancialFact.id).where(
            FinancialFact.symbol == symbol,
            FinancialFact.quality_status.in_([QUALITY_IMPLAUSIBLE_SCALE, QUALITY_SOURCE_DOCUMENT_QUARANTINED]),
        ).limit(1)
    )).scalar_one_or_none()
    return row is not None


async def main() -> None:
    async with AsyncSessionLocal() as db:
        snapshots = {}
        for symbol in ALL_ELIGIBLE_NSE_BANKS:
            row = (await db.execute(
                select(MarketRippleScoreSnapshot)
                .where(MarketRippleScoreSnapshot.symbol == symbol)
                .order_by(MarketRippleScoreSnapshot.calculated_at.desc())
                .limit(1)
            )).scalar_one_or_none()
            if row:
                snapshots[symbol] = row

        # Real, population-derived freshness reference -- the most common
        # financial_data_as_of across the universe, not a guessed rule.
        period_counts = collections.Counter(s.financial_data_as_of for s in snapshots.values() if s.financial_data_as_of)
        mode_period = period_counts.most_common(1)[0][0] if period_counts else None

        print(f"=== S5-B eligibility audit: {len(snapshots)} real banks, mode financial period = {mode_period} ===\n")
        header = (
            f"{'Symbol':<12}{'FinMetrics':>11}{'Fin%(of7)':>10}{'ValCov%':>9}{'MktCov%':>9}{'CICov%':>8}"
            f"{'Overall%':>9}  {'FinDataAsOf':>12}  {'Quarantined':>12}  {'A':>6}{'B':>6}{'C':>6}"
        )
        print(header)
        print("-" * len(header))

        results_by_policy = {p.name: [] for p in POLICIES}
        for symbol in ALL_ELIGIBLE_NSE_BANKS:
            s = snapshots.get(symbol)
            if not s:
                print(f"{symbol:<12} NO SNAPSHOT")
                continue
            quarantined = await _has_quarantined_or_implausible_facts(db, symbol)
            evals = {}
            for policy in POLICIES:
                r = evaluate_eligibility(
                    financial_strength_score=s.financial_strength, financial_coverage_pct=s.financial_coverage_pct,
                    overall_coverage_pct=s.coverage_pct, financial_data_as_of=s.financial_data_as_of, policy=policy,
                )
                evals[policy.name] = r
                results_by_policy[policy.name].append((symbol, r))

            stale_flag = "" if s.financial_data_as_of == mode_period or s.financial_data_as_of is None else "*"
            fm = evals[POLICIES[0].name].financial_metrics_used
            fm_pct = evals[POLICIES[0].name].financial_metrics_used_pct
            print(
                f"{symbol:<12}{fm:>11}{fm_pct:>10.1f}"
                f"{(s.valuation_coverage_pct if s.valuation_coverage_pct is not None else -1):>9.1f}"
                f"{(s.market_behaviour_coverage_pct if s.market_behaviour_coverage_pct is not None else -1):>9.1f}"
                f"{(s.current_intelligence_coverage_pct if s.current_intelligence_coverage_pct is not None else -1):>8.1f}"
                f"{s.coverage_pct:>9.1f}  {(s.financial_data_as_of or '—') + stale_flag:>12}  {'YES' if quarantined else '':>12}  "
                f"{'Y' if evals[POLICIES[0].name].eligible else 'N':>6}"
                f"{'Y' if evals[POLICIES[1].name].eligible else 'N':>6}"
                f"{'Y' if evals[POLICIES[2].name].eligible else 'N':>6}"
            )

        print("\n(-1 in a coverage column = pillar was INSUFFICIENT/no score; * next to FinDataAsOf = differs from the population mode)\n")

        print("=== Candidate policy summary ===\n")
        for policy in POLICIES:
            evs = [r for _, r in results_by_policy[policy.name]]
            eligible_count = sum(1 for r in evs if r.eligible)
            print(f"{policy.name}: {eligible_count}/{len(evs)} real banks eligible")
            reason_counts = collections.Counter(r for e in evs for r in e.reasons)
            for reason, count in reason_counts.most_common():
                print(f"    {reason}: {count} banks")
            print()

        print("=== Metric-count distribution across all 27 real banks ===\n")
        counts = collections.Counter(evaluate_eligibility(
            financial_strength_score=s.financial_strength, financial_coverage_pct=s.financial_coverage_pct,
            overall_coverage_pct=s.coverage_pct, financial_data_as_of=s.financial_data_as_of,
            policy=POLICIES[0],
        ).financial_metrics_used for s in snapshots.values())
        for n in range(8):
            print(f"  {n}/7 real metrics used: {counts.get(n, 0)} banks")


if __name__ == "__main__":
    asyncio.run(main())
