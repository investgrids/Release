"""
Collect real, source-attributed industry labels for directory companies
that have no sector (the C4 Company Master extension -- NSE's EQ master
file carries no sector, see companies.py _get_qualified_master_entries).

Sources, in priority order:
  1. NSE's own index constituent files (niftyindices.com
     ind_niftytotalmarket_list / ind_nifty500list / ind_niftymicrocap250_list),
     "Industry" column -- the exchange's official classification.
  2. Yahoo Finance quote profile (sector + industry) for everything else.

Writes RAW source labels only, never a guessed site sector:
app/data/company_industry_sources.json. Translating those labels into the
site's own sector names happens in
app/services/company_identity/sector_mapping.py, where the mapping table
is reviewable and tested. Resumable: symbols already present are skipped.
BSE's scrip list (which would cover more) is blocked by its WAF and is
deliberately not attempted.

Usage: python scripts/backfill_company_industries.py
"""
from __future__ import annotations

import asyncio
import csv
import io
import json
import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, ".")

import requests

OUT = Path("app/data/company_industry_sources.json")
NSE_FILES = ["ind_niftytotalmarket_list", "ind_nifty500list", "ind_niftymicrocap250_list"]
YAHOO_PAUSE_S = 1.5


def _load() -> dict:
    return json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}


def _save(data: dict) -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(dict(sorted(data.items())), indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def _nse_industries() -> dict[str, str]:
    out: dict[str, str] = {}
    for name in NSE_FILES:
        r = requests.get(f"https://niftyindices.com/IndexConstituent/{name}.csv",
                         headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
        r.raise_for_status()
        for row in csv.DictReader(io.StringIO(r.content.decode("utf-8-sig"))):
            sym, ind = row.get("Symbol", "").strip(), row.get("Industry", "").strip()
            if sym and ind:
                out.setdefault(sym, ind)
    return out


async def _blank_sector_symbols() -> list[str]:
    from app.api.companies import get_full_company_directory
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        directory = await get_full_company_directory(db)
    return [r["symbol"] for r in directory if not r["sector"]]


def main() -> None:
    import yfinance as yf

    today = date.today().isoformat()
    data = _load()
    todo = [s for s in asyncio.run(_blank_sector_symbols()) if s not in data]
    print(f"{len(todo)} symbols need a source label ({len(data)} already collected)")

    nse = _nse_industries()
    for sym in todo:
        if sym in nse:
            data[sym] = {"source": "NSE", "industry": nse[sym], "fetched": today}
    _save(data)
    remaining = [s for s in todo if s not in data]
    print(f"NSE covered {len(todo) - len(remaining)}; querying Yahoo for {len(remaining)}")

    backoff = 30
    i = 0
    while i < len(remaining):
        sym = remaining[i]
        try:
            info = yf.Ticker(f"{sym}.NS").info or {}
        except Exception as e:
            if "Rate" in type(e).__name__ or "Too Many" in str(e):
                print(f"  rate limited at {sym}; sleeping {backoff}s", flush=True)
                time.sleep(backoff)
                backoff = min(backoff * 2, 600)
                continue
            info = {}
        backoff = 30
        sector, industry = info.get("sector"), info.get("industry")
        if sector or industry:
            data[sym] = {"source": "Yahoo Finance", "sector": sector, "industry": industry, "fetched": today}
        print(f"[{i + 1}/{len(remaining)}] {sym}: {sector!r} / {industry!r}", flush=True)
        if (i + 1) % 25 == 0:
            _save(data)
        i += 1
        time.sleep(YAHOO_PAUSE_S)
    _save(data)
    print(f"done — {len(data)} symbols with a real source label")


if __name__ == "__main__":
    main()
