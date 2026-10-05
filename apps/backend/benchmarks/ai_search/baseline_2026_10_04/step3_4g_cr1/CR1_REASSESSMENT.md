# CR1 model-free reassessment (current pipeline: 3.4G.1 ranking + 3.4G.2 visibility + 3.4G.3 cold-start fix)

No pipeline code was changed. Zero provider calls. Scripts and data: `cr1_reassessment.py`/`.json` (frozen live-news snapshot), `cr1_live_now.py`/`.json` (the live feed as it is now), `relative_dates_check.py` (read-only data-quality check).

## Classification: **C (still substantively insufficient as a stable live specimen)**, with a **B moment**
- In the frozen snapshot (earlier today) CR1 had one genuinely outlook-bearing headline, so that moment is **B**: relevant but too shallow.
- In the live feed as it is now that headline is gone from the feed window, and what remains is a market-wrap headline, two content-free filing titles and a no-signal memory line: **C**.
- Because the one useful item is transient, CR1 is **not a candidate for a live call**. Keep it out of live benchmarking and keep the Gate A semantics debt and the retrieval gaps below open.

## Evidence journey, what the model sees (titles only)
**Snapshot moment** (cold-start fix in place): `N1` "Kotak Mahindra Bank Primed For Next Leg Of Growth As Street Cheers Anup Saha's Elevation" (rank 1, score 0.95); `N2` "HDFC Bank, YES Bank, AU SFB: Bank stocks jump; Bank Nifty up over 1%..." (a sector wrap that lists Kotak among top gainers); `A1` "Kotak Mahindra Bank Limited has informed the Exchange about Investor Presentation" (17 Aug, 49 days old); `A2` "...about General Updates." (24 Aug); `C1-C3`: market mood, a company-graph story that is about the Nifty and the RBI generally, and a development-memory line "Reconciliation: no_signal (confidence: 28%)". No events (none tagged to Kotak).
**Live now:** only the wrap headline as news (the "Primed" article has left the live feed window), the same two filings, the same context lines.

## Is "Primed For Next Leg Of Growth" enough model-visible evidence? **No: shallow.**
Counting only the headline (its summary is not shown to the model): it supports one sourced sentence: *a news report says analysts cheered Anup Saha's elevation and describes the bank as primed for its next phase of growth.* It carries no figure, no result, no guidance, no valuation, no statement of what the elevation is (the role is not in the title), and the optimism is the article's and "the Street's", not data. A grounded model can repeat it and say the operating outlook cannot be established; it cannot build an outlook. The facts that would help (the summary says analysts value his consumer-finance and credit-portfolio background) are not model-visible, so they cannot count. This is the clearest specimen so far for a grounded-snippet experiment, but CR1 is the wrong specimen to run it on because its evidence is unstable.

## What Gate A is actually relying on: any single non-administrative company-named item
Counterfactuals on the real bundle (Gate A status in each):
| Bundle | Gate A |
|---|---|
| as retrieved | SUFFICIENT |
| without the Investor Presentation filing | SUFFICIENT |
| without all announcements | SUFFICIENT |
| without news | SUFFICIENT (on the Investor Presentation title alone) |
| only the "Primed For Next Leg Of Growth" headline | SUFFICIENT |
| only the General Updates filing and the wrap | SUFFICIENT (on the wrap alone) |
| nothing | INSUFFICIENT |
So Gate A is satisfied by a **sector-wrap headline that merely lists Kotak among top gainers**, by a **content-free filing title**, or by the outlook headline: it cannot tell them apart. The better bundle did not fix sufficiency semantics. "Sufficient" still means "at least one company-named item that is not on the administrative list", not "evidence of the business". This is the same defect as in 3.4G, now demonstrated by removal.

## New findings (retrieval universe and data quality), not fixed
1. **A highly relevant, dated outlook item exists in the database and is never retrieved.** The news table holds "Only 9% up since last MD but Jefferies sees 10% more in Kotak Mahindra Bank shares after Anup Saha's appointment..." (published 2 Oct, 3 days old). It carries no company tag. Company-scoped news retrieval reaches the database only through the `companies` tag (about 7% coverage) and only when the live feed yields fewer than 20 matches, so it is invisible. Of 34 database news rows that mention Kotak Mahindra, 5 are within the 45-day window with a real date and only filings carry a tag. Fix direction: match database news to a company by name in the headline or summary, the way the live-feed path already does.
2. **Relative timestamps are persisted and then read as fresh forever.** 173 of 10,702 news rows store `published_at` as "9m ago"/"2h ago"/"1d ago". Example: "Kotak Mahindra Bank shares fall 3% after CEO's surprise exit. What Nomura, Jefferies said" was ingested on 2026-06-29 with `published_at = "9m ago"`, so the freshness filter computes an age of 0.006 days (and my recency score would give it 1.0). It carries a company tag, though in a form ("Kotak Mahindra Bank") that does not match the registry name ("Kotak Mahindra Bank Ltd"), so it was not retrieved this time. A tag that did match would present a three-month-old story as brand new. This is a freshness-integrity defect for any company news served from the database; it needs its own fix (treat a relative string in a stored row as an unknown age, not as now).
3. The two stories in play pull in opposite directions (a "Primed for growth" appointment story versus CEO-exit uncertainty stories). A user-facing outlook answer built on either alone would mislead; the evidence set cannot currently represent both honestly.

## Tracked for release (as you asked, not fixed)
A retrieval failure and a genuine absence of evidence converge on the same public Gate A refusal; before release a user should not be told "we don't have evidence" when the real condition was "one of our evidence sources failed". (3.4G.3 records failures internally and in the log; the public wording is untouched.)

## Verdict and next
CR1 stays out of live benchmarking. Required before it can be a candidate: (a) company-name matching for database news so relevant untagged items like the Jefferies one reach the bundle, (b) the relative-date integrity fix, (c) Gate A requiring an affirmative substantive signal rather than any non-administrative company-named item. None was started. Next in the agreed sequence: one SR2 live call on the current titles-only contract.
