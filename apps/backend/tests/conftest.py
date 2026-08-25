"""
Session-wide test DB isolation guardrail (C5, 2026-08-25).

Real, repeated incident this session: running the identity test suite
against a copy of the real local dev DB deleted real Company Master rows
(TMPV/RELIANCE/TCS/etc.) as a side effect of legitimate fixture cleanup —
twice, once during C2/C3 verification and again during C4. Neither was a
production defect (the cleanup was doing exactly what test isolation
requires), but tests should never be ABLE to mutate real local data in
the first place, regardless of how careful any individual fixture is.

This module MUST be the first thing pytest imports for this test tree
(conftest.py files load before sibling test modules, guaranteed by
pytest's collection order) and MUST set DATABASE_URL before anything else
imports app.core.config / app.db.session — both read the env var at
*module import time*, not per-call, so any later override is too late.

Every test run now gets its own on-disk scratch DB
(apps/backend/test_scratch.db, gitignored via the repo's existing *.db
rule), wiped and recreated fresh from the real ORM schema at the start of
every test session. It is never the real ig_dev.db, so nothing a test
does — however aggressive the cleanup — can touch real local data.
"""
from __future__ import annotations

import os

_TEST_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "test_scratch.db")
_TEST_DB_URL = f"sqlite+aiosqlite:///{_TEST_DB_PATH}"

for _stale in (_TEST_DB_PATH, _TEST_DB_PATH + "-shm", _TEST_DB_PATH + "-wal"):
    if os.path.exists(_stale):
        os.remove(_stale)

os.environ["DATABASE_URL"] = _TEST_DB_URL

import asyncio  # noqa: E402

import pytest  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _create_test_schema():
    """Synchronous (not async) session fixture, deliberately -- avoids the
    event-loop-scope mismatch a session-scoped ASYNC fixture would hit
    against pytest-asyncio's function-scoped default loop
    (asyncio_default_fixture_loop_scope). asyncio.run() here uses its own
    throwaway loop, independent of whatever loop each test function gets."""
    from app.db.base import Base
    from app.db.session import engine

    async def _create():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_create())
    yield
