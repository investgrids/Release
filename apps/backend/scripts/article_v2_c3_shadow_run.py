"""
Article V2 Phase C3 — shadow validation run (owner authorization,
2026-08-31). Re-derives the exact same 23 real C1.1 CANDIDATEs, runs the
real C2 Evidence Set Builder on each, filters to the 19 C2-usable sets
(8 COHERENT + 11 PARTIAL -- the 4 INSUFFICIENT ones deliberately never
reach C3, per explicit instruction), then runs the real C3 Context
Builder against each of those 19. Writes NOTHING. Prints full per-event
detail plus the exact summary the owner asked for: context availability
by event family, FinancialFacts considered vs. accepted, examples of
irrelevant facts correctly rejected, market-reaction availability,
historical/prior-period availability, and anywhere C3 was tempted to
infer more than the sources support (there is no such mechanism in this
module by construction, but the report says so explicitly rather than
assuming it).
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
from app.services.article_v2.candidate_gate import CANDIDATE, evaluate_candidate
from app.services.article_v2.context_builder import AVAILABLE, NONE_STATUS, PARTIAL, build_context
from app.services.article_v2.evidence_set_builder import build_evidence_set

SAMPLE_SIZE = 120


async def main() -> None:
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            select(EventTriage).order_by(EventTriage.triaged_at.desc()).limit(SAMPLE_SIZE * 2)
        )).scalars().all()
    with_ticker = [r for r in rows if r.tickers][:SAMPLE_SIZE]

    print("=== Re-deriving the C1.1 CANDIDATE cohort, then the C2-usable subset ===\n")
    usable = []
    for row in with_ticker:
        symbol = row.tickers[0]
        async with AsyncSessionLocal() as db:
            decision = await evaluate_candidate(db, symbol=symbol, event_headline=row.headline, event_id=row.event_id)
        if decision.outcome != CANDIDATE:
            continue
        async with AsyncSessionLocal() as db:
            es = await build_evidence_set(db, symbol=symbol, event_headline=row.headline, event_id=row.event_id)
        if es.primary_evidence is not None:
            usable.append(es)
    print(f"Re-derived {len(usable)} C2-usable evidence sets (expect 19: 8 COHERENT + 11 PARTIAL).\n")

    print(f"=== Article V2 Phase C3 shadow run: {len(usable)} usable evidence sets ===\n")

    status_counts: Counter[str] = Counter()
    family_counts: Counter[str] = Counter()
    family_status: dict[str, Counter] = {}
    total_facts_considered = 0
    total_facts_accepted = 0
    market_reaction_available = 0
    prior_period_available = 0
    rejected_examples = []

    for es in usable:
        async with AsyncSessionLocal() as db:
            try:
                ctx = await build_context(db, es)
            except Exception as e:
                print(f"  ERROR building context for {es.symbol}: {e}")
                continue

        status_counts[ctx.status] += 1
        fam_key = ",".join(ctx.matched_event_families) if ctx.matched_event_families else "UNRECOGNIZED"
        family_counts[fam_key] += 1
        family_status.setdefault(fam_key, Counter())[ctx.status] += 1
        total_facts_accepted += len(ctx.financial_context)
        for r in ctx.omitted_reasons:
            if "were NOT selected" in r:
                # parse the count out of the reason string's own prefix
                try:
                    total_facts_considered += int(r.split(" ")[0])
                except ValueError:
                    pass
                rejected_examples.append((es.symbol, r))
        if ctx.market_reaction is not None:
            market_reaction_available += 1
        if any(f.prior_period_value is not None for f in ctx.financial_context):
            prior_period_available += 1

        print(f"[{ctx.status:<10}] symbol={es.symbol:<12} families={fam_key:<20} facts={len(ctx.financial_context)} market_reaction={'yes' if ctx.market_reaction else 'no'}")
        print(f"    headline: {es.event_headline[:100]!r}")
        for f in ctx.financial_context:
            trend = f" (prior {f.prior_period_label}={f.prior_period_value})" if f.prior_period_value is not None else ""
            print(f"    fact: {f.metric_code}={f.value} {f.unit} [{f.fiscal_year}Q{f.fiscal_quarter or '-'}]{trend}")
        if ctx.market_reaction:
            print(f"    market: {ctx.market_reaction.price_move_pct:+.2f}% -- {ctx.market_reaction.note}")
        for r in ctx.omitted_reasons:
            print(f"    omitted: {r}")
        print()

    total_facts_accepted_plus_considered = total_facts_accepted + total_facts_considered

    print(f"\n\n=== Status distribution ({len(usable)} usable sets) ===")
    for status, count in status_counts.most_common():
        print(f"  {status:<10} {count:>4}  ({100.0*count/len(usable):5.1f}%)")

    print(f"\n=== Context availability by event family ===")
    for fam, count in family_counts.most_common():
        statuses = family_status[fam]
        print(f"  {fam:<20} {count:>4}  -> {dict(statuses)}")

    print(f"\n=== FinancialFacts: considered vs accepted ===")
    print(f"  total accepted (event-relevant, quality-passed): {total_facts_accepted}")
    print(f"  total explicitly rejected as irrelevant (real facts existed, wrong family): {total_facts_considered}")

    print(f"\n=== Market reaction availability: {market_reaction_available}/{len(usable)} ===")
    print(f"=== Prior-period trend availability: {prior_period_available}/{len(usable)} ===")

    print(f"\n=== Examples: real facts correctly rejected as irrelevant (up to 8) ===")
    for symbol, reason in rejected_examples[:8]:
        print(f"  {symbol}: {reason}")

    print(f"\n=== Explicit note on inference beyond sources ===")
    print("  This module has no free-text generation or LLM call anywhere -- there is no mechanism by")
    print("  which it could infer beyond what FinancialFact/price data literally states. Every omission")
    print("  above is a real, logged reason, not a silent gap.")


if __name__ == "__main__":
    asyncio.run(main())
