# Company Redesign — Batch 4: Ripple + Peers

Date: 2026-08-25
Branch: `company-identity/c1-reconciliation` (worktree `D:\ig-company-identity`), commit `105c456`
Scope: real graph-evidence Ripple tab; Peers confirmed compliant with real-comparison-fields-only.

## A real discrepancy found before any implementation

The owner's original instruction named `/api/ripple/company/{ticker}` as "the real company Ripple endpoint." Tracing it end to end (`app/api/ripple.py` → `app/services/ripple_service.py`) found it is not real graph evidence: it first tries an LLM call (`generate_ripple_graph`) that invents nodes/edges/strength/direction from a text prompt, and on failure falls back to hardcoded per-sector templates (`_geopolitical_template`, `_energy_template`, `_monetary_template`, etc.) — the same "sector-template data, not company data" pattern Batch 0 already removed elsewhere on this page. Every result is tagged `source: "ai_generated"` or `"fallback_template"` in its own DB row. This was surfaced to the owner before any code was written; the owner's explicit decision (recorded in the conversation) was **Option B**: use the real, evidence-only Intelligence Graph traversal (`get_subgraph`, already proven and used by `coherence.py`) instead, accepting real coverage sparsity over an always-populated but often-invented graph.

## What shipped

- **New `app/services/company_identity/graph_ripple.py`.** `get_company_ripple(db, raw_symbol, hops)`:
  1. Resolves the raw symbol through the same real Company Master resolver every other Batch 0-3 read path already uses (`resolve_entity_by_any_symbol`) — protects the TATAMOTORS/TELCO → TMPV class of cases from the start, not as an afterthought.
  2. `resolve_company_graph_node()` finds the real `IGNode` (if any) representing that entity, reusing `coverage.py`'s own `node.ticker → resolve_identifier` matching pattern. When more than one node resolves to the same entity (a real pre-C3-merge duplicate), picks the richest by real edge count — the same tie-break `graph_migration_executor.py`'s `_choose_canonical()` already uses.
  3. Calls the real, already-proven `intelligence_graph_service.get_subgraph()` BFS. No generation, no templates, anywhere in this path.
  4. Returns one of four real states: `no_entity` (symbol doesn't resolve to a real Company Master entity), `no_node` (real entity, no Graph node), `no_edges` (real node, zero real relationships), `has_edges` (real evidence exists) — never collapsed into one generic empty message.
- **New `GET /api/companies/{symbol}/ripple`** in `app/api/companies.py`, alongside the existing `/tier` endpoint.
- **New `RippleTabBody`** (replaces Batch 1's honest placeholder in `CompanyPageClient.tsx`). Fetches only while the Ripple tab is mounted — confirmed live via a real Playwright network listener that zero `/ripple` requests fire on initial page load, and the fetch only fires after clicking into the tab, satisfying the owner's explicit performance requirement that Ripple not weigh down the initial experience. Renders a compact list (top 8 real relationships by real weight) showing only fields genuinely stored on the real edge — `edge_type`, `weight`, `confidence`, `lag_days`, `description`, `source_event`, and real `source`/`target` direction — never a derived label like "Strong relationship" or "87% impact" the stored model doesn't actually support. "Explore full graph" links to the existing real `/graph` explorer rather than adding a second in-page graph-visualization library (reactflow was already removed in Batch 0; no graph-viz weight was added back). Three distinct honest empty/error states matching `graph_ripple.py`'s real states, plus a fourth for a genuine fetch failure.
- **Peers tab: reviewed, no changes needed.** `PeerComparison` and `CompareWithSection` were checked line by line and confirmed still compliant with Batch 0's cleanup — only real `symbol`/`name`/`price`/`pe`/`roe` fields (from `stock.peers` + live `/api/stocks/{symbol}` fetches) and real published-comparison-article links. No similarity percentage, no growth column, anywhere.

## Tab visibility decision

The owner's own guidance (via the ChatGPT-relayed decision) framed "keep the Ripple tab always visible with an honest empty state" as the primary preference and "hide the tab entirely for very sparse Tier C companies" as an acceptable-but-secondary alternative. Implemented the primary preference only — the tab is always present, and the four real states (including the two empty ones) are what teach a user what "Ripple" means on this page, per the owner's own reasoning ("avoids tabs appearing/disappearing unpredictably"). Did not add the secondary tier-conditional hiding, since it was explicitly optional and would have required fetching tier data at the page-shell level purely to gate tab visibility — real added complexity for something framed as a nice-to-have, not a requirement.

## Verification (real data, real browser, real tests)

- `tsc --noEmit`: clean, 0 errors.
- New `tests/services/test_company_ripple.py`: 6 real DB-backed tests — `no_entity`, `no_node` (a real fixture entity, AUROPHARMA, with no Graph node), `no_edges` (a real node with zero edges), `has_edges` (asserts every real edge field — `edge_type`, `weight`, `confidence`, `lag_days`, `description`, `source_event` — passes through unchanged, proving nothing is recomputed or invented), the richest-node tie-break, and the real TELCO → TATAMOTORS → TMPV historical-alias chain resolving to the correct graph node. Run alongside the existing `company_identity` suite: 43/43 pass.
- Live curl + Playwright pass against the real, safely-copied dev DB:
  - RELIANCE: `has_edges`, 17 real relationships, real edge types (`influences`, `benefits`, `hurts` all observed, not a single repeated value), real weight/confidence percentages, real event/development node labels.
  - TELCO: correctly resolves to `canonical_symbol: "TMPV"` and the real graph node `company:tatamotors`.
  - GOLDENTOBC: `no_node`, honest empty state renders (a first Playwright pass with a 2s wait produced a false negative purely from React hydration/fetch timing on a cold navigation — re-verified with a longer wait and response logging, confirming the real fetch returns 200 and the empty state renders correctly; not a code defect).
  - Confirmed live: 0 `/ripple` network requests on initial Overview-tab page load; the request only fires after clicking into the Ripple tab.

## Explicitly not done in this batch

No general graph-visualization work (deliberately deferred to the existing `/graph` explorer rather than duplicated here). No tier-conditional Ripple tab hiding (optional, not implemented — see above). Batch 5 (full-system verification across 5 real company profiles, desktop/mobile, accessibility, performance gate) is next.
