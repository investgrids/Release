"""
Real IPO feed from NSE's public issue lists (no fabricated fields).

Sources (NSE public JSON, session cookie from a page warm-up as in NSEProvider):
  /api/ipo-current-issue                  issues open for bidding now
  /api/all-upcoming-issues?category=ipo   issues announced, not open yet
  /api/public-past-issues                 closed / listed issues (large; trimmed to recent)

What NSE provides is what we show: name, symbol, board (Mainboard/SME), price band, final issue price, lot size,
shares on offer, open/close/listing dates, and subscription multiples when the current-issue list carries them.
It does NOT provide grey-market premium, ratings, sector or financials, so none of those exist here.
Status is derived from the dates against today's date in India, never stored.
"""
from __future__ import annotations

import asyncio
import re
import time
from datetime import date, datetime, timedelta, timezone

import httpx
import structlog

log = structlog.get_logger(__name__)

_BASE = "https://www.nseindia.com"
_WARMUP = f"{_BASE}/market-data/all-upcoming-issues-ipo"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": _WARMUP,
}
_IST = timezone(timedelta(hours=5, minutes=30))
_TTL_S = 600            # fresh for 10 minutes
_STALE_MAX_S = 6 * 3600  # serve a stale copy for up to 6 hours if NSE is unreachable
_PAST_DAYS = 120
_PAST_LIMIT = 120
_BOARD = {"EQ": "Mainboard", "SME": "SME", "BE": None}   # BE = trade-for-trade series, used by both boards, so the board is left unstated; other series are bonds/NCDs/rights, not IPOs

_cache: dict = {"at": 0.0, "data": None}
_lock = asyncio.Lock()


def _num(s) -> float | None:
    if s is None:
        return None
    m = re.sub(r"[^\d.]", "", str(s))
    try:
        return float(m) if m not in ("", ".") else None
    except ValueError:
        return None


def _band(text) -> tuple[float | None, float | None]:
    nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", str(text or "").replace(",", ""))]
    if not nums:
        return None, None
    return (nums[0], nums[-1]) if len(nums) > 1 else (nums[0], nums[0])


def _date(s) -> date | None:
    s = str(s or "").strip()
    if not s or s == "-":
        return None
    for fmt in ("%d-%b-%Y", "%d-%B-%Y"):
        try:
            return datetime.strptime(s.title(), fmt).date()
        except ValueError:
            continue
    return None


def _iso(d: date | None) -> str | None:
    return d.isoformat() if d else None


def _crore(value: float | None) -> str | None:
    if not value:
        return None
    cr = value / 1e7
    return f"₹{cr:,.0f} Cr" if cr >= 100 else f"₹{cr:,.1f} Cr"


def _slug(symbol: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", symbol.lower()).strip("-")


def _status(open_d: date | None, close_d: date | None, list_d: date | None, today: date) -> str:
    if open_d and open_d > today:
        return "Upcoming"
    if close_d and close_d >= today:
        return "Ongoing"
    if list_d and list_d <= today:
        return "Listed"
    return "Closed"          # bidding over, listing not yet on record


def _record(name, symbol, board, band_text, issue_price, lot, shares, open_d, close_d, list_d, today, subs=None) -> dict | None:
    if not (name and symbol):
        return None
    pmin, pmax = _band(band_text)
    final = _num(issue_price)
    shares_n = _num(shares)
    top = pmax or final
    value = shares_n * top if shares_n and top else None
    return {
        "id": _slug(symbol),
        "name": str(name).strip(),
        "symbol": str(symbol).strip().upper(),
        "type": board,
        "status": _status(open_d, close_d, list_d, today),
        "priceMin": pmin, "priceMax": pmax,
        "issuePrice": final,
        "lotSize": int(_num(lot)) if _num(lot) else None,
        "sharesOffered": int(shares_n) if shares_n else None,
        "issueValue": _crore(value),               # shares offered x upper price band: an arithmetic estimate, labelled as such in the UI
        "openDate": _iso(open_d), "closeDate": _iso(close_d), "listingDate": _iso(list_d),
        "subscription": subs,                       # {"total": x, "retail": x, ...} only when NSE supplies it
        "source": "NSE",
    }


def _subscription(row: dict) -> dict | None:
    out = {}
    for key, label in (("noOfTime", "total"), ("totalSubscription", "total"), ("retail", "retail"), ("nii", "nii"), ("qib", "qib")):
        v = _num(row.get(key))
        if v is not None:
            out.setdefault(label, v)
    return out or None


def build(upcoming: list, current: list, past: list, today: date) -> list[dict]:
    seen, out = set(), []

    def add(rec):
        if rec and rec["id"] not in seen:
            seen.add(rec["id"])
            out.append(rec)

    for r in current or []:
        board = _BOARD.get(str(r.get("series") or r.get("securityType") or "").upper(), "Mainboard")
        add(_record(r.get("companyName") or r.get("company"), r.get("symbol"), board, r.get("issuePrice") or r.get("priceBand"),
                    None, r.get("lotSize"), r.get("issueSize") or r.get("noOfSharesOffered"),
                    _date(r.get("issueStartDate")), _date(r.get("issueEndDate")), None, today, _subscription(r)))
    for r in upcoming or []:
        board = _BOARD.get(str(r.get("series") or "").upper(), "Mainboard")
        add(_record(r.get("companyName"), r.get("symbol"), board, r.get("priceBand") or r.get("issuePrice"),
                    None, r.get("lotSize"), r.get("issueSize"),
                    _date(r.get("issueStartDate")), _date(r.get("issueEndDate")), None, today))
    cutoff = today - timedelta(days=_PAST_DAYS)
    recent = []
    for r in past or []:
        series = str(r.get("securityType") or "").upper()
        board = _BOARD.get(series)
        start = _date(r.get("ipoStartDate"))
        if series in _BOARD and start and start >= cutoff:
            recent.append((start, r, board))
    for start, r, board in sorted(recent, key=lambda t: t[0], reverse=True)[:_PAST_LIMIT]:
        add(_record(r.get("companyName") or r.get("company"), r.get("symbol"), board, r.get("priceRange"),
                    r.get("issuePrice"), None, None, start, _date(r.get("ipoEndDate")), _date(r.get("listingDate")), today))
    return out


async def _fetch() -> tuple[list, list, list]:
    async with httpx.AsyncClient(headers=_HEADERS, timeout=20, follow_redirects=True) as c:
        await c.get(_WARMUP)                       # session cookies; the API rejects cookie-less calls

        async def get(path: str) -> list:
            r = await c.get(f"{_BASE}{path}", headers={"Accept": "application/json"})
            r.raise_for_status()
            d = r.json()
            return d if isinstance(d, list) else (d.get("data") or [])

        return await asyncio.gather(
            get("/api/all-upcoming-issues?category=ipo"), get("/api/ipo-current-issue"), get("/api/public-past-issues"))


def _stats(ipos: list[dict]) -> dict:
    by = lambda s: sum(1 for i in ipos if i["status"] == s)
    return {"upcoming": by("Upcoming"), "ongoing": by("Ongoing"), "closed": by("Closed"), "listed": by("Listed"),
            "mainboard": sum(1 for i in ipos if i["type"] == "Mainboard"), "sme": sum(1 for i in ipos if i["type"] == "SME")}


async def get_ipos() -> dict:
    """Cached IPO list. Never raises: returns data_source 'unavailable' with an empty list if NSE has never answered."""
    now = time.time()
    if _cache["data"] is not None and now - _cache["at"] < _TTL_S:
        return _cache["data"]
    async with _lock:
        if _cache["data"] is not None and time.time() - _cache["at"] < _TTL_S:
            return _cache["data"]
        try:
            upcoming, current, past = await _fetch()
            today = datetime.now(_IST).date()
            ipos = build(upcoming, current, past, today)
            data = {"ipos": ipos, "stats": _stats(ipos), "as_of": datetime.now(timezone.utc).isoformat(),
                    "data_source": "nse", "is_mock": False, "stale": False}
            _cache.update(at=time.time(), data=data)
            return data
        except Exception as exc:  # noqa: BLE001 - upstream is a scraped public API; degrade, never 500
            log.warning("ipo_feed.fetch_failed", error=str(exc)[:200])
            old = _cache["data"]
            if old is not None and time.time() - _cache["at"] < _STALE_MAX_S:
                return {**old, "stale": True}
            return {"ipos": [], "stats": _stats([]), "as_of": None, "data_source": "unavailable", "is_mock": False, "stale": False}
