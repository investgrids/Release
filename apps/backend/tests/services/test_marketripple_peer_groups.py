import json
from types import SimpleNamespace

import pytest

from app.services.marketripple_score import peer_groups
from app.services.marketripple_score.coverage import score_sector_for
from app.services.marketripple_score.data_quality import peer_group_reasons
from app.services.marketripple_score.eligibility import REASON_NO_MATCHING_PEER_GROUP, REASON_PEER_GROUP_UNDER_REVIEW

_DATA = peer_groups._data()


def test_assignments_and_unmatched_reconcile_to_390_with_no_overlap():
    assigned, unmatched = set(_DATA["assignments"]), set(_DATA["unmatched"])
    assert not assigned & unmatched
    assert len(assigned) + len(unmatched) == 390
    assert {a["group"] for a in _DATA["assignments"].values()} == set(_DATA["groups"])
    assert all(a["basis"] for a in _DATA["assignments"].values()) and all(_DATA["unmatched"].values())


def test_geship_is_logistics_and_unmatched_have_no_group():
    assert peer_groups.peer_group_for("GESHIP") == "Logistics & Transport"
    assert peer_groups.peer_group_for("LT") == "Construction & Infrastructure"
    assert peer_groups.peer_group_for("ADANIENT") is None and peer_groups.unmatched_reason("ADANIENT")


def test_split_excludes_unmatched_and_raises_on_unassigned():
    out = peer_groups.split_into_peer_groups("Infrastructure", ["LT", "GESHIP", "ADANIENT", "ABB"])
    assert sorted(m for v in out.values() for m in v) == ["ABB", "GESHIP", "LT"]
    with pytest.raises(ValueError):
        peer_groups.split_into_peer_groups("Infrastructure", ["NOT_A_REAL_SYMBOL"])
    assert peer_groups.split_into_peer_groups("Metals", ["X"]) == {"Metals": ["X"]}


def test_gate_withholds_review_unmatched_and_legacy_snapshots(monkeypatch):
    snap = SimpleNamespace(symbol="LT", peer_group="Construction & Infrastructure")
    assert peer_group_reasons(snap) == [REASON_PEER_GROUP_UNDER_REVIEW]  # sector under review
    monkeypatch.setattr(peer_groups, "REVIEW_SECTORS", set())
    assert peer_group_reasons(snap) == []  # released, calculated against its group
    assert peer_group_reasons(SimpleNamespace(symbol="LT", peer_group=None)) == [REASON_PEER_GROUP_UNDER_REVIEW]  # old mixed-peer snapshot
    assert peer_group_reasons(SimpleNamespace(symbol="ADANIENT", peer_group=None)) == [REASON_NO_MATCHING_PEER_GROUP]
    assert peer_group_reasons(SimpleNamespace(symbol="TCS", peer_group=None)) == [] or score_sector_for("TCS") != "Infrastructure"


def test_coverage_state_says_review_and_no_peer_group_consistently(monkeypatch):
    from app.services.marketripple_score.coverage import STATE_LABELS, coverage_fields, coverage_state

    old = SimpleNamespace(symbol="LT", peer_group=None, calculated_at=None)
    # sector under review: even with no snapshot, and for an old mixed-peer snapshot
    assert coverage_state("Infrastructure", None, "LT")[0] == "peer_group_review"
    assert coverage_fields("Infrastructure", None, "LT")["coverage_label"] == "Peer group under review"
    # unmatched is its own label, never "Insufficient data"
    f = coverage_fields("Infrastructure", None, "ADANIENT")
    assert f["coverage_state"] == "no_peer_group" and f["coverage_label"] == "No matching peer group"
    assert STATE_LABELS["peer_group_review"] != STATE_LABELS["insufficient_data"]
    # an ungrouped sector is untouched
    assert coverage_state("Metals", None, "TATASTEEL")[0] == "not_processed"
