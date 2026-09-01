"""
Article V2 Phase C5 — shadow validation run (owner authorization,
2026-08-31). Runs the real C1 -> C2 -> C3 -> C4 -> C5 chain over the
same 120-event cohort. Because C4 produced only 1 FULL_ARTICLE + 18
FACTUAL_UPDATE (19 total proposed public outputs), every one of them is
run through C5's identity + uniqueness + headline generation and printed
in full for manual inspection. Writes NOTHING -- no Newsroom record, no
DB mutation. Real LLM calls for headline generation (this is C5's own,
explicitly authorized exception to the "no LLM" rule of C1-C4).
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
from app.services.article_v2.context_builder import build_context
from app.services.article_v2.decision_engine import FACTUAL_UPDATE, FULL_ARTICLE, decide
from app.services.article_v2.evidence_set_builder import build_evidence_set
from app.services.article_v2.headline_engine import ValidationOutcome, generate_headline
from app.services.article_v2.identity import CREATE_NEW, NO_PUBLICATION, UPDATE_EXISTING, compute_identity, resolve_uniqueness

SAMPLE_SIZE = 120


async def main() -> None:
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            select(EventTriage).order_by(EventTriage.triaged_at.desc()).limit(SAMPLE_SIZE * 2)
        )).scalars().all()
    with_ticker = [r for r in rows if r.tickers][:SAMPLE_SIZE]

    print("=== Re-deriving the 19 real C4-proposed outputs (1 FULL_ARTICLE + 18 FACTUAL_UPDATE) ===\n")
    proposals = []
    for row in with_ticker:
        symbol = row.tickers[0]
        async with AsyncSessionLocal() as db:
            candidate = await evaluate_candidate(db, symbol=symbol, event_headline=row.headline, event_id=row.event_id)
        if candidate.outcome != CANDIDATE:
            continue
        async with AsyncSessionLocal() as db:
            es = await build_evidence_set(db, symbol=symbol, event_headline=row.headline, event_id=row.event_id)
        if es.primary_evidence is None:
            continue
        ctx = None
        async with AsyncSessionLocal() as db:
            ctx = await build_context(db, es)
        decision = decide(candidate, es, ctx)
        if decision.content_type in (FULL_ARTICLE, FACTUAL_UPDATE):
            proposals.append((row, candidate, es, ctx, decision))

    print(f"Re-derived {len(proposals)} proposed outputs (expect 19).\n")
    print(f"=== Article V2 Phase C5 shadow run: {len(proposals)} candidates through Identity -> Uniqueness -> Headline ===\n")

    known_identities: dict[str, str] = {}
    known_headlines: dict[str, str] = {}
    identity_type_counts: Counter[str] = Counter()
    publication_action_counts: Counter[str] = Counter()
    headline_status_counts: Counter[str] = Counter()
    total_attempts = 0
    all_final_h1s = []
    all_identity_keys: set[str] = set()
    collisions = 0

    for i, (row, candidate, es, ctx, decision) in enumerate(proposals, start=1):
        identity = compute_identity(es)
        resolution = resolve_uniqueness(
            identity, c4_publication_action=decision.publication_action,
            c4_matched_article_id=None, known_identities=known_identities,
        )
        identity_type_counts[identity.development_type] += 1
        publication_action_counts[resolution.publication_action] += 1
        all_identity_keys.add(identity.identity_key)
        if resolution.matched_identity_key:
            collisions += 1

        headline_result = None
        if resolution.publication_action in (CREATE_NEW, UPDATE_EXISTING):
            headline_result = await generate_headline(es, ctx, identity, other_accepted_headlines=known_headlines)
            headline_status_counts[headline_result.status] += 1
            total_attempts += headline_result.attempts
            if headline_result.h1:
                known_headlines[identity.identity_key] = headline_result.h1
                all_final_h1s.append((identity, headline_result.h1, decision.content_type, resolution.publication_action))

        if resolution.publication_action == CREATE_NEW:
            known_identities[identity.identity_key] = f"batch-item-{i}-{es.symbol}"

        print(f"[{i:2}] symbol={es.symbol:<12} content_type={decision.content_type:<15} pub_action={resolution.publication_action:<15}")
        print(f"     identity: entity={identity.entity_id} type={identity.development_type} anchor={identity.anchor} time={identity.time_bucket}")
        print(f"     resolution reason: {resolution.reason}")
        if headline_result:
            print(f"     headline [{headline_result.status}, attempts={headline_result.attempts}]: {headline_result.h1!r}")
            if headline_result.validation_notes:
                print(f"     validation notes: {headline_result.validation_notes}")
        print()

    print(f"\n\n=== Summary ({len(proposals)} candidates) ===")
    print(f"  unique ArticleIdentities: {len(all_identity_keys)}")
    print(f"  in-batch identity collisions (same real development, multiple triggering events): {collisions}")
    print(f"  development_type distribution:")
    for dt, count in identity_type_counts.most_common():
        print(f"    {dt:<20} {count:>3}")
    print(f"\n  publication_action distribution:")
    for pa, count in publication_action_counts.most_common():
        print(f"    {pa:<16} {count:>3}")
    print(f"\n  headline status distribution:")
    for status, count in headline_status_counts.most_common():
        print(f"    {status:<10} {count:>3}")
    print(f"\n  total LLM attempts across all headline generations: {total_attempts}")

    print(f"\n=== ALL FINAL PROPOSED H1s ({len(all_final_h1s)}) ===")
    for identity, h1, content_type, pub_action in all_final_h1s:
        print(f"  [{content_type:<14}/{pub_action:<11}] {identity.symbol:<12} {h1!r}")

    print(f"\n=== Cross-identity headline similarity check (misleadingly similar headlines for DIFFERENT identities) ===")
    from app.services.aipe.duplicate_detector import _jaccard, _tokenize
    found_any = False
    for i in range(len(all_final_h1s)):
        for j in range(i + 1, len(all_final_h1s)):
            id_a, h_a, _, _ = all_final_h1s[i]
            id_b, h_b, _, _ = all_final_h1s[j]
            if id_a.identity_key == id_b.identity_key:
                continue
            sim = _jaccard(_tokenize(h_a), _tokenize(h_b))
            if sim >= 0.3:
                found_any = True
                print(f"  similarity={sim:.2f}  {id_a.symbol!r} {h_a!r}  vs  {id_b.symbol!r} {h_b!r}")
    if not found_any:
        print("  none found above 0.30 Jaccard -- no misleadingly similar headlines across different identities.")


if __name__ == "__main__":
    asyncio.run(main())
