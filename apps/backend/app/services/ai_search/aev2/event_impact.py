"""
Deterministic event_impact assembly for AEV2 (2026-09-22, narrow contract
approved after the policy_macro_impact and event_impact read-only
audits). A PRESENTER over CoreAnswer's own `related_events[0]` — same
architecture rule as every other aev2/ assembler: zero new retrieval,
zero LLM calls, zero regeneration.

Scope decision (2026-09-22 audit, approved): policy_macro_impact was
found unsupportable in full (no RBI-linked price/index coverage exists
today). event_impact is narrower than its own original mockup too — no
transmission chain, no beneficiary/loser framing, no monitoring
checklist, no Ripple graph, no Intelligence Graph propagation, no
generic bull/bear case. It only ever states what Event's own structured
fields can actually prove:
  - the event happened — Event.title / Event.summary, both genuinely
    source-derived text for a real ingestion adapter (verified per
    source type in the 2026-09-22 audit), never Event.ai_summary
    (LLM-generated) and never a Development's own prompt text.
  - which real companies it names — Event.companies, the one
    ~97.9%-real, ingestion-time company<->event relationship this
    codebase has (per the 2026-09-22 audit). NEVER event_companies.
    impact_type/.reason (a separate, AI-generated narrative-judgment
    table keyed by the same event_id) and never a title-text join.
  - an honestly-labeled, explicitly-non-causal price association — IF
    the canonical pipeline ever carries clean post-event price
    observations. It does not today (app/services/ai_search never
    queries price_bars); see _build_observed_reactions's own docstring
    for why this stays [] and how it's still meaningfully tested.

Eligibility is structural, not an ID blacklist. The 3 leaked seed
fixtures removed in the 2026-09-22 content-integrity repair are kept as
regression fixtures (test_event_impact_assembly.py) precisely to prove
this: a seed fixture had no real `Event.source` and no real linked
companies, so it fails the gates below on its own shape — with or
without its specific ID ever appearing on any list.
"""
from __future__ import annotations

from app.services.ai_search.aev2 import language_gate
from app.services.ai_search.aev2.citation_validator import (
    entities_supported,
    numbers_supported,
    recognized_name_tokens,
)
from app.services.ai_search.aev2.schema import build_validated_claim
from app.services.ai_search.core_answer import CoreAnswer

# The only two windows this contract can honestly describe if the
# canonical pipeline ever carries the underlying price observation — see
# _build_observed_reactions.
WINDOW_NEXT_SESSION = "next_session"
WINDOW_FIVE_SESSIONS = "five_sessions"


def _company_refs(raw_companies: object) -> list[dict]:
    """Event.companies JSON entries -> plain {symbol, name} CompanyRef.
    Deliberately drops any 'impact'/direction key a JSON row might carry
    (event_lifecycle.py's own CompanyImpact shape has one) — that is the
    exact same beneficiary/loser-shaped judgment event_companies.
    impact_type makes, just sitting in a different column; excluded here
    for the identical reason ("Connected company," never a direction).
    Dedupes by symbol (first-seen order kept); skips any entry with no
    resolvable symbol."""
    seen: set[str] = set()
    refs: list[dict] = []
    for c in raw_companies or []:
        if not isinstance(c, dict):
            continue
        symbol = (c.get("symbol") or "").strip()
        if not symbol or symbol.upper() in seen:
            continue
        seen.add(symbol.upper())
        refs.append({"symbol": symbol, "name": c.get("name") or symbol})
    return refs


def _sector_refs(raw_sectors: object) -> list[dict]:
    """Event.sectors JSON entries — tolerant of either a bare string or a
    {"sector": ...}/{"name": ...} dict (both shapes exist across this
    codebase's own ingestion/consumption code; see event_lifecycle.py's
    own `s.get("sector")` usage for the dict form). Never carries a
    direction/impact key — same neutral-only rule as _company_refs."""
    seen: set[str] = set()
    refs: list[dict] = []
    for s in raw_sectors or []:
        if isinstance(s, dict):
            name = s.get("sector") or s.get("name") or ""
        elif isinstance(s, str):
            name = s
        else:
            continue
        name = name.strip()
        if not name or name.upper() in seen:
            continue
        seen.add(name.upper())
        refs.append({"name": name})
    return refs


def _build_observed_reactions(
    event_date: str | None, linked_companies: list[dict], price_observations: tuple[dict, ...],
) -> list[dict]:
    """Always [] today, by construction — CoreAnswer carries no
    price_bars-derived field (the ai_search pipeline never queries
    price_bars; confirmed 2026-09-22, and `assemble_event_impact` below
    always calls this with `price_observations=()`). This function
    exists, with real filtering/window logic, and is directly unit-
    tested with synthetic PriceBar-shaped input, so that WHEN a future
    slice adds a genuine `core.*` price-observation source (never
    invented here — see this module's own "Do not introduce an AEV2-
    only retrieval path" constraint), the rules are already correct:

      - only `data_quality == "good"` bars are ever eligible. A holiday
        or thin-volume bar (see the 2026-09-22 Repair 2 incident: 49
        Ganesh-Chaturthi bars that reached production before the
        trading-calendar ingestion guard existed) must never silently
        feed a reaction number.
      - every entry states an OBSERVED percent change over a named
        window (`next_session` = the first later trading-day bar,
        `five_sessions` = the fifth), never a causal claim — there is
        no "caused by" field anywhere in this shape, by design.
      - a company with no `good`-quality bar on or after the event date
        is simply absent from the result, not padded with a stale or
        low-quality substitute.
    """
    if not event_date or not price_observations:
        return []
    by_symbol: dict[str, list[dict]] = {}
    for bar in price_observations:
        if bar.get("data_quality") != "good":
            continue
        symbol = (bar.get("symbol") or "").upper()
        if not symbol:
            continue
        by_symbol.setdefault(symbol, []).append(bar)

    linked_by_symbol = {c["symbol"].upper(): c for c in linked_companies}
    reactions: list[dict] = []
    for symbol, bars in by_symbol.items():
        company = linked_by_symbol.get(symbol)
        if not company:
            continue
        bars_sorted = sorted(bars, key=lambda b: b["bar_date"])
        base = None
        for b in bars_sorted:
            if b["bar_date"] <= event_date:
                base = b
        after = [b for b in bars_sorted if b["bar_date"] > event_date]
        if base is None or not after or not base.get("close"):
            continue
        for window, count in ((WINDOW_NEXT_SESSION, 1), (WINDOW_FIVE_SESSIONS, 5)):
            if len(after) < count:
                continue
            end = after[count - 1]
            pct = round((end["close"] - base["close"]) / base["close"] * 100, 2)
            reactions.append({
                "company": company,
                "window": window,
                "start_date": base["bar_date"],
                "end_date": end["bar_date"],
                "percent_change": pct,
                "source": end.get("source") or "price_bars",
                "data_quality": "good",
                "evidence_refs": [],
            })
    return reactions


def assemble_event_impact(core: CoreAnswer, *, catalog_ids: set[str]) -> dict | None:
    """None — the honest "not applicable" state, same division of
    responsibility as switch_analysis.py/comparison.py — unless exactly
    one Event resolved for this query AND that event's own structured
    fields clear every gate below. A resolving event always gets a full
    object back; the FRONTEND eligibility gate (toEventImpactAEV2Answer)
    makes the final render/no-render call, same as every other mode.

    Deliberately does NOT accept assemble.py's globally-scoped
    claim_refs/claim_supporting_text/recognized_symbols/name_tokens the
    way switch_analysis.py/comparison.py do (2026-09-22 citation-
    invariant review). Those are computed from ALL of core.companies —
    for a 2-company comparison that is the right scope, but for a
    single-Event contract it is too wide: `deterministic_claim_evidence_
    refs` would also pull in any announcement for ANY OTHER company that
    happens to be in core.companies for unrelated reasons, letting an
    unrelated company's announcement validate this Event's own
    conclusion merely because both companies were resolved somewhere in
    the same query. This module computes its own strictly event-scoped
    citation set instead, so direct_conclusion.evidence_refs can only
    ever be `["event:{this event's id}"]` or `[]` — never a News,
    Policy, second Event, or unrelated-company Announcement ref, and
    never merely because "the same company" is mentioned somewhere
    else."""
    if len(core.related_events) != 1:
        return None
    raw_event = core.related_events[0]

    eid = raw_event.get("id")
    source_name = (raw_event.get("source") or "").strip()
    title = raw_event.get("title") or ""
    summary = raw_event.get("summary") or ""
    published_at = raw_event.get("published_at")
    if eid is None or not source_name or not title or not summary or not published_at:
        return None

    linked_companies = _company_refs(raw_event.get("companies"))
    if not linked_companies:
        return None
    linked_sectors = _sector_refs(raw_event.get("sectors"))

    slug = (raw_event.get("slug") or "").strip()
    internal_url = f"/events/{slug}" if slug else None
    if not internal_url:
        return None

    # The ONLY evidence this contract ever cites — the resolved primary
    # Event itself. `event_ref in catalog_ids` is provably always True
    # here (build_evidence_catalog includes every entry of core.
    # related_events, which is this exact one event, and eid is already
    # confirmed non-None above) — checked anyway rather than assumed,
    # matching this codebase's "verify a precondition, never trust it
    # silently" convention.
    event_ref = f"event:{eid}"
    event_scoped_refs = [event_ref] if event_ref in catalog_ids else []
    event_supporting_text = title if event_scoped_refs else ""

    event_symbols = {c["symbol"].upper() for c in linked_companies}
    event_name_tokens = recognized_name_tokens(tuple(linked_companies))

    gated = language_gate.gate("direct_conclusion", core.bottom_line)
    if gated.had_violation:
        direct_conclusion = build_validated_claim(gated.text, [], had_violation=True)
    elif not core.bottom_line:
        direct_conclusion = build_validated_claim("", [], had_violation=False)
    else:
        # Every company-like token in the text must be one of THIS
        # event's own linked companies — supporting_text is deliberately
        # "" so a mention can ONLY pass via event_symbols/event_name_
        # tokens, never by merely appearing somewhere in wider evidence
        # text (spec: "every company named in the conclusion belongs to
        # Event.companies").
        entities_ok = entities_supported(core.bottom_line, event_symbols, event_name_tokens, "")
        numbers_ok = numbers_supported(core.bottom_line, event_supporting_text)
        if not event_scoped_refs or not entities_ok or not numbers_ok:
            fallback = language_gate.FALLBACK_TEXT["direct_conclusion"]
            direct_conclusion = build_validated_claim(fallback, [], had_violation=True)
        else:
            direct_conclusion = build_validated_claim(core.bottom_line, event_scoped_refs, had_violation=False)

    # Always () today — see _build_observed_reactions's own docstring;
    # this is the one call site, and it never reads a price-observation
    # field from `core` because none exists.
    observed_reactions = _build_observed_reactions(raw_event.get("event_date"), linked_companies, ())

    return {
        "event": {
            "id": str(eid),
            "title": title,
            "summary": summary,
            "published_at": published_at,
            "source_name": source_name,
            "internal_url": internal_url,
            # Event carries no original-publisher-URL column at all
            # today (confirmed 2026-09-22 schema inspection) — always
            # None, which is the honest, EXPECTED state for virtually
            # every event, not a per-row failure. The frontend shows the
            # documented fallback notice for this.
            "original_source_url": None,
        },
        "linked_companies": linked_companies,
        "linked_sectors": linked_sectors,
        "observed_reactions": observed_reactions,
        "direct_conclusion": direct_conclusion,
    }
