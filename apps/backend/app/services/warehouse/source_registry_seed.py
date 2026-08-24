"""
Real Source Registry seed — Phase 1B Batch 1 (owner instruction,
2026-08-23: seed minimal Source Registry before tables that reference
it). Every row below traces to a source actually found and verified
during the Phase 1A data-flow audit (two independent agent passes,
market/macro and news/evidence) — nothing here is invented.

`rights_basis` is answered honestly per source, including "unverified"
and "unofficial_scraped_api" where that's the truth — the Phase 1A
audit's own finding was that only the Fed feed carried any explicit
rights-basis reasoning in code; this table makes every source answer
the same question instead of staying silent.

Idempotent — re-running replaces all rows (same convention as
index_membership_seed.py).
"""
from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.source_registry import Source

# (id, name, domain, source_type, collection_method, frequency, priority, rights_basis, robots_checked, notes)
_ROWS: list[tuple[str, str, str, str, str, str, int, str, bool, str]] = [
    # --- News/RSS (persisted pipeline — RSSProvider) ---
    ("rss_economic_times_markets", "Economic Times - Markets", "economictimes.indiatimes.com", "rss",
     "official publisher RSS feed", "15min", 5, "official_rss", False,
     "Persisted via RSSProvider -> news_articles. A second, cache-only duplicate fetch of the same URL exists in news_fetcher.py — see Phase 1A audit finding #6."),
    ("rss_moneycontrol_latest", "Moneycontrol - Latest News", "moneycontrol.com", "rss",
     "official publisher RSS feed", "15min", 5, "official_rss", False, "Persisted via RSSProvider."),
    ("rss_ndtv_profit", "NDTV Profit - Latest", "feeds.feedburner.com", "rss",
     "official publisher RSS feed (via Feedburner)", "15min", 5, "official_rss", False, "Persisted via RSSProvider."),
    ("rss_business_standard_markets", "Business Standard - Markets", "business-standard.com", "rss",
     "official publisher RSS feed", "15min", 5, "official_rss", False, "Persisted via RSSProvider."),
    ("rss_livemint_markets", "Livemint - Markets", "livemint.com", "rss",
     "official publisher RSS feed", "15min", 5, "official_rss", False, "Persisted via RSSProvider."),
    ("rss_google_news_india", "Google News - India stock market search", "news.google.com", "rss",
     "Google News search-query RSS", "15min", 4, "official_rss", False,
     "Aggregator search feed, not a direct publisher — lower priority than direct-publisher feeds."),

    # --- Regulatory filings ---
    ("nse_corporate_announcements", "NSE Corporate Announcements/Board Meetings/Corporate Actions", "nseindia.com", "api",
     "unofficial internal JSON API (scraped, cookie warm-up required)", "15min (news) + 30min (company_announcements)", 8,
     "unofficial_scraped_api", False,
     "Real, working, only source of company_announcements today. Two independent schedulers hit this endpoint at different cadences — Phase 1A duplicate-fetch finding. No PDF attachments retained (attachment_url always None)."),
    ("bse_corporate_announcements", "BSE Corporate Announcements", "api.bseindia.com", "api",
     "unofficial internal API (scraped)", "attempted 15/30min, currently always fails", 3, "unofficial_scraped_api", False,
     "Confirmed non-functional in production — Akamai bot wall, resistant to TLS-fingerprint impersonation. Contributes zero real rows. Needs a paid/registered BSE data feed decision, not more scraping engineering."),

    # --- Government/regulator RSS ---
    ("rbi_press_releases", "RBI Press Releases", "rbi.org.in", "rss", "official government RSS", "60min", 7,
     "official_rss", False, "No explicit in-code rights-basis reasoning found despite being an official government source — Phase 1A gap this table closes."),
    ("pib_finance", "PIB - Finance/Economic Affairs", "pib.gov.in", "rss", "official government RSS (ModId=6, Finance ministry)", "60min", 6,
     "official_rss", False, "Ministry attribution is keyword-guessed from headline text, not structured data."),
    ("sebi_circulars", "SEBI Circulars", "sebi.gov.in", "rss", "official government RSS/sitemap feed", "60min", 6,
     "official_rss", False, "Flagged in-repo as 'often unreliable' (module docstring)."),
    ("fed_press_releases", "US Federal Reserve Press Releases (Monetary Policy)", "federalreserve.gov", "rss",
     "official government RSS, filtered to Monetary Policy category", "60min", 6, "public_domain", False,
     "Only source in the codebase with an explicit rights-basis comment in code: public domain, 17 U.S.C. Sec.105."),

    # --- Market/macro (yfinance-backed) ---
    ("yfinance_india_vix", "India VIX", "finance.yahoo.com", "api", "yfinance quote (^INDIAVIX)", "intraday", 8,
     "vendor_data", False, "Fetched from 4 independent, non-communicating code paths per Phase 1A audit — MarketObservation is the first shared persistence point."),
    ("yfinance_banknifty", "Bank Nifty", "finance.yahoo.com", "api", "yfinance quote (^NSEBANK)", "intraday", 8, "vendor_data", False, ""),
    ("yfinance_usdinr", "USD/INR", "finance.yahoo.com", "api", "yfinance quote (USDINR=X)", "intraday", 6, "vendor_data", False, ""),
    ("yfinance_brent", "Brent Crude", "finance.yahoo.com", "api", "yfinance quote (BZ=F)", "intraday", 6, "vendor_data", False, ""),
    ("yfinance_sector_etfs", "NSE Sector ETF Proxies (12 sectors)", "finance.yahoo.com", "api",
     "yfinance quotes, 12 sector ETF tickers as a performance proxy", "intraday", 7, "vendor_data", False,
     "The live, accurate replacement for the dead seed-only sector_data table (Phase 1A audit)."),
    ("nse_gift_nifty", "GIFT Nifty", "nseindia.com", "api", "unofficial internal marketStatus API (scraped)", "intraday", 6,
     "unofficial_scraped_api", False, "gift_nifty_service.py has an explicit anti-fabrication design (never substituted/relabeled) but no DB write path before this batch."),
    ("nse_fii_dii", "FII/DII Net Flow", "nseindia.com", "api", "unofficial internal API (scraped, fiidiiTradeReact)", "6h (previous-session figure)", 6,
     "unofficial_scraped_api", False, "NSE's own figure is previous-session, not live same-session flow — stored as-is, never relabeled."),
    ("nse_option_chain_pcr", "Nifty Put-Call Ratio / Max Pain", "nseindia.com", "api",
     "unofficial internal option-chain API (scraped)", "15min", 6, "unofficial_scraped_api", False, ""),

    # --- Phase 1C Batch 3A additions (2026-08-23) ---
    ("yfinance_global_indices", "Global Indices (Dow/S&P500/Nasdaq/FTSE/DAX/CAC/Nikkei/HangSeng/Shanghai/KOSPI)",
     "finance.yahoo.com", "api", "yfinance quotes — canonical source: app/api/market.py::_GLOBAL_INDICES (superset of "
     "market_data.py's own narrower, overlapping _US_INDICES/_ASIAN_MARKETS dicts — chosen as the single producer per "
     "the owner's explicit 'no duplicate persistence pipelines' instruction)", "intraday", 5, "vendor_data", False, ""),
    ("yfinance_us_vix", "US VIX (CBOE)", "finance.yahoo.com", "api", "yfinance quote (^VIX) — distinct instrument from India VIX",
     "intraday", 5, "vendor_data", False, ""),
    ("yfinance_us_futures", "US Index Futures (ES/NQ/YM)", "finance.yahoo.com", "api",
     "yfinance quotes — app/api/market.py::_US_FUTURES_TICKERS", "intraday", 5, "vendor_data", False, ""),
    ("yfinance_adrs", "Indian ADRs (INFY/WIT/HDB/IBN)", "finance.yahoo.com", "api",
     "yfinance quotes — app/api/market.py::_ADR_TICKERS", "intraday", 5, "vendor_data", False, ""),
    ("yfinance_commodities", "Commodities (Gold/Silver/Copper/Platinum/WTI/NatGas/DXY)", "finance.yahoo.com", "api",
     "yfinance quotes — canonical source: app/api/commodities.py's _METALS_DEF/_ENERGY_DEF (more complete than "
     "market_data.py's own overlapping, narrower _COMMODITIES dict — chosen as the single producer per metric); DXY "
     "sourced from market_data.py._COMMODITIES since it's the only place that ticker exists", "intraday", 5, "vendor_data", False,
     "India Petrol (Retail) deliberately excluded — commodities.py's own ticker=None for it, a static non-market estimate, not a real quote."),
    ("yfinance_currency_pairs", "EUR/INR, GBP/INR", "finance.yahoo.com", "api",
     "yfinance quotes — app/api/market.py::_CURRENCY_PAIRS (USD/INR already covered by yfinance_usdinr)",
     "intraday", 4, "vendor_data", False, ""),
    ("macro_rates_us_treasury", "US Treasury 2Y/10Y Par Yield", "home.treasury.gov", "api",
     "official US Treasury XML feed — app/services/macro_rates/us_treasury_source.py, via the shared "
     "get_macro_rate_state() cache", "daily (source's own cadence)", 5, "official_api", False, ""),
    ("macro_rates_fed_funds", "US Fed Funds Rate", "federalreserve.gov", "api",
     "official Fed H.15 release — app/services/macro_rates/fed_funds_source.py, via get_macro_rate_state()",
     "daily (source's own cadence)", 5, "public_domain", False, ""),
    ("macro_rates_rbi_wss", "India Repo Rate / 10Y G-Sec (RBI WSS)", "rbi.org.in", "scrape",
     "RBI Weekly Statistical Supplement — app/services/macro_rates/rbi_wss_source.py, via get_macro_rate_state()",
     "weekly (source's own cadence)", 5, "official_api", False,
     "Deliberately delayed/weekly-cadence data — real india_10y_gsec_observed_at/repo_rate_observed_at from the source, never today's date substituted."),
    ("market_breadth_nifty500_sample", "NSE Market Breadth (estimated)", "finance.yahoo.com", "api",
     "yfinance quotes across a hardcoded 49-symbol Nifty 500 sample — app/services/market_data.py::get_top_movers/"
     "_NIFTY500_SAMPLE", "intraday", 3, "vendor_data", False,
     "A genuine sample-based ESTIMATE, not real exchange-wide advance/decline data — no honest source for that exists "
     "in this codebase today (Phase 1A audit finding). Always captured with quality=estimated, never presented as authoritative breadth."),
]


async def seed_source_registry(db: AsyncSession) -> dict:
    """Idempotent UPSERT — updates an existing row's fields in place by
    id, inserts genuinely new ones. Changed from an earlier delete-all/
    reinsert pattern (Batch 3, 2026-08-23): MarketObservation and
    RawEvidence now hold real rows with a FOREIGN KEY into this table's
    `id` — deleting and reinserting a still-referenced source risked an
    integrity error (or, if FK enforcement happens to be off, a silent
    dangling-reference window) for zero benefit over a plain update.
    Never removes a row no longer listed in _ROWS — a source going out
    of use should stay described, not disappear out from under its
    historical rows."""
    existing = {row.id: row for row in (await db.execute(select(Source))).scalars().all()}

    inserted = 0
    updated = 0
    for id_, name, domain, source_type, method, freq, priority, rights, robots, notes in _ROWS:
        if id_ in existing:
            row = existing[id_]
            row.name, row.domain, row.source_type = name, domain, source_type
            row.collection_method, row.frequency, row.priority = method, freq, priority
            row.rights_basis, row.robots_checked, row.notes = rights, robots, notes or None
            updated += 1
        else:
            db.add(Source(
                id=id_, name=name, domain=domain, source_type=source_type, collection_method=method,
                frequency=freq, priority=priority, rights_basis=rights, robots_checked=robots, notes=notes or None,
            ))
            inserted += 1
    await db.commit()
    return {"rows_inserted": inserted, "rows_updated": updated}
