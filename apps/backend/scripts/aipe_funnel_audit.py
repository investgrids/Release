"""
Production AIPE scheduler + publication-failure audit (owner-authorized
2026-08-30, after the Phase B shadow-quality checkpoint). Reconstructs
the real 7-day (extendable) funnel for the high_urgency_triage pathway
specifically -- NOT the separate "vs comparison" article pipeline, which
writes into the same intelligence_article table with trigger_type=None
and never runs quality_validator at all (confirmed via real data: 118
published rows with validation_passed=False all have trigger_type=None
and validation_results=NULL -- a different pipeline, not a quality
failure, explicitly out of scope for this audit).

Funnel:
  EventTriage (source item, all triaged real news/NSE/policy/price items)
    -> should_generate_intelligence() [REAL function, not reimplemented]
    -> IntelligenceArticle via trigger_event_id == EventTriage.event_id

Every EventTriage row in the window is bucketed into exactly one of:
  PUBLISHED
  CORRECT_SKIP_DUPLICATE       (real candidate, matched an existing article -> updated, not republished)
  CORRECT_SKIP_LOW_VALUE       (should_generate_intelligence() said no)
  FAILED_QUALITY               (candidate, article created, status=failed, validation_passed=False)
  FAILED_UNKNOWN                (candidate, should_generate=True, NO article record at all -- the
                                  real, disclosed gap: no persisted evidence of what happened)
"""
from __future__ import annotations

import asyncio
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone

sys.path.insert(0, ".")

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.db.models.intelligence import EventTriage
from app.db.models.intelligence_article import IntelligenceArticle
from app.services.aipe.intelligence_filter import should_generate_intelligence

WINDOW_DAYS = int(sys.argv[1]) if len(sys.argv) > 1 else 7


def _triage_to_dict(t: EventTriage) -> dict:
    return {
        "urgency": t.urgency, "importance": t.importance, "market_impact": t.market_impact,
        "is_structural": t.is_structural, "headline": t.headline, "one_liner": t.one_liner,
    }


async def main() -> None:
    since = datetime.now(timezone.utc) - timedelta(days=WINDOW_DAYS)
    async with AsyncSessionLocal() as db:
        triage_rows = (await db.execute(
            select(EventTriage).where(EventTriage.triaged_at >= since)
        )).scalars().all()
        print(f"EventTriage rows in last {WINDOW_DAYS} days: {len(triage_rows)}")

        from collections import Counter as _Counter
        by_day = _Counter(t.triaged_at.date() for t in triage_rows)
        all_days = [(since + timedelta(days=i)).date() for i in range(WINDOW_DAYS + 1)]
        print("Triage rows per calendar day (0 = no ingestion that day):")
        for d in sorted(set(all_days)):
            print(f"  {d}: {by_day.get(d, 0)}")

        # Articles from the high_urgency_triage pathway specifically, keyed by trigger_event_id.
        # Pull from a slightly wider window (articles can be created shortly after a triage row,
        # occasionally crossing the exact `since` boundary) to avoid an artificial undercount.
        article_rows = (await db.execute(
            select(IntelligenceArticle).where(
                IntelligenceArticle.trigger_event_id.is_not(None),
                IntelligenceArticle.created_at >= since - timedelta(days=1),
            )
        )).scalars().all()
        articles_by_event_id: dict[str, list[IntelligenceArticle]] = {}
        for a in article_rows:
            articles_by_event_id.setdefault(a.trigger_event_id, []).append(a)
        print(f"IntelligenceArticle rows (high_urgency_triage pathway, trigger_event_id set): {len(article_rows)}")

        reject_reasons = Counter()
        bucket_counts = Counter()
        no_record_examples = []
        quality_fail_examples = []

        for t in triage_rows:
            should_generate, reason = should_generate_intelligence(_triage_to_dict(t), source="triage")

            if not should_generate:
                bucket_counts["CORRECT_SKIP_LOW_VALUE"] += 1
                # bucket the reason to its stable prefix (urgency/importance numbers vary per row)
                reject_reasons[reason.split("(")[0].strip()] += 1
                continue

            matches = articles_by_event_id.get(t.event_id, [])
            if not matches:
                bucket_counts["FAILED_UNKNOWN"] += 1
                if len(no_record_examples) < 8:
                    no_record_examples.append((t.event_id, t.headline, t.urgency, t.importance, t.market_impact, reason))
                continue

            # NOTE: lifecycle_status ('published' vs 'updated') does NOT cleanly distinguish "a
            # fresh new article" from "duplicate-detector correctly routed this into an update of
            # a different existing story" -- real data shows the SAME trigger_event_id sometimes
            # appearing on 2 separate article rows, one 'updated' and one 'published', which does
            # not match that simple assumption. Rather than guess, this script counts any real
            # candidate that produced AT LEAST ONE status='published' article as a successful
            # PUBLISHED outcome (new or updated -- a real reader sees a correct, current article
            # either way) and reports this simplification plainly rather than overclaiming a
            # duplicate/fresh split this schema alone can't cleanly support.
            published = [a for a in matches if a.status == "published"]
            failed = [a for a in matches if a.status == "failed"]
            if published:
                bucket_counts["PUBLISHED"] += 1
            elif failed:
                bucket_counts["FAILED_QUALITY"] += 1
                if len(quality_fail_examples) < 8:
                    a = failed[0]
                    quality_fail_examples.append((t.event_id, t.headline, a.validation_failures, a.validation_results))
            else:
                bucket_counts["FAILED_UNKNOWN"] += 1

        print("\n=== Funnel bucket counts ===")
        for k, v in bucket_counts.most_common():
            print(f"  {k}: {v}")
        print(f"  TOTAL: {sum(bucket_counts.values())}  (should equal EventTriage count: {len(triage_rows)})")

        print("\n=== Reject-reason breakdown (CORRECT_SKIP_LOW_VALUE) ===")
        for reason, count in reject_reasons.most_common():
            print(f"  {count:5d}  {reason}")

        print("\n=== Sample FAILED_UNKNOWN (real candidate, should_generate=True, no article record at all) ===")
        for event_id, headline, urgency, importance, market_impact, reason in no_record_examples:
            print(f"  [{event_id}] urgency={urgency} importance={importance} impact={market_impact} filter_reason={reason!r}")
            print(f"    {headline!r:.140}")

        print("\n=== Sample FAILED_QUALITY (article created, status=failed) ===")
        for event_id, headline, n_failures, results in quality_fail_examples:
            print(f"  [{event_id}] validation_failures={n_failures}")
            print(f"    headline={headline!r:.100}")
            print(f"    validation_results={results}")


if __name__ == "__main__":
    asyncio.run(main())
