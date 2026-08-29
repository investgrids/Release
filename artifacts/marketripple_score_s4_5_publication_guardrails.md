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

## S4.5-B — filing-level contamination quarantine (owner decision: quarantine, not new bounds)

Owner's decision on the item-6 finding: don't invent a lower NPA/ROA bound (no real regulatory floor exists there the way it does for CET1 — an opinionated data-cleaner risk). Instead, make the **source filing itself** the trust boundary: one XBRL document shares one unit/scale convention across every tag it contains, so a structural failure on any one metric is real evidence the whole document is suspect.

**Built:**
- New `QUALITY_SOURCE_DOCUMENT_QUARANTINED` status, distinct from the triggering `QUALITY_IMPLAUSIBLE_SCALE` — the report can always tell "this was the evidence" from "this was quarantined by association."
- New `quality.quarantine_document_if_needed(db, symbol, source_provider, source_document_id, consolidation_scope)`, keyed on the **real document identity** — `(symbol, source_provider, source_document_id, consolidation_scope)`, never just symbol+period, so a Quarterly filing's scale problem can never leak into an Annual filing's real, unrelated facts for the same symbol/period. Wired into `ingest.py` once per filing, after that filing's own metrics loop completes.
- **Deliberately does not propagate from plain `ANOMALY`** — only from `QUALITY_STRUCTURAL_FAILURE_STATUSES` (today just `IMPLAUSIBLE_SCALE`, a set so a future `UNIT_MISMATCH`/`INVALID_NUMERIC_SCALE` check can join without changing the propagation logic). The real ICICIBANK Q1 FY25 case is exactly why: a genuine single-metric anomaly is signal about that one metric's own history, not proof the whole filing's scale is wrong — propagating from it would have wrongly quarantined ICICIBANK's other real, valid Q1 metrics.
- `_latest_valid_fact_value()` excludes `SOURCE_DOCUMENT_QUARANTINED` the same way it already excludes `ANOMALY`/`IMPLAUSIBLE_SCALE`.
- Retroactive backfill (`scripts/s45b_backfill_document_quarantine.py`) found YESBANK's 8 real trigger documents (the 8 already-flagged `cet1_ratio` rows) and propagated quarantine to 64 real rows (8 documents × 8 other populated metrics each — `gross_npa_pct`, `net_npa_pct`, `roa`, `gross_npa_amount`, `net_npa_amount`, `additional_tier1_ratio`, `interest_earned`, `interest_expended`). No `value` modified anywhere; `car_total`/`provision_coverage_ratio` correctly left untouched (never `POPULATED` in the first place).
- 4 new real DB-backed tests (`test_document_quarantine.py`): propagation from a real structural failure, non-propagation from a plain anomaly (the ICICI case), no cross-document leakage, and the no-document-id guard. Combined suite (`test_document_quarantine.py` + `test_financial_facts.py` + `test_marketripple_score.py`): **25/25 pass**.

**Real re-run, all four owner-requested checks:**

1. **Affected facts disappear from `metrics_used`**: confirmed — YESBANK's `gross_npa_pct`, `net_npa_pct`, `cet1_ratio`, `roa` all moved from `metrics_used` to `metrics_missing`.
2. **Coverage falls substantially, no re-inflation**: confirmed — YESBANK's `coverage_pct` dropped 67.5%→**25.0%** (down from the original pre-S4.5 70.8% too, now honestly reflecting only 3 of 7 metrics being real/usable). YESBANK's own FinStr score correspondingly fell **61.6→56.4** — close to the original, pre-any-fix 52.8, now computed purely from its 3 real yfinance-sourced metrics (ROE, NII growth, Profit growth), with zero contribution from the contaminated filing.
3. **YESBANK disappears from other banks' peer pools too**: confirmed via a direct query — all four fact-metrics now show `peer_pool_size` dropped from 27→26 and YESBANK's own value returns `None`, for every metric, not just CET1.
4. **Original five + outliers move only small, explainable amounts**: confirmed — every other bank's FinStr moved by ≤1.0 point versus the S4.5-A intermediate run (e.g. ICICIBANK 68.5→69.3, KOTAKBANK 71.8→72.8, MAHABANK 83.2→84.1, BANDHANBNK 24.8→24.6), consistent with YESBANK's values shifting out of two more real peer pools (NPA, ROA) on top of CET1 — no discontinuities, no other bank's ranking changed materially.

## Recommendation

**S4.5-A (peer universe/versioning): PASS. S4.5-B (filing quarantine): PASS, verified on real data.** All 8 original items plus the owner's S4.5-B addition are done and confirmed with real data — nothing invented reactively (no NPA/ROA bound was added; the trust boundary is the real document, not a guessed threshold). Per the owner's own gate: **S4.5 CLOSED.** `publishable=False` unchanged throughout. Recommend this now supports a **full GO for S5** publication prep, as previously scoped (single MarketRipple Score display, four pillar sub-scores, evidence-coverage line).
