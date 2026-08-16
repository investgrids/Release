"""
Economic Calendar ingestion — Phase 5A.3.

sync_engine.py is the one shared upsert path every source module (RBI,
MOSPI, ...) goes through — no source writes to EconomicCalendarEvent
directly. This is what makes "official source is truth, don't let a
lower tier overwrite it" an enforced rule rather than a convention each
source module would otherwise have to reimplement.
"""
