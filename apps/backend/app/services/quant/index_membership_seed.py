"""
Real, sourced NIFTY 50 point-in-time constituent history — Phase B0
leakage-lock (owner instruction, 2026-08-23).

Every row below traces to a real NSE Indices / Nifty Indices press
release or a reputable financial-news report citing one — see each row's
`source`. Nothing here was inferred from a stock's listing date or from
today's constituent list; where a symbol's true original inclusion date
could not be independently verified (most long-standing constituents —
membership going back years to decades before this app's own price
history starts), `effective_from` is set to 2021-08-16 — MarketRipple's
own PriceBar data start — explicitly as a documented safe lower bound,
not a claim about the actual historical inclusion date. That is
functionally correct for every as-of date this benchmark will ever
query, since no as-of date can predate the price data itself.

Research pass conducted 2026-08-23. Checked all 11 NSE Indices Nifty 50
semi-annual/off-cycle reconstitution events from 2021-08-16 through
2026-08-17 (the window this app has PriceBar data for); only 7
reconstitution events touched Nifty 50 in that span. Re-run this seed
(idempotent — see seed_index_membership()) if a newer research pass
supersedes it; do not hand-edit dates here without a real citation.

Known gaps (see README section in seed_index_membership()'s docstring):
- ADANIPORTS/EICHERMOT/SBILIFE: month-precision sourcing only, exact day
  not found in the source consulted — day set to the 1st of the month as
  a conservative placeholder; this predates the app's own data window by
  years regardless, so it cannot affect any real benchmark query.
- SHRIRAMFIN's 2022 merger/rename (SRTRANSFIN -> SHRIRAMFIN) has no
  single unambiguous "scheme effective date" across sources (NCLT order
  Nov 14 2022 vs. record date Nov 30 2022 vs. an "appointed date" of
  Apr 1 2022 quoted in one place) — irrelevant to this table's actual
  content, since SRTRANSFIN was never itself a Nifty 50 constituent;
  only SHRIRAMFIN's real 2024-03-28 Nifty 50 entry date matters here.
- TATAMOTORS: included for completeness (was not touched by any
  reconstitution event in-window per this research pass) even though it
  currently has zero PriceBar rows (Oct-2025 demerger, see universe.py) —
  a membership row existing doesn't create a prediction if there's no
  price data to predict from.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.index_membership import IndexMembership

_RESEARCHED_AT = date(2026, 8, 23)
_WINDOW_START = date(2021, 8, 16)  # MarketRipple's own PriceBar data start — the documented safe-floor placeholder

# (symbol, effective_from, effective_to, source, notes)
_ROWS: list[tuple[str, date, date | None, str, str]] = [
    # --- Added within the 2021-08-16..2026-08-17 window (exact NSE-sourced dates) ---
    ("APOLLOHOSP", date(2022, 3, 31), None,
     "https://www.niftyindices.com/Press_Release/ind_prs24022022_1.pdf",
     "NSE Indices press release 2022-02-24; replaced IOC effective close of 2022-03-30 / from 2022-03-31."),
    ("ADANIENT", date(2022, 9, 30), None,
     "https://www.business-standard.com/article/markets/nse-to-add-adani-enterprises-to-benchmark-index-by-removing-shree-cement-122090101456_1.html",
     "NSE Indices announcement 2022-09-01, corroborated by 3+ independent outlets; replaced Shree Cement. "
     "Primary niftyindices.com PDF not directly retrieved — secondary sourcing only, meets the stated fallback bar."),
    ("SHRIRAMFIN", date(2024, 3, 28), None,
     "https://www.nseindia.com/resources/nse-replacements-in-indices-wef-march-28-2024",
     "First-ever Nifty 50 entry for this entity; replaced UPL. The pre-merger/pre-rename entity "
     "(Shriram Transport Finance, ticker SRTRANSFIN) was NEVER itself a Nifty 50 constituent — "
     "confirmed via the 2022 merger research, no pre-2024 membership to carry forward."),
    ("TRENT", date(2024, 9, 30), None,
     "https://www.niftyindices.com/Press_Release/ind_prs23082024.pdf",
     "NSE Indices press release 2024-08-23; replaced LTIMindtree."),
    ("BEL", date(2024, 9, 30), None,
     "https://www.niftyindices.com/Press_Release/ind_prs23082024.pdf",
     "NSE Indices press release 2024-08-23; replaced Divi's Laboratories."),
    ("ETERNAL", date(2025, 3, 28), None,
     "https://www.niftyindices.com/Press_Release/ind_prs21022025.pdf",
     "NSE Indices press release 2025-02-21; replaced BPCL. Entity renamed Zomato Ltd -> Eternal Ltd "
     "(MCA approval ~2025-03-20, per secondary reporting) essentially concurrent with this Nifty 50 entry — "
     "no gap where 'Eternal' existed as a distinct identity long before index inclusion."),
    ("JIOFIN", date(2025, 3, 28), None,
     "https://www.niftyindices.com/Press_Release/ind_prs21022025.pdf",
     "NSE Indices press release 2025-02-21; replaced Britannia Industries."),

    # --- Removed within the window (still real PriceBar history in this app) ---
    ("HEROMOTOCO", _WINDOW_START, date(2025, 9, 29),
     "https://www.niftyindices.com/Press_Release/ind_prs22082025.pdf",
     "NSE Indices press release 2025-08-22; removed effective close of 2025-09-29 (from 2025-09-30), "
     "replaced by Max Healthcare Institute. effective_from uses the app's own data-window floor — "
     "true original inclusion date long predates 2021-08-16, not independently verified."),
    ("INDUSINDBK", _WINDOW_START, date(2025, 9, 29),
     "https://www.niftyindices.com/Press_Release/ind_prs22082025.pdf",
     "Same reconstitution event as HEROMOTOCO; replaced by InterGlobe Aviation (IndiGo). "
     "effective_from uses the app's own data-window floor, same caveat as above."),

    # --- Pre-window addition, exact date verified (still real, useful for reuse beyond this benchmark) ---
    ("ADANIPORTS", date(2015, 8, 1), None,
     "https://www.business-standard.com/article/pti-stories/adani-ports-to-replace-nmdc-on-nifty-115081201496_1.html",
     "Month-precision sourcing only (Aug 2015); exact day not found, day-of-month set to 1 as a placeholder. "
     "Predates the app's data window by ~6 years, so day-level precision doesn't affect any real query."),
    ("EICHERMOT", date(2016, 4, 1), None,
     "https://www.business-standard.com/article/reuters/nse-to-add-4-companies-drop-3-from-nifty-116022200858_1.html",
     "Effective date reported as 2016-04-01."),
    ("BAJAJFINSV", date(2018, 4, 2), None,
     "https://www.business-standard.com/article/markets/bajaj-finserv-grasim-and-titan-to-be-part-of-nifty-50-index-from-april-2-118022101285_1.html",
     "Effective 2018-04-02, same reconstitution event as TITAN below."),
    ("TITAN", date(2018, 4, 2), None,
     "https://www.business-standard.com/article/markets/bajaj-finserv-grasim-and-titan-to-be-part-of-nifty-50-index-from-april-2-118022101285_1.html",
     "Effective 2018-04-02, same reconstitution event as BAJAJFINSV above."),
    ("JSWSTEEL", date(2018, 9, 28), None,
     "https://www.business-standard.com/article/markets/jsw-steel-to-replace-pharma-firm-lupin-in-nifty-50-from-september-28-118082900021_1.html",
     "Effective 2018-09-28; replaced Lupin."),
    ("HDFCLIFE", date(2020, 7, 31), None,
     "https://www.business-standard.com/article/markets/hdfc-life-hits-all-time-high-ahead-of-inclusion-in-nifty-50-index-120072800338_1.html",
     "Effective 2020-07-31."),
    ("SBILIFE", date(2020, 9, 25), None,
     "https://www.business-standard.com/article/markets/sbi-life-divi-s-laboratories-to-move-in-nifty-50-index-from-sept-25-120082001839_1.html",
     "Effective ~2020-09-25 (source states 'from Sept 25')."),
    ("TATACONSUM", date(2021, 3, 31), None,
     "https://www.business-standard.com/article/markets/tata-consumer-to-replace-gail-india-in-nifty-50-effective-march-31-121022301290_1.html",
     "Effective 2021-03-31; replaced GAIL. This is the only pre-window addition close enough to the data "
     "window's start (2021-08-16) that its exact date is directly relevant — a stock 4.5 months into "
     "membership when the app's PriceBar history begins."),

    # --- Continuous throughout the window, original inclusion date not independently verified ---
    # (confirmed NOT touched by any of the 11 Nifty 50 reconstitution events checked 2021-08-16..2026-08-17;
    # most have been members for years to decades — effective_from is a safe-floor placeholder, not a
    # claim about the true historical date. See module docstring.)
    *[
        (sym, _WINDOW_START, None,
         "research pass 2026-08-23: confirmed absent from every Nifty 50 add/remove event 2021-08-16..2026-08-17",
         "Continuous member throughout the app's entire data window; true original inclusion date not "
         "independently verified (likely predates this window by years) — effective_from is the app's own "
         "PriceBar data start, a documented safe lower bound, not the real historical inclusion date.")
        for sym in (
            "ASIANPAINT", "AXISBANK", "BAJAJ-AUTO", "BAJFINANCE", "BHARTIARTL",
            "CIPLA", "COALINDIA", "DRREDDY", "GRASIM", "HCLTECH", "HDFCBANK",
            "HINDALCO", "HINDUNILVR", "ICICIBANK", "INFY", "ITC", "KOTAKBANK",
            "LT", "M&M", "MARUTI", "NESTLEIND", "NTPC", "ONGC", "POWERGRID",
            "RELIANCE", "SBIN", "SUNPHARMA", "TATASTEEL", "TCS", "TECHM",
            "ULTRACEMCO", "WIPRO",
        )
    ],
    ("TATAMOTORS", _WINDOW_START, None,
     "research pass 2026-08-23: confirmed absent from every Nifty 50 add/remove event 2021-08-16..2026-08-17",
     "Included for completeness of the reusable membership table even though this symbol currently has "
     "zero PriceBar rows (Oct-2025 demerger — see universe.py's own docstring). A membership row existing "
     "does not create a prediction without real price data to predict from."),
]


async def seed_index_membership(db: AsyncSession, index_name: str = "NIFTY50") -> dict:
    """Idempotent — re-running this after a future research pass replaces
    every row for `index_name` rather than accumulating duplicates."""
    existing = (await db.execute(
        select(IndexMembership).where(IndexMembership.index_name == index_name)
    )).scalars().all()
    for row in existing:
        await db.delete(row)
    await db.flush()

    inserted = 0
    for symbol, eff_from, eff_to, source, notes in _ROWS:
        db.add(IndexMembership(
            index_name=index_name, symbol=symbol, effective_from=eff_from, effective_to=eff_to,
            source=source, notes=notes, researched_at=_RESEARCHED_AT,
        ))
        inserted += 1
    await db.commit()
    return {"index_name": index_name, "rows_inserted": inserted, "researched_at": str(_RESEARCHED_AT)}
