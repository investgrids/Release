"""
B.5 Gate 2 -- event-specific evidence matching, built per the owner's
explicit 2026-08-30 evening authorization alongside the Gate 1 v4
refinement (b5_entity_resolver_v4.py). Real code against real data, not
a spec -- run against the real EvidenceEntityLink table (619 real rows,
built in Phase 2 of the Warehouse Consumption work) and the real 632-row
NSE RawEvidence corpus.

The owner's invariant, verbatim: "Same company != same event." Gate 1
only proves a real company is unambiguously named. Gate 2 must
separately prove the SPECIFIC event/topic the RSS item describes
corresponds to the SAME specific NSE disclosure -- correct company,
unrelated filing (the "Urban Company" example the owner gave: correct
company, unrelated NSE filing) must FAIL here, even though Gate 1
correctly linked the entity.

Design, precision-first (explicit acceptance bar: zero known wrong-
event matches; ambiguous cases reject, never guess):

1. Category classification, both sides, same fixed taxonomy (the one
   already established in this B.5 workstream's own category list --
   earnings/results, orders/contracts, partnerships/deals, fundraising/
   debt, regulatory/compliance, management/board changes, corporate
   actions, M&A/investment). NSE evidence is classified primarily from
   its own real, structured `desc` field (SEBI LODR disclosure category
   -- queried the real 632-item corpus's full distribution to build this
   mapping; see _NSE_DESC_TO_CATEGORY, every entry traced to a real
   observed desc value, not invented) -- falling back to the same
   keyword classifier as RSS text only when `desc` is None or one of
   the confirmed-vague values ("Updates", "General Updates", "Press
   Release"). RSS text is always keyword-classified (no structured
   category exists for RSS).
2. Candidate NSE evidence for a Gate-1-linked entity_id comes from the
   REAL EvidenceEntityLink table (resolution_method="source_symbol",
   the one real deterministic NSE link this codebase already has),
   narrowed to a +/-5 day window around the RSS item's published_at.
   Date proximity is a candidate FILTER only, never sufficient alone --
   the owner's explicit instruction.
3. PASS requires: the RSS item's own category is real and determined
   (not None/"other"), AND at least one candidate NSE evidence in the
   window shares that exact category. If exactly one such candidate
   exists, it PASSES uniquely. If 2+ share the category (real
   ambiguity -- which specific filing is "the" event), a token-overlap
   score disambiguates; if the top score does not clearly dominate the
   runner-up, Gate 2 REJECTS rather than guess (mirrors Gate 1's own
   ambiguous-stays-unlinked rule, extended to event matching).
4. Zero qualifying candidates -> Gate 2 FAILS (the company is real and
   linked, but no evidence for THIS specific event is attached) --
   this is the correct, intended outcome for a real "Urban Company,
   correct entity, unrelated/nonexistent NSE filing for this topic"
   case, not an error to fix.

Explicitly not built: any LLM-based semantic matching (out of B.5
scope, per the owner's "no new LLM reasoning yet" instruction) --
category classification and token overlap are both plain keyword/regex,
fully deterministic and inspectable.
"""
from __future__ import annotations

import asyncio
import json
import re
import sys
from datetime import timedelta

sys.path.insert(0, ".")

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.db.models.evidence_entity_link import EvidenceEntityLink
from app.db.models.raw_evidence import RawEvidence

_WINDOW_DAYS = 5

# Real desc -> category mapping. Every key is a real value from the 632-
# item NSE corpus (queried 2026-08-30); entries with genuinely mixed/
# ambiguous real-world meaning ("Outcome of Board Meeting" covers both
# results AND ordinary governance business; "General Updates"/"Updates"/
# "Press Release" carry no reliable category signal on their own) are
# deliberately left OUT so those rows fall through to the keyword
# classifier on their own attchmntText/title instead of being guessed.
_NSE_DESC_TO_CATEGORY: dict[str, str] = {
    "bagging/receiving of orders/contracts": "orders_contracts",
    "awarding of order(s)/contract(s)": "orders_contracts",
    "allotment of securities": "fundraising_debt",
    "issue of securities": "fundraising_debt",
    "qualified institutional placement": "fundraising_debt",
    "offer for sale": "fundraising_debt",
    "options to purchase securities": "fundraising_debt",
    "disclosure under sebi takeover regulations": "regulatory_compliance",
    "corporate insolvency resolution process": "regulatory_compliance",
    "trading window": "regulatory_compliance",
    "trading plan under pit": "regulatory_compliance",
    "pendency of litigation(s)/dispute(s) or the outcome impacting the company": "regulatory_compliance",
    "rumour verification - regulation 30(11)": "regulatory_compliance",
    "granting/withdrawal/surrender/cancellation/suspension of key licenses/ regulatory approvals": "regulatory_compliance",
    "credit rating- others": "regulatory_compliance",
    "credit rating- revision": "regulatory_compliance",
    "credit rating- new": "regulatory_compliance",
    "credit rating": "regulatory_compliance",
    "action(s) taken or orders passed": "regulatory_compliance",
    "change in management": "management_board",
    "appointment": "management_board",
    "change in director(s)": "management_board",
    "cessation": "management_board",
    "resignation of director/kmp/smp": "management_board",
    "resignation": "management_board",
    "change in auditors": "management_board",
    "change in company secretary/compliance officer": "management_board",
    "address change": "management_board",
    "name change": "management_board",
    "record date": "corporate_actions",
    "esop/esos/esps": "corporate_actions",
    "dividend": "corporate_actions",
    "amendment to aoa/moa": "corporate_actions",
    "scheme of arrangement": "ma_investment",
    "other restructuring": "ma_investment",
    "acquisition": "ma_investment",
    "diversification/disinvestment": "ma_investment",
}

_KEYWORD_CATEGORIES: dict[str, list[str]] = {
    "earnings": [r"\bq[1-4]\b", "quarterly result", "results for the quarter", "profit", "revenue",
                 "ebitda", "earnings", "net income", "\\bpat\\b", "financial result"],
    "orders_contracts": ["order from", "order for", "bags order", "bagging", "contract", "awarded",
                          "wins order", "project win", "work order"],
    "partnerships_deals": ["partnership", "tie-up", "tie up", "collaborat", "\\bmou\\b",
                            "joint venture", "\\bjv\\b", "alliance"],
    "fundraising_debt": ["raise funds", "fundraise", "\\bqip\\b", "rights issue", "\\bncd\\b", "bond issue",
                          "debenture", "\\bipo\\b", "\\bofs\\b", "stake sale", "divest", "allotment",
                          "offer for sale"],
    "regulatory_compliance": ["\\bsebi\\b", "\\brbi\\b", "regulatory", "compliance", "penalty", "notice",
                               "litigation", "inquiry", "insolvency", "\\bnclt\\b", "investigation"],
    "management_board": ["\\bceo\\b", "\\bcfo\\b", "\\bmd\\b", "director", "resign", "appoint", "board",
                          "management", "chairman", "\\bkmp\\b"],
    "corporate_actions": ["dividend", "bonus issue", "stock split", "buyback", "record date", "\\besop\\b"],
    "ma_investment": ["acquisition", "acquire", "merger", "stake in", "investment in", "takeover",
                       "scheme of arrangement"],
}
_KEYWORD_PATTERNS = {
    cat: re.compile("|".join(kws), re.IGNORECASE) for cat, kws in _KEYWORD_CATEGORIES.items()
}


def classify_keyword(text: str) -> str | None:
    best_cat, best_hits = None, 0
    for cat, pattern in _KEYWORD_PATTERNS.items():
        hits = len(pattern.findall(text or ""))
        if hits > best_hits:
            best_cat, best_hits = cat, hits
    return best_cat


def classify_nse_evidence(desc: str | None, attchmnt_text: str, title: str) -> str | None:
    if desc:
        mapped = _NSE_DESC_TO_CATEGORY.get(desc.strip().lower())
        if mapped:
            return mapped
    return classify_keyword(f"{title} {attchmnt_text}")


_STOPWORDS = {
    "the", "and", "for", "has", "with", "from", "that", "this", "was", "were", "are",
    "its", "their", "have", "will", "been", "which", "about", "into", "over", "amid",
}


def _significant_tokens(text: str) -> set[str]:
    words = re.findall(r"[a-zA-Z]{4,}", (text or "").lower())
    return {w for w in words if w not in _STOPWORDS}


def token_overlap(a: str, b: str) -> float:
    ta, tb = _significant_tokens(a), _significant_tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


async def load_nse_candidates_by_entity() -> dict[str, list[dict]]:
    """entity_id -> list of real NSE RawEvidence rows linked to it via
    the real EvidenceEntityLink table."""
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            select(EvidenceEntityLink.entity_id, RawEvidence.id, RawEvidence.title,
                   RawEvidence.published_at, RawEvidence.raw_payload)
            .join(RawEvidence, RawEvidence.id == EvidenceEntityLink.raw_evidence_id)
            .where(EvidenceEntityLink.relationship_type == "subject")
        )).all()
    by_entity: dict[str, list[dict]] = {}
    for entity_id, ev_id, title, published_at, raw_payload in rows:
        if published_at is None:
            continue
        try:
            payload = json.loads(raw_payload) if raw_payload else {}
        except json.JSONDecodeError:
            payload = {}
        by_entity.setdefault(entity_id, []).append({
            "id": ev_id, "title": title or "", "published_at": published_at,
            "desc": payload.get("desc"), "attchmnt_text": payload.get("attchmntText", ""),
        })
    return by_entity


def run_gate2_for_item(rss_text: str, rss_published_at, entity_id: str,
                        nse_by_entity: dict[str, list[dict]]) -> dict:
    rss_category = classify_keyword(rss_text)
    if rss_category is None:
        return {"status": "FAIL", "reason": "rss_category_undetermined"}

    candidates = nse_by_entity.get(entity_id, [])
    if rss_published_at is None:
        return {"status": "FAIL", "reason": "rss_published_at_missing"}
    window_start = rss_published_at - timedelta(days=_WINDOW_DAYS)
    window_end = rss_published_at + timedelta(days=_WINDOW_DAYS)
    in_window = [c for c in candidates if window_start <= c["published_at"] <= window_end]

    same_category = []
    for c in in_window:
        c_cat = classify_nse_evidence(c["desc"], c["attchmnt_text"], c["title"])
        if c_cat == rss_category:
            same_category.append((c, c_cat))

    if not same_category:
        return {"status": "FAIL", "reason": "no_same_category_evidence_in_window", "rss_category": rss_category}

    if len(same_category) == 1:
        c, cat = same_category[0]
        return {"status": "PASS", "evidence_id": c["id"], "category": cat, "method": "unique_candidate",
                "rss_category": rss_category, "date_delta_days": abs((c["published_at"] - rss_published_at).days)}

    scored = sorted(
        ((c, cat, token_overlap(rss_text, f"{c['title']} {c['attchmnt_text']}")) for c, cat in same_category),
        key=lambda t: t[2], reverse=True,
    )
    top, top_cat, top_score = scored[0]
    runner_score = scored[1][2]
    if top_score > 0 and top_score >= runner_score * 1.5:
        return {"status": "PASS", "evidence_id": top["id"], "category": top_cat, "method": "token_overlap_tiebreak",
                "rss_category": rss_category, "overlap_score": round(top_score, 3),
                "date_delta_days": abs((top["published_at"] - rss_published_at).days)}
    return {"status": "FAIL", "reason": "ambiguous_multiple_same_category_candidates",
            "rss_category": rss_category, "candidate_count": len(same_category)}


async def main() -> None:
    import pickle
    with open("b5_resolver_results_v4.pkl", "rb") as f:
        gate1_results = pickle.load(f)
    async with AsyncSessionLocal() as db:
        rss_rows = {r.id: r.published_at for r in
                    (await db.execute(select(RawEvidence.id, RawEvidence.published_at)
                                       .where(RawEvidence.source_type == "rss"))).all()}
    nse_by_entity = await load_nse_candidates_by_entity()
    print(f"real entities with >=1 linked NSE evidence: {len(nse_by_entity)}")

    single = [r for r in gate1_results if len(r["matches"]) == 1]
    outcomes = []
    for r in single:
        entity_id = r["matches"][0]["entity_id"]
        rss_text = f"{r['title']} {r['summary']}"
        published_at = rss_rows.get(r["id"])
        result = run_gate2_for_item(rss_text, published_at, entity_id, nse_by_entity)
        outcomes.append({"id": r["id"], "title": r["title"], "entity_id": entity_id, **result})

    passed = [o for o in outcomes if o["status"] == "PASS"]
    failed = [o for o in outcomes if o["status"] == "FAIL"]
    print(f"Gate-1-linked single-entity items run through Gate 2: {len(outcomes)}")
    print(f"  Gate 2 PASS (event confirmed): {len(passed)}")
    print(f"  Gate 2 FAIL (no confirmed same-event evidence): {len(failed)}")
    fail_reasons: dict[str, int] = {}
    for o in failed:
        fail_reasons[o["reason"]] = fail_reasons.get(o["reason"], 0) + 1
    print("  FAIL reason breakdown:", fail_reasons)

    import pickle as pkl
    with open("b5_gate2_results.pkl", "wb") as f:
        pkl.dump(outcomes, f)
    print("full Gate 2 results pickled to b5_gate2_results.pkl")


if __name__ == "__main__":
    asyncio.run(main())
