# B.5 — RSS Entity/Event Linkage: Design + Real Benchmark (Gate 1 only)

**Date:** 2026-08-30
**Scope:** design + measure Gate 1 (entity linkage) against the real, full 594-item RSS `RawEvidence` corpus on `integration/warehouse-company-master`. Gate 2 (event-specific evidence matching) is designed but **not implemented or tested** in this pass — explicitly deferred, per the two-gate architecture. No production code touched, no mass backfill, no Article V2 wiring.
**Branch:** `D:\ig-integration-wh-cm`. Scripts: `scripts/b5_entity_resolver.py`, `scripts/b5_dump_full_results.py`, `scripts/b5_dump_unlinked_sample.py`.

## Method

Gate 1 was built as real code (not a spec document) implementing exactly the required rules: explicit NSE symbol, exact canonical company name (legal-suffix-stripped), exact known alias (`CompanyAlias`, real/sourced, never fuzzy), multi-company allowed, ambiguous identifiers (colliding across 2+ real entities) dropped entirely rather than guessed. Real universe: 2,557 companies, 3,053 aliases.

Run against the real, full 594-item RSS corpus, **not a cherry-picked subset**. Every single-match result (97 items) was individually hand-reviewed against its real title+summary — a full census of that bucket, not a sample. A further 40-item real sample of the 439 unlinked items was reviewed for missed links (recall). Multi-entity matches (59) were spot-checked (~15).

## Three real iterations — the process itself is the finding

**v1** (case-insensitive symbol matching): 188 single, 96 multi. Immediate, serious false positives on real data: `oil`→Oil India, `dollar`→Dollar Industries, `retail`→a real company alias, `worth`→another alias, `Shah`→a company colliding with the surname "Shah" in "Devang Shah"/"Sudeep Shah". Root cause found and fixed: **symbol matching must be case-sensitive** — real financial journalism prose essentially never writes a bare ticker in lowercase; case-insensitivity is what let ordinary English words through.

**v2** (case-sensitive symbols + v1's stoplist): 97 single, 59 multi. New false-positive class surfaced: short/generic real company **names** (not symbols) — `take`→Take Solutions, `total`→a real alias, `race`→a real alias, `shree`→a real alias, `rishabh`→matched a cricketer's first name ("Rishabh Pant"), not the company. Fixed via targeted stoplist additions.

**v3** (final, this report's numbers): still surfaced `persistent`→Persistent Systems (in "persistent global uncertainties") and `deep`→Deep Industries (in "deep gorge", a bus-accident story) on a fresh, independent sample. **This is the real, load-bearing conclusion of the iteration process**: a manually-grown stoplist converges slowly and will keep finding new common-English-word collisions indefinitely. A production version needs a systematic fix (a real English-frequency/dictionary filter, or a stricter multi-word-only rule for name matches), not more one-off additions — recorded as a requirement below, not solved here.

## Real Gate 1 precision (v3, full census of the 97-item single-match bucket)

| Outcome | Count | Rate |
|---|---|---|
| Correct entity links | 75 | 77.3% |
| Wrong entity links | 22 | 22.7% |
| Missed valid links (0 clear misses in a 40-item real recall sample of the 439 unlinked items) | 0 clear | — |
| Correctly unlinked items | high (40/40 sampled correctly excluded; 2 were pre-IPO companies not yet in `CompanyEntity` — a real data-model boundary, not a resolver bug) | — |
| Multi-entity completeness | **partial misses observed** — see below | — |
| Correct event/evidence matches (Gate 2) | **not tested** — Gate 2 not built this pass | — |
| Wrong-event matches (Gate 2) | **not tested** | — |

**594 total real RSS items**: 439 unlinked (73.9%), 97 single-entity (16.3%), 59 multi-entity (9.9%).

## Real false-positive taxonomy (5 distinct classes, all found in real data — not hypothesized)

1. **RSS-aggregator source-name collision** (7 of 22 false positives): titles carry a `"... - NDTV"` / `"... - Groww"` suffix identifying the *publisher*, and NDTV/Groww happen to also be real listed companies. The match fires on the byline, not the subject. Example: `"Tempsens Instruments Shares Make Bumper Market Debut... - NDTV Profit"` matched "NDTV" — the story is about Tempsens, not NDTV.
2. **Generic English word coinciding with a short real company name/alias** (10 of 22): `persistent`, `deep`, `rain`, `spectrum`, `clean`, `advance`, `suraksha`, `affordable`, `gopal` — each a real company/alias fragment that also reads as ordinary prose.
3. **Substring-within-a-different-real-proper-noun** (2 of 22): `"Bank of India"` (a real, specific PSU bank) matches inside `"Reserve Bank of India"` (the central bank/regulator — an entirely different institution); `"Stanley"` (a real Indian company) matches inside `"Morgan Stanley"` (an unrelated global bank).
4. **Generic-institutional-name ambiguity** (2 of 22): `"Indian Bank"` is both a real, specific PSU bank's exact legal name *and* an everyday English phrase — `"Indian bank stocks show widest exchange price gap"` means "stocks of Indian banks" generically, not news about the company Indian Bank specifically.
5. **Unverifiable from truncated review text** (1 of 22): one match (`CDSL`) could not be confirmed or refuted from the visible title+summary alone.

**Real, honest recall finding** (multi-entity completeness): several genuinely multi-company real stories only had *some* of their companies caught — `"Balrampur Chini, Dhampur Sugar, Uttam Sugar Mills rally..."` matched only Uttam Sugar Mills (the other two appear without their full legal-suffix-stripped form in this exact phrasing); `"LIC, Indian Overseas Bank among 10 stocks..."` matched only Indian Overseas Bank (LIC's real matchable name/alias didn't fire); `"Indian Hotels Shares Fall... Oriental Hotels Jump"` matched only Oriental Hotels (Indian Hotels Company Limited's suffix-stripping left a 3-word core name that doesn't match the shortened "Indian Hotels" phrasing actually used). Root cause: legal-suffix stripping is single-pass, not iterative, and headline-style company references are often shorter than the full registered name.

## What this means for the acceptance bar

The owner's hard rule was **zero known wrong-event matches** in the labeled set. This benchmark only measured **Gate 1** (entity linkage); Gate 2 (does the matched entity's real Warehouse NSE evidence correspond to the SAME event as the RSS item) was designed but not built or tested this pass. Even so, **Gate 1 alone already shows a real 22.7% wrong-entity rate on its single-match bucket** — well short of what a Gate 2 pass could safely inherit, since Gate 2 can only be as reliable as the entity it's given. **This benchmark's real conclusion is that B.5 is not ready for a controlled backfill or any Article V2 wiring yet** — confirming, with real measured evidence rather than caution alone, the owner's own instruction not to proceed until precision is much higher.

## Real requirements for the next B.5 iteration (derived only from what this benchmark found)

1. **Strip or ignore RSS aggregator source-name suffixes** (`"... - NDTV"`, `"... - Groww"`, `"... - livemint.com"` etc.) before running entity resolution — closes false-positive class 1 entirely (7 of 22 = the single largest class).
2. **Replace the manually-grown stoplist with a systematic common-word filter** (a real English-frequency wordlist, or requiring multi-word phrase matches as the default for company *names*, reserving single-word matches for symbols only) — the v1→v2→v3 iteration itself proved ad hoc stoplist growth doesn't converge.
3. **Add proper-noun collision guards** for substring cases (`"Bank of India"` inside `"Reserve Bank of India"`; `"Stanley"` inside `"Morgan Stanley"`) — likely a negative-lookbehind/lookahead rule for specific known institutional phrases, or a rule that a matched company name must not itself be a strict substring of a longer, more common real institutional/proper-noun phrase.
4. **Make legal-suffix stripping iterative and headline-aware** — closes the real multi-entity-completeness misses (Balrampur Chini, LIC, Indian Hotels).
5. **Build and test Gate 2** (event-specific evidence matching) against real Warehouse NSE evidence for the entities Gate 1 *does* correctly resolve — not started this pass.
6. **Re-run this same benchmark methodology after 1-4 are built**, before considering any backfill — the real precision number, not an assumption, should decide readiness.

## Explicitly not done in this pass

- No Gate 2 implementation or testing.
- No `EvidenceEntityLink` rows written for RSS evidence — zero backfill, exactly as instructed.
- No Article V2 wiring to RSS evidence.
- No materiality scoring, article generation changes, title/SEO work, or FinancialFact selection changes — B.5 stayed scoped to identity + event linkage only, per instruction.
