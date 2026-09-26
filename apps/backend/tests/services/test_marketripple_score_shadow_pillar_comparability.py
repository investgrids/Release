"""
Regression test for the shadow pillar-comparability measurement (see
scripts/marketripple_score_shadow_pillar_comparability.py for the full,
printable report). Proves the real, quantified reason a 3-of-4-pillar
score is withheld from ranking today: dropping a single pillar for one
company, while its peers stay at full 4-of-4 coverage, measurably changes
that company's rank position in half of the simulated cases and moves the
score by up to ~9.5 points — a renormalized partial score is not a like-
for-like number next to a full one.
"""
from __future__ import annotations

from scripts.marketripple_score_shadow_pillar_comparability import COMPANIES, _weighted_score
from app.services.marketripple_score.engine import CANDIDATE_WEIGHTS


def test_dropping_a_pillar_materially_changes_rank_for_some_companies():
    true_scores = {name: _weighted_score(p) for name, p in COMPANIES.items()}
    true_rank = {
        name: i + 1
        for i, (name, _) in enumerate(sorted(true_scores.items(), key=lambda kv: kv[1], reverse=True))
    }

    rank_changes = 0
    max_delta = 0.0
    for name, pillars in COMPANIES.items():
        for dropped in CANDIDATE_WEIGHTS:
            partial = {p: v for p, v in pillars.items() if p != dropped}
            partial_score = _weighted_score(partial)
            max_delta = max(max_delta, abs(partial_score - true_scores[name]))

            hypothetical = dict(true_scores)
            hypothetical[name] = partial_score
            new_rank = {
                n: i + 1
                for i, (n, _) in enumerate(sorted(hypothetical.items(), key=lambda kv: kv[1], reverse=True))
            }[name]
            if new_rank != true_rank[name]:
                rank_changes += 1

    # Real, measured evidence backing the comparability interim rule — not
    # an assumption. If this ever drops to 0, the interim rule should be
    # revisited (it would mean renormalization stopped mattering for
    # ranking); if it changes at all, the underlying formula changed and
    # this test should be re-examined rather than blindly updated.
    assert rank_changes > 0, "dropping a pillar must be shown to actually change rank at least once"
    assert max_delta > 5.0, "the score movement from a dropped pillar must be shown to be material, not negligible"
