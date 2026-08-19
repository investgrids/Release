"""
Sector Setup + Companies In Focus (2026-08 Pre-Market rebuild, Part A4).

Companies In Focus must come SOLELY from Development.companies (the
canonical source per the plan's explicit refinement — graph company
coverage is too sparse to trust). Sector Setup must render honest
momentum labels regardless of graph enrichment, and any graph tag must be
qualitative (Direct/Secondary impact), never a raw accumulated_weight
decimal.
"""
from __future__ import annotations

import pytest

from app.services.impact_zone_service import build_companies_in_focus, build_sector_setup


def _dev(title, *, direction="negative", sectors=None, companies=None):
    return {"title": title, "direction": direction, "sectors": sectors or [], "companies": companies or []}


@pytest.mark.asyncio
async def test_sector_setup_uses_honest_momentum_labels_no_graph():
    themes = [
        {"theme": "Metals", "momentum": "rising", "score": 62.0},
        {"theme": "Banking", "momentum": "falling", "score": 40.0},
        {"theme": "FMCG", "momentum": "stable", "score": 50.0},
    ]

    rows = await build_sector_setup(themes, [])

    by_sector = {r["sector"]: r for r in rows}
    assert by_sector["Metals"]["label"] == "Strong momentum"
    assert by_sector["Banking"]["label"] == "Weak momentum"
    assert by_sector["FMCG"]["label"] == "Neutral momentum"
    # No forward-looking claim like "Expected Outperform" anywhere.
    for r in rows:
        assert "Outperform" not in r["label"]
        assert "Likely" not in r["label"]


@pytest.mark.asyncio
async def test_sector_setup_graph_tag_is_qualitative_not_numeric(monkeypatch):
    themes = [{"theme": "Banking", "momentum": "falling", "score": 40.0}]
    developments = [_dev("RBI liquidity action", direction="negative", sectors=["Banking"])]

    async def fake_ripple_from_node(node_id, change="rise"):
        return {
            "impacts": [
                {"node": {"type": "sector", "label": "Banking"}, "depth": 1, "accumulated_weight": 0.83},
            ]
        }

    monkeypatch.setattr(
        "app.services.intelligence_graph_service.ripple_from_node", fake_ripple_from_node
    )
    monkeypatch.setattr(
        "app.services.intelligence_graph_service.make_node_id", lambda t, s: f"{t}:{s.lower()}"
    )

    rows = await build_sector_setup(themes, developments)
    banking = next(r for r in rows if r["sector"] == "Banking")
    assert banking["impact_tag"] == "Direct impact"
    assert isinstance(banking["impact_tag"], str)
    assert banking["impact_source"] == "RBI liquidity action"
    # The raw 0.83 accumulated_weight must never leak into the row as a
    # rendered value — only the theme's own (unrelated) momentum score
    # is a float here.
    assert 0.83 not in banking.values()
    assert "accumulated_weight" not in banking


@pytest.mark.asyncio
async def test_sector_setup_survives_graph_failure():
    themes = [{"theme": "Banking", "momentum": "falling", "score": 40.0}]
    developments = [_dev("RBI liquidity action", sectors=["Banking"])]
    # No monkeypatch — real intelligence_graph_service import/call happens;
    # this proves a real (or failing) graph call never breaks sector_setup
    # itself, since the honest label is independent of graph enrichment.
    rows = await build_sector_setup(themes, developments)
    assert rows[0]["sector"] == "Banking"
    assert rows[0]["label"] == "Weak momentum"


def test_companies_in_focus_sourced_only_from_development_companies():
    developments = [
        _dev("RBI liquidity action", direction="negative", companies=["HDFCBANK", "ICICIBANK"]),
        _dev("Crude retreats", direction="positive", companies=["IOC"]),
    ]
    rows = build_companies_in_focus(developments)
    assert rows == [
        {"symbol": "HDFCBANK", "reason": "RBI liquidity action", "direction": "negative"},
        {"symbol": "ICICIBANK", "reason": "RBI liquidity action", "direction": "negative"},
        {"symbol": "IOC", "reason": "Crude retreats", "direction": "positive"},
    ]


def test_companies_in_focus_dedupes_by_symbol_keeping_first():
    developments = [
        _dev("Higher-importance development", direction="negative", companies=["HDFCBANK"]),
        _dev("Lower-importance development mentioning same company", direction="positive", companies=["HDFCBANK"]),
    ]
    rows = build_companies_in_focus(developments)
    assert len(rows) == 1
    assert rows[0]["reason"] == "Higher-importance development"
    assert rows[0]["direction"] == "negative"


def test_companies_in_focus_respects_limit():
    developments = [_dev(f"Development {i}", companies=[f"SYM{i}"]) for i in range(20)]
    rows = build_companies_in_focus(developments, limit=3)
    assert len(rows) == 3


def test_companies_in_focus_empty_when_no_developments():
    assert build_companies_in_focus([]) == []
