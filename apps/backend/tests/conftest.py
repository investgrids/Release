"""
Session-wide test DB isolation guardrail (P1.1, 2026-08-30).

Ported from the proven pattern built on company-identity/c1-reconciliation
(real repeated incident there: test cleanup deleted real Company Master
rows, twice). `main` never had this at all -- confirmed via `find` on
apps/backend/tests/ returning no conftest.py before this file existed.
Real, current consequence found this session: this branch's own new
CandidateRun tests, and every other test in this tree, were running
directly against the real local ig_dev.db file with zero isolation --
the P1 test suite passing meant nothing about whether it could also
mutate real, production-mirrored data along the way.

This module MUST be the first thing pytest imports for this test tree
(conftest.py files load before sibling test modules, guaranteed by
pytest's collection order) and MUST set DATABASE_URL before anything else
imports app.core.config / app.db.session -- both read the env var at
*module import time*, not per-call (Settings() is instantiated at
app/core/config.py's module level; the engine is created at
app/db/session.py's module level), so any later override is too late.

Every test run gets its own on-disk scratch DB (apps/backend/
test_scratch.db, gitignored via the repo's existing *.db rule), wiped and
recreated fresh from the real ORM schema at the start of every test
session. It is never the real ig_dev.db, so nothing a test does --
however aggressive the cleanup -- can touch real local data.

Fail-closed guard (new, not present in the ported original): after the
override, this module imports app.core.config for real and asserts its
resolved database_url is neither the real dev DB's filename nor anything
other than the exact expected scratch URL -- refusing to even collect
tests otherwise. This catches the override silently failing to take
effect (a future config refactor, an env var already set by something
that imports earlier, a .env precedence change) before any test can run
against real data, rather than trusting the string-setting step above
never regresses.
"""
from __future__ import annotations

import os

_TEST_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "test_scratch.db")
_TEST_DB_URL = f"sqlite+aiosqlite:///{_TEST_DB_PATH}"
_REAL_DEV_DB_MARKER = "ig_dev.db"  # the real dev DB's filename -- must never appear in the resolved test URL

for _stale in (_TEST_DB_PATH, _TEST_DB_PATH + "-shm", _TEST_DB_PATH + "-wal"):
    if os.path.exists(_stale):
        os.remove(_stale)

os.environ["DATABASE_URL"] = _TEST_DB_URL

import asyncio  # noqa: E402

import pytest  # noqa: E402

from app.core.config import settings  # noqa: E402

# Fail-closed: refuse to even collect tests if the override above didn't
# actually take effect, for any reason.
if _REAL_DEV_DB_MARKER in settings.database_url:
    raise RuntimeError(
        f"REFUSING TO RUN TESTS: settings.database_url resolved to "
        f"{settings.database_url!r}, which looks like the real development "
        f"database ({_REAL_DEV_DB_MARKER}). Tests must never be able to "
        f"connect to it. This means the DATABASE_URL override in this "
        f"conftest.py did not take effect -- check that nothing imports "
        f"app.core.config before this file runs."
    )
if settings.database_url != _TEST_DB_URL:
    raise RuntimeError(
        f"REFUSING TO RUN TESTS: settings.database_url is "
        f"{settings.database_url!r}, expected the isolated scratch DB "
        f"{_TEST_DB_URL!r}. Refusing to run tests against an unexpected "
        f"database rather than guessing it's safe."
    )


@pytest.fixture(scope="session", autouse=True)
def _create_test_schema():
    """Synchronous (not async) session fixture, deliberately -- avoids the
    event-loop-scope mismatch a session-scoped ASYNC fixture would hit
    against pytest-asyncio's function-scoped default loop
    (asyncio_default_fixture_loop_scope). asyncio.run() here uses its own
    throwaway loop, independent of whatever loop each test function gets."""
    import app.db.models  # noqa: F401 -- registers every real model (including
    # the new CandidateRun) on Base.metadata before create_all() below, so
    # a new table needs no one-off manual creation script -- the exact gap
    # that made this session create candidate_run by hand against the real
    # dev DB before this guardrail existed.
    from app.db.base import Base
    from app.db.session import engine

    async def _create():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_create())
    yield
