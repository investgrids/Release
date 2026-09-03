"""One-off exploration script for the Phase B shadow-quality checkpoint
(owner-authorized 2026-08-30). Buckets real linked evidence titles into
candidate event categories via keyword matching, and reports each
candidate entity's evidence count + financial-fact coverage so a diverse
strong/partial/sparse sample of 20 real events can be picked deliberately,
not just taken from whichever companies happen to have the richest data."""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")

from sqlalchemy import func, select

from app.db.models.company_entity import CompanyEntity
from app.db.models.evidence_entity_link import EvidenceEntityLink
from app.db.models.financial_fact import FinancialFact
from app.db.models.raw_evidence import RawEvidence
from app.db.session import AsyncSessionLocal

_CATEGORY_KEYWORDS = {
    "earnings_results": ["financial results", "unaudited", "audited", "board meeting intimation", "outcome of board meeting"],
    "orders_contracts": ["bagging", "receiving of order", "order", "contract", "loi", "letter of intent"],
    "partnerships_deals": ["partner", "partnership", "collaborat", "mou", "memorandum of understanding", "tie-up", "tie up"],
    "fundraising_debt": ["preferential", "rights issue", "qip", "debenture", "ncd", "bond", "note", "raise", "fund raising", "fund-raising"],
    "regulatory_compliance": ["regulation 30", "regulation 29", "sast", "insider trading", "show cause", "penalty", "compliance"],
    "management_board": ["resignation", "appointment of", "cessation", "director", "key managerial", "kmp"],
    "corporate_actions": ["dividend", "bonus", "split", "buyback", "record date", "book closure"],
    "mna_investment": ["acquisition", "amalgamation", "merger", "stake", "investment in", "subsidiary", "divest"],
}


async def main() -> None:
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            select(RawEvidence.id, RawEvidence.title, RawEvidence.published_at, EvidenceEntityLink.entity_id,
                   CompanyEntity.symbol, CompanyEntity.company_name, CompanyEntity.sector)
            .join(EvidenceEntityLink, EvidenceEntityLink.raw_evidence_id == RawEvidence.id)
            .join(CompanyEntity, CompanyEntity.entity_id == EvidenceEntityLink.entity_id)
            .where(RawEvidence.title.is_not(None))
        )).all()

        fact_counts = dict((await db.execute(
            select(FinancialFact.symbol, func.count()).group_by(FinancialFact.symbol)
        )).all())

        evidence_counts: dict[str, int] = {}
        for r in rows:
            evidence_counts[r.symbol] = evidence_counts.get(r.symbol, 0) + 1

        print(f"total rows scanned: {len(rows)}\n")
        for cat, keywords in _CATEGORY_KEYWORDS.items():
            print(f"=== {cat} ===")
            seen_symbols = set()
            for r in rows:
                title_lower = (r.title or "").lower()
                if any(kw in title_lower for kw in keywords):
                    if r.symbol in seen_symbols:
                        continue
                    seen_symbols.add(r.symbol)
                    print(f"  [{r.symbol}] ev_count={evidence_counts.get(r.symbol,0)} facts={fact_counts.get(r.symbol,0)} "
                          f"sector={r.sector}  {r.published_at}  {r.title[:100]!r}")
            print()


if __name__ == "__main__":
    asyncio.run(main())
