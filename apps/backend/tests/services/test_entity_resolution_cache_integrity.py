"""
6G Cutover Gate, Step 3C/3D — Entity Resolution & Cache Integrity hardening.

Independent root causes, all in the shared resolver/cache layer both V2
and V3 depend on, found live during the Step 3 browser rehearsal:

  A. Ambiguity suppression      -- session_context.check_ambiguous_group
  B. Overlapping exact aliases  -- entities._match_companies
  C. Fuzzy corpus hygiene       -- entities._corpus / _fuzzy_candidates
  D. Semantic cache identity    -- cache.semantic_key
  E. Unsupported-entity residual stripping -- entities._looks_like_unrecognized_company
  F. Query-framing fuzzy hygiene (Step 3D) -- entities._word_ngrams' gate

Each case gets its own test class: the originally-observed failing query
(now fixed) plus a negative control proving the fix didn't overcorrect.
No LLM calls anywhere -- this whole layer is deterministic and synchronous.
"""
from __future__ import annotations

from app.services.ai_search import cache as cache_mod
from app.services.ai_search import entities as entities_mod
from app.services.ai_search import session_context as session_context_mod


# ─────────────────────────────────────────────────────────────────────────
# Case A -- ambiguity suppression
# ─────────────────────────────────────────────────────────────────────────
class TestCaseA_AmbiguitySuppression:
    def test_hdfc_bank_does_not_trigger_generic_bank_ambiguity(self):
        query = "What is the investment outlook for HDFC Bank?"
        entities = entities_mod.extract_entities(query)
        assert "HDFCBANK" in entities["companies"]
        assert session_context_mod.check_ambiguous_group(query, entities) is None

    def test_bare_bank_still_triggers_ambiguity(self):
        """Negative control: no specific bank resolved -- the ambiguity
        check must still fire, proving the fix is scoped to "already
        resolved," not a blanket suppression of the word "bank"."""
        query = "What is the outlook for Bank stocks in general?"
        entities = entities_mod.extract_entities(query)
        assert not entities["companies"]  # nothing specific resolved
        result = session_context_mod.check_ambiguous_group(query, entities)
        assert result is not None
        assert result["term"] == "Bank"
        assert len(result["candidates"]) >= 3


# ─────────────────────────────────────────────────────────────────────────
# Case B -- overlapping exact aliases
# ─────────────────────────────────────────────────────────────────────────
class TestCaseB_OverlappingAliases:
    def test_tech_mahindra_does_not_also_resolve_mm(self):
        query = "Compare TCS, HCL Technologies, and Tech Mahindra as investments."
        entities = entities_mod.extract_entities(query)
        assert entities["companies"] == ["TCS", "HCLTECH", "TECHM"]
        assert "M&M" not in entities["companies"]

    def test_mahindra_and_mahindra_still_resolves_mm(self):
        """Negative control: the real company must still resolve on its
        own, non-overlapping occurrence of the same word."""
        query = "What is the outlook for Mahindra & Mahindra as an auto investment?"
        entities = entities_mod.extract_entities(query)
        assert "M&M" in entities["companies"]

    def test_non_overlapping_occurrences_both_resolve(self):
        """A company mentioned standalone AND a different company whose
        alias happens to contain that same word, in a genuinely separate
        span, must both resolve -- suppression is span-based, not word-based."""
        query = "Compare the Mahindra Group outlook with Tech Mahindra specifically."
        entities = entities_mod.extract_entities(query)
        assert "TECHM" in entities["companies"]
        assert "M&M" in entities["companies"]


# ─────────────────────────────────────────────────────────────────────────
# Case C -- fuzzy corpus hygiene
# ─────────────────────────────────────────────────────────────────────────
class TestCaseC_FuzzyCorpusHygiene:
    def test_india_does_not_resolve_3mindia(self):
        query = "What is the latest update on Colgate-Palmolive India?"
        entities = entities_mod.extract_entities(query)
        assert entities["companies"] == ["COLPAL"]
        assert "3MINDIA" not in entities["companies"]

    def test_3m_india_explicitly_still_resolves(self):
        """Negative control: naming 3M India by its full stored name (an
        EXACT match, not the fuzzy path this case hardened) must still
        work. A bare "3M India" with no "Ltd" can only ever resolve via
        the same loose single-word fuzzy match to "india" this case
        correctly disabled -- there is no other distinguishing alias for
        it in the current data (the digit-led "3M" itself doesn't survive
        word-tokenization), so that phrasing is not a safe case to require."""
        query = "What is the investment outlook for 3M India Ltd?"
        entities = entities_mod.extract_entities(query)
        assert "3MINDIA" in entities["companies"]

    def test_genuine_misspelling_of_distinctive_company_still_fuzzy_matches(self):
        """Negative control: the fuzzy pass itself must still catch a real
        misspelling of a company whose core is genuinely distinctive
        (multi-word or a unique single word), proving Case C's corpus
        filter didn't blanket-disable fuzzy matching."""
        entities = entities_mod.extract_entities("What is the outlook for Relaince Industries?")
        assert "RELIANCE" in entities["companies"]


# ─────────────────────────────────────────────────────────────────────────
# Case D -- semantic cache identity
# ─────────────────────────────────────────────────────────────────────────
class TestCaseD_SemanticCacheIdentity:
    def test_2company_and_3company_keys_differ(self):
        two_way = cache_mod.semantic_key({"is_comparison": True}, {"companies": ["TCS", "INFY"]})
        three_way = cache_mod.semantic_key({"is_comparison": True}, {"companies": ["TCS", "INFY", "WIPRO"]})
        assert two_way != three_way

    def test_identical_3company_queries_share_a_key(self):
        """Negative control: two DIFFERENT phrasings resolving to the same
        3 companies must still hit the same semantic cache entry -- Case D
        must not fragment the cache down to per-phrasing granularity."""
        a = cache_mod.semantic_key({"is_comparison": True}, {"companies": ["TCS", "INFY", "WIPRO"]})
        b = cache_mod.semantic_key({"is_comparison": True}, {"companies": ["WIPRO", "TCS", "INFY"]})
        assert a == b

    def test_2company_cache_key_shape_unchanged(self):
        """Negative control: ordinary 2-company comparisons keep working
        exactly as before -- same key shape, order-independent."""
        a = cache_mod.semantic_key({"is_comparison": True}, {"companies": ["TCS", "INFY"]})
        b = cache_mod.semantic_key({"is_comparison": True}, {"companies": ["INFY", "TCS"]})
        assert a == b == "v3:sem:cmp:INFY:TCS"

    def test_different_3company_sets_never_collide(self):
        a = cache_mod.semantic_key({"is_comparison": True}, {"companies": ["TCS", "INFY", "WIPRO"]})
        b = cache_mod.semantic_key({"is_comparison": True}, {"companies": ["TCS", "INFY", "HCLTECH"]})
        assert a != b


# ─────────────────────────────────────────────────────────────────────────
# Case E -- unsupported-entity residual stripping
# ─────────────────────────────────────────────────────────────────────────
class TestCaseE_UnsupportedEntityResidualStripping:
    def test_three_valid_companies_do_not_trigger_unsupported_entity(self):
        query = "Compare Reliance Industries, Maruti Suzuki, and Sun Pharmaceutical as investments."
        entities = entities_mod.extract_entities(query)
        assert set(entities["companies"]) == {"RELIANCE", "MARUTI", "SUNPHARMA"}
        assert entities_mod.looks_like_unrecognized_company(query, entities) is False

    def test_genuinely_fake_company_still_flagged(self):
        """Negative control: a real fictional company name must still be
        caught -- Case E must not weaken the unsupported-entity detector
        itself, only fix the false positive on already-resolved companies.

        Originally phrased without the word "investment" specifically to
        dodge the TATAINVEST query-framing collision found while writing
        this test (see TestCaseF below, Step 3D) -- kept phrased this way
        even after that fix landed, since this test's own job is narrowly
        about Case E, not re-proving Case F."""
        query = "What is the outlook for Zylotronix Micro Industries Ltd?"
        entities = entities_mod.extract_entities(query)
        assert not entities["companies"]
        assert entities_mod.looks_like_unrecognized_company(query, entities) is True

    def test_mixed_real_and_fake_still_flags_the_fake_half(self):
        """Negative control: the documented mixed-query behavior (one real
        match, one fabricated) must still work after longer strip candidates
        were added."""
        query = "Compare Apple India Defence Ltd vs HAL"
        entities = entities_mod.extract_entities(query)
        assert "HAL" in entities["companies"]
        assert entities_mod.looks_like_unrecognized_company(query, entities) is True


# ─────────────────────────────────────────────────────────────────────────
# Case F (Step 3D) -- query-framing fuzzy hygiene
# ─────────────────────────────────────────────────────────────────────────
class TestCaseF_QueryFramingFuzzyHygiene:
    """Confirmed live: "What is the investment outlook for Asian Paints?"
    injected TATAINVEST (Tata Investment Corporation, a financial holding
    company) into a paints-company query -- the query's own generic
    phrasing ("the investment outlook") fuzzy-matched TATAINVEST's core
    ("tata investment") at ratio 0.83. Worse than a stray extra tag: the
    LLM went on to rationalize TATAINVEST's presence with fabricated-
    sounding reasoning, a real reasoning-corruption risk, not just noise."""

    def test_investment_outlook_phrasing_does_not_inject_tatainvest(self):
        query = "What is the investment outlook for Asian Paints?"
        entities = entities_mod.extract_entities(query)
        assert entities["companies"] == ["ASIANPAINT"]

    def test_investment_outlook_for_tcs_does_not_inject_tatainvest(self):
        entities = entities_mod.extract_entities("investment outlook for TCS")
        assert entities["companies"] == ["TCS"]

    def test_should_i_invest_phrasing_does_not_inject_tatainvest(self):
        entities = entities_mod.extract_entities("Should I invest in HDFC Bank?")
        assert entities["companies"] == ["HDFCBANK"]

    def test_explicit_tata_investment_corporation_still_resolves(self):
        """Negative control: the real company must still resolve when
        actually named -- Case F must not blanket-disable TATAINVEST."""
        entities = entities_mod.extract_entities("Tata Investment Corporation outlook")
        assert "TATAINVEST" in entities["companies"]

    def test_misspelled_tata_investment_still_fuzzy_resolves(self):
        """Negative control: a genuine misspelling of the real company,
        with its own distinctive "Tata" token present, must still fuzzy-
        match -- proving a distinctive token still rescues a gram that
        also contains query-framing words."""
        entities = entities_mod.extract_entities("What is the outlook for Tata Invstment Corporation?")
        assert "TATAINVEST" in entities["companies"]

    def test_no_regression_to_case_c_india_fix(self):
        """Negative control: Case F's new stopword/query-framing gate must
        not interact badly with Case C's fix."""
        entities = entities_mod.extract_entities("What is the latest update on Colgate-Palmolive India?")
        assert entities["companies"] == ["COLPAL"]
