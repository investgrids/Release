"""
Shared evidence loading/normalization — used by both the continuous
observation builder and the pilot, so the two never drift into two
different definitions of "positive evidence."

Sources used (see safe_sources.py for the full allowlist and why):
  EventTriage       — importance*10 -> magnitude (0-100), confidence*10
                       -> confidence (0-100), sentiment -> direction.
  AICompanySignal    — |signed_magnitude| -> magnitude (already ~0-100),
                       confidence*100 -> confidence (0-100, only when the
                       source article/opportunity actually had one), sign
                       of signed_magnitude -> direction.
  CompanyAnnouncement — impact_score*10 -> magnitude (0-100), sentiment ->
                       direction, no confidence field (honestly None, not
                       fabricated).

ScoreHistory is structurally safe (append-only) but deliberately NOT
used here: entity_type="company" rows carry an unsigned score with no
documented sign convention, and attributing entity_type="event" rows to
a symbol would require an extra event->ticker join this pilot doesn't
need given EventTriage already covers event-level signal directly.
MarketSnapshot/MarketStory are market-wide, not per-company, so they
don't feed company-level evidence at all.

Every direction/magnitude/confidence value here is computed from a
single already-frozen row (never re-derived from a live/mutable
lookup) — this is what "classification-at-write-time" means in
practice for Phase 2E.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.intelligence import EventTriage
from app.db.models.company_signal import AICompanySignal
from app.db.models.company_announcements import CompanyAnnouncement
from app.services.quant.universe import NIFTY_50, SECTOR

_MAGNITUDE_DEADBAND = 5.0   # |magnitude*sign| below this on the 0-100 scale is treated as neutral, not noise-fit as a direction

_SENTIMENT_DIRECTION = {"bullish": "positive", "bearish": "negative", "neutral": "neutral"}


@dataclass
class EvidenceEvent:
    source_type: str        # "triage" | "signal" | "announcement"
    source_id: str
    symbol: str
    occurred_at: datetime
    direction: str            # "positive" | "negative" | "neutral"
    magnitude_0_100: float
    confidence_0_100: float | None


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _direction_from_magnitude_sign(signed: float) -> str:
    if signed >= _MAGNITUDE_DEADBAND:
        return "positive"
    if signed <= -_MAGNITUDE_DEADBAND:
        return "negative"
    return "neutral"


async def load_all_evidence(db: AsyncSession) -> dict[str, list[EvidenceEvent]]:
    """Loads every safe-source row once, normalizes it, and indexes by
    symbol. Small enough tables (thousands of rows, not hundreds of
    thousands) that loading everything into memory once and reusing it
    across every (symbol, as_of) observation beats re-querying per
    observation — same efficiency pattern as Phase 2D's benchmark dict."""
    nifty_set = set(NIFTY_50)
    by_symbol: dict[str, list[EvidenceEvent]] = {s: [] for s in NIFTY_50}

    triage_rows = (await db.execute(
        select(EventTriage.id, EventTriage.tickers, EventTriage.sentiment,
               EventTriage.importance, EventTriage.confidence, EventTriage.triaged_at)
    )).all()
    for r in triage_rows:
        if not r.tickers:
            continue
        occurred_at = _aware(r.triaged_at)
        if occurred_at is None:
            continue
        direction = _SENTIMENT_DIRECTION.get((r.sentiment or "").lower(), "neutral")
        magnitude = float(r.importance or 0) * 10.0
        confidence = float(r.confidence or 0) * 10.0
        for t in r.tickers:
            sym = str(t).upper().split(".")[0]
            if sym in nifty_set:
                by_symbol[sym].append(EvidenceEvent(
                    "triage", r.id, sym, occurred_at, direction, magnitude, confidence,
                ))

    signal_rows = (await db.execute(
        select(AICompanySignal.id, AICompanySignal.symbol, AICompanySignal.signed_magnitude,
               AICompanySignal.confidence, AICompanySignal.signal_at)
        .where(AICompanySignal.symbol.in_(nifty_set))
    )).all()
    for r in signal_rows:
        occurred_at = _aware(r.signal_at)
        if occurred_at is None:
            continue
        magnitude = abs(float(r.signed_magnitude or 0.0))
        direction = _direction_from_magnitude_sign(float(r.signed_magnitude or 0.0))
        confidence = float(r.confidence) * 100.0 if r.confidence is not None else None
        by_symbol[r.symbol].append(EvidenceEvent(
            "signal", str(r.id), r.symbol, occurred_at, direction, magnitude, confidence,
        ))

    ann_rows = (await db.execute(
        select(CompanyAnnouncement.id, CompanyAnnouncement.symbol, CompanyAnnouncement.sentiment,
               CompanyAnnouncement.impact_score, CompanyAnnouncement.announcement_date)
        .where(CompanyAnnouncement.symbol.in_(nifty_set))
    )).all()
    for r in ann_rows:
        occurred_at = _aware(r.announcement_date)
        if occurred_at is None:
            continue
        direction = _SENTIMENT_DIRECTION.get((r.sentiment or "").lower(), "neutral")
        magnitude = float(r.impact_score or 0) * 10.0
        by_symbol[r.symbol].append(EvidenceEvent(
            "announcement", r.id, r.symbol, occurred_at, direction, magnitude, None,
        ))

    for sym in by_symbol:
        by_symbol[sym].sort(key=lambda e: e.occurred_at)
    return by_symbol


def evidence_trigger_dates(events: list[EvidenceEvent]) -> list[date]:
    """One as-of trigger per distinct calendar date something new was
    observed for this symbol — avoids manufacturing observations on
    empty days, and matches the product framing directly ("when Market
    Ripple observed X, what happened next")."""
    return sorted({e.occurred_at.date() for e in events})


@dataclass
class EvidenceState:
    symbol: str
    as_of_date: date
    window_days: int
    positive_count: int
    negative_count: int
    neutral_count: int
    highest_impact_0_100: float
    aggregate_signed_magnitude: float
    aggregate_confidence_0_100: float | None
    signal_count: int
    triage_count: int
    announcement_count: int
    conflict_bucket: str
    evidence_refs: list[dict]


def _conflict_bucket(pos: int, neg: int) -> str:
    if pos > 0 and neg == 0:
        return "all_positive"
    if neg > 0 and pos == 0:
        return "all_negative"
    if pos > neg:
        return "mostly_positive"
    if neg > pos:
        return "mostly_negative"
    if pos == neg and pos > 0:
        return "balanced_conflict"
    return "no_signal"


def build_evidence_state(symbol: str, as_of_date: date, events: list[EvidenceEvent], window_days: int = 7) -> EvidenceState:
    """Aggregates every event with occurred_at in (as_of_date - window_days, as_of_date] —
    inclusive of the trigger day itself, nothing after it. This is the
    leakage boundary: no event with occurred_at > as_of_date is ever
    included, enforced here in one place."""
    window_start = datetime.combine(as_of_date - timedelta(days=window_days), datetime.min.time(), tzinfo=timezone.utc)
    cutoff = datetime.combine(as_of_date, datetime.max.time(), tzinfo=timezone.utc)
    in_window = [e for e in events if window_start <= e.occurred_at <= cutoff]

    pos = sum(1 for e in in_window if e.direction == "positive")
    neg = sum(1 for e in in_window if e.direction == "negative")
    neu = sum(1 for e in in_window if e.direction == "neutral")
    signed_vals = [e.magnitude_0_100 if e.direction == "positive" else -e.magnitude_0_100 if e.direction == "negative" else 0.0 for e in in_window]
    confidences = [e.confidence_0_100 for e in in_window if e.confidence_0_100 is not None]

    return EvidenceState(
        symbol=symbol, as_of_date=as_of_date, window_days=window_days,
        positive_count=pos, negative_count=neg, neutral_count=neu,
        highest_impact_0_100=max((e.magnitude_0_100 for e in in_window), default=0.0),
        aggregate_signed_magnitude=round(sum(signed_vals), 2),
        aggregate_confidence_0_100=round(sum(confidences) / len(confidences), 2) if confidences else None,
        signal_count=sum(1 for e in in_window if e.source_type == "signal"),
        triage_count=sum(1 for e in in_window if e.source_type == "triage"),
        announcement_count=sum(1 for e in in_window if e.source_type == "announcement"),
        conflict_bucket=_conflict_bucket(pos, neg),
        evidence_refs=[{"source_type": e.source_type, "id": e.source_id} for e in in_window],
    )
