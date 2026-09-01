"""
Article V2 Phase C8 -- production-hardening shadow rerun (owner
authorization, 2026-09-01). Runs the complete C1 -> C8 pipeline:

  C1 -> C2 -> C3 -> C4 -> C5 (identity/uniqueness)
    -> C8.1 publication-tier classification
    -> ARTICLE only: C8.2-hardened headline generation
    -> C8.3 batch-wide final uniqueness closure (may downgrade an
       ARTICLE to EVENT_ONLY if it's still indistinguishable from
       another ARTICLE after every real-fact repair)
    -> C8.4-gated composition for whatever survives as ARTICLE

Per the owner's explicit architectural decision, EVENT_ONLY and REJECT
candidates never reach headline generation or composition at all -- the
Event itself is the canonical object for those, not a generated page.
Writes NOTHING to any production table.

Takes --sample-size and --skip (to run a genuinely different, second
cohort rather than the same 500 events, for the owner's requested
generalization check) plus --detail-out for the full per-ARTICLE dump.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from collections import Counter

sys.path.insert(0, ".")

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from sqlalchemy import select

from app.db.models.intelligence import EventTriage
from app.db.session import AsyncSessionLocal
from app.services.aipe.duplicate_detector import _jaccard, _tokenize
from app.services.article_v2.candidate_gate import CANDIDATE, evaluate_candidate
from app.services.article_v2.candidate_gate import SKIP as C1_SKIP
from app.services.article_v2.composer import ComposerRefusal, compose_article
from app.services.article_v2.context_builder import build_context
from app.services.article_v2.decision_engine import FACTUAL_UPDATE, FULL_ARTICLE, decide
from app.services.article_v2.evidence_set_builder import build_evidence_set
from app.services.article_v2.headline_engine import finalize_batch_uniqueness, generate_headline
from app.services.article_v2.identity import CREATE_NEW, UPDATE_EXISTING, compute_identity, resolve_uniqueness
from app.services.article_v2.publication_tier import ARTICLE, EVENT_ONLY, REJECT, classify_publication_tier

DEFAULT_SAMPLE_SIZE = 500


async def main(sample_size: int, skip: int, detail_out: str) -> None:
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            select(EventTriage).order_by(EventTriage.triaged_at.desc())
        )).scalars().all()
    with_ticker = [r for r in rows if r.tickers][skip:skip + sample_size]
    print(f"=== C8 cohort: {len(with_ticker)} real EventTriage rows (target {sample_size}, skip {skip}) ===\n")

    c1_outcomes: Counter[str] = Counter()
    c5_publication_action: Counter[str] = Counter()
    tier_counts: Counter[str] = Counter()
    tier_reason_counts: Counter[str] = Counter()

    known_identities: dict[str, str] = {}
    known_headlines: dict[str, str] = {}  # for per-item disambiguation during generation only
    article_candidates = []  # list of dicts holding everything needed to compose later

    for i, row in enumerate(with_ticker, start=1):
        symbol = row.tickers[0]
        if i % 50 == 0:
            print(f"  ... processed {i}/{len(with_ticker)}")

        async with AsyncSessionLocal() as db:
            candidate = await evaluate_candidate(db, symbol=symbol, event_headline=row.headline, event_id=row.event_id)
        c1_outcomes[candidate.outcome] += 1
        if candidate.outcome == C1_SKIP:
            continue

        async with AsyncSessionLocal() as db:
            es = await build_evidence_set(db, symbol=symbol, event_headline=row.headline, event_id=row.event_id)
        if es.primary_evidence is None:
            continue

        async with AsyncSessionLocal() as db:
            ctx = await build_context(db, es)

        decision = decide(candidate, es, ctx)
        if decision.content_type not in (FULL_ARTICLE, FACTUAL_UPDATE):
            continue

        identity = compute_identity(es)
        resolution = resolve_uniqueness(
            identity, c4_publication_action=decision.publication_action,
            c4_matched_article_id=None, known_identities=known_identities,
        )
        c5_publication_action[resolution.publication_action] += 1
        if resolution.publication_action == CREATE_NEW:
            known_identities[identity.identity_key] = f"item-{i}-{symbol}"
        if resolution.publication_action not in (CREATE_NEW, UPDATE_EXISTING):
            continue

        tier_result = classify_publication_tier(decision, es, ctx)
        tier_counts[tier_result.tier] += 1
        for r in tier_result.reason_codes:
            tier_reason_counts[r] += 1

        if tier_result.tier != ARTICLE:
            continue  # EVENT_ONLY / REJECT -- no headline, no composition, per explicit architectural decision

        headline_result = await generate_headline(es, ctx, identity, other_accepted_headlines=known_headlines)
        if headline_result.h1:
            known_headlines[identity.identity_key] = headline_result.h1

        article_candidates.append({
            "symbol": symbol, "identity": identity, "decision": decision, "es": es, "ctx": ctx,
            "resolution": resolution, "headline_result": headline_result, "tier_reasons": tier_result.reason_codes,
        })

    print(f"\nRe-scanned {len(with_ticker)} events -> {tier_counts.get(ARTICLE, 0)} tier=ARTICLE candidates before batch uniqueness closure.\n")

    # -- C8.3: batch-wide final uniqueness closure over ARTICLE candidates only --
    ordered_pairs = [(c["identity"], c["headline_result"].h1) for c in article_candidates]
    batch_result = finalize_batch_uniqueness(ordered_pairs)

    uniqueness_downgrades = []
    composed = []
    refused = 0
    for c in article_candidates:
        br = batch_result[c["identity"].identity_key]
        if not br.kept:
            uniqueness_downgrades.append((c, br.collided_with))
            continue
        try:
            article = await compose_article(
                c["decision"], c["es"], c["ctx"], c["identity"], c["resolution"], c["headline_result"],
            )
        except ComposerRefusal as exc:
            refused += 1
            print(f"  COMPOSER REFUSED for {c['symbol']}: {exc}")
            continue
        composed.append((c, article))

    print(f"=== C8.3 batch uniqueness closure: {len(uniqueness_downgrades)} ARTICLE candidate(s) downgraded to EVENT_ONLY ===")
    for c, collided_with in uniqueness_downgrades:
        print(f"  [{c['symbol']}] headline {c['headline_result'].h1!r} still collides with {collided_with} after all real-fact repairs -- downgraded to EVENT_ONLY")

    print(f"\n=== C8 Funnel ({len(with_ticker)} real events) ===")
    print(f"C1 outcomes: {dict(c1_outcomes)}")
    print(f"C5 publication_action: {dict(c5_publication_action)}")
    print(f"Publication tier (of C5 CREATE_NEW/UPDATE_EXISTING): {dict(tier_counts)}")
    print(f"Tier reason codes: {dict(tier_reason_counts)}")
    print(f"ARTICLE candidates before batch uniqueness: {len(article_candidates)}")
    print(f"Downgraded by batch uniqueness closure: {len(uniqueness_downgrades)}")
    print(f"Final composed ARTICLEs: {len(composed)}  (refused: {refused})")
    depth_downgrades = sum(1 for _, a in composed if a.depth_gate_downgraded)
    print(f"FULL_ARTICLE downgraded to FACTUAL_UPDATE-shape by C8.4 depth gate: {depth_downgrades}")

    # -- Real, final acceptance checks --
    print(f"\n=== Acceptance checks ===")
    hijack_flags = 0
    for c, article in composed:
        es = c["es"]
        if article.headline and es.primary_evidence and es.primary_evidence.title:
            h_tokens = _tokenize(article.headline)
            primary_sim = _jaccard(h_tokens, _tokenize(es.primary_evidence.title))
            best_supporting = max(
                (_jaccard(h_tokens, _tokenize(s.title)) for s in es.supporting_evidence if s.title), default=0.0,
            )
            if best_supporting > primary_sim + 0.05:
                hijack_flags += 1
                print(f"  HIJACK STILL PRESENT: [{c['symbol']}] {article.headline!r}")
    print(f"  headline subject hijacks among final ARTICLEs: {hijack_flags}")

    truncation_flags = 0
    for c, article in composed:
        if article.headline and (article.headline.rstrip().endswith(("…",)) is False and
                                  len(article.headline) > 0 and article.headline[-1].isalpha() and
                                  len(article.headline.rsplit(" ", 1)[-1]) == 1):
            truncation_flags += 1
            print(f"  POSSIBLE TRUNCATION: [{c['symbol']}] {article.headline!r}")
    print(f"  possible broken/truncated headlines among final ARTICLEs: {truncation_flags}")

    collision_pairs = 0
    for a in range(len(composed)):
        for b in range(a + 1, len(composed)):
            c_a, art_a = composed[a]
            c_b, art_b = composed[b]
            if c_a["identity"].identity_key == c_b["identity"].identity_key:
                continue
            sim = _jaccard(_tokenize(art_a.headline), _tokenize(art_b.headline))
            if sim >= 0.50:
                collision_pairs += 1
                print(f"  RESIDUAL COLLISION: {sim:.2f}  {c_a['symbol']!r} vs {c_b['symbol']!r}")
    print(f"  cross-identity headline collisions >=0.50 among final ARTICLEs: {collision_pairs}")

    raw_dump_flags = sum(1 for _, a in composed if a.content_type == FULL_ARTICLE and a.word_count > 300)
    print(f"  FULL_ARTICLEs over 300 words (possible raw filing dump): {raw_dump_flags}")

    print(f"\n=== ALL {len(composed)} FINAL COMPOSED ARTICLES (full detail, for manual inspection) ===\n")
    detail_lines = []
    for c, article in composed:
        header = f"[{c['symbol']}] content_type={article.content_type} depth_gate_downgraded={article.depth_gate_downgraded} tier_reasons={c['tier_reasons']}"
        print(header)
        print(f"  headline: {article.headline!r}")
        print(f"  llm_status={article.llm_status} attempts={article.llm_attempts} word_count={article.word_count}")
        for s in article.sections:
            print(f"  -- [{s.name}] {s.text[:500]}")
        print()
        detail_lines.append(header)
        detail_lines.append(f"  headline: {article.headline!r}")
        for s in article.sections:
            detail_lines.append(f"  -- [{s.name}] {s.text}")
        detail_lines.append("")

    with open(detail_out, "w", encoding="utf-8") as f:
        f.write("\n".join(detail_lines))
    print(f"\nFull detail written to: {detail_out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample-size", type=int, default=DEFAULT_SAMPLE_SIZE)
    parser.add_argument("--skip", type=int, default=0)
    parser.add_argument("--detail-out", type=str, default="c8_shadow_detail.txt")
    args = parser.parse_args()
    asyncio.run(main(args.sample_size, args.skip, args.detail_out))
