"""
Regression suite — recommendation_language.py, offline (no DB/network/LLM).

P0-CD2 Generation Containment (2026-09-01): the deterministic backstop behind
content_templates.py's prompt changes. Exercises the exact adversarial cases
named in the CD2 authorization.
"""
from __future__ import annotations

from app.services.aipe.recommendation_language import scan_recommendation_language


def _opp(title="", description=""):
    return {"opportunities": [{"title": title, "description": description}]}


# ── Must flag ─────────────────────────────────────────────────────────────────

def test_buy_instruction_in_opportunity_title_flagged():
    v = scan_recommendation_language(_opp(title="Buy HDFC Bank now"))
    assert any("opportunities" in e for e in v)


def test_price_surge_turned_into_buy_instruction_flagged():
    # "XYZ surged 20% today" must not become "buy XYZ" — the taxonomy check
    # against key_takeaway specifically, per the CD2 authorization's own
    # adversarial case.
    v = scan_recommendation_language({"key_takeaway": "XYZ surged 20% today — buy XYZ before it runs further."})
    assert any("key_takeaway" in e for e in v)


def test_historical_gain_relabeled_likely_winner_flagged():
    v = scan_recommendation_language(_opp(title="ONGC is a likely winner based on the historical pattern"))
    assert any("opportunities" in e for e in v)


def test_short_instruction_flagged():
    v = scan_recommendation_language(_opp(title="Short Nifty into resistance"))
    assert len(v) == 1


def test_accumulate_reduce_exit_target_stoploss_bookprofits_overweight_underweight_dipbuy_flagged():
    cases = [
        "Accumulate on every dip",
        "Reduce your position in the stock",
        "Exit your holding before the results",
        "Target price of 1,850 looks achievable",
        "Set a stop-loss below the recent low",
        "Book profits at current levels",
        "Stay Overweight on the sector",
        "Underweight the stock given headwinds",
        "This looks like a good dip-buy candidate",
        "Consider buying on weakness",
        "Investors should buy the stock now",
        "This is a good entry point",
        "Wait for a potential entry near support",
        "This is a buying opportunity for long-term investors",
    ]
    for text in cases:
        v = scan_recommendation_language(_opp(title=text))
        assert v, f"expected a violation for: {text!r}"


def test_analyst_recommendation_in_opportunities_flagged_even_if_phrased_as_attribution():
    # High-risk fields (opportunities[]/key_takeaway) exist specifically to
    # state MarketRipple's own conclusion -- per the CD2 authorization,
    # attribution belongs in why_it_matters (unscanned), not here.
    v = scan_recommendation_language(_opp(title="Analysts issued a strong buy rating on the stock"))
    assert v


# ── Must NOT flag ─────────────────────────────────────────────────────────────

def test_share_buyback_not_rejected():
    v = scan_recommendation_language(_opp(title="Company announces share buyback", description="The board approved a buyback of up to 5% of shares."))
    assert v == []


def test_promoter_purchase_fact_not_rejected():
    v = scan_recommendation_language(_opp(title="Promoters purchased additional shares on the open market"))
    assert v == []


def test_unknown_company_no_symbol_field_not_this_modules_job():
    # Entity resolution is a separate gate (article_generator._resolve_
    # company_symbols) -- this module only scans language, never symbols.
    v = scan_recommendation_language({"companies_affected": [{"name": "Unknown Co", "symbol": "MADEUP"}]})
    assert v == []


def test_source_quote_attributed_in_why_it_matters_not_scanned():
    # "Source itself quotes an analyst saying 'Buy HDFC Bank.'" -- allowed
    # to be attributed in a narrative field; only the high-risk fields are
    # held to the strict policy.
    article = {
        "why_it_matters": 'An analyst at a major brokerage was quoted saying "Buy HDFC Bank" in a note today.',
        "opportunities": [],
        "key_takeaway": "The stock is being closely watched after the analyst note.",
    }
    assert scan_recommendation_language(article) == []


def test_short_term_not_flagged_as_short_instruction():
    v = scan_recommendation_language(_opp(title="A short-term catalyst is worth watching", description="short term momentum may continue"))
    assert v == []


def test_neutral_analytical_language_not_flagged():
    v = scan_recommendation_language({
        "opportunities": [{
            "title": "HDFC Bank's cost-of-funds pressure eases if RBI holds through Q3",
            "description": "Evidence points to margin stability for private banks under a steady-rate regime.",
        }],
        "key_takeaway": "The evidence points to margin stability for private lenders this quarter.",
    })
    assert v == []


def test_empty_article_not_flagged():
    assert scan_recommendation_language({}) == []


def test_non_dict_opportunity_items_skipped_safely():
    v = scan_recommendation_language({"opportunities": ["not-a-dict", {"title": "clean text here"}]})
    assert v == []


# ── Comparative recommendation phrasing (2026-09-03, directional-surface
# reassessment — comparison_publisher.py's real leak) ───────────────────────

def test_favor_preferred_choice_over_flagged_the_real_live_specimen():
    # The exact real live specimen this pass was found from: a comparison
    # article's key_takeaway matched none of the pre-existing patterns.
    v = scan_recommendation_language({
        "key_takeaway": "Favor GAIL India Ltd for 12-month capital appreciation... "
                         "preferred choice over Oil & Natural Gas Corporation",
    })
    assert v


def test_comparative_recommendation_phrases_flagged():
    cases = [
        "We favor Company A over Company B for the next 12 months",
        "Company A is our preferred choice for growth investors",
        "This makes Company A the better investment right now",
        "Most investors would choose Company A here",
        "Analysts prefer Company A over Company B",
    ]
    for text in cases:
        v = scan_recommendation_language({"key_takeaway": text})
        assert v, f"expected a violation for: {text!r}"


def test_preferred_stock_not_flagged():
    # Real financial instrument type, not a recommendation -- must not
    # collide with the new "preferred" pattern.
    v = scan_recommendation_language({"key_takeaway": "The company issued new preferred stock last quarter."})
    assert v == []
    v = scan_recommendation_language({"key_takeaway": "Preferred shares carry a fixed dividend."})
    assert v == []


# ── Field awareness ───────────────────────────────────────────────────────────

def test_only_high_risk_fields_scanned():
    # what_happened/executive_summary/faqs are legitimately allowed to
    # report facts using these same words -- confirmed here they're simply
    # never scanned, matching the CD2 authorization's field-aware policy.
    article = {
        "what_happened": "The stock's brokerage rating was upgraded to Buy.",
        "executive_summary": "Analysts recommend investors buy the stock on this news.",
        "faqs": [{"question": "Should I buy?", "answer": "Some analysts have a Buy rating on the stock."}],
        "opportunities": [],
        "key_takeaway": "The evidence points to a stronger near-term outlook.",
    }
    assert scan_recommendation_language(article) == []
