"""
Financial Strength pillar — Non-Banking Commercial & Industrial V1 (NS1,
owner instruction 2026-09-27). A SEPARATE metric set from Banking's — no
NPA, no CET1, no bank-regulatory ratio, per explicit instruction. Six real
metrics, all derived from the company's own real, dated financial
statements (yfinance `.financials`/`.balance_sheet`) rather than
`.info`'s pre-computed fields, per the real NS1 data-inventory finding
that `.info.get("returnOnEquity")` is frequently absent and
`.info.get("debtToEquity")` is inconsistently scaled across real
companies (see scripts/ns1_nonbank_data_inventory.py's own output) —
self-computing from the underlying statement line items (Net Income,
Stockholders Equity, EBIT, Total Debt, Total Assets, Current Liabilities)
is both more reliable AND still a real, sourced number, never an
estimate.

    revenue_growth_pct   Total Revenue, YoY (most recent 2 real periods)
    profit_growth_pct    Net Income, YoY (most recent 2 real periods)
    roe                  Net Income / Stockholders Equity (latest period)
    roce                 EBIT / (Total Assets - Current Liabilities) (latest period)
    debt_to_equity       Total Debt / Stockholders Equity (latest period)
    interest_coverage    EBIT / Interest Expense (latest period) — omitted
                         (never fabricated as infinite) when Interest
                         Expense is zero, negative, or absent.

A metric missing for this symbol reduces coverage; it is never estimated,
interpolated, or substituted from a peer.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from app.services.marketripple_score.contracts import PillarScore, PillarStatus
from app.services.marketripple_score.sector_universe import sector_peer_universe
from app.services.marketripple_score.valuation import _percentile_rank

# (metric_code, higher_is_better)
_INDUSTRIAL_METRICS: list[tuple[str, bool]] = [
    ("revenue_growth_pct", True),
    ("profit_growth_pct", True),
    ("roe", True),
    ("roce", True),
    ("debt_to_equity", False),  # lower leverage relative to equity is better
    ("interest_coverage", True),
]
REAL_INDUSTRIAL_METRICS_TOTAL = len(_INDUSTRIAL_METRICS)

FORMULA_VERSION = "financial_strength_industrial_v1"


def _is_real(v) -> bool:
    try:
        return v is not None and v == v and abs(float(v)) != float("inf")
    except (TypeError, ValueError):
        return False


def _fetch_industrial_inputs_sync(symbol: str) -> dict:
    """Real, self-computed metrics for one symbol from its own real
    financials/balance_sheet — never from `.info`'s pre-computed (and, per
    the real NS1 inventory, unreliable/inconsistently-scaled) fields.
    Returns a dict of metric_code -> (value, period_label, statement_date)
    or metric_code -> None when that metric's real inputs aren't present
    for this company."""
    import yfinance as yf

    out: dict[str, tuple[float, str, str] | None] = {code: None for code, _ in _INDUSTRIAL_METRICS}
    t = yf.Ticker(f"{symbol.upper()}.NS")

    try:
        fin = t.financials
    except Exception:
        fin = None
    try:
        bs = t.balance_sheet
    except Exception:
        bs = None

    def _period_label(col) -> str:
        dt = col.to_pydatetime() if hasattr(col, "to_pydatetime") else None
        return dt.strftime("%Y-%m-%d") if dt else "unknown"

    def _statement_date(col) -> str | None:
        dt = col.to_pydatetime() if hasattr(col, "to_pydatetime") else None
        return dt.replace(tzinfo=timezone.utc).isoformat() if dt else None

    fin_has = fin is not None and not fin.empty
    bs_has = bs is not None and not bs.empty

    if fin_has and "Total Revenue" in fin.index and len(fin.columns) >= 2:
        cur, prev = fin.loc["Total Revenue"].iloc[0], fin.loc["Total Revenue"].iloc[1]
        if _is_real(cur) and _is_real(prev) and float(prev) != 0:
            growth = round(float(cur - prev) / abs(float(prev)) * 100, 1)
            out["revenue_growth_pct"] = (growth, f"{_period_label(fin.columns[1])} -> {_period_label(fin.columns[0])}", _statement_date(fin.columns[0]))

    if fin_has and "Net Income" in fin.index and len(fin.columns) >= 2:
        cur, prev = fin.loc["Net Income"].iloc[0], fin.loc["Net Income"].iloc[1]
        if _is_real(cur) and _is_real(prev) and float(prev) != 0:
            growth = round(float(cur - prev) / abs(float(prev)) * 100, 1)
            out["profit_growth_pct"] = (growth, f"{_period_label(fin.columns[1])} -> {_period_label(fin.columns[0])}", _statement_date(fin.columns[0]))

    net_income_latest = None
    if fin_has and "Net Income" in fin.index and len(fin.columns) >= 1:
        v = fin.loc["Net Income"].iloc[0]
        net_income_latest = float(v) if _is_real(v) else None

    equity_latest = None
    if bs_has and "Stockholders Equity" in bs.index and len(bs.columns) >= 1:
        v = bs.loc["Stockholders Equity"].iloc[0]
        equity_latest = float(v) if _is_real(v) else None

    if net_income_latest is not None and equity_latest is not None and equity_latest > 0:
        out["roe"] = (round(net_income_latest / equity_latest * 100, 2), _period_label(bs.columns[0]), _statement_date(bs.columns[0]))

    ebit_latest = None
    if fin_has and "EBIT" in fin.index and len(fin.columns) >= 1:
        v = fin.loc["EBIT"].iloc[0]
        ebit_latest = float(v) if _is_real(v) else None

    total_assets_latest = None
    if bs_has and "Total Assets" in bs.index and len(bs.columns) >= 1:
        v = bs.loc["Total Assets"].iloc[0]
        total_assets_latest = float(v) if _is_real(v) else None

    current_liab_latest = None
    if bs_has and "Current Liabilities" in bs.index and len(bs.columns) >= 1:
        v = bs.loc["Current Liabilities"].iloc[0]
        current_liab_latest = float(v) if _is_real(v) else None

    if ebit_latest is not None and total_assets_latest is not None and current_liab_latest is not None:
        capital_employed = total_assets_latest - current_liab_latest
        if capital_employed > 0:
            out["roce"] = (round(ebit_latest / capital_employed * 100, 2), _period_label(bs.columns[0]), _statement_date(bs.columns[0]))

    total_debt_latest = None
    if bs_has and "Total Debt" in bs.index and len(bs.columns) >= 1:
        v = bs.loc["Total Debt"].iloc[0]
        total_debt_latest = float(v) if _is_real(v) else None

    if total_debt_latest is not None and equity_latest is not None and equity_latest > 0:
        out["debt_to_equity"] = (round(total_debt_latest / equity_latest, 3), _period_label(bs.columns[0]), _statement_date(bs.columns[0]))

    interest_expense_latest = None
    if fin_has and "Interest Expense" in fin.index and len(fin.columns) >= 1:
        v = fin.loc["Interest Expense"].iloc[0]
        interest_expense_latest = abs(float(v)) if _is_real(v) else None  # yfinance sometimes reports this as a negative expense

    if ebit_latest is not None and interest_expense_latest is not None and interest_expense_latest > 0:
        out["interest_coverage"] = (round(ebit_latest / interest_expense_latest, 2), _period_label(fin.columns[0]), _statement_date(fin.columns[0]))

    return out


async def score_financial_strength_industrial(symbol: str, sector: str, peer_group: list[str] | None = None) -> PillarScore:
    """The Non-Banking Commercial & Industrial V1 Financial Strength
    pillar — a real, separate metric set and formula from Banking's own
    score_financial_strength(), never mixed with it. `peer_group`
    override exists for the same reason financial_strength.py's own
    parameter does — default is the real, live sector_peer_universe(sector),
    never a caller-varied population for the same company."""
    loop = asyncio.get_event_loop()
    symbol = symbol.upper()
    retrieved_at = datetime.now(timezone.utc).isoformat()

    active_peer_group = peer_group if peer_group is not None else sector_peer_universe(sector)
    peer_symbols = list(dict.fromkeys([symbol] + [s for s in active_peer_group if s != symbol]))

    fetched = []
    for s in peer_symbols:
        fetched.append(await loop.run_in_executor(None, _fetch_industrial_inputs_sync, s))
        await asyncio.sleep(0.4)
    by_symbol = dict(zip(peer_symbols, fetched))
    own = by_symbol[symbol]

    metrics_used, metrics_missing = [], []
    sub_scores: dict[str, float] = {}
    metric_provenance: dict[str, dict] = {}
    detail: dict = {"peer_group": peer_symbols, "sector": sector}

    for code, higher_is_better in _INDUSTRIAL_METRICS:
        values = {s: by_symbol[s][code][0] for s in peer_symbols if by_symbol[s].get(code) is not None}
        pctile = _percentile_rank(values, symbol, cheaper_is_better=not higher_is_better)
        if pctile is not None:
            sub_scores[code] = pctile
            metrics_used.append(f"{code}_peer_percentile (real, statement-derived)")
            own_rec = own.get(code)
            detail[code] = own_rec[0] if own_rec else None
            metric_provenance[code] = {
                "value": own_rec[0] if own_rec else None,
                "source": "yfinance_financials_balance_sheet",
                "period": own_rec[1] if own_rec else None,
                "retrieved_at": retrieved_at,
                "observation_as_of": own_rec[2] if own_rec else None,
                "formula_version": FORMULA_VERSION,
            }
        else:
            metrics_missing.append(f"{code} (no real, peer-comparable observation for this symbol/sector yet)")

    detail["metrics"] = metric_provenance

    if not sub_scores:
        return PillarScore(
            name="financial_strength", score=None, coverage_pct=0.0, status=PillarStatus.INSUFFICIENT,
            metrics_used=metrics_used, metrics_missing=metrics_missing,
            sources=[f"yfinance financials/balance_sheet ({symbol}.NS + {len(peer_symbols)-1} real peers)"],
            detail=detail, methodology_version=FORMULA_VERSION,
        )

    score = round(sum(sub_scores.values()) / len(sub_scores), 1)
    coverage_pct = round(len(sub_scores) / REAL_INDUSTRIAL_METRICS_TOTAL * 100, 1)
    status = PillarStatus.COMPLETE if len(sub_scores) == REAL_INDUSTRIAL_METRICS_TOTAL else PillarStatus.PARTIAL

    return PillarScore(
        name="financial_strength", score=score, coverage_pct=coverage_pct, status=status,
        metrics_used=metrics_used, metrics_missing=metrics_missing,
        sources=[f"yfinance financials/balance_sheet ({symbol}.NS + {len(peer_symbols)-1} real peers: {', '.join(s for s in peer_symbols if s != symbol)})"],
        detail=detail, methodology_version=FORMULA_VERSION,
    )
