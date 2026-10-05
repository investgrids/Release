"""
event_impact assembly (2026-09-22 audit -> narrow contract). See aev2/
event_impact.py's own docstring for exactly what this contract can and
cannot claim, and why.

Follows test_switch_analysis_assembly.py's own pattern: build a plain V3
response dict, project it through the real from_v3_response(), then
assemble through the real assemble_aev2() entry point — never construct
a CoreAnswer or an event_impact dict by hand for the eligibility tests.
The one exception is _build_observed_reactions, which is directly unit-
tested with synthetic PriceBar-shaped input (same precedent as
test_quant_backfill.py testing backfill._reject_non_trading_sessions
directly) since the real pipeline never calls it with non-empty input
today — see that function's own docstring.
"""
from __future__ import annotations

from app.services.ai_search.aev2 import event_impact
from app.services.ai_search.aev2.assemble import assemble_aev2
from app.services.ai_search.aev2.language_gate import FALLBACK_TEXT
from app.services.ai_search.aev2.mode import AEV2Mode
from app.services.ai_search.core_answer import from_v3_response

RELIANCE = {"symbol": "RELIANCE", "name": "Reliance Industries Ltd"}
TCS = {"symbol": "TCS", "name": "Tata Consultancy Services Ltd"}

REAL_EVENT = {
    "id": "e-reliance-1",
    "slug": "reliance-jio-completes-pan-india-5g-rollout-e-reliance-1",
    "title": "Reliance Jio completes pan-India 5G network rollout",
    "summary": "Reliance Jio Infocomm Limited informed the Exchange that it has completed 5G network rollout across all 22 telecom circles in India.",
    "category": "Corporate",
    "impact_score": 7.5,
    "confidence": 8.0,
    "sectors": ["Telecom"],
    "companies": [RELIANCE],
    "date": "Sep 15, 2026",
    "source": "nse_announcements",
    "event_date": "2026-09-15",
    "published_at": "2026-09-15T09:30:00+00:00",
}

# The real shape the 2026-09-22 provenance trace found for the 3 leaked
# seed fixtures removed in that day's content-integrity repair: no real
# `source`, no real linked companies. Kept as a regression fixture here
# (never re-inserted into any production data) to prove eligibility
# rejects this SHAPE structurally, not by matching its specific id.
LEAKED_FIXTURE_SHAPED_EVENT = {
    "id": "evt-rbi-june-2026",
    "slug": "",
    "title": "RBI Monetary Policy Committee Holds Repo Rate",
    "summary": "The RBI's MPC held the repo rate steady at its June meeting.",
    "category": "Market",
    "impact_score": 0.0,
    "confidence": 0.0,
    "sectors": [],
    "companies": [],
    "date": "",
    "source": "",
    "event_date": None,
    "published_at": None,
}


def _v3_response(**overrides) -> dict:
    base = {
        "query": "Reliance Jio just announced its 5G rollout is complete, what does this mean?",
        "response_id": "resp-event-impact-1",
        "specialist": "company",
        "intent": "news_reaction",
        "answer": {
            "bottom_line": "Jio's completion of its nationwide 5G rollout strengthens Reliance's telecom infrastructure position.",
            "summary": "ok",
            "what_happened": "", "why_it_happened": "", "immediate_impact": "",
            "medium_term": "", "long_term": "", "risks": [],
        },
        "companies": [
            {"symbol": "RELIANCE", "name": "Reliance Industries Ltd", "price": "1,257.50", "change": "+0.40%",
             "positive": True, "price_fetched_at": "2026-09-21T10:00:00+00:00"},
        ],
        "related_events": [dict(REAL_EVENT)],
        "news": [], "policies": [],
        "investment_verdict": {"horizon": "3-6 months"},
        "confidence_breakdown": {
            "evidence_quality": 65.0, "market_confirmation": 55.0,
            "historical_similarity": 30.0, "data_freshness": 95.0,
        },
    }
    base.update(overrides)
    return base


def _assemble(**overrides):
    core = from_v3_response(_v3_response(**overrides))
    return assemble_aev2(core, mode=AEV2Mode.PUBLIC)


# ── Eligibility — structural, not an ID blacklist ───────────────────────

def test_real_source_derived_event_succeeds():
    result = _assemble()
    ei = result["event_impact"]
    assert ei is not None
    assert ei["event"]["id"] == "e-reliance-1"
    assert ei["event"]["title"] == REAL_EVENT["title"]
    assert ei["event"]["summary"] == REAL_EVENT["summary"]
    assert ei["event"]["source_name"] == "nse_announcements"
    assert ei["event"]["published_at"] == "2026-09-15T09:30:00+00:00"
    assert ei["event"]["internal_url"] == f"/events/{REAL_EVENT['slug']}"
    assert ei["linked_companies"] == [{"symbol": "RELIANCE", "name": "Reliance Industries Ltd"}]


def test_source_null_event_fails():
    result = _assemble(related_events=[{**REAL_EVENT, "source": ""}])
    assert result["event_impact"] is None


def test_known_leaked_fixture_shape_fails_structurally():
    """Not an ID check — this exact fixture id could be renamed tomorrow
    and this test would still pass, because the rejection is driven by
    the shape (no source, no linked companies), never a blacklist
    lookup."""
    result = _assemble(related_events=[dict(LEAKED_FIXTURE_SHAPED_EVENT)])
    assert result["event_impact"] is None


def test_missing_company_attribution_fails():
    result = _assemble(related_events=[{**REAL_EVENT, "companies": []}])
    assert result["event_impact"] is None


def test_missing_published_at_fails():
    result = _assemble(related_events=[{**REAL_EVENT, "published_at": None}])
    assert result["event_impact"] is None


def test_missing_title_or_summary_fails():
    result = _assemble(related_events=[{**REAL_EVENT, "summary": ""}])
    assert result["event_impact"] is None


def test_missing_internal_url_fails_when_no_slug_exists():
    result = _assemble(related_events=[{**REAL_EVENT, "slug": ""}])
    assert result["event_impact"] is None


def test_optional_sectors_omitted_cleanly():
    result = _assemble(related_events=[{**REAL_EVENT, "sectors": []}])
    ei = result["event_impact"]
    assert ei is not None
    assert ei["linked_sectors"] == []


def test_two_resolved_events_fail_honestly():
    second_event = {**REAL_EVENT, "id": "e-reliance-2", "title": "A second, unrelated Reliance event"}
    result = _assemble(related_events=[dict(REAL_EVENT), second_event])
    assert result["event_impact"] is None


def test_original_source_url_is_always_none_today():
    """Event carries no original-publisher-URL column at all (schema
    inspection, 2026-09-22) — always None, the honest state for every
    real event, not a per-row failure. The frontend renders the
    documented fallback notice for this."""
    result = _assemble()
    assert result["event_impact"]["event"]["original_source_url"] is None


# ── direct_conclusion — validated + event-scoped entity check ──────────

def test_direct_conclusion_text_and_refs_when_validated():
    result = _assemble()
    dc = result["event_impact"]["direct_conclusion"]
    assert dc["validation_status"] == "validated"
    assert "Jio's completion" in dc["text"]
    assert dc["evidence_refs"] == ["event:e-reliance-1"]


def test_direct_conclusion_fails_closed_on_advisory_language():
    result = _assemble(answer={
        "bottom_line": "This is a solid buy opportunity following Reliance Jio's 5G rollout.",
        "summary": "ok", "what_happened": "", "why_it_happened": "", "immediate_impact": "",
        "medium_term": "", "long_term": "", "risks": [],
    })
    dc = result["event_impact"]["direct_conclusion"]
    assert dc["validation_status"] == "unvalidated"
    assert dc["text"] == FALLBACK_TEXT["direct_conclusion"]
    assert dc["evidence_refs"] == []


def test_wrong_company_citation_fails_even_though_the_company_resolved_elsewhere():
    """TCS is a real, resolved CoreAnswer.companies entry (so it passes
    the GENERAL entities_supported check), but it is NOT one of THIS
    event's own linked companies — the event-scoped check must reject it
    on its own, proving 'every company named in the conclusion belongs
    to Event.companies' is enforced independently of the general check."""
    result = _assemble(
        companies=[
            {"symbol": "RELIANCE", "name": "Reliance Industries Ltd", "price": "1,257.50", "change": "+0.40%",
             "positive": True, "price_fetched_at": "2026-09-21T10:00:00+00:00"},
            {"symbol": "TCS", "name": "Tata Consultancy Services Ltd", "price": "4,102.50", "change": "-0.20%",
             "positive": False, "price_fetched_at": "2026-09-21T10:00:00+00:00"},
        ],
        answer={
            "bottom_line": "Reliance Jio's 5G rollout completion also benefits TCS through expanded network partnerships.",
            "summary": "ok", "what_happened": "", "why_it_happened": "", "immediate_impact": "",
            "medium_term": "", "long_term": "", "risks": [],
        },
    )
    ei = result["event_impact"]
    assert ei is not None  # not applicable -> still None; ineligible claim -> object still returns, unvalidated
    dc = ei["direct_conclusion"]
    assert dc["validation_status"] == "unvalidated"
    assert dc["text"] == FALLBACK_TEXT["direct_conclusion"]


def test_validated_direct_conclusion_always_cites_the_primary_event_id():
    """Citation invariant (2026-09-22 review): direct_conclusion.
    evidence_refs must be a subset of {resolved primary Event evidence}
    — and on a validated claim, must actually CONTAIN the primary Event
    ID, not just be a permissible subset that happens to be empty."""
    result = _assemble()
    dc = result["event_impact"]["direct_conclusion"]
    assert dc["validation_status"] == "validated"
    assert dc["evidence_refs"] == ["event:e-reliance-1"]


def test_unrelated_announcement_for_a_company_resolved_elsewhere_never_leaks_into_evidence_refs():
    """Citation invariant (2026-09-22 review): the general citation
    catalogue must not let an unrelated Announcement (or News/Policy/
    second Event) validate this Event's own conclusion merely because
    it names a company that happens to be resolved somewhere else in
    the same query. TCS is a real CoreAnswer.companies entry with a real
    attributed announcement, but TCS is NOT one of THIS event's own
    linked companies and is never mentioned in bottom_line — under the
    old, too-broad claim_refs scoping this TCS announcement would have
    leaked into direct_conclusion.evidence_refs simply because
    deterministic_claim_evidence_refs matches against ALL of
    core.companies, not this event's own companies."""
    result = _assemble(
        companies=[
            {"symbol": "RELIANCE", "name": "Reliance Industries Ltd", "price": "1,257.50", "change": "+0.40%",
             "positive": True, "price_fetched_at": "2026-09-21T10:00:00+00:00"},
            {"symbol": "TCS", "name": "Tata Consultancy Services Ltd", "price": "4,102.50", "change": "-0.20%",
             "positive": False, "price_fetched_at": "2026-09-21T10:00:00+00:00"},
        ],
        announcements=[{"id": "ann-tcs-1", "symbol": "TCS", "subject": "TCS wins a new cloud contract", "announcement_date": "2026-09-20"}],
    )
    dc = result["event_impact"]["direct_conclusion"]
    assert dc["validation_status"] == "validated"
    assert dc["evidence_refs"] == ["event:e-reliance-1"]
    assert "announcement:ann-tcs-1" not in dc["evidence_refs"]


# ── Forbidden concepts are structurally unreachable ─────────────────────

def _all_keys(obj) -> set[str]:
    keys: set[str] = set()
    if isinstance(obj, dict):
        keys |= set(obj.keys())
        for v in obj.values():
            keys |= _all_keys(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            keys |= _all_keys(v)
    return keys


def test_ai_summary_and_event_companies_reason_and_ripple_fields_are_structurally_unreachable():
    result = _assemble()
    keys = _all_keys(result["event_impact"])
    assert "ai_summary" not in keys
    assert "reason" not in keys
    assert "impact_type" not in keys
    assert "ripple" not in keys
    assert "graph" not in keys


def test_input_and_cached_objects_remain_unmodified():
    v3 = _v3_response()
    import copy
    original = copy.deepcopy(v3)
    core = from_v3_response(v3)
    before = dict(core.related_events[0])
    assemble_aev2(core, mode=AEV2Mode.PUBLIC)
    assert v3 == original
    assert dict(core.related_events[0]) == before


# ── observed_reactions — always [] today, but the filtering/window logic
#    is real and directly tested (see event_impact._build_observed_
#    reactions's own docstring for why). ──────────────────────────────

def test_missing_price_data_still_succeeds():
    result = _assemble()
    ei = result["event_impact"]
    assert ei is not None
    assert ei["observed_reactions"] == []


def test_holiday_and_thin_volume_price_data_excluded():
    linked = [{"symbol": "RELIANCE", "name": "Reliance Industries Ltd"}]
    bars = (
        {"symbol": "RELIANCE", "bar_date": "2026-09-11", "close": 1250.0, "data_quality": "good"},
        # A holiday bar that reached production before the trading-
        # calendar guard existed (the real 2026-09-22 Repair 2 incident).
        {"symbol": "RELIANCE", "bar_date": "2026-09-14", "close": 1250.0, "data_quality": "thin_volume"},
        {"symbol": "RELIANCE", "bar_date": "2026-09-15", "close": 1275.0, "data_quality": "good"},
    )
    reactions = event_impact._build_observed_reactions("2026-09-11", linked, bars)
    dates_used = {r["end_date"] for r in reactions}
    assert "2026-09-14" not in dates_used
    assert any(r["window"] == "next_session" and r["end_date"] == "2026-09-15" for r in reactions)


def test_clean_price_reaction_uses_correct_post_event_sessions():
    linked = [{"symbol": "RELIANCE", "name": "Reliance Industries Ltd"}]
    bars = tuple(
        {"symbol": "RELIANCE", "bar_date": d, "close": c, "data_quality": "good"}
        for d, c in [
            ("2026-09-11", 1250.0),  # base (on/before event date)
            ("2026-09-15", 1262.5),  # next_session (+1.0%)
            ("2026-09-16", 1260.0),
            ("2026-09-17", 1268.0),
            ("2026-09-18", 1270.0),
            ("2026-09-21", 1275.0),  # five_sessions
        ]
    )
    reactions = event_impact._build_observed_reactions("2026-09-11", linked, bars)
    next_session = next(r for r in reactions if r["window"] == "next_session")
    five_sessions = next(r for r in reactions if r["window"] == "five_sessions")
    assert next_session["start_date"] == "2026-09-11"
    assert next_session["end_date"] == "2026-09-15"
    assert next_session["percent_change"] == 1.0
    assert five_sessions["end_date"] == "2026-09-21"
    assert five_sessions["percent_change"] == 2.0


def test_price_reaction_never_claims_causation():
    linked = [{"symbol": "RELIANCE", "name": "Reliance Industries Ltd"}]
    bars = (
        {"symbol": "RELIANCE", "bar_date": "2026-09-11", "close": 1250.0, "data_quality": "good"},
        {"symbol": "RELIANCE", "bar_date": "2026-09-15", "close": 1262.5, "data_quality": "good"},
    )
    reactions = event_impact._build_observed_reactions("2026-09-11", linked, bars)
    assert reactions
    for r in reactions:
        assert set(r.keys()) == {
            "company", "window", "start_date", "end_date", "percent_change",
            "source", "data_quality", "evidence_refs",
        }
        assert r["data_quality"] == "good"


def test_observed_reactions_never_returned_for_a_company_not_linked_to_the_event():
    linked = [{"symbol": "RELIANCE", "name": "Reliance Industries Ltd"}]
    bars = (
        {"symbol": "TCS", "bar_date": "2026-09-11", "close": 4000.0, "data_quality": "good"},
        {"symbol": "TCS", "bar_date": "2026-09-15", "close": 4100.0, "data_quality": "good"},
    )
    reactions = event_impact._build_observed_reactions("2026-09-11", linked, bars)
    assert reactions == []
