"""
app/api/sectors.py's _norm() (2026-08 fix) — the fuzzy substring match
(`key in s`) matched garbage sector slugs to a real sector whenever the
input merely contained a short key as a substring: "it" is a substring of
"definitely", "credit", "digital", etc., so /api/sectors/{garbage}/
intelligence resolved to the real IT sector and returned HTTP 200 with
real data instead of 404 — a duplicate-content generator of exactly the
kind flagged in Google Search Console for other routes in the same
investigation (see the notFound()/loading.tsx fix in apps/web).
"""
from __future__ import annotations

from app.api.sectors import _norm, _SECTOR_STOCKS


def test_garbage_slugs_that_merely_contain_a_short_key_do_not_match():
    for garbage in ["definitely-fake-sector", "credit-analysis-xyz", "digital-garbage"]:
        assert _norm(garbage) not in _SECTOR_STOCKS


def test_exact_short_key_still_matches():
    assert _norm("it") in _SECTOR_STOCKS
    assert _norm("IT") in _SECTOR_STOCKS


def test_legitimate_fuzzy_variants_still_match():
    assert _norm("automotive") == "auto"
    assert _norm("infra") == "infrastructure"
    assert _norm("metal") == "metals"
