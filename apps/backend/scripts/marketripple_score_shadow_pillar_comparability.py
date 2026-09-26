"""
Shadow pillar-comparability check — 2026-09-26 audit follow-up.

Question: is a company scored from 3-of-4 pillars (renormalized weights)
comparable, for ranking purposes, to one scored from all 4? Run manually
(`python scripts/marketripple_score_shadow_pillar_comparability.py`), no
network calls, no writes — uses synthetic-but-realistic pillar values so
the comparison is fast, deterministic, and reviewable, rather than
depending on live market data that changes daily (see the real, network-
backed scripts/marketripple_score_five_bank_comparison.py for that).

Method: 5 synthetic companies with varied real-shaped pillar scores. For
each company, compute its true 4-of-4 score, then simulate each of the 4
possible "this one pillar went missing" cases (renormalized 3-of-4
weights, same formula engine.py uses today) and measure the score delta
and whether the company's RANK among the other 4 (left at full coverage)
changes.

This is what backs the comparability interim rule in engine.py/contracts.py:
score is withheld below 4-of-4 pillars until evidence like this says which
partial combinations are actually safe to rank.
"""
from __future__ import annotations

from app.services.marketripple_score.engine import CANDIDATE_WEIGHTS

# name -> {pillar: score}. Deliberately varied so ranking is non-trivial:
# a company can be strong on fundamentals but weak on market behaviour, etc.
COMPANIES = {
    "BANK_A": {"financial_strength": 78.0, "valuation": 55.0, "market_behaviour": 60.0, "current_intelligence": 50.0},
    "BANK_B": {"financial_strength": 60.0, "valuation": 70.0, "market_behaviour": 65.0, "current_intelligence": 55.0},
    "BANK_C": {"financial_strength": 65.0, "valuation": 60.0, "market_behaviour": 40.0, "current_intelligence": 80.0},
    "BANK_D": {"financial_strength": 55.0, "valuation": 58.0, "market_behaviour": 62.0, "current_intelligence": 60.0},
    "BANK_E": {"financial_strength": 70.0, "valuation": 50.0, "market_behaviour": 55.0, "current_intelligence": 45.0},
}


def _weighted_score(pillars: dict[str, float]) -> float:
    used_weight = sum(CANDIDATE_WEIGHTS[p] for p in pillars)
    return round(sum(pillars[p] * CANDIDATE_WEIGHTS[p] for p in pillars) / used_weight, 1)


def main() -> None:
    true_scores = {name: _weighted_score(p) for name, p in COMPANIES.items()}
    true_rank = {
        name: i + 1
        for i, (name, _) in enumerate(sorted(true_scores.items(), key=lambda kv: kv[1], reverse=True))
    }

    print("True 4-of-4 scores and ranks:")
    for name in COMPANIES:
        print(f"  {name}: score={true_scores[name]}  rank={true_rank[name]}")

    print()
    print("Effect of ONE company dropping ONE pillar (others stay at full 4-of-4 coverage):")
    max_delta = 0.0
    rank_change_examples = []
    for name, pillars in COMPANIES.items():
        for dropped in CANDIDATE_WEIGHTS:
            partial = {p: v for p, v in pillars.items() if p != dropped}
            partial_score = _weighted_score(partial)
            delta = round(partial_score - true_scores[name], 1)
            max_delta = max(max_delta, abs(delta))

            hypothetical_scores = dict(true_scores)
            hypothetical_scores[name] = partial_score
            new_rank = {
                n: i + 1
                for i, (n, _) in enumerate(sorted(hypothetical_scores.items(), key=lambda kv: kv[1], reverse=True))
            }[name]
            rank_changed = new_rank != true_rank[name]
            if rank_changed:
                rank_change_examples.append((name, dropped, true_rank[name], new_rank, delta))

            print(f"  {name} missing {dropped:<22} true={true_scores[name]:>5} "
                  f"partial={partial_score:>5} delta={delta:>+5}  "
                  f"rank {true_rank[name]}->{new_rank}{'  *** RANK CHANGED ***' if rank_changed else ''}")

    print()
    print(f"Max absolute score delta from dropping any single pillar: {max_delta}")
    print(f"Rank-changing cases: {len(rank_change_examples)} of {len(COMPANIES) * len(CANDIDATE_WEIGHTS)}")
    for name, dropped, old_rank, new_rank, delta in rank_change_examples:
        print(f"  {name} dropping {dropped}: rank {old_rank} -> {new_rank} (delta {delta:+})")


if __name__ == "__main__":
    main()
