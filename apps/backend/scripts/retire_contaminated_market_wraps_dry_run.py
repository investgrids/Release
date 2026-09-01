"""
P0 remediation -- read-only dry-run report for the 28 confirmed-
contaminated market_wrap articles (owner authorization, 2026-09-01).

Strictly GET-only against production. Cannot write anything -- this
script has no DB session at all, only an HTTP client. Re-fetches each
article's REAL CURRENT state (never trusts the earlier audit's snapshot)
and feeds it through the exact same decide_retirement() decision core
that the real retire_article() execution path uses, so this dry run is
provably the same logic that would run for real, not a parallel
approximation.

Explicitly excludes 5b2779d4 (nifty-cautious-bearish-tilt-nse-0463) --
the one contaminated article with real search demand, held back for a
separate truthful-replacement decision per owner instruction.

The 29 slugs below are the exact, complete CONFIRMED_CONTAMINATED list
from the provenance audit (verified via trigger_event_id, corroborated
1:1 by slug suffix) -- never re-derived from prose/keyword matching.
"""
import argparse
import json
import sys

sys.path.insert(0, ".")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import requests

from app.services.aipe.article_retirement import decide_retirement, WOULD_RETIRE

PROD_API = "https://backend-production-78042.up.railway.app"

# Full 29 CONFIRMED_CONTAMINATED slugs from the audit; EXCLUDES
# 5b2779d4 / nifty-cautious-bearish-tilt-nse-0463 per explicit
# instruction -- 28 slugs below.
CONTAMINATED_SLUGS = [
    "sensex-crash-800-points-today-what-investors-should-do-rss-a4f4",
    "us-iran-tensions-banking-stocks-it-sector-rss-ce66",
    "rbi-intervention-indian-market-oil-stocks-tata-consumer-rss-15d2",
    "why-july-auto-sales-surge-boosts-maruti-tata-motors-investors-rss-8594",
    "rbi-mpc-impact-large-cap-financials-rss-410a",
    "rbi-mpc-meeting-healthcare-stocks-rss-9ee2",
    "rbi-policy-bajaj-electricals-aegis-logistics-investors-rss-2b8d",
    "advanced-enzymes-acquisition-pharma-sector-investors-nse-31cb",
    "rbi-comments-boost-banking-stocks-rss-cd86",
    "rbi-iran-war-resilience-consumer-stocks-fmcg-investors-rss-c7fc",
    "bharat-dynamics-q1-results-defence-stocks-investors-rss-300a",
    "us-fed-minutes-crude-oil-prices-indian-market-sbi-hdfc-bank-rss-dd12",
    "rbi-diaspora-swap-sbi-hdfc-bank-investors-nse-5717",
    "rbi-compounding-order-boosts-tiger-logistics-small-cap-investors-rss-39ec",
    "nifty-bank-support-57300-sbi-hdfc-icici-investors-rss-185a",
    "lic-hdfc-bank-stake-build-investors-rss-da26",
    "why-zydus-usfda-approval-boosts-pharma-investors-nse-8d5b",
    "essar-shipping-revised-results-nifty-range-bound-market-wrap-nse-a073",
    "range-bound-nifty-bank-nifty-investor-strategies-banking-services-nse-9a51",
    "nifty-dip-24200-mixed-sector-momentum-nse-e5dc",
    "why-flat-nifty-signals-caution-mid-cap-fertiliser-investors-nse-41f1",
    "why-bank-niftys-rally-offers-intraday-buying-opportunities-nse-9ef8",
    "middle-east-conflict-energy-prices-impact-reliance-ioc-investors-rss-5177",
    "how-range-bound-nifty-24104-impacts-sugar-stocks-happiest-minds-nse-cb35",
    "jio-platforms-ipo-boosts-telecom-sugar-stocks-rss-7c38",
    "hdfc-bank-ceo-exit-impact-banking-sector-investors-tomorrow-rss-9b0a",
    "sensex-drop-400-points-it-metals-realty-investors-today-rss-5fc1",
    "rkec-sebi-query-real-estate-bank-nifty-tbz-surge-market-wrap-nse-94af",
]

assert len(CONTAMINATED_SLUGS) == 28, f"expected exactly 28 slugs, got {len(CONTAMINATED_SLUGS)}"


def main(out_path: str):
    session = requests.Session()
    session.headers.setdefault("User-Agent", "MarketRipple-P0-Remediation-DryRun/1.0")

    # One real source for id/status/trigger_event_id, regardless of
    # current publication state (unlike /api/insights/{slug}, which is
    # public-facing and 404s for anything not currently status=
    # "published" -- exactly the ambiguity a real "already retired?"
    # check needs to see through). /api/publishing/articles applies no
    # status filter (confirmed in the provenance audit's own methodology).
    list_resp = session.get(
        f"{PROD_API}/api/publishing/articles",
        params={"article_type": "market_wrap", "limit": 100, "offset": 0}, timeout=20,
    )
    list_resp.raise_for_status()
    by_slug = {row["slug"]: row for row in list_resp.json().get("articles", [])}
    print(f"Fetched {len(by_slug)} real current market_wrap rows from production.\n")

    results = []
    for slug in CONTAMINATED_SLUGS:
        row = by_slug.get(slug)
        if row is None:
            decision = decide_retirement(found=False, current_status=None, trigger_event_id=None, dry_run=True)
            results.append({"slug": slug, "found": False, "outcome": decision.outcome, "reason": decision.reason})
            continue

        decision = decide_retirement(
            found=True, current_status=row.get("status"), trigger_event_id=row.get("trigger_event_id"), dry_run=True,
        )
        results.append({
            "slug": slug, "found": True, "article_id": row.get("id"), "current_status": row.get("status"),
            "trigger_event_id": row.get("trigger_event_id"), "outcome": decision.outcome, "reason": decision.reason,
        })

    requested = len(CONTAMINATED_SLUGS)
    found = sum(1 for r in results if r.get("found"))
    provenance_valid = sum(1 for r in results if r.get("outcome") == WOULD_RETIRE)
    legitimate_affected = sum(1 for r in results if r.get("outcome") == "SKIPPED_PROVENANCE_MISMATCH")
    already_retired = sum(1 for r in results if r.get("outcome") == "SKIPPED_ALREADY_RETIRED")
    not_found = sum(1 for r in results if r.get("outcome") == "SKIPPED_NOT_FOUND")
    not_published = sum(1 for r in results if r.get("outcome") == "SKIPPED_NOT_PUBLISHED")

    print("=== P0 remediation dry-run report (read-only, no writes possible) ===\n")
    for r in results:
        print(f"  {r.get('outcome', '?'):<28} {r['slug']}")
        if r.get("outcome") not in (WOULD_RETIRE,):
            print(f"      -> {r.get('reason', r.get('fetch_error', 'unknown'))}")
    print()
    print(f"{requested} requested -> {found} found -> {provenance_valid} provenance-valid -> {provenance_valid} would retire -> {legitimate_affected} legitimate affected")
    print(f"(also: {already_retired} already retired, {not_found} not found, {not_published} not published)")

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "requested": requested, "found": found, "provenance_valid": provenance_valid,
            "would_retire": provenance_valid, "legitimate_affected": legitimate_affected,
            "already_retired": already_retired, "not_found": not_found, "not_published": not_published,
            "results": results,
        }, f, indent=2)
    print(f"\nFull detail written to: {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="p0_remediation_dry_run.json")
    args = parser.parse_args()
    main(args.out)
