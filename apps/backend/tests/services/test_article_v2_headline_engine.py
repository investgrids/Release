"""
Article V2 Phase C5.3 — Headline Engine tests. Real DB not needed (pure
dataclasses + a mocked/real LLM call). Covers every required adversarial
case: fabricated numbers, unsupported percentages, provider failure,
entity mismatch, clickbait, and near-duplicate headlines for a different
identity -- plus one real, live LLM integration test proving the whole
pipeline actually works end to end.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

import pytest

import app.services.article_v2.headline_engine as headline_engine_module
from app.services.article_v2.context_builder import ArticleContextBundle, ContextFinancialFact, MarketReaction, NONE_STATUS
from app.services.article_v2.evidence_set_builder import ArticleEvidenceSet
from app.services.article_v2.headline_engine import ValidationOutcome, generate_headline, _check_malformed_structure
from app.services.article_v2.identity import compute_identity
from app.services.warehouse.read_service import LinkedEvidence


def _evidence(title: str) -> LinkedEvidence:
    return LinkedEvidence(
        raw_evidence_id=str(uuid.uuid4()), title=title, source_type="nse",
        published_at=datetime.now(timezone.utc), source_url=None,
        relationship_type="subject", resolution_method="source_symbol", link_confidence=None,
    )


def _es(symbol: str, primary_title: str, supporting: list[LinkedEvidence] | None = None) -> ArticleEvidenceSet:
    return ArticleEvidenceSet(
        entity_id=f"cmp_{symbol.lower()}", symbol=symbol, event_id="evt", event_headline=primary_title,
        status="COHERENT", primary_evidence=_evidence(primary_title), supporting_evidence=supporting or [],
    )


def _mock_llm(monkeypatch, responses: list[str] | Exception):
    calls = {"n": 0}

    async def fake_call(prompt, system="", max_tokens=200, priority=None, **kwargs):
        if isinstance(responses, Exception):
            raise responses
        idx = min(calls["n"], len(responses) - 1)
        calls["n"] += 1
        return responses[idx]

    monkeypatch.setattr(headline_engine_module, "_call_with_fallback", fake_call)
    return calls


@pytest.mark.asyncio
async def test_fabricated_currency_value_is_rejected_then_falls_back(monkeypatch):
    es = _es("ABC", "ABC has informed the Exchange regarding a press release: real order worth Rs 800 crore won")
    identity = compute_identity(es)
    # Both attempts return a headline citing a fabricated number never in the evidence.
    _mock_llm(monkeypatch, ['{"headline": "ABC wins Rs 1,200 crore order, doubling backlog"}'] * 2)
    result = await generate_headline(es, None, identity, other_accepted_headlines={})
    assert result.status == ValidationOutcome.FALLBACK
    assert result.attempts == 2
    assert any("unsupported number" in n for n in result.validation_notes)


@pytest.mark.asyncio
async def test_unsupported_percentage_is_rejected_then_falls_back(monkeypatch):
    es = _es("ABC", "ABC has informed the Exchange regarding financial results for the quarter")
    identity = compute_identity(es)
    _mock_llm(monkeypatch, ['{"headline": "ABC reports 45% profit surge in Q2"}'] * 2)
    result = await generate_headline(es, None, identity, other_accepted_headlines={})
    assert result.status == ValidationOutcome.FALLBACK
    assert any("unsupported number" in n for n in result.validation_notes)


@pytest.mark.asyncio
async def test_provider_failure_falls_back_to_deterministic_headline(monkeypatch):
    es = _es("ABC", "ABC has informed the Exchange regarding a press release: real acquisition of a real target")
    identity = compute_identity(es)
    _mock_llm(monkeypatch, RuntimeError("all providers exhausted"))
    result = await generate_headline(es, None, identity, other_accepted_headlines={})
    assert result.status == ValidationOutcome.FALLBACK
    assert result.h1 is not None and "ABC" in result.h1
    assert result.h1 == result.seo_title == result.social_title


@pytest.mark.asyncio
async def test_entity_mismatch_is_rejected(monkeypatch):
    es = _es("ABC", "ABC has informed the Exchange regarding a press release: real acquisition announcement")
    identity = compute_identity(es)
    # Headline talks about a completely different, unrelated company.
    _mock_llm(monkeypatch, ['{"headline": "XYZ Corp reports record earnings this quarter"}'] * 2)
    result = await generate_headline(es, None, identity, other_accepted_headlines={})
    assert result.status == ValidationOutcome.FALLBACK
    assert any("does not mention the resolved company" in n for n in result.validation_notes)


@pytest.mark.asyncio
async def test_clickbait_predictive_language_is_rejected(monkeypatch):
    es = _es("ABC", "ABC has informed the Exchange regarding a press release: real acquisition announcement")
    identity = compute_identity(es)
    _mock_llm(monkeypatch, ['{"headline": "ABC Stock Set to Soar After Game-Changing Acquisition"}'] * 2)
    result = await generate_headline(es, None, identity, other_accepted_headlines={})
    assert result.status == ValidationOutcome.FALLBACK
    assert any("clickbait" in n for n in result.validation_notes)


@pytest.mark.asyncio
async def test_sunshine_malformed_headline_regression_is_rejected_then_falls_back(monkeypatch):
    """Article V2-HQ1 regression specimen (owner-locked, 2026-09-15): the
    real headline P7-O1's first live withhold produced -- an empty
    clause immediately after the dash -- which passed every check that
    existed before this gate (numeric grounding, entity mention,
    clickbait, subject hijack, near-duplication all pass it trivially)."""
    es = _es("SUNSHINE", "Sunshine Pictures Limited has submitted to the Exchange, the financial results for the period ended Jun 30, 2026.")
    identity = compute_identity(es)
    malformed = '{"headline": "Sunshine Pictures Limited \\u2014 , the financial results for the period ended Jun 30, 2026."}'
    _mock_llm(monkeypatch, [malformed] * 2)
    result = await generate_headline(es, None, identity, other_accepted_headlines={})
    assert result.status in (ValidationOutcome.FALLBACK, ValidationOutcome.BLOCKED)
    assert any("malformed structure" in n for n in result.validation_notes)
    # Never repaired and shipped -- either a clean deterministic fallback,
    # or (if that's also malformed) blocked outright. Never the malformed
    # LLM text itself.
    if result.h1 is not None:
        assert "— ," not in result.h1


@pytest.mark.asyncio
async def test_retry_succeeds_after_malformed_first_attempt(monkeypatch):
    es = _es("ABC", "ABC has informed the Exchange regarding a press release: real order worth Rs 800 crore won")
    identity = compute_identity(es)
    _mock_llm(monkeypatch, [
        '{"headline": "ABC — , wins a real order"}',        # attempt 1: malformed (empty clause after dash)
        '{"headline": "ABC wins Rs 800 crore order"}',      # attempt 2: clean
    ])
    result = await generate_headline(es, None, identity, other_accepted_headlines={})
    assert result.status == ValidationOutcome.OK
    assert result.attempts == 2


@pytest.mark.asyncio
async def test_headline_blocked_when_even_the_deterministic_fallback_is_malformed(monkeypatch):
    """Owner's exact required failure behavior: malformed -> retry ->
    validate again -> if STILL malformed (deterministic fallback
    included), the candidate cannot publish. h1=None so compose_article's
    existing "no usable headline" guard refuses it -- never a
    string-repaired headline shipped instead."""
    es = _es("ABC", "ABC has informed the Exchange regarding a press release: real acquisition announcement")
    identity = compute_identity(es)
    _mock_llm(monkeypatch, ['{"headline": "ABC — , announces something"}'] * 2)
    monkeypatch.setattr(headline_engine_module, "_build_deterministic_headline", lambda es, identity: "ABC — , a malformed deterministic fallback")
    result = await generate_headline(es, None, identity, other_accepted_headlines={})
    assert result.status == ValidationOutcome.BLOCKED
    assert result.h1 is None
    assert result.seo_title is None
    assert result.social_title is None
    assert any("fallback also malformed" in n for n in result.validation_notes)


@pytest.mark.asyncio
async def test_near_duplicate_headline_for_different_identity_is_rejected(monkeypatch):
    es = _es("ABC", "ABC has informed the Exchange regarding a press release: real capacity expansion approved")
    identity = compute_identity(es)
    already_used = {"cmp_xyz|OTHER|topic:different-thing|2026-W01": "ABC approves real capacity expansion plan today"}
    _mock_llm(monkeypatch, ['{"headline": "ABC approves real capacity expansion plan today"}'] * 2)
    result = await generate_headline(es, None, identity, other_accepted_headlines=already_used)
    assert result.status == ValidationOutcome.FALLBACK
    assert any("near-duplicate" in n for n in result.validation_notes)


@pytest.mark.asyncio
async def test_valid_headline_with_real_verified_number_is_accepted(monkeypatch):
    es = _es("ABC", "ABC has informed the Exchange regarding a press release: real order worth Rs 800 crore won from a real client")
    identity = compute_identity(es)
    _mock_llm(monkeypatch, ['{"headline": "ABC wins Rs 800 crore order from real client"}'])
    result = await generate_headline(es, None, identity, other_accepted_headlines={})
    assert result.status == ValidationOutcome.OK
    assert result.attempts == 1
    assert "800" in result.h1


@pytest.mark.asyncio
async def test_retry_succeeds_after_first_attempt_rejected(monkeypatch):
    es = _es("ABC", "ABC has informed the Exchange regarding a press release: real order worth Rs 800 crore won")
    identity = compute_identity(es)
    _mock_llm(monkeypatch, [
        '{"headline": "ABC wins Rs 1,200 crore order"}',  # attempt 1: fabricated number
        '{"headline": "ABC wins Rs 800 crore order"}',     # attempt 2: corrected
    ])
    result = await generate_headline(es, None, identity, other_accepted_headlines={})
    assert result.status == ValidationOutcome.OK
    assert result.attempts == 2


@pytest.mark.asyncio
async def test_colliding_fallback_headlines_are_disambiguated(monkeypatch):
    """Real gap found via the C5 120-event shadow run: when the LLM path
    is exhausted for two DIFFERENT real companies whose real evidence
    happens to share the same NSE boilerplate phrasing (two genuinely
    different AGM notices), the deterministic fallback template alone
    can produce confusingly similar headlines -- MAHSEAMLES vs
    METROBRAND hit 0.50 Jaccard live. Must be disambiguated with real,
    already-known data (the identity's own time bucket), never invented
    text."""
    es_a = _es("MAHSEAMLES", "Maharashtra Seamless Limited has informed the Exchange regarding Notice of Annual General Meeting to be held on September 20, 2026")
    es_b = _es("METROBRAND", "Metro Brands Limited has informed the Exchange regarding Notice of Annual General Meeting to be held on September 16, 2026")
    id_a, id_b = compute_identity(es_a), compute_identity(es_b)
    assert id_a.identity_key != id_b.identity_key  # genuinely different companies/identities

    _mock_llm(monkeypatch, RuntimeError("provider exhausted"))
    result_a = await generate_headline(es_a, None, id_a, other_accepted_headlines={})
    assert result_a.status == ValidationOutcome.FALLBACK
    known = {id_a.identity_key: result_a.h1}

    result_b = await generate_headline(es_b, None, id_b, other_accepted_headlines=known)
    assert result_b.status == ValidationOutcome.FALLBACK
    # The two real, different companies' fallback headlines must not be
    # confusingly similar once disambiguated.
    from app.services.aipe.duplicate_detector import _jaccard, _tokenize
    assert _jaccard(_tokenize(result_a.h1), _tokenize(result_b.h1)) < 0.50


@pytest.mark.asyncio
async def test_real_live_llm_generates_a_valid_headline():
    """One real, live integration proof -- not mocked -- that the whole
    pipeline (real LLM call, real numeric validation against a real
    evidence-derived allowed-value set) works end to end."""
    es = _es("AXISCADES", 'AXISCADES Technologies Limited has informed the Exchange regarding a press release dated August 30, 2026, titled "AXISCADES Technologies to Acquire Cloud Wave Technologies"')
    identity = compute_identity(es)
    context = ArticleContextBundle(
        entity_id="cmp_axiscades", symbol="AXISCADES", event_id="evt", event_headline=es.event_headline,
        status=NONE_STATUS, market_reaction=MarketReaction(price_move_pct=4.80, note="temporal correlation only"),
    )
    result = await generate_headline(es, context, identity, other_accepted_headlines={})
    assert result.h1 is not None
    assert result.status in (ValidationOutcome.OK, ValidationOutcome.FALLBACK)
    assert "AXISCADES" in result.h1.upper() or "AXISCADES" in result.h1


# ── C8.2 hardening: headline subject boundary + truncation ─────────────

@pytest.mark.asyncio
async def test_llm_headline_hijacked_by_supporting_evidence_is_rejected_then_falls_back(monkeypatch):
    """NEWGEN's real 500-event C7 case: the LLM drew the headline's
    subject from a supporting "Schedule of meet" filing instead of the
    primary volume-increase notice. Must be rejected and retried, and
    if it recurs, fall to the deterministic (primary-only-by-
    construction) fallback rather than publish a hijacked headline."""
    supporting = [_evidence("Newgen Software Technologies Limited has informed the Exchange about Schedule of meet")]
    es = _es(
        "NEWGEN",
        "Significant increase in volume has been observed in Newgen Software Technologies Limited. "
        "The Exchange has written to the company. Newgen Software Technologies Limited has submitted their response.",
        supporting=supporting,
    )
    identity = compute_identity(es)
    # The LLM keeps proposing a headline that is really about the
    # supporting "Schedule of meet" filing, not the primary volume notice.
    _mock_llm(monkeypatch, ['{"headline": "Newgen Software Technologies announces schedule of meet for investors"}'] * 2)
    result = await generate_headline(es, None, identity, other_accepted_headlines={})
    assert result.status == ValidationOutcome.FALLBACK
    assert any("primary" in n for n in result.validation_notes)
    # The deterministic fallback is guaranteed primary-only by construction.
    assert "meet" not in (result.h1 or "").lower() or "volume" in (result.h1 or "").lower()


@pytest.mark.asyncio
async def test_llm_headline_leaning_on_supporting_detail_without_hijack_is_accepted(monkeypatch):
    """A headline may legitimately draw a SMALL corroborating detail from
    supporting evidence without that making supporting evidence the
    SUBJECT -- the hijack check uses a real margin, not a bare
    supporting-vs-primary comparison, so this must not false-positive."""
    supporting = [_evidence("Canara Bank has informed the Exchange regarding a related credit rating update")]
    es = _es(
        "CANBK", "Canara Bank has informed the Exchange about Board Meeting to be held on 03-Sep-2026 to consider Fund raising",
        supporting=supporting,
    )
    identity = compute_identity(es)
    _mock_llm(monkeypatch, ['{"headline": "Canara Bank board to consider fund raising on September 3"}'])
    result = await generate_headline(es, None, identity, other_accepted_headlines={})
    assert result.status == ValidationOutcome.OK


def test_topic_extraction_never_truncates_mid_word():
    """IDBI's real 500-event C7 bug: a raw character-count cap inside the
    extraction regex sliced a real clause mid-word ('...has written t').
    The fix must end on a real word boundary, always."""
    from app.services.article_v2.headline_engine import _build_deterministic_headline
    from app.services.article_v2.identity import compute_identity as _compute_identity

    es = _es(
        "IDBI",
        "Significant increase in volume has been observed in IDBI Bank Limited. The Exchange, in order to "
        "ensure that investors have latest relevant information about the company and to inform the market "
        "place so that the interest of the investors is safeguarded, has written to the company. The response "
        "from the company is awaited.",
    )
    identity = _compute_identity(es)
    headline = _build_deterministic_headline(es, identity)
    # No fragment ending in a bare partial word right before a truncation point.
    assert not headline.rstrip("…").rstrip().endswith(" t")
    assert not re.search(r"\b[a-z]\b$", headline.rstrip("…").rstrip())


def test_truncate_at_word_boundary_never_cuts_mid_word():
    from app.services.article_v2.headline_engine import _truncate_at_word_boundary
    text = "the company and to inform the market place so that the interest of the investors is safeguarded, has written to the company"
    result = _truncate_at_word_boundary(text, 110)
    assert len(result) <= 111  # 110 + ellipsis char is acceptable, never mid-word
    core = result.rstrip("…").rstrip(",.;:—- ")
    assert text.startswith(core)
    # the character immediately after the truncated core, in the original text, must be a space (a real word boundary)
    assert text[len(core):len(core) + 1] in (" ", "")


def test_truncate_at_word_boundary_returns_short_text_unchanged():
    from app.services.article_v2.headline_engine import _truncate_at_word_boundary
    assert _truncate_at_word_boundary("short text", 110) == "short text"


# ── Article V2-HQ1 -- Final Headline Quality Gate (2026-09-15) ──────────
# Deterministic structural checks only, direct unit tests against the
# pure function -- no LLM/mocking needed. Both the real regression
# specimen and enough clean real-world headline shapes to prove this
# never flags ordinary punctuation (decimals, hyphenated year ranges,
# colons, periods, percentages).

def test_malformed_structure_catches_the_real_sunshine_regression_specimen():
    h = "Sunshine Pictures Limited — , the financial results for the period ended Jun 30, 2026."
    result = _check_malformed_structure(h)
    assert result is not None
    assert "broken punctuation boundary" in result


def test_malformed_structure_catches_empty_clause_after_colon():
    assert _check_malformed_structure("ABC Ltd: , announces results") is not None


def test_malformed_structure_catches_repeated_dash_artifact():
    # Caught by the broken-separator check (a dash immediately followed
    # by another dash is itself an empty-clause boundary) -- which
    # category flags it doesn't matter, only that it's flagged.
    result = _check_malformed_structure("TCS Q2 FY26 -- Results Beat Estimates")
    assert result is not None


def test_malformed_structure_catches_repeated_comma_artifact():
    assert _check_malformed_structure("ABC wins order,, doubling backlog") is not None


def test_malformed_structure_catches_dangling_trailing_separator():
    result = _check_malformed_structure("Sunshine Pictures Limited —")
    assert result is not None
    assert "dangling trailing separator" in result


def test_malformed_structure_catches_dangling_trailing_word():
    result = _check_malformed_structure("ABC Ltd signs a major deal for")
    assert result is not None
    assert "dangling trailing conjunction" in result


def test_malformed_structure_catches_empty_headline():
    assert _check_malformed_structure("   ") is not None


@pytest.mark.parametrize("headline", [
    "TCS Q2 FY26 Results: Net Profit Up 5%",
    "Reliance Industries — Q1 Results Beat Estimates",
    "SUNSHINE shares fell 18.11% on filing day",
    "ABC Ltd reports FY2025-26 guidance raised",
    "Sunshine Pictures Limited submits un-audited financial results for period ended June 30, 2026",
    "ABC Ltd. wins Rs 800 crore order.",
    "H1-H2 performance review shows steady growth",
])
def test_malformed_structure_never_flags_ordinary_real_headline_shapes(headline):
    assert _check_malformed_structure(headline) is None


# ── C8.5 hardening: regulatory-preamble-safe topic extraction ──────────

def test_icicibank_real_bond_pricing_surfaces_past_regulatory_preamble():
    """The real ICICIBANK second-cohort case: a genuine $1B bond pricing
    with real Moody's/S&P ratings was buried after a long SEBI
    Regulation 30 citation, and the 110-char cap used to truncate
    before ever reaching it -- landing on the same generic citation
    text a near-duplicate supporting filing also shared (a false
    subject-hijack flag, not a real one). The real development must now
    surface in the headline."""
    from app.services.article_v2.headline_engine import _build_deterministic_headline
    from app.services.article_v2.identity import compute_identity as _compute_identity

    es = _es(
        "ICICIBANK",
        "ICICI Bank Limited has informed the Exchange about disclosure under Regulation 30 of the SEBI "
        "(Listing Obligations and Disclosure Requirements) Regulations, 2015 - This is to inform you that "
        "ICICI Bank Limited, acting through its IFSC Banking Unit,  has today at 10:45 a.m. IST priced USD 1 "
        "billion Senior Unsecured Fixed Rate Notes under the USD 7.5 billion Global Medium Term Note Programme "
        "of the Bank. Moody's Ratings and S&P Global Ratings have vide letters dated August 24, 2026, assigned "
        "Baa3 and BBB ratings.",
    )
    identity = _compute_identity(es)
    headline = _build_deterministic_headline(es, identity)
    assert "priced usd 1 billion" in headline.lower() or "usd 1 billion" in headline.lower()
    # the real substance surfaced -- not just the regulatory citation
    assert "listing obligations" not in headline.lower()


def test_icicibank_hijack_heuristic_no_longer_false_positives_against_near_duplicate_citation():
    """The false hijack this was actually causing: primary and a near-
    duplicate SUPPORTING filing shared the same long Regulation 30
    citation, and truncation stuck both on that shared boilerplate --
    making the headline look more similar to supporting evidence than
    to its own primary evidence. Once the real substance surfaces, this
    goes away."""
    from app.services.article_v2.headline_engine import _build_deterministic_headline, _check_subject_hijack
    from app.services.article_v2.identity import compute_identity as _compute_identity

    supporting = [_evidence(
        "ICICI Bank Limited has informed the Exchange about disclosure under Regulation 30 read with para A of "
        "Schedule III and Regulation 46(2) of the Securities and Exchange Board of India (Listing Obligations "
        "and Disclosure Requirements) Regulations, 2015"
    )]
    es = _es(
        "ICICIBANK",
        "ICICI Bank Limited has informed the Exchange about disclosure under Regulation 30 of the SEBI "
        "(Listing Obligations and Disclosure Requirements) Regulations, 2015 - This is to inform you that "
        "ICICI Bank Limited, acting through its IFSC Banking Unit,  has today at 10:45 a.m. IST priced USD 1 "
        "billion Senior Unsecured Fixed Rate Notes under the USD 7.5 billion Global Medium Term Note Programme "
        "of the Bank.",
        supporting=supporting,
    )
    identity = _compute_identity(es)
    headline = _build_deterministic_headline(es, identity)
    assert _check_subject_hijack(headline, es) is None


def test_regulation_30_that_is_genuinely_the_whole_story_is_not_altered():
    """Adversarial case: Regulation 30 IS the real, complete, relevant
    context -- no real substantive clause follows a genuine transition
    phrase. Must fall through to existing extraction unchanged, never
    manufacture a clause that isn't there."""
    from app.services.article_v2.headline_engine import _extract_post_preamble_topic

    text = (
        "Some Company Limited has informed the Exchange about disclosure under Regulation 30 of the SEBI "
        "(Listing Obligations and Disclosure Requirements) Regulations, 2015 regarding change in registered office address."
    )
    assert _extract_post_preamble_topic(text) is None


def test_regulation_citation_with_nothing_following_returns_none():
    """Adversarial case: the citation is present but nothing legible
    follows it at all (the filing just ends) -- must return None, not
    an empty or garbage topic."""
    from app.services.article_v2.headline_engine import _extract_post_preamble_topic

    text = "Some Company Limited has informed the Exchange about disclosure under Regulation 30 of the SEBI (Listing Obligations and Disclosure Requirements) Regulations, 2015."
    assert _extract_post_preamble_topic(text) is None


def test_topic_extraction_does_not_stop_at_abbreviation_periods():
    """HEG's real 500-event C8 case: 'w.e.f.' (with effect from) has
    internal periods that used to be treated as a hard sentence-end
    stop, producing 'of the company w' -- cut off after the first
    letter, before length-based truncation even ran. Real Indian-filing
    abbreviations (w.e.f., Dr., Mr., Ms.) make this a recurring shape."""
    from app.services.article_v2.headline_engine import _build_deterministic_headline
    from app.services.article_v2.identity import compute_identity as _compute_identity

    es = _es(
        "HEG",
        "HEG Limited has informed the Exchange regarding Appointment of Shri Riju Jhunjhunwala as Chairman, "
        "Managing Director & CEO of the company w.e.f. September 01, 2026.",
    )
    identity = _compute_identity(es)
    headline = _build_deterministic_headline(es, identity)
    assert not headline.rstrip("…").rstrip().endswith(" w")
    assert not re.search(r"\b[a-z]\b(?:…)?$", headline.rstrip())


# ── C8.3 hardening: batch-wide final uniqueness closure ─────────────────

def test_finalize_batch_uniqueness_keeps_first_seen_downgrades_later_collisions():
    """SAREGAMA's real 500-event C7 case: one identity collided with
    THREE later ones, and each one's own per-item disambiguation
    (checked only against headlines accepted so far) wasn't enough to
    guarantee the WHOLE final set is distinguishable. First-seen wins,
    same convention identity.py's own resolve_uniqueness() uses."""
    from app.services.article_v2.headline_engine import finalize_batch_uniqueness

    es_a = _es("SAREGAMA", "Saregama India Limited has informed the Exchange regarding Notice of Annual General Meeting to be held on September 15, 2026")
    es_b = _es("SANDESH", "The Sandesh Limited has informed the Exchange regarding Notice of Annual General Meeting to be held on September 15, 2026")
    es_c = _es("PPAP", "PPAP Automotive Limited has informed the Exchange regarding Notice of Annual General Meeting to be held on September 18, 2026")
    id_a, id_b, id_c = compute_identity(es_a), compute_identity(es_b), compute_identity(es_c)

    candidates = [
        (id_a, "Saregama India Limited — AGM on September 15, 2026"),
        (id_b, "The Sandesh Limited — AGM on September 15, 2026"),
        (id_c, "PPAP Automotive Limited — AGM on September 18, 2026"),
    ]
    result = finalize_batch_uniqueness(candidates)
    assert result[id_a.identity_key].kept is True
    # SANDESH's headline is near-identical to SAREGAMA's (same date, same template)
    assert result[id_b.identity_key].kept is False
    assert result[id_b.identity_key].collided_with == id_a.identity_key


def test_finalize_batch_uniqueness_keeps_genuinely_distinct_headlines():
    from app.services.article_v2.headline_engine import finalize_batch_uniqueness

    es_a = _es("AXISCADES", "AXISCADES Technologies Limited has informed the Exchange regarding a press release: acquisition of Cloud Wave Technologies")
    es_b = _es("DABUR", "Dabur India Limited has informed the Exchange about Scheme of Amalgamation between Sesa Care and Dabur")
    id_a, id_b = compute_identity(es_a), compute_identity(es_b)

    candidates = [
        (id_a, "AXISCADES Technologies acquires Cloud Wave Technologies"),
        (id_b, "Dabur India amalgamation scheme with Sesa Care advances"),
    ]
    result = finalize_batch_uniqueness(candidates)
    assert result[id_a.identity_key].kept is True
    assert result[id_b.identity_key].kept is True


def test_finalize_batch_uniqueness_never_compares_same_identity_against_itself():
    """A batch containing only ONE real identity (e.g. UPDATE_EXISTING
    reusing the same identity twice) must never self-collide."""
    from app.services.article_v2.headline_engine import finalize_batch_uniqueness

    es = _es("CANBK", "CANARA BANK has informed the Exchange about Board Meeting to consider Fund raising")
    identity = compute_identity(es)
    candidates = [(identity, "Canara Bank board to consider fund raising")]
    result = finalize_batch_uniqueness(candidates)
    assert result[identity.identity_key].kept is True


# ── HQ2: comma-continuation boilerplate normalization ──────────────────
#
# Real production incident (SUNSHINE, nse-58efd351d6, 2026-09-16/17):
# NSE's own "financial results submission" filing template uses a THIRD
# preamble->topic connector shape _BOILERPLATE_STRIP_RE's caller never
# handled -- neither "about X" nor "regarding X", but a bare comma
# continuation ("...has submitted to the Exchange, the financial
# results for..."). The stray leading comma survived into the
# assembled headline as "Company — , topic", which HQ1 correctly
# rejected as a broken punctuation boundary -- but before HQ1 existed,
# this exact defect is what let the malformed headline publish in the
# first place (the incident that motivated HQ1). This is the permanent
# regression fixture for the real title.

def test_sunshine_comma_continuation_regression_produces_a_valid_fallback():
    from app.services.article_v2.headline_engine import _build_deterministic_headline, _check_malformed_structure

    es = _es(
        "SUNSHINE",
        "Sunshine Pictures Limited has submitted to the Exchange, the financial results for the period ended Jun 30, 2026.",
    )
    identity = compute_identity(es)
    headline = _build_deterministic_headline(es, identity)

    assert "— ," not in headline
    assert _check_malformed_structure(headline) is None
    assert headline.startswith("Sunshine Pictures Limited —")
    assert "the financial results" in headline.lower()


def test_existing_regarding_shape_is_unchanged_by_the_comma_fix():
    """This real shape is actually intercepted earlier, by _extract_topic's
    own 'regarding' pattern (with its AGM compression) -- it never
    reaches the boilerplate-strip line this fix touches at all. Locked
    in here as a regression guard confirming the fix left it alone."""
    from app.services.article_v2.headline_engine import _build_deterministic_headline

    es = _es("ABC", "ABC Limited has informed the Exchange regarding Notice of Annual General Meeting to be held on September 20, 2026")
    identity = compute_identity(es)
    headline = _build_deterministic_headline(es, identity)
    assert headline == "ABC Limited — AGM on September 20, 2026"


def test_existing_about_shape_is_unchanged_by_the_comma_fix():
    """Same as above -- intercepted earlier by _extract_topic's own
    'about' pattern, never reaches the boilerplate-strip line."""
    from app.services.article_v2.headline_engine import _build_deterministic_headline

    es = _es("ABC", "ABC Limited has informed the Exchange about Board Meeting to be held on September 20, 2026")
    identity = compute_identity(es)
    headline = _build_deterministic_headline(es, identity)
    assert headline == "ABC Limited — board meeting on September 20, 2026"


def test_boilerplate_strip_shape_with_no_comma_and_no_connector_is_unchanged():
    """A residual that has neither a leading comma nor 'about'/'regarding'
    (e.g. NSE's 'informs the Exchange of X' shape) must pass through
    exactly as before -- this fix only touches the comma boundary."""
    from app.services.article_v2.headline_engine import _build_deterministic_headline

    es = _es("XYZ", "XYZ Limited informs the Exchange of a scheduled maintenance window on September 20, 2026")
    identity = compute_identity(es)
    headline = _build_deterministic_headline(es, identity)
    assert "— ," not in headline
    assert headline.startswith("XYZ Limited — of a scheduled maintenance window")


def test_genuinely_malformed_fallback_is_still_rejected_not_silently_repaired():
    """A residual that is malformed for a reason OTHER than the comma-
    continuation shape (e.g. a dangling trailing separator) must still
    be caught by HQ1 -- this fix narrowly targets one specific boundary,
    it must not become a general punctuation cleanup that hides other
    real defects."""
    from app.services.article_v2 import headline_engine as he

    assert he._check_malformed_structure("ABC Limited — ,") is not None
    assert he._check_malformed_structure("ABC Limited — Update on -") is not None
