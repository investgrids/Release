"""
Owner-authorized follow-up probe (2026-08-30), before freezing Phase B:
does select_relevant_financial_facts() inject NPA/CET1/ROA merely
because a company is a bank, even when the real triggering event has
nothing to do with financial health?

5 real Banking-sector symbols, each confirmed to have real FinancialFact
rows AND whose only real linked evidence is genuinely non-financial-
themed (branch opening, AGM outcome, ESOP allotment, BRSR/ESG
disclosure, a market-surveillance volume query) -- verified via
wh_checkpoint_explore.py-style querying before this script was written,
not assumed.
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")

from app.db.session import AsyncSessionLocal
from app.services.warehouse.article_evidence_bundle import build_article_evidence_bundle, compose_what_happened_from_evidence
from app.services.warehouse.why_it_matters import build_why_it_matters, select_relevant_financial_facts

SYMBOLS = ["CUB", "BANDHANBNK", "FEDERALBNK", "J&KBANK", "IDBI"]


async def run_one(symbol: str) -> None:
    print(f"\n{'=' * 100}\n{symbol}\n{'=' * 100}")
    async with AsyncSessionLocal() as db:
        bundle = await build_article_evidence_bundle(db, symbol)
        if not bundle.resolved:
            print("  UNRESOLVED -- skipping")
            return
        print(f"company: {bundle.company_name}")
        print(f"evidence used (top-{len(bundle.evidence)}):")
        for e in bundle.evidence:
            print(f"  [{e.source_type}] {e.title!r:.140}")
        print(f"\nWhat Happened: {compose_what_happened_from_evidence(bundle)}")

        fc = bundle.financial_context
        print(f"\navailable FinancialFacts: {'none' if not fc or not fc.has_real_facts else len(fc.facts)}")
        selected = select_relevant_financial_facts(fc)
        print(f"selected FinancialFacts for the prompt: {[f.metric_code for f in selected]}")

        wim = await build_why_it_matters(bundle)
        print(f"\nWhy It Matters: status={wim.status}")
        if wim.text:
            print(f"  text: {wim.text}")
            print(f"  claims:")
            for c in wim.claims:
                print(f"    - [{c.claim_type}] {c.text}  financial_fact_ids={c.financial_fact_ids}")
        else:
            print(f"  <omitted> validation_errors={wim.validation_errors}")


async def main() -> None:
    for symbol in SYMBOLS:
        try:
            await run_one(symbol)
        except Exception as exc:
            print(f"{symbol} -- ERROR: {exc!r}")


if __name__ == "__main__":
    asyncio.run(main())
