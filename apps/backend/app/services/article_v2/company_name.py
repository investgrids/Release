"""
Article V2 — shared company-name resolution (C6.1 hardening, owner
review 2026-09-01). One deterministic implementation, now reused by
both `headline_engine.py` and `composer.py` -- the two real bugs found
during C6's shadow-run manual inspection (SUPREMEENG, NAZARA) both
traced to each module keeping its OWN copy of the same regex, which had
already started to drift: `composer.py`'s copy only ever matched "has
informed"/"has submitted to"; NAZARA's real filing uses present-tense
"informs the Exchange", which neither copy handled, so extraction
silently fell back to the bare symbol in one module while the LLM (in
the other) got the real name right on its own -- a visible headline/
body inconsistency in one composed article. Fixing it once, here,
closes both bugs and removes the drift risk going forward.

Priority order, per owner instruction:
  1. The real, resolver-verified canonical company name already
     resolved upstream (`ArticleEvidenceSet.company_name`, threaded
     through from `company_identity`'s own canonical resolver via
     `build_article_evidence_bundle` -- the SAME real name C1-C5
     already trust throughout this pipeline) -- never re-derived, never
     re-guessed from prose when this is available.
  2. Only when that's unavailable: extract from the primary evidence's
     own text, but validated -- a garbled real-world filing header like
     "SUPREMEENG : 31-Aug-2026 : The Company has informed the
     Exchange..." must not be accepted as a company name just because
     it happens to precede the boilerplate phrase.
  3. Only when neither tier produced a trustworthy name: the bare
     symbol -- always correct, if less specific than a real name.

No fuzzy inference anywhere in this chain -- each tier is either a
real, already-verified value or a validated regex match, never a guess.
"""
from __future__ import annotations

import re

# Matches both real phrasings seen in production NSE filing text:
# "X has informed the Exchange..." and "X informs the Exchange..."
# (present tense, no "has" -- NAZARA's real shape).
_BOILERPLATE_RE = re.compile(
    r"^(.*?)\s+(?:has (?:informed|submitted to)|informs)\s+(?:the exchange|bse|nse)",
    re.IGNORECASE,
)

# A real, garbled filing-header shape found live (SUPREMEENG): the
# "name" candidate itself contains a colon-separated date/label prefix
# ("SUPREMEENG : 31-Aug-2026 : The Company") rather than an actual
# company name. Reject outright rather than trying to further parse it.
_GARBLED_MARKERS_RE = re.compile(r"[:;]|\bthe company\b", re.IGNORECASE)
_MAX_PLAUSIBLE_NAME_LENGTH = 80


def _is_plausible_company_name(candidate: str) -> bool:
    if not candidate:
        return False
    if len(candidate) > _MAX_PLAUSIBLE_NAME_LENGTH:
        return False
    if _GARBLED_MARKERS_RE.search(candidate):
        return False
    return True


def resolve_company_name(
    *, verified_company_name: str | None, primary_evidence_title: str | None, symbol: str | None,
) -> str:
    """The one shared entry point for both headline_engine.py and
    composer.py. `verified_company_name` should be
    ArticleEvidenceSet.company_name when the caller has it -- always
    preferred over prose extraction. Falls back to a validated
    extraction from the primary evidence's own title, then to the bare
    symbol. Always returns a real, non-empty string."""
    if verified_company_name:
        return verified_company_name

    if primary_evidence_title:
        m = _BOILERPLATE_RE.match(primary_evidence_title)
        if m:
            candidate = m.group(1).strip().rstrip(",")
            if _is_plausible_company_name(candidate):
                return candidate

    return symbol or "The company"
