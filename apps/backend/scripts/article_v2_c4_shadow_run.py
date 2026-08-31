"""
Article V2 Phase C4 — full-funnel shadow validation run (owner
authorization, 2026-08-31). Runs the ENTIRE original 120-event
EventTriage cohort through the real C1 -> C2 -> C3 -> C4 chain, not
just survivors -- this is the first real end-to-end funnel report.
Writes NOTHING anywhere. Prints the complete funnel, every single
FULL_ARTICLE result in full (expected to be few enough for real manual
inspection), and a representative sample of FACTUAL_UPDATE and SKIP.
"""
from __future__ import annotations

import asyncio
import sys
from collections import Counter

sys.path.insert(0, ".")

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from sqlalchemy import select

from app.db.models.intelligence import EventTriage
from app.db.session import AsyncSessionLocal
from app.services.article_v2.candidate_gate import CANDIDATE, SKIP as C1_SKIP, UPDATE_CANDIDATE, evaluate_candidate
from app.services.article_v2.context_builder import build_context
from app.services.article_v2.decision_engine import FACTUAL_UPDATE, FULL_ARTICLE, SKIP as C4_SKIP, decide
from app.services.article_v2.evidence_set_builder import ArticleEvidenceSet, INSUFFICIENT, build_evidence_set

SAMPLE_SIZE = 120


async def main() -> None:
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            select(EventTriage).order_by(EventTriage.triaged_at.desc()).limit(SAMPLE_SIZE * 2)
        )).scalars().all()
    with_ticker = [r for r in rows if r.tickers][:SAMPLE_SIZE]
    no_ticker_count = len([r for r in rows if not r.tickers])

    print(f"=== Article V2 full funnel: C1 -> C2 -> C3 -> C4 over {len(with_ticker)} real events ===\n")

    c1_outcomes: Counter[str] = Counter()
    c2_status: Counter[str] = Counter()
    c4_content_type: Counter[str] = Counter()
    c4_publication_action: Counter[str] = Counter()
    c4_reason_codes: Counter[str] = Counter()
    decisions = []

    for row in with_ticker:
        symbol = row.tickers[0]
        async with AsyncSessionLocal() as db:
            candidate = await evaluate_candidate(db, symbol=symbol, event_headline=row.headline, event_id=row.event_id)
        c1_outcomes[candidate.outcome] += 1

        if candidate.outcome == C1_SKIP:
            empty_es = ArticleEvidenceSet(
                entity_id=candidate.entity_id, symbol=candidate.symbol, event_id=row.event_id,
                event_headline=row.headline, status=INSUFFICIENT, primary_evidence=None,
            )
            decision = decide(candidate, empty_es, None)
        else:
            async with AsyncSessionLocal() as db:
                es = await build_evidence_set(db, symbol=symbol, event_headline=row.headline, event_id=row.event_id)
            c2_status[es.status] += 1
            ctx = None
            if es.primary_evidence is not None:
                async with AsyncSessionLocal() as db:
                    ctx = await build_context(db, es)
            decision = decide(candidate, es, ctx)

        c4_content_type[decision.content_type] += 1
        c4_publication_action[decision.publication_action] += 1
        for code in decision.reason_codes:
            c4_reason_codes[code] += 1
        decisions.append((row, candidate, decision))

    print(f"=== FULL FUNNEL ===")
    print(f"  raw events sampled (most recent {SAMPLE_SIZE * 2}):    {SAMPLE_SIZE * 2}")
    print(f"  events with a real ticker:                              {len(with_ticker)}")
    print(f"  events with no ticker (never gated, reported separately): {no_ticker_count}")
    print()
    print(f"  C1 outcomes:")
    for outcome, count in c1_outcomes.most_common():
        print(f"    {outcome:<17} {count:>4}")
    print()
    print(f"  C2 status (of the {sum(c2_status.values())} that reached C2):")
    for status, count in c2_status.most_common():
        print(f"    {status:<14} {count:>4}")
    print()
    print(f"  C4 content_type (final editorial decision, all {len(with_ticker)} events):")
    for ct, count in c4_content_type.most_common():
        print(f"    {ct:<15} {count:>4}  ({100.0*count/len(with_ticker):5.1f}%)")
    print()
    print(f"  C4 publication_action:")
    for pa, count in c4_publication_action.most_common():
        print(f"    {pa:<15} {count:>4}")
    print()
    print(f"  C4 reason codes (a decision can carry more than one):")
    for code, count in c4_reason_codes.most_common():
        print(f"    {code:<28} {count:>4}")

    full_articles = [(r, c, d) for r, c, d in decisions if d.content_type == FULL_ARTICLE]
    factual_updates = [(r, c, d) for r, c, d in decisions if d.content_type == FACTUAL_UPDATE]
    skips = [(r, c, d) for r, c, d in decisions if d.content_type == C4_SKIP]

    print(f"\n\n=== EVERY FULL_ARTICLE result ({len(full_articles)}) -- full detail for manual inspection ===")
    for row, candidate, decision in full_articles:
        print(f"\n  symbol={decision.symbol}  event_id={decision.event_id}")
        print(f"  headline: {row.headline!r}")
        print(f"  C1 top_evidence_score={candidate.top_evidence_score}  reasons={candidate.top_evidence_reasons}")
        print(f"  C4 reason_codes={decision.reason_codes}")
        print(f"  C4 reason_detail: {decision.reason_detail}")

    print(f"\n\n=== FACTUAL_UPDATE sample (10 of {len(factual_updates)}) ===")
    for row, candidate, decision in factual_updates[:10]:
        print(f"  {decision.symbol:<12} action={decision.publication_action:<15} reasons={decision.reason_codes}  {row.headline[:80]!r}")

    print(f"\n=== SKIP sample (10 of {len(skips)}) ===")
    for row, candidate, decision in skips[:10]:
        print(f"  {decision.symbol:<12} reasons={decision.reason_codes}  {row.headline[:80]!r}")


if __name__ == "__main__":
    asyncio.run(main())
