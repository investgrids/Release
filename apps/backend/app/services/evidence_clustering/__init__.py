"""
Evidence Clustering — shared cross-consumer infrastructure (Phase 5E.3).

Moved here from app/services/weekend_intelligence/{evidence,dedup}.py,
where it was built and proven (Weekend Intelligence's materiality/risk/
sector/company synthesis all depend on it recognizing that one real
development covered by several sources is one thing, not several). The
logic itself was never Weekend-Intelligence-specific — EvidenceItem is
a source-agnostic normalized view over 6 already-durable tables, and
cluster_evidence() clusters on title/company/time-proximity plus real
DB relational links, nothing about "weekend" or a checkpoint schedule.
Only its import path was.

Phase 5E's own audit (2026-08-17) found the reason this needed to move:
AI Search and Opportunity Radar both count evidence rows toward a
number that matters (source_count -> confidence; len(events) ->
opportunity_score) with ZERO cross-source deduplication — the same
real NSE filing, reported by a news outlet too, was inflating both.
Weekend Intelligence had already solved this correctly; the fix for
the other two consumers is to use the same proven primitive, not
reinvent a third clustering scheme next to the two Jaccard
implementations that already existed in this codebase.

app/services/weekend_intelligence/evidence.py and dedup.py now
re-export from here unchanged, so none of that package's 13 existing
internal importers needed to change for this move.
"""
