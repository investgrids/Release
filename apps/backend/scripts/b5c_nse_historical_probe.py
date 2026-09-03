"""
B.5-C -- NSE historical-range feasibility probe. Owner-authorized
2026-08-30 evening, READ-ONLY against NSE's real public API.

Explicit constraints from the owner's authorization:
  - No writes to RawEvidence/EvidenceEntityLink/any DB table.
  - Small, single-day (or very small range) requests only per period.
  - No aggressive repeated requests, no parallel request storm, no
    attempt to bypass NSE protections.
  - Record: HTTP status, real filings returned, oldest/newest
    timestamps, response count, whether a count of exactly 50
    indicates OUR helper's truncation vs an NSE-side limit,
    pagination/offset metadata if present, response shape
    consistency, throttling behavior, cookie/header requirements for
    older queries.
  - Test one historically high-volume day specifically because a
    result of exactly 50 could hide truncation.
  - Do NOT work around the app's existing 50-item slice in this probe
    -- this script calls the raw endpoint directly (bypassing
    NSEProvider._get entirely) so the FULL, un-truncated real response
    is visible, which is required to tell the difference between "NSE
    returned <=50 items" and "we sliced a larger response down to 50."

This script is standalone -- it does NOT import app.db.session or any
model, so there is no way for it to touch the database even by
accident.
"""
from __future__ import annotations

import asyncio
import json
from datetime import date, timedelta

import httpx

_URL = "https://www.nseindia.com/api/corporate-announcements?index=equities"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://www.nseindia.com/",
}
_TODAY = date(2026, 8, 30)


async def probe_one(client: httpx.AsyncClient, label: str, from_date: date, to_date: date) -> dict:
    params = {"from_date": from_date.isoformat(), "to_date": to_date.isoformat()}
    result: dict = {"label": label, "from_date": from_date.isoformat(), "to_date": to_date.isoformat(), "params": params}
    try:
        r = await client.get(_URL, params=params)
        result["http_status"] = r.status_code
        result["response_headers_of_interest"] = {
            k: v for k, v in r.headers.items()
            if k.lower() in ("content-type", "x-ratelimit-limit", "x-ratelimit-remaining", "retry-after", "set-cookie")
        }
        try:
            data = r.json()
        except Exception as exc:
            result["json_parse_error"] = str(exc)[:200]
            result["raw_text_sample"] = r.text[:300]
            return result

        if isinstance(data, list):
            items = data
            result["top_level_shape"] = "list"
            result["top_level_keys"] = None
        elif isinstance(data, dict):
            result["top_level_shape"] = "dict"
            result["top_level_keys"] = list(data.keys())
            items = data.get("data", [])
        else:
            result["top_level_shape"] = type(data).__name__
            items = []

        result["item_count_returned"] = len(items)
        result["exactly_50"] = len(items) == 50

        # Look for any pagination-related metadata anywhere in the top-level dict.
        if isinstance(data, dict):
            pagination_like = {
                k: v for k, v in data.items()
                if k.lower() != "data" and any(t in k.lower() for t in ("total", "count", "page", "offset", "next", "limit", "size"))
            }
            result["pagination_metadata_found"] = pagination_like or None

        if items:
            dates_found = []
            for it in items:
                d = it.get("an_dt") or it.get("sort_date") or it.get("dt")
                if d:
                    dates_found.append(d)
            result["sample_first_item_keys"] = list(items[0].keys())
            result["oldest_date_in_response"] = min(dates_found) if dates_found else None
            result["newest_date_in_response"] = max(dates_found) if dates_found else None
            result["distinct_symbols_in_response"] = len({it.get("symbol") for it in items if it.get("symbol")})
        else:
            result["oldest_date_in_response"] = None
            result["newest_date_in_response"] = None

    except httpx.HTTPStatusError as exc:
        result["http_status"] = exc.response.status_code
        result["error"] = "HTTPStatusError"
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
    return result


async def main() -> None:
    periods = [
        ("30 days ago (single day)", _TODAY - timedelta(days=30), _TODAY - timedelta(days=30)),
        ("~3 months ago (single day)", _TODAY - timedelta(days=90), _TODAY - timedelta(days=90)),
        ("~6 months ago (single day)", _TODAY - timedelta(days=182), _TODAY - timedelta(days=182)),
        ("~1 year ago (single day)", _TODAY - timedelta(days=365), _TODAY - timedelta(days=365)),
        ("~2 years ago (single day)", _TODAY - timedelta(days=730), _TODAY - timedelta(days=730)),
        ("known/likely high-volume day (Q1 FY27 results season, single day)", date(2026, 7, 30), date(2026, 7, 30)),
        ("small wide range (30 days ago -> today, to test if range is honored)", _TODAY - timedelta(days=30), _TODAY),
    ]

    results = []
    async with httpx.AsyncClient(headers=_HEADERS, timeout=15, follow_redirects=True) as client:
        # Same warm-up pattern already proven live-reliable in nse_provider.py --
        # session cookies from the homepage before any /api/* call.
        warmup = await client.get("https://www.nseindia.com/")
        results.append({"label": "WARMUP (homepage)", "http_status": warmup.status_code})
        if warmup.status_code == 403:
            print("WARMUP blocked (403) -- stopping immediately per owner instruction, no retries/bypasses.")
            with open("b5c_nse_historical_probe_results.json", "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2, default=str, ensure_ascii=False)
            return

        for label, from_d, to_d in periods:
            r = await probe_one(client, label, from_d, to_d)
            results.append(r)
            print(f"{label}: status={r.get('http_status')} count={r.get('item_count_returned')} "
                  f"oldest={r.get('oldest_date_in_response')} newest={r.get('newest_date_in_response')} "
                  f"pagination={r.get('pagination_metadata_found')}")
            await asyncio.sleep(2)  # polite, non-aggressive spacing between requests

    with open("b5c_nse_historical_probe_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=str, ensure_ascii=False)
    print("\nfull results written to b5c_nse_historical_probe_results.json")


if __name__ == "__main__":
    asyncio.run(main())
