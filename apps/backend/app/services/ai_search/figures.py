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
_FISCAL = re.compile(r"\b(?:FY\s?\d{2,4}|Q[1-4](?:\s?FY\s?\d{2,4})?|H[12]\s?FY\s?\d{2,4})\b", re.IGNORECASE)

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


def unsupported_figures(ai: dict, evidence_text: str, query: str, today: date | None = None) -> list[dict]:
    """Figures and dates in the generated public text that neither the evidence nor the question contains. Each result: {kind, value, path, text}."""
    today = today or datetime.now(timezone.utc).date()
    ev_dates = find_dates(evidence_text) | find_dates(query) | {today}
    hay = re.sub(r"[,\s]", "", _strip_dates(evidence_text + " " + query))
    hay_nums = {n.replace(",", "").rstrip(".").lstrip("+") for n in _NUM.findall(_strip_dates(evidence_text + " " + query))}
    flagged: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for path, text in public_strings(ai):
        for d in find_dates(text):
            if d not in ev_dates and ("date", d.isoformat()) not in seen:
                seen.add(("date", d.isoformat()))
                flagged.append({"kind": "date", "value": d.isoformat(), "path": path, "text": text[:160]})
        scrub = _FISCAL.sub(" ", _HORIZON.sub(" ", _strip_dates(text)))
        for tok in _NUM.findall(scrub):
            n = tok.replace(",", "").rstrip(".").lstrip("+").rstrip("%")
            if not n or n in ("-",):
                continue
            if re.fullmatch(r"\d{4}", n) and 2000 <= int(n) <= 2035:
                continue
            if "." not in n and len(n.lstrip("-")) < 2 and not tok.endswith("%"):
                continue
            if n in {h.rstrip("%") for h in hay_nums} or n in hay:
                continue
            if ("number", f"{tok}|{path}") in seen:
                continue
            seen.add(("number", f"{tok}|{path}"))
            flagged.append({"kind": "number", "value": tok, "path": path, "text": text[:160]})
    return flagged
