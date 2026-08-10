"""
Regression suite — content_planner.plan_extra_angles, offline.

Built for the AI Newsroom redesign (2026-08-10) to pin down the real
production duplicate the audit flagged: Advanced Enzyme Technologies Ltd
(NSE: ADVENZYMES) published both a "primary" company_intelligence article
and a redundant "per_company" angle for the exact same single-company
acquisition event — two near-identical articles competing for the same
search intent.

The skip-guard in plan_extra_angles already carries a code comment
documenting this exact incident (by its old codename "ADVANZEN") and the
fix that shipped for it: comparing the extra-angle company's symbol against
the primary article's own subject (companies[0]["symbol"] when the primary
IS a company_intelligence piece with no angle_entity set yet, since
angle_entity only gets populated on the spinoff itself). This suite
verifies that fix holds for the real ADVENZYMES-shaped input, not just
that the comment claims it does.
"""
from __future__ import annotations

from app.services.aipe.content_planner import plan_extra_angles

_ADVENZYMES = {"symbol": "ADVENZYMES", "name": "Advanced Enzyme Technologies Ltd", "impact": "positive"}


def test_single_company_acquisition_does_not_spawn_duplicate_per_company_angle():
    """The exact real scenario: one company, one event, primary_article_type
    is already company_intelligence for this same company. No per_company
    angle should be planned for ADVENZYMES itself — that would just be the
    same article twice under a different angle label."""
    plans = plan_extra_angles(
        primary_article_type="company_intelligence",
        primary_story_id="intel-advenzymes-acq-20260810",
        primary_headline="Advanced Enzyme Technologies announces acquisition of overseas biotech unit",
        companies_affected=[_ADVENZYMES],
        sectors_affected=[{"name": "Pharma"}],
        primary_angle_entity=None,  # primary articles always store angle_entity=None
    )
    per_company_symbols = [entity for (atype, _, angle, entity, _) in plans if angle == "per_company"]
    assert "ADVENZYMES" not in per_company_symbols, (
        f"Duplicate per_company angle planned for the primary's own company: {plans}"
    )


def test_second_company_in_multi_company_event_still_gets_its_own_angle():
    """Guard against an over-broad fix: a genuinely different second company
    in the same event must still get its own per_company spinoff — only the
    primary's OWN subject should be skipped."""
    other = {"symbol": "GNFC", "name": "Gujarat Narmada Valley Fertilizers", "impact": "neutral"}
    plans = plan_extra_angles(
        primary_article_type="company_intelligence",
        primary_story_id="intel-advenzymes-acq-20260810",
        primary_headline="Advanced Enzyme Technologies announces acquisition of overseas biotech unit",
        companies_affected=[_ADVENZYMES, other],
        sectors_affected=[{"name": "Pharma"}],
        primary_angle_entity=None,
    )
    per_company_symbols = [entity for (atype, _, angle, entity, _) in plans if angle == "per_company"]
    assert "GNFC" in per_company_symbols
    assert "ADVENZYMES" not in per_company_symbols


def test_non_company_primary_still_spawns_per_company_angles_normally():
    """A macro/sector primary article (not itself about one company) should
    still fan out per-company angles as usual — the skip-guard only applies
    when the primary itself IS a company_intelligence piece."""
    plans = plan_extra_angles(
        primary_article_type="sector_intelligence",
        primary_story_id="intel-pharma-rollup-20260810",
        primary_headline="Pharma sector rallies on strong Q1 earnings across the board",
        companies_affected=[_ADVENZYMES],
        sectors_affected=[{"name": "Pharma"}, {"name": "Healthcare"}],
        primary_angle_entity=None,
    )
    per_company_symbols = [entity for (atype, _, angle, entity, _) in plans if angle == "per_company"]
    assert "ADVENZYMES" in per_company_symbols


def test_per_company_spinoff_itself_does_not_recurse_into_another_duplicate():
    """Once a per_company angle for a DIFFERENT company has already become
    its own primary (angle_entity now set to that company), running
    plan_extra_angles again from that new primary must not re-propose an
    angle for itself either — the same skip-guard, exercised from the
    spinoff's own perspective."""
    plans = plan_extra_angles(
        primary_article_type="company_intelligence",
        primary_story_id="intel-advenzymes-acq-20260810-co-GNFC",
        primary_headline="Advanced Enzyme Technologies announces acquisition of overseas biotech unit",
        companies_affected=[{"symbol": "GNFC", "name": "Gujarat Narmada Valley Fertilizers", "impact": "neutral"}],
        sectors_affected=[],
        primary_angle_entity="GNFC",
    )
    per_company_symbols = [entity for (atype, _, angle, entity, _) in plans if angle == "per_company"]
    assert "GNFC" not in per_company_symbols
