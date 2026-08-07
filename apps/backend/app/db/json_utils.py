"""
JSON-array-column containment helper.

SQLAlchemy's generic `Column(JSON, ...).contains([value])` is designed for
PostgreSQL's ARRAY/JSONB `@>` operator. On SQLite (this deployment's actual
production database — confirmed via `/health`), there is no such operator,
so SQLAlchemy silently falls back to a LIKE-based substring match against
the column's serialized text. That match only succeeds for a degenerate
single-element array with matching case (`["Banking"]`, exact string) — any
real multi-element array, or a differently-cased value, gets zero matches
with no error, no warning, nothing. Confirmed live across 4 real call sites
(2026-08-07): `HistoricalMarketEvent.companies.contains(["RELIANCE"])`
returned 0 rows against 9 real matches; `.tags.contains(["2008"])` returned
0 against 1 real match; the `.sectors.contains([...])` bug already found in
publisher.py/market_story_engine.py silently zeroed `historical_intelligence`
publishing for 2 straight days.

This uses SQLite's native JSON1 `json_each()` table-valued function instead
— confirmed available on this deployment — which is the actually-correct
mechanism for "does this JSON array contain this exact value."
"""
from __future__ import annotations

import uuid

from sqlalchemy import text
from sqlalchemy.sql.elements import ColumnElement


def json_array_contains(column, value: str) -> ColumnElement:
    """Returns a boolean SQL expression: true iff `column` (a JSON array)
    contains `value` as an element. Safe to combine with `or_()`/`and_()`
    and to call multiple times against the same column within one query —
    each call gets its own uniquely-named bind parameter, so a loop like
    `[json_array_contains(Model.sectors, s) for s in sectors]` doesn't
    collide.
    """
    table_name = column.table.name
    col_name = column.name
    param_name = f"jac_{col_name}_{uuid.uuid4().hex[:8]}"
    return text(
        f"EXISTS (SELECT 1 FROM json_each({table_name}.{col_name}) je WHERE je.value = :{param_name})"
    ).bindparams(**{param_name: value})
