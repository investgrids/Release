"""
Claim-level evidence references + fail-closed validation for AEV2
(Build 1, 2026-09-21; hardened in review, 2026-09-21 second pass).

Every AEV2 text field (direct_conclusion, what_happened, why_it_matters)
carries `evidence_refs` — NOT the whole evidence[] catalog attached
blindly, but the output of `deterministic_claim_evidence_refs()` below,
the one real deterministic relationship this codebase has today: an
event's own structured `companies` field (set at ingestion) naming one
of CoreAnswer's own resolved companies. This mirrors pipeline.py's
`_filter_events_to_entities` matching rule exactly (duplicated here,
not imported — aev2/ must not import from ai_search.pipeline; see the
package-wide import-scan test). News/policy rows carry no company field
today (the same known gap _filter_events_to_entities's own docstring
names), so they are never attributed to a specific claim here — they
still appear in the full evidence[] catalog for transparency, just
uncited by any field, which is the honest state of what this codebase
can actually prove today, not an invented link. If zero companies
resolved, or none of the retrieved events are company-linked,
evidence_refs is genuinely empty — not padded with unrelated catalog
entries to look more complete than it is.

A field's generated text is only used if it passes ALL of:

  1. every evidence_ref it cites actually exists in the catalog
  2. every number in its text is backed by matching text somewhere in
     the SPECIFIC evidence it cites (not the whole catalog, and not
     some other source elsewhere in the response) — see
     numbers_supported
  3. every company-like token in its text is either one of CoreAnswer's
     own resolved companies (by symbol or a word from its name) OR
     appears literally in the cited evidence text itself — see
     entities_supported

Any failure removes the claim (assemble.py falls back to that field's
honest empty/fallback shape) — this module never repairs, rewrites, or
partially trusts a claim; it only says yes or no.

Review correction (2026-09-21, second pass): the first draft had two
real gaps, both fixed here:
  - entities_supported returned a VACUOUS PASS when zero companies had
    resolved — exactly the situation where an unsupported company claim
    is riskiest (nothing was ever verified, so anything the specialist
    names is unearned). It is no longer vacuous: with nothing resolved,
    an all-caps company-like token must still appear in the cited
    evidence text itself to pass, or the claim fails.
  - _KNOWN_ACRONYMS was a blanket global trust list (RBI, GDP, IPO...)
    applied regardless of context. Removed entirely. An acronym-shaped
    token now passes only when it is one of CoreAnswer's own resolved
    companies, OR it appears literally in the evidence text actually
    cited for that claim — never on the strength of being a "well-known"
    word alone.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.services.ai_search.core_answer import CoreAnswer

_NUMBER_RE = re.compile(r"\d{1,3}(?:,\d{2,3})+(?:\.\d+)?|\d+\.\d+|\d{2,}")
_SYMBOL_TOKEN_RE = re.compile(r"\b[A-Z]{3,10}\b")


def build_evidence_catalog(core: CoreAnswer) -> list[dict]:
    """One entry per real event/news/policy row already sitting in
    CoreAnswer — pure re-formatting, zero new retrieval. Titles are
    immutable source text (already validated upstream by
    validation.py's own checks) and are never scanned by the language
    gate or altered here. This is the full, transparent catalog shown
    in the response's evidence[] field — NOT what any single claim's
    evidence_refs is limited to; see deterministic_claim_evidence_refs
    for that narrower, per-claim relationship."""
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


def _event_company_symbols(event: dict) -> set[str]:
    return {
        (c.get("symbol") or "").upper()
        for c in (event.get("companies") or [])
        if isinstance(c, dict) and c.get("symbol")
    }


def deterministic_claim_evidence_refs(core: CoreAnswer) -> list[str]:
    """The genuinely deterministic evidence<->claim relationship: an
    event whose own structured `companies` field names one of
    CoreAnswer's resolved companies. Never positional (first-N events),
    never "attach everything", never text-similarity-based — a real
    ingestion-time field match or nothing. Returns [] when core.companies
    is empty or no retrieved event is company-linked; an empty result is
    the honest answer in that case, not a fallback to attaching
    unrelated evidence."""
    wanted = {(c.get("symbol") or "").upper() for c in core.companies if c.get("symbol")}
    if not wanted:
        return []
    refs = []
    for e in core.related_events:
        eid = e.get("id")
        if eid is None:
            continue
        if _event_company_symbols(e) & wanted:
            refs.append(f"event:{eid}")
    return refs


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
    stripping thousands separators, somewhere in `supporting_text` — the
    concatenated titles of ONLY the evidence this specific claim cites
    (deterministic_claim_evidence_refs's output), never the whole
    catalog and never a different field's own evidence. A number that is
    real but sits in some OTHER, uncited source is still unsupported for
    THIS claim — fail-closed, not "it's true somewhere.\""""
    normalized_support = _normalize_numbers(supporting_text)
    return all(num in normalized_support for num in extract_numbers(text))


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


def entities_supported(
    text: str, recognized_symbols: set[str], name_tokens: set[str] | None, supporting_text: str,
) -> bool:
    """Any bare all-caps token that looks like a stock symbol or
    acronym must be traceable to something concrete: one of CoreAnswer's
    own resolved companies (by symbol or a word from its name), OR
    literal presence in the evidence text actually cited for this claim.
    There is NO third path — no global "well-known acronym" allowlist,
    and NO vacuous pass when nothing resolved. A query that resolved
    zero companies is exactly where an unsupported company mention is
    riskiest, so it gets the strictest check, not a skip: every
    candidate token must appear in the cited evidence text itself."""
    if not text:
        return True
    name_tokens = name_tokens or set()
    supporting_upper = (supporting_text or "").upper()
    for token in _SYMBOL_TOKEN_RE.findall(text):
        if token in recognized_symbols or token in name_tokens:
            continue
        if token in supporting_upper:
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
    `supporting_text` must be the concatenated titles of exactly
    `evidence_refs` (deterministic_claim_evidence_refs's output for this
    claim) — never the whole catalog, never a blanket attachment."""
    reasons: list[str] = []
    for ref in evidence_refs:
        if ref not in catalog_ids:
            reasons.append("invalid_evidence_ref")
            break
    if not numbers_supported(text, supporting_text):
        reasons.append("unsupported_number")
    if not entities_supported(text, recognized_symbols, name_tokens, supporting_text):
        reasons.append("unsupported_entity")
    return ClaimValidation(valid=not reasons, reasons=reasons)
