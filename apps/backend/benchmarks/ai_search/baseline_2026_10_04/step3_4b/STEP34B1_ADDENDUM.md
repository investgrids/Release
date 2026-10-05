# Step 3.4B.1 addendum: two permissive numeric authorization defects closed

Scope: `app/services/ai_search/figures.py` only. No retrieval, sufficiency, provider, Gate B policy, numeric-date or unit-conversion change. Model-free; nothing pushed or deployed.

## Changes
1. **Complete-token numeric matching.** Evidence numbers are extracted as whole tokens and compared by canonical value (commas removed, `%`/sign/trailing dot removed, trailing decimal zeros removed). The old substring test is gone. `18`/`18%` is no longer supported by `2,180`, `2180`, `118`, `180` or `18.5`; `18.5%` is not supported by `18`. No rounding or fuzzy matching.
2. **Bounded word-form percentages.** Only `<number words> percent` / `per cent` (1-99 and "one hundred") is converted to digits, in both the answer and the evidence, and then checked like any other figure. Other word forms (`eighteen basis points`, fractions, compound constructions such as "one hundred and seventy-three point four") are NOT parsed and remain unchecked; this is recorded as `KNOWN_FALSE_ACCEPT` rather than building a parser.

## Preserved (all still pass)
comma normalization, trailing decimal zeros (`1200.5` vs `1,200.50`, `12%` vs `12.0%`), `%` vs `percent` vs `per cent`, Rs vs ₹, `2500MW` vs `2,500 MW`, evidence glued to a prefix (`Rs1,200`), Indian grouping (`1,18,000`), supported date representations, year/fiscal/horizon/single-digit exemptions.

## Results
- Gate suites (3.4A + 3.4B + new boundary fixtures): **144 passed** (previous 128 all still pass; 16 new variant fixtures).
- AI Search regression selection: **427 passed, 2 xfailed, 6 failed**; the 6 are the same pre-existing `test_ai_search_engines_live.py` live_e2e failures. Attributable failures: 0.

## Remaining known limitations (unchanged by decision)
| Case | Direction |
|---|---|
| `01/10/2026` numeric date supported by evidence | false rejection |
| `1.2 lakh crore` vs `120,000 crore` | false rejection |
| Word-form numbers in other units (e.g. "eighteen basis points") | false acceptance (not parsed) |
| Administrative filing cited as a claim source | not blocked by Gate B (left as is, wait for real misuse) |
