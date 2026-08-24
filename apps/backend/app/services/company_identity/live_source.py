"""
Thin, deliberately untested network wrapper around the two real NSE
archive endpoints this Master is seeded from. Kept separate from
importer.py's parsing/upsert logic specifically so that logic can be
tested against fixed real fixture text without depending on NSE's own
uptime or a live network call in CI.
"""
from __future__ import annotations

import httpx

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Accept": "text/csv",
}

EQUITY_L_URL = "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"
SYMBOLCHANGE_URL = "https://nsearchives.nseindia.com/content/equities/symbolchange.csv"


async def fetch_nse_eq_csv(timeout: float = 20.0) -> str:
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.get(EQUITY_L_URL, headers=_HEADERS)
        resp.raise_for_status()
        return resp.text


async def fetch_nse_symbolchange_csv(timeout: float = 20.0) -> str:
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.get(SYMBOLCHANGE_URL, headers=_HEADERS)
        resp.raise_for_status()
        return resp.text
