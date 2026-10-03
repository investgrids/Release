"""Shared fixtures: a financial statement date and market-input provenance that
pass the public data-quality gate (data_quality.py)."""
from __future__ import annotations

from datetime import date, timedelta

FRESH_AS_OF = (date.today() - timedelta(days=60)).isoformat()


def verified_inputs(symbol: str) -> dict:
    """Recorded completed-session inputs: dated closes stop at the cutoff and
    the symbol's own series reaches the market's last session."""
    end = (date.today() - timedelta(days=1)).isoformat()
    series = {f"{symbol.upper()}.NS": {"observation_end": end, "observation_count": 200},
              "^NSEI": {"observation_end": end, "observation_count": 64}}
    return {"version": 1, "cutoff_date": end, "series": series, "inputs": {}}
