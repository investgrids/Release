"""
Deterministic, explainable evidence ranking (Step 3.4G.1).

Problem (Step 3.4G diagnosis): candidates were cut by a stored `impact_score` with a hard SQL LIMIT, and the live-news scan window was the newest 20 or 60 items depending on cache state, BEFORE any
question-aware ranking. Strong, on-topic items sat beyond the cut; single-company filings that the filter later dropped consumed the slots.

New order: wide candidate pool -> the existing eligibility/age/relevance filter (unchanged) -> this module ranks the survivors -> bounded final selection.

Score (all components 0..1, recorded per item so every selection is explainable):
  coverage   0.50  how many distinct question terms (sector/policy/macro vocabulary, query content words, company names) appear in the TITLE (full weight) or only in the summary (half weight)
  recency    0.25  1 - age/limit within the plan's age window for that kind
  substance  0.15  administrative or routine corporate action -> low; results/earnings/orders/rates/outlook/collaboration style content -> high; otherwise neutral
  impact     0.10  the stored impact_score, normalised; a signal only, never the candidate cutoff
Selection is greedy by score with near-duplicate suppression (title content-word Jaccard >= 0.5 against an already selected item): duplicates are deferred and only fill leftover budget.
Comparison and multi-company questions are selected per company so one side cannot take every slot. No embeddings, no model call, no per-question special cases: the signals are generic categories.
Pure functions, no I/O.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from app.services.ai_search import evidence_filter as EF
from app.services.ai_search import evidence_scope as scope

WEIGHTS = {"coverage": 0.50, "recency": 0.25, "substance": 0.15, "impact": 0.10}
DUP_JACCARD = 0.5
EVENT_BUDGET = 10
NEWS_BUDGET = 10
COMPARISON_PER_COMPANY = 5

_ROUTINE = re.compile(
    r"(?<![a-z])(?:allotment\s+of|esop|employee\s+stock|trading\s+window|investor\s+conference|analyst\s*/?\s*institutional|schedule\s+of\s+(?:meet|analyst|investor)|general\s+updates?|intimation|"
    r"change\s+in\s+(?:management|directorate)|loss\s+of\s+share\s+certificate)(?![a-z])", re.IGNORECASE)
_SUBSTANTIVE = re.compile(
    r"(?<![a-z])(?:results?|earnings|revenue|profit|margins?|orders?|contracts?|wins?|won|acquisition|acquires?|merger|demerger|dividend|buyback|fund\s*raising|guidance|outlook|forecast|rating|"
    r"capacity|expansion|launch\w*|partnership|collaboration|agreement|presentation|crash\w*|rall\w*|surge\w*|jump\w*|declin\w*|slump\w*|repo|rate\s+(?:cut|hike|decision)|mpc|policy|inflation|"
    r"yields?|demand|growth|spending|slowdown)(?![a-z])", re.IGNORECASE)


def substance(title: str, summary: str = "") -> float:
    """-1 administrative, -0.6 routine corporate action, +0.8 substantive, 0 neutral; mapped to 0..1."""
    if scope.is_administrative(title, summary):
        raw = -1.0
    elif _ROUTINE.search(title or ""):
        raw = -0.6
    elif _SUBSTANTIVE.search(title or ""):
        raw = 0.8
    else:
        raw = 0.0
    return round((raw + 1.0) / 2.0, 3)


def query_terms(query: str, entities: dict, kind: str) -> list[str]:
    """Distinct terms an item is judged against: sector/policy/macro vocabulary, query content words and, for company questions, the company's own names."""
    terms = list(EF.topic_search_terms(query, entities))
    terms += EF.content_words(query)
    symbols = [c for c in (entities.get("companies") or []) if c]
    if symbols and kind in ("company", "comparison"):
        terms += EF.company_terms(symbols)
    return list(dict.fromkeys(t.lower() for t in terms if t))


def coverage(title: str, summary: str, terms: list[str]) -> float:
    if not terms:
        return 0.5
    in_title = {t for t in terms if EF.mentions(title or "", [t])}
    in_summary = {t for t in terms if t not in in_title and EF.mentions(summary or "", [t])}
    denom = 2 * min(len(terms), 3)
    return round(min(1.0, (2 * len(in_title) + len(in_summary)) / denom), 3)


def _norm_impact(v) -> float:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return 0.5
    x = x / 10.0 if x <= 10 else x / 100.0
    return round(max(0.0, min(1.0, x)), 3)


def _recency(age: float | None, limit_days: int | None) -> float:
    if age is None:
        return 0.4                      # undated: neither fresh nor stale
    limit = float(limit_days or 30)
    return round(max(0.0, 1.0 - age / limit), 3)


_BOILERPLATE = re.compile(r"^.*?\bhas\s+informed\s+the\s+exchange\s+(?:about|regarding)\b", re.IGNORECASE | re.DOTALL)


def dedup_key(title: str) -> str:
    """Title with exchange-filing boilerplate removed ("X Limited has informed the Exchange about ..."), so two different filings by the same company do not look like duplicates of each other."""
    t = _BOILERPLATE.sub(" ", title or "")
    return re.sub(r"\blimited\b", " ", t, flags=re.IGNORECASE)


def _title_jaccard(a: str, b: str) -> float:
    wa, wb = set(EF.content_words(dedup_key(a))), set(EF.content_words(dedup_key(b)))
    return len(wa & wb) / max(1, len(wa | wb))


def score_item(*, title: str, summary: str, age: float | None, limit_days: int | None, impact, terms: list[str]) -> dict:
    comp = {"coverage": coverage(title, summary, terms), "recency": _recency(age, limit_days), "substance": substance(title, summary), "impact": _norm_impact(impact)}
    comp["score"] = round(sum(WEIGHTS[k] * comp[k] for k in WEIGHTS), 4)
    return comp


def select(rows: list[dict], scored: list[dict], budget: int) -> tuple[list[dict], list[dict]]:
    """Greedy by score with near-duplicate suppression. Returns (selected rows, trace). Ties break on recency, then original order, so the result is deterministic."""
    order = sorted(range(len(rows)), key=lambda i: (-scored[i]["score"], -scored[i]["recency"], i))
    chosen: list[int] = []
    deferred: list[int] = []
    for i in order:
        if len(chosen) >= budget:
            break
        t = scored[i]["_title"]
        if any(_title_jaccard(t, scored[j]["_title"]) >= DUP_JACCARD for j in chosen):
            deferred.append(i)
            continue
        chosen.append(i)
    # The budget is a ceiling, not a quota: near-duplicates are never used to fill leftover slots (they stay in the trace, flagged), so a thin pool yields fewer, more distinct items.
    chosen_set = set(chosen)
    trace = []
    for rank, i in enumerate(order[:40], 1):
        s = scored[i]
        trace.append({"id": rows[i].get("id"), "title": s["_title"][:110], "rank": rank, "selected": i in chosen_set, "duplicate_deferred": i in deferred,
                      **{k: s[k] for k in ("score", "coverage", "recency", "substance", "impact")}})
    return [rows[i] for i in chosen], trace


def _age_event(e: dict, now) -> float | None:
    return EF._event_age(e, now)


def rank_events(rows: list[dict], query: str, entities: dict, plan, now: datetime | None = None) -> tuple[list[dict], list[dict]]:
    now = now or datetime.now(timezone.utc)
    limit = EF.MAX_AGE_DAYS[plan.age_key]["events"]
    terms = query_terms(query, entities, plan.kind)
    symbols = [c for c in (entities.get("companies") or []) if c]

    def scored_for(rs):
        out = []
        for e in rs:
            s = score_item(title=e.get("title", ""), summary=e.get("summary", ""), age=_age_event(e, now), limit_days=limit, impact=e.get("impact_score"), terms=terms)
            s["_title"] = e.get("title", "")
            out.append(s)
        return out

    if plan.events == "tagged" and len(symbols) >= 2:
        picked, trace, seen = [], [], set()
        for sym in symbols[:3]:
            mine = [e for e in rows if EF._tagged_to(e, [sym]) and str(e.get("id")) not in seen]
            sel, tr = select(mine, scored_for(mine), COMPARISON_PER_COMPANY)
            for e in sel:
                seen.add(str(e.get("id")))
            picked += sel
            trace += [{**t, "company": sym} for t in tr]
        return picked, trace
    return select(rows, scored_for(rows), EVENT_BUDGET)


def rank_news(rows: list[dict], query: str, entities: dict, plan, now: datetime | None = None) -> tuple[list[dict], list[dict]]:
    now = now or datetime.now(timezone.utc)
    limit = EF.MAX_AGE_DAYS[plan.age_key]["news"]
    terms = query_terms(query, entities, plan.kind)
    scored = []
    for n in rows:
        s = score_item(title=n.get("headline", ""), summary=n.get("summary", ""), age=EF.age_days(n.get("published_at"), now), limit_days=limit, impact=n.get("impact_score"), terms=terms)
        s["_title"] = n.get("headline", "")
        scored.append(s)
    return select(rows, scored, NEWS_BUDGET)


def rank_announcements(rows: list[dict], query: str, entities: dict, plan, budget: int, now: datetime | None = None) -> tuple[list[dict], list[dict], int]:
    """Drops announcements outside the age window (counted, so the filter report stays honest), then ranks the rest: substantive and question-relevant filings ahead of administrative recency."""
    now = now or datetime.now(timezone.utc)
    limit = EF.MAX_AGE_DAYS[plan.age_key]["announcements"]
    terms = query_terms(query, entities, plan.kind)
    fresh, stale = [], 0
    for a in rows:
        age = EF.age_days(a.get("announcement_date"), now)
        if age is not None and limit and age > limit:
            stale += 1
            continue
        fresh.append(a)
    scored = []
    for a in fresh:
        text = " ".join(str(a.get(k) or "") for k in ("category", "description"))
        s = score_item(title=a.get("subject", "") or "", summary=text, age=EF.age_days(a.get("announcement_date"), now), limit_days=limit, impact=a.get("impact_score"), terms=terms)
        # announcement subjects are boilerplate ("X has informed the Exchange about ..."): substance and coverage are judged on the subject AND the category/description
        s["substance"] = substance(f"{a.get('subject') or ''} {a.get('category') or ''}", a.get("description") or "")
        s["score"] = round(sum(WEIGHTS[k] * s[k] for k in WEIGHTS), 4)
        s["_title"] = a.get("subject", "") or ""
        scored.append(s)
    sel, trace = select(fresh, scored, budget)
    return sel, trace, stale
