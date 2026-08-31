"""
Article V2 Phase C2 — shadow validation run (owner authorization,
2026-08-31). Re-derives the exact same 23 real CANDIDATE events C1.1
produced from the same 120-event EventTriage cohort (deterministic given
unchanged DB state and unchanged C1 code), then runs the real C2
Evidence Set Builder against each. Writes NOTHING. Prints full per-event
detail plus the exact summary statistics requested: usable/coherent vs
partial/insufficient sets, primary evidence source distribution, average
raw vs deduplicated-accepted evidence count, DIFFERENT_DEVELOPMENT/
DUPLICATE_EVIDENCE/STALE_CONTEXT exclusion counts, conflicts detected,
and named examples of both successful noise removal and successful
multi-source corroboration.
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
from app.services.article_v2.evidence_set_builder import (
    COHERENT, DIFFERENT_DEVELOPMENT, DUPLICATE_EVIDENCE, INSUFFICIENT, PARTIAL,
    STALE_CONTEXT, build_evidence_set,
)

SAMPLE_SIZE = 120


async def main() -> None:
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            select(EventTriage).order_by(EventTriage.triaged_at.desc()).limit(SAMPLE_SIZE * 2)
        )).scalars().all()
    with_ticker = [r for r in rows if r.tickers][:SAMPLE_SIZE]

    print(f"=== Re-deriving the C1.1 CANDIDATE cohort from the same {len(with_ticker)}-event sample ===\n")
    candidates: list[tuple] = []
    for row in with_ticker:
        symbol = row.tickers[0]
        async with AsyncSessionLocal() as db:
            decision = await evaluate_candidate(db, symbol=symbol, event_headline=row.headline, event_id=row.event_id)
        if decision.outcome == CANDIDATE:
            candidates.append((symbol, row.headline, row.event_id))
    print(f"Re-derived {len(candidates)} real CANDIDATE events (expect 23, matching C1.1's own report).\n")

    print(f"=== Article V2 Phase C2 shadow run: {len(candidates)} real candidates ===\n")

    status_counts: Counter[str] = Counter()
    primary_source_counts: Counter[str] = Counter()
    exclusion_reason_counts: Counter[str] = Counter()
    raw_counts, accepted_counts = [], []
    conflict_events = []
    noise_removed_examples = []
    multi_source_examples = []

    for symbol, headline, event_id in candidates:
        async with AsyncSessionLocal() as db:
            try:
                es = await build_evidence_set(db, symbol=symbol, event_headline=headline, event_id=event_id)
            except Exception as e:
                print(f"  ERROR building evidence set for {symbol}: {e}")
                continue

        status_counts[es.status] += 1
        raw_counts.append(es.raw_evidence_count)
        accepted = (1 if es.primary_evidence else 0) + len(es.supporting_evidence)
        accepted_counts.append(accepted)
        if es.primary_evidence:
            primary_source_counts[es.primary_evidence.source_type] += 1
        for e in es.excluded_evidence:
            exclusion_reason_counts[e.reason_code] += 1
        if es.conflicts:
            conflict_events.append((symbol, headline, es.conflicts))
        different_dev_excluded = [e for e in es.excluded_evidence if e.reason_code == DIFFERENT_DEVELOPMENT]
        if different_dev_excluded and es.primary_evidence:
            noise_removed_examples.append((symbol, headline, es.primary_evidence, different_dev_excluded))
        if len(es.supporting_evidence) >= 2:
            multi_source_examples.append((symbol, headline, es.primary_evidence, es.supporting_evidence))

        print(
            f"[{es.status:<12}] symbol={symbol:<12} raw={es.raw_evidence_count:<3} "
            f"accepted={accepted:<3} excluded={len(es.excluded_evidence):<3} "
            f"conflicts={len(es.conflicts)}  primary_source={es.primary_evidence.source_type if es.primary_evidence else '-'}"
        )
        print(f"    headline: {headline[:110]!r}")
        if es.primary_evidence:
            print(f"    primary : [{es.primary_evidence.source_type}] {es.primary_evidence.title[:100]!r}")
        for s in es.supporting_evidence:
            print(f"    support : [{s.source_type}] {s.title[:100]!r}")
        for e in es.excluded_evidence:
            print(f"    excluded [{e.reason_code}]: {e.evidence.title[:90]!r}")
        for c in es.conflicts:
            print(f"    CONFLICT [{c.kind}]: values={c.values} evidence_ids={c.evidence_ids}")
        print()

    n = len(candidates)
    print(f"\n\n=== Status distribution ({n} candidates) ===")
    for status, count in status_counts.most_common():
        print(f"  {status:<14} {count:>4}  ({100.0*count/n:5.1f}%)")

    print(f"\n=== Primary evidence source distribution ===")
    for src, count in primary_source_counts.most_common():
        print(f"  {src:<10} {count:>4}")

    print(f"\n=== Evidence counts ===")
    print(f"  average raw evidence per candidate:      {sum(raw_counts)/n:.2f}")
    print(f"  average deduplicated-accepted per candidate: {sum(accepted_counts)/n:.2f}")

    print(f"\n=== Exclusion reason breakdown ===")
    for code, count in exclusion_reason_counts.most_common():
        print(f"  {code:<22} {count:>4}")

    print(f"\n=== Conflicts detected: {len(conflict_events)} candidate(s) ===")
    for symbol, headline, conflicts in conflict_events:
        print(f"  {symbol}: {headline[:80]!r}")
        for c in conflicts:
            print(f"    -> {c.detail}")

    print(f"\n=== Examples: same-company-unrelated-evidence successfully removed (up to 5) ===")
    for symbol, headline, primary, excluded in noise_removed_examples[:5]:
        print(f"  {symbol}: {headline[:80]!r}")
        print(f"    kept primary: {primary.title[:90]!r}")
        for e in excluded:
            print(f"    removed ({e.reason_code}): {e.evidence.title[:90]!r}")

    print(f"\n=== Examples: multiple genuinely corroborating sources retained (up to 5) ===")
    for symbol, headline, primary, supporting in multi_source_examples[:5]:
        print(f"  {symbol}: {headline[:80]!r}")
        print(f"    primary: [{primary.source_type}] {primary.title[:90]!r}")
        for s in supporting:
            print(f"    support: [{s.source_type}] {s.title[:90]!r}")


if __name__ == "__main__":
    asyncio.run(main())
