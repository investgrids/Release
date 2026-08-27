"""
Point-in-time NIFTY 50 membership — Phase B0 leakage-lock regression
tests (owner instruction, 2026-08-23). Real, sourced membership data
(index_membership_seed.py), not synthetic — same convention as the
existing leakage tests (test_quant_leakage.py).

These directly validate the fix for a confirmed survivorship bias: real
stored predictions exist for ETERNAL dated back to 2021-09-24, more than
three years before it actually joined the NIFTY 50 (2025-03-28, real
NSE Indices press release — see index_membership_seed.py).
"""
from __future__ import annotations

from datetime import date

import pytest

from app.db.session import AsyncSessionLocal
from app.services.quant import universe as universe_module
from app.services.quant.membership import is_member_at, universe_as_of


@pytest.mark.asyncio
async def test_future_constituent_exclusion():
    """A company joining at date J must not be eligible for any T < J.
    ETERNAL joined 2025-03-28 (real, sourced) — the exact literal case
    the Phase B0 audit found contaminated: real stored predictions dated
    2021-09-24, the audit's own flagged date."""
    async with AsyncSessionLocal() as db:
        assert await is_member_at(db, "ETERNAL", date(2021, 9, 24)) is False, (
            "the exact contaminated date the audit found — must be ineligible"
        )
        assert await is_member_at(db, "ETERNAL", date(2025, 3, 27)) is False, "one day before inclusion"
        assert await is_member_at(db, "ETERNAL", date(2025, 3, 28)) is True, "the real inclusion date itself"
        assert await is_member_at(db, "ETERNAL", date(2025, 6, 1)) is True, "well after inclusion"


@pytest.mark.asyncio
async def test_removed_constituent_history():
    """A company removed at R remains eligible before R and becomes
    ineligible after the effective removal date. HEROMOTOCO: removed
    effective 2025-09-30 (real, sourced) — eligible through 2025-09-29."""
    async with AsyncSessionLocal() as db:
        assert await is_member_at(db, "HEROMOTOCO", date(2021, 8, 16)) is True, "was a real member at data-window start"
        assert await is_member_at(db, "HEROMOTOCO", date(2025, 9, 29)) is True, "last real day of membership"
        assert await is_member_at(db, "HEROMOTOCO", date(2025, 9, 30)) is False, "removal effective date — no longer eligible"
        assert await is_member_at(db, "HEROMOTOCO", date(2026, 1, 1)) is False, "well after removal"


@pytest.mark.asyncio
async def test_as_of_universe_reflects_only_the_interval_containing_t():
    """universe_as_of(T) must return membership based only on the
    interval containing T — checked at three real, distinct dates."""
    async with AsyncSessionLocal() as db:
        # Before ANY of the four Phase B0-flagged additions existed as constituents.
        early = await universe_as_of(db, date(2021, 9, 24))
        for sym in ("ETERNAL", "TRENT", "BEL", "SHRIRAMFIN"):
            assert sym not in early, f"{sym} must not be eligible on 2021-09-24 — real inclusion is years later"
        assert "RELIANCE" in early, "long-standing real constituent must still be present"

        # After all four are real members, before HEROMOTOCO/INDUSINDBK removal.
        mid = await universe_as_of(db, date(2025, 6, 1))
        for sym in ("ETERNAL", "TRENT", "BEL", "SHRIRAMFIN"):
            assert sym in mid, f"{sym} must be eligible on 2025-06-01 — real inclusion already happened"
        assert "HEROMOTOCO" in mid, "not yet removed on this date"

        # After the Sept 2025 reconstitution.
        late = await universe_as_of(db, date(2026, 1, 1))
        assert "HEROMOTOCO" not in late, "removed effective 2025-09-30 — must be gone by 2026"
        assert "INDUSINDBK" not in late, "same reconstitution event"
        assert "ETERNAL" in late


@pytest.mark.asyncio
async def test_current_snapshot_does_not_control_history():
    """Changing today's static NIFTY_50 list must not alter historical
    membership returned for a past date — universe_as_of() reads only
    the IndexMembership table and never imports universe.py::NIFTY_50 at
    all, so this is structurally guaranteed, not incidentally true."""
    original = universe_module.NIFTY_50
    try:
        # Mutate the static "current" list — remove RELIANCE entirely.
        universe_module.NIFTY_50 = tuple(s for s in original if s != "RELIANCE")

        async with AsyncSessionLocal() as db:
            historical = await universe_as_of(db, date(2022, 1, 1))
        assert "RELIANCE" in historical, (
            "mutating today's static list changed a PAST as-of result — "
            "universe_as_of() must be fully decoupled from universe.py::NIFTY_50"
        )
    finally:
        universe_module.NIFTY_50 = original
