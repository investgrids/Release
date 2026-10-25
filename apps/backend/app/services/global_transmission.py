"""
Global Markets Brief — transmission linkage (deterministic, isolated).

Reads ONLY the isolated global_transmission_relationships table; never the
shared ig_edges graph. Produces "potential India impact" hypotheses only when
BOTH an eligible (approved + cited) relationship AND a verified, timestamped
triggering observation exist, and the observation falls within the
relationship's explicit lag window. No LLM. No fabrication. A relationship
existing is not evidence; a trigger existing is not proof of impact.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.global_transmission import GlobalTransmissionRelationship

_VALID_TARGET_TYPES = {"sector", "instrument", "indicator"}
_VALID_DIRECTIONS = {"positive", "negative"}
_LIMITATION = "Potential relationship; actual market impact is not confirmed."


def is_eligible(rel: Any) -> bool:
    """A relationship may produce a hypothesis only if ALL hold. A row that
    fails any check is silently unusable — never a fabrication path."""
    if not getattr(rel, "approved", False):
        return False
    if not (getattr(rel, "citation", None) or "").strip():
        return False
    if not (getattr(rel, "evidence_basis", None) or "").strip():
        return False
    if not (getattr(rel, "source_factor", None) or "").strip():
        return False
    if getattr(rel, "target_type", None) not in _VALID_TARGET_TYPES:
        return False
    if not (getattr(rel, "target_key", None) or "").strip():
        return False
    if getattr(rel, "direction", None) not in _VALID_DIRECTIONS:
        return False
    # Explicit lag window — no silent default; must be defined and non-negative.
    lo, hi = getattr(rel, "lag_days_min", None), getattr(rel, "lag_days_max", None)
    if lo is None or hi is None or lo < 0 or hi < lo:
        return False
    return True


async def get_eligible_relationships(db: AsyncSession) -> list[GlobalTransmissionRelationship]:
    rows = (await db.execute(select(GlobalTransmissionRelationship))).scalars().all()
    return [r for r in rows if is_eligible(r)]


async def observed_global_triggers() -> list[dict]:
    """Verified, timestamped global observations keyed by source_factor.

    Phase 1: returns [] — there is no wired, verified global-trigger source yet
    mapped to source_factor keys. (US Fed policy events exist in EventTriage but
    aren't tagged to a factor; macro-rate observations aren't persisted — see the
    separate macro-rates defect.) This is the honest current state: the machinery
    is complete and will populate as the Phase 2 feed/evidence work lands. Until
    then, zero triggers ⇒ zero implications, regardless of approved relationships.
    """
    return []


def derive_india_implications(
    relationships: list[Any],
    triggers: list[dict],
    now: datetime | None = None,
) -> list[dict]:
    """Pure linkage. For each verified trigger, emit a labeled hypothesis for
    every eligible relationship whose source_factor matches AND whose explicit
    lag window contains the trigger's age. Output never claims an observed target
    move; it describes a POTENTIAL path with an explicit limitation."""
    now = now or datetime.now(timezone.utc)
    out: list[dict] = []
    by_factor: dict[str, list[Any]] = {}
    for r in relationships:
        if is_eligible(r):
            by_factor.setdefault(r.source_factor, []).append(r)

    for trig in triggers:
        factor = trig.get("factor")
        observed_at = trig.get("observed_at")
        if not factor or observed_at is None or factor not in by_factor:
            continue
        age_days = (now - observed_at).total_seconds() / 86400.0
        for r in by_factor[factor]:
            # Trigger must fall within the relationship's explicit window.
            if age_days < r.lag_days_min or age_days > r.lag_days_max:
                continue
            verb = "upward pressure on" if r.direction == "positive" else "downward pressure on"
            out.append({
                # Public-facing (the existing india_implications item shape):
                "hypothesis": f"{trig.get('label', factor)} could exert {verb} {r.target_label}",
                "basis": r.evidence_basis,
                "confidence": "hypothesis",
                "limitation": _LIMITATION,
                # Internal provenance for review (not required by the public UI):
                "_provenance": {
                    "trigger_factor": factor,
                    "trigger_label": trig.get("label"),
                    "trigger_observed_at": observed_at.isoformat() if hasattr(observed_at, "isoformat") else str(observed_at),
                    "trigger_source": trig.get("source"),
                    "relationship_id": getattr(r, "id", None),
                    "direction": r.direction,
                    "target_type": r.target_type,
                    "target_key": r.target_key,
                    "numeric_confidence": r.confidence,
                    "lag_window_days": [r.lag_days_min, r.lag_days_max],
                    "citation": r.citation,
                },
            })
    return out
