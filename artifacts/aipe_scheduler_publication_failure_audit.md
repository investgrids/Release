# Production AIPE — Scheduler & Publication-Failure Audit

**Date:** 2026-08-30
**Scope:** real production data reconstruction of the `high_urgency_triage` pathway's funnel (EventTriage → intelligence_filter → article_generator → quality_validator → IntelligenceArticle), 7-day window extended to 30 days per instruction (real ingestion gaps made 7 days unrepresentative). The separate "vs comparison" article pipeline (`trigger_type=None`, never runs `quality_validator`) is explicitly out of scope — confirmed via real data (see below).
**Scripts:** `scripts/aipe_funnel_audit.py` (funnel reconstruction, reuses the real `intelligence_filter.should_generate_intelligence()` — not reimplemented), ad hoc queries for the outage/linkage/recovery findings below.

## Scoping note: two pipelines share one table

118 real `IntelligenceArticle` rows have `status='published'` but `validation_passed=False` — all 118 have `trigger_type=None` and `validation_results=NULL`. These are "X vs Y: Which is the better investment?" comparison articles from a separate pipeline that never runs `quality_validator.validate()` at all; `validation_passed=False` is a default, not a real failure. Excluded from this audit, which focuses on the `high_urgency_triage` pathway the owner's funnel diagram describes.

## The real funnel (30-day window, 6,027 triaged items)

```
6,027 EventTriage rows
   -> intelligence_filter.should_generate_intelligence()
4,815 CORRECT_SKIP_LOW_VALUE  (79.9%)
1,212 real candidates (20.1%)
   -> IntelligenceArticle via trigger_event_id
  218 PUBLISHED                (3.6% of all triaged, 18.0% of real candidates)
  994 FAILED_UNKNOWN            (16.5% of all triaged, 82.0% of real candidates — no article record of any kind)
    0 FAILED_QUALITY            (0 candidates produced an article that then failed validation)
```

Reject-reason breakdown for the 4,815 correct skips: 3,096 "Urgency too low", 1,678 "Routine corporate event — no investor action implication" (hard-NO regex), 38 "Insufficient intelligence signal", 3 "Market impact classified as low". No surprises here — the filter is doing its job on the bulk of low-signal volume.

**The 7-day window (1,359 triaged items) shows the same shape**: 1,198 correct skips, 147 FAILED_UNKNOWN, 14 published, 0 failed-quality — proportionally similar to the 30-day figures, confirming the pattern isn't a 30-day-only artifact.

## Finding 1 (highest severity): recurring multi-day total ingestion outages

Real `EventTriage.triaged_at` counts per calendar day over 30 days show **zero rows at all** on: 2026-08-19 (partial, only 8 rows) through 08-21, and 2026-08-26 through 08-29 — two separate multi-day gaps totaling 7 of the 30 days with no or near-no triage activity (the 07-31/08-01/08-02 zeros are the window's edge, not necessarily an outage). This is not a filtering artifact — it means the upstream ingestion/triage worker was not producing rows at all during these windows, so **every real event that occurred during those days, however important, had zero chance of becoming a candidate.** This is the single highest-severity, most surprising finding of the audit and is unrelated to anything this session did — it is a real, recurring production reliability gap that predates and is independent of the Warehouse/Article V2 work.

## Finding 2: generation/quality failure is NOT the bottleneck

Across the entire `intelligence_article` table, only 17 rows have `status='failed'` (out of 571 rows with `trigger_type` set), and 0 of the 30-day window's 994 FAILED_UNKNOWN candidates match any article row at all — not even a failed one. **The loss happens entirely before generation is ever attempted**, not because the LLM/quality-validator layer is unreliable. This is a materially different picture than "LLM formatting failures" or "quality-template failures" being the dominant loss — those are real but rare (17 all-time). The dominant loss mode is "recognized as worth generating, then never processed at all."

A real, concrete daily cap exists in code (`content_planner.should_generate_today`, `max_per_day=8`, non-critical events only) which — given real candidate volume of 40-70+/day on several active days — plausibly contributes to this gap. However, real daily published counts do **not** show a clean 8-per-day ceiling (e.g. 116 published on 2026-08-14, 61 on 08-15) — likely because Critical/High-tier events bypass the cap and/or `continuous_updater` writes additional rows for ongoing stories that don't count against "new" generation. **This audit could not cleanly isolate the exact mechanism behind the residual FAILED_UNKNOWN volume from DB data alone** — the daily cap, a possible narrow real-time selection window in `get_high_urgency_triage` letting candidates go stale between 5-minute cycles, and live LLM-provider rate-limiting (directly, repeatedly observed in this session's own Why It Matters calls: `ai.exhausted status=429`, `ai.rate_limited status=402` across multiple providers) are all plausible real contributors. Recommend a follow-up correlating the structlog event names `aipe.cycle.skipped` / `aipe.cycle.daily_limit_reached` / `article_generator.ai_error` against real server logs for specific dates — this audit only had DB access, not historical log retention.

## Finding 3 (most actionable for Phase C/recovery): Article V2's evidence base has 0% RSS coverage

Real, quantified: of 558 real `RawEvidence` rows with `source_type='rss'`, **zero** have any `EvidenceEntityLink` row. Of 604 real `source_type='nse'` rows, 595 are linked. Real 30-day triage source distribution is 1,357 of 1,359 "news" (RSS) — i.e. **the overwhelming majority of real production candidates originate from RSS, and Article V2 currently cannot ground any of them**, regardless of how important the underlying event is. This was previously flagged as a known scope limitation in the Warehouse Consumption Audit ("NSE-only linkage scope"); this audit gives it a hard, quantified, real-production consequence.

## Recovery matrix — real tests, not hypothetical

The owner's recovery-matrix question was tested against 3 real, actual missed candidates from the 30-day FAILED_UNKNOWN sample, run through the real Article V2 pipeline:

| Real missed candidate | Source | V2 evidence found | Actual V2 output | Decision |
|---|---|---|---|---|
| "Bajaj Finserv shares rise over 2% after Q1 earnings" (real triage item, urgency 2-6, importance 6-7) | RSS | **None** — 0 linked evidence, 0 financial facts reachable via this event | `omitted_no_evidence` | **Not recoverable today** — not a V2 defect, a Warehouse evidence-coverage gap (Finding 3) |
| "Urban Company shares zoom 15% after Q1 results" (real triage item) | RSS | Urban Company IS a resolved entity with 2 real linked NSE items — but neither is the Q1-results event itself (they're an analyst-meeting schedule and a Reg 30 disclosure from a different date) | A real, coherent, but *unrelated* factual update was produced (the actual missed 15% earnings story has no NSE-side evidence at all) | **Partially recoverable, but for the wrong event** — V2 would ground *a* real story about this company, not *the* story production missed |
| "Osia Hyper Retail Limited has informed the Exchange about Corporate Insolvency Resolution Process" (real triage item, NSE-sourced) | NSE | Real, direct evidence match | *"The announcement of a Corporate Insolvency Resolution Process signals severe financial distress for Osia Hyper Retail, and the market reacted sharply, pushing the stock down 4.21%."* — correct, well-grounded, genuinely useful | **Fully recoverable** — a real, material event production silently dropped, that V2 handles correctly today |

**This differs from the owner's hypothesized table** (LLM formatting failures, quality-template failures) because those failure modes barely exist in real production data (Finding 2). The real, actionable recovery story is narrower and more structural: **V2 can reliably recover NSE-sourced candidates that production drops (capacity/outage), but cannot yet touch the much larger RSS-sourced share of real candidates at all.**

## Combined with the Phase B shadow-quality checkpoint

Putting both audits together:
- The shadow checkpoint showed V2 produces something truthful and useful for 18/20 diverse NSE-linked events (5 full, 13 factual update), with 2 correctly-identified skips.
- This audit shows production's real bottleneck is *upstream* of anything Phase B controls — ingestion reliability and RSS-evidence coverage, not generation quality.
- Together, they point to the same conclusion the owner named: **MarketRipple does not need every event to become an "AI article."** For the NSE-linked candidates V2 can already see, the Full Article / Factual Update / Skip triage is the right shape. But before that triage matters much in production, closing the RSS-linkage gap (Finding 3) determines how much of the real candidate volume V2 can even attempt.

## Explicitly not done in this audit

- No code changes to intelligence_filter, content_planner, duplicate_detector, or the scheduler.
- No fix to the ingestion outages (Finding 1) — flagged for a separate decision; root cause not investigated beyond confirming the outage exists in triage data.
- No RSS-evidence-linkage work started (Finding 3) — this is a real, large, separate engineering effort (extending `EvidenceEntityLink`-style resolution to RSS sources), not something to improvise inside this audit.
- No Phase C implementation.
