"""
B.5 Gate 2 failure-cause audit, per owner's explicit instruction: don't
change the algorithm before understanding WHY the 85 single-entity
failures happened. Splits each failure into a real, checkable root
cause:

  no_nse_evidence_at_all       -- entity has ZERO EvidenceEntityLink rows, period
  no_evidence_in_window        -- entity has real linked evidence, but none within +/-5 days
  category_mismatch_in_window  -- real linked evidence exists in-window, but its
                                   classified category != the RSS item's category
  rss_category_undetermined    -- the RSS item's own text didn't classify (kept
                                   separate from the above three, which all
                                   require a determined RSS category)

For rss_category_undetermined, also captures the raw text so a human
(or a follow-up pass) can judge whether the real cause is a genuine
taxonomy gap (should have classified, keyword list too narrow) or
correctly-uncategorizable content (pure price-movement listicles with
no describable corporate action).
"""
from __future__ import annotations

import asyncio
import pickle
import sys
from datetime import timedelta

sys.path.insert(0, ".")

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.db.models.raw_evidence import RawEvidence
from b5_gate2_event_matching import classify_keyword, classify_nse_evidence, load_nse_candidates_by_entity


async def main() -> None:
    with open("b5_gate2_results.pkl", "rb") as f:
        outcomes = pickle.load(f)
    failed = [o for o in outcomes if o["status"] == "FAIL"]

    async with AsyncSessionLocal() as db:
        rss_rows = {r.id: (r.title, r.published_at) for r in
                    (await db.execute(select(RawEvidence.id, RawEvidence.title, RawEvidence.published_at)
                                       .where(RawEvidence.source_type == "rss"))).all()}
    nse_by_entity = await load_nse_candidates_by_entity()

    categorized = []
    for o in failed:
        if o["reason"] == "rss_category_undetermined":
            categorized.append({**o, "root_cause": "rss_category_undetermined"})
            continue

        entity_id = o["entity_id"]
        _, published_at = rss_rows.get(o["id"], (None, None))
        candidates = nse_by_entity.get(entity_id, [])
        if not candidates:
            categorized.append({**o, "root_cause": "no_nse_evidence_at_all"})
            continue

        window_start = published_at - timedelta(days=5)
        window_end = published_at + timedelta(days=5)
        in_window = [c for c in candidates if window_start <= c["published_at"] <= window_end]
        if not in_window:
            nearest = min(candidates, key=lambda c: abs((c["published_at"] - published_at).days))
            categorized.append({**o, "root_cause": "no_evidence_in_window",
                                 "nearest_evidence_days_away": abs((nearest["published_at"] - published_at).days),
                                 "nearest_evidence_title": nearest["title"][:150]})
            continue

        mismatches = []
        for c in in_window:
            c_cat = classify_nse_evidence(c["desc"], c["attchmnt_text"], c["title"])
            mismatches.append((c_cat, c["desc"], c["title"][:150]))
        categorized.append({**o, "root_cause": "category_mismatch_in_window",
                             "in_window_candidate_categories": mismatches})

    from collections import Counter
    counts = Counter(c["root_cause"] for c in categorized)
    print("Root-cause breakdown of the 85 single-entity Gate 2 failures:")
    for cause, n in counts.most_common():
        print(f"  {cause}: {n}")

    with open("b5_gate2_failure_audit.pkl", "wb") as f:
        pickle.dump(categorized, f)

    with open("b5_gate2_failure_audit.txt", "w", encoding="utf-8") as out:
        for cause in counts:
            out.write(f"\n=== {cause} ({counts[cause]}) ===\n")
            for c in categorized:
                if c["root_cause"] != cause:
                    continue
                out.write(f"[{c['id'][:8]}] {c['title'][:130]}\n")
                if cause == "no_evidence_in_window":
                    out.write(f"   nearest real evidence: {c['nearest_evidence_days_away']}d away -- {c['nearest_evidence_title']}\n")
                elif cause == "category_mismatch_in_window":
                    out.write(f"   rss_category={c.get('rss_category')}  in-window NSE candidates: {c['in_window_candidate_categories']}\n")
    print("done -- b5_gate2_failure_audit.pkl, b5_gate2_failure_audit.txt")


if __name__ == "__main__":
    asyncio.run(main())
