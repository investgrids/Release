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

# P0-CD2 Generation Containment (2026-09-01): trailing corporate suffixes,
# stripped before any name comparison. Real regression this closes: the
# universe's own `co["name"]` is always the FULL registered form ("LIC
# Housing Finance Ltd"), but an LLM-given company_name very often omits it
# ("LIC Housing Finance") — the substring check only ever looked for the
# (longer, suffixed) alias WITHIN the (shorter, unsuffixed) input, which
# can never match when the input is shorter than the alias. Confirmed live
# against a real shadow-corpus scan of 174 published articles: LIC Housing
# Finance, HDFC Ltd, Cholamandalam Investment, Godrej Industries, and
# Reliance Industries all incorrectly fell through to None the moment the
# symbol<->name cross-check (added earlier in this same pass) started
# actually exercising the name-matching path for an already-symbol-matched
# company. Stripping the suffix from both sides before comparing fixes the
# length mismatch without weakening the ambiguous-alias protection (an
# exact match after stripping still only wins when it's exact).
_CORP_SUFFIX_RE = re.compile(r"\s+(ltd|limited|pvt|private|inc|incorporated|corp|corporation|co|plc|llc)\.?\s*$", re.IGNORECASE)


def _strip_corp_suffix(s: str) -> str:
    return _CORP_SUFFIX_RE.sub("", s).strip()


def _is_plausible_nse_ticker(candidate: str) -> bool:
    """NSE tickers are short, alphabetic (with occasional & or digits for
    things like M&M, 3M), never purely numeric — a purely numeric string is
    always a BSE scrip code, never a real NSE symbol."""
    if not candidate or candidate.isdigit():
        return False
    return bool(re.fullmatch(r"[A-Z0-9&]{1,20}", candidate.upper()))


def _word_boundary_substring(needle: str, haystack: str) -> bool:
    idx = haystack.find(needle)
    if idx == -1:
        return False
    before_ok = idx == 0 or not haystack[idx - 1].isalnum()
    after_idx = idx + len(needle)
    after_ok = after_idx == len(haystack) or not haystack[after_idx].isalnum()
    return before_ok and after_ok


_ambiguous_aliases_cache: set[str] | None = None


def _ambiguous_aliases(universe: list[dict]) -> set[str]:
    """P0-CD2 Generation Containment (2026-09-01): precomputed, cached set
    of alias/name strings that appear (word-boundary-safe) in MORE THAN ONE
    company's own name/aliases across the whole universe — e.g. "apollo"
    genuinely belongs to Apollo Hospitals (APOLLOHOSP), but also appears as
    a substring inside APL Apollo Tubes' and Apollo Tyres' real names. A
    match on an ambiguous alias alone is a weak signal (confirmed live:
    "Apollo Micro Systems" — a real company NOT in this universe at all —
    used to confidently resolve to Apollo Hospitals purely because "apollo"
    matched), so it's only trusted when it covers the ENTIRE given name,
    not just a leading word of it. Computed once (~500 entries, O(n^2) but
    trivial at this size) and cached — the universe is a static module-level
    list, not something that changes at runtime."""
    global _ambiguous_aliases_cache
    if _ambiguous_aliases_cache is not None:
        return _ambiguous_aliases_cache

    per_company: list[tuple[str, list[str]]] = [
        (co["symbol"], list({*(co.get("aliases") or []), _strip_corp_suffix(co["name"].lower())}))
        for co in universe
    ]
    ambiguous: set[str] = set()
    for i, (sym_a, aliases_a) in enumerate(per_company):
        for j, (sym_b, names_b) in enumerate(per_company):
            if i == j:
                continue
            haystack = " | ".join(names_b)
            for alias in aliases_a:
                if len(alias) >= 3 and _word_boundary_substring(alias, haystack):
                    ambiguous.add(alias)
    _ambiguous_aliases_cache = ambiguous
    return ambiguous


# A single bare word that reads as ordinary English rather than a company
# identifier — the _ambiguous_aliases check only catches a word that
# literally collides with ANOTHER real entry in this specific curated
# ~500-company universe, which "home" doesn't (no other company happens to
# be named with "home" in it), even though it's much too generic a signal
# to trust against an arbitrary company name it doesn't itself belong to.
# Confirmed live via the shadow-corpus scan: "Reliance Home Finance" (a
# real company NOT in this universe) matched Home First Finance purely via
# its bare "home" alias. Deliberately small and specific rather than a
# general dictionary — extend it if the shadow-corpus scan surfaces more.
_GENERIC_SINGLE_WORDS = {"home", "national", "central", "global", "united", "star", "royal", "prime", "city"}


def _alias_matches_name(alias: str, name: str, ambiguous: set[str]) -> bool:
    """Word-boundary-safe substring check. An alias flagged ambiguous (see
    _ambiguous_aliases) is only trusted when it covers the WHOLE given
    name (alias == name after normalization) — a partial/leading-word
    match on a generic, cross-company-shared word isn't a confident
    identification. A non-ambiguous alias is trusted at any length,
    including short unambiguous ones ("tcs", "infosys") that are perfectly
    fine — the risk was never short aliases per se, it was aliases that
    collide with other real companies (or, per _GENERIC_SINGLE_WORDS, read
    as ordinary English rather than a company identifier at all)."""
    if len(alias) < 3:
        return False
    if alias in _GENERIC_SINGLE_WORDS and alias != name:
        return False
    if alias in ambiguous and alias != name:
        return False
    return _word_boundary_substring(alias, name)


def _company_name_matches(co: dict, name: str, ambiguous: set[str]) -> bool:
    if not name:
        return True  # nothing given to cross-check against — not a mismatch
    aliases = (co.get("aliases") or []) + [_strip_corp_suffix(co["name"].lower()), co["symbol"].lower()]
    return any(_alias_matches_name(a, name, ambiguous) for a in aliases)


def normalize_symbol(raw_symbol: str | None, company_name: str | None = None) -> str | None:
    """
    Resolve a possibly-malformed symbol to a canonical NSE ticker from the
    real ~500-company universe (app.api.companies._NSE_UNIVERSE), or None
    if it can't be confidently resolved.

    Resolution order:
      1. Exact symbol match (case-insensitive) against the universe — but
         ONLY when company_name (if given) actually agrees with THAT
         company's own name/aliases. P0-CD2 Generation Containment
         (2026-09-01): this cross-check is new — the real, confirmed
         production bug was a REAL, valid symbol attached to the WRONG
         real company ("Bajaj Finance" paired with BAJAJFINSV, which is
         Bajaj Finserv — a different listed company), which the old
         version trusted unconditionally the moment the symbol matched
         anything in the universe, never checking whether it matched the
         company the LLM actually said it was. A name that disagrees with
         the matched symbol falls through to name-based resolution below,
         since the LLM is far more likely to get a company's real name
         right than to correctly recall its ticker.
      2. Exchange-qualified codes ("BOM:500400"): strip the prefix; if the
         remainder is itself a real ticker (same name cross-check), use
         it; otherwise fall through to name-based resolution using
         company_name (the numeric BSE scrip code alone carries no
         resolvable ticker).
      3. Name-based resolution: company_name matched against each entry's
         real name/aliases using the same word-boundary-safe technique as
         app.services.ai_search.entities._match_companies (reused, not
         reinvented — same lesson as the compute_priority word-boundary
         fix). An alias shared with another real universe entry (see
         _ambiguous_aliases) is only trusted on a full-name match, not a
         partial/leading-word one.
      4. No match → None. Callers must drop the link, not guess.
    """
    from app.api.companies import _NSE_UNIVERSE

    sym = (raw_symbol or "").strip()
    name = _strip_corp_suffix((company_name or "").strip().lower())
    ambiguous = _ambiguous_aliases(_NSE_UNIVERSE)

    if sym:
        upper = sym.upper()
        for co in _NSE_UNIVERSE:
            if co["symbol"].upper() == upper:
                if _company_name_matches(co, name, ambiguous):
                    return co["symbol"]
                break  # real symbol, but for a different company than `name` says

        m = _EXCHANGE_PREFIX_RE.match(sym)
        if m:
            remainder = m.group(2).strip().upper()
            for co in _NSE_UNIVERSE:
                if co["symbol"].upper() == remainder and _company_name_matches(co, name, ambiguous):
                    return co["symbol"]
        elif _is_plausible_nse_ticker(upper):
            # Not exchange-qualified and not in the universe — still worth
            # trying the name before giving up, in case it's a real but
            # unlisted-in-our-universe ticker paired with a real name.
            pass

    if name:
        for co in _NSE_UNIVERSE:
            if _company_name_matches(co, name, ambiguous):
                return co["symbol"]

    return None
