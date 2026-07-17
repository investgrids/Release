"""
Evidence Fusion Engine — merges evidence from every retriever that ran into
one deduplicated, conflict-aware list.

- Dedupe: exact `Evidence.id` collisions are dropped (the same fact
  surfaced by more than one retrieval path).
- Conflict resolution: when two or more retrievers disagree on polarity for
  the *same* entity (one says positive, another negative), all conflicting
  evidence is kept — dropping either side would silently discard a real
  signal — but each item's confidence is dampened, since contradictory
  sources are inherently less reliable than corroborating ones. The
  contradiction itself is returned so the Decision Intelligence Engine can
  record it in `missing_data`/notes rather than pretend certainty.
- Normalize: magnitude/confidence are re-clipped to [0,1] defensively (each
  retriever is expected to already emit normalized values, but fusion is
  the single choke point where that invariant is enforced).
"""
from __future__ import annotations

from app.ai_pipeline.contracts import Evidence

_CONFLICT_DAMPING = 0.85


def _clip(v: float) -> float:
    return min(max(v, 0.0), 1.0)


def fuse(evidence: list[Evidence]) -> tuple[list[Evidence], list[str]]:
    """Returns (fused_evidence, conflicting_entities)."""
    # Dedupe by id, first-seen wins.
    seen_ids: set[str] = set()
    deduped: list[Evidence] = []
    for e in evidence:
        if e.id in seen_ids:
            continue
        seen_ids.add(e.id)
        deduped.append(e)

    # Group by entity to find polarity conflicts.
    by_entity: dict[str, list[Evidence]] = {}
    for e in deduped:
        if e.entity:
            by_entity.setdefault(e.entity, []).append(e)

    conflicting_entities: list[str] = []
    dampened_ids: set[str] = set()
    for entity, items in by_entity.items():
        polarities = {e.polarity for e in items if e.polarity in ("positive", "negative")}
        if len(polarities) > 1:
            conflicting_entities.append(entity)
            dampened_ids.update(e.id for e in items)

    fused: list[Evidence] = []
    for e in deduped:
        confidence = _clip(e.confidence)
        magnitude = _clip(e.magnitude)
        if e.id in dampened_ids:
            confidence = _clip(confidence * _CONFLICT_DAMPING)
        fused.append(Evidence(
            id=e.id, source=e.source, entity=e.entity, claim=e.claim,
            polarity=e.polarity, magnitude=magnitude, confidence=confidence,
            timestamp=e.timestamp, raw=e.raw,
        ))

    return fused, conflicting_entities
