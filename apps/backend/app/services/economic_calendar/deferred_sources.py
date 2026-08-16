"""
Phase 5A — sources evaluated and explicitly deferred, not implemented.

Kept as a real, structured record (not just a comment buried in a PR
description) so a future attempt starts from what was already learned
rather than re-discovering the same dead end, and so nothing here can
be mistaken for "not yet gotten to" when it was actually "tried,
correctly declined."

Owner's rule, applied consistently to every entry below: no guessed
endpoint, no lower-tier fallback, no scraping a third-party aggregator,
no inferred/cadence-based date standing in for an official one.
"""
from __future__ import annotations

DEFERRED_SOURCES = {
    "eurostat": {
        "status": "DEFERRED_SOURCE_DISCOVERY",
        "reason": (
            "Official calendar exists and an official .ics subscription is "
            "advertised (ec.europa.eu/eurostat/subscribe/ics.format), but "
            "the current stable machine-readable feed URL cannot be "
            "recovered reliably without executing Eurostat's client-side "
            "subscription logic (the 'Want to subscribe?' button "
            "constructs the link via JavaScript reading the page's "
            "current filter selections, not a static URL in the page's "
            "HTML). The commonly-cited direct URL "
            "(ec.europa.eu/eurostat/cache/RELEASE_CALENDAR/calendar_EN.ics) "
            "returns a real, server-generated 404 as of 2026-08-16 — "
            "confirmed with a realistic browser User-Agent and Referer, "
            "not a bot-block page."
        ),
        "no_lower_tier_fallback_used": True,
        "no_inferred_url_used": True,
        "no_data_fabricated": True,
        "revisit_condition": (
            "A stable, reproducible way to obtain the official feed "
            "URL exists — e.g. a documented static endpoint Eurostat "
            "publishes, or headless-browser rendering becomes available "
            "in the ingestion environment to execute the subscribe "
            "button's JS. Genuinely valuable once unblocked: the Euro "
            "indicators calendar covers GDP, employment, inflation, "
            "industrial production, retail trade, unemployment, and "
            "bond yields, confirmed running in Europe/Luxembourg time "
            "with the coming week's schedule confirmed every Friday."
        ),
    },
    "ecb": {
        "status": "DEFERRED_NO_TRUSTED_AUTOMATED_INGESTION",
        "reason": (
            "ECB's Governing Council meeting calendar is real and public "
            "(ecb.europa.eu/press/calendars/mgcgc), with a highly regular "
            "cadence (8 meetings/year, always Thursday, decision 14:15 "
            "CET) — but no official machine-readable feed (RSS/.ics) was "
            "confirmed to exist for it during the Phase 5A source audit. "
            "The regularity itself is exactly why an inferred/cadence-"
            "based date is explicitly NOT used here (owner's rule: "
            "'ECB should either be Tier 1 exact-date ingestion or "
            "excluded' — a fixed weekday pattern is precisely the kind "
            "of assumption that quietly breaks the one year a real "
            "schedule shift happens)."
        ),
        "no_lower_tier_fallback_used": True,
        "no_inferred_url_used": True,
        "no_data_fabricated": True,
        "revisit_condition": (
            "An official ECB machine-readable feed is found, or a "
            "reliable page-parsing approach is confirmed against "
            "ecb.europa.eu's own calendar page directly (not yet "
            "attempted with the same rigor as RBI's annualpolicy.aspx "
            "parse)."
        ),
    },
}
