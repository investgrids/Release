"""
Development -> Intelligence Graph linking — Phase 6B.

A new consumer of Development Memory, not a change to the existing graph.
Reuses upsert_node()/upsert_edge() (app/services/intelligence_graph_service.py)
— the exact primitives update_from_event() already uses for its own
event:{id} nodes — rather than any new write path into ig_nodes/ig_edges.
update_from_event()/triage_worker.py are untouched by this module and keep
running exactly as before; the two paths coexist deliberately (see this
module's docstring on is_graph_worthy for why retiring the raw event:*
path is a later decision, not part of 6B).

Not every Development gets a node — is_graph_worthy() gates on
CORROBORATION or MATERIALITY (whichever comes first), reusing existing
signals rather than inventing a new score: Development.evidence_count
(6A), Development.formation_impact_tier (already sourced from
scoring_engine's compute_priority via evidence_clustering's
normalize_event), and EventTriage.urgency (the same >=7 threshold
update_from_event itself uses for its own node-creation decision).

Company matching uses IGNode.ticker equality, not id-slug guessing —
existing company nodes are inconsistently slugged from either a resolved
name or a ticker fallback (confirmed against the live graph: some ids are
clean, some are junk like "company:nse-nse"), so ticker is the only
reliable join key. Sector/theme matching uses upsert_node's own
label->slug id derivation directly, since IGNode ids are already
lowercase-normalized and this codebase's sector labels, despite
inconsistent casing, tokenize to the same slug either way.

Every read on the passed-in `db` is immediately followed by a commit,
even though these are all SELECTs with nothing to flush -- upsert_node()/
upsert_edge() each open and commit their OWN AsyncSessionLocal(), and on
SQLite a writer can't get its exclusive lock while `db` is still holding
an open (even read-only) transaction from an uncommitted SELECT. Confirmed
live: without this, a real multi-Development sync run hit "database is
locked" on the second or third upsert_node() call. This function's own
reads/writes interleave company/sector/theme/policy lookups with upserts
per Development, so the discipline has to be applied consistently
throughout, not just once at the top.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.development import Development, DevelopmentEvidence
from app.db.models.event import GovernmentPolicy
from app.db.models.intelligence import EventTriage
from app.db.models.intelligence_graph import IGNode
from app.services.intelligence_graph_service import upsert_edge, upsert_node

HIGH_IMPACT_TIERS = {"Critical", "High"}
HIGH_URGENCY_THRESHOLD = 7  # matches update_from_event's own node-creation gate exactly


async def is_graph_worthy(db: AsyncSession, dev: Development) -> bool:
    """Corroboration OR materiality — a single authoritative filing (e.g.
    an RBI decision) shouldn't need a second outlet repeating it to earn
    a node, and routine duplicate coverage of something minor shouldn't
    earn one just because 2 outlets carried it. These are different
    dimensions, checked independently, not combined into one score."""
    if (dev.evidence_count or 0) >= 2:
        return True
    if dev.formation_impact_tier in HIGH_IMPACT_TIERS:
        return True

    event_source_ids = (await db.execute(
        select(DevelopmentEvidence.source_id).where(
            DevelopmentEvidence.development_id == dev.id,
            DevelopmentEvidence.source_type == "event",
        )
    )).scalars().all()
    if not event_source_ids:
        await db.commit()  # DO NOT REMOVE — releases db's read lock before the next upsert_node()/upsert_edge() call opens its own session; see module docstring ("database is locked")
        return False

    urgencies = (await db.execute(
        select(EventTriage.urgency).where(EventTriage.event_id.in_(event_source_ids))
    )).scalars().all()
    await db.commit()  # DO NOT REMOVE — see module docstring ("database is locked")
    return any((u or 0) >= HIGH_URGENCY_THRESHOLD for u in urgencies)


def _edge_type_for_direction(direction: str | None) -> str:
    if direction in ("positive", "bullish"):
        return "benefits"
    if direction in ("negative", "bearish"):
        return "hurts"
    return "influences"


async def _find_company_node_id(db: AsyncSession, ticker: str) -> str | None:
    result = await db.execute(
        select(IGNode.id).where(IGNode.node_type == "company", IGNode.ticker == ticker)
    )
    node_id = result.scalar_one_or_none()
    await db.commit()  # DO NOT REMOVE — see module docstring ("database is locked")
    return node_id


async def _linked_policy_titles(db: AsyncSession, development_id: str) -> list[str]:
    policy_ids = (await db.execute(
        select(DevelopmentEvidence.source_id).where(
            DevelopmentEvidence.development_id == development_id,
            DevelopmentEvidence.source_type == "policy",
        )
    )).scalars().all()
    await db.commit()  # DO NOT REMOVE — see module docstring ("database is locked")
    if not policy_ids:
        return []
    titles = (await db.execute(
        select(GovernmentPolicy.title).where(GovernmentPolicy.id.in_([int(pid) for pid in policy_ids]))
    )).scalars().all()
    await db.commit()  # DO NOT REMOVE — see module docstring ("database is locked")
    return [t for t in titles if t]


async def _backfill_legacy_event_link(db: AsyncSession, development_id: str, dev_node_id: str) -> None:
    """Exact-membership-only: if a legacy event:{id} node already exists
    for an event this Development actually contains as evidence, link it.
    Never fuzzy-searches for a "probably related" legacy node. Idempotent
    via upsert_edge's deterministic edge id — safe to call on every sync."""
    event_source_ids = (await db.execute(
        select(DevelopmentEvidence.source_id).where(
            DevelopmentEvidence.development_id == development_id,
            DevelopmentEvidence.source_type == "event",
        )
    )).scalars().all()
    await db.commit()  # DO NOT REMOVE — see module docstring ("database is locked")

    for event_id in event_source_ids:
        legacy_node_id = f"event:{event_id}"
        exists = (await db.execute(
            select(IGNode.id).where(IGNode.id == legacy_node_id)
        )).scalar_one_or_none()
        await db.commit()  # DO NOT REMOVE — see module docstring ("database is locked")
        if exists:
            await upsert_edge(legacy_node_id, dev_node_id, "represented_by", auto_added=True)


async def link_development_to_graph(db: AsyncSession, dev: Development) -> str | None:
    """Create/refresh the development:{id} node and its entity edges.
    Returns the node id if linked (already-linked Developments are
    refreshed, not skipped, so new companies/sectors/themes accumulated
    since the last link still get edges). No-op (returns None) if
    is_graph_worthy() says no. Does not commit `dev` itself — caller
    persists dev.ig_node_id.

    Snapshots every `dev` field into a local up front, before any of the
    intermediate commits below run — AsyncSession's default
    expire_on_commit means touching an ORM attribute after any of those
    commits would trigger a fresh implicit SELECT that itself leaves a
    new open (uncommitted) transaction on `db`, undoing the whole point
    of committing after each read."""
    dev_id, canonical_title = dev.id, dev.canonical_title
    companies, sectors, themes = list(dev.companies or []), list(dev.sectors or []), list(dev.themes or [])
    direction = dev.current_direction

    if not await is_graph_worthy(db, dev):
        return None

    dev_node_id = f"development:{dev_id}"
    await upsert_node("development", canonical_title, node_id=dev_node_id, auto_added=True)

    et = _edge_type_for_direction(direction)

    for ticker in companies:
        company_node_id = await _find_company_node_id(db, ticker)
        if company_node_id is None:
            company_node_id = await upsert_node("company", ticker, ticker=ticker, auto_added=True)
        await upsert_edge(dev_node_id, company_node_id, et, auto_added=True)

    for sector in sectors[:5]:
        sector_node_id = await upsert_node("sector", sector, auto_added=True)
        await upsert_edge(dev_node_id, sector_node_id, et, auto_added=True)

    for theme in themes[:5]:
        theme_node_id = await upsert_node("theme", theme, auto_added=True)
        await upsert_edge(dev_node_id, theme_node_id, et, auto_added=True)

    for policy_title in await _linked_policy_titles(db, dev_id):
        policy_node_id = await upsert_node("policy", policy_title, auto_added=True)
        # development triggered_by policy — the causal direction runs
        # policy -> development, matching how "triggered_by" is already
        # used elsewhere (source triggered_by target = source was caused
        # by target).
        await upsert_edge(dev_node_id, policy_node_id, "triggered_by", auto_added=True)

    await _backfill_legacy_event_link(db, dev_id, dev_node_id)

    return dev_node_id
