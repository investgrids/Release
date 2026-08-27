# Cross-Sector `companies_affected` Extraction Audit (read-only)

Date: 2026-08-25. Follow-up to `company_signal_semantic_integrity_audit.md` §4 (the ICICIBANK-in-IT-article finding). Scope: determine whether that was isolated or systemic, across all 569 real articles / 1167 real (article, company) associations in the dev DB. **No code changed.**

## Verdict up front

**Isolated, not systemic.** Of 1167 real (article, company) pairs, manual verification found **4 confirmed defects across 3 distinct incidents** (~0.34%). The overwhelming majority of what looked suspicious on first pass turned out to be legitimate — real, coherent cross-sector macro reasoning (RBI policy genuinely affects banks *and* NBFCs *and* autos in the same real event; Reliance genuinely has bond, FX, and media exposure alongside its core business). Per your own decision rule — "if isolated, fix the extraction guard; if systemic, add a stronger eligibility gate" — this is the isolated case. A cheap, targeted guard is justified; a new scoring-eligibility system is not, on this evidence.

## Methodology — two proxies, both overstated the problem, corrected by manual review

I want to show this honestly rather than lead with the scariest number: my first automated pass would have badly misled the conclusion if reported as-is.

**Proxy 1 (discarded)**: "does the company's symbol/name literally appear in the article's headline text?" — flagged 625/1167 (53.6%) as suspicious. This number is **not usable**: headlines are demonstrably truncated ("What RBI's Rate Hold Means For SBI, HDFC Bank, ICICI…") and don't list every real company in `companies_affected[]`. Reporting 53.6% would have been a fabricated-by-methodology number, not a real finding.

**Proxy 2 (better, still not the answer)**: flag a company as a "sector outlier" only when its real sector doesn't match *any* other company in the same article, and those other companies unanimously share one different sector. This is a much sharper filter — down to 53 candidates — but still mostly flags **legitimate** cross-sector journalism (an RBI-NBFC article naming banks, autos, and NBFCs together is correct, not an error).

**Ground truth**: manually read all 53 candidates against their real `companies_affected[]` reason text. That's what the verdict above is based on.

## The 4 confirmed real defects

**1–2. Headline/scope mismatch (sector_intelligence, id `f3a165cd…`)** — headline "What IT Stock Rally Means For INFY, TCS, HCLTECH Investors" but the real stored `companies_affected[]` also contains:
```json
{"name": "HDFC Bank", "symbol": "HDFCBANK", "impact": "positive", "reason": "strong Q1 earnings"},
{"name": "ICICI Bank", "symbol": "ICICIBANK", "impact": "positive", "reason": "strong Q1 earnings"}
```
The reason text ("strong Q1 earnings") is real and coherent *on its own* — it just doesn't belong under an IT-only headline. This reads as two real stories (IT rally + bank Q1 earnings) merged during generation, with the headline reflecting only one of them. Not a hallucination — a scope/title mismatch. Both rows carry real, non-zero weight in HDFCBANK's and ICICIBANK's scores (this article type isn't part of the zeroed-field bug from the prior audit).

**3. Unrelated aside (market_wrap)** — headline "Why Banking and Infra Flatness Matters For HDFC Bank, ICICI Bank, and Tata Motors Investors," but `SUNPHARMA` appears with reason "Healthcare sector resilience boosted by strong Q1 results" — a real fact about Sunpharma, with no stated connection to the actual headline topic. Real, non-zero weight.

**4. Symbol/entity conflation (policy_intelligence)** — the clearest, most concrete bug. The same underlying query ("RBI's NBFC Compliance Crackdown…") was generated 4 separate real times (LLM non-determinism / retry). Three times it correctly wrote:
```json
{"name": "PNB Housing Finance", "symbol": "PNBHOUSING", ...}
```
One time it wrote:
```json
{"name": "PNB Housing Finance", "symbol": "PNB", "reason": "PNB Housing Finance is a mid-sized housing finance company..."}
```
`PNB` is Punjab National Bank — a real, unrelated public-sector bank. The LLM wrote the right company name and the wrong ticker. This is a genuine entity-resolution failure at extraction time, and it's real, non-zero weight on the wrong company (PNB, not PNBHOUSING). Same failure class as the earlier-session 3IINFOLTD/IIFL contamination — an LLM producing a plausible-looking but wrong symbol for a real company name.

## What the other ~49 "outlier" candidates actually were (all verified legitimate)

Representative real examples, so the "legitimate" claim isn't just asserted:

- `RELIANCE (Energy)` in an RBI bond-yield article: *"Indirect impact through bond-market yields affecting corporate borrowing costs"* — real, coherent, and honestly hedged ("indirect").
- `INFY/TCS/WIPRO/HDFCBANK/ICICIBANK/SBIN` together in "What RBI's Rupee Defense Means For TCS, Infosys, HCL Tech Investors" — the article genuinely covers both IT (translation/budgeting exposure) and banking (funding costs, FX bond portfolios) sides of one real rupee-stability story; reasons are fully differentiated per company, not copy-pasted.
- `BAJFINANCE/CHOLAFIN/MUTHOOTFIN/PNBHOUSING` all correctly tagged (with real, differentiated NBFC-specific reasoning) on NBFC-compliance articles nominally headlined around banks — my sector-outlier filter flagged these only because "Banking" and "Finance" are separate labels in `_NSE_UNIVERSE`, not because the pairing is wrong.
- `RELIANCE (Energy)` in a media-stocks article: *"Diversified exposure, but media segment impact is marginal"* — real (Reliance does own Network18/Viacom18), and honestly caveated as marginal rather than overclaimed.

## Answering your specific framework

```
IT article        → bank?          CONFIRMED, 1 real incident (2 rows) — headline/scope mismatch, not pure hallucination
Banking article    → IT company?    Checked extensively — always legitimate (real macro linkage, differentiated reasoning)
Energy article      → unrelated financial?   Checked (Reliance/bonds, Reliance/media) — always legitimate
Company article      → unrelated company?     Found via policy_intelligence, not company_intelligence — PNB/PNBHOUSING symbol conflation
Policy article        → legitimate multi-sector exposure?   Overwhelming majority of the 53 candidates — yes, legitimate
```

## Recommendation (not implemented — your call to make)

Per your own branching rule, this is the isolated case, so: **fix the extraction guard, don't build a new eligibility gate.** The specific, cheap, deterministic fix that would catch defect #4 (and similar future cases) without any LLM call or scoring-policy change: when `extract_company_signals()` reads a `companies_affected[]` entry, cross-check the entry's `symbol` against `_NSE_UNIVERSE` and flag/drop it if the entry's own `name` field doesn't reasonably match that symbol's real registered name (e.g., "PNB Housing Finance" should never resolve to symbol `PNB`). This wouldn't catch #1–3 (headline/scope mismatches and unrelated asides aren't symbol errors — the symbols were correct), which are a real but much smaller-magnitude category of "this trigger is thinner than the article's presentation implies," better addressed later as part of your Evidence Confidence work (contradiction/relevance signals) than as an urgent standalone fix.

## What this does not resolve

- Doesn't change the prior audit's 18-inert-row finding or its recommendation.
- Doesn't fix anything — read-only per your instruction.
- Doesn't claim 0.34% generalizes precisely to the full production dataset (this is the dev DB); worth a lighter recheck against production before treating the rate as final, though the *mechanism* (headline/scope mismatch during generation; occasional LLM symbol/name conflation) is a code-level property that would reproduce there too.
