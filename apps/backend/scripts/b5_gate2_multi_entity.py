"""
B.5 Gate 2 -- multi-entity run, per owner's explicit 2026-08-30 evening
instruction: "For each entity in a multi-company RSS story, evidence
must independently correspond to the event; don't allow one company's
confirmed filing to implicitly validate every company mentioned."

Reuses run_gate2_for_item() from b5_gate2_event_matching.py UNCHANGED --
the only difference from the single-entity run is that this iterates
every entity in a Gate 1 multi-match separately against the SAME RSS
text and reports a per-entity verdict, never a single item-level
verdict. A multi-company story where 3 of 4 companies have confirmed
evidence and 1 doesn't produces 3 PASS + 1 FAIL, not "PASS" for the
whole item.
"""
from __future__ import annotations

import asyncio
import pickle
import sys

sys.path.insert(0, ".")

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.db.models.raw_evidence import RawEvidence
from b5_gate2_event_matching import load_nse_candidates_by_entity, run_gate2_for_item


async def main() -> None:
    with open("b5_resolver_results_v4.pkl", "rb") as f:
        gate1_results = pickle.load(f)
    async with AsyncSessionLocal() as db:
        rss_rows = {r.id: r.published_at for r in
                    (await db.execute(select(RawEvidence.id, RawEvidence.published_at)
                                       .where(RawEvidence.source_type == "rss"))).all()}
    nse_by_entity = await load_nse_candidates_by_entity()

    multi = [r for r in gate1_results if len(r["matches"]) >= 2]
    outcomes = []
    for r in multi:
        rss_text = f"{r['title']} {r['summary']}"
        published_at = rss_rows.get(r["id"])
        for m in r["matches"]:
            entity_id = m["entity_id"]
            result = run_gate2_for_item(rss_text, published_at, entity_id, nse_by_entity)
            outcomes.append({
                "rss_id": r["id"], "title": r["title"], "entity_id": entity_id,
                "entity_matched_text": m["matched_text"],
                "other_entities_in_story": [x["entity_id"] for x in r["matches"] if x["entity_id"] != entity_id],
                **result,
            })

    passed = [o for o in outcomes if o["status"] == "PASS"]
    failed = [o for o in outcomes if o["status"] == "FAIL"]
    print(f"multi-entity stories: {len(multi)}, per-entity Gate 2 checks run: {len(outcomes)}")
    print(f"  PASS: {len(passed)}")
    print(f"  FAIL: {len(failed)}")

    # Stories where entities within the SAME story got DIFFERENT verdicts
    # -- direct proof the per-entity independence requirement is doing
    # real work, not just theoretically possible.
    by_story: dict[str, set[str]] = {}
    for o in outcomes:
        by_story.setdefault(o["rss_id"], set()).add(o["status"])
    mixed_stories = [sid for sid, statuses in by_story.items() if len(statuses) > 1]
    print(f"  stories with a MIXED verdict across their own entities: {len(mixed_stories)}")

    with open("b5_gate2_multi_results.pkl", "wb") as f:
        pickle.dump(outcomes, f)
    with open("b5_gate2_multi_mixed.txt", "w", encoding="utf-8") as out:
        out.write(f"mixed-verdict stories: {len(mixed_stories)}\n\n")
        for sid in mixed_stories:
            story_outcomes = [o for o in outcomes if o["rss_id"] == sid]
            out.write(f"TITLE: {story_outcomes[0]['title']}\n")
            for o in story_outcomes:
                out.write(f"  entity={o['entity_id']} matched={o['entity_matched_text']!r} -> {o['status']} ({o.get('reason') or o.get('method')})\n")
            out.write("\n")
    print("done -- b5_gate2_multi_results.pkl, b5_gate2_multi_mixed.txt")


if __name__ == "__main__":
    asyncio.run(main())
