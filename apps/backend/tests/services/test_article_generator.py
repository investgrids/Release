"""
Regression suite — article_generator.py's P0-CD2 additions, offline
(no DB/network/LLM): the entity authorization gate (_resolve_company_symbols)
and the SEO score breadth-incentive removal (compute_seo_score).
"""
from __future__ import annotations

from app.services.aipe.article_generator import _resolve_company_symbols, compute_seo_score


# ── Entity authorization gate ────────────────────────────────────────────────
# P0-CD2 Generation Containment (2026-09-01): companies_affected[].symbol
# used to persist verbatim, whatever the LLM guessed -- normalize_symbol()
# already existed but was only ever applied to internal_links/
# related_companies (cosmetic link generation), never to the field every
# surface actually renders. Concrete confirmed damage: Bajaj Finance stored
# under BAJAJFINSV (a different real company), an invented APOLLOMS symbol,
# unlisted entities (CIAL) presented as tradeable.

def test_correct_symbol_passes_through_unchanged():
    data = {"companies_affected": [{"name": "Tata Consultancy Services", "symbol": "TCS", "impact": "positive"}]}
    _resolve_company_symbols(data)
    assert data["companies_affected"][0]["symbol"] == "TCS"


def test_wrong_symbol_corrected_via_real_company_name():
    # The real production bug shape: Bajaj Finance's reason/name are
    # correct, but the LLM attached Bajaj Finserv's symbol -- a different
    # real, listed company.
    data = {"companies_affected": [{"name": "Bajaj Finance", "symbol": "BAJAJFINSV", "impact": "positive"}]}
    _resolve_company_symbols(data)
    assert data["companies_affected"][0]["symbol"] == "BAJFINANCE"


def test_invented_symbol_with_unresolvable_name_becomes_none():
    # The real production bug shape: a plausible-looking but entirely
    # invented ticker for a company that isn't in the real NSE universe.
    data = {"companies_affected": [{"name": "Apollo Micro Systems", "symbol": "APOLLOMS", "impact": "positive"}]}
    _resolve_company_symbols(data)
    assert data["companies_affected"][0]["symbol"] is None
    # Unknown stays unknown -- the company MENTION (name/reason) is real
    # content and is never dropped, only its unverifiable symbol.
    assert data["companies_affected"][0]["name"] == "Apollo Micro Systems"


def test_unlisted_entity_becomes_none_not_a_guessed_symbol():
    data = {"companies_affected": [{"name": "Cochin International Airport Limited", "symbol": "CIAL", "impact": "positive"}]}
    _resolve_company_symbols(data)
    assert data["companies_affected"][0]["symbol"] is None


def test_empty_symbol_resolved_via_name_when_possible():
    data = {"companies_affected": [{"name": "Infosys", "symbol": "", "impact": "positive"}]}
    _resolve_company_symbols(data)
    assert data["companies_affected"][0]["symbol"] == "INFY"


def test_no_companies_affected_key_does_not_raise():
    data = {"headline": "No companies here"}
    _resolve_company_symbols(data)  # must not raise
    assert "companies_affected" not in data


def test_non_dict_list_items_skipped_safely():
    data = {"companies_affected": ["not-a-dict", {"name": "TCS", "symbol": "tcs"}]}
    _resolve_company_symbols(data)
    assert data["companies_affected"][0] == "not-a-dict"
    assert data["companies_affected"][1]["symbol"] == "TCS"


# ── SEO score breadth-incentive removal ──────────────────────────────────────
# P0-CD2: >=2 companies_affected (+10) and >=2 ripple_effect (+5) rewarded
# an article purely for NAMING more companies/relationships, with no check
# either was evidence-supported -- an incentive pointed the wrong way.

_BASE_ARTICLE = {
    "headline": "What RBI's Rate Hold Means For SBI, HDFC Bank Investors",
    "seo_title": "What RBI's Rate Hold Means For SBI, HDFC Bank Investors Today",
    "meta_description": "A" * 140,
    "slug": "what-rbi-rate-hold-means-sbi-hdfc",
    "faqs": [{"question": "q1", "answer": "a1"}, {"question": "q2", "answer": "a2"}],
    "sectors_affected": [{"name": "Banking"}],
    "historical_context": "Similar holds in the past kept yields flat.",
    "what_to_watch_next": ["a", "b", "c"],
}


def test_seo_score_unaffected_by_company_or_ripple_count():
    few = {**_BASE_ARTICLE, "companies_affected": [{"name": "SBI"}], "ripple_effect": []}
    many = {**_BASE_ARTICLE, "companies_affected": [{"name": "SBI"}, {"name": "HDFC"}, {"name": "ICICI"}],
            "ripple_effect": [{"from_entity": "a", "to_entity": "b"}, {"from_entity": "b", "to_entity": "c"}]}
    assert compute_seo_score(few) == compute_seo_score(many)


def test_seo_score_max_possible_without_breadth_bonuses():
    # 12 (headline) + 15 (seo_title) + 15 (meta_description) + 8 (slug) +
    # 12 (faqs>=2) + 8 (sectors_affected>=1) + 10 (historical_context) +
    # 5 (what_to_watch_next>=3) = 85. No path to 95/100 via company/ripple
    # count alone any more.
    assert compute_seo_score(_BASE_ARTICLE) == 85
