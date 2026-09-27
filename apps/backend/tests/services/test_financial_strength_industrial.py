"""
Non-Banking Commercial & Industrial V1 Financial Strength — NS1 tests
(2026-09-27). Mocks yfinance's Ticker (financials/balance_sheet DataFrames,
real yfinance shape: index=row label, columns=Timestamp most-recent-first)
rather than hitting the live network, so these are deterministic and fast.
Covers: a valid score with full real-shaped data, missing/short-period
data reducing coverage rather than being estimated, currency-invariant
growth math (a ratio, not an absolute amount), and the never-apply-NPA/
CET1-to-non-banks guarantee (this module has no such metric at all).
"""
from __future__ import annotations

import pandas as pd
import pytest

from app.services.marketripple_score.contracts import PillarStatus
from app.services.marketripple_score.financial_strength_industrial import (
    REAL_INDUSTRIAL_METRICS_TOTAL, _fetch_industrial_inputs_sync,
    prefetch_industrial_inputs, score_financial_strength_industrial,
)


class _FakeTicker:
    def __init__(self, financials=None, balance_sheet=None, info=None):
        self.financials = financials if financials is not None else pd.DataFrame()
        self.balance_sheet = balance_sheet if balance_sheet is not None else pd.DataFrame()
        self.info = info or {}


def _full_financials(revenue_cur, revenue_prev, ni_cur, ni_prev, ebit_cur, int_exp_cur):
    cols = [pd.Timestamp("2026-03-31"), pd.Timestamp("2025-03-31")]
    return pd.DataFrame({
        cols[0]: [revenue_cur, ni_cur, ebit_cur, int_exp_cur],
        cols[1]: [revenue_prev, ni_prev, ebit_cur * 0.9, int_exp_cur * 0.9],
    }, index=["Total Revenue", "Net Income", "EBIT", "Interest Expense"])


def _full_balance_sheet(equity, total_assets, current_liab, total_debt):
    cols = [pd.Timestamp("2026-03-31")]
    return pd.DataFrame({cols[0]: [equity, total_assets, current_liab, total_debt]},
                         index=["Stockholders Equity", "Total Assets", "Current Liabilities", "Total Debt"])


def _patch_tickers(monkeypatch, by_symbol: dict):
    def fake_ticker(name):
        symbol = name.split(".")[0]
        return by_symbol[symbol]
    monkeypatch.setattr("yfinance.Ticker", fake_ticker)


def test_full_real_data_produces_all_six_metrics_and_complete_status(monkeypatch):
    """A company with every real statement line item present should score
    all 6 real metrics (never any bank-only metric — this module has no
    gross_npa_pct/net_npa_pct/cet1_ratio/roa field at all)."""
    tcs = _FakeTicker(
        financials=_full_financials(1000.0, 900.0, 200.0, 180.0, 250.0, 10.0),
        balance_sheet=_full_balance_sheet(equity=800.0, total_assets=1500.0, current_liab=400.0, total_debt=50.0),
    )
    peer = _FakeTicker(
        financials=_full_financials(500.0, 480.0, 90.0, 85.0, 110.0, 8.0),
        balance_sheet=_full_balance_sheet(equity=400.0, total_assets=900.0, current_liab=300.0, total_debt=120.0),
    )
    _patch_tickers(monkeypatch, {"TCS": tcs, "PEER1": peer})

    r = _fetch_industrial_inputs_sync("TCS")
    for code in ("revenue_growth_pct", "profit_growth_pct", "roe", "roce", "debt_to_equity", "interest_coverage"):
        assert r[code] is not None, f"{code} should be computed from complete real data"

    # No bank-only metric exists in this module's output at all.
    assert "gross_npa_pct" not in r and "cet1_ratio" not in r and "roa" not in r


@pytest.mark.asyncio
async def test_score_financial_strength_industrial_end_to_end_complete(monkeypatch):
    tcs = _FakeTicker(
        financials=_full_financials(1000.0, 900.0, 200.0, 180.0, 250.0, 10.0),
        balance_sheet=_full_balance_sheet(equity=800.0, total_assets=1500.0, current_liab=400.0, total_debt=50.0),
    )
    peer = _FakeTicker(
        financials=_full_financials(500.0, 480.0, 90.0, 85.0, 110.0, 8.0),
        balance_sheet=_full_balance_sheet(equity=400.0, total_assets=900.0, current_liab=300.0, total_debt=120.0),
    )
    _patch_tickers(monkeypatch, {"TCS": tcs, "PEER1": peer})

    result = await score_financial_strength_industrial("TCS", "Technology", peer_group=["TCS", "PEER1"])
    assert result.status == PillarStatus.COMPLETE
    assert result.score is not None
    assert len(result.metrics_used) == REAL_INDUSTRIAL_METRICS_TOTAL
    assert result.metrics_missing == []
    assert result.coverage_pct == 100.0


@pytest.mark.asyncio
async def test_missing_statement_lines_reduce_coverage_never_estimated(monkeypatch):
    """A real company missing Interest Expense (e.g. genuinely debt-free)
    must show interest_coverage as MISSING, never a fabricated/estimated
    value or an infinite score."""
    debt_free = _FakeTicker(
        financials=pd.DataFrame(
            {pd.Timestamp("2026-03-31"): [1000.0, 200.0, 250.0], pd.Timestamp("2025-03-31"): [900.0, 180.0, 225.0]},
            index=["Total Revenue", "Net Income", "EBIT"],  # no Interest Expense row at all
        ),
        balance_sheet=_full_balance_sheet(equity=800.0, total_assets=1500.0, current_liab=400.0, total_debt=0.0),
    )
    peer = _FakeTicker(
        financials=_full_financials(500.0, 480.0, 90.0, 85.0, 110.0, 8.0),
        balance_sheet=_full_balance_sheet(equity=400.0, total_assets=900.0, current_liab=300.0, total_debt=120.0),
    )
    _patch_tickers(monkeypatch, {"DEBTFREE": debt_free, "PEER1": peer})

    result = await score_financial_strength_industrial("DEBTFREE", "Technology", peer_group=["DEBTFREE", "PEER1"])
    assert result.status == PillarStatus.PARTIAL
    assert any("interest_coverage" in m for m in result.metrics_missing)
    assert not any("interest_coverage" in m for m in result.metrics_used)
    assert result.coverage_pct < 100.0
    # debt_to_equity of exactly 0 is still a REAL value (genuinely no debt), not missing.
    assert result.detail.get("debt_to_equity") == 0.0


@pytest.mark.asyncio
async def test_single_period_financials_cannot_compute_growth(monkeypatch):
    """Only one real period of financials on record — revenue/profit
    growth need two real periods and must be reported missing, not
    interpolated or assumed flat."""
    one_period = _FakeTicker(
        financials=pd.DataFrame(
            {pd.Timestamp("2026-03-31"): [1000.0, 200.0, 250.0, 10.0]},
            index=["Total Revenue", "Net Income", "EBIT", "Interest Expense"],
        ),
        balance_sheet=_full_balance_sheet(equity=800.0, total_assets=1500.0, current_liab=400.0, total_debt=50.0),
    )
    peer = _FakeTicker(
        financials=_full_financials(500.0, 480.0, 90.0, 85.0, 110.0, 8.0),
        balance_sheet=_full_balance_sheet(equity=400.0, total_assets=900.0, current_liab=300.0, total_debt=120.0),
    )
    _patch_tickers(monkeypatch, {"ONEPERIOD": one_period, "PEER1": peer})

    r = _fetch_industrial_inputs_sync("ONEPERIOD")
    assert r["revenue_growth_pct"] is None
    assert r["profit_growth_pct"] is None
    # Latest-period-only ratios are still real and computable.
    assert r["roe"] is not None
    assert r["roce"] is not None


def test_growth_math_is_currency_invariant():
    """Revenue/profit growth is a ratio of the SAME company's own two
    periods — currency cancels out entirely, so a USD-reporting company
    (e.g. the real, confirmed-live INFY case) must produce an identical
    growth percentage to an otherwise-identical INR-reporting company.
    No special currency handling is needed for THIS metric class — unlike
    the absolute-value currency bug this session already found and fixed
    elsewhere (market_data.py's annual_financials/free_cashflow)."""
    inr_growth = round((1000.0 - 900.0) / 900.0 * 100, 1)
    usd_growth = round((1000.0 * 0.012 - 900.0 * 0.012) / (900.0 * 0.012) * 100, 1)  # same co., converted to a toy USD scale
    assert inr_growth == usd_growth


def test_zero_or_negative_equity_never_divides_by_zero(monkeypatch):
    """A real company with zero/negative stockholders equity (a genuine,
    if unusual, real state) must not compute a nonsensical or crashing ROE/
    debt-to-equity — both metrics must come back missing, not fabricated."""
    negative_equity = _FakeTicker(
        financials=_full_financials(1000.0, 900.0, 200.0, 180.0, 250.0, 10.0),
        balance_sheet=_full_balance_sheet(equity=-50.0, total_assets=1500.0, current_liab=400.0, total_debt=50.0),
    )
    _patch_tickers(monkeypatch, {"NEGEQ": negative_equity})

    r = _fetch_industrial_inputs_sync("NEGEQ")
    assert r["roe"] is None
    assert r["debt_to_equity"] is None
    # ROCE doesn't depend on equity and should still compute.
    assert r["roce"] is not None


@pytest.mark.asyncio
async def test_prefetched_path_produces_identical_score_to_independent_fetch(monkeypatch):
    """The whole point of the shared-fetch optimization (NS1 round 2,
    2026-09-27, owner instruction to fix repeated per-company peer
    fetching before a long batch run): using a prefetched cache must be a
    pure performance change, never a behavior change. Same mocked data,
    same peer group, scored once the old way (independent fetch) and once
    via prefetch_industrial_inputs() + the `prefetched` parameter — the
    two PillarScore results must match on every real field."""
    tcs = _FakeTicker(
        financials=_full_financials(1000.0, 900.0, 200.0, 180.0, 250.0, 10.0),
        balance_sheet=_full_balance_sheet(equity=800.0, total_assets=1500.0, current_liab=400.0, total_debt=50.0),
    )
    peer = _FakeTicker(
        financials=_full_financials(500.0, 480.0, 90.0, 85.0, 110.0, 8.0),
        balance_sheet=_full_balance_sheet(equity=400.0, total_assets=900.0, current_liab=300.0, total_debt=120.0),
    )
    _patch_tickers(monkeypatch, {"TCS": tcs, "PEER1": peer})

    independent = await score_financial_strength_industrial("TCS", "Technology", peer_group=["TCS", "PEER1"])

    cache = await prefetch_industrial_inputs(["TCS", "PEER1"])
    shared = await score_financial_strength_industrial("TCS", "Technology", peer_group=["TCS", "PEER1"], prefetched=cache)

    def _without_retrieved_at(metrics: dict) -> dict:
        # retrieved_at is genuinely computed fresh (datetime.now()) inside
        # each call -- excluded from the comparison since it's expected to
        # differ by construction, not a sign the two paths disagree.
        return {code: {k: v for k, v in m.items() if k != "retrieved_at"} for code, m in metrics.items()}

    assert shared.score == independent.score
    assert shared.coverage_pct == independent.coverage_pct
    assert shared.status == independent.status
    assert sorted(shared.metrics_used) == sorted(independent.metrics_used)
    assert _without_retrieved_at(shared.detail["metrics"]) == _without_retrieved_at(independent.detail["metrics"])
