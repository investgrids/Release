"""
Peer groups inside one display sector (owner decision 2026-10-03).

"Infrastructure" mixed three different kinds of business — road/EPC builders,
capital-goods manufacturers and logistics operators — so the valuation and
financial-strength percentiles compared a road builder with a machine-tool
maker. The display sector stays "Infrastructure"; scores are calculated and
ranked against the company's own peer group instead:

    Construction & Infrastructure | Capital Goods | Logistics & Transport

Assignments are explicit, per company, in app/data/infrastructure_peer_groups.json
(each with the business basis it was assigned on). A company whose business
fits none of the three is listed under "unmatched" with the reason and is not
scored — it is never placed in a group it doesn't belong to.

Release control: a grouped sector listed in REVIEW_SECTORS is withheld from the
public ("Peer group under review") whatever snapshots exist, so the corrected
group is switched on together after a before/after review. A snapshot that
carries no peer_group is never public in a grouped sector, so old and new peer
definitions can never mix. Releasing = removing the sector from REVIEW_SECTORS.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

GROUPED_SECTORS = {"Infrastructure"}
REVIEW_SECTORS: set[str] = {"Infrastructure"}  # withheld until released by a deliberate change

_DATA = Path(__file__).resolve().parents[2] / "data" / "infrastructure_peer_groups.json"


@lru_cache(maxsize=1)
def _data() -> dict:
    return json.loads(_DATA.read_text(encoding="utf-8"))


def peer_group_names() -> list[str]:
    return list(_data()["groups"])


def peer_group_for(symbol: str | None) -> str | None:
    """The company's peer group, or None (unmatched, or not in a grouped sector)."""
    entry = _data()["assignments"].get((symbol or "").upper().split(".")[0])
    return entry["group"] if entry else None


def unmatched_reason(symbol: str | None) -> str | None:
    return _data()["unmatched"].get((symbol or "").upper().split(".")[0])


def split_into_peer_groups(sector: str, symbols: list[str]) -> dict[str, list[str]]:
    """{peer group: members}. An ungrouped sector is one group named after the
    sector. In a grouped sector, unmatched companies are left out entirely and
    a company with no assignment at all raises: it must be reviewed, not guessed."""
    if sector not in GROUPED_SECTORS:
        return {sector: list(symbols)}
    groups: dict[str, list[str]] = {name: [] for name in peer_group_names()}
    unassigned = []
    for s in symbols:
        g = peer_group_for(s)
        if g:
            groups[g].append(s)
        elif unmatched_reason(s) is None:
            unassigned.append(s)
    if unassigned:
        raise ValueError(f"{sector}: {len(unassigned)} candidate(s) have no peer-group assignment: {sorted(unassigned)[:10]}")
    return {k: v for k, v in groups.items() if v}
