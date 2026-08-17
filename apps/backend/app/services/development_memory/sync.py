"""
Development Memory sync — the standalone job that feeds identity.py's
matching lifecycle. Deliberately NOT run from any of the 3 existing
evidence_clustering call sites (Opportunity Radar, AI Search V2/V3,
Weekend Intelligence aggregator) — those need low-latency per-request
counts, not write-path risk, and Weekend Intelligence only runs Sat/Sun
while Developments need to form every day. Reuses the exact evidence-
collection function Weekend Intelligence already built
(collect_evidence_since) rather than a new one.

Windows overlap by design (LOOKBACK > the job's own schedule interval)
instead of tracking "since last run" state — resolve_development's
evidence_key existence check makes re-processing the same evidence a safe
no-op (see identity.py's "existing" tier), so overlap just trades a
little redundant work for never needing persisted job-run state or
worrying about a missed/late run leaving a real gap.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.development import Development
from app.services.development_memory.graph_link import link_development_to_graph
from app.services.development_memory.identity import resolve_development, sweep_close_stale
from app.services.development_memory.prediction_recording import record_development_prediction
from app.services.weekend_intelligence.evidence_window import collect_evidence_since

LOOKBACK = timedelta(hours=2)  # > the 30-60min schedule interval in scheduler.py — deliberate overlap, see module docstring


async def sync_development_memory(db: AsyncSession) -> dict:
    until = datetime.now(timezone.utc)
    since = until - LOOKBACK
    failed_sources: list[str] = []
    evidence = await collect_evidence_since(db, since, until, failed_sources=failed_sources)

    created = 0
    merged = 0
    already_attached = 0
    tier_counts: dict[str, int] = {}
    touched_development_ids: set[str] = set()
    for item in evidence:
        result = await resolve_development(db, item)
        tier_counts[result.tier] = tier_counts.get(result.tier, 0) + 1
        if result.created:
            created += 1
        elif result.tier == "existing":
            already_attached += 1
        else:
            merged += 1
        if result.tier != "existing":
            touched_development_ids.add(result.development.id)

    await db.commit()

    # Phase 6B — graph linking runs as a distinct pass after evidence
    # resolution, not inline per-item: is_graph_worthy() depends on the
    # Development's final evidence_count for this run, which isn't settled
    # until all of this run's evidence has been merged in.
    graph_linked = 0
    predictions_recorded = 0
    for dev_id in touched_development_ids:
        dev = await db.get(Development, dev_id)
        if dev is None:
            await db.commit()  # DO NOT REMOVE — see the comment below; applies here too
            continue
        node_id = await link_development_to_graph(db, dev)
        if node_id:
            dev.ig_node_id = node_id
            graph_linked += 1
        # Phase 6C V1 — shadow-mode predictions, same loop iteration so
        # `dev` doesn't need a second fetch. record_development_prediction()
        # is its own idempotent no-op on repeat calls (query-based dedup),
        # so calling it every sync run for every touched Development is
        # safe and matches this loop's existing per-iteration shape.
        prediction_id = await record_development_prediction(db, dev)
        if prediction_id:
            predictions_recorded += 1
        # DO NOT REMOVE, DO NOT batch this outside the loop — commit
        # per-Development, not once at the end. link_development_to_graph()
        # and record_development_prediction() each open/commit their own
        # AsyncSessionLocal() per upsert_node()/upsert_edge()/
        # store_prediction() call (see graph_link.py's module docstring);
        # on SQLite, a writer can't get its exclusive lock while `db` here
        # still holds an open transaction. Closing this iteration's
        # transaction out now, before the next iteration's db.get()/
        # upserts, is what actually avoids "database is locked" —
        # confirmed live against 86 real Developments. Moving this commit
        # back outside the loop (e.g. "to reduce commits") reintroduces
        # the bug.
        await db.commit()

    closed = await sweep_close_stale(db)
    await db.commit()

    return {
        "evidence_seen": len(evidence),
        "developments_created": created,
        "evidence_merged": merged,
        "evidence_already_attached": already_attached,
        "developments_closed": closed,
        "developments_graph_linked": graph_linked,
        "predictions_recorded": predictions_recorded,
        "failed_sources": failed_sources,
        "tier_counts": tier_counts,
    }
