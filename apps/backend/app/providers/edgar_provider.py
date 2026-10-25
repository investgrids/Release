"""
SEC EDGAR material-filings provider (Phase 1, 2026-10-25).

US-gov public domain (17 U.S.C. §105) — free, no auth, public display permitted.
Mirrors fed_provider.py pattern-for-pattern: fetch → normalize → RawItem, impact
left None (real impact is computed downstream by the Event pipeline, never a
fabricated placeholder — see providers/base.py's RawItem docstring).

Access respects SEC fair-access policy (verified 2026-10-25 against
sec.gov/os/accessing-edgar-data): a declared User-Agent with contact, bounded
requests (one getcurrent GET per form, <=10 req/s), conservative polling.

Company resolution goes ONLY through the existing read-only resolver
(company_identity.resolver.resolve_identifier). Against the current India-centric
company master a US issuer resolves to UNRESOLVED, which yields NO company link —
never a fabricated company, alias, or relationship.
"""
from __future__ import annotations

import re
import time
from datetime import date
from xml.etree import ElementTree as ET

import httpx

from .base import BaseProvider, RawItem
# Module-level imports so tests can monkeypatch them cleanly.
from app.db.session import AsyncSessionLocal
from app.services.company_identity.resolver import resolve_identifier, ResolutionStatus

_UA = {
    "User-Agent": "MarketRipple/1.0 (investgrids@gmail.com)",  # SEC requires a declared UA + contact
    "Accept-Encoding": "gzip, deflate",
}
_GETCURRENT = "https://www.sec.gov/cgi-bin/browse-edgar"
_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
_ATOM_NS = {"a": "http://www.w3.org/2005/Atom"}

# Approved Phase-1 allowlist. getcurrent `type=` prefix-matches, so each base
# form also returns its "/A" amendment (preserved as a DISTINCT filing by its
# own accession number). 6-K is intentionally excluded here (separately
# controlled extension, not in the initial approved scope).
_BASE_FORMS = ["8-K", "10-K", "10-Q", "SC 13D", "SC 13G", "S-1"]

# CIK->ticker map (company_tickers.json), cached in-memory; used only to feed the
# existing resolver a ticker. One extra GET at most once/day.
_cik_ticker_cache: dict = {"ts": 0.0, "map": {}}
_TICKER_TTL = 86400


def _cik_int(cik: str | None) -> int | None:
    try:
        return int(str(cik).lstrip("0") or "0")
    except Exception:
        return None


def _parse_atom(xml_text: str) -> list[dict]:
    """Parse an EDGAR getcurrent Atom feed into raw dicts."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    out: list[dict] = []
    for entry in root.findall("a:entry", _ATOM_NS):
        title = (entry.findtext("a:title", default="", namespaces=_ATOM_NS) or "").strip()
        link_el = entry.find("a:link", _ATOM_NS)
        url = (link_el.get("href") if link_el is not None else "") or ""
        updated = (entry.findtext("a:updated", default="", namespaces=_ATOM_NS) or "").strip()
        # title form: "8-K - APPLE INC (0000320193) (Filer)"
        m = re.match(r"^(.*?)\s+-\s+(.*?)\s+\((\d{10})\)", title)
        form = company = cik = ""
        if m:
            form, company, cik = m.group(1).strip(), m.group(2).strip(), m.group(3).strip()
        # accession number from the filing URL
        acc = ""
        am = re.search(r"/(\d{10}-\d{2}-\d{6})-index", url)
        if am:
            acc = am.group(1)
        else:
            am2 = re.search(r"/(\d{18})/", url)  # dashless accession folder
            if am2:
                s = am2.group(1)
                acc = f"{s[:10]}-{s[10:12]}-{s[12:]}"
        out.append({
            "form": form, "company": company, "cik": cik, "url": url,
            "accession": acc, "published_at": (updated[:10] if updated else ""),
        })
    return out


class EdgarProvider(BaseProvider):
    source_name = "SEC EDGAR"
    capture_raw_evidence = True
    FORMS = _BASE_FORMS

    async def fetch_latest(self) -> list[dict]:
        raws: list[dict] = []
        async with httpx.AsyncClient(headers=_UA, timeout=15, follow_redirects=True) as c:
            for form in self.FORMS:
                try:
                    r = await c.get(_GETCURRENT, params={
                        "action": "getcurrent", "type": form, "company": "",
                        "dateb": "", "owner": "include", "count": 100, "output": "atom",
                    })
                    r.raise_for_status()
                    raws.extend(_parse_atom(r.text))
                except Exception:
                    # Per-form failure isolated — one form's error never drops the rest.
                    continue
        return raws

    async def fetch_by_date(self, target: date) -> list[dict]:
        items = await self.fetch_latest()
        ts = target.isoformat()
        return [i for i in items if (i.get("published_at", "") or "").startswith(ts)]

    def normalize(self, raw: dict) -> RawItem | None:
        accession = (raw.get("accession") or "").strip()
        form = (raw.get("form") or "").strip()
        company = (raw.get("company") or "").strip()
        if not accession or not form or not company:
            return None  # need a stable accession identity + form + issuer
        url = raw.get("url", "")
        cik = raw.get("cik", "")
        summary = f"{form} filed by {company} (CIK {cik}). Source: SEC EDGAR. {url}".strip()
        return RawItem(
            id=f"edgar-{accession}",   # accession number is globally unique; amendments get their own
            headline=f"{company} - {form}"[:512],
            summary=summary[:1000],
            source="SEC EDGAR",
            url=url,
            published_at=raw.get("published_at", ""),
            companies=[],              # resolved below via the existing resolver; never fabricated
            impact_score=None,         # real impact computed downstream
            event_type="filing",
            extra={"cik": cik, "form": form, "accession": accession},
        )

    async def fetch_and_normalize(self) -> list[RawItem]:
        items = await super().fetch_and_normalize()
        try:
            await self._resolve_companies(items)
        except Exception:
            # Resolution is additive; its failure must never break ingestion.
            # Items simply keep companies=[] (no fabricated link).
            pass
        return items

    async def _resolve_companies(self, items: list[RawItem]) -> None:
        """Attach a company link ONLY when the existing resolver RESOLVES the
        issuer's ticker to a real entity. UNRESOLVED / CONFLICT / no-ticker →
        leave companies=[] (never create a company, alias, or link)."""
        if not items:
            return
        cik_map = await self._cik_ticker_map()
        async with AsyncSessionLocal() as db:
            for it in items:
                cik = (it.extra or {}).get("cik")
                ticker = cik_map.get(_cik_int(cik)) if cik else None
                if not ticker:
                    continue
                res = await resolve_identifier(db, ticker)
                if res.status == ResolutionStatus.RESOLVED and res.entity_id:
                    it.companies = [res.entity_id]

    async def _cik_ticker_map(self) -> dict:
        now = time.time()
        if _cik_ticker_cache["map"] and now - _cik_ticker_cache["ts"] < _TICKER_TTL:
            return _cik_ticker_cache["map"]
        try:
            async with httpx.AsyncClient(headers=_UA, timeout=15, follow_redirects=True) as c:
                r = await c.get(_TICKERS_URL)
                r.raise_for_status()
                data = r.json()
            m: dict = {}
            for row in (data.values() if isinstance(data, dict) else data):
                try:
                    m[int(row["cik_str"])] = row["ticker"]
                except Exception:
                    continue
            _cik_ticker_cache.update(ts=now, map=m)
            return m
        except Exception:
            return _cik_ticker_cache["map"] or {}
