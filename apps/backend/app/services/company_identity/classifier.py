"""
Identifier type classifier — the "type protection" the C1 reconciliation
proved is missing (app/db/models/company_entity.py's own module docstring
has the numbers). 48 Intelligence Graph nodes with node_type='company'
turned out, on inspection, to be indices (^NSEI, ^BSESN, BANK_NIFTY),
commodities (CRUDEOIL — already has its own real `commodity`-type node
elsewhere), FX (USDINR), bond/rate references (GOI10YR, 10YBENCH), or
garbled exchange-prefix artifacts (NSE:NSE, BSE:BSE, SHSE:688299) — all
auto-created as if they were companies, with nothing upstream checking
first.

This module answers exactly one question — "what KIND of thing is this
identifier" — and nothing else. It never touches the database and it
never decides whether a COMPANY-shaped identifier is a REAL, already-known
company; that's app.services.company_identity.resolver's job, which reads
(never writes) against the real CompanyEntity/CompanyAlias tables the
importer populates from a sourced universe file. Splitting these two
concerns is what makes "an unknown symbol never silently becomes a
company" actually true: classify() only ever says "this shape is
plausible as a company", and only the importer — fed by a real NSE file,
never by an arbitrary string encountered elsewhere in the app — is
allowed to create a CompanyEntity row.
"""
from __future__ import annotations

import re
from enum import Enum


class IdentifierType(str, Enum):
    COMPANY = "company"          # plausible company/security ticker shape — NOT a confirmed real company
    INDEX = "index"
    COMMODITY = "commodity"
    CURRENCY_FX = "currency_fx"
    BOND_RATE = "bond_rate"
    UNKNOWN = "unknown"          # not confidently any of the above — never auto-created as a company


_EXCHANGE_PREFIXES = ("NSE", "BSE", "MCX", "SHSE", "NYSE", "NASDAQ")

# Real names found in the C1 graph-node sweep (artifacts/company_identity_c1_reconciliation.md §3a).
# Deliberately a denylist, not a guess-by-pattern — a ticker not on any of
# these lists and not shaped like an exchange-prefix/index falls through to
# COMPANY (a *candidate*, still gated by the resolver) or UNKNOWN, never
# silently assumed to be an index/commodity/etc.
_INDEX_NAMES = {
    "NIFTY", "NIFTY50", "BANKNIFTY", "BANK_NIFTY", "BANKEX", "SENSEX",
    "NSEI", "BSESN", "BSESENSEX", "SHCOMP", "HSI",
}
_COMMODITY_NAMES = {
    "CRUDEOIL", "GOLD", "SILVER", "NATURALGAS", "COPPER", "ALUMINIUM",
    "ZINC", "NICKEL", "LEAD", "NATGAS",
}
_CURRENCY_RE = re.compile(r"^[A-Z]{3}(INR|USD|EUR|GBP|JPY)$")
_BOND_RATE_NAMES = {"GSEC", "10YBENCH", "GOI10YR"}
_BOND_RATE_RE = re.compile(r"^GOI\d+Y")  # GOI10YR, GOI10YT=RR, GOI5YR, ...
# Regulators/exchange operators referenced by acronym, not as their own
# listed security (BSE the *company* is real and listed — see
# _resolve_bare_exchange_name below; NSE/SEBI/RBI are not).
_INSTITUTION_NAMES = {"NSE", "SEBI", "RBI"}

_TICKER_SHAPE_RE = re.compile(r"^[A-Z0-9&\-]{1,20}$")


def _strip_exchange_prefix(s: str) -> tuple[str | None, str]:
    """Returns (exchange, remainder) if s looks like 'EXCHANGE:REST', else (None, s)."""
    if ":" in s:
        exch, _, rest = s.partition(":")
        if exch in _EXCHANGE_PREFIXES:
            return exch, rest
    return None, s


def classify_identifier(raw: str) -> IdentifierType:
    """Classify a raw ticker-like string. Pure function, no DB access —
    safe to call from anywhere (ingestion, the resolver, ad-hoc scripts)
    without risking a write."""
    if not raw or not raw.strip():
        return IdentifierType.UNKNOWN

    s = raw.strip().upper()

    if s.startswith("^"):
        return IdentifierType.INDEX

    exch, rest = _strip_exchange_prefix(s)
    if exch is not None:
        if rest in _EXCHANGE_PREFIXES or not rest:
            # self- or cross-exchange references (NSE:NSE, BSE:BSE,
            # NSE:BSE, MCX:MCX) carry no real security identity at all.
            return IdentifierType.UNKNOWN
        # A real exchange-code prefix like "SHSE:688299" is a genuine
        # ticker on a DIFFERENT exchange than the one this Master models
        # (NSE) — not a company in this universe, and not confidently any
        # of the other categories either.
        if exch != "NSE":
            return IdentifierType.UNKNOWN
        return classify_identifier(rest)

    s_bare = re.sub(r"\.(NS|BO)$", "", s).lstrip("^")

    if s_bare in _INDEX_NAMES or s_bare.endswith("SENSEX") or s_bare.endswith("NIFTY"):
        return IdentifierType.INDEX
    if s_bare in _COMMODITY_NAMES:
        return IdentifierType.COMMODITY
    if _CURRENCY_RE.match(s_bare):
        return IdentifierType.CURRENCY_FX
    if s_bare in _BOND_RATE_NAMES or _BOND_RATE_RE.match(s_bare) or "=RR" in s_bare:
        return IdentifierType.BOND_RATE
    if s_bare in _INSTITUTION_NAMES:
        return IdentifierType.UNKNOWN

    if _TICKER_SHAPE_RE.match(s_bare):
        return IdentifierType.COMPANY

    return IdentifierType.UNKNOWN


def normalize_identifier(raw: str) -> str:
    """The one normalization the resolver and importer both need: strip a
    real exchange prefix, strip .NS/.BO, strip a leading '^', uppercase.
    Recognizing 'RELIANCE', 'RELIANCE.NS', and 'NSE:RELIANCE' as the same
    string is the whole point — this does NOT decide whether the result is
    a real company; classify_identifier()/the resolver do that."""
    if not raw:
        return ""
    s = raw.strip().upper()
    exch, rest = _strip_exchange_prefix(s)
    if exch is not None and exch == "NSE":
        s = rest
    s = re.sub(r"\.(NS|BO)$", "", s)
    return s.lstrip("^")
