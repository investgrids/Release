"""
Symbol normalization — shared, reusable resolver for company symbols that
show up on articles/cards/links across the site.

Built for the AI Newsroom redesign (2026-08-10) after confirming a real,
unmitigated bug: `isRealSymbol()` (apps/web/lib/text.ts) only blocklists
placeholder strings like "Not Provided" — it never validates symbol
*format* — so malformed BSE-exchange codes like "BOM:500400" pass straight
through into `/companies/BOM:500400` links, a URL that resolves to nothing
on a site built around NSE symbols.

This module is intentionally generic and framework-agnostic (no FastAPI/DB
imports) so it can be reused anywhere a symbol becomes a link — the article
page, company cards, winners/losers, related-companies, internal-link
candidates — without depending on which caller wired it in. Daily Brief is
deliberately NOT wired to this in this pass (explicit "do not modify Daily
Brief" instruction) even though it could adopt it later.

Never fabricates a company: if a symbol can't be confidently resolved to a
real entry in the NSE universe, `normalize_symbol` returns None and the
caller is expected to drop the link rather than publish a broken one.
"""
from __future__ import annotations

import re

# A BSE-style exchange-qualified code: "BOM:500400", "NSE:INFY", "BSE:500325".
# The numeric BSE form (`BOM:500400`) carries no resolvable ticker at all —
# it can only be resolved via the company *name*, never the code itself.
_EXCHANGE_PREFIX_RE = re.compile(r"^(BOM|BSE|NSE)\s*[:.]\s*(.+)$", re.IGNORECASE)


def _is_plausible_nse_ticker(candidate: str) -> bool:
    """NSE tickers are short, alphabetic (with occasional & or digits for
    things like M&M, 3M), never purely numeric — a purely numeric string is
    always a BSE scrip code, never a real NSE symbol."""
    if not candidate or candidate.isdigit():
        return False
    return bool(re.fullmatch(r"[A-Z0-9&]{1,20}", candidate.upper()))


def normalize_symbol(raw_symbol: str | None, company_name: str | None = None) -> str | None:
    """
    Resolve a possibly-malformed symbol to a canonical NSE ticker from the
    real ~500-company universe (app.api.companies._NSE_UNIVERSE), or None
    if it can't be confidently resolved.

    Resolution order:
      1. Exact symbol match (case-insensitive) against the universe.
      2. Exchange-qualified codes ("BOM:500400"): strip the prefix; if the
         remainder is itself a real ticker, use it; otherwise fall through
         to name-based resolution using company_name (the numeric BSE scrip
         code alone carries no resolvable ticker).
      3. Name-based resolution: company_name matched against each entry's
         real name/aliases using the same word-boundary-safe technique as
         app.services.ai_search.entities._match_companies (reused, not
         reinvented — same lesson as the compute_priority word-boundary fix).
      4. No match → None. Callers must drop the link, not guess.
    """
    from app.api.companies import _NSE_UNIVERSE

    sym = (raw_symbol or "").strip()
    if sym:
        upper = sym.upper()
        for co in _NSE_UNIVERSE:
            if co["symbol"].upper() == upper:
                return co["symbol"]

        m = _EXCHANGE_PREFIX_RE.match(sym)
        if m:
            remainder = m.group(2).strip().upper()
            for co in _NSE_UNIVERSE:
                if co["symbol"].upper() == remainder:
                    return co["symbol"]
        elif _is_plausible_nse_ticker(upper):
            # Not exchange-qualified and not in the universe — still worth
            # trying the name before giving up, in case it's a real but
            # unlisted-in-our-universe ticker paired with a real name.
            pass

    name = (company_name or "").strip().lower()
    if name:
        for co in _NSE_UNIVERSE:
            aliases = (co.get("aliases") or []) + [co["name"].lower(), co["symbol"].lower()]
            for a in aliases:
                if len(a) < 3:
                    continue
                idx = name.find(a)
                if idx == -1:
                    continue
                before_ok = idx == 0 or not name[idx - 1].isalnum()
                after_idx = idx + len(a)
                after_ok = after_idx == len(name) or not name[after_idx].isalnum()
                if before_ok and after_ok:
                    return co["symbol"]

    return None
