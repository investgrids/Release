"""EDGAR/ECB ingestion wiring — flag gating, failure isolation, flag defaults,
and source-registry rows. Mocked; no live calls, no DB."""
from __future__ import annotations

import pytest

import app.tasks.ingest_tasks as ingest
from app.core.config import Settings, settings
from app.services.warehouse.source_registry_seed import _ROWS


# ── Flag defaults ─────────────────────────────────────────────────────────────

def test_flags_default_off():
    s = Settings()
    assert s.edgar_ingestion_enabled is False
    assert s.ecb_ingestion_enabled is False


# ── _fetch_edgar_items gating / isolation ─────────────────────────────────────

class _BoomInit:
    def __init__(self):
        raise AssertionError("provider constructed while flag OFF — no network expected")


class _Ok:
    def __init__(self):
        pass

    async def fetch_and_normalize(self):
        return ["SENTINEL"]


class _Fail:
    def __init__(self):
        pass

    async def fetch_and_normalize(self):
        raise RuntimeError("boom")


async def test_edgar_off_makes_no_provider(monkeypatch):
    monkeypatch.setattr(settings, "edgar_ingestion_enabled", False)
    monkeypatch.setattr(ingest, "EdgarProvider", _BoomInit)   # would raise if constructed
    assert await ingest._fetch_edgar_items() == []


async def test_edgar_on_calls_provider(monkeypatch):
    monkeypatch.setattr(settings, "edgar_ingestion_enabled", True)
    monkeypatch.setattr(ingest, "EdgarProvider", _Ok)
    assert await ingest._fetch_edgar_items() == ["SENTINEL"]


async def test_edgar_failure_isolated(monkeypatch):
    monkeypatch.setattr(settings, "edgar_ingestion_enabled", True)
    monkeypatch.setattr(ingest, "EdgarProvider", _Fail)
    assert await ingest._fetch_edgar_items() == []   # failure -> [], never raised


async def test_ecb_off_makes_no_provider(monkeypatch):
    monkeypatch.setattr(settings, "ecb_ingestion_enabled", False)
    monkeypatch.setattr(ingest, "EcbProvider", _BoomInit)
    assert await ingest._fetch_ecb_items() == []


async def test_ecb_on_calls_provider(monkeypatch):
    monkeypatch.setattr(settings, "ecb_ingestion_enabled", True)
    monkeypatch.setattr(ingest, "EcbProvider", _Ok)
    assert await ingest._fetch_ecb_items() == ["SENTINEL"]


async def test_ecb_failure_isolated(monkeypatch):
    monkeypatch.setattr(settings, "ecb_ingestion_enabled", True)
    monkeypatch.setattr(ingest, "EcbProvider", _Fail)
    assert await ingest._fetch_ecb_items() == []


# ── Independent flags ─────────────────────────────────────────────────────────

async def test_flags_are_independent(monkeypatch):
    monkeypatch.setattr(settings, "edgar_ingestion_enabled", True)
    monkeypatch.setattr(settings, "ecb_ingestion_enabled", False)
    monkeypatch.setattr(ingest, "EdgarProvider", _Ok)
    monkeypatch.setattr(ingest, "EcbProvider", _BoomInit)   # must not be constructed
    assert await ingest._fetch_edgar_items() == ["SENTINEL"]
    assert await ingest._fetch_ecb_items() == []


# ── Source-registry rows ──────────────────────────────────────────────────────

def test_source_registry_rows_present():
    by_id = {row[0]: row for row in _ROWS}
    assert "sec_edgar_filings" in by_id
    assert "ecb_press_releases_intl" in by_id
    # (id, name, domain, type, method, freq, priority, rights_basis, robots_checked, notes)
    assert by_id["sec_edgar_filings"][7] == "public_domain"
    assert by_id["sec_edgar_filings"][8] is True        # robots/policy checked
    assert by_id["ecb_press_releases_intl"][7] == "official_rss"
