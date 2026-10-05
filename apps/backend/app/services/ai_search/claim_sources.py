"""
Claim-level source IDs: validation.

The specialist prompts tag every piece of evidence with an ID (E events, N news, P policies, A announcements, C context lines; see EvidenceBundle.index()) and ask the model to list, for
each factual sentence of its answer, the IDs that support it ("claim_sources"). This module checks what comes back, deterministically, without a model:

  * structure          the entry has a claim string and a list of IDs
  * unknown_source     an ID that is not in the evidence index (the model invented it)
  * no_source          a claim with no ID at all
  * claim_not_in_answer the claim sentence does not appear in the generated answer (the model listed a sentence it never wrote)
  * ineligible_sources every cited item is something that cannot support this claim: a stock-tips article, a filing by another company for a sector claim, a brand-only mention for a
                       company claim (evidence_scope.py)
  * premise_unsupported the claim asserts the event the question assumed, and no evidence confirmed it
  * uncovered factual sentences in the answer that no claim entry covers

Non-blocking: the result is attached to the response (and read by the offline gate); it never rewrites or removes answer text. status: "not_provided" when the model returned no usable
claim_sources, "ok" when there is nothing to report, "problems" otherwise.
"""
from __future__ import annotations

import re

from app.services.ai_search import evidence_scope as scope

_FACT_RE = re.compile(r"\d|%|₹|\brs\.?\b|\bcrore\b|\bannounc|\bwon\b|\bwins?\b|\bsigned\b|\breported\b|\braised\b|\bdelivered\b|\bacquir|\bapproved\b|\blaunch|\bawarded\b|\bsecured\b|\bfiled\b|\bdisclosed\b|\binformed\b|\bdeclared\b|\bcompleted\b|\bentered into\b", re.IGNORECASE)
# A period label ("52-week", "1-day", "6-12 months") describes the window a statement covers; it is not a figure. It is removed before the digit test, so "52-week ranges only" is not a
# factual sentence, while "the 52-week high is 3350" still is (3350 remains). Deliberately narrow: nothing else is exempted, and a sentence with any other digit, %, rupee or event verb stays factual.
_PERIOD_LABEL = re.compile(r"(?<![\w.])\d+(?:\s*[-\u2013]\s*\d+)?[- ]?(?:week|day|month|year|quarter|hour|minute)s?(?![a-z])", re.IGNORECASE)


def is_factual(sentence: str) -> bool:
    return bool(_FACT_RE.search(_PERIOD_LABEL.sub(" ", sentence)))


_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(])")
_ID_RE = re.compile(r"^[ENPAC]\d{1,3}$")


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9%₹.]+", " ", (text or "").lower()).strip().rstrip(".").strip()


def _field(d: dict, key: str):
    a = d.get("answer") if isinstance(d.get("answer"), dict) else {}
    return d.get(key) if d.get(key) not in (None, "") else a.get(key)


def answer_pieces(d: dict) -> list[str]:
    """The generated prose a user reads, from either the flat specialist output or the final response shape."""
    out: list[str] = []
    for k in ("summary", "bottom_line", "what_happened", "why_it_happened", "immediate_impact", "medium_term", "long_term", "what_priced_in"):
        v = _field(d, k)
        if isinstance(v, str) and v.strip():
            out.append(v)
    for k in ("risks", "opportunities"):
        for x in _field(d, k) or []:
            if isinstance(x, str):
                out.append(x)
    for x in d.get("key_drivers") or []:
        if isinstance(x, dict):
            out.append(" ".join(str(x.get(k) or "") for k in ("title", "explanation")).strip())
    for c in d.get("companies") or []:
        if isinstance(c, dict) and c.get("reason"):
            out.append(str(c["reason"]))
    # Step 3.4G.1: sectors[].explanation is public model-written text. Every public factual surface must be inspectable by the same claim authorization.
    for s in d.get("sectors") or []:
        if isinstance(s, dict) and s.get("explanation"):
            out.append(str(s["explanation"]))
    de = d.get("decision_engine_v2") or {}
    if isinstance(de, dict) and de.get("why"):
        out.append(str(de["why"]))
    return [p for p in out if p.strip()]


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENT_SPLIT.split((text or "").replace("\n", " ")) if len(s.strip()) > 3]


_TOKEN_RE = re.compile(r"[a-z0-9%₹.]+")


def _tokens(text: str) -> set[str]:
    return {t.strip(".") for t in _TOKEN_RE.findall((text or "").lower()) if t.strip(".")}


def similar(a: str, b: str, threshold: float = 0.7) -> bool:
    """True when two sentences are the same sentence for our purposes: one contains the other after normalisation, or their word sets overlap by at least `threshold` (Jaccard).
    Lets a model that copies a sentence with a changed article or trailing punctuation still be matched, without matching different sentences."""
    na, nb = _norm(a), _norm(b)
    if not na or not nb:
        return False
    if na in nb or nb in na:
        return True
    ta, tb = _tokens(a), _tokens(b)
    return bool(ta and tb) and len(ta & tb) / len(ta | tb) >= threshold


def factual_sentences(answer: dict) -> list[str]:
    """Sentences of the generated prose that look like factual statements (a number, a currency amount, or an event verb)."""
    out: list[str] = []
    for p in answer_pieces(answer):
        for s in _sentences(p):
            if is_factual(s):
                out.append(s)
    return list(dict.fromkeys(out))


def _claim_scope(sentence: str, resolved: list[str], universe: list[dict], sectors: list[str]) -> tuple[str, str | None]:
    for sym in resolved:
        if scope.names_company(sentence, scope.company_terms(sym, universe)):
            return "company", sym
    low = sentence.lower()
    if any(s.lower() in low for s in sectors) or re.search(r"\b(?:sector|industry|it services|banking|banks|lenders)\b", low):
        return "sector", None
    return "market", None


def validate_claim_sources(raw, index: list[dict], answer: dict, entities: dict, universe: list[dict], premise: dict | None = None) -> dict:
    by_id = {e["id"]: e for e in index}
    resolved = [c for c in (entities.get("companies") or []) if c]
    sectors = entities.get("sectors") or []
    pieces = answer_pieces(answer)
    haystack = _norm(" ".join(pieces))

    if not isinstance(raw, list) or not raw:
        return {"status": "not_provided", "claims": [], "summary": {"claims": 0, "ok": 0, "problems": 0, "uncovered_factual_sentences": None}, "uncovered": []}

    claims_out: list[dict] = []
    for entry in raw:
        problems: list[str] = []
        claim = entry.get("claim") if isinstance(entry, dict) else None
        sources = entry.get("sources") if isinstance(entry, dict) else None
        if not isinstance(claim, str) or not claim.strip() or not isinstance(sources, list):
            claims_out.append({"claim": str(claim)[:200] if claim else "", "sources": [], "status": "malformed", "problems": ["malformed entry (needs a claim string and a sources list)"]})
            continue
        ids = [str(s).strip().strip("[]").upper() for s in sources if str(s).strip()]
        known = [i for i in ids if i in by_id]
        unknown = [i for i in ids if i not in by_id]
        if not ids:
            problems.append("no_source")
        if unknown:
            problems.append(f"unknown_source: {', '.join(unknown)}")
        if _norm(claim) and not any(similar(claim, s) for p in pieces for s in _sentences(p)) and _norm(claim) not in haystack:
            problems.append("claim_not_in_answer")
        sc, sym = _claim_scope(claim, resolved, universe, sectors)
        verdicts = []
        for i in known:
            e = by_id[i]
            item = {"kind": e["kind"], "title": e.get("title") or "", "summary": e.get("summary") or "", "companies": e.get("companies") or []}
            if e["kind"] == "context":
                verdicts.append((i, True, "context line"))
            elif sc == "company":
                ok, why = scope.eligible_for_company(item, sym, universe)
                verdicts.append((i, ok, why))
            elif sc == "sector":
                ok, why = scope.eligible_for_sector(item)
                verdicts.append((i, ok, why))
            else:
                ok = not scope.is_tips_article(item["title"], item["summary"]) and not scope.is_single_company_filing(item["title"])
                verdicts.append((i, ok, "market claim" if ok else "tips article or single-company filing"))
        if known and not any(ok for _i, ok, _w in verdicts):
            problems.append("ineligible_sources: " + "; ".join(f"{i} ({why})" for i, _ok, why in verdicts))
        if premise and premise.get("required") and not premise.get("supported"):
            pg = scope.premise_groups("just " + " ".join(premise.get("terms") or []))
            if sym and pg and any(scope._has_term(claim, t) for g in pg for t in g):
                problems.append("premise_unsupported: the question's event was not confirmed by any retrieved evidence")
        claims_out.append({"claim": claim.strip()[:300], "sources": ids, "scope": sc, "company": sym, "status": "ok" if not problems else "problem", "problems": problems,
                           "ineligible": [i for i, ok, _w in verdicts if not ok]})

    claim_texts = [c["claim"] for c in claims_out]
    uncovered = []
    for p in pieces:
        for s in _sentences(p):
            if is_factual(s) and not any(similar(s, c) for c in claim_texts):
                uncovered.append(s[:200])
    uncovered = list(dict.fromkeys(uncovered))
    n_ok = sum(1 for c in claims_out if c["status"] == "ok")
    n_bad = len(claims_out) - n_ok
    status = "ok" if (n_bad == 0 and not uncovered) else "problems"
    return {"status": status, "claims": claims_out, "uncovered": uncovered[:10],
            "summary": {"claims": len(claims_out), "ok": n_ok, "problems": n_bad, "uncovered_factual_sentences": len(uncovered)}}


def compact_index(index: list[dict]) -> list[dict]:
    """The evidence index as shipped in the response: enough to resolve any ID in claim_sources."""
    return [{k: e.get(k) for k in ("id", "kind", "title", "date", "source", "companies")} for e in index]
