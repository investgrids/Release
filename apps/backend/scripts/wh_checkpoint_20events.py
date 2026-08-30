"""
Phase B shadow-quality checkpoint (owner-authorized 2026-08-30). Runs 20
real, diverse Warehouse events through the full grounded pipeline and
prints the complete trace for manual qualitative review -- this script
does NOT classify results itself (that requires human judgment on
relevance/usefulness), it only captures every real, inspectable step:

  trigger event -> canonical company -> ranked evidence + reasons
  -> selected evidence -> deterministic What Happened
  -> available FinancialFacts -> selected FinancialFacts
  -> Why It Matters -> FACT/INTERPRETATION claims -> evidence/fact IDs
  -> extracted numbers -> allowed numbers -> validation result

The 20 symbols were chosen from real linked-evidence keyword buckets
(see wh_checkpoint_explore.py's output) to deliberately span strong,
partial, and sparse evidence/financial-fact coverage -- not cherry-picked
for companies that already look good (ICICIBANK-style richness is the
exception in this sample, not the norm).
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.db.models.intelligence_article import IntelligenceArticle
from app.services.warehouse.article_evidence_bundle import build_article_evidence_bundle, claims_from_what_happened, compose_what_happened_from_evidence
from app.services.warehouse.numeric_validation import build_allowed_values, extract_numeric_claims
from app.services.warehouse.read_service import get_verified_financial_context
from app.services.warehouse.why_it_matters import build_why_it_matters, select_relevant_financial_facts

# (symbol, category) -- category is the owner's checkpoint bucket, not derived from code
EVENTS = [
    ("HEG", "earnings_results"),
    ("UCOBANK", "earnings_results"),
    ("MACPOWER", "earnings_results"),
    ("RATNAMANI", "orders_contracts"),
    ("KRYSTAL", "orders_contracts"),
    ("S&SPOWER", "orders_contracts"),
    ("TCS", "partnerships_deals"),
    ("OIL", "partnerships_deals"),
    ("CANBK", "fundraising_debt"),
    ("ASHIANA", "fundraising_debt"),
    ("URBANCO", "regulatory_compliance"),
    ("BHARATRAS", "regulatory_compliance"),
    ("CTE", "management_board"),
    ("MWL", "management_board"),
    ("GESHIP", "corporate_actions"),
    ("NMDC", "corporate_actions"),
    ("SYNGENE", "mna_investment"),
    ("COALINDIA", "mna_investment"),
    ("MARATHON", "other_surveillance_query"),
    ("SIMBHALS", "other_insolvency_proceeding"),
]


async def _find_similar_published_articles(db, company_name: str | None):
    if not company_name:
        return []
    first_word = company_name.split()[0]
    rows = (await db.execute(
        select(IntelligenceArticle.headline, IntelligenceArticle.created_at)
        .where(IntelligenceArticle.status == "published", IntelligenceArticle.headline.ilike(f"%{first_word}%"))
        .order_by(IntelligenceArticle.created_at.desc())
        .limit(3)
    )).all()
    return rows


async def run_one(symbol: str, category: str) -> None:
    print(f"\n{'=' * 100}\n[{category}] {symbol}\n{'=' * 100}")
    async with AsyncSessionLocal() as db:
        bundle = await build_article_evidence_bundle(db, symbol)

        if not bundle.resolved:
            print("  UNRESOLVED -- symbol did not resolve to a canonical CompanyEntity. Skipping.")
            return

        print(f"canonical company: {bundle.company_name} (entity_id={bundle.entity_id})")

        print(f"\nranked evidence ({len(bundle.ranked_evidence)} total):")
        for r in bundle.ranked_evidence[:5]:
            print(f"  score={r.score:.2f}  reasons={r.reasons}")
            print(f"    [{r.evidence.source_type}] {r.evidence.published_at}  {r.evidence.title!r:.140}")

        print(f"\nselected (top-ranked, up to 3) evidence used for the bundle:")
        for e in bundle.evidence[:3]:
            print(f"  [{e.raw_evidence_id[:8]}] {e.title!r:.140}")

        what_happened = compose_what_happened_from_evidence(bundle)
        print(f"\nWhat Happened (deterministic):\n  {what_happened}")

        fact_claims = claims_from_what_happened(bundle)
        print(f"\nFACT claims from What Happened ({len(fact_claims)}):")
        for c in fact_claims:
            print(f"  - {c.text}  evidence_ids={c.evidence_ids}  financial_fact_ids={c.financial_fact_ids}")

        fc = bundle.financial_context
        print(f"\navailable FinancialFacts: {'none' if not fc or not fc.has_real_facts else f'{len(fc.facts)} verified, as_of={fc.as_of}'}")
        if fc and fc.has_real_facts:
            for f in fc.facts:
                print(f"  - {f.metric_name} ({f.metric_code}) = {f.value} {f.unit}  FY{f.fiscal_year}"
                      + (f"Q{f.fiscal_quarter}" if f.fiscal_quarter else ""))
        selected_facts = select_relevant_financial_facts(fc)
        print(f"selected FinancialFacts for the prompt: {[f.metric_code for f in selected_facts]}")

        allowed = build_allowed_values(bundle, bundle.evidence[:3])
        print(f"allowed-number set ({len(allowed)}): {[(round(a.value, 4), a.kind, a.source) for a in allowed]}")

        wim = await build_why_it_matters(bundle)
        print(f"\nWhy It Matters: status={wim.status}  attempts={wim.attempts}")
        if wim.text:
            print(f"  text: {wim.text}")
            nums = extract_numeric_claims(wim.text)
            print(f"  numbers extracted from text: {[(n.raw_text, n.value, n.kind) for n in nums]}")
            print(f"  claims ({len(wim.claims)}):")
            for c in wim.claims:
                print(f"    - [{c.claim_type}] {c.text}  evidence_ids={c.evidence_ids}  financial_fact_ids={c.financial_fact_ids}")
        else:
            print(f"  <omitted>  validation_errors={wim.validation_errors}")

        similar = await _find_similar_published_articles(db, bundle.company_name)
        print(f"\nrecent published articles mentioning this company (uniqueness check, manual judgment):")
        if not similar:
            print("  none found")
        for headline, created_at in similar:
            print(f"  - [{created_at}] {headline!r}")


async def main() -> None:
    for symbol, category in EVENTS:
        try:
            await run_one(symbol, category)
        except Exception as exc:
            print(f"\n[{category}] {symbol} -- ERROR: {exc!r}")


if __name__ == "__main__":
    asyncio.run(main())
