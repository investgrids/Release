"""
IndexMembership — real, sourced, point-in-time index constituent history
(Phase B0 leakage-lock, owner instruction, 2026-08-23).

Fixes a confirmed survivorship/future-composition bias: the quant
backtest's universe (app/services/quant/universe.py::NIFTY_50) is a
single static current-day snapshot, applied identically to every
historical as-of date. Real, database-verified evidence: symbol ETERNAL
(Zomato's renamed ticker) has stored predictions dated back to
2021-09-24 — more than three years before it actually joined the NIFTY
50 index on 2025-03-28.

Every row here is sourced to a real NSE Indices / Nifty Indices press
release or a reputable financial-news report of one — see `source` and
`notes`. No row's dates were guessed, inferred from a stock's listing
date, or inferred from today's constituent list. Where the exact
original inclusion date for a long-standing constituent could not be
independently verified (most of the 50 — many have been members for
years to decades before this app's own price history begins
2021-08-16), `effective_from` is set to 2021-08-16 (MarketRipple's own
PriceBar data start) with an explicit note that this is a documented
safe lower bound, not a claim about the true historical inclusion date —
it is functionally correct for every as-of date this benchmark will ever
query, since no as-of date can predate the price data itself.

`effective_to = NULL` means still a member as of this table's last
research pass (2026-08-23) — not "forever."

See app/services/quant/membership.py for the point-in-time query
function (universe_as_of()) that reads this table.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import Column, Date, DateTime, Index, Integer, String, Text

from app.db.base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class IndexMembership(Base):
    __tablename__ = "index_memberships"

    id             = Column(Integer, primary_key=True, autoincrement=True)
    index_name     = Column(String(32), nullable=False, default="NIFTY50", index=True)
    symbol         = Column(String(32), nullable=False, index=True)   # matches PriceBar.symbol exactly
    effective_from = Column(Date, nullable=False)
    effective_to   = Column(Date, nullable=True)   # NULL = still a member as of the last research pass
    source         = Column(String(500), nullable=False)   # citation URL — required, never blank/fabricated
    notes          = Column(Text, nullable=True)   # precision caveats, rename/merger context, etc.
    researched_at  = Column(Date, nullable=False)   # date this row's facts were verified (not row-insert time)
    created_at     = Column(DateTime(timezone=True), nullable=False, default=_now)

    __table_args__ = (
        Index("ix_index_membership_symbol_dates", "index_name", "symbol", "effective_from"),
    )
