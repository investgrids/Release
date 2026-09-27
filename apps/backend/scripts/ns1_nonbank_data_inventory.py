"""
NS1 — real data inventory for non-banking MarketRipple Score cohort
selection. Samples real, live yfinance data for a handful of companies
across candidate sectors to measure (not assume) what's actually
available: currency, multi-period revenue/net income (for growth calcs),
balance-sheet debt/equity, ROE, EBIT/interest expense (for interest
coverage), and real daily price depth (market_behaviour pillar). No
writes, no fixtures — every number printed is a real live fetch.
"""
from __future__ import annotations

import sys
sys.path.insert(0, ".")

import time
import yfinance as yf

CANDIDATES = {
    "Technology":       ["TCS", "INFY", "WIPRO"],
    "FMCG":             ["HINDUNILVR", "ITC", "NESTLEIND"],
    "Automotive":       ["MARUTI", "TATAMOTORS", "M&M"],
    "Pharmaceuticals":  ["SUNPHARMA", "DRREDDY", "CIPLA"],
    "Chemicals":        ["PIDILITIND", "SRF", "UPL"],
    "Consumer":         ["TITAN", "ASIANPAINT", "DABUR"],
    "Metals":           ["TATASTEEL", "HINDALCO", "JSWSTEEL"],
    "Infrastructure":   ["LT", "ADANIPORTS", "GMRINFRA"],
    "Finance":          ["BAJFINANCE", "SBILIFE", "HDFCAMC"],
}


def inspect(symbol: str) -> dict:
    t = yf.Ticker(f"{symbol}.NS")
    out = {"symbol": symbol}
    try:
        info = t.info or {}
    except Exception as e:
        info = {}
        out["info_error"] = str(e)
    out["currency"] = info.get("financialCurrency")
    out["roe"] = info.get("returnOnEquity")
    out["debt_to_equity_info"] = info.get("debtToEquity")

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
    for sector, symbols in CANDIDATES.items():
        print(f"\n=== {sector} ===")
        for s in symbols:
            r = inspect(s)
            print(f"  {s}: currency={r['currency']} roe={r['roe']} d/e_info={r['debt_to_equity_info']} "
                  f"fin_periods={r['financials_periods']} revenue={r['has_total_revenue']} "
                  f"net_income={r['has_net_income']} ebit={r['has_ebit']} int_exp={r['has_interest_expense']} "
                  f"bs_periods={r['balance_sheet_periods']} total_debt={r['has_total_debt']} "
                  f"equity={r['has_stockholders_equity']} total_assets={r['has_total_assets']} "
                  f"curr_liab={r['has_current_liabilities']} daily_rows_1y={r['daily_rows_1y']}")
            time.sleep(0.6)


if __name__ == "__main__":
    main()
