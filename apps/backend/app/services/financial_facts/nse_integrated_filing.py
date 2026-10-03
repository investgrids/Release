"""
Reader for NSE's official "Integrated Filing - Financials" listing and its XBRL files (pilot, 2026-10-03).

Why: the older results feed used by nse_xbrl_client.py stops at Dec-2024. The official listing page
(https://www.nseindia.com/companies-listing/corporate-integrated-filing) calls
    GET /api/integrated-filing-results?index=equities&symbol=<SYMBOL>&page=<n>&size=<n>
and every row carries its own `xbrl` URL, which this module follows as given (never a constructed path).

Rules this reader enforces:
- paginate until `totalCount` rows are collected;
- pick the filing for one period end and one scope; among the original and its revisions use the latest
  (by revised_Date, else broadcast_Date);
- keep, with every extracted value: filing id (seq_Id + the file id in the URL), source URL, retrieval time,
  currency and level of rounding, the exact XBRL concept name, the context period, and the raw-file SHA-256;
- never infer a value: a concept that is absent is reported as missing;
- reported (after-tax) profit and "profit before exceptional items and tax" are separate named values; the filing
  has no after-tax adjusted figure and none is derived here.

Not wired into the scorer or any scheduler.
"""
from __future__ import annotations

import hashlib
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

import requests

_BASE = "https://www.nseindia.com"
_LIST_URL = _BASE + "/api/integrated-filing-results"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": _BASE + "/companies-listing/corporate-integrated-filing",
}
_PAGE_SIZE = 50
_XBRLI = "{http://www.xbrl.org/2003/instance}"
_XBRLDI = "{http://xbrl.org/2006/xbrldi}"

# Concept -> role. Flow concepts are read for the full-year context, instants at the period end.
FLOW_CONCEPTS = (
    "RevenueFromOperations", "OtherIncome", "FinanceCosts", "DepreciationDepletionAndAmortisationExpense",
    "ProfitBeforeExceptionalItemsAndTax", "ExceptionalItemsBeforeTax", "ProfitBeforeTax", "TaxExpense",
    "ShareOfProfitLossOfAssociatesAndJointVenturesAccountedForUsingEquityMethod",
    "ProfitLossForPeriod", "ProfitLossForPeriodFromContinuingOperations",
    "ComprehensiveIncomeForThePeriod", "ComprehensiveIncomeForThePeriodAttributableToOwnersOfParent",
)  # NB: the filing has no profit-attributable-to-owners concept; only total profit and comprehensive income splits
INSTANT_CONCEPTS = (
    "Assets", "Equity", "EquityAttributableToOwnersOfParent", "CurrentLiabilities",
    "BorrowingsCurrent", "BorrowingsNoncurrent", "EquityAndLiabilities",
)
CORE_CONCEPTS = FLOW_CONCEPTS + INSTANT_CONCEPTS
_MONTHS = {m: i for i, m in enumerate(["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], 1)}


def _session() -> requests.Session:
    s = requests.Session()
    s.get(_BASE, headers=_HEADERS, timeout=15)
    return s


def _parse_dt(raw: str | None) -> datetime | None:
    if not raw:
        return None
    for fmt in ("%d-%b-%Y %H:%M:%S", "%d-%b-%Y"):
        try:
            return datetime.strptime(raw.title(), fmt)
        except ValueError:
            continue
    return None


def _parse_qe(raw: str | None) -> date | None:
    d = _parse_dt(raw)
    return d.date() if d else None


@dataclass
class FilingRef:
    symbol: str
    period_end: date
    scope: str  # "Consolidated" | "Standalone"
    audited: str | None
    type_sub: str | None  # "Original" | "Revision" | "New"
    seq_id: str
    broadcast: datetime | None
    revised: datetime | None
    xbrl_url: str
    filing_file_id: str  # the numeric id inside the XBRL file name, e.g. 1677547


@dataclass
class ExtractedFact:
    concept: str
    value_inr: float
    period: str
    decimals: str | None
    raw_text: str


@dataclass
class FilingExtract:
    ref: FilingRef
    retrieved_at: str
    sha256: str
    nbytes: int
    currency: str | None
    level_of_rounding: str | None
    facts: dict[str, ExtractedFact] = field(default_factory=dict)       # current fiscal year / period end
    prior: dict[str, ExtractedFact] = field(default_factory=dict)       # prior fiscal year comparatives
    missing: list[str] = field(default_factory=list)


def list_filings(symbol: str, session: requests.Session | None = None) -> list[dict]:
    """Every listing row for the symbol (paginated until totalCount is reached)."""
    s = session or _session()
    rows: list[dict] = []
    page = 1
    while True:
        r = s.get(_LIST_URL, headers=_HEADERS, params={"index": "equities", "symbol": symbol.upper(), "page": page, "size": _PAGE_SIZE}, timeout=30)
        r.raise_for_status()
        j = r.json() or {}
        batch = j.get("data") or []
        rows.extend(batch)
        total = int(j.get("totalCount") or 0)
        if not batch or len(rows) >= total:
            break
        page += 1
        time.sleep(0.3)
    return rows


def _ref(row: dict) -> FilingRef | None:
    qe = _parse_qe(row.get("qe_Date"))
    url = row.get("xbrl") or ""
    if qe is None or not url.endswith(".xml") or "/null" in url:
        return None
    m = re.search(r"_(\d+)_\d{12,14}_", url)
    return FilingRef(
        symbol=row.get("symbol"), period_end=qe, scope=row.get("consolidated") or "", audited=row.get("audited"),
        type_sub=row.get("type_Sub"), seq_id=str(row.get("seq_Id")), broadcast=_parse_dt(row.get("broadcast_Date")),
        revised=_parse_dt(row.get("revised_Date")), xbrl_url=url, filing_file_id=m.group(1) if m else "",
    )


def select_filing(rows: list[dict], period_end: date, scope: str) -> FilingRef | None:
    """The applicable financial-results filing for one period end and scope (Ind-AS financial rows only;
    governance filings share the period). An Audited filing is preferred over an Un-Audited one; within the
    chosen class the latest of original/revisions wins. The caller must read `ref.audited` and surface it."""
    cands: list[FilingRef] = []
    for row in rows:
        if "INDAS" not in (row.get("xbrl") or "") or row.get("consolidated") != scope:
            continue
        ref = _ref(row)
        if ref and ref.period_end == period_end:
            cands.append(ref)
    if not cands:
        return None
    audited = [c for c in cands if c.audited == "Audited"]
    pool = audited or cands
    return max(pool, key=lambda c: (c.revised or c.broadcast or datetime.min))


def available_scopes(rows: list[dict], period_end: date) -> list[str]:
    return sorted({r.get("consolidated") for r in rows if "INDAS" in (r.get("xbrl") or "") and _parse_qe(r.get("qe_Date")) == period_end and r.get("consolidated")})


def _contexts(root) -> dict[str, tuple[str, date | None, date | None, bool]]:
    out = {}
    for c in root.iter(_XBRLI + "context"):
        per = c.find(_XBRLI + "period")
        sd, ed, ins = (per.find(_XBRLI + "startDate"), per.find(_XBRLI + "endDate"), per.find(_XBRLI + "instant"))
        has_dim = c.find(".//" + _XBRLI + "scenario") is not None or c.find(".//" + _XBRLDI + "explicitMember") is not None
        if sd is not None and ed is not None:
            out[c.get("id")] = ("duration", date.fromisoformat(sd.text), date.fromisoformat(ed.text), has_dim)
        elif ins is not None:
            out[c.get("id")] = ("instant", None, date.fromisoformat(ins.text), has_dim)
    return out


def _is_year(start: date, end: date) -> bool:
    return 350 <= (end - start).days <= 380


def extract(ref: FilingRef, session: requests.Session | None = None, raw_dir: str | None = None) -> FilingExtract:
    s = session or _session()
    resp = s.get(ref.xbrl_url, headers=_HEADERS, timeout=60)
    resp.raise_for_status()
    body = resp.content
    sha = hashlib.sha256(body).hexdigest()
    if raw_dir:
        with open(f"{raw_dir}/{ref.symbol}_{ref.filing_file_id}_{sha[:12]}.xml", "wb") as fh:
            fh.write(body)
    root = ET.fromstring(body)
    ctx = _contexts(root)
    ex = FilingExtract(ref=ref, retrieved_at=datetime.now(timezone.utc).isoformat(), sha256=sha, nbytes=len(body), currency=None, level_of_rounding=None)
    prior_end = date(ref.period_end.year - 1, ref.period_end.month, min(ref.period_end.day, 28)) if ref.period_end.month == 2 else date(ref.period_end.year - 1, ref.period_end.month, ref.period_end.day)
    for el in root.iter():
        name = el.tag.split("}")[-1]
        if name == "DescriptionOfPresentationCurrency" and el.text:
            ex.currency = el.text.strip()
        elif name == "LevelOfRounding" and el.text:
            ex.level_of_rounding = el.text.strip()
        if name not in CORE_CONCEPTS:
            continue
        c = ctx.get(el.get("contextRef"))
        if not c or c[3]:  # skip dimensional facts
            continue
        kind, start, end, _ = c
        try:
            val = float((el.text or "").strip())
        except ValueError:
            continue
        fact = ExtractedFact(concept=name, value_inr=val, period=f"{start}..{end}" if kind == "duration" else f"@{end}", decimals=el.get("decimals"), raw_text=(el.text or "").strip())
        if name in FLOW_CONCEPTS and kind == "duration" and _is_year(start, end):
            if end == ref.period_end:
                ex.facts.setdefault(name, fact)
            elif end == prior_end:
                ex.prior.setdefault(name, fact)
        elif name in INSTANT_CONCEPTS and kind == "instant":
            if end == ref.period_end:
                ex.facts.setdefault(name, fact)
            elif end == prior_end:
                ex.prior.setdefault(name, fact)
    ex.missing = [c for c in CORE_CONCEPTS if c not in ex.facts]
    return ex


def crore(fact: ExtractedFact | None) -> float | None:
    return None if fact is None else round(fact.value_inr / 1e7, 2)
