"""
Article V2 Phase C6 — shadow validation run (owner authorization,
2026-09-01). Runs the real C1 -> C2 -> C3 -> C4 -> C5 -> C6 chain over
the same 120-event cohort every prior checkpoint used. Every real
CREATE_NEW/UPDATE_EXISTING output (SKIP and NO_PUBLICATION are never
composed, by C6's own hard refusal) is composed in full and printed for
manual inspection. Writes NOTHING -- no Newsroom record, no DB mutation.
Real LLM calls for Why It Matters (FULL_ARTICLE only) and for headline
generation (C5's own already-authorized exception to the "no LLM" rule).
"""
from __future__ import annotations

import asyncio
import sys
from collections import Counter

sys.path.insert(0, ".")

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from sqlalchemy import select

from app.db.models.intelligence import EventTriage
from app.db.session import AsyncSessionLocal
from app.services.article_v2.candidate_gate import CANDIDATE, evaluate_candidate
from app.services.article_v2.composer import ComposerRefusal, compose_article
from app.services.article_v2.context_builder import build_context
from app.services.article_v2.decision_engine import FACTUAL_UPDATE, FULL_ARTICLE, decide
from app.services.article_v2.evidence_set_builder import build_evidence_set
from app.services.article_v2.headline_engine import generate_headline
from app.services.article_v2.identity import CREATE_NEW, NO_PUBLICATION, UPDATE_EXISTING, compute_identity, resolve_uniqueness

SAMPLE_SIZE = 120


async def main() -> None:
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            select(EventTriage).order_by(EventTriage.triaged_at.desc()).limit(SAMPLE_SIZE * 2)
        )).scalars().all()
    with_ticker = [r for r in rows if r.tickers][:SAMPLE_SIZE]

    print("=== Re-deriving the real C4-proposed outputs (1 FULL_ARTICLE + 18 FACTUAL_UPDATE expected) ===\n")
    proposals = []
    for row in with_ticker:
        symbol = row.tickers[0]
        async with AsyncSessionLocal() as db:
            candidate = await evaluate_candidate(db, symbol=symbol, event_headline=row.headline, event_id=row.event_id)
        if candidate.outcome != CANDIDATE:
            continue
        async with AsyncSessionLocal() as db:
            es = await build_evidence_set(db, symbol=symbol, event_headline=row.headline, event_id=row.event_id)
        if es.primary_evidence is None:
            continue
        async with AsyncSessionLocal() as db:
            ctx = await build_context(db, es)
        decision = decide(candidate, es, ctx)
        if decision.content_type in (FULL_ARTICLE, FACTUAL_UPDATE):
            proposals.append((row, candidate, es, ctx, decision))

    print(f"Re-derived {len(proposals)} proposed outputs.\n")
    print(f"=== Article V2 Phase C6 shadow run: {len(proposals)} candidates through Identity -> Uniqueness -> Headline -> Composer ===\n")

    known_identities: dict[str, str] = {}
    known_headlines: dict[str, str] = {}
    content_type_counts: Counter[str] = Counter()
    llm_status_counts: Counter[str] = Counter()
    total_llm_attempts = 0
    numeric_failures = 0
    causal_or_predictive_failures = 0
    total_claims = 0
    claims_with_provenance = 0
    section_omission_counts: Counter[str] = Counter()
    word_counts: list[int] = []
    composed = []
    refused = 0

    for i, (row, candidate, es, ctx, decision) in enumerate(proposals, start=1):
        identity = compute_identity(es)
        resolution = resolve_uniqueness(
            identity, c4_publication_action=decision.publication_action,
            c4_matched_article_id=None, known_identities=known_identities,
        )
        if resolution.publication_action == CREATE_NEW:
            known_identities[identity.identity_key] = f"batch-item-{i}-{es.symbol}"

        print(f"[{i:2}] symbol={es.symbol:<12} content_type={decision.content_type:<14} pub_action={resolution.publication_action:<15}")

        if resolution.publication_action not in (CREATE_NEW, UPDATE_EXISTING):
            print(f"     -> not composed ({resolution.publication_action})\n")
            continue

        headline_result = await generate_headline(es, ctx, identity, other_accepted_headlines=known_headlines)
        if headline_result.h1:
            known_headlines[identity.identity_key] = headline_result.h1
        total_llm_attempts += headline_result.attempts

        try:
            article = await compose_article(decision, es, ctx, identity, resolution, headline_result)
        except ComposerRefusal as exc:
            refused += 1
            print(f"     -> COMPOSER REFUSED: {exc}\n")
            continue

        composed.append((es, identity, article))
        content_type_counts[article.content_type] += 1
        llm_status_counts[article.llm_status] += 1
        if article.llm_status != "not_used":
            total_llm_attempts += article.llm_attempts
        if any("unsupported number" in n for n in article.llm_validation_notes):
            numeric_failures += 1
        if any("causal/predictive" in n for n in article.llm_validation_notes):
            causal_or_predictive_failures += 1
        word_counts.append(article.word_count)
        total_claims += len(article.all_claims)
        claims_with_provenance += sum(1 for c in article.all_claims if c.evidence_ids or c.financial_fact_ids)

        expected_full = {"what_happened", "why_it_matters", "verified_context", "what_to_watch", "source_updated"}
        expected_update = {"what_happened", "key_details", "source_updated"}
        expected = expected_full if article.content_type == FULL_ARTICLE else expected_update
        present = {s.name for s in article.sections}
        for missing in expected - present:
            section_omission_counts[f"{article.content_type}:{missing}"] += 1

        print(f"     headline: {article.headline!r}")
        print(f"     llm_status={article.llm_status} attempts={article.llm_attempts} word_count={article.word_count} claims={len(article.all_claims)}")
        for s in article.sections:
            print(f"     -- [{s.name}] {s.text}")
        if article.llm_validation_notes:
            print(f"     validation notes: {article.llm_validation_notes}")
        print()

    print(f"\n\n=== Summary ({len(proposals)} candidates, {len(composed)} composed, {refused} refused) ===")
    print(f"  content_type distribution: {dict(content_type_counts)}")
    print(f"  llm_status distribution: {dict(llm_status_counts)}")
    print(f"  total LLM attempts (headline + why_it_matters): {total_llm_attempts}")
    print(f"  numeric validation failures (why_it_matters): {numeric_failures}")
    print(f"  causal/predictive-language failures (why_it_matters): {causal_or_predictive_failures}")
    print(f"  total claims across all compositions: {total_claims}")
    print(f"  claims with real provenance (evidence_ids or financial_fact_ids): {claims_with_provenance}")
    print(f"  section omissions (expected-but-absent, by content_type:section): {dict(section_omission_counts)}")
    if word_counts:
        print(f"  word counts: min={min(word_counts)} max={max(word_counts)} avg={sum(word_counts)/len(word_counts):.0f}")

    print(f"\n=== ALL {len(composed)} COMPOSED OUTPUTS — headline + section names only (for manual inspection above) ===")
    for es, identity, article in composed:
        print(f"  [{article.content_type:<14}] {es.symbol:<12} {article.headline!r}")
        print(f"      sections: {[s.name for s in article.sections]}  words={article.word_count}")


if __name__ == "__main__":
    asyncio.run(main())
