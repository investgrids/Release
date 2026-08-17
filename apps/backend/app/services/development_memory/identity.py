"""
Development identity resolution — the persistent counterpart to
app/services/evidence_clustering/dedup.py's in-memory cluster_evidence().

Given one EvidenceItem, decide whether it belongs to an already-persisted
Development or should start a new one. Reuses dedup.py's exact matching
rules (title-token Jaccard, company compatibility, time proximity) rather
than forking them — this only adds persistence and a second, wider
matching tier on top of the same primitives.

Four tiers, checked in order (first match wins):

  existing — the exact same evidence row (by evidence_key) was already
             attached to a Development on a previous run. No-op merge:
             return that Development unchanged. Makes the sync job safe
             to re-run over overlapping windows.

  tier1    — real relational link (OpportunityEvent junction, or a
             company_signal's "opportunity:<id>" encoding) to evidence
             already attached to a Development. Attaches regardless of
             the fuzzy time/title window — same as dedup.py's Tier 1.

  tier2a   — normal fuzzy match: company-compatible, title Jaccard >=
             _TITLE_OVERLAP_THRESHOLD against BOTH the Development's
             canonical (formation) title AND its most-recently-added
             evidence's title, within 24h of last_observed_at. Matches
             dedup.py's existing in-request threshold exactly.

  tier2b   — extended persistent-memory match: same primary_company
             (strict, not just "compatible"), same category where both
             sides have one, title Jaccard >= _TITLE_OVERLAP_THRESHOLD_EXT
             (stronger than tier2a) against both canonical and most-recent
             titles, within _TIME_PROXIMITY_EXTENDED (72h) of
             last_observed_at. Exists so a Friday-afternoon filing and a
             Monday-morning follow-up can still join the same Development
             even though they're >24h apart — without loosening the
             normal 24h rule, which stays exactly as strict as it is
             in-request.

Both tier2a and tier2b require agreement with BOTH the canonical title AND
the most-recent evidence's title (not just the most recent) — a chain
A~B~C~D where each hop is locally similar but A and D have drifted apart
would fail the canonical check and correctly start a new Development
instead of silently absorbing an unrelated later story.

A Development with status="closed" (72h+ since last_observed_at, flipped
by sweep_close_stale() — see sync.py) is excluded from candidate
retrieval and never reopened; matching evidence for a closed Development
starts a fresh one (Phase 6B links related Developments later).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.development import Development, DevelopmentEvidence
from app.db.models.opportunity import OpportunityEvent
from app.services.evidence_clustering.dedup import _title_tokens
from app.services.evidence_clustering.evidence import EvidenceItem

SCHEMA_VERSION = "6a-development-v1"

_TITLE_OVERLAP_THRESHOLD = 0.5       # matches dedup.py's _TITLE_OVERLAP_THRESHOLD exactly
_TITLE_OVERLAP_THRESHOLD_EXT = 0.65  # tier2b's stronger bar
_TIME_PROXIMITY = timedelta(hours=24)         # tier2a — matches dedup.py's _TIME_PROXIMITY exactly
_TIME_PROXIMITY_EXTENDED = timedelta(hours=72)  # tier2b
CLOSE_AFTER = timedelta(hours=72)  # sweep_close_stale() in sync.py


def compute_evidence_key(item: EvidenceItem) -> str:
    """source_id verbatim for every source type except company_signal,
    where AICompanySignal.source_id encodes the originating article/
    opportunity rather than the signal row itself — multiple companies
    extracted from one article legitimately share a source_id. Disambiguate
    with the resolved company so each is its own evidence identity."""
    if item.source_type == "company_signal":
        company = item.companies[0] if item.companies else "unresolved"
        return f"{item.source_id}:{company}"
    return item.source_id


def _aware(dt: datetime) -> datetime:
    """SQLite round-trips DateTime(timezone=True) columns as naive Python
    datetimes on SELECT even though the stored value is real UTC (see
    project_sqlite_footgun_family) — guard every Development timestamp
    read back from the DB before any Python-level arithmetic/comparison
    against it, the same way ai_search/evidence.py's _parse_evidence_date
    already does."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _title_overlap(a: str, b: str) -> float:
    ta, tb = _title_tokens(a), _title_tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _company_compatible(item_companies: list[str], dev_companies: list[str]) -> bool:
    """Same rule as dedup.py's _companies_compatible: two company-less
    sides are compatible on title+time alone; one company-specific + one
    company-less side never merge."""
    if not item_companies and not dev_companies:
        return True
    if not item_companies or not dev_companies:
        return False
    return bool(set(item_companies) & set(dev_companies))


@dataclass
class ResolutionResult:
    development: Development
    tier: str          # "existing" | "tier1" | "tier2a" | "tier2b" | "seed"
    created: bool


async def _find_existing_evidence(db: AsyncSession, source_type: str, evidence_key: str) -> DevelopmentEvidence | None:
    result = await db.execute(
        select(DevelopmentEvidence).where(
            DevelopmentEvidence.source_type == source_type,
            DevelopmentEvidence.evidence_key == evidence_key,
        )
    )
    return result.scalar_one_or_none()


async def _tier1_match(db: AsyncSession, item: EvidenceItem) -> Development | None:
    """Real relational link to evidence already attached to a Development
    — mirrors dedup.py's _tier1_links, applied against persisted evidence
    instead of same-request items."""
    linked_opportunity_ids: list[str] = []

    if item.source_type == "event":
        rows = (await db.execute(
            select(OpportunityEvent.opportunity_id).where(OpportunityEvent.event_id == item.source_id)
        )).scalars().all()
        linked_opportunity_ids = [str(oid) for oid in rows]
    elif item.source_type == "opportunity":
        linked_opportunity_ids = [item.source_id]
    elif item.source_type == "company_signal" and item.source_id.startswith("opportunity:"):
        linked_opportunity_ids = [item.source_id.split(":", 1)[1]]

    if not linked_opportunity_ids:
        return None

    evidence = (await db.execute(
        select(DevelopmentEvidence).where(
            DevelopmentEvidence.source_type == "opportunity",
            DevelopmentEvidence.source_id.in_(linked_opportunity_ids),
        )
    )).scalars().first()
    if evidence is None:
        return None

    return await db.get(Development, evidence.development_id)


async def _candidates(db: AsyncSession, item: EvidenceItem) -> list[Development]:
    cutoff = item.observed_at - _TIME_PROXIMITY_EXTENDED
    stmt = select(Development).where(Development.status == "open", Development.last_observed_at >= cutoff)
    if item.companies:
        stmt = stmt.where(Development.primary_company.in_(item.companies))
    else:
        # Company-less evidence (macro/policy) only ever matches a
        # company-less Development — without this, every macro item would
        # have to be compared against every open company-specific
        # Development in the system.
        stmt = stmt.where(Development.primary_company.is_(None))
    return list((await db.execute(stmt)).scalars().all())


async def _most_recent_title(db: AsyncSession, development_id: str) -> str | None:
    result = await db.execute(
        select(DevelopmentEvidence.title)
        .where(DevelopmentEvidence.development_id == development_id)
        .order_by(DevelopmentEvidence.observed_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _tier2_match(db: AsyncSession, item: EvidenceItem) -> tuple[Development, str] | None:
    for dev in await _candidates(db, item):
        if not _company_compatible(item.companies, dev.companies or []):
            continue

        recent_title = await _most_recent_title(db, dev.id)
        canonical_overlap = _title_overlap(item.title, dev.canonical_title)
        recent_overlap = _title_overlap(item.title, recent_title) if recent_title else canonical_overlap
        gap = abs(item.observed_at - _aware(dev.last_observed_at))

        if (
            gap <= _TIME_PROXIMITY
            and canonical_overlap >= _TITLE_OVERLAP_THRESHOLD
            and recent_overlap >= _TITLE_OVERLAP_THRESHOLD
        ):
            return dev, "tier2a"

        same_company = bool(item.companies) and dev.primary_company in item.companies
        same_category = (
            item.category is not None and dev.category is not None and item.category == dev.category
        )
        if (
            same_company
            and same_category
            and gap <= _TIME_PROXIMITY_EXTENDED
            and canonical_overlap >= _TITLE_OVERLAP_THRESHOLD_EXT
            and recent_overlap >= _TITLE_OVERLAP_THRESHOLD_EXT
        ):
            return dev, "tier2b"

    return None


def _net_direction(directions: list[str]) -> str | None:
    if not directions:
        return None
    pos = directions.count("positive") + directions.count("bullish")
    neg = directions.count("negative") + directions.count("bearish")
    if pos and neg:
        return "mixed"
    if pos:
        return "positive"
    if neg:
        return "negative"
    return "neutral"


async def _attach_evidence(db: AsyncSession, dev: Development, item: EvidenceItem, tier: str, membership_confidence: float) -> None:
    db.add(DevelopmentEvidence(
        id=str(uuid.uuid4()),
        development_id=dev.id,
        source_type=item.source_type,
        source_id=item.source_id,
        evidence_key=compute_evidence_key(item),
        observed_at=item.observed_at,
        title=item.title,
        direction=item.direction,
        confidence=item.confidence,
        match_tier=tier,
        membership_confidence=membership_confidence,
    ))

    directions_result = await db.execute(
        select(DevelopmentEvidence.direction).where(DevelopmentEvidence.development_id == dev.id)
    )
    all_directions = [d for d in directions_result.scalars().all() if d] + ([item.direction] if item.direction else [])
    confidences_result = await db.execute(
        select(DevelopmentEvidence.confidence).where(DevelopmentEvidence.development_id == dev.id)
    )
    all_confidences = [c for c in confidences_result.scalars().all() if c is not None] + (
        [item.confidence] if item.confidence is not None else []
    )

    dev.last_observed_at = max(_aware(dev.last_observed_at), item.observed_at)
    dev.evidence_count = (dev.evidence_count or 0) + 1
    dev.current_direction = _net_direction(all_directions) or dev.current_direction
    if item.impact_strength:
        dev.current_impact_tier = item.impact_strength
    dev.current_confidence = (sum(all_confidences) / len(all_confidences)) if all_confidences else dev.current_confidence
    dev.updated_at = datetime.now(timezone.utc)


async def resolve_development(db: AsyncSession, item: EvidenceItem) -> ResolutionResult:
    """
    Attach `item` to an existing Development or create a new one.
    Does not commit — caller batches commits (matches this codebase's
    repository convention, see EventRepository).
    """
    existing = await _find_existing_evidence(db, item.source_type, compute_evidence_key(item))
    if existing is not None:
        dev = await db.get(Development, existing.development_id)
        return ResolutionResult(development=dev, tier="existing", created=False)

    tier1_dev = await _tier1_match(db, item)
    if tier1_dev is not None:
        await _attach_evidence(db, tier1_dev, item, "tier1", membership_confidence=1.0)
        return ResolutionResult(development=tier1_dev, tier="tier1", created=False)

    tier2 = await _tier2_match(db, item)
    if tier2 is not None:
        dev, tier = tier2
        strength = _TITLE_OVERLAP_THRESHOLD if tier == "tier2a" else _TITLE_OVERLAP_THRESHOLD_EXT
        await _attach_evidence(db, dev, item, tier, membership_confidence=strength)
        return ResolutionResult(development=dev, tier=tier, created=False)

    dev = Development(
        id=str(uuid.uuid4()),
        canonical_title=item.title,
        status="open",
        primary_company=item.companies[0] if item.companies else None,
        companies=list(item.companies),
        sectors=list(item.sectors),
        category=item.category,
        first_observed_at=item.observed_at,
        last_observed_at=item.observed_at,
        formation_direction=item.direction,
        formation_impact_tier=item.impact_strength,
        formation_confidence=item.confidence,
        current_direction=item.direction,
        current_impact_tier=item.impact_strength,
        current_confidence=item.confidence,
        evidence_count=0,
        schema_version=SCHEMA_VERSION,
    )
    db.add(dev)
    await db.flush()  # dev.id must exist before DevelopmentEvidence FKs to it
    await _attach_evidence(db, dev, item, "seed", membership_confidence=1.0)
    return ResolutionResult(development=dev, tier="seed", created=True)


async def sweep_close_stale(db: AsyncSession) -> int:
    """Flip status open -> closed for Developments with no qualifying
    evidence in CLOSE_AFTER. Never reopened — see module docstring.
    Returns the count closed. Caller commits."""
    cutoff = datetime.now(timezone.utc) - CLOSE_AFTER
    stale = (await db.execute(
        select(Development).where(Development.status == "open", Development.last_observed_at < cutoff)
    )).scalars().all()
    for dev in stale:
        dev.status = "closed"
        dev.updated_at = datetime.now(timezone.utc)
    return len(stale)
