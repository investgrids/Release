# Score/Confidence Provenance Audit — ICICIBANK (read-only)

Date: 2026-08-25. Scope: trace the two numbers on ICICIBANK's Company page that are both labeled "confidence" (56.9/71% AI Company Score vs. 40% "Why ICICIBANK Matters Today"), to the exact code and real data producing them. No code changed. All numbers below are live-verified against the real local dev DB (`ig_dev.db`), which reproduces the user-reported values exactly (56.9 / 0.71 / 103 signals; 55 / 40 / 16 / 100 / 60 / 40%).

## Verdict up front

Your hypothesis is correct, and sharper than you knew: this isn't two systems that happen to disagree — it's **three** computations sharing the word "confidence," two of which are structurally unrelated to each other, and the third (the 8-factor engine) has two real consumers where the *same field* (`ai_certainty`) means different things: a genuine LLM self-rating in one, a hardcoded constant in the other. The 40% card doesn't even use real AI self-confidence — it fakes having one.

---

## System 1 — WHY 56.9 (AI Company Score) and 71% (its confidence)

**File**: `app/services/aipe/company_score_engine.py::compute_company_score()` (line 279)

**103 signals** — real, verified via direct query on `ai_company_signals WHERE symbol='ICICIBANK'`: 93 rows from published `IntelligenceArticle.companies_affected[]` entries, 10 from `OpportunityCompany` rows. `signal_count = len(rows)` (line 364).

**Duplicates — mostly clean, one real soft spot found.** No literal duplicate `source_id` rows (the idempotency guard in `extract_company_signals`/`extract_opportunity_signals` — skip if a row already exists for that article/opportunity id — is working, confirmed empty on a `GROUP BY source_id HAVING COUNT(*)>1` query). But of 103 rows only **81 distinct `reason` strings** — real repetition exists:

| reason | count |
|---|---|
| "Intelligence Detection" | 9 |
| "Directly exposed to Banking opportunity through core operations." | 6 |
| "Comparison subject" | 5 |
| "Directly exposed to Technology opportunity through core operations." | 3 |

"Comparison subject" (5×) and the "Technology opportunity" line (3×, on a bank) are worth a closer look separately from this audit — they read like ICICIBANK is being pulled in as a peer-comparison entity in unrelated opportunities' company lists, which would mean some of the 103 "signals" aren't really about ICICIBANK's own news at all. Not confirmed further here; flagging as an open question, not a finding.

**Age spread**: real `signal_at` values range 2026-07-17 → 2026-08-25 (39 days). This is a decayed rolling blend of ~5.5 weeks of coverage, not "today" — the recency half-life is 21 days (line 38), so a 39-day-old signal still carries `0.5^(39/21) ≈ 0.28×` weight, not zero. Worth knowing: "Matters Today" (System 2) and "AI Company Score" (System 1) are answering different time-windows even before you get to the confidence question.

**Score arithmetic** (lines 309–325):
```
weighted = signed_magnitude × confidence × quality × recency_decay(age_days) × accuracy_multiplier
score = 50 + clamp(-50, 50, sum(weighted)/n × 0.5)
```
Real breakdown for ICICIBANK: `raw_total = 1416.3` over 103 rows, `accuracy_multiplier = 1.011` (near-neutral — the historical-accuracy sample is presumably still under `_MIN_ACCURACY_SAMPLE=10` or close to break-even). `1416.3/103×0.5 ≈ 6.9` → `score = 56.9`. Exact match. 52 negative-signed rows vs. 51 positive — near-even split, so 56.9 reflects a thin positive lean, not a strong one. "Mixed" is an accurate characterization of the underlying evidence, not just a UI label choice.

**71% confidence — completely different arithmetic than System 2.** Line 326: `avg_confidence = mean(r.confidence for r in rows)`, defaulting to 0.5 per-row when `r.confidence is None`. Verified directly: `AVG(confidence)=0.7071` over the 103 real rows (range 0.0–0.95). **This is a plain arithmetic mean of 103 independent per-signal confidence values** (each sourced from `article.confidence_score` or `OpportunityCompany.confidence` — themselves upstream LLM/pipeline-assigned per-article confidences), with no relationship whatsoever to the 8-factor engine below. It answers "on average, how confident was the *evidence extraction* for each of the 103 things that went into this score" — not "how strong is the case for ICICIBANK today."

---

## System 2 — WHY 40% ("Why ICICIBANK Matters Today")

**File**: `app/services/company_intelligence.py::compute_confidence_breakdown()` (line 219), wrapping `app/services/confidence_service.py::calculate_confidence()` — an unrelated, general-purpose 8-factor deterministic scorer built for a different original purpose (AI Search query confidence).

Real traced arithmetic, verified against the live API call with the real params the frontend actually sends (`gov_score=60`, `price_positive=true`):

| raw factor (confidence_service.py) | max | real points | how it was reached |
|---|---|---|---|
| `sources` (line 70–72) | 15 | **12** | `source_count=4` (4 real active events, `[0,3,6,9,12,15][4]`) |
| `company_sensitivity` (line 109) | 10 | **10** | `gov_score=60 ≥ 60` → `"high"` |
| `sector_confirmation` (line 113) | 15 | **0** | top event's sentiment wasn't literally `"bullish"` |
| `historical` (line 88–92) | 25 | **3.9** | 1 match, similarity 12.5% → `2 + round(0.125×15,1)=1.9` → `3.9` |
| `market_confirmation` (line 100–101) | 20 | **8.0** | `market_confirming=1` (price up) → `mkt_base=8`, no ≥0.5% move bonus |
| `macro_alignment` (line 119) | 15 | **0** | `macro_aligned=False` — **hardcoded**, line 239 |
| `ai_certainty` (line 126) | 10 | **6.0** | **hardcoded `ai_certainty=6`**, line 240 — not a real rating, see below |
| `volatility` (line 130–132) | −10..+5 | **0** | `vix_level=0.0` hardcoded → `"normal"` regime |
| **total (`final_confidence`)** | ~115, capped 100 | **39.9 → 40%** | `12+10+0+3.9+8+0+6+0 = 39.9` ✓ exact |

The 5 numbers shown next to the 40% headline (`compute_confidence_breakdown`, lines 246–250) are each **independently rescaled to their own max**, which is why they don't average to 40% and why summing them gives a wrong number:

- `evidence_quality = (sources+company_sensitivity+sector_confirmation)/40×100 = 22/40×100 = 55.0%` ✓
- `market_confirmation = 8/20×100 = 40.0%` ✓
- `historical_similarity = 3.9/25×100 = 15.6%` (displays as 16%) ✓
- `reasoning_confidence = 6.0/10×100 = 60.0%` ✓
- `data_freshness = 100.0%` — a real event in `LIVE`/`Developing` lifecycle exists

**Two real, invisible-to-the-user findings:**

1. **`macro_alignment` (0/15) and `volatility` (0, but can be −10 to +5) are full raw components of `final_confidence` that never appear anywhere in the UI breakdown.** A user sees 5 numbers (Evidence Quality/Market Confirmation/Historical Match/AI Reasoning/Data Freshness) and reasonably assumes those *are* the ingredients of the 40%. Two of the real ingredients are invisible; one visible number (Data Freshness) isn't an ingredient at all.
2. **"Data Freshness: 100%" is not part of the `final_confidence` sum.** It's computed separately (line 250, a 3-tier heuristic on event lifecycle) and shown alongside the other four purely as description — it contributes zero points to the 40%. A user could reasonably read "100% Data Freshness" as *helping* the confidence score. It doesn't.

**Your "16% is punishing us for a capability we don't have" instinct is correct on the outcome, wrong on the cause.** The Historical Match engine here is `historical_memory_service.find_similar_events` — an existing, pre-Warehouse historical-analogy matcher, **not connected to the Intelligence Warehouse at all.** It found exactly one real match (Yes Bank's 2020 RBI moratorium, 12.5% similarity — barely above its own `min_similarity=10.0` floor) and that weak match is what produces the 3.9/25 points. So it's not "Warehouse is immature, therefore penalize" — it's "a different, older, unrelated engine found one weak analogy and that gets algebraically summed into the headline number as if it were evidence of *uncertainty*, rather than being flagged as *insufficient basis to compare*." Same underlying architectural complaint you raised, different actual mechanism than you guessed — worth knowing precisely before deciding how to fix it, since "wire in Warehouse" wouldn't touch this specific number at all.

**"AI Reasoning: 60%" is not AI reasoning.** `ai_certainty=6` is a hardcoded constant at company_intelligence.py:240, with its own comment explaining why ("no LLM call to draw from here... rather than a fabricated 'AI said X'"). It will read **60% for every company, every time**, regardless of any actual reasoning quality — the code already tried to do the responsible thing (not fabricate a fake rating) but the result is a number that *looks* measured and sits at the same visual weight as the four real numbers next to it, with nothing distinguishing "this is real evidence" from "this is a placeholder constant."

---

## Why two (really three) systems exist — the actual architecture

`confidence_service.calculate_confidence()` is a single shared 8-factor engine with **two real, independently-fed consumers**:

- `company_intelligence.py` (System 2, this company page) → `ai_certainty` is a **fixed 6/10 constant**, `macro_aligned` is **fixed False**, `vix_level` is **fixed 0.0**. Three of the eight factors are hardcoded placeholders for this consumer, not real signals.
- `ai_search/postprocess.py::compute_confidence_breakdown()` (AI Search's per-query confidence — a different surface, not on this page) → `ai_certainty=int(parsed.get("confidence_self_rating", 5))`, a **genuine LLM self-rating**, plus real VIX/macro signals. Your original worry ("don't let the model's self-rated certainty determine production confidence") is a live, real issue *there* — just not the source of ICICIBANK's 40%.

`company_score_engine.compute_company_score()` (System 1) is architecturally unrelated to either — it never calls `calculate_confidence()` at all. It's a plain mean of per-signal confidences that happen to already exist on 103 independently-scored rows.

So: not two competing opinions about ICICIBANK. Three different questions, two of them answered by an engine three-eighths hardcoded for this specific use, all labeled "confidence" with no visual or textual distinction on the page.

---

## What this does *not* tell us

- Not whether 56.9 or 40% is the "right" number for ICICIBANK today.
- Not a recommendation to match Moneycontrol or any external benchmark.
- Not a proposed fix — per the brief, this stops at provenance.

## Suggested next real step (not started)

Before any formula redesign: decide whether "Why Matters Today" needs its own confidence concept at all, or whether it should either (a) stop showing a percentage next to real evidence-quality numbers it doesn't actually derive from, or (b) be rebuilt on the "how strongly does trustworthy evidence support this" model you sketched — observable properties only (entity correctness, source quality, independent confirmation, freshness, agreement, evidence volume), with `macro_alignment`/`volatility`/`ai_certainty` either wired to real signals or removed rather than left as unlabeled constants. Historical absence should render as *not available*, not as *16%*.
