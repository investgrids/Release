# Company Signal Semantic Integrity Audit — ICICIBANK (read-only)

Date: 2026-08-25. Follow-up to `company_confidence_provenance_audit_icicibank.md`. Scope: classify ICICIBANK's 103 real `AICompanySignal` rows by role, determine whether "merely a comparison/context entity" signals enter scoring, sample other companies for systemic-ness, and run a read-only counterfactual. **No code or data changed** — every number below is a live query or a re-implementation of the exact existing formula run outside the app.

## Verdict up front

The role-classification framing was right to ask for, and the answer is real — but the actual root cause is sharper and cheaper to reason about than "semantic contamination needs a classifier." **Two of the ~9 real signal-producing pipelines (`comparison_publisher.py`, `signal_publisher.py`) never populate `confidence_score`/`quality_score`/`event_score` on the articles they create.** Every signal born from those two pipelines is *already* mathematically inert in the score formula today (multiplying by a real, stored `0.0` zeroes the row out) — the bug isn't that they're wrongly influencing 56.9, it's that they inflate "103 tracked signals" with rows that contribute nothing, and their real `0.0` confidence values get folded into the 71% average, dragging it down. **56.9 turns out to be closer to reliable than 71% is.**

---

## 1. Every path that creates an `AICompanySignal`

| Producer | Feeds via | Real per-company differentiation? |
|---|---|---|
| `article_generator.py` → 9 real article types (`company_intelligence`, `breaking_intelligence`, `market_wrap`, `morning_intelligence`, `policy_intelligence`, `question_intelligence`, `ripple_intelligence`, `sector_intelligence`, `theme_intelligence`) | `extract_company_signals()` reads `IntelligenceArticle.companies_affected[]` | **Yes, confirmed by direct sampling** — genuinely LLM-authored, per-company reason text even when the trigger is sector/macro-wide (e.g., "Cost-income ratio improved to 38% from 42%," "Healthy CASA ratio and retail-heavy portfolio provide margin stability") |
| `comparison_publisher.py` (`_build_companies_affected`, line 118) | same `extract_company_signals()`, `article_type='comparison_intelligence'` | Real per-entity thesis when the AI Search run produced one; **falls back to the literal string `"Comparison subject"`** when it didn't (5/5 of ICICIBANK's comparison rows hit this fallback) |
| `signal_publisher.py` (`_companies_for_item`, line 130) | same `extract_company_signals()`, `article_type='live_signal'` | **No** — every company in a detected cluster/theme/policy-ripple gets the same generic type label as its "reason" (`"Intelligence Detection"`, `"Policy Intelligence"`, `"Emerging Theme"`, `"Pattern Detected"`), differentiated only by a real per-company impact *direction*, never a real per-company narrative |
| `opportunity_generator.py` (V1, line 358–371) | `extract_opportunity_signals()` reads `OpportunityCompany` | **No** — every company in an opportunity's `companies[:8]` list gets the identical templated `"Directly exposed to {sector} opportunity through core operations."`, differentiated only by list position (`base_score = max(70, score - i*2)`) |

## 2. Role classification of ICICIBANK's 103 real signals

Classified by joining each `article`-sourced row to its real `intelligence_articles.article_type`, then verified against a direct sample of real `reason`/`headline` pairs per type (not inferred from type name alone — one assumption below turned out wrong on inspection, see §4):

| Role (user's taxonomy) | Article/source type(s) | Count | Basis |
|---|---|---|---|
| PRIMARY_SUBJECT | `company_intelligence` | 9 | Articles genuinely centered on ICICIBANK (though 1/9 sampled was a market-wide "Sensex Surges..." roundup — not perfectly pure) |
| DIRECTLY_AFFECTED | `breaking_intelligence`(10), `market_wrap`(9), `morning_intelligence`(7), `policy_intelligence`(19), `question_intelligence`(3), `ripple_intelligence`(2), `sector_intelligence`(4), `theme_intelligence`(10) | 64 | Real, distinct LLM-authored per-company reasoning tied to a sector/macro trigger (RBI policy, Fed decisions, sector earnings) — genuinely about ICICI Bank specifically even when the headline names several banks together |
| DIRECTLY_AFFECTED (opportunity-claimed, templated) | `opportunity` source_type | 10 | Real per-company impact *score*, but identical templated reason text — see table above |
| PEER_COMPARISON | `comparison_intelligence` | 5 | Confirmed: ICICIBANK vs HDFC Bank / Bank of Baroda / Canara Bank — both sides of every comparison get a signal regardless of which one the article concludes is better |
| SECTOR_CONTEXT | `live_signal` | 13 | Cluster/theme/policy-ripple detections — real direction, no company-specific narrative |
| MENTION_ONLY | `educational_intelligence` | 2 | ICICIBANK used as an illustrative example in generic explainer content ("What FII and DII Flows Mean For Nifty 50 and Sensex Investors"), not real news about it |

103 = 9 + 64 + 10 + 5 + 13 + 2. ✓

## 3. Does role currently gate scoring? No — but two roles are already mathematically inert anyway

`compute_company_score()` has no role concept at all; every row of the 103 is summed with equal structural treatment. **But** a direct query of the real stored values shows `comparison_intelligence` and `live_signal` rows carry real, stored `0.0` — not `NULL`, not a neutral default:

```
live_signal (ICICIBANK, 13/13 rows):      confidence=0.0, quality=0.0, signed_magnitude=0.0  — every row
comparison_intelligence (ICICIBANK):      quality=0.0 on every row (confidence real but modest, avg 0.29)
```

Confirmed **platform-wide, not ICICIBANK-specific** — every real article of these two types in the whole database:

| article_type | avg confidence_score | avg quality_score | avg event_score | real rows |
|---|---|---|---|---|
| `live_signal` | **0.0** | **0.0** | **0.0** | 40 |
| `comparison_intelligence` | 0.32 | **0.0** | **0.0** | 78 |
| (every other type, e.g. `company_intelligence`) | 0.88 | 0.97 | 42 | 157 |

Since `weighted = signed_magnitude × confidence × quality × decay × accuracy_multiplier`, a real `0.0` in *any* one factor already zeroes the row's contribution to `56.9` today. `signal_publisher.py` and `comparison_publisher.py` simply never set these fields on the `IntelligenceArticle` rows they create (unlike the 7 other producers, which reliably do) — a data-completeness gap in exactly 2 of ~9 pipelines, not a scoring-logic bug and not something a role taxonomy is strictly required to fix, though the taxonomy in §2 independently confirms these are the right two categories to treat differently.

**What this actually costs**: not a wrongly-inflated 56.9 — these 18 rows already contribute nothing to the sum. It costs (a) an inflated, misleading "103 signals" headline (18 of which are inert), and (b) a deflated 71% confidence average, since 13 real `0.0`s and 5 real `0.29`s are averaged in alongside 85 rows that average `0.84`.

## 4. One concrete contamination case *not* explained by the above

Sampling `sector_intelligence` (kept as DIRECTLY_AFFECTED above, and rightly so for 3 of its 4 rows) turned up a real, specific data-quality problem:

> headline: **"What IT Stock Rally Means For INFY, TCS, HCLTECH Investors"**
> ICICIBANK's reason: **"strong Q1 earnings"**

This article is about IT stocks, names no bank, yet ICICIBANK received a real, non-zero, weighted signal from it. This is a genuine LLM-extraction miss on `companies_affected[]` for that one article, not a pipeline-wide defect — flagging it as a specific, narrow finding worth a targeted look, not something the type-exclusion in §3 fixes.

## 5. Is this systemic or ICICI-specific?

Sampled 5 other real companies for the same two zeroed categories (`comparison_intelligence` + `live_signal`) as a share of their total signal pool:

| symbol | total signals | opportunity-sourced | comparison_intelligence | live_signal | zeroed share |
|---|---|---|---|---|---|
| HDFCBANK | 155 | 20 | 3 | 13 | 10.3% |
| TCS | 47 | 3 | 1 | 7 | 17.0% |
| RELIANCE | 78 | 23 | 0 | 5 | 6.4% |
| TATASTEEL | 10 | 1 | 2 | 1 | 30.0% |
| INFY | 67 | 4 | 7 | 7 | 20.9% |
| **ICICIBANK** | **103** | **10** | **5** | **13** | **17.5%** |

Systemic, ranging 6–30% across a small real sample. Not an ICICI anomaly.

## 6. Read-only counterfactual — real formula, real data, filtered inputs

Re-implemented `compute_company_score()`'s exact arithmetic outside the app (recency half-life 21 days, same real `accuracy_multiplier=1.011` pulled from the live API) and verified it reproduces the live result exactly before trusting the counterfactual:

```
REPLICATED FULL SET (103 rows)              -> score 56.9   confidence 0.71   (live API: 56.9 / 0.71 / 103 — exact match)
COUNTERFACTUAL, exclude comparison+live_signal (18 rows) -> score 58.3   confidence 0.84   n=85
```

**Score barely moves (56.9 → 58.3)** — confirms §3: those 18 rows were already contributing ~zero weighted magnitude, so removing them doesn't meaningfully change the evidence-weighted direction, just cleans the denominator slightly. **Confidence moves substantially (71% → 84%)** — because the blended average was being dragged down by 18 rows of real stored zeros/near-zeros that don't reflect the quality of the other 85 rows' evidence at all.

## Answers to the two questions this audit was asked to resolve

**"Is 56.9 trustworthy?"** — More trustworthy than 71% is, specifically. The score itself isn't meaningfully distorted by peer-comparison/sector-context noise, because that noise happens to already carry zero weight due to the missing-field bug. The number that *is* distorted is the confidence percentage shown next to it.

**"What does the evidence set become without comparison/context signals?"** — 85 real signals (not 103), spanning company_intelligence/breaking/market_wrap/morning/policy/question/ripple/sector/theme_intelligence + opportunity-sourced rows, averaging 0.84 real per-signal confidence — a meaningfully different, more honest headline than "103 signals, 71% confidence."

## What this does not resolve

- Not a recommendation on whether to filter these 18 rows out of `signal_count`, fix the two publishers' missing fields, or both — that's a real decision with tradeoffs (filtering changes what "103" means everywhere this score is shown; fixing the publishers means `comparison_intelligence`/`live_signal` rows would start actually moving the score, not just the count, which is a different behavior change).
- Not a fix for §4's specific cross-sector extraction miss — needs its own look, likely at a broader sample than one row.
- Not a redesign of the confidence-percentage system — that's the separate, already-audited System 2 (`confidence_service.py`) from the prior report, untouched here.

## Your three interim decisions on the 40% engine — noted, not yet implemented

Per your message: don't expose the current 40% as "Confidence" as-is; remove `ai_certainty=6` from any future design; treat missing/weak historical analogy as *not available* rather than negative evidence; stop showing Data Freshness as if it contributes to the 40% when it contributes zero. All four are consistent with both audits' findings and are ready to act on whenever you want to move from audit to implementation — nothing here contradicts them, and nothing here has been built yet.
