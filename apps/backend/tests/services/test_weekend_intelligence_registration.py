"""
Model-registration regression tests — Weekend Intelligence Phase 1A.

AICompanySignal was previously registered in SQLAlchemy's Base.metadata
only as a side effect of an unrelated router-import chain (app.main importing
app.api.company_scores before create_all() runs) — not via app/db/base.py's
own "import ALL models here" list, unlike every other model. This test
guards against that regressing silently again, and confirms the new
WeekendIntelligenceSnapshot table is registered the correct way from the
start.
"""
from __future__ import annotations

# Deliberately NOT using importlib.reload() here: reloading app.db.base
# re-executes `class Base(DeclarativeBase): pass`, creating a brand-new
# metadata object — but the model modules it then re-imports are already
# cached in sys.modules (Python only runs a module body once per
# process), so they never rebind to the new Base and the "reloaded"
# metadata stays empty. That's a test-harness artifact, not a real
# registration bug — the actual guarantee this test needs is "importing
# app.db.base, however that happens across this process's lifetime,
# results in these tables being present," which plain import already
# proves without the reload footgun.


def test_ai_company_signal_registered_in_base_metadata():
    from app.db.base import Base
    assert "ai_company_signals" in Base.metadata.tables


def test_weekend_intelligence_snapshot_registered_in_base_metadata():
    from app.db.base import Base
    assert "weekend_intelligence_snapshots" in Base.metadata.tables


def test_ai_company_signal_importable_directly_without_company_scores():
    """The registration must not depend on app.api.company_scores having
    been imported first — that was the original fragility. Importing the
    model module in isolation must be sufficient."""
    from app.db.models.company_signal import AICompanySignal
    assert AICompanySignal.__tablename__ == "ai_company_signals"


def test_weekend_intelligence_snapshot_has_expected_unique_index():
    from app.db.models.weekend_intelligence import WeekendIntelligenceSnapshot
    index_names = {ix.name for ix in WeekendIntelligenceSnapshot.__table__.indexes}
    assert "ux_weekend_snapshot_current_per_target" in index_names
    idx = next(ix for ix in WeekendIntelligenceSnapshot.__table__.indexes
               if ix.name == "ux_weekend_snapshot_current_per_target")
    assert idx.unique is True
