# Step 3.3b: Gemini-only qualification. Result: 1/3, STOP; plus a serious integrity defect on the one real answer

2026-10-04 (about 19:10 IST), `release/ai-answer-v2` at a871a8d prompts and contracts. Gemini `gemini-3.6-flash` only, production credential through `railway run`, environment scrubbed to the Gemini key before the app loaded (database, Redis, admin key and every other production value never reached the process), 3 specialist requests maximum, no classifier call, no retry, no fallback, not a production user query. Nothing changed in code, prompts, retrieval, timeouts or cooldowns. Not pushed, not deployed. The 18-question run was **not** started. No credential in any artifact.

## Result
| Question | Request (est. input / output cap) | Outcome | Structured output | Final state |
|---|---|---|---|---|
| CR2 3M India | 2,566 input tokens (actual) / 6,500 | **HTTP 200**, 21.5 s, finish `stop`, 2,405 completion tokens, 5,951 total | parsed | real answer |
| EI1 BEL order | ~2,444 / 6,500 | **HTTP 429 RESOURCE_EXHAUSTED** after 1.2 s | none | degraded (capacity) |
| CC1 TCS vs Infosys | ~3,064 / 7,000 | **HTTP 429 RESOURCE_EXHAUSTED** after 1.2 s | none | degraded (capacity) |

**Gemini full specialist successes: 1/3. Specialist requests made: 3 of 3.** Branch per the plan: do not run the 18; determine why the failed requests differ.

## Why the failures differ (quota, not request size)
- Both refusals carry the same provider text: "You exceeded your current quota ... Quota exceeded for metric: <name redacted>, **limit: 20**, model: gemini-3.6-flash. Please retry in **10h20m**". Same limit, same model, retry window counting down between the two (10h20m10s to 10h20m0s). A 20-request allowance with a 10-hour retry is consistent with a daily per-model free-tier quota; **my sanitizer redacted the metric name, so "per day" is inferred from the 10-hour window, not read literally**.
- Not size: CC1's request was larger than CR2's yet was refused in 1.2 s, before any generation; CR2's real-size request (2.6K in, up to 6.5K out) completed.
- Not timeout, safety refusal, JSON failure or schema problem: those did not occur (the one answer parsed).
- Production implication (hypothesis, not proven): the production Gemini key hit a 20-request allowance for this model the same day. The service's own comments describe Gemini as a "1,500 req/day" workhorse; that matches older models, not `gemini-3.6-flash` at the limit observed here. `gemini-3.5-flash-lite` (the second Gemini model) was deliberately not tried, so its allowance is unknown.
- Latency note: CR2 took 21.5 s for 2,405 output tokens (about 110 tokens/s) against the app's 30 s read timeout. A longer answer (CC1 allows 7,000 output tokens) would probably exceed 30 s on this model and be cut by the timeout. One sample; hypothesis.

## The one real answer: CR2 "How is 3M India doing as a business?" (bundle: 0 events, news, announcements, policies; only a market-wide context line)
**Verdict: serious integrity defect. It answers confidently from nothing MarketRipple holds.**
- **No admission of missing evidence.** The answer states "continues to demonstrate strong operational performance", "zero-debt balance sheet", "superior return capital metrics", "premium valuation multiples", "healthy margins supported by industrial tapes, automotive adhesives, and medical solutions", names peers (Honeywell Automation India, Siemens) and gives a **"Constructive / bullish"** verdict (confidence 21.3, labelled Low). The gate's honest-insufficiency check for an empty bundle: **FAIL** (states insufficient evidence: no; 16 of 17 factual-looking claims unsupported).
- **Invented specifics.** Two earnings-release dates in the timeline (10 Nov 2026 "Q2 FY27 Earnings Release", 12 Feb 2027 "Q3 FY27") with no calendar behind them (the codebase documents that no company earnings-date source exists), and scenario figures: "volume growth exceeds 18% YoY", "gross margin expansion above 200 bps", "10-12% top-line compounding". The gate flagged 8 numbers; 2 of those (85, 82) are the model's own confidence scores in the JSON, a gate artifact, so 6 are real.
- **Claim-source contract ignored.** The model returned `claim_sources: []` (an empty list) while stating 17 factual-looking claims. The pipeline reported `claim_validation: not_provided`. So `claim_sources` could not protect against this; its first live outcome is "the model did not use it".
- Confirmed in the prompt text: the company specialist tells the model to "use real NSE symbols, actual rupee amounts, and genuine Indian market context throughout", and nothing tells it what to do when the evidence lists are all "None". Whether that wording is the cause is **inference**: the details match real 3M India facts (segments, peers), so the model most likely answered from its own knowledge, presented as current fact with no source and no date.
- Not checked on this question: premise (not applicable), score references (none stated), citations (the response lists none because none exist).

## Not reviewable
EI1 (BEL premise) and CC1 (first real test of `claim_sources` on a rich bundle) produced no answer, so the plan's other two inspections could not be done.

## Decision
- Stop (1/3). Do not run the 18-question benchmark.
- A serious integrity defect exists independent of provider capacity: **for a company question with no evidence, AI Search V2 currently produces a confident, specific, unsourced analysis including invented dates and figures.** This is a design defect in how the pipeline and prompt treat an empty or insufficient bundle and in the claim-source contract's lack of enforcement, not a quota issue.
- Candidate next task (not started, needs your go): **zero-evidence and unsupported-premise handling**, designed from this one answer and the Tera/BEL findings: decide deterministically, before any model call, when a company or event question has too little relevant evidence to analyse, and answer with an honest insufficient-evidence response instead (this also saves quota); enforce a non-empty `claim_sources` or reject/flag answers that state facts without it; and re-qualify. The questions to settle first are what a "sufficient evidence" threshold is per question type, and what the user sees instead of an analysis.
- Separately, as agreed: **benchmark capacity needs its own accounts** (production's Groq, OpenRouter and Gemini free tiers are shared and nearly empty), and the pipeline's 5-token classifier is incompatible with reasoning models (provider-efficiency debt). Neither is touched here.

Files: `qualify_gemini.py`, `gemini_qualification.json` (per-request diagnostics, raw model output, response, evidence snapshot).
