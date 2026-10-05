"""
Retrieval planning by question type, and the date / relevance checks applied to evidence BEFORE it reaches the specialist prompt or the response.

Why this exists (Step 1 baseline, 2026-10-04): every question used to go through the same retrieval. A question that merely contained a word resembling a ticker
("crude oil" -> Oil India) pulled that company's data; an educational question ("What is a P/E ratio?") got ten unrelated events and four US Federal Reserve items;
a comparison got one event (85 days old), no announcements and no valuation; and nothing was ever dropped for being old. The plan below decides WHAT to fetch per
question type, and filter_bundle decides WHAT SURVIVES. Nothing here calls a model, and it never invents evidence: a filter can only remove items or leave the
bundle empty, which is reported honestly downstream.

Question types:
  comparison    two or more resolved companies -> events tagged to EACH company, announcements and valuation for each, news that mentions a company
  company       one resolved company           -> events tagged to it (no word-match fallback), announcements, news that mentions it
  explanation   educational/definitional, no company/sector/policy named -> no company, event, news or policy retrieval at all (macro indices still come from
                the existing macro trigger)
  topic         sector / policy / macro / general -> word-matched events and news, but each item must be relevant to the named sector/policy or share at least two
                distinctive query words with the question
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from app.services.ai_search import evidence_scope as scope
from app.services.ai_search.education import CURRENT_DATA_RE

_EXPLAIN_RE = re.compile(
    r"^\s*(?:what\s+(?:is|are|does|do)|explain|define|how\s+(?:does|do|should\s+i\s+(?:read|use|interpret)|to\s+read)|meaning\s+of|difference\s+between)",
    re.IGNORECASE,
)

# Maximum age, in days, before an item is dropped for each source and question kind. An "event impact" question ("just announced") is held to a tighter window
# than general company research; topic questions about sectors move faster than policy/macro ones.
MAX_AGE_DAYS = {
    "comparison": {"events": 90, "news": 45, "announcements": 90},
    "company": {"events": 90, "news": 45, "announcements": 90},
    "company_event": {"events": 45, "news": 30, "announcements": 45},
    "topic": {"events": 90, "news": 45, "announcements": 90},
    "topic_sector": {"events": 60, "news": 45, "announcements": 90},
    "explanation": {"events": 0, "news": 0, "announcements": 0},
}


@dataclass
class RetrievalPlan:
    kind: str                       # comparison | company | explanation | topic
    events: str                     # "tagged" | "words" | "none"
    news: str                       # "entity" | "words" | "none"
    policies: bool
    announcements_for: list[str] = field(default_factory=list)
    valuation_for: list[str] = field(default_factory=list)
    age_key: str = "topic"          # key into MAX_AGE_DAYS


def plan_for(query: str, intent_data: dict, entities: dict) -> RetrievalPlan:
    companies = [c for c in (entities.get("companies") or []) if c]
    sectors = entities.get("sectors") or []
    policies = entities.get("policies") or []
    is_cmp = bool(intent_data.get("is_comparison")) or len(companies) >= 2
    if is_cmp and len(companies) >= 2:
        return RetrievalPlan("comparison", "tagged", "entity", bool(policies), announcements_for=companies[:3], valuation_for=companies[:3], age_key="comparison")
    if companies:
        event_q = intent_data.get("intent") == "news_reaction"
        return RetrievalPlan("company", "tagged", "entity", bool(policies), announcements_for=companies[:2], age_key="company_event" if event_q else "company")
    # Step 4B: the evidence-free explanation plan is for definitions only. A question that asks about now, a price or a quantity ("What is the Nifty today?") is a data question and must take the topic plan, where it is
    # held to Gate A and Gate B like any other, instead of reaching a model with no evidence and no authorization.
    if not sectors and not policies and _EXPLAIN_RE.search(query or "") and not CURRENT_DATA_RE.search(query or ""):
        return RetrievalPlan("explanation", "none", "none", False, age_key="explanation")
    return RetrievalPlan("topic", "words", "words", bool(policies), age_key="topic_sector" if sectors else "topic")


# ── age ──────────────────────────────────────────────────────────────────────────
_REL_RE = re.compile(r"^\s*(\d+)\s*(m|min|mins|minutes?|h|hr|hrs|hours?|d|days?|w|wk|weeks?|mo|months?)\s+ago\s*$", re.IGNORECASE)


def age_days(value, now: datetime | None = None) -> float | None:
    """Age in days of a date in any shape the bundle carries: "%b %d, %Y", ISO, or a relative string ("44m ago", "1d ago"). None when it cannot be read - never
    a guess (the existing _parse_evidence_date falls back to "now", which would make an undated item look brand new)."""
    now = now or datetime.now(timezone.utc)
    if not value or not isinstance(value, str):
        return None
    s = value.strip()
    if s.lower() in ("just now", "now"):
        return 0.0
    m = _REL_RE.match(s)
    if m:
        n, unit = int(m.group(1)), m.group(2).lower()
        per_day = {"m": 1440, "h": 24}
        if unit.startswith("mo"):
            return n * 30.0
        if unit.startswith("w"):
            return n * 7.0
        if unit.startswith("d"):
            return float(n)
        if unit.startswith("h"):
            return n / per_day["h"]
        return n / per_day["m"]
    for fmt in ("%b %d, %Y", None):
        try:
            d = datetime.strptime(s, fmt) if fmt else datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            continue
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return max((now - d).total_seconds() / 86400, 0.0)
    return None


def _event_age(e: dict, now) -> float | None:
    for k in ("event_date", "published_at", "date"):
        a = age_days(e.get(k), now)
        if a is not None:
            return a
    return None


# ── relevance ────────────────────────────────────────────────────────────────────
_WORD_RE = re.compile(r"[a-z0-9&]+")
_FILLER = {
    "what", "whats", "how", "why", "when", "where", "who", "which", "does", "did", "are", "was", "were", "the", "and", "for", "with", "from", "into", "this", "that",
    "give", "should", "stock", "stocks", "shares", "market", "markets", "indian", "india", "mean", "means", "happen", "happens", "would", "will", "can", "could",
    "latest", "right", "now", "today", "lately", "about", "tell", "look", "looks", "outlook", "impact", "affect", "effect", "doing", "like", "need", "know",
}


def content_words(query: str) -> list[str]:
    return [w for w in _WORD_RE.findall((query or "").lower()) if len(w) >= 3 and w not in _FILLER]


def mentions(text: str, terms: list[str]) -> bool:
    t = (text or "").lower()
    for term in terms:
        if re.search(r"(?<![a-z0-9])" + re.escape(term.lower()) + r"(?![a-z0-9])", t):
            return True
    return False


_SECTOR_TERMS = {
    "banking": ["bank", "banks", "banking", "lender", "lenders", "credit", "loan", "loans", "nbfc", "rbi"],
    "it": ["it services", "software", "infosys", "tcs", "wipro", "hcltech", "tech mahindra", "nasdaq", "it sector", "it stocks", "it spending", "it industry", "it firms",
           "it companies", "it exporters", "it demand", "it majors", "nifty it"],
    "technology": ["technology", "tech", "software", "ai"],
    "defence": ["defence", "defense", "hal", "bel", "missile", "navy", "army"],
    "energy": ["energy", "oil", "gas", "crude", "power", "renewable"],
    "pharma": ["pharma", "drug", "usfda", "api", "medicine"],
    "auto": ["auto", "automobile", "vehicle", "ev", "tractor"],
    "fmcg": ["fmcg", "consumer", "staples"],
    "metals": ["metal", "metals", "steel", "aluminium", "copper"],
    "realty": ["realty", "real estate", "housing", "property"],
    "telecom": ["telecom", "5g", "spectrum", "airtel", "jio"],
    "power": ["power", "electricity", "discom"],
    "finance": ["finance", "nbfc", "lending", "insurance"],
    "logistics": ["logistics", "freight", "port", "shipping"],
    "railway": ["railway", "railways", "rail"],
    "infrastructure": ["infrastructure", "infra", "capex", "roads"],
}


def topic_terms(entities: dict) -> list[str]:
    out: list[str] = []
    for s in entities.get("sectors") or []:
        out += _SECTOR_TERMS.get(s.lower(), [s])
    out += list(entities.get("policies") or [])
    return list(dict.fromkeys(out))


# Macro words a question can carry without naming a sector or policy ("a weaker rupee", "higher crude oil prices"): each maps to the phrases a relevant item uses.
_MACRO_VOCAB = {
    "rupee": ["rupee", "usd/inr", "usdinr", "dollar"],
    "dollar": ["dollar", "usd/inr", "rupee"],
    "crude": ["crude", "oil price", "brent", "opec"],
    "brent": ["brent", "crude", "opec"],
    "inflation": ["inflation", "cpi", "wpi"],
    "gdp": ["gdp", "economic growth"],
    "fii": ["fii", "fpi", "foreign institutional", "foreign portfolio"],
    "fpi": ["fpi", "fii", "foreign portfolio"],
    "repo": ["repo", "rate cut", "rate hike", "rbi", "monetary policy"],
    "fed": ["federal reserve", "fed rate", "fomc"],
}


def topic_search_terms(query: str, entities: dict) -> list[str]:
    """Terms a topic question (sector / policy / macro) should be searched and judged by: the named sector's and policy's own vocabulary plus any macro vocabulary
    in the question. Replaces searching on every raw query word, which included 2-letter words like "it" (a substring of almost any title) and let unrelated
    high-impact events win. Event.sectors tags are NOT used: they are model-assigned and unreliable (an RBI crypto article was tagged IT)."""
    out = topic_terms(entities)
    words = set(_WORD_RE.findall((query or "").lower()))
    for key, phrases in _MACRO_VOCAB.items():
        if key in words:
            out += phrases
    return list(dict.fromkeys(out))


def _relevant_topic_item(text: str, terms: list[str], words: list[str]) -> bool:
    if terms:
        return mentions(text, terms)
    hits = {w for w in words if mentions(text, [w])}
    return len(hits) >= 2


def company_terms(symbols: list[str]) -> list[str]:
    """Names a news item can use for these companies, from the same alias set entity matching uses, minus aliases that are ordinary commodity words."""
    from app.api.companies import _NSE_UNIVERSE
    from app.services.ai_search.entities import _company_aliases, _is_common_word_alias
    wanted = set(symbols)
    out: list[str] = []
    for co in _NSE_UNIVERSE:
        if co["symbol"] in wanted:
            out += [a for a in _company_aliases(co) if not _is_common_word_alias(a)]
    return list(dict.fromkeys(out))


def _tagged_to(event: dict, symbols: list[str]) -> bool:
    tagged = {c.get("symbol") for c in (event.get("companies") or []) if isinstance(c, dict)}
    return bool(tagged & set(symbols))


def filter_bundle(bundle, plan: RetrievalPlan, query: str, entities: dict, now: datetime | None = None) -> dict:
    """Removes stale and irrelevant items from the bundle IN PLACE and returns a report of what was dropped and why. Events/announcements/news only; policies are kept
    only when the question named a policy and the item mentions it."""
    now = now or datetime.now(timezone.utc)
    if getattr(bundle, "rank_trace", None) is None:       # minimal stand-in bundles (tests) predate the ranking trace
        bundle.rank_trace = {}
    limits = MAX_AGE_DAYS[plan.age_key]
    symbols = [c for c in (entities.get("companies") or []) if c]
    words = content_words(query)
    terms = topic_search_terms(query, entities)
    report: dict = {"plan": plan.kind, "events": {}, "news": {}, "announcements": {}, "policies": {}}

    from app.api.companies import _NSE_UNIVERSE as UNIVERSE

    # events
    kept, stale, irrelevant, tips, filings = [], 0, 0, 0, 0
    for e in bundle.events:
        if plan.events == "none":
            irrelevant += 1
            continue
        if scope.is_tips_article(e.get("title", ""), e.get("summary", "")):
            tips += 1                    # a recommendation article is not evidence that anything happened
            continue
        if plan.kind in ("topic", "explanation") and not scope.eligible_for_sector(scope.normalize("event", e))[0]:
            filings += 1                 # a single-company filing cannot support a sector or market question
            continue
        if plan.events == "tagged" and not _tagged_to(e, symbols):
            irrelevant += 1
            continue
        if plan.events == "words" and not _relevant_topic_item(f"{e.get('title', '')} {e.get('summary', '')}", terms, words):
            irrelevant += 1
            continue
        a = _event_age(e, now)
        if a is not None and limits["events"] and a > limits["events"]:
            stale += 1
            continue
        kept.append(e)
    report["events"] = {"kept": len(kept), "dropped_stale": stale, "dropped_irrelevant": irrelevant, "dropped_tips": tips, "dropped_single_company_filing": filings}
    # Step 3.4G.1: the survivors are ranked (coverage, recency, substance, impact; near-duplicates deferred; per company for comparisons) BEFORE the bounded selection, instead of taking the first 10
    # of an impact-ordered list.
    from app.services.ai_search import evidence_ranking as ranking
    bundle.events, ev_trace = ranking.rank_events(kept, query, entities, plan, now)
    bundle.rank_trace["events"] = ev_trace
    report["events"]["selected"] = len(bundle.events)

    # news
    kept, stale, irrelevant, undated, tips, filings = [], 0, 0, 0, 0, 0
    for n in bundle.news:
        text = f"{n.get('headline', '')} {n.get('summary', '')}"
        if plan.news == "none":
            irrelevant += 1
            continue
        if scope.is_tips_article(n.get("headline", ""), n.get("summary", "")):
            tips += 1
            continue
        if plan.news == "words" and not scope.eligible_for_sector(scope.normalize("news", n))[0]:
            filings += 1
            continue
        # company-scoped: the item must use the registered name or symbol; a bare brand alias, or a brand inside another entity's name ("Kotak Institutional
        # Equities"), is not a fact about the company.
        if plan.news == "entity" and not any(scope.eligible_for_company(scope.normalize("news", n), s, UNIVERSE)[0] for s in symbols):
            irrelevant += 1
            continue
        if plan.news == "words" and not _relevant_topic_item(text, terms, words):
            irrelevant += 1
            continue
        a = age_days(n.get("published_at"), now)
        if a is None and plan.news == "entity":
            undated += 1               # a company-scoped claim needs a date; an undated item cannot be shown as recent
            continue
        if a is not None and limits["news"] and a > limits["news"]:
            stale += 1
            continue
        kept.append(n)
    report["news"] = {"kept": len(kept), "dropped_stale": stale, "dropped_irrelevant": irrelevant, "dropped_undated": undated, "dropped_tips": tips, "dropped_single_company_filing": filings}
    bundle.news, news_trace = ranking.rank_news(kept, query, entities, plan, now)
    bundle.rank_trace["news"] = news_trace
    report["news"]["selected"] = len(bundle.news)

    # announcements
    kept, stale = [], 0
    for a_row in bundle.announcements or []:
        a = age_days(a_row.get("announcement_date"), now)
        if a is not None and limits["announcements"] and a > limits["announcements"]:
            stale += 1
            continue
        kept.append(a_row)
    report["announcements"] = {"kept": len(kept), "dropped_stale": stale + int(getattr(bundle, "ann_stale", 0) or 0)}
    bundle.announcements = kept

    # policies
    kept, irrelevant = [], 0
    pterms = list(entities.get("policies") or [])
    for p in bundle.policies:
        if pterms and mentions(f"{p.get('title', '')} {p.get('summary', '')} {p.get('ministry', '')}", pterms):
            kept.append(p)
        else:
            irrelevant += 1
    report["policies"] = {"kept": len(kept), "dropped_irrelevant": irrelevant}
    bundle.policies = kept

    # premise: a question phrased as news ("BEL just won a new defence order") asserts an event. It is supported only if eligible evidence about the company mentions that
    # kind of event. Otherwise the model is told the event could not be verified (see EvidenceBundle.premise_notice).
    report["premise"] = {"required": False, "terms": [], "supported": None, "supporting": []}
    if plan.kind in ("company", "comparison"):
        groups = scope.premise_groups(query)
        if groups:
            items = ([scope.normalize("event", e) for e in bundle.events] + [scope.normalize("news", n) for n in bundle.news]
                     + [scope.normalize("announcement", a) for a in bundle.announcements or []])
            supporting = [it["title"][:100] for it in items
                          if any(scope.eligible_for_company(it, s, UNIVERSE)[0] for s in symbols) and scope.supports_premise(it, groups)]
            report["premise"] = {"required": True, "terms": [g[0] for g in groups], "supported": bool(supporting), "supporting": supporting[:5]}
    bundle.premise = report["premise"]
    return report
