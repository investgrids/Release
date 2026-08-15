"""
Evidence deduplication / clustering — EvidenceCluster.

Brief §6: one real-world development (e.g. an RBI rate decision) can
surface as a NewsArticle + an Event + an AICompanySignal + an
Opportunity. Those must not count as four independent confirmations. No
LLM is used here (brief §6/§20 — "do not use an LLM merely to
deduplicate") — clustering is deterministic, in two tiers:

Tier 1 — REAL relational links already in the schema, no heuristics:
  - OpportunityEvent(opportunity_id, event_id): a real junction table
    already linking specific Opportunity rows to the Event rows that
    generated them (app/db/models/opportunity.py).
  - AICompanySignal.source_id: Phase 1A's normalize_company_signal()
    encodes this as f"{source_type}:{source_id}" (evidence.py). When
    source_type == "opportunity", source_id is a real Opportunity.id —
    an exact link back to that Opportunity's own EvidenceItem.

Tier 2 — deterministic heuristic, only for pairs Tier 1 didn't already
connect: normalized-title token overlap (Jaccard) above a threshold,
AND observed within 24h of each other, AND "company-compatible" (see
_companies_compatible: two company-specific items must name the SAME
company; two company-LESS items — broad-market/macro evidence, which
includes every GovernmentPolicy row since normalize_policy never
populates companies — are compatible with each other on title+time
alone). This catches e.g. an independently-ingested NewsArticle and
Event describing the same real story with no DB-level link between
them, INCLUDING the case where neither item names a specific company
at all (an RBI policy decision covered by 3 separate outlets, none of
which tag a company) — a pure "AND at least one shared company" rule
would make that case structurally impossible, since an empty list
never overlaps with anything, silently defeating this module's own
stated goal of letting GovernmentPolicy join a cluster via Tier 2
(see sector_synthesis.py's module docstring, which assumes this works).

Union-find over both tiers produces the final clusters. Every cluster
keeps a reference to every member EvidenceItem — no source reference is
dropped, per brief §6 ("Preserve all source references").
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.opportunity import OpportunityEvent
from app.services.weekend_intelligence.evidence import EvidenceItem

_TITLE_STOPWORDS = {
    "the", "a", "an", "to", "of", "in", "on", "for", "and", "or", "with",
    "at", "by", "from", "has", "have", "is", "are", "was", "were", "its",
}
_TOKEN_RE = re.compile(r"[a-z0-9]+")

# Two normalized titles are considered "the same story" when their
# significant-token Jaccard overlap is at least this — a single shared
# generic word ("results", "update") must not be enough to merge two
# unrelated items; a near-identical headline reliably clears it.
_TITLE_OVERLAP_THRESHOLD = 0.5
_TIME_PROXIMITY = timedelta(hours=24)


def _title_tokens(title: str) -> set[str]:
    tokens = set(_TOKEN_RE.findall(title.lower()))
    return tokens - _TITLE_STOPWORDS


def _titles_match(a: EvidenceItem, b: EvidenceItem) -> bool:
    ta, tb = _title_tokens(a.title), _title_tokens(b.title)
    if not ta or not tb:
        return False
    overlap = len(ta & tb) / len(ta | tb)
    return overlap >= _TITLE_OVERLAP_THRESHOLD


def _companies_compatible(a: EvidenceItem, b: EvidenceItem) -> bool:
    """Company-specific items may only merge with another item naming the
    SAME company — never blend two different companies' stories just
    because their headlines share tokens. Two company-LESS items are
    compatible with each other on title+time alone (see module
    docstring); one company-specific + one company-less item never merge
    (a specific-company story and an unrelated broad-market story should
    not collapse just because of generic shared words)."""
    if not a.companies and not b.companies:
        return True
    if not a.companies or not b.companies:
        return False
    return bool(set(a.companies) & set(b.companies))


def _within_time_proximity(a: EvidenceItem, b: EvidenceItem) -> bool:
    return abs((a.observed_at - b.observed_at)) <= _TIME_PROXIMITY


@dataclass
class EvidenceCluster:
    members: list[EvidenceItem] = field(default_factory=list)

    @property
    def representative(self) -> EvidenceItem:
        """The member used for the cluster's display title/summary —
        prefers a DETERMINISTIC-scored item (a real Event, per
        evidence.py's classification) over heuristic/LLM-rated ones,
        falling back to whichever member sorts first by observed_at."""
        from app.services.weekend_intelligence.evidence import DETERMINISTIC
        deterministic = [m for m in self.members if m.score_kind == DETERMINISTIC]
        pool = deterministic or self.members
        return sorted(pool, key=lambda m: m.observed_at)[0]

    @property
    def source_types(self) -> set[str]:
        return {m.source_type for m in self.members}

    @property
    def companies(self) -> set[str]:
        return {c for m in self.members for c in m.companies}

    @property
    def sectors(self) -> set[str]:
        return {s for m in self.members for s in m.sectors}

    @property
    def directions(self) -> list[str]:
        return [m.direction for m in self.members if m.direction]

    @property
    def net_direction(self) -> str:
        """Majority vote across members with a stated direction;
        "mixed" on a genuine tie between positive and negative (never
        silently picks a side) — feeds risk synthesis (brief §12: a
        thesis with real contradictory evidence must not look
        uncontested)."""
        dirs = self.directions
        if not dirs:
            return "neutral"
        pos = dirs.count("positive") + dirs.count("bullish")
        neg = dirs.count("negative") + dirs.count("bearish")
        if pos and neg:
            return "mixed"
        if pos:
            return "positive"
        if neg:
            return "negative"
        return "neutral"

    def evidence_refs(self) -> list[dict]:
        return [{"source_type": m.source_type, "source_id": m.source_id} for m in self.members]


class _UnionFind:
    def __init__(self, n: int):
        self.parent = list(range(n))

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


async def _tier1_links(db: AsyncSession, evidence: list[EvidenceItem]) -> list[tuple[int, int]]:
    """Index pairs (into `evidence`) connected by a real DB relationship."""
    event_index: dict[str, int] = {
        e.source_id: i for i, e in enumerate(evidence) if e.source_type == "event"
    }
    opportunity_index: dict[str, int] = {
        e.source_id: i for i, e in enumerate(evidence) if e.source_type == "opportunity"
    }
    pairs: list[tuple[int, int]] = []

    if event_index and opportunity_index:
        rows = (await db.execute(
            select(OpportunityEvent.opportunity_id, OpportunityEvent.event_id)
            .where(OpportunityEvent.event_id.in_(event_index.keys()))
        )).all()
        for opp_id, event_id in rows:
            opp_i = opportunity_index.get(str(opp_id))
            evt_i = event_index.get(event_id)
            if opp_i is not None and evt_i is not None:
                pairs.append((opp_i, evt_i))

    # AICompanySignal(source_type="opportunity") -> that Opportunity's own
    # EvidenceItem, via the "opportunity:<id>" encoding evidence.py's
    # normalize_company_signal() already produces.
    for i, item in enumerate(evidence):
        if item.source_type == "company_signal" and item.source_id.startswith("opportunity:"):
            opp_id = item.source_id.split(":", 1)[1]
            opp_i = opportunity_index.get(opp_id)
            if opp_i is not None:
                pairs.append((i, opp_i))

    return pairs


async def cluster_evidence(db: AsyncSession, evidence: list[EvidenceItem]) -> list[EvidenceCluster]:
    """
    Group `evidence` (already normalized, already window-bounded — see
    evidence_window.collect_evidence_since) into EvidenceClusters. Order
    of the returned clusters is not meaningful; callers sort as needed.
    """
    if not evidence:
        return []

    uf = _UnionFind(len(evidence))

    for i, j in await _tier1_links(db, evidence):
        uf.union(i, j)

    # Tier 2 — O(n^2) heuristic pass. Evidence windows in this codebase
    # are small (checkpoint-scoped, `limit_per_source=200` per source in
    # evidence_window.py, and real weekend volume is far below that per
    # the Phase 0 audit) — quadratic over a few hundred items is fine;
    # not worth a smarter index for Phase 1B's actual data volume.
    for i in range(len(evidence)):
        for j in range(i + 1, len(evidence)):
            if uf.find(i) == uf.find(j):
                continue
            a, b = evidence[i], evidence[j]
            if _titles_match(a, b) and _companies_compatible(a, b) and _within_time_proximity(a, b):
                uf.union(i, j)

    groups: dict[int, list[EvidenceItem]] = {}
    for i, item in enumerate(evidence):
        groups.setdefault(uf.find(i), []).append(item)

    return [EvidenceCluster(members=members) for members in groups.values()]
