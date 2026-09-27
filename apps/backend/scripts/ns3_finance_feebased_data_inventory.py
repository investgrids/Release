"""
NS3 — targeted real data inventory for the Finance-sector companies that
are fee-based market infrastructure/services businesses, not balance-
sheet-driven lenders/insurers (CDSL: Depositories, MCX: Commodity
Exchange, CRISIL: ratings, CAMS: Mutual Fund Services, ANGELONE: Broking).
These are structurally closer to a standard commercial services company
than an NBFC/insurer, so they're worth testing individually rather than
excluding the whole Finance sector label on the strength of the two NBFC/
insurer samples NS1 already took (BAJFINANCE, SBILIFE).
"""
from __future__ import annotations

import sys
sys.path.insert(0, ".")

import time
import yfinance as yf

CANDIDATES = ["CDSL", "MCX", "CRISIL", "CAMS", "ANGELONE"]


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
    for s in CANDIDATES:
        r = inspect(s)
        print(f"{s}: currency={r['currency']} fin_periods={r['financials_periods']} "
              f"revenue={r['has_total_revenue']} net_income={r['has_net_income']} "
              f"ebit={r['has_ebit']} int_exp={r['has_interest_expense']} "
              f"bs_periods={r['balance_sheet_periods']} total_debt={r['has_total_debt']} "
              f"equity={r['has_stockholders_equity']} total_assets={r['has_total_assets']} "
              f"curr_liab={r['has_current_liabilities']} daily_rows_1y={r['daily_rows_1y']}")
        time.sleep(0.6)


if __name__ == "__main__":
    main()
