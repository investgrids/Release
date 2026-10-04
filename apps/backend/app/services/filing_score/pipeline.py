"""
Filing-backed score pipeline: universe -> per-company collection (injectable) -> peer scoring -> immutable run rows.

Segments: industrial (NSE_FILING_METRICS_V1 contract + NSE_FILING_SCORE_V2 scorer), bank (NSE_FILING_BANK_V1), fin (NSE_FILING_FIN_V1: LENDERS / OTHER).
Every listed company gets a row: either a score, or an explicit withheld reason (never silently dropped). Nothing here writes to any table other than
filing_score_runs / filing_score_snapshots, and nothing here is read by a page unless the (off by default) reader flag is turned on.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Protocol

from app.services.financial_facts import bank_metric_contract as bmc
from app.services.financial_facts import filing_metric_contract as fmc
from app.services.financial_facts import filing_shadow_score as fss
from app.services.financial_facts import nbfc_metric_contract as fin

METHOD_VERSION = "NSE_FILING_SCORE_V3"
CONTRACTS = {"industrial": fmc.CONTRACT_VERSION, "bank": bmc.BANK_CONTRACT_VERSION, "fin": fin.FIN_CONTRACT_VERSION, "scorer": fss.SCORING_VERSION}
BANK_SECTORS = {"Banking"}
FIN_SECTORS = {"Finance", "NBFC"}
UNSUPPORTED_SECTORS = {"Insurance", "ETF", "REIT", "InvIT"}   # separate formats / not scoreable on fundamentals: explicit N/A, never guessed


@dataclass
class Company:
    symbol: str
    sector: str | None
    peer_group: str | None = None   # inside a grouped sector (Infrastructure); None otherwise


@dataclass
class Collected:
    symbol: str
    segment: str                    # industrial | bank | fin
    fm: dict | None                 # contract output as a dict (metrics, valuation, flags, provenance, status ...)
    mb: float | None = None         # market-behaviour pillar score
    inputs: dict = field(default_factory=dict)   # extracted figures (crore), prior-year figures, reference multiples, price
    error: str | None = None


class Collector(Protocol):
    def collect(self, company: Company, segment: str) -> Collected: ...


def classify(company: Company, taxonomy: str | None = None) -> str | None:
    """Segment for a company. A banking-format filer is a bank whatever the sector label says (8 banks sit under 'Finance'). None = not supported."""
    if taxonomy == "BANKING" or company.sector in BANK_SECTORS:
        return "bank"
    if not company.sector:
        return None
    if company.sector in UNSUPPORTED_SECTORS:
        return None
    if company.sector in FIN_SECTORS:
        return "fin"
    return "industrial"


def _label_for(reason: str | None, flags: dict | None) -> str | None:
    if (flags or {}).get("na_label"):
        return flags["na_label"]
    return {"NO_SECTOR_ASSIGNED": "N/A - Sector not assigned", "SEGMENT_NOT_SUPPORTED": "N/A - Scoring method not available for this company type",
            "COLLECTION_ERROR": "N/A - Data collection failed"}.get(reason or "", None)


def _row(c: Collected | None, symbol: str, segment: str, peer_group: str | None, r: dict | None, contract_version: str | None) -> dict:
    fm = (c.fm if c else None) or {}
    r = r or {}
    scored = r.get("state") == "scored"
    reason = None if scored else (r.get("reason") or "NO_FILING_RECORD")
    return {
        "symbol": symbol, "segment": segment, "peer_group": peer_group, "state": "scored" if scored else "withheld",
        "score": r.get("score"), "rating": r.get("rating"), "financial_strength": r.get("fs"), "valuation": r.get("val"), "market_behaviour": r.get("mb"),
        "coverage_pct": r.get("coverage"), "metrics_used": r.get("fs_n"), "withheld_reason": reason,
        "na_label": None if scored else (r.get("label") or _label_for(reason, fm.get("flags"))),
        "metadata_flags": r.get("metadata_flags"), "rule_tags": r.get("rule_tags") or (fm.get("flags") or {}).get("rule_tags"),
        "metrics": fm.get("metrics"), "valuation_detail": fm.get("valuation"), "provenance": fm.get("provenance"),
        "inputs": (c.inputs if c else None), "contract_version": contract_version,
    }


def score_universe(universe: list[Company], collector: Collector, taxonomy: dict[str, str] | None = None) -> tuple[list[dict], dict]:
    """Collect every company, score inside peer groups, return (rows, counts). Never raises for one company: a failure becomes a withheld row."""
    taxonomy = taxonomy or {}
    collected: dict[str, Collected] = {}
    segment_of: dict[str, str | None] = {}
    for co in universe:
        seg = classify(co, taxonomy.get(co.symbol))
        segment_of[co.symbol] = seg
        if seg is None:
            continue
        try:
            collected[co.symbol] = collector.collect(co, seg)
        except Exception as exc:  # one company never stops a run
            collected[co.symbol] = Collected(symbol=co.symbol, segment=seg, fm=None, error=f"{type(exc).__name__}: {str(exc)[:120]}")
    by_company = {co.symbol: co for co in universe}
    results: dict[str, dict] = {}
    # industrial: peers = the company's sector (or its peer group inside a grouped sector)
    groups: dict[str, list[str]] = defaultdict(list)
    for s, c in collected.items():
        if c.segment == "industrial":
            co = by_company[s]
            groups[f"{co.sector}|{co.peer_group or ''}"].append(s)
    for members in groups.values():
        fmd = {s: (collected[s].fm if (collected[s].fm or {}).get("metrics") is not None else None) for s in members}
        mb = {s: collected[s].mb for s in members}
        results.update(fss.score_group(members, fmd, mb, pool_statuses=None))
    banks = [s for s, c in collected.items() if c.segment == "bank"]
    if banks:
        results.update(bmc.score_bank_group(banks, {s: collected[s].fm for s in banks if collected[s].fm}, {s: collected[s].mb for s in banks}))
    fins = [s for s, c in collected.items() if c.segment == "fin"]
    if fins:
        results.update(fin.score_fin_groups(fins, {s: collected[s].fm for s in fins if collected[s].fm}, {s: collected[s].mb for s in fins}))
    rows = []
    for co in universe:
        seg = segment_of[co.symbol]
        if seg is None:
            reason = "NO_SECTOR_ASSIGNED" if not co.sector else "SEGMENT_NOT_SUPPORTED"
            rows.append(_row(None, co.symbol, "unsupported", co.peer_group, {"state": "withheld", "reason": reason}, None))
            continue
        c = collected[co.symbol]
        seg = c.segment   # the collector may re-route (a banking-format filer listed under another sector)
        if c.error:
            rows.append(_row(c, co.symbol, seg, co.peer_group, {"state": "withheld", "reason": "COLLECTION_ERROR"}, None))
            continue
        fm = c.fm or {}
        grp = fm.get("group")
        segname = "fin_" + grp.lower() if (seg == "fin" and grp) else seg
        cv = {"industrial": fmc.CONTRACT_VERSION, "bank": bmc.BANK_CONTRACT_VERSION, "fin": fin.FIN_CONTRACT_VERSION}[seg]
        rows.append(_row(c, co.symbol, segname, co.peer_group, results.get(co.symbol), cv))
    counts = {
        "universe": len(rows), "scored": sum(1 for r in rows if r["state"] == "scored"),
        "by_segment": {k: {"scored": sum(1 for r in rows if r["segment"] == k and r["state"] == "scored"), "total": sum(1 for r in rows if r["segment"] == k)}
                       for k in sorted({r["segment"] for r in rows})},
        "withheld_reasons": dict(Counter(r["withheld_reason"] for r in rows if r["state"] != "scored")),
    }
    return rows, counts


def market_cap_check(stored_mcap_cr: float | None, price: float | None, paid_up_inr: float | None, face_value: float | None,
                     live_pb: float | None, equity_cr: float | None) -> dict | None:
    """Rule 4C market-cap arm input. The stored market cap (price x Yahoo shares) is compared with price x the FILING's own share count (paid-up capital /
    face value). It is flagged only when they differ by more than 1.5x AND live P/B x filed equity agrees with the filing-share figure rather than with the stored
    one (a wrong Yahoo share count). A stale filing share count after a split or bonus leaves live P/B agreeing with the stored figure, so nothing is flagged."""
    if not (stored_mcap_cr and price and paid_up_inr and face_value and live_pb and equity_cr and equity_cr > 0):
        return None
    filing_mc = price * (paid_up_inr / face_value) / 1e7
    near = lambda x, y: bool(x and y and 1 / 1.5 <= x / y <= 1.5)
    if near(stored_mcap_cr, filing_mc):
        return None
    implied = live_pb * equity_cr
    if near(filing_mc, implied) and not near(stored_mcap_cr, implied):
        return {"stored": round(stored_mcap_cr, 2), "price_x_filing_shares": round(filing_mc, 2), "live_pb_x_equity": round(implied, 2), "ratio": round(stored_mcap_cr / filing_mc, 2)}
    return None
