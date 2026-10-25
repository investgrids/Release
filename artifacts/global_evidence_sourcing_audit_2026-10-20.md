# Phase 2 — Global Evidence Sourcing Audit (read-only gap report)

*2026-10-20 · worktree `D:\IG-global-markets` · no code changed · a gap report + prioritized remediation plan, NOT an implementation or purchase decision*

## Ingestion inventory (what exists today)

**Providers (`apps/backend/app/providers/`):**
| Provider | Scope | Nature |
|---|---|---|
| `nse_provider`, `bse_provider` | India exchanges | equity quotes + corporate announcements |
| `rss_provider` | **India-only** — 6 feeds: Economic Times, Moneycontrol, NDTV Profit, Business Standard, Livemint, Google News *India* (query literally `"Indian stock market NSE BSE"`) | market news |
| `fed_provider` | **US (global)** — federalreserve.gov press RSS, filtered to `monetary policy` | structured `event_type="policy"` |
| `pib_provider`, `rbi_provider`, `sebi_provider` | India govt / RBI / SEBI | policy/regulatory |

**Macro sources (`services/macro_rates/`):** US Treasury (live ✓), Fed funds (live ✓), RBI WSS (**broken** — separate defect). Feed in-memory state only (persistence unwired — see `macro_rates_defect_2026-10-20.md`).

**Economic calendar (`services/economic_calendar/`):** working sync engine; India-centric events (e.g. India IIP).

## The five questions answered

**1. Which global events / international news are actually ingested?**
Essentially one real global source: **US Fed monetary-policy press releases** (`fed_provider`), plus US rates via macro_rates (in-memory). Everything else is India-scoped — including the Google News feed. **No US/European/Asian equity-market news or events, no international general news, no crypto news.**

**2. Which official macro sources provide usable, timestamped data?**
US Treasury yields and Fed funds (both verified live, timestamped) and the Fed press RSS. India economic-calendar events. **Caveat:** none of the macro-rate *values* currently reach the queryable `macro_releases` table (persistence unwired + RBI parser broken — the separate defect). The Fed press RSS does flow into the normal event pipeline.

**3. What is missing per market?**
| Market | Have | Missing |
|---|---|---|
| **US** | Fed policy RSS, Treasury/Fed rates (in-memory), index *quotes* (Phase 1) | US equity-market news/earnings, CPI/jobs/GDP structured releases |
| **Europe** | index *quotes* only (Phase 1) | **everything else** — no ECB, no European news/events |
| **Asia-Pacific** | index *quotes* only (Phase 1) | **everything else** — no BoJ/PBoC, no Asian market news/events |
| **Crypto** | price/volume *quotes* only (Phase 1) | **everything else** — no regulatory, network/on-chain, or exchange-event ingestion |

**4. Can existing providers/infra fill the gaps (before buying a new provider)?**
Largely **yes, structurally** — `fed_provider` proves the pattern: a free official/outlet **RSS feed → `BaseProvider` → event pipeline**. ECB, BoJ, and major global outlets publish RSS; crypto outlets publish RSS. So new *free* feeds can be added with the existing framework, no paid provider, **subject to three real gates:**
- **RSS cross-source dedup** (`ingestion_dedup.py`) — the standing hard gate before adding feeds; must handle cross-source duplicates.
- **Relevance/entity-linkage** — a global event must connect to Indian instruments to be useful; that relationship layer doesn't exist (the exact gap that kept Phase 1's India implications empty).
- **Macro-rates persistence + RBI parser** must be fixed (separate workstream) for macro *values* to be queryable.

**5. What evidence/provenance is required before claiming a development *caused* a move?**
Four conditions, none fully met today for global→India:
1. A **timestamped event from a verified source** (have this for US Fed + Indian sources; not for EU/Asia/crypto).
2. **Temporal ordering** (event precedes the move) — not currently computed for global→India.
3. An **established, provenanced transmission relationship** — does **not exist** (the graph has no global-index nodes; `ripple_service` links are hardcoded templates). This is the core blocker.
4. **Explicit uncertainty labeling** — the provenance discipline built this month supplies this.
Until #2 and #3 exist, causal claims for global→India are unsupportable — Phase 1's empty-implications stance is the correct default.

## Prioritized remediation plan (no implementation here)

| Priority | Item | Rationale | Depends on |
|---|---|---|---|
| **P0** | Fix macro-rates persistence + RBI parser | makes already-ingested US/India macro *values* queryable | separate tracked defect |
| **P1** | Add ECB + BoJ official RSS via existing `fed_provider` pattern | cheapest real EU/Asia policy coverage, no new provider | RSS dedup gate |
| **P1** | Define the global→India **transmission-relationship + provenance model** | unblocks India-impact and any causal claim; the true gate | design decision |
| **P2** | Add a crypto-news feed (free outlet RSS) for crypto catalysts | enables the crypto "why it's moving" layer | RSS dedup + relevance |
| **P2** | Broaden US coverage (CPI/jobs/GDP structured releases) | completes US macro picture | source selection |
| **P3** | Evaluate a paid/licensed global-news or data provider | only if free feeds prove insufficient AND Yahoo licensing forces a provider change anyway | licensing decision |

## Constraints honored
Read-only; no code changed; both feature flags stay off; macro-rates defects remain a separate workstream; Yahoo licensing remains the public-release blocker. This is a gap report, not a build or purchase.
