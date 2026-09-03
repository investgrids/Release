"""
B.5 design support (owner-authorized 2026-08-30) -- pulls the real RSS
RawEvidence corpus, extracts real title+summary+source from raw_payload,
and buckets into the 10 requested benchmark categories via real keyword
matching (a first pass to help pick a diverse 100-item sample; final
category assignment and all entity/event labeling is done by hand
against the real text, not trusted from this bucketing alone).
"""
from __future__ import annotations

import asyncio
import json
import sys

sys.path.insert(0, ".")

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.db.models.raw_evidence import RawEvidence

_CATEGORY_KEYWORDS = {
    "earnings": ["q1 ", "q2 ", "q3 ", "q4 ", "results", "profit", "net profit", "revenue rises", "earnings"],
    "orders_contracts": ["bags order", "wins order", "contract", "order from", "order worth", "awarded"],
    "acquisitions": ["acqui", "stake in", "buys ", "merger", "amalgamat", "takeover"],
    "management_changes": ["appoint", "resign", "steps down", "ceo", "cfo", "md &", "managing director", "chairman"],
    "dividends": ["dividend", "bonus share", "buyback", "record date", "split"],
    "stock_moves": ["shares surge", "shares jump", "shares rally", "shares fall", "shares slump", "stock hits", "52-week", "circuit"],
    "regulatory": ["sebi", "rbi ", "compliance", "probe", "penalty", "show cause", "regulator"],
    "macro": ["nifty", "sensex", "fii", "dii", "rupee", "inflation", "gdp", "fed ", "crude oil", "bitcoin", "market wrap", "d-street", "dalal street"],
}


async def main() -> None:
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            select(RawEvidence.id, RawEvidence.title, RawEvidence.raw_payload, RawEvidence.published_at)
            .where(RawEvidence.source_type == "rss")
        )).all()

    print(f"total RSS rows: {len(rows)}\n")
    bucketed: dict[str, list] = {k: [] for k in _CATEGORY_KEYWORDS}
    bucketed["multi_company_or_uncategorized"] = []

    for r in rows:
        try:
            payload = json.loads(r.raw_payload) if r.raw_payload else {}
        except json.JSONDecodeError:
            payload = {}
        summary = payload.get("summary", "")
        source = payload.get("source", "")
        text = f"{r.title or ''} {summary}".lower()

        matched = False
        for cat, kws in _CATEGORY_KEYWORDS.items():
            if any(kw in text for kw in kws):
                bucketed[cat].append((r.id, r.title, summary, source, r.published_at))
                matched = True
                break
        if not matched:
            bucketed["multi_company_or_uncategorized"].append((r.id, r.title, summary, source, r.published_at))

    for cat, items in bucketed.items():
        print(f"=== {cat} ({len(items)}) ===")
        for item in items[:15]:
            print(f"  [{item[0][:8]}] {item[1][:100]!r}  src={item[3]}  pub={item[4]}")
        print()


if __name__ == "__main__":
    asyncio.run(main())
