"""Chart rows for the price chart: OHLCV for candles, close kept as `value` for the line chart; periods the page sends must exist; empty answers are not cached."""
import math

import pandas as pd
import pytest

from app.services import market_data as md


def _frame(index, rows, multiindex=True):
    df = pd.DataFrame(rows, index=index, columns=["Open", "High", "Low", "Close", "Volume"])
    if multiindex:
        df.columns = pd.MultiIndex.from_product([df.columns, ["TCS.NS"]])   # yf.download returns (field, ticker) columns for a single ticker
    return df


def test_daily_rows_carry_ohlcv_iso_time_and_the_legacy_label_and_value():
    idx = pd.to_datetime(["2026-09-29", "2026-09-30"])
    rows = md._chart_rows(_frame(idx, [[100, 105, 98, 103, 1000], [103, 104, 99, 100, 2000]]), "1d")
    assert rows[0] == {"label": "Sep 29", "value": 103.0, "time": "2026-09-29", "open": 100.0, "high": 105.0, "low": 98.0, "close": 103.0, "volume": 1000}
    assert rows[1]["close"] == rows[1]["value"] == 100.0 and rows[1]["time"] == "2026-09-30"


def test_intraday_rows_use_epoch_seconds_for_time_and_clock_labels():
    idx = pd.DatetimeIndex(["2026-09-30 09:15", "2026-09-30 09:20"], tz="Asia/Kolkata")
    rows = md._chart_rows(_frame(idx, [[10, 11, 9, 10.5, 5], [10.5, 12, 10, 11, 7]]), "5m")
    assert rows[0]["label"] == "09:15" and isinstance(rows[0]["time"], int) and rows[1]["time"] - rows[0]["time"] == 300


def test_a_bar_with_a_non_finite_price_is_skipped_and_high_low_always_contain_open_and_close():
    idx = pd.to_datetime(["2026-09-29", "2026-09-30", "2026-10-01"])
    df = _frame(idx, [[100, 105, 98, 103, 1], [float("nan"), 104, 99, 100, 1], [100, 99, 101, 102, math.nan]], multiindex=False)
    rows = md._chart_rows(df, "1d")
    assert [r["time"] for r in rows] == ["2026-09-29", "2026-10-01"]
    last = rows[-1]
    assert last["high"] >= max(last["open"], last["close"]) and last["low"] <= min(last["open"], last["close"]) and last["volume"] == 0


def test_every_period_the_company_page_sends_is_mapped_and_long_ranges_are_daily():
    for p in ("1D", "5D", "1M", "3M", "6M", "1Y", "5Y", "Max"):
        assert p in md._PERIOD_MAP, p
    assert md._PERIOD_MAP["3M"][1] == "1d" and md._PERIOD_MAP["6M"][1] == "1d" and md._PERIOD_MAP["1Y"][1] == "1d" and md._PERIOD_MAP["5D"][1] == "60m"


async def test_chart_is_cached_but_an_empty_answer_never_is(monkeypatch):
    md._CHART_CACHE.clear()
    calls = {"n": 0}
    idx = pd.to_datetime(["2026-09-29"])

    def fake_download(*a, **k):
        calls["n"] += 1
        return _frame(idx, [[1, 2, 0.5, 1.5, 10]]) if calls["n"] != 1 else pd.DataFrame()

    monkeypatch.setattr(md.yf, "download", fake_download)
    assert await md.get_stock_chart("TCS", "6M") == []            # transient empty answer
    first = await md.get_stock_chart("TCS", "6M")                  # not cached: fetched again
    again = await md.get_stock_chart("TCS", "6M")                  # cached now
    assert first and again == first and calls["n"] == 2
    md._CHART_CACHE.clear()
