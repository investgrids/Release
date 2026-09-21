"""
Claim-level evidence references + fail-closed validation for AEV2
(Build 1, 2026-09-21).

Every AEV2 text field (direct_conclusion, what_happened, why_it_matters)
carries `evidence_refs` pointing into one shared `evidence[]` catalog
built once per response from CoreAnswer's already-retrieved
related_events/news/policies — never a new retrieval, never a new
provider call. A field's generated text is only used if it passes ALL of:

  1. every evidence_ref it cites actually exists in the catalog
  2. every number in its text is backed by matching text somewhere in
     the evidence it cites (see numbers_supported)
  3. every company-like token in its text is one CoreAnswer already
     resolved/validated (see entities_supported) — not a name the
     specialist introduced that was never actually evidenced

Any failure removes the claim (assemble.py falls back to that field's
honest empty/fallback shape) — this module never repairs, rewrites, or
partially trusts a claim; it only says yes or no.

Deliberately conservative on (3): financial text is full of legitimate
all-caps acronyms (RBI, GDP, IPO...) that are not company symbols and
must not be flagged as unsupported entities. _KNOWN_ACRONYMS is a
curated allowlist, not an attempt at real NER — this is Build 1's
heuristic, expected to be extended as real false positives are found in
review, not a claim of completeness.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.services.ai_search.core_answer import CoreAnswer

_NUMBER_RE = re.compile(r"\d{1,3}(?:,\d{2,3})+(?:\.\d+)?|\d+\.\d+|\d{2,}")

_KNOWN_ACRONYMS = {
    "RBI", "SEBI", "NSE", "BSE", "GDP", "GST", "IPO", "FII", "DII", "CPI", "WPI",
    "EPS", "YOY", "QOQ", "ROE", "ROCE", "EBITDA", "PE", "PB", "IT", "US", "UK", "EU",
    "FY", "H1", "H2", "Q1", "Q2", "Q3", "Q4", "CEO", "CFO", "COO", "MD", "PSU",
    "NBFC", "AUM", "NPA", "CAGR", "FDI", "FPI", "RTC", "PPA", "MW", "GW", "KWH",
    "USD", "INR", "IT", "PSU", "MSME", "GDPR", "SOP", "AGM", "EGM", "SME",
}


def build_evidence_catalog(core: CoreAnswer) -> list[dict]:
    """One entry per real event/news/policy row already sitting in
    CoreAnswer — pure re-formatting, zero new retrieval. Titles are
    immutable source text (already validated upstream by
    validation.py's own checks) and are never scanned by the language
    gate or altered here."""
    catalog: list[dict] = []
    for e in core.related_events:
        eid = e.get("id")
        if eid is None:
            continue
        catalog.append({
            "id": f"event:{eid}",
            "type": "event",
            "title": e.get("title") or "",
            "date": e.get("date") or e.get("event_date") or None,
        })
    for n in core.news:
        nid = n.get("id")
        if nid is None:
            continue
        catalog.append({
            "id": f"news:{nid}",
            "type": "news",
            "title": n.get("title") or n.get("headline") or "",
            "date": n.get("date") or n.get("published_at") or None,
        })
    for p in core.policies:
        pid = p.get("id")
        if pid is None:
            continue
        catalog.append({
            "id": f"policy:{pid}",
            "type": "policy",
            "title": p.get("title") or "",
            "date": p.get("date") or None,
        })
    return catalog


def _normalize_numbers(text: str) -> str:
    return (text or "").replace(",", "")


def extract_numbers(text: str) -> list[str]:
    """Numbers with 2+ digits only — deliberately skips bare single
    digits (too common as structural/ordinal noise: "1 of 3 risks") to
    keep this check focused on figures that actually carry a factual
    claim (prices, percentages, capacities, amounts)."""
    if not text:
        return []
    return [_normalize_numbers(m) for m in _NUMBER_RE.findall(text)]


def numbers_supported(text: str, supporting_text: str) -> bool:
    """Every number in `text` must appear, digit-for-digit after
    stripping thousands separators, somewhere in `supporting_text`
    (the concatenated titles of the evidence this field actually
    cites). A number with no match is treated as unsupported —
    fail-closed, not "probably fine."""
    normalized_support = _normalize_numbers(supporting_text)
    return all(num in normalized_support for num in extract_numbers(text))


_SYMBOL_TOKEN_RE = re.compile(r"\b[A-Z]{3,10}\b")


def recognized_name_tokens(companies: tuple[dict, ...]) -> set[str]:
    """Individual words (3+ letters, uppercased) from each resolved
    company's own `name` — a company's trading symbol and its common
    name-shorthand often differ ("HDFC Bank" vs symbol "HDFCBANK"; "Tata
    Motors" vs "TATAMOTORS"), so checking against symbols alone would
    flag a company's own genuine name as an unsupported entity. Generic
    words this pulls in ("BANK", "LTD", "MOTORS") are an accepted
    precision trade-off — see module docstring."""
    tokens: set[str] = set()
    for c in companies:
        name = c.get("name") or ""
        for word in re.findall(r"[A-Za-z]+", name):
            if len(word) >= 3:
                tokens.add(word.upper())
    return tokens


def entities_supported(text: str, recognized_symbols: set[str], name_tokens: set[str] | None = None) -> bool:
    """Any bare all-caps token that looks like a stock symbol but is
    neither a known non-company acronym nor traceable to one of
    CoreAnswer's own resolved companies (by symbol or by a word from its
    name) is treated as an entity the specialist introduced without
    evidence. See module docstring for why this is deliberately
    conservative (allowlist, not real NER).

    Vacuous pass when NEITHER recognized_symbols nor name_tokens has
    anything in it (e.g. a macro/sector query that resolved zero
    companies) — there is nothing concrete to compare against, so this
    check is skipped rather than rejecting every all-caps token in the
    text; numbers_supported and evidence_ref validity still apply."""
    if not text:
        return True
    name_tokens = name_tokens or set()
    if not recognized_symbols and not name_tokens:
        return True
    for token in _SYMBOL_TOKEN_RE.findall(text):
        if token in _KNOWN_ACRONYMS:
            continue
        if token in recognized_symbols or token in name_tokens:
            continue
        return False
    return True


@dataclass
class ClaimValidation:
    valid: bool
    reasons: list[str] = field(default_factory=list)


def validate_claim(
    text: str,
    evidence_refs: list[str],
    catalog_ids: set[str],
    recognized_symbols: set[str],
    supporting_text: str,
    name_tokens: set[str] | None = None,
) -> ClaimValidation:
    """The one entry point assemble.py calls for every candidate field.
    `supporting_text` is the concatenated titles of exactly the evidence
    items `evidence_refs` names (not the whole catalog) — a number is
    only "supported" by the evidence actually cited for THIS claim, not
    by evidence backing some other field in the same response."""
    reasons: list[str] = []
    for ref in evidence_refs:
        if ref not in catalog_ids:
            reasons.append("invalid_evidence_ref")
            break
    if not numbers_supported(text, supporting_text):
        reasons.append("unsupported_number")
    if not entities_supported(text, recognized_symbols, name_tokens):
        reasons.append("unsupported_entity")
    return ClaimValidation(valid=not reasons, reasons=reasons)
