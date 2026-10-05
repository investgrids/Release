"""
Deterministic AEV2 presenter for CoreMarketPulse (2026-09-22, Market
Pulse AEV2 audit). Same architecture rule as aev2/assemble.py's research
path: a PRESENTER, never a second reasoning pipeline — zero new
retrieval, zero LLM calls, reads only CoreMarketPulse.

Every "market value" (index, sector, mover) is wrapped in a small
provenance envelope — {value, as_of, source, session} — rather than
handed through as a bare display string. `as_of`/`session` are the
SAME single generation timestamp/session CoreMarketPulse itself carries
(the whole payload is fetched in one asyncio.gather batch — see
market_intelligence_service.get_market_pulse), not a fresh per-item
timestamp; adding genuinely independent per-item fetch timestamps would
mean changing the underlying market-data fetch functions themselves,
which is out of scope for a presenter. `source` is a fixed per-category
label naming which real feed produced that category (never invented,
never per-item — see _SOURCE_LABELS).

Risk (RiskContext) is a discriminated union with an explicit
non-negotiable asymmetry: the "tracked_event" branch renders because it
has a real, citable Event id (see intelligence/engine.py::
_derive_biggest_risk); the "ai_synthesis" branch — the AI market
story's own risk narrative, with no real Event or structured fact
behind it today — can NEVER produce a valid evidence_refs entry in this
slice, so per the approved rule ("if AI synthesis lacks valid evidence
references, omit it" / "never substitute uncited narrative merely
because no tracked Event exists"), it is always omitted here. This is
not a bug or a gap to fix later with a fallback — it is the correct,
honest behavior until a real structured source for that narrative
exists. Self-rated confidence (both branches' raw dicts carry a
`confidence` field from EventTriage.confidence / the AI story's own
self-report) is dropped entirely — neither branch's AEV2 shape has a
confidence field at all, making it structurally unreachable, not just
conventionally omitted.

Generated prose (generated_summary/generated_conclusion/mover
narratives) is independently re-scanned for advisory language here —
defense in depth, matching aev2/language_gate.py's own precedent of
re-checking even though response_finalize.py's market_pulse_safety
gate already ran upstream — and independently validated against the
REAL structured payload (numbers_supported / entities_supported, the
same two checks aev2/citation_validator.py already provides, reused
verbatim rather than reimplemented) before being allowed to render.
Any failure omits that piece of prose entirely; the structured payload
(indices, movers, sectors, drivers, themes, opportunity, risk,
calendar) is built and returned regardless — Market Pulse's two honest
states are `synthesis_status: "complete"` and `"unavailable"`, never a
missing index or mover.
"""
from __future__ import annotations

from app.services.ai_search.advisory_language import scan as _scan_advisory_language
from app.services.ai_search.aev2.citation_validator import (
    entities_supported,
    numbers_supported,
    recognized_name_tokens,
)
from app.services.ai_search.aev2.schema import build_validated_claim
from app.services.ai_search.core_market_pulse import CoreMarketPulse

# Market Pulse's own independent contract version (2026-09-22, six-mode
# integration audit follow-up). `kind` discriminates WHICH AEV2 variant
# a response carries (market_pulse vs the research AEV2Response shape)
# — it does not replace schema versioning, since the discriminator value
# itself never changes across a real field-shape revision. Deliberately
# its own version lineage, not schema.py's SCHEMA_VERSION ("aev2.4") —
# this shape evolves independently of the research contract (see this
# module's own docstring: a fully separate presenter, never merged with
# AEV2Response). Bump this, not schema.py's constant, when this specific
# dict's own field shape changes.
MARKET_PULSE_SCHEMA_VERSION = "aev2-market-pulse.1"

_SOURCE_LABELS = {
    "index": "yfinance_nse_index",
    "sector": "yfinance_sector_etf",
    "mover": "yfinance_top_movers",
}


def _with_provenance(value: str | None, *, as_of: str | None, session: str | None, source: str) -> dict | None:
    if value is None:
        return None
    return {"value": value, "as_of": as_of, "source": source, "session": session}


def _market_index(raw: dict, *, as_of: str | None, session: str | None) -> dict:
    return {
        "name": raw.get("name"),
        "ticker": raw.get("ticker"),
        "price": _with_provenance(raw.get("value"), as_of=as_of, session=session, source=_SOURCE_LABELS["index"]),
        "change": _with_provenance(raw.get("change"), as_of=as_of, session=session, source=_SOURCE_LABELS["index"]),
        "chart": raw.get("chart") or [],
    }


def _sector_move(raw: dict, *, as_of: str | None, session: str | None) -> dict:
    return {
        "id": raw.get("id"),
        "name": raw.get("name"),
        "change": _with_provenance(raw.get("value"), as_of=as_of, session=session, source=_SOURCE_LABELS["sector"]),
        "momentum_score": raw.get("momentum_score"),
    }


def _market_mover(raw: dict, *, as_of: str | None, session: str | None, narrative: str | None) -> dict:
    drivers = raw.get("verified_drivers") or []
    return {
        "company": raw.get("company"),
        "ticker": raw.get("ticker"),
        "price": _with_provenance(raw.get("subtitle"), as_of=as_of, session=session, source=_SOURCE_LABELS["mover"]),
        "change": _with_provenance(raw.get("value"), as_of=as_of, session=session, source=_SOURCE_LABELS["mover"]),
        "verified_drivers": [_verified_driver(d) for d in drivers],
        # Rendered ONLY when it independently passes the same
        # numbers/entities validation every generated-text field does —
        # see assemble_market_pulse's own validation pass. Structurally
        # honest either way: [] drivers + no narrative is "no verified
        # driver identified," never a filled-in placeholder.
        "narrative": narrative,
    }


def _verified_driver(raw: dict) -> dict:
    return {
        "driver": raw.get("driver"),
        "driver_type": raw.get("driver_type"),
        "confidence_tier": raw.get("confidence_tier"),
        "driver_strength": raw.get("driver_strength"),
        "evidence_refs": [f"event:{eid}" for eid in (raw.get("related_event_ids") or []) if eid],
    }


def _theme_momentum(raw: dict) -> dict:
    return {
        "theme": raw.get("theme"),
        "score": raw.get("score"),
        "momentum": raw.get("momentum"),
        "price_signal": raw.get("price_signal"),
        "news_signal": raw.get("news_signal"),
    }


def _calendar_event(raw: dict) -> dict:
    return {
        "id": raw.get("id"),
        "title": raw.get("title"),
        "date": raw.get("date"),
        "category": raw.get("category"),
        "description": raw.get("description"),
    }


def _opportunity_ref(raw: dict | None) -> dict | None:
    """None when core.biggest_opportunity is None — the honest "no
    public opportunity" state, never fabricated. `raw` is already
    exclusively sourced from public, non-shadow rows upstream (V2:
    list_public_opportunities_v2; V1: OpportunityService's own public
    listing — see intelligence/engine.py::read_opportunities) — this
    function re-verifies nothing further (no new retrieval is allowed
    here), it only relabels the score field so it can never be
    mistaken for a forecast probability. `href` already carries the
    real, server-built stable slug/id (never a raw id the frontend has
    to guess how to route)."""
    if not raw:
        return None
    score = raw.get("opportunity_score")
    if score is None:
        score = raw.get("current_strength")
    return {
        "title": raw.get("title"),
        "href": raw.get("href"),
        "opportunity_score": score,
    }


def _risk_context(raw: dict | None) -> dict | None:
    """The one place the tracked_event/ai_synthesis asymmetry is
    enforced — see this module's own docstring for why ai_synthesis
    can never render in this slice (no real evidence_refs exist for
    it). Self-rated confidence (present on both raw branches) is
    dropped unconditionally — neither output shape below has a
    confidence field."""
    if not raw:
        return None
    if raw.get("source") == "tracked_event" and raw.get("event_id"):
        return {
            "source": "tracked_event",
            "event_id": str(raw["event_id"]),
            "title": raw.get("headline") or raw.get("reason") or "",
            "published_at": raw.get("published_at"),
            "evidence_refs": [f"event:{raw['event_id']}"],
        }
    # ai_synthesis (or a tracked_event row missing its own event_id,
    # which would make evidence_refs empty anyway) — never rendered.
    return None


def _build_supporting_text(core: CoreMarketPulse) -> str:
    parts: list[str] = []
    for i in core.indices:
        parts.append(f"{i.get('name') or ''} {i.get('value') or ''} {i.get('change') or ''}")
    for s in (*core.leading_sectors, *core.lagging_sectors):
        parts.append(f"{s.get('name') or ''} {s.get('value') or ''}")
    for m in (*core.top_gainers, *core.top_losers, *core.most_active):
        parts.append(f"{m.get('company') or ''} {m.get('ticker') or ''} {m.get('value') or ''} {m.get('subtitle') or ''}")
    for t in core.theme_momentum:
        parts.append(str(t.get("theme") or ""))
    for e in core.upcoming_events:
        parts.append(str(e.get("title") or ""))
    if core.biggest_opportunity:
        parts.append(str(core.biggest_opportunity.get("title") or ""))
    if core.risk_context:
        parts.append(f"{core.risk_context.get('headline') or ''} {core.risk_context.get('reason') or ''}")
    return " ".join(p for p in parts if p.strip())


def _recognized_symbols(core: CoreMarketPulse) -> set[str]:
    symbols: set[str] = set()
    for i in core.indices:
        if i.get("ticker"):
            symbols.add(str(i["ticker"]).upper())
    for m in (*core.top_gainers, *core.top_losers, *core.most_active):
        if m.get("ticker"):
            symbols.add(str(m["ticker"]).upper())
    return symbols


def _name_tokens(core: CoreMarketPulse) -> set[str]:
    named = tuple(
        {"name": v} for v in (
            *(i.get("name") for i in core.indices),
            *(s.get("name") for s in (*core.leading_sectors, *core.lagging_sectors)),
            *(m.get("company") for m in (*core.top_gainers, *core.top_losers, *core.most_active)),
            *(t.get("theme") for t in core.theme_momentum),
        ) if v
    )
    return recognized_name_tokens(named)


def _validate_generated_text(
    text: str, *, supporting_text: str, recognized_symbols: set[str], name_tokens: set[str],
) -> bool:
    """True only if `text` clears every rendering condition the approved
    spec requires: no advisory-language violation, every number in it
    appears somewhere in the real structured payload, and every
    company/index-like token in it is either a real recognized
    symbol/name or appears literally in that same supporting text."""
    if not text:
        return False
    if _scan_advisory_language(text):
        return False
    if not numbers_supported(text, supporting_text):
        return False
    if not entities_supported(text, recognized_symbols, name_tokens, supporting_text):
        return False
    return True


def assemble_market_pulse(core: CoreMarketPulse) -> dict:
    """Always returns a full AEV2MarketPulse dict — there is no "not
    applicable" None state the way event_impact/comparison have, since
    every market-pulse-classified query has real structured data to
    show (mirrors CoreMarketPulse always being constructable from any
    market_pulse result). The caller (aev2/assemble.py) is the one
    place that decides whether `mode` allows this to run at all."""
    as_of, session = core.as_of, core.market_session
    supporting_text = _build_supporting_text(core)
    recognized_symbols = _recognized_symbols(core)
    name_tokens = _name_tokens(core)

    def _claim(text: str) -> dict | None:
        if not _validate_generated_text(
            text, supporting_text=supporting_text, recognized_symbols=recognized_symbols, name_tokens=name_tokens,
        ):
            return None
        return build_validated_claim(text, [], had_violation=False)

    generated_summary = _claim(core.generated_summary)
    generated_conclusion = _claim(core.generated_conclusion)

    def _movers(raws: tuple[dict, ...], narratives: dict) -> list[dict]:
        out = []
        for raw in raws:
            ticker = raw.get("ticker") or ""
            raw_narrative = narratives.get(ticker) or ""
            narrative = raw_narrative if _validate_generated_text(
                raw_narrative, supporting_text=supporting_text,
                recognized_symbols=recognized_symbols, name_tokens=name_tokens,
            ) else None
            out.append(_market_mover(raw, as_of=as_of, session=session, narrative=narrative))
        return out

    top_gainers = _movers(core.top_gainers, core.gainer_narratives)
    top_losers = _movers(core.top_losers, core.loser_narratives)
    most_active = [_market_mover(m, as_of=as_of, session=session, narrative=None) for m in core.most_active]

    driver_covered = sum(1 for m in (*core.top_gainers, *core.top_losers) if m.get("verified_drivers"))
    driver_total = len(core.top_gainers) + len(core.top_losers)
    tracked_event_count = sum(
        1 for m in (*core.top_gainers, *core.top_losers) for d in (m.get("verified_drivers") or [])
        if d.get("related_event_ids")
    )

    return {
        "kind": "market_pulse",
        "schema_version": MARKET_PULSE_SCHEMA_VERSION,
        "as_of": as_of,
        "market_session": session,
        "market_status": core.market_status,
        "indices": [_market_index(i, as_of=as_of, session=session) for i in core.indices],
        "sector_movement": {
            "leading": [_sector_move(s, as_of=as_of, session=session) for s in core.leading_sectors],
            "lagging": [_sector_move(s, as_of=as_of, session=session) for s in core.lagging_sectors],
        },
        "movers": {
            "gainers": top_gainers,
            "losers": top_losers,
            "most_active": most_active,
        },
        "theme_momentum": [_theme_momentum(t) for t in core.theme_momentum],
        "biggest_opportunity": _opportunity_ref(core.biggest_opportunity),
        "risk_context": _risk_context(core.risk_context),
        "upcoming_events": [_calendar_event(e) for e in core.upcoming_events],
        "generated_summary": generated_summary,
        "generated_conclusion": generated_conclusion,
        "synthesis_status": "complete" if generated_summary is not None else "unavailable",
        "evidence_coverage": {
            "movers_with_driver": driver_covered,
            "movers_total": driver_total,
            "tracked_event_count": tracked_event_count,
            "calendar_event_count": len(core.upcoming_events),
        },
    }
