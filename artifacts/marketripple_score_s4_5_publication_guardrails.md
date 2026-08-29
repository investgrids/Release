# MarketRipple Score — S4.5 Publication Guardrails

**Date:** 2026-08-29
**Scope:** Owner-authorized S4.5 (8 items, in response to the S4 report). Frozen S3-D algorithm and weights untouched — this phase adds peer-universe canonicalization, methodology versioning, and cross-sectional plausibility validation. `publishable=False` throughout.
**Branch:** `company-identity/c1-reconciliation`

## What was built

1. **Canonical peer universe.** New `app/services/marketripple_score/banking_universe.py` derives `ALL_ELIGIBLE_NSE_BANKS` (27 real symbols) directly from `app.api.companies._NSE_UNIVERSE`, not hand-copied. `score_financial_strength()`/`score_valuation()` now default to it when `peer_group=None` — replacing the old 5-bank default. The old 5-bank group is kept as `LARGE_PRIVATE_PEER_GROUP`, explicitly marked as reserved for a possible future "Large Private Bank Rank" sub-analytic, never the primary score's default again.
2. **Methodology/version metadata.** `MarketRippleScore` now carries real, structural fields — `methodology_version` (`BANKING_V1` for Banking), `peer_universe` (the actual symbol list used), `peer_universe_count`, `peer_universe_as_of` — so the population a score was computed against travels with the score itself, verified live below.
3. **Cross-sectional plausibility validation.** New `quality.assess_plausibility(metric_code, value)` in `financial_facts/quality.py`, a new `QUALITY_IMPLAUSIBLE_SCALE` status, wired into the real ingestion pipeline (`ingest.py`) alongside the existing within-entity anomaly check. Bounds are metric/unit-grounded, not fit to YESBANK: `cet1_ratio` gets a real regulatory floor (2%-60%, based on Basel III's 4.5% absolute minimum / RBI's ~8% effective minimum); `gross_npa_pct`/`net_npa_pct`/`roa` get loose structural sanity bounds (catch a gross scale error, not a "looks weird vs. peers" judgment).
4. **Exclusion, never correction.** `_latest_valid_fact_value()` now excludes `IMPLAUSIBLE_SCALE` rows the same way it already excluded `ANOMALY` rows — applies uniformly whether the symbol is the one being scored or a peer feeding someone else's percentile rank. No `value` is ever modified.
5. **Retroactive backfill** (`scripts/s45_backfill_plausibility.py`) applied the new check to the 1,862 already-ingested real rows: exactly 8 flagged, all YESBANK `cet1_ratio`, all 8 real quarters — zero false positives across the other 26 banks' real data.
6. **Real verification re-run** (`scripts/s45_verification_rerun.py`, `s45_yesbank_submetric_check.py`) — see below.
7. **Tests**: 3 new unit tests for `assess_plausibility` (real YESBANK case, real observed-range non-false-positive check across all 5 CET1 values in the 27-bank sample, unscoped-metric passthrough). Full relevant suite (`test_financial_facts.py` + `test_marketripple_score.py`): 21/21 pass. Full backend suite: 1099 passed / 7 failed (all pre-existing, unrelated — AI search live tests, comparison publisher V3 live tests, development historical retrieval — none touching `marketripple_score`/`financial_facts`/`financial_fact`).

## Real re-run results (15 banks: original five + top/bottom outliers + YESBANK)

| Symbol | FinStr | MRScore | Coverage | MethodVer | PeerCount | Publishable |
|---|---|---|---|---|---|---|
| ICICIBANK | 68.5 | 60.2 | 83.3% | BANKING_V1 | 27 | False |
| HDFCBANK | 64.5 | 51.4 | 83.3% | BANKING_V1 | 27 | False |
| AXISBANK | 58.2 | 48.7 | 83.3% | BANKING_V1 | 27 | False |
| KOTAKBANK | 71.8 | 57.6 | 80.0% | BANKING_V1 | 27 | False |
| SBIN | 45.0 | 47.6 | 83.3% | BANKING_V1 | 27 | False |
| MAHABANK | 83.2 | 74.1 | 77.8% | BANKING_V1 | 27 | False |
| KARURVYSYA | 89.0 | 71.0 | 73.3% | BANKING_V1 | 27 | False |
| IDBI | 60.9 | 65.8 | 77.8% | BANKING_V1 | 27 | False |
| IOB | 69.2 | 61.9 | 77.8% | BANKING_V1 | 27 | False |
| BANDHANBNK | 24.8 | 25.7 | 73.3% | BANKING_V1 | 27 | False |
| PSB | 32.3 | 37.5 | 77.8% | BANKING_V1 | 27 | False |
| BANKBARODA | 34.6 | 41.0 | 68.3% | BANKING_V1 | 27 | False |
| CANBK | 28.3 | 40.9 | 73.3% | BANKING_V1 | 27 | False |
| RBLBANK | 36.1 | 41.2 | 73.3% | BANKING_V1 | 27 | False |
| YESBANK | 61.6 | 55.1 | 67.5% | BANKING_V1 | 27 | False |

**Items 1-2 confirmed**: every bank now carries `methodology_version=BANKING_V1`, `peer_universe_count=27` — real, structural metadata, not a detail-dict afterthought. Non-YESBANK scores moved by 0.0-0.3 points versus the S4 baseline — small, consistent with a single bank (YESBANK) shifting out of a 27-bank percentile pool, not noise.

**Item 7 confirmed** (peer-pool exclusion works for other banks, not just the scored symbol): a direct query shows CET1's real peer pool size dropped from 27 to 26 once YESBANK's value is excluded — confirmed by `_latest_valid_fact_value` returning `None` for YESBANK's `cet1_ratio` even when YESBANK is being read as *someone else's* peer.

## Item 6 — real finding, not just a pass/fail

The naive check ("did coverage drop instead of silently defaulting to zero-inflation") **passes**: YESBANK's `coverage_pct` correctly dropped 70.8%→67.5%, and `cet1_ratio` is confirmed absent from its `metrics_used`/`detail`.

But a deeper, real check surfaced something the naive one misses. **YESBANK's own Financial Strength score rose from 52.8 to 61.6** after excluding its implausible CET1 — the opposite of what "fixing a contaminated filer" should do. A direct per-metric percentile pull explains why:

| Metric | YESBANK real value | Peer pool | YESBANK percentile |
|---|---|---|---|
| `gross_npa_pct` | 0.0002 (0.02%) | 27 | **100.0** (ranked #1 of 27 — "best" asset quality of any real bank) |
| `net_npa_pct` | 0.0 | 27 | **100.0** (tied #1 of 27) |
| `cet1_ratio` | *(excluded)* | 26 | — |
| `roa` | 0.0001 (0.01%) | 27 | 0.0 (correctly ranks last — near-zero ROA is genuinely bad) |

Gross NPA and Net NPA come from the exact same contaminated filer as CET1 — almost certainly the same underlying scale/unit error — but neither has a comparable hard regulatory floor the way CET1 does (Basel/RBI mandate a capital minimum; there's no equivalent legal minimum an NPA ratio must clear), so the current bounds (loose, upper-only sanity checks) don't catch them. Under the frozen percentile formula, "lower NPA is better" — so an implausible near-zero value doesn't just fail to hurt YESBANK, it makes YESBANK rank **#1 of 27 real banks** on both asset-quality metrics, which is why removing only the CET1 drag let the average rise.

**This is a real, disclosed limitation, not a new bug**: the plausibility layer as scoped only has a defensible bound for the one metric with a genuine structural/regulatory floor. Two honest paths forward, not something to decide unilaterally:
- **(a) Extend the bounds** to NPA/ROA with a real, defensible floor if one exists (harder to justify than CET1's — no legal minimum), or
- **(b) Quarantine at the observation level**: if any one metric for a symbol+period is flagged `IMPLAUSIBLE_SCALE`, treat every metric from that same symbol+period as suspect too, since they likely share the same filing-level scale error — a different, second-generation design (cross-metric, not purely per-metric/unit) that goes beyond what "metric plausibility validation" as originally scoped covers.

Neither was implemented here — flagging for a decision rather than inventing a threshold reactively, matching the standing instruction throughout this initiative.

## Items 3, 4, 8 — status

- Item 3 (non-blocking, deferred by design): historical `parse_failed` rows unchanged from S4 — not revisited, per the S4 report's own "not a publication blocker" conclusion.
- Item 4 confirmed: the 37-40 min sequential-fetch pattern is unchanged (this phase didn't touch performance) — still a real S5 productionization item, not attempted here.
- Item 8: `publishable=False` unchanged everywhere, confirmed in every row of the re-run table above.

## Recommendation

Items 1, 2, 5, 7, 8 are done and verified with real data. Item 6 is verified in the narrow sense (no silent zero-inflation) but surfaced a real, more important finding that needs a decision before S5: **the plausibility layer currently only fully protects CET1** — a filer with the same class of scale error on NPA/ROA can still land at the top of the peer ranking. Recommend deciding between extending bounds vs. observation-level quarantine before treating S4.5 as closed.
