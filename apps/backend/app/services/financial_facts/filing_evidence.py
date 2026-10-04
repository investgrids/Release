"""
Evidence standard for reconciling a filing value to its results PDF (pilot rule, 2026-10-03). Not wired into the scorer.

A value is VERIFIED against the PDF only by one of two kinds of evidence:
  E1  image read   the statement page was rendered at >= MIN_IMAGE_DPI (full page or a clip of it), the printed number was legible, and the
                   page number and render resolution are recorded. Contact sheets and thumbnails are NOT evidence (a thumbnail read of a
                   profit row gave 1,118.88 where the page prints 1,118.94).
  E2  exact text   the filing value equals a number on a labelled row of the correct statement and scope, compared at the PRINTED precision of
                   that number after unit conversion (not a percentage tolerance). The text layer may be OCR (every PDF in the pilot is an image
                   scan with an OCR overlay): an exact match between two independent sources is evidence; a non-match is never evidence of an error.
Everything else (tolerance matches, near matches, thumbnail reads, "not found") is UNVERIFIED, not PASS and not FAIL. FAIL needs a value read at E1
quality that contradicts the filing after reconciling items (scope, associates, netted prior-period items) are applied.
Every record keeps: field, filing value (crore), evidence type, page, dpi or the matched string, scope, and any reconciling item.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

MIN_IMAGE_DPI = 100
UNIT_TO_CRORE = {"crore": 1.0, "lakh": 0.01, "million": 0.1, "thousand": 0.0001, "inr": 1e-7}
_GROUPED = re.compile(r"^\(?-?\d{1,3}( \d{3})+(\.\d+)?\)?$")


def parse_printed_number(raw: str) -> tuple[float, int] | None:
    """(value, number of printed decimals) from a printed string; tolerates Indian grouping ('1,26,000.50') and a stray OCR space inside
    the digit groups ('29 096.38'). Returns None if the string is not a plain number."""
    s = raw.strip()
    neg = s.startswith("(") or s.startswith("-")
    s = s.strip("()-").strip()
    if _GROUPED.match(raw.strip()):
        s = s.replace(" ", "")
    s = s.replace(",", "")
    if not re.fullmatch(r"\d+(\.\d+)?", s):
        return None
    dec = len(s.split(".")[1]) if "." in s else 0
    v = float(s)
    return (-v if neg else v), dec


def exact_at_printed_precision(printed: str, unit: str, filing_value_cr: float) -> bool:
    """True when |printed x unit| equals |filing value| to within half a unit of the printed last digit (converted to crore).
    Pass the RAW filed value (unrounded, from the XBRL), not a value already rounded to 0.01 crore."""
    p = parse_printed_number(printed)
    if p is None or unit not in UNIT_TO_CRORE:
        return False
    v, dec = p
    half_unit = 0.5 * (10 ** -dec) * UNIT_TO_CRORE[unit]
    return abs(abs(v) * UNIT_TO_CRORE[unit] - abs(filing_value_cr)) <= half_unit + 1e-9


@dataclass
class Evidence:
    field: str
    filing_value_cr: float
    kind: str                 # "image" | "exact_text" | "thumbnail" | "tolerance_text" | "none"
    page: int | None = None
    dpi: int | None = None
    matched: str | None = None
    scope: str | None = None
    reconciling_item: str | None = None


def status(e: Evidence) -> str:
    """VERIFIED only for E1 (>= MIN_IMAGE_DPI) or E2; otherwise UNVERIFIED. Never PASS from a thumbnail or a tolerance match."""
    if e.kind == "image" and e.page is not None and (e.dpi or 0) >= MIN_IMAGE_DPI:
        return "VERIFIED"
    if e.kind == "exact_text" and e.page is not None and e.matched:
        return "VERIFIED"
    return "UNVERIFIED"
