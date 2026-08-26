"""
Unified MarketRipple Score — S2 (2026-08-25).

Phase S1 (artifacts/marketripple_score_s1_feasibility_audit.md) traced every
proposed input to real data and found the engine PARTIALLY READY: Current
Intelligence, Market Behaviour, and Valuation are real and buildable today;
Financial Strength (Banking) is real but covers only 4 of 12 proposed
metrics — the two categories a credit analyst checks first (asset quality,
capital adequacy) are completely absent from every data source this app has.

Owner decision following S1: build the engine now, but gate publication.
S2 computes a real, coverage-aware score for the reference banking cohort
and can be inspected end to end — it does NOT replace anything on the
Company page yet. See engine.py::MarketRippleScore.publishable.

"S2 may calculate. S2 may test. S2 may not replace the Company-page score
yet." — only once S3 (a real banking fundamentals data initiative, not
started) closes the Financial Strength gap, or another structured source is
found, does this get re-validated and activated.
"""
