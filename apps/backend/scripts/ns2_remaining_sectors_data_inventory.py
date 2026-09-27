"""
NS2 — real data inventory for the 12 sectors NOT measured in the original
NS1 pass (Infrastructure, Power, Energy, Real Estate, Telecom, Media,
Cement, Healthcare, Textiles, Electronics, Retail, Defence). Same method
as scripts/ns1_nonbank_data_inventory.py: samples real, live yfinance
financials/balance_sheet/price data for real symbols pulled directly from
_NSE_UNIVERSE (never hand-typed, to avoid the stale/delisted-symbol trap
NS1 itself hit) to determine which of these sectors have the standardized
commercial/industrial statement shape financial_strength_industrial.py
needs, before extending NONBANK_INDUSTRIAL_SECTORS to any of them.
"""
from __future__ import annotations

import sys
sys.path.insert(0, ".")

import time
import yfinance as yf

from app.api.companies import _NSE_UNIVERSE

SECTORS = [
    "Infrastructure", "Power", "Energy", "Real Estate", "Telecom", "Media",
    "Cement", "Healthcare", "Textiles", "Electronics", "Retail", "Defence",
]


def real_sample(sector: str, n: int = 3) -> list[str]:
    return [r["symbol"] for r in _NSE_UNIVERSE if r.get("sector") == sector][:n]


def inspect(symbol: str) -> dict:
    t = yf.Ticker(f"{symbol}.NS")
    out = {"symbol": symbol}
    try:
        info = t.info or {}
    except Exception:
        info = {}
    out["currency"] = info.get("financialCurrency")

    try:
        fin = t.financials
    except Exception:
        fin = None
    try:
        bs = t.balance_sheet
    except Exception:
        bs = None

    out["financials_periods"] = 0 if fin is None or fin.empty else len(fin.columns)
    out["has_total_revenue"] = bool(fin is not None and not fin.empty and "Total Revenue" in fin.index)
    out["has_net_income"] = bool(fin is not None and not fin.empty and "Net Income" in fin.index)
    out["has_ebit"] = bool(fin is not None and not fin.empty and "EBIT" in fin.index)
    out["has_interest_expense"] = bool(fin is not None and not fin.empty and "Interest Expense" in fin.index)

    out["balance_sheet_periods"] = 0 if bs is None or bs.empty else len(bs.columns)
    out["has_total_debt"] = bool(bs is not None and not bs.empty and "Total Debt" in bs.index)
    out["has_stockholders_equity"] = bool(bs is not None and not bs.empty and "Stockholders Equity" in bs.index)
    out["has_total_assets"] = bool(bs is not None and not bs.empty and "Total Assets" in bs.index)
    out["has_current_liabilities"] = bool(bs is not None and not bs.empty and "Current Liabilities" in bs.index)

    try:
        hist = yf.download(f"{symbol}.NS", period="1y", interval="1d", progress=False, auto_adjust=True, timeout=10)
        out["daily_rows_1y"] = 0 if hist is None else len(hist)
    except Exception:
        out["daily_rows_1y"] = 0

    return out


def main() -> None:
    for sector in SECTORS:
        symbols = real_sample(sector)
        print(f"\n=== {sector} (real sample: {symbols}) ===")
        for s in symbols:
            r = inspect(s)
            print(f"  {s}: currency={r['currency']} fin_periods={r['financials_periods']} "
                  f"revenue={r['has_total_revenue']} net_income={r['has_net_income']} "
                  f"ebit={r['has_ebit']} int_exp={r['has_interest_expense']} "
                  f"bs_periods={r['balance_sheet_periods']} total_debt={r['has_total_debt']} "
                  f"equity={r['has_stockholders_equity']} total_assets={r['has_total_assets']} "
                  f"curr_liab={r['has_current_liabilities']} daily_rows_1y={r['daily_rows_1y']}")
            time.sleep(0.6)


if __name__ == "__main__":
    main()
