"""
Article V2 Phase C1 — shadow validation run (owner authorization,
2026-08-31). Runs the real Candidate Gate against a real, recent sample
of EventTriage rows -- the same real production candidate stream
run_aipe_cycle itself reads via market_story_engine.get_high_urgency_triage().
Writes NOTHING -- no article, no candidate-run record, no DB mutation of
any kind. Prints a full per-event log plus a distribution summary for
manual inspection.

Sample selection: the most recent EventTriage rows with a real, non-empty
`tickers` list, most-recent-first, capped at `SAMPLE_SIZE`. Rows with no
ticker at all are a real, distinct, honest category (there's no company
to gate against) and are reported separately, not silently dropped and
not force-fit into the gate.
"""
from __future__ import annotations

import asyncio
import sys
from collections import Counter

sys.path.insert(0, ".")

# Real NSE/RSS headlines routinely carry non-ASCII characters (Rupee sign,
# smart quotes, dashes) that Windows' default console codepage (cp1252)
# can't display -- reconfigure stdout to UTF-8 so the run completes and
# prints correctly rather than crashing partway through a long real
# sample. Not a functional change to the gate itself.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from sqlalchemy import select

from app.db.models.intelligence import EventTriage
from app.db.session import AsyncSessionLocal
from app.services.article_v2.candidate_gate import evaluate_candidate

SAMPLE_SIZE = 120


async def main() -> None:
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            select(EventTriage).order_by(EventTriage.triaged_at.desc()).limit(SAMPLE_SIZE * 2)
        )).scalars().all()

    no_ticker = [r for r in rows if not r.tickers]
    with_ticker = [r for r in rows if r.tickers][:SAMPLE_SIZE]

    print(f"=== Article V2 Phase C1 shadow run: {len(with_ticker)} real events with a ticker "
          f"(+ {len(no_ticker)} skipped for having none, reported separately below) ===\n")

    outcomes: Counter[str] = Counter()
    reason_codes: Counter[str] = Counter()
    records: list[dict] = []

    for row in with_ticker:
        symbol = row.tickers[0]
        async with AsyncSessionLocal() as db:
            try:
                decision = await evaluate_candidate(
                    db, symbol=symbol, event_headline=row.headline, event_id=row.event_id,
                )
            except Exception as e:
                print(f"  ERROR gating event_id={row.event_id} symbol={symbol}: {e}")
                continue

        outcomes[decision.outcome] += 1
        reason_codes[decision.reason_code] += 1
        records.append({
            "event_id": row.event_id, "symbol": symbol, "headline": row.headline,
            "urgency": row.urgency, "importance": row.importance, "market_impact": row.market_impact,
            "outcome": decision.outcome, "reason_code": decision.reason_code,
            "evidence_count": decision.evidence_count, "top_evidence_score": decision.top_evidence_score,
            "matched_article_id": decision.matched_article_id,
        })
        print(
            f"[{decision.outcome:<17}] [{decision.reason_code:<20}] "
            f"symbol={symbol:<12} evidence={decision.evidence_count:<3} "
            f"score={decision.top_evidence_score!s:<6} "
            f"headline={row.headline[:90]!r}"
        )

    print(f"\n\n=== Distribution ({len(with_ticker)} real events gated) ===")
    for outcome, count in outcomes.most_common():
        pct = 100.0 * count / len(with_ticker) if with_ticker else 0.0
        print(f"  {outcome:<17} {count:>4}  ({pct:5.1f}%)")

    print(f"\n=== Reason code breakdown ===")
    for code, count in reason_codes.most_common():
        pct = 100.0 * count / len(with_ticker) if with_ticker else 0.0
        print(f"  {code:<22} {count:>4}  ({pct:5.1f}%)")

    print(f"\n=== No-ticker events (reported, not gated): {len(no_ticker)} ===")
    for row in no_ticker[:10]:
        print(f"  event_id={row.event_id}  headline={row.headline[:90]!r}")
    if len(no_ticker) > 10:
        print(f"  ... and {len(no_ticker) - 10} more")

    print(f"\n=== CANDIDATE examples (up to 8) ===")
    for r in [r for r in records if r["outcome"] == "CANDIDATE"][:8]:
        print(f"  {r['symbol']:<12} score={r['top_evidence_score']}  {r['headline'][:100]!r}")

    print(f"\n=== UPDATE_CANDIDATE examples (up to 8) ===")
    for r in [r for r in records if r["outcome"] == "UPDATE_CANDIDATE"][:8]:
        print(f"  {r['symbol']:<12} matched_article={r['matched_article_id']}  {r['headline'][:100]!r}")

    print(f"\n=== SKIP examples by reason (up to 5 each) ===")
    for code in ["ENTITY_UNRESOLVED", "INSUFFICIENT_EVIDENCE", "LOW_MATERIALITY"]:
        examples = [r for r in records if r["outcome"] == "SKIP" and r["reason_code"] == code][:5]
        if examples:
            print(f"  -- {code} --")
            for r in examples:
                print(f"    {r['symbol']:<12} evidence={r['evidence_count']}  {r['headline'][:100]!r}")


if __name__ == "__main__":
    asyncio.run(main())
