"""
V1 vs V2 shadow comparison — proves the whole chain without touching
public Radar behavior (owner instruction, 2026-08-22). Reads V1's real
opportunities/opportunity_companies tables and V2's real opportunities_v2/
opportunity_v2_developments tables; writes nothing anywhere. V1's public
read path (app/api/radar.py) is never called or modified by this module.

The V1<->V2 correlation (split/merge sections) is necessarily a heuristic
— there is no FK between the two systems by design (see the Opportunity
Engine V2 plan's migration section: V1 rows predate Development Memory
for the most part, so no reliable backward mapping exists). Correlation
here is via real shared company tickers within the same analysis window,
disclosed as approximate, not presented as an exact match.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.opportunity import Opportunity, OpportunityCompany
from app.db.models.opportunity_v2 import OpportunityV2, OpportunityV2Development
from app.services.opportunity_v2.orchestration import PassSummary

# Same two real V1 fallback signatures the audit found (opportunity_generator.py):
# an 8-word raw-headline slice (heuristically: title has no terminal
# punctuation a real generated title would have, or ends mid-clause), and
# the generic "{Sector} Growth/Investment Opportunity" template.
import re

_GENERIC_TITLE_RE = re.compile(r"^[\w &]+ (Growth|Investment) Opportunity$")


@dataclass
class V1Stats:
    total: int = 0
    duplicate_title_count: int = 0  # rows sharing a title with >=1 other row
    generic_template_title_count: int = 0
    companies: set[str] = field(default_factory=set)


@dataclass
class V2Stats:
    total_open: int = 0
    duplicate_thesis_count: int = 0  # should be 0 by construction — sanity check on identity.py
    score_distribution: dict[str, int] = field(default_factory=dict)
    companies: set[str] = field(default_factory=set)
    top_opportunities: list[dict] = field(default_factory=list)


@dataclass
class ComparisonReport:
    generated_at: datetime
    pass_summary: PassSummary
    v1: V1Stats
    v2: V2Stats
    v1_only_companies: list[str]
    v2_only_companies: list[str]
    shared_companies: list[str]
    # V1 opportunities whose real companies now map to MORE THAN ONE
    # distinct open V2 thesis — the real, evidence-grounded signal for
    # "V2 split this V1 bucket into multiple coherent opportunities"
    # (approximate — see module docstring).
    v1_buckets_v2_split: list[dict]
    # Straight from this run's PassSummary — real merge events where new
    # Development evidence attached to an ALREADY-open V2 opportunity
    # instead of creating a duplicate.
    v2_merge_events: list[dict]


async def _v1_stats(db: AsyncSession) -> V1Stats:
    rows = (await db.execute(select(Opportunity.id, Opportunity.title))).all()
    stats = V1Stats(total=len(rows))

    title_counts: dict[str, int] = defaultdict(int)
    for _id, title in rows:
        title_counts[title] += 1
        if _GENERIC_TITLE_RE.match(title or ""):
            stats.generic_template_title_count += 1
    stats.duplicate_title_count = sum(1 for t, c in title_counts.items() if c > 1 for _ in range(c))

    company_rows = (await db.execute(select(OpportunityCompany.company_id))).scalars().all()
    stats.companies = {c for c in company_rows if c}
    return stats


async def _v2_stats(db: AsyncSession) -> V2Stats:
    rows = (await db.execute(
        select(OpportunityV2).where(OpportunityV2.status == "open")
    )).scalars().all()
    stats = V2Stats(total_open=len(rows))

    thesis_counts: dict[tuple[str, str], int] = defaultdict(int)
    buckets = {"0-20": 0, "20-40": 0, "40-60": 0, "60-80": 0, "80-100": 0}
    companies: set[str] = set()
    for opp in rows:
        thesis_counts[(opp.thesis_anchor, opp.thesis_direction)] += 1
        companies.update(opp.companies or [])
        score = opp.current_score or 0.0
        if score < 20:
            buckets["0-20"] += 1
        elif score < 40:
            buckets["20-40"] += 1
        elif score < 60:
            buckets["40-60"] += 1
        elif score < 80:
            buckets["60-80"] += 1
        else:
            buckets["80-100"] += 1
    stats.duplicate_thesis_count = sum(1 for c in thesis_counts.values() if c > 1)
    stats.score_distribution = buckets
    stats.companies = companies

    top = sorted(rows, key=lambda o: o.current_score or 0.0, reverse=True)[:20]
    stats.top_opportunities = [
        {
            "id": o.id, "title": o.current_title, "score": o.current_score,
            "thesis_anchor": o.thesis_anchor, "thesis_direction": o.thesis_direction,
            "narrative_status": o.narrative_status, "companies": o.companies, "sectors": o.sectors,
        }
        for o in top
    ]
    return stats


async def _v1_buckets_v2_split(db: AsyncSession, v2_open: list[OpportunityV2]) -> list[dict]:
    """For each real V1 opportunity, which distinct open V2 theses share
    at least one of its real companies. Only reported when that's MORE
    than one — the real, company-grounded signal that V2 treated what V1
    lumped into one bucket as genuinely separate theses."""
    v1_company_rows = (await db.execute(
        select(OpportunityCompany.opportunity_id, OpportunityCompany.company_id)
    )).all()
    v1_companies_by_opp: dict[int, set[str]] = defaultdict(set)
    for opp_id, company_id in v1_company_rows:
        if company_id:
            v1_companies_by_opp[opp_id].add(company_id)

    v1_titles = dict((await db.execute(select(Opportunity.id, Opportunity.title))).all())

    results: list[dict] = []
    for v1_id, v1_companies in v1_companies_by_opp.items():
        matching_v2_ids = {o.id for o in v2_open if v1_companies & set(o.companies or [])}
        if len(matching_v2_ids) > 1:
            results.append({
                "v1_opportunity_id": v1_id,
                "v1_title": v1_titles.get(v1_id),
                "v1_companies": sorted(v1_companies),
                "v2_opportunity_ids": sorted(matching_v2_ids),
            })
    return results


async def build_comparison_report(db: AsyncSession, pass_summary: PassSummary) -> ComparisonReport:
    v1 = await _v1_stats(db)
    v2 = await _v2_stats(db)
    v2_open = (await db.execute(select(OpportunityV2).where(OpportunityV2.status == "open"))).scalars().all()

    shared = sorted(v1.companies & v2.companies)
    v1_only = sorted(v1.companies - v2.companies)
    v2_only = sorted(v2.companies - v1.companies)

    v1_split = await _v1_buckets_v2_split(db, v2_open)

    merge_events = [
        {
            "opportunity_id": o.opportunity_id, "title": o.title, "thesis_anchor": o.thesis_anchor,
            "newly_linked_development_ids": o.new_development_ids,
        }
        for o in pass_summary.outcomes
        if o.action == "updated" and o.new_development_ids
    ]

    return ComparisonReport(
        generated_at=datetime.now(timezone.utc), pass_summary=pass_summary, v1=v1, v2=v2,
        v1_only_companies=v1_only, v2_only_companies=v2_only, shared_companies=shared,
        v1_buckets_v2_split=v1_split, v2_merge_events=merge_events,
    )


def format_report(report: ComparisonReport) -> str:
    """Plain-text rendering for a manual review pass — not a public API
    response, this is a debug/ops artifact only."""
    p, v1, v2 = report.pass_summary, report.v1, report.v2
    lines = [
        f"Opportunity Engine V2 — shadow comparison ({report.generated_at.isoformat()})",
        "",
        "== This run ==",
        f"  Developments considered:  {p.developments_considered}",
        f"  Gate-passed candidates:   {p.developments_gate_passed}",
        f"  Coherent clusters formed: {p.clusters_formed}",
        f"  Opportunities created:    {p.opportunities_created}",
        f"  Opportunities updated:    {p.opportunities_updated}",
        f"  Rejected (no identity):   {p.rejected_no_identity}",
        f"  Narrative generated:      {p.narrative_generated}",
        f"  Narrative reused (0 LLM): {p.narrative_reused}",
        f"  Narrative failed_capacity:{p.narrative_failed}",
        "",
        "== V1 (production, unchanged) ==",
        f"  Total opportunities:      {v1.total}",
        f"  Duplicate-title rows:     {v1.duplicate_title_count}",
        f"  Generic-template titles:  {v1.generic_template_title_count}",
        f"  Distinct real companies:  {len(v1.companies)}",
        "",
        "== V2 (shadow) ==",
        f"  Open opportunities:       {v2.total_open}",
        f"  Duplicate-thesis rows:    {v2.duplicate_thesis_count}  (should always be 0)",
        f"  Score distribution:       {v2.score_distribution}",
        f"  Distinct real companies:  {len(v2.companies)}",
        "",
        f"== Company overlap == shared={len(report.shared_companies)} v1_only={len(report.v1_only_companies)} v2_only={len(report.v2_only_companies)}",
        "",
        f"== V1 buckets V2 split into multiple theses ({len(report.v1_buckets_v2_split)}) ==",
    ]
    for item in report.v1_buckets_v2_split[:10]:
        lines.append(f"  V1 #{item['v1_opportunity_id']} \"{item['v1_title']}\" -> V2 {item['v2_opportunity_ids']}")
    lines.append("")
    lines.append(f"== V2 merges this run ({len(report.v2_merge_events)}) ==")
    for item in report.v2_merge_events[:10]:
        lines.append(f"  {item['opportunity_id']} \"{item['title']}\" += {len(item['newly_linked_development_ids'])} new development(s)")
    lines.append("")
    lines.append("== Top V2 opportunities ==")
    for o in v2.top_opportunities[:20]:
        lines.append(f"  [{o['score']}] {o['title'] or '(narrative failed)'} — {o['thesis_anchor']}/{o['thesis_direction']} — {o['narrative_status']}")
    return "\n".join(lines)
