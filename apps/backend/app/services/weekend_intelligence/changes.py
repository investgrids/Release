"""
Changes-since-prior synthesis — brief §8.

Generalizes the proven HomepageDailySnapshot / get_yesterday_changes()
pattern (Phase 1 architecture doc §5): diff the newly-computed sector/
company signals against the PRIOR WeekendIntelligenceSnapshot's own
stored compact state for the same target_trading_date — not a fresh
re-derivation from raw evidence, and not a naive date subtraction (a
Saturday-morning checkpoint has no "yesterday" row; this compares
against whatever the most recent PRIOR VERSION actually was, exactly
like get_yesterday_changes()'s "most recent prior day, whatever that
is" query shape).

Output stays machine-readable (brief §8: "Do not make these
frontend-formatted sentences only") — `reason` is a plain-English
one-liner for convenience, but type/entity_type/entity_id/direction/
strength/evidence_refs are the structured fields callers should key off.

IMPORTANT — this is NOT "what's new since Friday's close" (that's
materiality.select_new_since_close / aggregator.py's
new_since_close_refs, a separate concept computed directly from the
evidence window). This module diffs against the PRIOR SNAPSHOT
VERSION's own stored top_sector_refs/top_company_refs. On the very
first checkpoint ever created for a target_trading_date, there IS no
prior version, so every entry here trivially reports type=NEW — that
is correct for what this function actually measures ("did anything
change since the last time we computed this"), but it must not be read
as "N new developments this weekend": a quiet weekend with one real
development still produces one NEW entry per top sector/company it
touches on v1, which is a structural artifact of "no prior version to
diff against," not a count of real developments. Use
new_since_close_count for that question instead.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.services.weekend_intelligence.company_synthesis import CompanySignal
from app.services.weekend_intelligence.sector_synthesis import SectorSignal

SECTOR = "sector"
COMPANY = "company"

NEW = "new"
STRENGTHENED = "strengthened"
WEAKENED = "weakened"
STATE_CHANGED = "state_changed"

# Below this confidence delta, a sector's change is noise, not a real
# strengthen/weaken worth surfacing.
_CONFIDENCE_DELTA_THRESHOLD = 0.15


@dataclass
class Change:
    type: str
    entity_type: str
    entity_id: str
    direction: str | None
    strength: str | None
    reason: str
    evidence_refs: list[dict] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "type": self.type, "entity_type": self.entity_type, "entity_id": self.entity_id,
            "direction": self.direction, "strength": self.strength, "reason": self.reason,
            "evidence_refs": self.evidence_refs,
        }


def compute_changes(
    sector_signals: list[SectorSignal],
    company_signals: list[CompanySignal],
    prior_top_sector_refs: list[dict] | None,
    prior_top_company_refs: list[dict] | None,
) -> list[Change]:
    changes: list[Change] = []

    prior_sectors = {r["sector"]: r for r in (prior_top_sector_refs or [])}
    for s in sector_signals:
        prior = prior_sectors.get(s.sector)
        if prior is None:
            if s.confidence >= _CONFIDENCE_DELTA_THRESHOLD:
                changes.append(Change(
                    type=NEW, entity_type=SECTOR, entity_id=s.sector,
                    direction=s.direction, strength=s.strength,
                    reason=f"{s.sector} newly appeared with a {s.direction} signal ({s.evidence_count} evidence item(s))",
                    evidence_refs=s.evidence_refs,
                ))
            continue
        delta = s.confidence - float(prior.get("score", 0.0))
        if abs(delta) >= _CONFIDENCE_DELTA_THRESHOLD:
            changes.append(Change(
                type=STRENGTHENED if delta > 0 else WEAKENED,
                entity_type=SECTOR, entity_id=s.sector,
                direction=s.direction, strength=s.strength,
                reason=f"{s.sector} signal {'strengthened' if delta > 0 else 'weakened'} ({prior.get('score', 0.0):.2f} -> {s.confidence:.2f})",
                evidence_refs=s.evidence_refs,
            ))

    prior_companies = {r["symbol"]: r for r in (prior_top_company_refs or [])}
    for c in company_signals:
        prior = prior_companies.get(c.symbol)
        if prior is None:
            changes.append(Change(
                type=NEW, entity_type=COMPANY, entity_id=c.symbol,
                direction=None, strength=c.signal_strength,
                reason=f"{c.symbol} entered {c.state.replace('_', ' ')}",
            ))
            continue
        if prior.get("state") != c.state:
            changes.append(Change(
                type=STATE_CHANGED, entity_type=COMPANY, entity_id=c.symbol,
                direction=None, strength=c.signal_strength,
                reason=f"{c.symbol} moved from {str(prior.get('state')).replace('_', ' ')} to {c.state.replace('_', ' ')}",
            ))

    return changes
