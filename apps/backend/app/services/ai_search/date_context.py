"""
Shared current-date/fiscal-year context, injected into every LLM prompt in
both pipelines (V2 and V3) so a response can't reference a stale
"current"/"upcoming" fiscal year or quarter.

Computed fresh on every call — never baked into a module-level constant.
Both pipelines' server processes routinely run for days between deploys (the
P0-P3.5 deploy's old backend ran unchanged since 2026-08-04), so a date
string frozen at import time would silently go stale for the process's
entire uptime. This is the confirmed root cause of a real hallucination: a
report referenced "FY25E" (India FY25 = Apr 2024-Mar 2025, already ended)
as if it were current/upcoming while the real date was ~17 months later —
traced to no prompt anywhere ever stating the actual current date.
"""
from __future__ import annotations

from datetime import date


def current_date_context(today: date | None = None) -> str:
    """India's fiscal year runs April-March — FY26 means Apr 2025-Mar 2026,
    the labeling convention already used throughout this codebase's own
    prompts (e.g. "FY26 revenue growth"). `today` is overridable for tests;
    real callers should never pass it, so this always reflects the actual
    moment the prompt is built."""
    d = today or date.today()
    fy_end_year = d.year + 1 if d.month >= 4 else d.year
    fy_start_year = fy_end_year - 1
    fy_label = f"FY{str(fy_end_year)[2:]}"
    return (
        f"Today's real date is {d:%Y-%m-%d}. India's current fiscal year is {fy_label} "
        f"(April {fy_start_year}–March {fy_end_year}). Do not describe any fiscal "
        f"year, quarter, or date as current/upcoming/recent if it has already passed "
        f"relative to today's real date above — check before writing any "
        f"date-relative language."
    )
