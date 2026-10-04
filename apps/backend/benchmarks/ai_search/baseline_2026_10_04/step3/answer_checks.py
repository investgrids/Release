"""
Step 3 answer-level checks. Pure functions over a saved answer (the finalized response dict) and the evidence snapshot saved with it. No model calls, no network.

These checks do not judge writing quality. They find claims the retrieved evidence cannot support, and they are deliberately conservative: a flag is a candidate for the
manual review that follows, a pass means "no problem found by this check", never "the answer is correct".

Scope rules (the two lexical traps found in Step 2):
  * A single-company exchange filing ("Tera Software Limited has informed the Exchange ...") is a fact about THAT company. It can never support a sector-level or market-level claim,
    however many sector words it contains ("software").
  * A mention of a brand inside another entity's name ("Kotak Institutional Equities", "Kotak Securities") is not a fact about the bank. Only the registered name, the symbol, or an
    event tagged to the company counts as a company fact.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone

NOW = datetime(2026, 10, 4, tzinfo=timezone.utc)

# ── evidence snapshot ────────────────────────────────────────────────────────

def snapshot_evidence(bundle) -> dict:
    """The whole evidence bundle as plain data, so any check can be re-run later without the database."""
    return {
        "plan_kind": getattr(bundle, "plan_kind", None),
        "filter_report": getattr(bundle, "filter_report", None),
        "events": [{"id": e.get("id"), "title": e.get("title"), "summary": e.get("summary"), "date": e.get("event_date") or e.get("published_at") or e.get("date"),
                    "source": e.get("source"), "companies": [c.get("symbol") for c in (e.get("companies") or []) if isinstance(c, dict)]} for e in bundle.events],
        "news": [{"id": n.get("id"), "title": n.get("headline"), "summary": n.get("summary"), "date": n.get("published_at"), "source": n.get("source")} for n in bundle.news],
        "announcements": [{"id": a.get("id"), "title": a.get("subject"), "category": a.get("category"), "date": a.get("announcement_date")} for a in (bundle.announcements or [])],
        "policies": [{"id": p.get("id"), "title": p.get("title"), "summary": p.get("summary"), "ministry": p.get("ministry")} for p in bundle.policies],
        "valuation": bundle.valuation, "vix": bundle.vix_level,
        "sector_rows": bundle.sector_rows, "macro_indices": bundle.macro_indices,
        "context_lines": list(bundle.context_lines or []),
        "historical": [{"title": h.get("title") or h.get("event"), "similarity": h.get("similarity")} for h in (bundle.similar_historical or [])],
    }


def evidence_total(ev: dict) -> int:
    return len(ev["events"]) + len(ev["news"]) + len(ev["announcements"]) + len(ev["policies"])


def all_items(ev: dict) -> list[dict]:
    out = []
    for kind in ("events", "news", "announcements", "policies"):
        for it in ev[kind]:
            out.append({**it, "kind": kind[:-1] if kind != "news" else "news"})
    return out


# ── text of the answer ───────────────────────────────────────────────────────

_TEXT_FIELDS = ("summary", "bottom_line", "what_happened", "why_it_happened", "immediate_impact", "medium_term", "long_term", "what_priced_in")


def answer_pieces(res: dict) -> list[tuple[str, str]]:
    """(field, text) for every generated text field a user can read."""
    out: list[tuple[str, str]] = []
    a = res.get("answer") or {}
    for k in _TEXT_FIELDS:
        if a.get(k):
            out.append((f"answer.{k}", str(a[k])))
    for k in ("risks", "opportunities"):
        for i, x in enumerate(a.get(k) or []):
            out.append((f"answer.{k}[{i}]", x if isinstance(x, str) else json.dumps(x, ensure_ascii=False)))
    for i, d in enumerate(res.get("key_drivers") or []):
        out.append((f"key_drivers[{i}]", json.dumps(d, ensure_ascii=False) if isinstance(d, dict) else str(d)))
    for i, d in enumerate(res.get("insights") or []):
        out.append((f"insights[{i}]", " ".join(str(d.get(k) or "") for k in ("title", "summary")) if isinstance(d, dict) else str(d)))
    for i, c in enumerate(res.get("companies") or []):
        out.append((f"companies[{i}:{c.get('symbol')}]", f"{c.get('reason') or ''} {c.get('why_it_matters') or ''}".strip()))
    for k, v in (res.get("ai_conclusion") or {}).items():
        if isinstance(v, str) and v:
            out.append((f"ai_conclusion.{k}", v))
    de = res.get("decision_engine_v2") or {}
    if de.get("why"):
        out.append(("decision_engine_v2.why", str(de["why"])))
    for k in ("what_changes_the_view", "what_invalidates_the_thesis"):
        for i, x in enumerate(de.get(k) or []):
            out.append((f"decision_engine_v2.{k}[{i}]", x if isinstance(x, str) else json.dumps(x, ensure_ascii=False)))
    for i, t in enumerate(res.get("timeline") or []):
        out.append((f"timeline[{i}]", json.dumps(t, ensure_ascii=False) if isinstance(t, dict) else str(t)))
    for name, sc in (res.get("scenarios") or {}).items():
        if isinstance(sc, dict):
            out.append((f"scenarios.{name}", " ".join(str(sc.get(k) or "") for k in ("outcome",) ) + " " + " ".join(str(x) for x in (sc.get("key_drivers") or []))))
    iv = res.get("investment_verdict") or {}
    for k in ("risks", "catalysts"):
        for i, x in enumerate(iv.get(k) or []):
            out.append((f"investment_verdict.{k}[{i}]", x if isinstance(x, str) else json.dumps(x, ensure_ascii=False)))
    return [(f, t) for f, t in out if t and t.strip()]


_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(])")


def sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENT_SPLIT.split(text.replace("\n", " ")) if len(s.strip()) > 3]


# ── numbers ──────────────────────────────────────────────────────────────────

_NUM = re.compile(r"(?<![\w.])[-+]?\d[\d,]*\.?\d*%?")


def _norm_num(tok: str) -> str:
    return tok.replace(",", "").rstrip(".").lstrip("+").rstrip("%")


def evidence_text(ev: dict, query: str) -> str:
    chunks = [query, *ev.get("context_lines", [])]
    for it in all_items(ev):
        chunks += [str(it.get("title") or ""), str(it.get("summary") or ""), str(it.get("date") or ""), str(it.get("category") or "")]
    chunks += [json.dumps(ev.get("valuation"), default=str), json.dumps(ev.get("sector_rows"), default=str), json.dumps(ev.get("macro_indices"), default=str), str(ev.get("vix")),
               json.dumps(ev.get("historical"), default=str)]
    return " ".join(chunks)


def unsupported_numbers(res: dict, ev: dict, query: str) -> list[dict]:
    """Numbers (2+ digits, or a decimal, or a percent) in generated text that appear nowhere in the query or the evidence. Years 2000-2035 are ignored, as are bare
    horizon phrases like "6-12 months"."""
    hay = _norm_num(evidence_text(ev, query))
    hay_set = {_norm_num(t) for t in _NUM.findall(evidence_text(ev, query))}
    flagged = []
    for field, text in answer_pieces(res):
        for sent in sentences(text):
            for tok in _NUM.findall(sent):
                n = _norm_num(tok)
                if not n or n in ("-", "+"):
                    continue
                if re.fullmatch(r"\d{4}", n) and 2000 <= int(n) <= 2035:
                    continue
                if "." not in n and len(n) < 2 and not tok.endswith("%"):
                    continue
                if re.search(rf"{re.escape(tok)}\s*(?:-|to)\s*\d+\s*(?:months?|years?|quarters?|weeks?|days?)", sent) or re.search(rf"(?:{re.escape(tok)})\s*(?:months?|years?|quarters?|weeks?|days?)", sent):
                    continue
                if n in hay_set or n in hay:
                    continue
                flagged.append({"number": tok, "field": field, "sentence": sent[:220]})
    seen, out = set(), []
    for f in flagged:
        key = (f["number"], f["sentence"])
        if key not in seen:
            seen.add(key)
            out.append(f)
    return out


# ── scope: what can an item support? ─────────────────────────────────────────

_INSTITUTION_AFTER = re.compile(
    r"^\s*(?:institutional|securities|mutual\s+fund|asset\s+management|alternate|investment\s+advis|capital\s+markets|general\s+insurance|life\s+insurance|prudential|lombard|"
    r"sec\b|broking|wealth|research|equities|amc)", re.IGNORECASE)
_SINGLE_FILING = re.compile(r"\bhas\s+informed\s+the\s+exchange\b|\binformed\s+the\s+stock\s+exchanges?\b", re.IGNORECASE)


def company_terms(symbol: str, universe: list[dict]) -> dict:
    """Registered name stem, symbol and aliases for a company; `strong` are the forms that identify the company by itself."""
    co = next((c for c in universe if c["symbol"] == symbol), None)
    if not co:
        return {"strong": [symbol.lower()], "weak": []}
    name = re.sub(r"\s+(?:ltd\.?|limited|inc\.?|plc)$", "", co["name"].lower()).strip()
    strong = [name, symbol.lower()]
    weak = [a.lower() for a in (co.get("aliases") or []) if a.lower() not in strong]
    return {"strong": list(dict.fromkeys(strong)), "weak": weak}


def names_company(text: str, terms: dict) -> str | None:
    """'strong' when the text uses the registered name / symbol; 'weak' when only a short brand alias appears and it is not part of another entity's name; None otherwise."""
    t = (text or "").lower()
    for s in terms["strong"]:
        if re.search(r"(?<![a-z0-9])" + re.escape(s) + r"(?![a-z0-9])", t):
            return "strong"
    for w in terms["weak"]:
        for m in re.finditer(r"(?<![a-z0-9])" + re.escape(w) + r"(?![a-z0-9])", t):
            if not _INSTITUTION_AFTER.match(t[m.end():m.end() + 30]):
                return "weak"
    return None


def eligible_for_company(item: dict, symbol: str, universe: list[dict]) -> tuple[bool, str]:
    """May this item support a claim about the company? Tagged events: yes. Otherwise the text must use the registered name or symbol; a brand-only mention that sits inside
    another entity's name ("Kotak Institutional Equities") never counts, and a brand-only mention in news is treated as not eligible."""
    if symbol in (item.get("companies") or []):
        return True, "event tagged to the company"
    terms = company_terms(symbol, universe)
    text = f"{item.get('title') or ''} {item.get('summary') or ''}"
    hit = names_company(text, terms)
    if hit == "strong":
        return True, "uses the registered name or symbol"
    if hit == "weak":
        return False, "brand alias only (not the registered name or symbol); could be another entity"
    return False, "does not name the company"


def eligible_for_sector(item: dict) -> tuple[bool, str]:
    """A single-company filing cannot support a sector or market claim; an event tagged to three or more companies, or a news/policy item, can."""
    if item["kind"] == "announcement":
        return False, "single-company filing"
    if item["kind"] == "event":
        tagged = item.get("companies") or []
        if len(tagged) >= 3:
            return True, "event tagged to several companies"
        if _SINGLE_FILING.search(item.get("title") or ""):
            return False, "single-company exchange filing"
        return True, "market or sector event"
    if _SINGLE_FILING.search(item.get("title") or ""):
        return False, "single-company exchange filing"
    return True, "news or policy item"


# ── claim support ────────────────────────────────────────────────────────────

_FILLER = {
    "that", "this", "with", "from", "have", "has", "had", "been", "were", "was", "will", "would", "could", "should", "their", "there", "which", "while", "about", "into", "over",
    "than", "then", "them", "they", "also", "more", "most", "such", "some", "only", "very", "much", "many", "well", "does", "did", "are", "and", "for", "the", "its", "can",
    "may", "might", "market", "markets", "indian", "india", "company", "companies", "stock", "stocks", "shares", "share", "investors", "investor", "analysis", "recent",
    "currently", "likely", "continue", "expected", "driven", "growth", "outlook", "impact", "sector", "sectors", "performance", "mixed", "positive", "negative",
}
_TOKEN = re.compile(r"[a-z0-9][a-z0-9&.\-]{2,}")


def salient(text: str) -> set[str]:
    return {t.strip(".-") for t in _TOKEN.findall((text or "").lower()) if t.strip(".-") not in _FILLER and not t.isdigit()}


def _claim_scope(sentence: str, resolved: list[str], universe: list[dict], sectors: list[str]) -> tuple[str, str | None]:
    for sym in resolved:
        if names_company(sentence, company_terms(sym, universe)):
            return "company", sym
    low = sentence.lower()
    if any(s.lower() in low for s in sectors) or re.search(r"\b(?:sector|industry|it services|banking|banks|lenders)\b", low):
        return "sector", None
    return "market", None


_FACTUAL = re.compile(r"\d|%|₹|\brs\.?\b|\bcrore\b|\bannounc|\bwon\b|\bwins?\b|\bsigned\b|\breported\b|\braised\b|\bdelivered\b|\bacquir|\bapproved\b|\blaunch", re.IGNORECASE)


def claim_checks(res: dict, ev: dict, query: str, resolved: list[str], sectors: list[str], universe: list[dict]) -> list[dict]:
    """For every factual-looking sentence: which evidence items share its salient terms, and whether any of them is eligible for the scope of the claim. Statuses:
    supported (eligible item matches), ineligible_only (items match lexically but none may support this scope: the lexical-trap case), unsupported (nothing matches)."""
    items = all_items(ev)
    out = []
    seen = set()
    for field, text in answer_pieces(res):
        for sent in sentences(text):
            if sent in seen or _INSUFFICIENT.search(sent):    # a sentence that says evidence is lacking is not itself a factual claim
                continue
            scope, sym = _claim_scope(sent, resolved, universe, sectors)
            sal = salient(sent)
            # A claim is a sentence with a number / event verb, OR one that names a company or sector and says something substantive about it.
            if not (_FACTUAL.search(sent) or (scope != "market" and len(sal) >= 3)):
                continue
            seen.add(sent)
            matched, eligible = [], []
            for it in items:
                shared = sal & salient(f"{it.get('title') or ''} {it.get('summary') or ''}")
                if len(shared) >= 2:
                    matched.append({"id": it.get("id"), "title": (it.get("title") or "")[:90], "shared": sorted(shared)[:6]})
                    ok, why = eligible_for_company(it, sym, universe) if scope == "company" else eligible_for_sector(it) if scope == "sector" else (True, "market claim")
                    if ok:
                        eligible.append(it.get("id"))
                    else:
                        matched[-1]["ineligible_because"] = why
            ctx_match = any(len(sal & salient(line)) >= 2 for line in ev.get("context_lines", []))
            struct_match = bool(ev.get("sector_rows") or ev.get("macro_indices") or ev.get("valuation")) and bool(re.search(r"\d", sent)) and (
                any(str(r.get("name", "")).lower() in sent.lower() for r in (ev.get("sector_rows") or [])) or any(str(r.get("name", "")).lower() in sent.lower() for r in (ev.get("macro_indices") or []))
                or any(str(k).lower() in sent.lower() for k in (ev.get("valuation") or {})))
            if eligible or ctx_match or struct_match:
                status = "supported"
            elif matched:
                status = "ineligible_only"
            else:
                status = "unsupported"
            out.append({"field": field, "sentence": sent[:260], "scope": scope, "company": sym, "status": status, "matched": matched[:4]})
    return out


# ── dates ────────────────────────────────────────────────────────────────────

_RECENCY = re.compile(r"\b(?:just|today|yesterday|this week|this month|recently|latest|currently|newly|has announced|have announced|announced)\b", re.IGNORECASE)
_REL = re.compile(r"^\s*(\d+)\s*(m|min|mins|minutes?|h|hr|hrs|hours?|d|days?|w|wk|weeks?|mo|months?)\s+ago\s*$", re.IGNORECASE)


def item_age_days(date) -> float | None:
    if not date or not isinstance(date, str):
        return None
    s = date.strip()
    m = _REL.match(s)
    if m:
        n, u = int(m.group(1)), m.group(2).lower()
        return n * 30.0 if u.startswith("mo") else n * 7.0 if u.startswith("w") else float(n) if u.startswith("d") else n / 24 if u.startswith("h") else n / 1440
    for fmt in ("%b %d, %Y", None):
        try:
            d = datetime.strptime(s, fmt) if fmt else datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            continue
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return max((NOW - d).total_seconds() / 86400, 0.0)
    return None


def recency_claims(claims: list[dict], ev: dict, max_age_days: int) -> list[dict]:
    """A sentence that presents something as new ("just announced", "recently") needs eligible evidence dated inside the window. Flags those that rest only on older items."""
    by_id = {str(it.get("id")): it for it in all_items(ev)}
    out = []
    for c in claims:
        if not _RECENCY.search(c["sentence"]):
            continue
        ages = []
        for m in c["matched"]:
            if "ineligible_because" in m:
                continue
            a = item_age_days((by_id.get(str(m["id"])) or {}).get("date"))
            if a is not None:
                ages.append(a)
        if not ages:
            out.append({"sentence": c["sentence"], "problem": "presented as recent but no dated eligible evidence supports it"})
        elif min(ages) > max_age_days:
            out.append({"sentence": c["sentence"], "problem": f"presented as recent; newest supporting evidence is {min(ages):.0f} days old (window {max_age_days})"})
    return out


# ── honest insufficiency ─────────────────────────────────────────────────────

_INSUFFICIENT = re.compile(
    r"\b(?:no recent|not enough|insufficient|limited (?:recent )?(?:evidence|information|data)|no (?:verified|reliable|relevant|supporting) (?:evidence|information|data)|"
    r"unable to (?:find|verify|confirm)|cannot (?:confirm|verify)|could(?:n't| not) (?:find|verify|confirm)|there is no (?:recent|verified|available)|"
    r"does not have|do not have|don't have|lack(?:s|ing)? (?:recent|verified|reliable|sufficient)|not available)\b", re.IGNORECASE)


def insufficient_evidence_check(res: dict, ev: dict, query: str, universe: list[dict], resolved: list[str]) -> dict:
    """For a question whose retrieval found nothing relevant and recent: PASS only if the answer says so and does not assert company-specific facts or numbers.
    Not applicable (None status) when evidence exists."""
    if evidence_total(ev) > 0:
        return {"applicable": False}
    text = " ".join(t for _f, t in answer_pieces(res))
    says = bool(_INSUFFICIENT.search(text))
    nums = unsupported_numbers(res, ev, query)
    claims = [c for c in claim_checks(res, ev, query, resolved, [], universe) if c["status"] != "supported"]
    status = "PASS" if (says and not nums and not claims) else "FAIL"
    return {"applicable": True, "status": status, "states_insufficient_evidence": says, "unsupported_numbers": len(nums), "unsupported_claims": len(claims),
            "examples": [c["sentence"] for c in claims[:3]] + [n["sentence"] for n in nums[:2]]}


# ── citations ────────────────────────────────────────────────────────────────

def citation_check(res: dict, ev: dict) -> dict:
    have = {f"event:{e['id']}" for e in ev["events"]} | {f"news:{n['id']}" for n in ev["news"]} | {f"policy:{p['id']}" for p in ev["policies"]}
    claimed = set(res.get("source_attribution") or [])
    news_sources = {n.get("source") for n in ev["news"]}
    cites = set(res.get("citations") or [])
    shown_events = res.get("related_events") or []
    shown_news = res.get("news") or []
    ev_ids = {str(e["id"]) for e in ev["events"]}
    news_ids = {str(n["id"]) for n in ev["news"]}
    return {
        "attribution_ids_not_in_evidence": sorted(x for x in claimed if x not in have and not x.startswith("historical:")),
        "citation_sources_not_in_news": sorted(c for c in cites if c not in news_sources),
        "shown_events_not_in_evidence": [e.get("title") for e in shown_events if str(e.get("id")) not in ev_ids],
        "shown_news_not_in_evidence": [n.get("headline") for n in shown_news if str(n.get("id")) not in news_ids],
        "claim_level_attribution_available": False,   # the pipeline attributes the whole bundle, not individual claims
    }


# ── score / rank references ──────────────────────────────────────────────────

_SCORE_REF = re.compile(r"marketripple\s+score|market\s?ripple|\bscore\s+of\s+\d|\b\d{1,3}(?:\.\d+)?\s*/\s*100\b|\bstrong\b\s+(?:band|rating)|\b(?:positive|neutral|cautious)\s+(?:band|rating)\b", re.IGNORECASE)
_POSITIVE = {"strongly constructive", "constructive", "positive outlook", "selectively constructive", "positive", "strong"}
_NEGATIVE = {"cautious", "elevated risk", "high uncertainty", "weak"}


def score_reference_check(res: dict, published: dict[str, dict]) -> dict:
    """`published` maps symbol -> {"score": float|None, "band": str|None} for the companies the answer is about. Flags any MarketRipple score/band the text states (the pipeline
    never reads the score, so any such statement is unsupported) and any AI verdict that contradicts a published band."""
    text = " ".join(t for _f, t in answer_pieces(res))
    refs = [m.group(0) for m in _SCORE_REF.finditer(text)]
    iv = res.get("investment_verdict") or {}
    ai_rating = str(iv.get("rating") or (res.get("decision_engine_v2") or {}).get("verdict_scale") or "").lower()
    contradictions = []
    for sym, p in (published or {}).items():
        band = (p.get("band") or "").lower()
        if not band or not ai_rating:
            continue
        if (band in ("cautious",) and ai_rating in _POSITIVE) or (band in ("positive", "strong") and ai_rating in _NEGATIVE):
            contradictions.append({"symbol": sym, "published_band": p.get("band"), "published_score": p.get("score"), "ai_rating": ai_rating})
    return {"score_statements_in_text": refs, "ai_rating": ai_rating or None, "contradicts_published_band": contradictions,
            "published": published}


def comparison_rank_check(res: dict, published: dict[str, dict], valuation: dict | None) -> dict:
    """When two companies are compared and both have a published score, the answer's stated stronger company must not be the lower-scored one. Falls back to nothing (UNVERIFIED)
    when scores are missing."""
    scored = {s: p["score"] for s, p in (published or {}).items() if p.get("score") is not None}
    di = res.get("decision_intelligence") or {}
    rec = (di.get("engine_recommendation") or {}) if isinstance(di, dict) else {}
    winner = rec.get("preferred") or rec.get("winner") or di.get("preferred") or di.get("winner")
    text = " ".join(t for _f, t in answer_pieces(res)).lower()
    if len(scored) < 2:
        return {"checkable": False, "reason": "published scores for both companies are not available"}
    top = max(scored, key=scored.get)
    low = min(scored, key=scored.get)
    states_low_stronger = bool(re.search(rf"{re.escape(low.lower())}[^.]{{0,60}}(?:stronger|better|preferred|ahead)", text)) and not re.search(rf"{re.escape(top.lower())}[^.]{{0,60}}(?:stronger|better|preferred|ahead)", text)
    return {"checkable": True, "scores": scored, "engine_winner": winner, "text_prefers_lower_scored": states_low_stronger}
