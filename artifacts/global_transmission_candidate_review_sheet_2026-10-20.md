# Global Transmission Relationships — Candidate Review Sheet (UNSEEDED)

*2026-10-20 · for human sourcing + approval · **zero of these are seeded or approved** · the Brief's India section stays empty until a human adds a real citation and sets `approved=True`*

## How to make a candidate eligible

A row in `global_transmission_relationships` produces a hypothesis **only when ALL hold** (enforced by `is_eligible()` in `services/global_transmission.py`):
`approved=True` · non-empty `citation` (a real source) · non-empty `evidence_basis` · valid `source_factor` · `target_type ∈ {sector, instrument, indicator}` · non-empty `target_key` · `direction ∈ {positive, negative}` (effect on target when source **rises**) · a defined, non-negative lag window (`lag_days_min ≤ lag_days_max`).

And even then, a hypothesis appears only if a **verified, timestamped global observation** for that `source_factor` falls within the lag window. An approved relationship is a *documented potential path*, not proof of any market move.

## Candidates (NOT approved — each needs sourcing + review)

| # | source_factor | direction | target (type / key / label) | lag (days) | rationale (needs a REAL citation) | unresolved questions |
|---|---|---|---|---|---|---|
| 1 | `US_10Y_YIELD` | negative | sector / `rate_sensitive` / Indian rate-sensitive sectors | ? | Higher US yields raise relative attractiveness of US assets → pressure on EM rate-sensitive equities | Which exact sectors count as "rate-sensitive"? Is the effect direct or via FII flows (intermediate node)? Lag evidence? |
| 2 | `DXY` | negative | instrument / `USDINR` / USD/INR | ? | A stronger dollar tends to weaken the rupee, all else equal | Confounded by RBI intervention + oil; is a *direct* DXY→USDINR edge defensible, or only jointly with other drivers? |
| 3 | `BRENT` | negative | sector / `oil_sensitive` / Indian oil-sensitive sectors | ? | India imports most crude; higher Brent raises input costs/margins pressure | Which sectors? OMCs benefit/suffer differently (refining margins) — direction may be sector-specific, not uniform |
| 4 | `US_RISK_OFF` | negative | indicator / `fii_flows` / Foreign portfolio flows | ? | Global risk aversion is associated with EM portfolio outflows | Needs *actual flow evidence* to confirm per episode; "risk-off" itself needs a measurable, timestamped definition |
| 5 | `FED_POLICY` | negative | indicator / `financial_conditions` / Indian financial conditions | ? | Fed tightening can transmit via rates, currency and capital flows | Very broad; likely needs decomposition into the above channels rather than one direct edge |

## Blocking requirements before ANY seed

- **Real citation** per row (RBI/IMF/BIS/peer-reviewed/official — not "textbook").
- **Human review + approval** (`approved_by`, `approved_at`) — the AI cannot self-approve.
- **Lag window** justified per relationship (currently all `?`), with an explicit rule for the trigger source that will populate it.
- Several candidates (#1, #4, #5) likely need **intermediate nodes/channels** rather than a single direct global-factor→sector edge; decide the modeling before seeding.

## Current state

Machinery implemented and tested (eligibility, temporal linkage, isolated table, empty-state). **Seeds: none.** India implications: **empty, by design.** This is the correct, defensible outcome — not an incomplete build.
