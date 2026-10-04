from datetime import date

import pandas as pd

from app.services.stock_extras import dividends_block, earnings_block, growth_valuation_rows


def test_growth_rows_skip_missing_and_format():
    rows = growth_valuation_rows({"revenueGrowth": 0.052, "enterpriseToEbitda": 18.456, "payoutRatio": None, "ebitda": 5e11, "totalDebt": 1e11, "financialCurrency": "INR"})
    assert rows == [{"label": "Revenue growth (latest quarter, YoY)", "value": "5.2%"}, {"label": "EV / EBITDA", "value": "18.46"}]


def test_earnings_block_next_and_history():
    idx = pd.to_datetime(["2026-10-09", "2026-07-10", "2026-04-09"])
    df = pd.DataFrame({"EPS Estimate": [34.0, 33.0, 32.0], "Reported EPS": [None, 33.5, 31.0], "Surprise(%)": [None, 1.5, -3.1]}, index=idx)
    out = earnings_block(df, "₹", today=date(2026, 10, 4))
    assert out["next_date"] == "2026-10-09" and out["next_eps_estimate"] == "₹34.00"
    assert [h["date"] for h in out["history"]] == ["2026-07-10", "2026-04-09"]
    assert out["history"][0]["surprise_pct"] == "+1.5%" and out["history"][1]["surprise_pct"] == "-3.1%"


def test_earnings_block_empty_and_unknown_currency():
    assert earnings_block(None, "₹")["history"] == []
    idx = pd.to_datetime(["2026-07-10"])
    df = pd.DataFrame({"EPS Estimate": [33.0], "Reported EPS": [33.5], "Surprise(%)": [1.5]}, index=idx)
    assert earnings_block(df, None)["history"][0]["estimate"] is None   # currency unconfirmed: no figure rather than a guessed symbol


def test_dividends_yield_scale_and_history():
    s = pd.Series([10.0, 27.0], index=pd.to_datetime(["2025-06-01", "2026-06-01"]))
    d = dividends_block(s, {"dividendYield": 1.23, "dividendRate": 27.0}, "₹")
    assert d["yield"] == "1.23%" and d["rate"] == "₹27.00" and d["history"][0] == {"date": "2026-06-01", "amount": "₹27.00"}
    assert dividends_block(s, {"dividendYield": 0.16, "dividendRate": 0.65, "currentPrice": 418.35}, "₹")["yield"] == "0.16%"   # Kotak: percent, not 16%


def test_dividend_yield_pct():
    from app.services.market_data import _dividend_yield_pct
    assert round(_dividend_yield_pct({"dividendRate": 65.0, "currentPrice": 2075.0}), 2) == 3.13
    assert _dividend_yield_pct({"dividendYield": 0.16}) == 0.16      # no rate: Yahoo's value is already a percent
    assert _dividend_yield_pct({"dividendYield": 0}) is None and _dividend_yield_pct({}) is None


def test_debt_to_equity_is_shown_as_a_multiple():
    from app.services.market_data import _debt_to_equity_str
    assert _debt_to_equity_str(10.2, 0.11) == "0.11"      # statement ratio wins (same unit as the Financials tab)
    assert _debt_to_equity_str(10.2, None) == "0.10"      # Yahoo's value is a percentage
    assert _debt_to_equity_str(None, None) == "—"
