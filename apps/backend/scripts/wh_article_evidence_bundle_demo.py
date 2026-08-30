"""
AI Article V2 Phase A — real, shadow-mode demonstration. Builds a real
ArticleEvidenceBundle for the two companies with confirmed real linked
evidence (ICICIBANK, TCS — see artifacts/warehouse_entity_linkage_demonstration.md),
composes the new grounded "What Happened," and prints it next to a real
current AIPE article's own "what_happened" for style/grounding-approach
comparison.

Honest disclosure, not glossed over: no currently-published AIPE article
covers the EXACT same real event as either linked evidence item (checked
directly against all 552 real published articles) — so this is a
same-APPROACH comparison (fact-grounded extraction vs. free-text LLM
narrative), not a same-event fact-check. Never presented as more than
that.
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.db.models.intelligence_article import IntelligenceArticle
from app.services.warehouse.article_evidence_bundle import (
    build_article_evidence_bundle, claims_from_what_happened, compose_what_happened_from_evidence,
)
from app.services.warehouse.numeric_validation import build_allowed_values, extract_numeric_claims, validate_numeric_claims
from app.services.warehouse.why_it_matters import build_why_it_matters, select_relevant_financial_facts


async def main() -> None:
    for symbol in ["ICICIBANK", "TCS", "YESBANK"]:
        async with AsyncSessionLocal() as db:
            bundle = await build_article_evidence_bundle(db, symbol)
        print(f"\n=== {symbol} — real ArticleEvidenceBundle ===")
        print(f"resolved={bundle.resolved}  entity_id={bundle.entity_id}  company_name={bundle.company_name}")
        print(f"real linked evidence count: {len(bundle.evidence)}")
        for e in bundle.evidence[:3]:
            print(f"  - [{e.source_type}] {e.published_at}  {e.title!r:.120}")
        print(f"real price_move_pct: {bundle.price_move_pct}")
        print(f"marketripple_score: {bundle.marketripple_score}  (deliberately always None, see module docstring)")
        print(f"\nreal financial_context (Phase B — quality-passed FinancialFact rows only):")
        fc = bundle.financial_context
        if fc is None or not fc.has_real_facts:
            print(f"  <none> — has_real_facts=False (no verified facts for this symbol, or all excluded by quality)")
        else:
            print(f"  as_of={fc.as_of}")
            for f in fc.facts:
                print(f"  - {f.metric_name} ({f.metric_code}) = {f.value} {f.unit}  [{f.quality_status}]")
        print(f"\nGROUNDED What Happened (code-composed, real evidence only):")
        print(f"  {compose_what_happened_from_evidence(bundle)}")
        print(f"\nreal claims (FACT-only today):")
        for c in claims_from_what_happened(bundle):
            print(f"  - [{c.claim_type}] {c.text}  evidence_ids={c.evidence_ids}")

        # Phase B — real, live LLM call. Print full inspection detail, not
        # just pass/fail: the allowed-number set it was checked against,
        # the resulting claims/provenance, attempt count, and (if omitted)
        # exactly why.
        selected_facts = select_relevant_financial_facts(bundle.financial_context)
        allowed = build_allowed_values(bundle, bundle.evidence[:3])
        print(f"\nWhy It Matters — real LLM call, constrained to the bundle above:")
        print(f"  facts offered to the prompt ({len(selected_facts)} of {len(fc.facts) if fc else 0} verified): "
              f"{[f.metric_code for f in selected_facts]}")
        print(f"  allowed-number set: {[(round(a.value, 4), a.kind, a.source) for a in allowed]}")
        wim = await build_why_it_matters(bundle)
        print(f"  status={wim.status}  attempts={wim.attempts}")
        if wim.text:
            print(f"  generated text: {wim.text}")
            print(f"  numbers extracted from that text: {extract_numeric_claims(wim.text)}")
            for c in wim.claims:
                print(f"  - claim [{c.claim_type}] {c.text}  evidence_ids={c.evidence_ids}  financial_fact_ids={c.financial_fact_ids}")
        else:
            print(f"  <omitted> — validation_errors={wim.validation_errors}")

    # Step 5 (owner's acceptance gate) — adversarial injection: take a real
    # allowed set and confirm a deliberately unsupported number is rejected
    # and discarded, independent of any live LLM variance.
    print("\n\n=== Adversarial check: a deliberately unsupported number must be rejected ===")
    async with AsyncSessionLocal() as db:
        icici_bundle = await build_article_evidence_bundle(db, "ICICIBANK")
    icici_allowed = build_allowed_values(icici_bundle, icici_bundle.evidence[:3])
    injected_text = "ICICI Bank's ROA came in at an implausible 47.5%, far above any real reported figure."
    passed, errors = validate_numeric_claims(injected_text, icici_allowed)
    print(f"  injected text: {injected_text!r}")
    print(f"  passed={passed}  rejected_numbers={errors}")
    assert passed is False and any(e["raw_text"].strip() == "47.5%" for e in errors), "adversarial injection was NOT rejected — real bug"
    print("  CONFIRMED: the fabricated number was rejected, not published.")

    print("\n\n=== For comparison: a REAL current AIPE article's what_happened (different real event, same illustrative purpose) ===")
    async with AsyncSessionLocal() as db:
        row = (await db.execute(
            select(IntelligenceArticle.headline, IntelligenceArticle.what_happened, IntelligenceArticle.sources)
            .where(IntelligenceArticle.status == "published")
            .limit(1)
        )).first()
        if row:
            headline, what_happened, sources = row
            print(f"headline: {headline}")
            print(f"sources field (real, as stored): {sources}")
            print(f"what_happened (LLM-generated, current pipeline):\n  {what_happened}")


if __name__ == "__main__":
    asyncio.run(main())
