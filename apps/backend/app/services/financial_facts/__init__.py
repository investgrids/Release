"""
Financial Facts — S3-B (2026-08-25). Reusable infrastructure for real,
traceable, per-filing banking fundamentals, sourced from NSE's real XBRL
financial-results filings (not PDF — see artifacts/marketripple_score_s3_
pdf_extraction_feasibility.md and its S3-A follow-up for how this source
was found and validated: 20/20 real bank-quarters populated across the 5
MarketRipple Score reference banks once correctly scoped to Non-
Consolidated filings).

Not coupled to the MarketRipple Score engine — this is meant to also feed
Company Financials, AI Search, and future Article Truth Layer work, same
as the module docstring on app/db/models/financial_fact.py explains.
"""
