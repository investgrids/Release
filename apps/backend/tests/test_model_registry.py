"""
DB model registry completeness — closes the exact class of bug found live
in production 2026-08-31: `MarketRippleScoreSnapshot` was defined and
actively used throughout S1-S5E, but was never added to
`app/db/models/__init__.py`'s import list. `Base.metadata.create_all()`
(app/main.py's real startup path) only creates tables for model classes
that have actually been imported by the time it runs — and every
marketripple_score/ service module imports the model lazily, inside
function bodies, specifically to avoid unnecessary startup cost. So on a
database that had never seen a request reach one of those lazy imports
before `create_all()` ran (production, until today's Company Identity
bootstrap made entity resolution succeed for the first time), the table
was simply never created -- `no such table: marketripple_score_snapshots`
on the very first real query. Every existing test that exercised this
model happened to pass anyway, because some OTHER test file's own direct
top-level import of the model incidentally registered it on Base.metadata
before conftest.py's create_all() ran — masking the real production gap
for as long as this initiative existed.

`test_every_declared_model_is_registered` is the generic guard: it scans
every app/db/models/*.py file directly (never importing app.db.models
itself, so it can't be fooled the same way) for real Base subclasses and
asserts each one appears in __init__.py's own source. Anything not
already registered must be in `_KNOWN_UNREGISTERED_MODELS` below — an
explicit, real, currently-existing gap (found by this same audit,
2026-08-31) in unrelated subsystems (Quant/Index Membership research,
V1 Ripple graph) that already have real production tables from some
earlier registration path and are out of scope for this fix. Adding a
NEW class to that set requires touching this file, which is the point --
it can no longer happen silently.
"""
from __future__ import annotations

import ast
import pathlib

_MODELS_DIR = pathlib.Path(__file__).parent.parent / "app" / "db" / "models"

# Real, pre-existing gaps found during the 2026-08-31 registry audit,
# confirmed via a live production query to already have real tables
# (created through some earlier path, not create_all()'s current
# registry) -- so NOT actively broken today, unlike MarketRippleScoreSnapshot
# was. Deliberately not fixed here: unrelated subsystems, out of scope for
# the Company Identity/MarketRipple Score work this fix belongs to.
_KNOWN_UNREGISTERED_MODELS_WITH_EXISTING_TABLES = {
    "Development", "DevelopmentEvidence",
    "EventCompany", "EventSector", "EventTimeline", "EventNews",
    "EventGraphNode", "EventGraphEdge", "EventSimilar",
    "GovernmentPolicy", "EventPolicy",
    "MacroRelease",
    "OpportunityV2", "OpportunityV2Development",
    "ReturningUserFeedback",
}

# Real, pre-existing gaps confirmed to have NO table in production today
# (same broken state MarketRippleScoreSnapshot was in) -- flagged to the
# owner 2026-08-31, not fixed here: unrelated subsystems (Quant/Index
# Membership research, V1 Ripple graph), not exercised by anything in the
# Company Identity/MarketRipple Score bootstrap.
_KNOWN_UNREGISTERED_MODELS_WITHOUT_TABLES_YET = {
    "IndexMembership", "RippleGraph",
}

_ALLOWED_UNREGISTERED = _KNOWN_UNREGISTERED_MODELS_WITH_EXISTING_TABLES | _KNOWN_UNREGISTERED_MODELS_WITHOUT_TABLES_YET


def _declared_base_subclasses() -> list[tuple[str, str]]:
    """(filename, class_name) for every real ORM model class declared
    directly in app/db/models/*.py -- via source scanning, not import, so
    this can't be fooled by some other module's incidental import."""
    found = []
    for f in sorted(_MODELS_DIR.glob("*.py")):
        if f.name == "__init__.py":
            continue
        tree = ast.parse(f.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                bases = [b.id if isinstance(b, ast.Name) else getattr(b, "attr", "") for b in node.bases]
                if "Base" in bases:
                    found.append((f.name, node.name))
    return found


def test_marketripple_score_snapshot_is_registered():
    """The exact real production bug, 2026-08-31: MarketRippleScoreSnapshot
    must be importable from app.db.models so create_all() creates its table
    on a fresh database (production's real startup path), not just
    incidentally via some test file's own direct import."""
    init_source = (_MODELS_DIR / "__init__.py").read_text(encoding="utf-8")
    assert "MarketRippleScoreSnapshot" in init_source


def test_every_declared_model_is_registered_or_explicitly_known():
    init_source = (_MODELS_DIR / "__init__.py").read_text(encoding="utf-8")
    unregistered = [
        (fname, cname) for fname, cname in _declared_base_subclasses()
        if cname not in init_source
    ]
    unexpected = [(fname, cname) for fname, cname in unregistered if cname not in _ALLOWED_UNREGISTERED]
    assert unexpected == [], (
        f"Found model class(es) not registered in app/db/models/__init__.py and not in the "
        f"documented allowlist -- create_all() will never create their table on a fresh "
        f"database (this is the exact class of bug MarketRippleScoreSnapshot had in "
        f"production): {unexpected}"
    )
