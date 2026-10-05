"""
Unsupported figures and dates in generated public text.

The claim-source validator covers the answer's main prose. The live CR2 failure (Step 3.3b) put invented earnings-release dates in `timeline` and invented growth/margin figures in
`scenarios`, fields that validator does not read. This module checks EVERY string a user can read (timeline, scenarios, insights, drivers, monitoring, ...) for two things the evidence must
contain for them to be shown as fact:

  * dates:   a full date ("2026-11-10", "10 Nov 2026", "Nov 10, 2026") must appear in the evidence (an item's date or text) or be today's date
  * numbers: a number with two or more digits, a decimal or a percent sign must appear in the evidence or the question

Exempt by design: years, fiscal labels (FY27, Q2), horizon phrases ("6-12 months"), single digits, and structured numeric fields (confidence, probabilities, scores), because only STRINGS are read.
Pure functions, no I/O.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timezone

_MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
_ISO = re.compile(r"(?<!\d)(20\d{2})-(\d{2})-(\d{2})(?!\d)")
_DMY = re.compile(r"(?<!\d)(\d{1,2})(?:st|nd|rd|th)?\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?,?\s+(20\d{2})(?!\d)", re.IGNORECASE)
_MDY = re.compile(r"(?<![a-z])(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(20\d{2})(?!\d)", re.IGNORECASE)
_NUM = re.compile(r"(?<![\w.])[-+]?\d[\d,]*\.?\d*%?")
_HORIZON = re.compile(r"\d+\s*(?:-|to|–)\s*\d+\s*(?:months?|years?|quarters?|weeks?|days?|yrs?)|\d+\s*(?:months?|years?|quarters?|weeks?|days?|yrs?)", re.IGNORECASE)
# Step 3.4B.1: a number is supported only by a COMPLETE numeric token with the same canonical value ("18" is never supported by "2,180", "118", "180" or "18.5"); no fuzzy matching.
# Evidence tokens keep an explicit leading sign ("Banking -0.4%", "+1.3%"). A hyphen glued to a digit ("681.9-1020.5", "FY26-27") is a range, not a sign: the lookbehind makes that token unsigned.
_EVNUM = re.compile(r"(?<![\d.,])[-+]?\d[\d,]*(?:\.\d+)?")
_UNITS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
          "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19}
_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}
_NUMWORD = "|".join(sorted(list(_UNITS) + list(_TENS) + ["hundred"], key=len, reverse=True))
# Bounded: only "<number words> percent / per cent" (1-99 and "one hundred"); other word forms (basis points, fractions, "one hundred and seventy-three point four") are NOT parsed.
_WORD_PCT = re.compile(r"(?<![a-z])((?:one\s+)?hundred|(?:" + "|".join(_TENS) + r")(?:[-\s](?:" + "|".join(list(_UNITS)[:9]) + r"))?|" + "|".join(_UNITS) + r")\s+(?:percent|per\s*cent)(?![a-z])", re.IGNORECASE)
# Fiscal / period labels are descriptors of a reporting window, not figures: FY26, FY2026, FY26-27, FY26/27, Q1-Q4 (with or without FY: Q2, Q2 FY27, Q2FY27, Q2'27), 1Q-4Q (1Q26), H1/H2 (with or without FY).
# Single source of truth: the figure validator scrubs them from numeric checks, and claim_sources.is_factual strips them inside evidence-limitation clauses (Step 3.4G.4).
FISCAL_LABEL_PATTERN = (r"(?<![A-Za-z0-9])(?:FY\s?\d{2,4}(?:\s?[-\u2013/]\s?\d{2,4})?|Q[1-4](?:\s?['\u2019]?\s?(?:FY)?\s?\d{2,4})?|[1-4]Q(?:\s?(?:FY)?\s?\d{2,4})?|H[12](?:\s?(?:FY)?\s?\d{2,4})?)(?![A-Za-z0-9])")
_FISCAL = re.compile(FISCAL_LABEL_PATTERN, re.IGNORECASE)

# Top-level keys of the flat specialist output whose STRINGS a user can read.
_TEXT_KEYS = ("summary", "bottom_line", "what_happened", "why_it_happened", "immediate_impact", "medium_term", "long_term", "what_priced_in", "key_drivers", "risks", "opportunities",
              "companies", "sectors", "insights", "timeline", "scenarios", "monitoring", "timeline_intelligence", "ai_conclusion", "decision_engine_v2", "what_to_monitor", "decision_intelligence")


def find_dates(text: str) -> set[date]:
    out: set[date] = set()
    for y, m, d in _ISO.findall(text or ""):
        try:
            out.add(date(int(y), int(m), int(d)))
        except ValueError:
            pass
    for d, mon, y in _DMY.findall(text or ""):
        try:
            out.add(date(int(y), _MONTHS[mon[:3].lower()], int(d)))
        except (ValueError, KeyError):
            pass
    for mon, d, y in _MDY.findall(text or ""):
        try:
            out.add(date(int(y), _MONTHS[mon[:3].lower()], int(d)))
        except (ValueError, KeyError):
            pass
    return out


def _strip_dates(text: str) -> str:
    for pat in (_ISO, _DMY, _MDY):
        text = pat.sub(" ", text or "")
    return text


def _leaves(node, path: str = "") -> list[tuple[str, str]]:
    """Every string leaf under `node` with a readable path. Numbers are skipped on purpose (confidence, probability and score fields are not prose)."""
    if isinstance(node, str):
        return [(path, node)] if node.strip() else []
    if isinstance(node, dict):
        out: list[tuple[str, str]] = []
        for k, v in node.items():
            out += _leaves(v, f"{path}.{k}" if path else str(k))
        return out
    if isinstance(node, list):
        out = []
        for i, v in enumerate(node):
            out += _leaves(v, f"{path}[{i}]")
        return out
    return []


def public_strings(ai: dict) -> list[tuple[str, str]]:
    """(path, text) for every readable string in the generated answer. Accepts the flat specialist output or the assembled response (answer fields live under `answer`)."""
    out: list[tuple[str, str]] = []
    answer = ai.get("answer") if isinstance(ai.get("answer"), dict) else {}
    for k in _TEXT_KEYS:
        v = ai.get(k) if ai.get(k) not in (None, "", [], {}) else answer.get(k)
        if v in (None, "", [], {}):
            continue
        if k == "companies" and isinstance(v, list):
            v = [{"reason": c.get("reason"), "why_it_matters": c.get("why_it_matters")} for c in v if isinstance(c, dict)]
        out += _leaves(v, k)
    return out


def _word_value(words: str) -> int | None:
    parts = [w for w in re.split(r"[-\s]+", words.lower().strip()) if w]
    low = " ".join(parts)
    if low in ("hundred", "one hundred"):
        return 100
    total = 0
    for w in parts:
        if w in _TENS:
            total += _TENS[w]
        elif w in _UNITS:
            total += _UNITS[w]
        else:
            return None
    return total or None


def word_percents_to_digits(text: str) -> str:
    """'eighteen percent' / 'eighteen per cent' -> '18%'. Anything else written in words is left untouched (documented limitation, not parsed)."""
    def sub(m):
        v = _word_value(m.group(1))
        return f" {v}% " if v is not None else m.group(0)
    return _WORD_PCT.sub(sub, text or "")


def canonical_number(tok: str) -> str:
    """Comma-free, percent/trailing-dot-free, trailing decimal zeros removed, explicit sign kept: '1,200.50' -> '1200.5', '12.0%' -> '12', '-0.40%' -> '-0.4'."""
    n = tok.replace(",", "").rstrip(".").rstrip("%")
    if n.startswith("+"):
        n = n[1:]
    if "." in n:
        n = n.rstrip("0").rstrip(".")
    return n


def split_sign(canonical: str) -> tuple[str, str]:
    return ("-", canonical[1:]) if canonical.startswith("-") else ("", canonical)


def signed_supported(answer_canonical: str, evidence_tokens: list[str], answer_plus: bool = False) -> bool:
    """Step 3.4G.1. Is this figure grounded, with its direction?
      * An unsigned answer figure needs the magnitude somewhere in the evidence (the direction is then carried by words).
      * A negative answer figure is supported by the same negative figure, or by the magnitude appearing UNSIGNED in the evidence (the upstream text lost its sign: 'fell 0.4%').
        It is NOT supported when the evidence gives that magnitude only as an explicitly positive figure.
      * A positive answer figure is supported by the magnitude unsigned or explicitly positive, and NOT when the evidence gives it only as an explicitly negative figure.
    An explicit opposite sign in the evidence never validates the opposite signed claim."""
    sign, mag = split_sign(answer_canonical)
    ev = [(split_sign(canonical_number(t)), t) for t in evidence_tokens]
    same_mag = [s for (s, m), _t in ev if m == mag]
    if not same_mag:
        return False
    if not sign and not answer_plus:
        return True            # magnitude only
    explicit_neg = any(s == "-" for s in same_mag)
    explicit_pos = any(t.strip().startswith("+") for (s, m), t in ev if m == mag)
    unsigned = any((s == "" and not t.strip().startswith("+")) for (s, m), t in ev if m == mag)
    if sign == "-":
        return explicit_neg or unsigned
    return explicit_pos or unsigned


def unsupported_figures(ai: dict, evidence_text: str, query: str, today: date | None = None) -> list[dict]:
    """Figures and dates in the generated public text that neither the evidence nor the question contains. Each result: {kind, value, path, text}."""
    today = today or datetime.now(timezone.utc).date()
    ev_dates = find_dates(evidence_text) | find_dates(query) | {today}
    ev_clean = word_percents_to_digits(_strip_dates(evidence_text + " " + query))
    hay_tokens = _EVNUM.findall(ev_clean)
    flagged: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for path, text in public_strings(ai):
        for d in find_dates(text):
            if d not in ev_dates and ("date", d.isoformat()) not in seen:
                seen.add(("date", d.isoformat()))
                flagged.append({"kind": "date", "value": d.isoformat(), "path": path, "text": text[:160]})
        scrub = _FISCAL.sub(" ", _HORIZON.sub(" ", word_percents_to_digits(_strip_dates(text))))
        for tok in _NUM.findall(scrub):
            n = tok.replace(",", "").rstrip(".").lstrip("+").rstrip("%")
            if not n or n in ("-",):
                continue
            cn = canonical_number(tok)
            if re.fullmatch(r"\d{4}", n) and 2000 <= int(n) <= 2035:
                continue
            if "." not in n and len(n.lstrip("-")) < 2 and not tok.endswith("%"):
                continue
            if signed_supported(cn, hay_tokens, tok.lstrip().startswith("+")):
                continue
            if ("number", f"{tok}|{path}") in seen:
                continue
            seen.add(("number", f"{tok}|{path}"))
            flagged.append({"kind": "number", "value": tok, "path": path, "text": text[:160]})
    return flagged
