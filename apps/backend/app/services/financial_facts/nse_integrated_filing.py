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
    "ProfitOrLossAttributableToOwnersOfParent", "ProfitOrLossAttributableToNonControllingInterests",
    "ComprehensiveIncomeForThePeriod", "ComprehensiveIncomeForThePeriodAttributableToOwnersOfParent",
)  # owners' profit is a non-dimensional in-capmkt concept, populated only by some filings (not e.g. SYRMA's)
INSTANT_CONCEPTS = (
    "Assets", "Equity", "EquityAttributableToOwnersOfParent", "CurrentLiabilities",
    "BorrowingsCurrent", "BorrowingsNoncurrent", "EquityAndLiabilities",
)
REQUIRED_CONCEPTS = FLOW_CONCEPTS + INSTANT_CONCEPTS
# Read when present (disposal / discontinued-operations disclosures); their absence is not "missing".
OPTIONAL_FLOW = ("ProfitLossFromDiscontinuedOperationsAfterTax",)
OPTIONAL_INSTANT = ("Borrowings", "DebtSecurities", "SubordinatedLiabilities", "LongTermBorrowings", "ShortTermBorrowings", "ShareholdersFunds",
                    "AssetsClassifiedAsHeldForSale", "NoncurrentAssetsOrDisposalGroupsClassifiedAsHeldForSale",
                    "LiabilitiesDirectlyAssociatedWithAssetsInDisposalGroupClassifiedAsHeldForSale")
CORE_CONCEPTS = FLOW_CONCEPTS + INSTANT_CONCEPTS + OPTIONAL_FLOW + OPTIONAL_INSTANT
_REG_BAL = re.compile(r"^RegulatoryDeferralAccount(Debit|Credit)Balances")
_DISPOSAL_NAME = re.compile(r"HeldForSale|DisposalGroup|DiscontinuedOperations")
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
    annual_status: str = ""  # "audited" | "unverified_unaudited": a year-end filing is not treated as audited unless it is
    xbrl_fullyear_audit: str = ""  # value of WhetherResultsAreAuditedOrUnaudited on the full-year context ("Audited" / "Unaudited" / "")
    audit_source: str = ""         # "xbrl_fullyear" | "listing": which source decided annual_status
    disposal_facts: dict = field(default_factory=dict)  # concept -> crore, any non-dimensional held-for-sale / disposal-group / discontinued-operations fact
    regulatory: dict = field(default_factory=dict)      # {"debit": crore, "credit": crore} regulatory-deferral account balances at the period end


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
    body = None
    if raw_dir:  # reuse a previously saved copy of this exact filing (same symbol + file id); verified by its hash in provenance
        import glob
        hits = sorted(glob.glob(f"{raw_dir}/{ref.symbol}_{ref.filing_file_id}_*.xml"))
        if hits:
            with open(hits[0], "rb") as fh:
                body = fh.read()
    if body is None:
        s = session or _session()
        resp = s.get(ref.xbrl_url, headers=_HEADERS, timeout=60)
        resp.raise_for_status()
        body = resp.content
        if raw_dir:
            with open(f"{raw_dir}/{ref.symbol}_{ref.filing_file_id}_{hashlib.sha256(body).hexdigest()[:12]}.xml", "wb") as fh:
                fh.write(body)
    sha = hashlib.sha256(body).hexdigest()
    root = ET.fromstring(body)
    ctx = _contexts(root)
    # Legacy (in-bse-fin) annual files define their contexts with quarter dates and state the real period of each context in the
    # DateOfStart/EndOfReportingPeriod facts; where a context has both, those facts are the period.
    _starts, _ends = {}, {}
    for _el in root.iter():
        _n = _el.tag.split("}")[-1]
        if _n == "DateOfStartOfReportingPeriod" and _el.text:
            _starts[_el.get("contextRef")] = _el.text.strip()
        elif _n == "DateOfEndOfReportingPeriod" and _el.text:
            _ends[_el.get("contextRef")] = _el.text.strip()
    for _cid in set(_starts) & set(_ends):
        try:
            if _cid in ctx and ctx[_cid][0] == "duration":
                ctx[_cid] = ("duration", date.fromisoformat(_starts[_cid]), date.fromisoformat(_ends[_cid]), ctx[_cid][3])
        except ValueError:
            pass
    ex = FilingExtract(ref=ref, retrieved_at=datetime.now(timezone.utc).isoformat(), sha256=sha, nbytes=len(body), currency=None, level_of_rounding=None)
    prior_end = date(ref.period_end.year - 1, ref.period_end.month, min(ref.period_end.day, 28)) if ref.period_end.month == 2 else date(ref.period_end.year - 1, ref.period_end.month, ref.period_end.day)
    for el in root.iter():
        name = el.tag.split("}")[-1]
        if name == "DescriptionOfPresentationCurrency" and el.text:
            ex.currency = el.text.strip()
        elif name == "LevelOfRounding" and el.text:
            ex.level_of_rounding = el.text.strip()
        if name == "WhetherResultsAreAuditedOrUnaudited" and el.text:
            cd = ctx.get(el.get("contextRef"))
            if cd and cd[0] == "duration" and not cd[3] and _is_year(cd[1], cd[2]) and cd[2] == ref.period_end:
                v = el.text.strip()
                # two different statements for the same full-year context are ambiguous: never treated as audited
                ex.xbrl_fullyear_audit = v if ex.xbrl_fullyear_audit in ("", v) else "AMBIGUOUS"
        if _DISPOSAL_NAME.search(name) and "PerShare" not in name:
            cd = ctx.get(el.get("contextRef"))
            if cd and not cd[3] and (cd[2] == ref.period_end):
                try:
                    ex.disposal_facts.setdefault(name, round(float((el.text or "").strip()) / 1e7, 2))
                except ValueError:
                    pass
        if _REG_BAL.match(name):
            cd = ctx.get(el.get("contextRef"))
            if cd and not cd[3] and cd[0] == "instant" and cd[2] == ref.period_end:
                try:
                    k = "debit" if "Debit" in name else "credit"
                    ex.regulatory[k] = round(ex.regulatory.get(k, 0.0) + float((el.text or "").strip()) / 1e7, 2)
                except ValueError:
                    pass
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
        if name in FLOW_CONCEPTS + OPTIONAL_FLOW and kind == "duration" and _is_year(start, end):
            if end == ref.period_end:
                ex.facts.setdefault(name, fact)
            elif end == prior_end:
                ex.prior.setdefault(name, fact)
        elif name in INSTANT_CONCEPTS + OPTIONAL_INSTANT and kind == "instant":
            if end == ref.period_end:
                ex.facts.setdefault(name, fact)
            elif end == prior_end:
                ex.prior.setdefault(name, fact)
    ex.missing = [c for c in REQUIRED_CONCEPTS if c not in ex.facts]
    # The listing's audited flag describes the filing's reporting quarter, not the year, and has disagreed with the filing in the unsafe
    # direction (listing Audited, full-year Unaudited). Only the filing's own full-year statement can make a year-end filing audited; a missing,
    # Unaudited or conflicting statement means audit status is unverified. The listing flag is never used as a fallback.
    ex.annual_status = "audited" if (ex.xbrl_fullyear_audit or "").lower() == "audited" else "unverified_unaudited"
    ex.audit_source = "xbrl_fullyear" if ex.xbrl_fullyear_audit else "missing_statement"
    return ex


def crore(fact: ExtractedFact | None) -> float | None:
    return None if fact is None else round(fact.value_inr / 1e7, 2)


def latest_annual(rows: list[dict], scope_preference=("Consolidated", "Standalone"), session: requests.Session | None = None,
                  raw_dir: str | None = None, max_periods: int = 6) -> tuple["FilingExtract | None", list[str]]:
    """The newest Ind-AS filing that actually contains a full-year (about 12 months) revenue fact, for any fiscal-year end.
    Walks period ends newest first; interim periods (no 12-month context) are skipped and listed in the notes."""
    notes: list[str] = []
    ends = sorted({_parse_qe(r.get("qe_Date")) for r in rows if "INDAS" in (r.get("xbrl") or "") and _parse_qe(r.get("qe_Date"))}, reverse=True)
    for pe in ends[:max_periods]:
        scopes = available_scopes(rows, pe)
        scope = next((sc for sc in scope_preference if sc in scopes), None)
        if scope is None:
            continue
        ref = select_filing(rows, pe, scope)
        if ref is None:
            continue
        ex = extract(ref, session, raw_dir)
        if "RevenueFromOperations" in ex.facts or "ProfitBeforeTax" in ex.facts:
            return ex, notes
        notes.append(f"{pe} {scope}: no full-year context (interim)")
    return None, notes


def owners_profit(ex: "FilingExtract") -> tuple[float | None, str]:
    """Profit attributable to owners of the parent, in INR crore, with the basis it was taken on.
    Consolidated filings may leave the field unpopulated, or populate it as 0 while total profit is not 0 (seen:
    NESTLEIND FY2026); neither is trusted. Falls back to total profit ONLY when the entity has no minority."""
    total = crore(ex.facts.get("ProfitLossForPeriod"))
    owners = crore(ex.facts.get("ProfitOrLossAttributableToOwnersOfParent"))
    nci = crore(ex.facts.get("ProfitOrLossAttributableToNonControllingInterests"))
    if owners is not None and not (owners == 0 and total not in (None, 0)):
        return owners, "owners (filing)"
    if owners is not None:
        return None, "owners reported as 0 while total profit is not 0: unreliable"
    if ex.ref.scope == "Standalone":
        return total, "total profit (standalone, no minority)"
    eq_total, eq_owners = crore(ex.facts.get("Equity")), crore(ex.facts.get("EquityAttributableToOwnersOfParent"))
    if eq_total is not None and eq_owners is not None and abs(eq_total - eq_owners) < 0.01 and total is not None:
        # balance-sheet evidence of no minority: total equity equals equity attributable to owners, so total profit is owners' profit
        return total, "total profit (no minority: equity attributable to owners equals total equity)"
    if nci is not None and total is not None:
        return round(total - nci, 2), "total less non-controlling interest (filing)"
    return None, "owners' profit not populated in a consolidated filing"


def select_annual(rows: list[dict], scope_preference=("Consolidated", "Standalone"), session: requests.Session | None = None,
                  raw_dir: str | None = None, max_periods: int = 6) -> tuple["FilingExtract | None", dict]:
    """Contract rule: choose an eligible year-end filing whose full-year context is AUDITED (the filing's own statement, see extract), then
    apply the scope preference among those (an unverified consolidated filing can never displace an audited standalone one for the same year).
    Year-end periods are those sharing a month with any listing row flagged Audited (the listing flags audited rows only at year end).
    info["newer_unaudited_year_end"] is True when a newer year-end filing exists whose full-year status is not Audited.
    When no audited annual filing exists at all, falls back to the newest year-end filing (flagged unaudited)."""
    info: dict = {"notes": [], "newer_unaudited_year_end": False, "fallback_unaudited": False}
    indas = [r for r in rows if "INDAS" in (r.get("xbrl") or "") and _parse_qe(r.get("qe_Date"))]
    fy_months = {_parse_qe(r["qe_Date"]).month for r in indas if r.get("audited") == "Audited"}
    ends = sorted({_parse_qe(r["qe_Date"]) for r in indas if _parse_qe(r["qe_Date"]).month in fy_months}, reverse=True)
    unverified_ends: list[date] = []
    for pe in ends[:max_periods]:
        scopes = sorted({r.get("consolidated") for r in indas if _parse_qe(r["qe_Date"]) == pe and r.get("consolidated")})
        for scope in [sc for sc in scope_preference if sc in scopes]:
            ref = select_filing(rows, pe, scope)
            if ref is None:
                continue
            try:
                ex = extract(ref, session, raw_dir)
            except requests.HTTPError as exc:  # the row's own link is dead: try the next scope, record the gap
                info["notes"].append(f"{pe} {scope}: XBRL_LINK_{exc.response.status_code if exc.response is not None else 'ERROR'} (seq {ref.seq_id})")
                continue
            if "RevenueFromOperations" not in ex.facts and "ProfitBeforeTax" not in ex.facts:
                info["notes"].append(f"{pe} {scope}: no full-year context (interim)")
                continue
            if ex.annual_status != "audited":
                info["notes"].append(f"{pe} {scope}: full-year status not Audited ({ex.xbrl_fullyear_audit or ref.audited})")
                unverified_ends.append(pe)
                continue
            info["newer_unaudited_year_end"] = any(u > pe for u in unverified_ends)
            return ex, info
    ex, notes = latest_annual(rows, scope_preference, session, raw_dir, max_periods)
    info["notes"] += notes
    info["fallback_unaudited"] = ex is not None
    return ex, info
