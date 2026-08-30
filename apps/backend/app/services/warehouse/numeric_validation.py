"""
Numeric-claim validation — AI Article V2 Phase B (owner decision,
2026-08-30): every number "Why It Matters" asserts must trace to a real
number present in the evidence/financial bundle it was given, or the
generation fails validation and gets omitted (never published
unsupported). This module never trusts the LLM's own claim about which
numbers it used — the owner's explicit instruction was that validation
must operate on the ACTUAL GENERATED TEXT. It independently re-extracts
every numeric token from that text and checks each one against a real
"allowed" set built from the same bundle the model was given.

Scope, stated plainly (mirrors fact_grounding.py's own scoping
discipline): this handles the numeric forms actually seen in this app's
real evidence/financial data — percentages, ₹/Rs/INR figures (with
crore/lakh multipliers), $/USD figures (with billion/million
multipliers), and simple ratios ("1.4x") — plus a lighter, separate
check for stated fiscal periods (FY2025, Q3 FY2025). It does not attempt
full natural-language number parsing (spelled-out numbers, exotic
compound units) — those don't appear in this app's real content today.

Formatting-equivalence, not permission to invent: ₹1,410 crore and
Rs 1,410 crore normalize to the same comparison value. A number that
merely differs from a real fact by more than rounding — e.g. an LLM
"converting" ₹ to $ at a guessed exchange rate — is a genuinely NEW
number the bundle never supplied, and correctly fails this check.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# ── Extraction ────────────────────────────────────────────────────────────

_PCT_RE = re.compile(r"[-+]?\d[\d,]*\.?\d*\s*%")
_RATIO_RE = re.compile(r"\b\d+\.\d+\s*[xX]\b")
_CURRENCY_RE = re.compile(
    r"(?:(?P<symbol>₹|Rs\.?|INR|\$|USD)\s*(?P<num1>\d[\d,]*\.?\d*)"
    r"(?:\s*(?P<mult1>crore|lakh|lac|billion|bn|million|mn|thousand|k\b))?)"
    r"|(?:(?P<num2>\d[\d,]*\.?\d*)\s*(?P<mult2>crore|lakh|lac|billion|bn|million|mn|thousand))",
    re.IGNORECASE,
)
_MULTIPLIERS = {
    "crore": 1e7, "lakh": 1e5, "lac": 1e5,
    "billion": 1e9, "bn": 1e9,
    "million": 1e6, "mn": 1e6,
    "thousand": 1e3, "k": 1e3,
}
_INR_WORDS = {"₹", "RS", "RS.", "INR"}
_INR_ONLY_MULTIPLIERS = {"crore", "lakh", "lac"}  # unambiguous Indian-convention words, even with no symbol


@dataclass(frozen=True)
class ExtractedNumber:
    raw_text: str
    value: float
    kind: str  # "percent" | "currency_inr" | "currency_usd" | "currency_generic" | "ratio"
    span: tuple[int, int]


def extract_numeric_claims(text: str) -> list[ExtractedNumber]:
    """Real, deterministic extraction — no LLM involved. Order matters:
    percent and ratio patterns are more specific and claimed first so a
    currency regex never re-consumes part of an already-matched span."""
    if not text:
        return []
    found: list[ExtractedNumber] = []
    claimed: list[tuple[int, int]] = []

    def _overlaps(span: tuple[int, int]) -> bool:
        return any(span[0] < c[1] and span[1] > c[0] for c in claimed)

    for m in _PCT_RE.finditer(text):
        if _overlaps(m.span()):
            continue
        try:
            val = float(m.group().replace("%", "").replace(",", "").strip())
        except ValueError:
            continue
        found.append(ExtractedNumber(m.group(), val, "percent", m.span()))
        claimed.append(m.span())

    for m in _RATIO_RE.finditer(text):
        if _overlaps(m.span()):
            continue
        try:
            val = float(re.sub(r"[xX\s]", "", m.group()))
        except ValueError:
            continue
        found.append(ExtractedNumber(m.group(), val, "ratio", m.span()))
        claimed.append(m.span())

    for m in _CURRENCY_RE.finditer(text):
        if _overlaps(m.span()):
            continue
        symbol = m.group("symbol")
        if symbol:
            num_str, mult_str = m.group("num1"), m.group("mult1")
            kind = "currency_inr" if symbol.upper().rstrip(".") in {"₹", "RS", "INR"} else "currency_usd"
        else:
            num_str, mult_str = m.group("num2"), m.group("mult2")
            if not mult_str:
                continue
            kind = "currency_inr" if mult_str.lower() in _INR_ONLY_MULTIPLIERS else "currency_generic"
        try:
            val = float(num_str.replace(",", ""))
        except ValueError:
            continue
        if mult_str:
            val *= _MULTIPLIERS[mult_str.lower()]
        found.append(ExtractedNumber(m.group().strip(), val, kind, m.span()))
        claimed.append(m.span())

    found.sort(key=lambda e: e.span[0])
    return found


_PERIOD_RE = re.compile(r"\bFY\s?-?\s?(\d{2,4})(?:\s*[- ]?\s*Q(\d))?\b", re.IGNORECASE)


def extract_period_claims(text: str) -> list[tuple[int, int | None]]:
    """Lighter, separate check for stated fiscal periods (e.g. 'FY2025 Q3',
    'FY25') — real but not folded into numeric-value matching, since
    attributing a period to a specific nearby number reliably would need
    real NLP the rest of this module deliberately avoids."""
    if not text:
        return []
    out: list[tuple[int, int | None]] = []
    for m in _PERIOD_RE.finditer(text):
        year = int(m.group(1))
        if year < 100:
            year += 2000
        quarter = int(m.group(2)) if m.group(2) else None
        out.append((year, quarter))
    return out


# ── Allowed-value set ────────────────────────────────────────────────────

@dataclass(frozen=True)
class AllowedValue:
    value: float
    kind: str
    tolerance: float
    source: str  # human-readable provenance for observability, e.g. "FinancialFact:roa"


def _pct_allowed(fraction_value: float, source: str) -> list[AllowedValue]:
    """Metrics with unit='pct' in this app are stored as a 0-1 fraction
    (confirmed against quality.py's own plausibility ranges, e.g.
    roa in (-0.10, 0.10)) — the real, expected prose form multiplies by
    100, so that's the only representation offered here."""
    return [AllowedValue(value=fraction_value * 100, kind="percent", tolerance=0.05, source=source)]


def _inr_allowed(rupees: float, source: str) -> list[AllowedValue]:
    # Raw rupees -- matching extract_numeric_claims's own convention: a
    # "crore"/"lakh" suffix in text is multiplied BACK UP to raw rupees at
    # extraction time (e.g. "Rs 1,410 crore" -> 1.41e10), so the allowed
    # value must live in that same raw-rupee space, not a crore-divided
    # one, or every real crore-phrased figure would silently mismatch.
    tol = max(abs(rupees) * 0.015, 1e5)
    return [AllowedValue(value=rupees, kind="currency_inr", tolerance=tol, source=source)]


def build_allowed_values(bundle, evidence_used: list) -> list[AllowedValue]:
    """The one real allowed-value set 'Why It Matters' output is checked
    against — built entirely from the SAME bundle contents the model was
    given, never from anything the model claims about itself."""
    allowed: list[AllowedValue] = []

    for e in evidence_used:
        if not getattr(e, "title", None):
            continue
        for num in extract_numeric_claims(e.title):
            tol = max(abs(num.value) * 0.02, 0.01)
            allowed.append(AllowedValue(value=num.value, kind=num.kind, tolerance=tol, source=f"evidence:{e.raw_evidence_id}"))

    if getattr(bundle, "price_move_pct", None) is not None:
        pm = bundle.price_move_pct
        allowed.append(AllowedValue(value=pm, kind="percent", tolerance=0.05, source="price_move"))
        allowed.append(AllowedValue(value=abs(pm), kind="percent", tolerance=0.05, source="price_move"))

    fc = getattr(bundle, "financial_context", None)
    if fc and fc.has_real_facts:
        for f in fc.facts:
            src = f"FinancialFact:{f.metric_code}"
            if f.unit == "pct":
                allowed += _pct_allowed(f.value, src)
            elif f.unit == "inr":
                allowed += _inr_allowed(f.value, src)
            else:
                allowed.append(AllowedValue(value=f.value, kind="ratio", tolerance=max(abs(f.value) * 0.02, 0.01), source=src))

    return allowed


_CURRENCY_KINDS = {"currency_inr", "currency_usd", "currency_generic"}


def _kind_compatible(extracted_kind: str, allowed_kind: str) -> bool:
    if extracted_kind == allowed_kind:
        return True
    return extracted_kind in _CURRENCY_KINDS and allowed_kind in _CURRENCY_KINDS


def validate_numeric_claims(text: str, allowed: list[AllowedValue]) -> tuple[bool, list[dict]]:
    """Required gate, same severity discipline as fact_grounding.py's
    validate_fact_grounding — returns (passed, errors), never raises."""
    unsupported: list[dict] = []
    for num in extract_numeric_claims(text):
        if any(_kind_compatible(num.kind, a.kind) and abs(num.value - a.value) <= a.tolerance for a in allowed):
            continue
        unsupported.append({"raw_text": num.raw_text, "value": num.value, "kind": num.kind})
    return len(unsupported) == 0, unsupported


def validate_period_claims(text: str, financial_context, evidence_used: list) -> tuple[bool, list[dict]]:
    allowed_years: set[int] = set()
    if financial_context and financial_context.has_real_facts:
        allowed_years.update(f.fiscal_year for f in financial_context.facts)
    for e in evidence_used:
        published_at = getattr(e, "published_at", None)
        if published_at is not None:
            allowed_years.add(published_at.year)

    unsupported = [
        {"fiscal_year": year, "fiscal_quarter": quarter}
        for year, quarter in extract_period_claims(text)
        if year not in allowed_years
    ]
    return len(unsupported) == 0, unsupported
