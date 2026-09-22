"""
CoreMarketPulse — the canonical core for a market-pulse-shaped query, the
sibling of CoreAnswer (core_answer.py). Together they form the
discriminated canonical core this codebase's presenters read from:

    CanonicalAnswerCore = CoreAnswer | CoreMarketPulse

(No shared base class or `kind` field ties the two together — Python's
own `isinstance` check is the discriminant every dispatch point in this
package uses, e.g. aev2/assemble.py's assemble_aev2. This is a deliberate
choice, not an oversight: CoreAnswer is deeply embedded and extensively
tested as its own frozen dataclass; adding a redundant field to it for
symmetry would touch far more surface than the actual architectural
requirement — "one shared finalizer/safety-gate/telemetry/cache/AEV2-
dispatch/serialization boundary for both variants" — needs. `isinstance`
already gives every one of those boundaries a correct, type-safe
discriminant.)

Market Pulse keeps its own specialized real-data collector
(market_intelligence_service.get_market_pulse, market_pulse.py's prompt/
LLM-synthesis step) — that collection step is genuinely different work
from the specialist pipeline research answers go through, and nothing
here asks it to pretend otherwise. What changes (2026-09-22, Market
Pulse AEV2 audit) is everything DOWNSTREAM of collection: Market Pulse's
result dict now flows through the identical response_finalize.py steps
(safety gate -> canonical core construction -> AEV2 assembly -> public-
serialization gate) a research answer does, never a second, independently
-wired finalization/presentation pipeline.

Same discipline as core_answer.py: `from_market_pulse_response()` is a
pure function (no I/O, never mutates its input) and CoreMarketPulse is
frozen AND deep-copied on every nested tuple/dict field, so a presenter
holding this object can never accidentally mutate the original result
dict (or vice versa) through a shared reference.

Sub-item shapes (indices/sectors/movers/drivers/themes/calendar) stay
plain dicts, not further nested dataclasses — same convention
CoreAnswer.companies/related_events/announcements already use. Each
one's real shape is documented where it's produced (market_data.py,
market_intelligence_service.py, theme_worker.py, intelligence/engine.py)
rather than re-declared here as a parallel type that could drift.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class CoreMarketPulse:
    kind: Literal["market_pulse"]
    query: str
    response_id: str | None
    synthesis_incomplete: bool
    degraded_reason: str | None

    as_of: str | None
    market_session: str | None
    market_status: str | None

    indices: tuple[dict, ...] = field(default_factory=tuple)
    leading_sectors: tuple[dict, ...] = field(default_factory=tuple)
    lagging_sectors: tuple[dict, ...] = field(default_factory=tuple)
    top_gainers: tuple[dict, ...] = field(default_factory=tuple)
    top_losers: tuple[dict, ...] = field(default_factory=tuple)
    most_active: tuple[dict, ...] = field(default_factory=tuple)
    theme_momentum: tuple[dict, ...] = field(default_factory=tuple)
    upcoming_events: tuple[dict, ...] = field(default_factory=tuple)

    # None when neither a tracked bearish event nor an AI story risk
    # narrative exists — see intelligence/engine.py::_derive_biggest_risk.
    # Carries the real "source": "tracked_event" | "ai_synthesis"
    # discriminant at the raw-dict level already; the AEV2 assembler is
    # what turns this into the typed RiskContext union with its own
    # rendering-label rules.
    risk_context: dict | None = None

    # None when no public Opportunity exists — see intelligence/
    # engine.py::read_opportunities, which already excludes shadow V2
    # rows (calls list_public_opportunities_v2, the public-only read
    # service) and unpublished V1 rows.
    biggest_opportunity: dict | None = None

    # Raw, not-yet-citation-validated generated text — same convention as
    # CoreAnswer.bottom_line: already passed through market_pulse_safety's
    # recommendation-language gate (response_finalize.py's step 1, shared
    # with the research path's own safety_gate.py) by the time this
    # projection runs, but NOT yet checked against the structured payload
    # (cited facts exist, numbers match, mentioned entities exist) — that
    # citation-style validation is aev2/market_pulse.py's job, mirroring
    # exactly how aev2/assemble.py validates CoreAnswer.bottom_line.
    generated_summary: str = ""
    generated_conclusion: str = ""
    # Keyed by ticker, one sentence each — same raw/ungated convention as
    # generated_summary/generated_conclusion above.
    gainer_narratives: dict = field(default_factory=dict)
    loser_narratives: dict = field(default_factory=dict)


def from_market_pulse_response(result: dict | None) -> CoreMarketPulse:
    """Pure projection — reads `result` (the dict market_pulse.py's
    _run_market_pulse_search produces, already safety-gated by
    response_finalize.py before this ever runs), never mutates it, never
    calls out to any provider/evidence/market-data code. Every nested
    list is deep-copied before being frozen into a tuple, so this
    CoreMarketPulse can never alias — and therefore never let a
    presenter accidentally mutate — the original result dict's nested
    structures. Constructed exactly once per request, unconditionally
    (matching from_v3_response's own discipline), regardless of AEV2
    mode — cheap, pure assembly, ready the moment a mode is enabled
    without needing a second read of `result`."""
    result = result or {}
    movers_top_gainers = result.get("top_gainers") or []
    movers_top_losers = result.get("top_losers") or []

    def _narratives_for(movers: list) -> dict:
        out = {}
        for m in movers:
            ticker = m.get("ticker")
            if ticker and m.get("narrative"):
                out[ticker] = m["narrative"]
        return out

    return CoreMarketPulse(
        kind="market_pulse",
        query=result.get("query", ""),
        response_id=result.get("response_id"),
        synthesis_incomplete=bool(result.get("synthesis_incomplete", False)),
        degraded_reason=result.get("degraded_reason"),
        as_of=result.get("generated_at"),
        market_session=result.get("market_session"),
        market_status=(result.get("market_status") or {}).get("status"),
        indices=tuple(copy.deepcopy(result.get("indices") or [])),
        leading_sectors=tuple(copy.deepcopy(result.get("leading_sectors") or [])),
        lagging_sectors=tuple(copy.deepcopy(result.get("lagging_sectors") or [])),
        top_gainers=tuple(copy.deepcopy(movers_top_gainers)),
        top_losers=tuple(copy.deepcopy(movers_top_losers)),
        most_active=tuple(copy.deepcopy(result.get("most_active") or [])),
        theme_momentum=tuple(copy.deepcopy(result.get("theme_momentum") or [])),
        upcoming_events=tuple(copy.deepcopy(result.get("what_to_watch_next") or [])),
        risk_context=copy.deepcopy(result.get("biggest_risk")) if result.get("biggest_risk") else None,
        biggest_opportunity=copy.deepcopy(result.get("biggest_opportunity")) if result.get("biggest_opportunity") else None,
        generated_summary=result.get("market_summary") or "",
        generated_conclusion=result.get("ai_conclusion") or "",
        gainer_narratives=_narratives_for(movers_top_gainers),
        loser_narratives=_narratives_for(movers_top_losers),
    )
