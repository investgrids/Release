"""
What a piece of evidence is ALLOWED to support. One definition, used by retrieval (evidence_filter), the prompt (what the model is shown), claim-source validation
(claim_sources) and the offline answer gate, so they cannot drift apart.

Found in the Step 2/3 baselines:
  * A single-company exchange filing ("Tera Software Limited has informed the Exchange ...") is a fact about THAT company. It must not enter a sector or market bundle, however
    many sector words it contains.
  * A stock-tips article ("Top 3 stocks to buy: HDFC Bank, Infosys, BEL ...") is a recommendation, not evidence that anything happened. It must not enter any bundle, and it can
    never confirm an event ("BEL won an order").
  * A brand inside another entity's name ("Kotak Institutional Equities", "Kotak Securities") is not a fact about Kotak Mahindra Bank. Only the registered name, the symbol, or an
    event tagged to the company counts as a company fact; a bare brand alias does not.
  * An event the question asserts ("BEL just won a new defence order") is a PREMISE. If no eligible evidence about the company mentions that kind of event, the premise is
    unsupported and the model must be told so rather than handed unrelated BEL material.

Pure functions, no I/O. Items are normalised dicts: {"kind": event|news|announcement|policy, "title", "summary", "companies": [symbols]}.
"""
from __future__ import annotations

import re

# ── item normalisation ───────────────────────────────────────────────────────

def normalize(kind: str, raw: dict) -> dict:
    """Bundle rows come in 4 shapes (events carry `title`+`companies` as dicts, news `headline`, announcements `subject`, policies `title`); snapshots carry `title` and symbol lists."""
    companies = raw.get("companies") or []
    symbols = [c.get("symbol") if isinstance(c, dict) else c for c in companies]
    return {
        "kind": kind, "id": raw.get("id"),
        "title": raw.get("title") or raw.get("headline") or raw.get("subject") or "",
        "summary": raw.get("summary") or "", "companies": [s for s in symbols if s],
        "date": raw.get("event_date") or raw.get("published_at") or raw.get("announcement_date") or raw.get("date"),
    }


# ── tips articles and single-company filings ─────────────────────────────────

_TIPS_RE = re.compile(
    r"(?:(?<![a-z])(?:top|best)\s+\d*\s*(?:stocks?|shares|picks?|midcaps?|smallcaps?)\s+to\s+(?:buy|sell|bet\s+on|invest)|(?<![a-z])stocks?\s+to\s+(?:buy|sell)(?![a-z])|"
    r"(?<![a-z])buy\s+or\s+sell(?![a-z])|(?<![a-z])target\s+price(?![a-z])|(?<![a-z])stop[- ]?loss(?![a-z])|(?<![a-z])stock\s+picks?(?![a-z])|"
    r"(?<![a-z])multibagger(?![a-z])|(?<![a-z])should\s+you\s+buy(?![a-z])|(?<![a-z])buy\s+(?:call|rating)(?![a-z])|(?<![a-z])recommends?\s+(?:buying|selling))",
    re.IGNORECASE,
)
# Exchange communications about ONE company. The common form is "<Company> Limited has informed the Exchange ..."; the exchange's own notices about a named company
# ("The Exchange has sought clarification from Oracle Financial Services Software Limited ...") and Regulation 30 disclosures are the same kind of item.
_SINGLE_FILING_RE = re.compile(
    r"(?<![a-z])has\s+informed\s+the\s+(?:stock\s+)?exchanges?(?![a-z])|(?<![a-z])informed\s+the\s+stock\s+exchanges?(?![a-z])|"
    r"(?<![a-z])the\s+exchange\s+has\s+(?:sought|issued|sent|observed|noted)(?![a-z])|(?<![a-z])clarification\s+(?:sought\s+)?from\s+[A-Z][\w&.\- ]{2,60}\s(?:Limited|Ltd\.?)(?![a-z])|"
    r"(?<![a-z])has\s+(?:submitted|intimated|filed)\s+(?:to\s+)?the\s+(?:stock\s+)?exchanges?(?![a-z])|(?<![a-z])pursuant\s+to\s+regulation\s+30(?![a-z])|"
    r"(?<![a-z])(?:Limited|Ltd\.?)\s+has\s+(?:informed|intimated|announced\s+to)(?![a-z])",
    re.IGNORECASE,
)


def is_tips_article(title: str, summary: str = "") -> bool:
    return bool(_TIPS_RE.search(f"{title or ''} {summary or ''}"))


def is_single_company_filing(title: str) -> bool:
    return bool(_SINGLE_FILING_RE.search(title or ""))


# ── company naming ───────────────────────────────────────────────────────────

_INSTITUTION_AFTER = re.compile(
    r"^\s*(?:institutional|securities|mutual\s+fund|asset\s+management|alternate|investment\s+advis|capital\s+markets|general\s+insurance|life\s+insurance|prudential|lombard|"
    r"broking|wealth|research|equities|amc)", re.IGNORECASE)
_LEGAL_SUFFIX_RE = re.compile(r"\s+(?:ltd\.?|limited|inc\.?|plc)$", re.IGNORECASE)


def company_terms(symbol: str, universe: list[dict]) -> dict:
    """`strong`: registered name without its legal suffix, and the symbol. `weak`: short brand aliases, which are not enough on their own."""
    co = next((c for c in universe if c["symbol"] == symbol), None)
    if not co:
        return {"strong": [symbol.lower()], "weak": []}
    name = _LEGAL_SUFFIX_RE.sub("", co["name"].lower()).strip()
    strong = [name, symbol.lower()]
    weak = [a.lower() for a in (co.get("aliases") or []) if a.lower() not in strong]
    return {"strong": list(dict.fromkeys(strong)), "weak": weak}


def names_company(text: str, terms: dict) -> str | None:
    """'strong' = registered name or symbol; 'weak' = only a short brand alias that is NOT part of another entity's name; None otherwise."""
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
    """May this item support a claim about the company? A tagged event, or text using the registered name or symbol. A brand-only mention never qualifies."""
    if is_tips_article(item.get("title", ""), item.get("summary", "")):
        return False, "stock-tips article"
    if symbol in (item.get("companies") or []):
        return True, "event tagged to the company"
    hit = names_company(f"{item.get('title') or ''} {item.get('summary') or ''}", company_terms(symbol, universe))
    if hit == "strong":
        return True, "uses the registered name or symbol"
    if hit == "weak":
        return False, "brand alias only (not the registered name or symbol); could be another entity"
    return False, "does not name the company"


def eligible_for_sector(item: dict) -> tuple[bool, str]:
    """Sector / market claims: never a single-company filing or a tips article; an event tagged to three or more companies, or ordinary news/policy, qualifies."""
    if is_tips_article(item.get("title", ""), item.get("summary", "")):
        return False, "stock-tips article"
    if item.get("kind") == "announcement":
        return False, "single-company filing"
    if is_single_company_filing(item.get("title", "")) and len(item.get("companies") or []) < 3:
        return False, "single-company exchange filing"
    return True, "market, sector or news item"


# ── premises ─────────────────────────────────────────────────────────────────

_EVENT_CUE = re.compile(
    r"(?<![a-z])(?:just|newly|announced|announces|announce|reported|reports|won|wins|bags|bagged|signed|signs|declared|launched|completed|delivered|raised|approved|secured|secures|awarded)(?![a-z])",
    re.IGNORECASE)

# Groups of equivalent event words. A question that triggers a group asserts that kind of event; an item confirms it only by using a word from the same group.
_PREMISE_GROUPS: list[tuple[str, ...]] = [
    ("order", "orders", "contract", "contracts", "bags", "bagged", "wins", "won", "win", "awarded", "secures", "secured", "letter of award", "loa", "l1 bidder"),
    ("deal", "deals", "partnership", "agreement", "signed", "signs", "mou"),
    ("acquisition", "acquire", "acquires", "acquired", "takeover", "merger", "stake"),
    ("result", "results", "earnings", "profit", "revenue", "quarterly", "q1", "q2", "q3", "q4"),
    ("dividend", "bonus", "buyback", "split"),
    ("launch", "launches", "launched", "rollout", "expansion", "capacity", "plant", "facility"),
    ("director", "directors", "ceo", "cfo", "chairman", "appoint", "appointed", "resign", "resigns", "resignation", "leadership"),
    ("research center", "research centre", "ai research", "innovation center", "innovation centre"),
    ("fund raising", "fundraise", "fundraising", "qip", "rights issue", "ipo", "fpo", "insolvency"),
    ("penalty", "fine", "fraud", "investigation", "probe", "raid"),
    ("approval", "approved", "clearance"),
]


def _has_term(text: str, term: str) -> bool:
    return bool(re.search(r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])", text.lower()))


def premise_groups(query: str) -> list[tuple[str, ...]]:
    """Event-word groups the question asserts, only when the question is phrased as news ("just won", "announced ..."); empty otherwise."""
    if not _EVENT_CUE.search(query or ""):
        return []
    return [g for g in _PREMISE_GROUPS if any(_has_term(query, t) for t in g)]


def supports_premise(item: dict, groups: list[tuple[str, ...]]) -> bool:
    text = f"{item.get('title') or ''} {item.get('summary') or ''}"
    return any(_has_term(text, t) for g in groups for t in g)
