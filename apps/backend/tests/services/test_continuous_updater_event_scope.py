"""
Workstream B regression suite (2026-10-24) — event-scope mismatch in the
continuous updater's takeaway path.

Confirmed from production: the 2026-09-01 CD2 fix removed the unfiltered-event
leak but kept SECTOR overlap sufficient for an event to update an article. A
market-wide development tagged with broad sectors (or an index ticker)
legitimately overlaps many unrelated articles' sectors, so the single
highest-urgency such event was stamped — identically — as the "LATEST:"
takeaway of dozens of company / question / theme / sector / ripple articles
(93 cross-type duplicate-takeaway groups / 425 articles published on/after
2026-09-01; newest 2026-10-07).

These tests pin the two defects closed:
  B1 scope mismatch — a market-wide event must not become a specific article's
     own takeaway via a bare sector overlap.
  B2 missing provenance — each takeaway update records its source event id,
     deterministic scope, and triage provenance in update_history.

No deployment, no production data changes. Pure functions where possible; a few
DB-backed tests exercise update_article()'s persistence and the why_it_matters
note the same way the existing CD2 suite does.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import delete, select

from app.db.session import AsyncSessionLocal
from app.db.models.intelligence_article import IntelligenceArticle
from app.services.aipe.continuous_updater import (
    _event_scope,
    _event_sets_takeaway,
    _generate_updated_takeaway,
    _select_takeaway_event,
    update_article,
)


# A minimal stand-in with just the two attributes the scope helpers read, so the
# pure-function tests need no DB row.
class _Article:
    def __init__(self, companies=None, sectors=None):
        self.companies_affected = companies or []
        self.sectors_affected = sectors or []


def _ev(**kw):
    kw.setdefault("urgency", 8)
    kw.setdefault("one_liner", "some development")
    return kw


# ── _event_scope: deterministic, conservative, metadata-only ─────────────────

def test_scope_entity_from_specific_ticker():
    assert _event_scope(_ev(tickers=["AMBUJACEM"], sectors=["Cement"])) == "entity"


def test_scope_specific_ticker_wins_even_with_index_ticker():
    # An event about a named company that also tags Nifty is entity-scoped — we
    # must not suppress a legitimate company update (safeguard 3).
    assert _event_scope(_ev(tickers=["AMBUJACEM", "NIFTY50"])) == "entity"


def test_scope_market_wide_from_index_ticker_only():
    assert _event_scope(_ev(tickers=["NIFTY 50"], sectors=["Banking"])) == "market_wide"


def test_scope_market_wide_from_is_structural():
    assert _event_scope(_ev(tickers=[], sectors=["Banking"], is_structural=True)) == "market_wide"


def test_scope_market_wide_from_many_sectors():
    assert _event_scope(_ev(tickers=[], sectors=["Energy", "Banking", "IT"])) == "market_wide"


def test_scope_single_broad_sector_tag_is_not_market_wide():
    # Safeguard 1: one broad sector tag alone must NOT read as market-wide.
    assert _event_scope(_ev(tickers=[], sectors=["Banking"])) == "sector"
    assert _event_scope(_ev(tickers=[], sectors=["Energy", "Banking"])) == "sector"


def test_scope_unscoped_when_no_tickers_and_no_sectors():
    assert _event_scope(_ev(tickers=[], sectors=[])) == "unscoped"


# ── (1) market-wide event never sets a specific article's takeaway ───────────

def test_market_wide_event_does_not_set_company_article_takeaway():
    company = _Article(companies=[{"symbol": "AMBUJACEM"}], sectors=["Cement"])
    market_wide = _ev(tickers=["NIFTY50"], sectors=["Cement", "Banking", "IT"],
                      one_liner="A sharp 400-point drop in Sensex drags the market lower")
    assert _event_sets_takeaway(market_wide, company) is False
    assert _generate_updated_takeaway(company, {}, [market_wide]) is None


# ── (2) entity relevance: a real ticker overlap DOES update (no over-suppress) ─

def test_entity_ticker_overlap_sets_takeaway():
    company = _Article(companies=[{"symbol": "AMBUJACEM"}], sectors=["Cement"])
    ev = _ev(tickers=["AMBUJACEM"], sectors=["Cement"],
             one_liner="Ambuja Cements announces capacity expansion")
    assert _event_sets_takeaway(ev, company) is True
    assert _generate_updated_takeaway(company, {}, [ev]) == "LATEST: Ambuja Cements announces capacity expansion"


def test_entity_event_for_other_company_does_not_set_takeaway():
    company = _Article(companies=[{"symbol": "AMBUJACEM"}], sectors=["Cement"])
    other = _ev(tickers=["ULTRACEMCO"], sectors=["Cement"], one_liner="UltraTech raises prices")
    # Same sector, different company — a bare sector match is NOT enough.
    assert _event_sets_takeaway(other, company) is False
    assert _generate_updated_takeaway(company, {}, [other]) is None


# ── (3) scope preservation across article types ──────────────────────────────

def test_sector_event_updates_pure_sector_article_but_not_company_article():
    sector_article = _Article(companies=[], sectors=["Banking"])           # sector/theme article
    company_article = _Article(companies=[{"symbol": "HDFCBANK"}], sectors=["Banking"])
    sector_ev = _ev(tickers=[], sectors=["Banking"], one_liner="Banking sector margins compress on rate pass-through")
    assert _event_sets_takeaway(sector_ev, sector_article) is True
    # A specific-company article requires entity overlap, not a bare sector match.
    assert _event_sets_takeaway(sector_ev, company_article) is False


def test_unscoped_event_is_pass_through_not_suppressed():
    # Deliberate: an event with NO sector/ticker metadata is not provable
    # evidence of a market-wide development, and the live caller's overlap filter
    # means it never reaches update_article anyway. Allow it rather than suppress
    # a possibly-legitimate update — only explicitly market-wide events are blocked.
    company = _Article(companies=[{"symbol": "AMBUJACEM"}], sectors=["Cement"])
    unscoped = _ev(tickers=[], sectors=[], one_liner="generic development")
    assert _event_sets_takeaway(unscoped, company) is True


# ── (4) provenance persisted in update_history (DB-backed) ───────────────────

def _row(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    base = dict(
        id=str(uuid.uuid4()), slug=f"test-scope-{uuid.uuid4().hex[:8]}",
        article_type="company_intelligence", angle="primary", is_evergreen=False,
        lifecycle_status="published", status="published",
        headline="Ambuja Cements Q2 Results", executive_summary="s",
        key_takeaway="Ambuja Cements posted a real, grounded quarterly result.",
        why_it_matters="Real cement-sector-specific analysis about Ambuja.",
        companies_affected=[{"name": "Ambuja Cements", "symbol": "AMBUJACEM"}],
        sectors_affected=[{"name": "Cement"}], sources=["NSE"],
        story_version=1, update_count=0, update_history=[],
        market_context={"session": "post_market", "mood": "neutral"},
        published_at=now, last_updated=now,
    )
    base.update(overrides)
    return base


async def _seed(**overrides) -> str:
    data = _row(**overrides)
    async with AsyncSessionLocal() as db:
        db.add(IntelligenceArticle(**data))
        await db.commit()
    return data["id"]


async def _cleanup(article_id: str) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(delete(IntelligenceArticle).where(IntelligenceArticle.id == article_id))
        await db.commit()


async def _fetch(article_id: str) -> IntelligenceArticle:
    async with AsyncSessionLocal() as db:
        return (await db.execute(
            select(IntelligenceArticle).where(IntelligenceArticle.id == article_id)
        )).scalar_one()


@pytest.mark.asyncio
async def test_provenance_recorded_for_entity_update():
    aid = await _seed()
    try:
        ev = _ev(tickers=["AMBUJACEM"], sectors=["Cement"], event_id="evt-123",
                 triage_source="ai", one_liner="Ambuja Cements wins a large PPA")
        async with AsyncSessionLocal() as db:
            article = await _fetch(aid)
            db.add(article)
            ok = await update_article(db, article, {"story_hash": "h2"}, new_triage_events=[ev])
        assert ok is True
        row = await _fetch(aid)
        assert row.key_takeaway == "LATEST: Ambuja Cements wins a large PPA"
        entry = row.update_history[-1]
        assert entry["takeaway_source_event_id"] == "evt-123"
        assert entry["takeaway_event_scope"] == "entity"
        assert entry["triage_source"] == "ai"
    finally:
        await _cleanup(aid)


@pytest.mark.asyncio
async def test_company_article_gets_no_market_wide_note_when_no_eligible_event():
    """Owner review #4: when a cycle produces no in-scope event for a specific-
    company article, NEITHER the takeaway NOR the why_it_matters note may be left
    carrying an unrelated market-wide explanation — not the event one_liner and
    not the global market-narrative story."""
    aid = await _seed()
    original_takeaway = "Ambuja Cements posted a real, grounded quarterly result."
    original_why = "Real cement-sector-specific analysis about Ambuja."
    try:
        market_wide = _ev(tickers=["NIFTY50"], sectors=["Cement", "Banking", "IT"], triage_source="ai",
                          one_liner="A sharp 400-point drop in Sensex drags the market lower")
        async with AsyncSessionLocal() as db:
            article = await _fetch(aid)
            db.add(article)
            await update_article(
                db, article,
                {"story": "Broad global market narrative about rate uncertainty", "mood": "Bearish", "story_hash": "h9"},
                new_triage_events=[market_wide], market_move_reason=None,
            )
        row = await _fetch(aid)
        assert row.key_takeaway == original_takeaway
        # No market-wide leakage into why_it_matters via either path.
        assert "400-point drop" not in (row.why_it_matters or "")
        assert "Broad global market narrative" not in (row.why_it_matters or "")
        # A company article with no in-scope event gets no appended note at all.
        assert row.why_it_matters == original_why
    finally:
        await _cleanup(aid)


@pytest.mark.asyncio
async def test_provenance_persists_and_is_per_event_across_successive_updates():
    """Owner review #3: successive updates append (never overwrite) history, and
    each entry's provenance names the event that actually set THAT cycle's
    takeaway."""
    aid = await _seed()
    try:
        ev1 = _ev(tickers=["AMBUJACEM"], sectors=["Cement"], event_id="evt-A", triage_source="ai",
                  one_liner="Ambuja wins a large PPA")
        ev2 = _ev(tickers=["AMBUJACEM"], sectors=["Cement"], event_id="evt-B", triage_source="ai",
                  one_liner="Ambuja raises guidance")
        async with AsyncSessionLocal() as db:
            article = await _fetch(aid)
            db.add(article)
            await update_article(db, article, {"story_hash": "h1"}, new_triage_events=[ev1])
        async with AsyncSessionLocal() as db:
            article = await _fetch(aid)
            db.add(article)
            await update_article(db, article, {"story_hash": "h2"}, new_triage_events=[ev2])
        row = await _fetch(aid)
        hist = row.update_history
        assert len(hist) == 2, "history is appended, not overwritten"
        assert hist[0]["takeaway_source_event_id"] == "evt-A"
        assert hist[1]["takeaway_source_event_id"] == "evt-B"
        assert hist[0]["new_takeaway"] == "LATEST: Ambuja wins a large PPA"
        assert hist[1]["new_takeaway"] == "LATEST: Ambuja raises guidance"
        assert row.key_takeaway == "LATEST: Ambuja raises guidance"
    finally:
        await _cleanup(aid)


@pytest.mark.asyncio
async def test_market_wide_event_leaves_takeaway_and_note_untouched_but_records_none_provenance():
    aid = await _seed()
    original_takeaway = "Ambuja Cements posted a real, grounded quarterly result."
    original_why = "Real cement-sector-specific analysis about Ambuja."
    try:
        market_wide = _ev(tickers=["NIFTY50"], sectors=["Cement", "Banking", "IT"],
                          event_id="evt-macro", triage_source="ai",
                          one_liner="A sharp 400-point drop in Sensex drags the market lower")
        async with AsyncSessionLocal() as db:
            article = await _fetch(aid)
            db.add(article)
            ok = await update_article(db, article, {"story": "global narrative", "mood": "Bearish", "story_hash": "h3"},
                                      new_triage_events=[market_wide])
        row = await _fetch(aid)
        # Takeaway preserved; the market-wide one_liner never leaks into either field.
        assert row.key_takeaway == original_takeaway
        assert "400-point drop" not in (row.key_takeaway or "")
        assert "400-point drop" not in (row.why_it_matters or "")
        assert row.why_it_matters.split("\n\n**Update ")[0] == original_why
        if ok:
            entry = row.update_history[-1]
            assert entry["takeaway_source_event_id"] is None
            assert entry["takeaway_event_scope"] is None
    finally:
        await _cleanup(aid)


# ── (5) fallback: EVENT_ONLY / fallback / no-relevant-event never fabricates ──

def test_fallback_source_event_never_becomes_takeaway():
    company = _Article(companies=[{"symbol": "AMBUJACEM"}], sectors=["Cement"])
    # Scope-eligible (entity overlap) but rule_based_fallback provenance → still rejected.
    fallback = _ev(tickers=["AMBUJACEM"], sectors=["Cement"], triage_source="rule_based_fallback",
                   one_liner="raw unprocessed headline")
    assert _select_takeaway_event(company, [fallback]) is None
    assert _generate_updated_takeaway(company, {}, [fallback]) is None


def test_no_relevant_event_returns_none_not_manufactured():
    company = _Article(companies=[{"symbol": "AMBUJACEM"}], sectors=["Cement"])
    assert _generate_updated_takeaway(company, {"mood": "Bullish", "opportunity": "x"}, []) is None


# ── (6) idempotency / retries: no double "LATEST:" prefix, stable output ──────

def test_rerun_is_stable_and_never_double_prefixes():
    company = _Article(companies=[{"symbol": "AMBUJACEM"}], sectors=["Cement"])
    ev = _ev(tickers=["AMBUJACEM"], sectors=["Cement"], one_liner="Ambuja Cements wins a large PPA")
    first = _generate_updated_takeaway(company, {}, [ev])
    second = _generate_updated_takeaway(company, {}, [ev])
    assert first == second == "LATEST: Ambuja Cements wins a large PPA"
    assert first.count("LATEST:") == 1


# ── (owner-required) two unrelated articles + one high-urgency market-wide ───
# event with a broad shared sector cannot both receive the same takeaway. ─────

def test_two_unrelated_articles_cannot_share_a_market_wide_takeaway():
    art_a = _Article(companies=[{"symbol": "AMBUJACEM"}], sectors=["Cement", "Banking"])
    art_b = _Article(companies=[{"symbol": "TCS"}], sectors=["IT", "Banking"])
    # Highest-urgency event of the cycle, market-wide, broad sectors overlapping both.
    market_wide = _ev(urgency=10, tickers=["SENSEX"], sectors=["Banking", "IT", "Cement"],
                      one_liner="Escalating Iran-US tensions trigger a broad risk-off selloff")
    ta = _generate_updated_takeaway(art_a, {}, [market_wide])
    tb = _generate_updated_takeaway(art_b, {}, [market_wide])
    assert ta is None and tb is None
    # And even mixed with an entity event, each article only gets its OWN.
    ev_a = _ev(urgency=6, tickers=["AMBUJACEM"], sectors=["Cement"], one_liner="Ambuja-specific development")
    ev_b = _ev(urgency=5, tickers=["TCS"], sectors=["IT"], one_liner="TCS-specific development")
    events = [market_wide, ev_a, ev_b]
    assert _generate_updated_takeaway(art_a, {}, events) == "LATEST: Ambuja-specific development"
    assert _generate_updated_takeaway(art_b, {}, events) == "LATEST: TCS-specific development"
