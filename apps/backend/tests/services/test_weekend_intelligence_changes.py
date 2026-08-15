"""Changes-since-prior synthesis — pure function, no DB."""
from __future__ import annotations

from app.services.weekend_intelligence.changes import COMPANY, NEW, SECTOR, STATE_CHANGED, STRENGTHENED, WEAKENED, compute_changes
from app.services.weekend_intelligence.company_synthesis import CompanySignal
from app.services.weekend_intelligence.sector_synthesis import SectorSignal


def _sector(name, confidence, direction="positive"):
    return SectorSignal(sector=name, direction=direction, strength="medium", confidence=confidence,
                         evidence_count=2, positive_evidence=2, negative_evidence=0)


def _company(symbol, state):
    return CompanySignal(symbol=symbol, state=state, signal_strength="medium", confidence=0.5, evidence_count=2)


def test_new_sector_with_no_prior_state():
    changes = compute_changes([_sector("Defence", 0.6)], [], None, None)
    assert len(changes) == 1
    assert changes[0].type == NEW
    assert changes[0].entity_type == SECTOR
    assert changes[0].entity_id == "Defence"


def test_sector_strengthened():
    prior = [{"sector": "Banking", "score": 0.3, "direction": "positive"}]
    changes = compute_changes([_sector("Banking", 0.6)], [], prior, None)
    assert len(changes) == 1
    assert changes[0].type == STRENGTHENED


def test_sector_weakened():
    prior = [{"sector": "Banking", "score": 0.7, "direction": "positive"}]
    changes = compute_changes([_sector("Banking", 0.3)], [], prior, None)
    assert changes[0].type == WEAKENED


def test_sector_small_delta_is_not_reported():
    prior = [{"sector": "Banking", "score": 0.5, "direction": "positive"}]
    changes = compute_changes([_sector("Banking", 0.52)], [], prior, None)
    assert changes == []


def test_new_company_entering_watch_list():
    """The brief's own literal example: 'BEL entered high-conviction watch'."""
    changes = compute_changes([], [_company("BEL", "high_conviction_watch")], None, None)
    assert len(changes) == 1
    assert changes[0].type == NEW
    assert changes[0].entity_type == COMPANY
    assert "high conviction watch" in changes[0].reason


def test_company_state_transition_detected():
    prior = [{"symbol": "BEL", "state": "positive_watch"}]
    changes = compute_changes([], [_company("BEL", "high_conviction_watch")], None, prior)
    assert changes[0].type == STATE_CHANGED
    assert "positive watch" in changes[0].reason and "high conviction watch" in changes[0].reason


def test_company_same_state_produces_no_change():
    prior = [{"symbol": "BEL", "state": "high_conviction_watch"}]
    changes = compute_changes([], [_company("BEL", "high_conviction_watch")], None, prior)
    assert changes == []


def test_no_prior_and_no_current_produces_no_changes():
    assert compute_changes([], [], None, None) == []
