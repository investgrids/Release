"""
Live collector: NSE Integrated Filing XBRL + Yahoo Finance (market cap, price and live reference multiples, interim and labelled) + the production
market-behaviour pillar. Network-bound and blocking: run it in a worker thread (the runner does). Not used by any request path.
"""
from __future__ import annotations

import asyncio
import dataclasses
from datetime import date, datetime

from app.services.filing_score.pipeline import Collected, Company, market_cap_check
from app.services.financial_facts import bank_metric_contract as bmc
from app.services.financial_facts import filing_metric_contract as fmc
from app.services.financial_facts import nbfc_metric_contract as fin
from app.services.financial_facts import nse_integrated_filing as nif


def _yahoo(symbol: str) -> dict:
    import yfinance as yf
    try:
        i = yf.Ticker(symbol + ".NS").info or {}
    except Exception:
        i = {}
    px = i.get("currentPrice") or i.get("regularMarketPrice")
    sh, mc = i.get("sharesOutstanding"), i.get("marketCap")
    mcap = round((px * sh if (px and sh) else (mc or 0)) / 1e7, 2) or None
    return {"price": px, "market_cap_cr": mcap, "pb": i.get("priceToBook"), "pe": i.get("trailingPE")}


def _same_scope_prior(rows, marker: str, period: date, scope: str):
    ref_period = date(period.year - 1, period.month, min(period.day, 28) if period.month == 2 else period.day)
    c = [nif._ref(r) for r in rows if marker in (r.get("xbrl") or "") and r.get("consolidated") == scope and nif._parse_qe(r.get("qe_Date")) == ref_period]
    c = [x for x in c if x]
    if not c:
        return None
    aud = [x for x in c if x.audited == "Audited"]
    return sorted(aud or c, key=lambda x: (x.revised or x.broadcast or datetime.min))[-1]


class LiveCollector:
    def __init__(self, today: date | None = None, raw_dir: str | None = None, market_behaviour: bool = True):
        self.today, self.raw_dir, self.behaviour = today or date.today(), raw_dir, market_behaviour
        self.sess = nif._session()

    def _mb(self, symbol: str, sector: str | None) -> float | None:
        if not self.behaviour:
            return None
        from app.services.marketripple_score.market_behaviour import score_market_behaviour
        try:
            return asyncio.run(score_market_behaviour(symbol, sector)).score
        except Exception:
            return None

    def collect(self, company: Company, segment: str) -> Collected:
        sym = company.symbol
        rows = nif.list_filings(sym, self.sess)
        if segment != "bank" and any("BANKING" in (r.get("xbrl") or "") for r in rows):
            segment = "bank"   # a banking-format filer is scored as a bank whatever its sector label says
        y = _yahoo(sym)
        ref = {"pb": y["pb"], "pe": y["pe"]}
        inputs: dict = {"price": y["price"], "market_cap_cr": y["market_cap_cr"], "market_cap_source": "Yahoo Finance (interim)", "reference": ref}
        if segment == "bank":
            bf, info = bmc.select_bank_annual(rows, session=self.sess, raw_dir=self.raw_dir)
            prior = ratio = None
            if bf is not None:
                pr = _same_scope_prior(rows, "BANKING", bf.ref.period_end, bf.ref.scope)
                prior = bmc.extract_bank(pr, self.sess, self.raw_dir) if pr else None
                if bf.ref.scope == "Consolidated":
                    sr = _same_scope_prior(rows, "BANKING", date(bf.ref.period_end.year + 1, bf.ref.period_end.month, min(bf.ref.period_end.day, 28)), "Standalone")
                    ratio = bmc.extract_bank(sr, self.sess, self.raw_dir) if sr else None
            fm = bmc.compute_bank(sym, bf, prior, y["market_cap_cr"], today=self.today, newer_unaudited_year_end=info["newer_unaudited_year_end"], reference=ref,
                                  ratio_source=ratio, price=y["price"])
            inputs.update({"facts_cr": bf.facts if bf else None, "prior_facts_cr": prior.prior if prior else (bf.prior if bf else None), "eps": bf.eps if bf else None})
            return Collected(sym, "bank", dataclasses.asdict(fm), self._mb(sym, company.sector or "Banking"), inputs)
        if segment == "fin":
            bf, info = fin.select_fin_annual(rows, session=self.sess, raw_dir=self.raw_dir)
            prior = None
            if bf is not None:
                pr = _same_scope_prior(rows, fin.MARKER, bf.ref.period_end, bf.ref.scope)
                prior = bmc.extract_bank(pr, self.sess, self.raw_dir, flow=fin.FLOW, instant=fin.INSTANT, ratio=("DebtEquityRatio",), per_share=fin.PER_SHARE) if pr else None
            fm = fin.compute_fin(sym, bf, prior, y["market_cap_cr"], today=self.today, newer_unaudited_year_end=info["newer_unaudited_year_end"], reference=ref, price=y["price"])
            inputs.update({"facts_cr": bf.facts if bf else None, "prior_facts_cr": prior.facts if prior else None, "eps": bf.eps if bf else None})
            return Collected(sym, "fin", dataclasses.asdict(fm), self._mb(sym, company.sector or "Finance"), inputs)
        ex, info = nif.select_annual(rows, session=self.sess, raw_dir=self.raw_dir)
        prior = None
        if ex is not None:
            pe = ex.ref.period_end
            pr = nif.select_filing(rows, date(pe.year - 1, pe.month, min(pe.day, 28) if pe.month == 2 else pe.day), ex.ref.scope)
            if pr:
                try:
                    prior = nif.extract(pr, self.sess, self.raw_dir)
                except Exception:
                    prior = None
            if ex.eps and y["price"] and ex.eps > 0:
                ref["pe_eps"] = round(y["price"] / ex.eps, 2)
            eq = fmc._c(ex, "EquityAttributableToOwnersOfParent") if ex.ref.scope == "Consolidated" else fmc._c(ex, "Equity")
            mci = market_cap_check(y["market_cap_cr"], y["price"], ex.paid_up_inr, ex.face_value, y["pb"], eq if eq is not None else fmc._c(ex, "Equity"))
            if mci:
                ref["mc_inconsistent"] = mci
        fm = fmc.compute(sym, ex, prior, y["market_cap_cr"], today=self.today, newer_unaudited_year_end=info["newer_unaudited_year_end"], reference=ref, price=y["price"])
        inputs.update({"facts_cr": {k: nif.crore(v) for k, v in ex.facts.items()} if ex else None,
                       "prior_facts_cr": {k: nif.crore(v) for k, v in prior.facts.items()} if prior else None, "eps": ex.eps if ex else None})
        return Collected(sym, "industrial", dataclasses.asdict(fm), self._mb(sym, company.sector), inputs)
