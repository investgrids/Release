# SR2 single live call on the titles-only contract (after 3.4G.1 ranking, 3.4G.2 visibility, 3.4G.3 cold-start fix)

Artifact: `../step3_4c/openai_sr2_g4.json`. `gpt-6-luna`, 1 request, HTTP 200, no retries, prompt/gates/retrieval unchanged. No key in the artifact. Nothing pushed or deployed.

## Result: withheld by Gate B, and thin even if it had been authorized
| Measure | Value |
|---|---|
| Gate A | sufficient (sector assessment) |
| Gate B | **rejected**: `claim_not_in_answer`, `uncovered_factual_sentences` (4 factual sentences) |
| Tokens | 2,312 prompt + 4,014 completion (3,335 reasoning) = 6,326 |
| Latency | **44.3 s** (above the 30 s production timeout) |
| OpenAI window left | about 47,750 of 100,000 tokens |

## What the model saw (visible evidence)
Events E1-E6 include "**Nifty IT crashes 11% in September**" (E3), the Accenture read-through items (E1, E4, E6) and "Nifty IT jumps 2%" (E5). News N1-N5 include "IT Q2 Preview: From Revenue To Margin Outlook...", "**Accenture's Growth Beat Sparks Rally, But Street Divided On Indian IT's Fortunes**" (N3) and "Weekly Market Wrap... IT indices fall 4%" (N5). Plus the live sector rows. The strong evidence was selected and visible.

## What the model wrote (rejected generation)
Summary: the headlines "link Indian IT share moves to Accenture earnings and forecasts and highlight Q2 results expectations"; the evidence "does not establish actual operating results or a full-year IT-services outlook". Bottom line: "A forward outlook for IT services cannot be established from the available evidence." One key driver (Accenture read-through) and one risk (no Q2 results or sector forecast). **It does not mention the 11% September decline, the rally magnitudes, the weaker-growth or "Street divided" caution, or any sector move.** It cites seven items in one vague claim.

## Why Gate B rejected it (validators unchanged, run on the saved generation)
1. **Model contract (correct rejection):** the model listed the claim "IT was flat at +0.0% over one day, compared with FMCG at +1.3% and Banking at +0.2%" but never wrote that sentence in the answer (`claim_not_in_answer`).
2. **Detector false positives on limitation sentences (two new variants of the earlier classes):**
   - "The available evidence does not establish actual **Q2** operating results or a full-year sector forecast." is read as factual because of the digit in the fiscal label "Q2". The figure check already exempts fiscal labels (Q1-Q4, FY, H1); the factual-sentence detector does not.
   - "A forward outlook for IT services cannot be established from the available evidence; **it** does not include reported operating results." The second clause's subject is the pronoun "it", so the evidence-absence frame (which needs an evidence noun in the clause) does not match, and "reported" counts as an event verb.
   Without those two, only the unlisted-claim problem would remain, so a fixed detector would still not authorize this specimen.

## Verdict on the experiment
**Not useful from titles alone; but titles are not the cause.** The strong, specific headlines were visible and well ranked, and the model still produced a generic "cannot be established" answer that ignores them. So the thinness is a composition behaviour, not an information shortage: the headline facts (11% September fall, Accenture rally, "Street divided", weaker growth) were available to state as sourced claims and were not. A grounded-snippet experiment would add text the model would probably also decline to use, and would enlarge the authorization surface and cost (this call already took 44 s and 6.3K tokens). I do **not** recommend snippets yet.

Likely contributors (hypotheses, not proven by one call): the canonical-claim and "state only what the evidence supports; no verdict" rules, combined with a gate that withholds the whole answer for any uncovered factual sentence, push the model toward a minimal, hedged claim set; and a reasoning model spends most of its budget deliberating (3,335 reasoning tokens, 44 s) before writing a very short answer.

## Candidate next steps (none started; choose one)
- **A. Composition contract (prompt only, model-free first):** ask for the 3-5 most informative facts stated by the strongest visible headlines as individual verbatim claims ("Headline E3 reports a Nifty IT fall of 11% in September"), then one hedged synthesis sentence; run a model-free prompt inspection and at most one more call.
- **B. Detector fixes first (narrow, adversarially tested):** treat fiscal labels (Q1-Q4, FY, H1/H2) like period labels in the factual-sentence test, and let a pronoun-subject clause that directly follows an evidence-absence clause in the same sentence count as part of it. Needed regardless, because limitation sentences will keep hitting them.
- **C. Latency:** 44 s exceeds the production timeout; reasoning budget and output length need attention before this model could serve live.

Snippets stay parked until a specimen shows thinness with the strongest evidence visible and the composition contract already tightened.
