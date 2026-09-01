"""
Article V2 Phase C7 -- Full-system shadow quality gate (owner
authorization, 2026-09-01). Runs the complete C1 -> C6 pipeline over a
FRESH, larger cohort -- the 500 most recent real EventTriage rows, not
the original 120-event tuning cohort (which stays untouched as a
separate regression reference: article_v2_c1_shadow_run.py through
article_v2_c6_shadow_run.py). Writes NOTHING to any production table.
Real LLM calls for headline generation and, for any FULL_ARTICLE, Why
It Matters.

Two outputs:
  - stdout: the full funnel (every stage's real counts), summary
    statistics, and a one-line-per-item index of every composed output
    with automated flags (headline-hijack heuristic, cross-identity
    near-duplicate headlines, V1-comparison match).
  - a detail file (--detail-out): the full composed text (headline +
    every section + every claim) for EVERY composed output, for manual
    Truth/Usefulness/Uniqueness/Presentation review.

The headline-hijack check is a real, quantifiable PROXY for the C6
finding (BLS's headline drawing its subject from supporting evidence
instead of primary evidence): Jaccard(headline, primary.title) vs.
max(Jaccard(headline, supporting[i].title)). Flagged when a supporting
item's similarity exceeds the primary's AND clears a real minimum bar
(not just a rounding artifact). This does not replace manual reading --
it tells the reviewer WHERE to look first.
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
from app.db.models.intelligence_article import IntelligenceArticle
from app.db.session import AsyncSessionLocal
from app.services.aipe.duplicate_detector import _jaccard, _tokenize
from app.services.article_v2.candidate_gate import SKIP as C1_SKIP
from app.services.article_v2.candidate_gate import evaluate_candidate
from app.services.article_v2.composer import ComposerRefusal, compose_article
from app.services.article_v2.context_builder import build_context
from app.services.article_v2.decision_engine import FACTUAL_UPDATE, FULL_ARTICLE, decide
from app.services.article_v2.evidence_set_builder import build_evidence_set
from app.services.article_v2.headline_engine import generate_headline
from app.services.article_v2.identity import CREATE_NEW, UPDATE_EXISTING, compute_identity, resolve_uniqueness

DEFAULT_SAMPLE_SIZE = 500
_HIJACK_MIN_SIMILARITY = 0.20


async def main(sample_size: int, detail_out: str) -> None:
    # Real data characteristic, confirmed via direct query: recent
    # EventTriage rows skew toward unresolved tickers (empty list, not
    # null) -- a fixed limit*2 window (the pattern the 120-event cohort
    # scripts used) isn't reliably deep enough at this scale. Query all
    # rows ordered by recency and take the first N with a real ticker,
    # rather than guessing a window size.
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            select(EventTriage).order_by(EventTriage.triaged_at.desc())
        )).scalars().all()
    with_ticker = [r for r in rows if r.tickers][:sample_size]
    print(f"=== C7 cohort: {len(with_ticker)} real EventTriage rows (target {sample_size}) ===\n")

    c1_outcomes: Counter[str] = Counter()
    c2_status: Counter[str] = Counter()
    c3_status: Counter[str] = Counter()
    c4_content_type: Counter[str] = Counter()
    c4_publication_action: Counter[str] = Counter()
    c5_publication_action: Counter[str] = Counter()
    c5_collisions = 0
    c6_composed = 0
    c6_refused = 0
    llm_status_counts: Counter[str] = Counter()
    hijack_flags: list[tuple[str, str, float, float]] = []  # symbol, headline, primary_sim, best_supporting_sim
    v1_matches: list[dict] = []
    all_final: list[dict] = []  # {symbol, identity, headline, content_type}

    known_identities: dict[str, str] = {}
    known_headlines: dict[str, str] = {}

    detail_lines: list[str] = []

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
        c2_status[es.status] += 1
        if es.primary_evidence is None:
            continue

        async with AsyncSessionLocal() as db:
            ctx = await build_context(db, es)
        c3_status[ctx.status] += 1

        decision = decide(candidate, es, ctx)
        c4_content_type[decision.content_type] += 1
        c4_publication_action[decision.publication_action] += 1
        if decision.content_type not in (FULL_ARTICLE, FACTUAL_UPDATE):
            continue

        identity = compute_identity(es)
        resolution = resolve_uniqueness(
            identity, c4_publication_action=decision.publication_action,
            c4_matched_article_id=None, known_identities=known_identities,
        )
        c5_publication_action[resolution.publication_action] += 1
        if resolution.matched_identity_key:
            c5_collisions += 1
        if resolution.publication_action == CREATE_NEW:
            known_identities[identity.identity_key] = f"item-{i}-{symbol}"

        if resolution.publication_action not in (CREATE_NEW, UPDATE_EXISTING):
            continue

        headline_result = await generate_headline(es, ctx, identity, other_accepted_headlines=known_headlines)
        if headline_result.h1:
            known_headlines[identity.identity_key] = headline_result.h1

        try:
            article = await compose_article(decision, es, ctx, identity, resolution, headline_result)
        except ComposerRefusal:
            c6_refused += 1
            continue

        c6_composed += 1
        llm_status_counts[article.llm_status] += 1
        all_final.append({"symbol": symbol, "identity": identity, "headline": article.headline, "content_type": article.content_type})

        # -- Headline-hijack heuristic --
        if article.headline and es.primary_evidence.title:
            h_tokens = _tokenize(article.headline)
            primary_sim = _jaccard(h_tokens, _tokenize(es.primary_evidence.title))
            best_supporting_sim = 0.0
            for s in es.supporting_evidence:
                if s.title:
                    sim = _jaccard(h_tokens, _tokenize(s.title))
                    best_supporting_sim = max(best_supporting_sim, sim)
            if best_supporting_sim > primary_sim and best_supporting_sim >= _HIJACK_MIN_SIMILARITY:
                hijack_flags.append((symbol, article.headline, primary_sim, best_supporting_sim))

        # -- Real V1 comparison: same triggering EventTriage row already
        # has a real, existing V1 article. Strongest possible match. --
        async with AsyncSessionLocal() as db:
            v1 = (await db.execute(
                select(IntelligenceArticle).where(IntelligenceArticle.trigger_event_id == row.event_id)
            )).scalars().first()
        if v1 is not None:
            v1_matches.append({
                "symbol": symbol, "v1_headline": v1.headline, "v1_what_happened": v1.what_happened,
                "v1_why_it_matters": v1.why_it_matters, "v1_status": v1.status,
                "v2_headline": article.headline, "v2_content_type": article.content_type,
            })

        detail_lines.append(f"[{i}] symbol={symbol} content_type={article.content_type} pub_action={resolution.publication_action}")
        detail_lines.append(f"    identity: type={identity.development_type} anchor={identity.anchor} time={identity.time_bucket}")
        detail_lines.append(f"    headline: {article.headline!r}")
        detail_lines.append(f"    llm_status={article.llm_status} attempts={article.llm_attempts} word_count={article.word_count}")
        for s in article.sections:
            detail_lines.append(f"    -- [{s.name}] {s.text}")
        if article.llm_validation_notes:
            detail_lines.append(f"    validation notes: {article.llm_validation_notes}")
        detail_lines.append("")

    # -- Cross-identity headline similarity across the FULL composed set --
    similarity_pairs = []
    for a in range(len(all_final)):
        for b in range(a + 1, len(all_final)):
            id_a, id_b = all_final[a]["identity"], all_final[b]["identity"]
            if id_a.identity_key == id_b.identity_key:
                continue
            h_a, h_b = all_final[a]["headline"], all_final[b]["headline"]
            if not h_a or not h_b:
                continue
            sim = _jaccard(_tokenize(h_a), _tokenize(h_b))
            if sim >= 0.5:
                similarity_pairs.append((all_final[a]["symbol"], h_a, all_final[b]["symbol"], h_b, sim))

    print(f"\n\n=== C7 Funnel ({len(with_ticker)} real events) ===")
    print(f"C1 outcomes: {dict(c1_outcomes)}")
    print(f"C2 status (of C1 non-SKIP): {dict(c2_status)}")
    print(f"C3 status: {dict(c3_status)}")
    print(f"C4 content_type: {dict(c4_content_type)}")
    print(f"C4 publication_action: {dict(c4_publication_action)}")
    print(f"C5 publication_action: {dict(c5_publication_action)} (in-batch collisions: {c5_collisions})")
    print(f"C6: composed={c6_composed} refused={c6_refused}")
    print(f"C6 llm_status distribution: {dict(llm_status_counts)}")

    print(f"\n=== Headline-hijack heuristic (supporting-evidence similarity > primary-evidence similarity, >= {_HIJACK_MIN_SIMILARITY}) ===")
    print(f"  {len(hijack_flags)} of {c6_composed} composed outputs flagged ({100*len(hijack_flags)/max(c6_composed,1):.1f}%)")
    for symbol, headline, p_sim, s_sim in hijack_flags:
        print(f"  [{symbol}] primary_sim={p_sim:.2f} best_supporting_sim={s_sim:.2f}  headline={headline!r}")

    print(f"\n=== Cross-identity near-duplicate headlines (>= 0.50 Jaccard, different identities) ===")
    print(f"  {len(similarity_pairs)} pairs found across {c6_composed} composed outputs")
    for sym_a, h_a, sym_b, h_b, sim in similarity_pairs:
        print(f"  similarity={sim:.2f}  {sym_a!r} {h_a!r}  vs  {sym_b!r} {h_b!r}")

    print(f"\n=== Real V1-vs-V2 comparison ({len(v1_matches)} exact trigger_event_id matches) ===")
    for m in v1_matches:
        print(f"  [{m['symbol']}]")
        print(f"    V1 [{m['v1_status']}] headline: {m['v1_headline']!r}")
        print(f"    V1 what_happened: {(m['v1_what_happened'] or '')[:300]!r}")
        print(f"    V1 why_it_matters: {(m['v1_why_it_matters'] or '')[:300]!r}")
        print(f"    V2 [{m['v2_content_type']}] headline: {m['v2_headline']!r}")
        print()

    print(f"\n=== ALL {c6_composed} COMPOSED OUTPUTS (index) ===")
    for item in all_final:
        flagged = any(item["symbol"] == h[0] and item["headline"] == h[1] for h in hijack_flags)
        print(f"  [{item['content_type']:<14}] {item['symbol']:<12} {'[HIJACK-FLAG] ' if flagged else ''}{item['headline']!r}")

    with open(detail_out, "w", encoding="utf-8") as f:
        f.write("\n".join(detail_lines))
    print(f"\nFull per-item detail written to: {detail_out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample-size", type=int, default=DEFAULT_SAMPLE_SIZE)
    parser.add_argument("--detail-out", type=str, default="c7_shadow_detail.txt")
    args = parser.parse_args()
    asyncio.run(main(args.sample_size, args.detail_out))
