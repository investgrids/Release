"""
Directory sector backfill (2026-09-28, owner: "some company we are not able
to show the sector") — real source labels mapped into the site's own sector
names, never guessed.
"""
from __future__ import annotations

import pytest

from app.api.companies import _NSE_UNIVERSE
from app.services.company_identity import sector_mapping as sm


@pytest.fixture
def sources(monkeypatch):
    def _set(data: dict):
        monkeypatch.setattr(sm, "_sources", lambda: data)
    return _set


def test_nse_label_takes_its_mapped_site_sector(sources):
    sources({"X": {"source": "NSE", "industry": "Automobile and Auto Components"}})
    assert sm.site_sector_for("X") == "Automotive"


def test_yahoo_industry_label_takes_its_mapped_site_sector(sources):
    sources({"X": {"source": "Yahoo Finance", "sector": "Industrials", "industry": "Integrated Freight & Logistics"}})
    assert sm.site_sector_for("X") == "Infrastructure"  # CONCOR/DELHIVERY precedent


def test_ambiguous_or_unknown_labels_stay_blank_never_guessed(sources):
    sources({
        "A": {"source": "NSE", "industry": "Services"},
        "B": {"source": "Yahoo Finance", "industry": "Packaging & Containers"},
        "C": {"source": "Yahoo Finance", "industry": "Some Brand New Industry"},
    })
    assert sm.site_sector_for("A") is None
    assert sm.site_sector_for("B") is None
    assert sm.site_sector_for("C") is None
    assert sm.site_sector_for("NOSUCHSYMBOL") is None


def test_every_mapped_value_is_an_existing_site_sector():
    site_sectors = {c["sector"] for c in _NSE_UNIVERSE}
    mapped = {v for v in (*sm._NSE_INDUSTRY.values(), *sm._YAHOO_INDUSTRY.values()) if v}
    assert mapped <= site_sectors, mapped - site_sectors


def test_real_collected_labels_all_have_an_explicit_decision():
    """Every label actually present in the committed data file must be an
    explicit key (mapped or deliberately None) — a new label the backfill
    picks up can't silently fall through unreviewed."""
    missing = set()
    for entry in sm._sources().values():
        table = sm._NSE_INDUSTRY if entry.get("source") == "NSE" else sm._YAHOO_INDUSTRY
        if entry.get("industry") not in table:
            missing.add((entry.get("source"), entry.get("industry")))
    assert not missing, sorted(missing)
