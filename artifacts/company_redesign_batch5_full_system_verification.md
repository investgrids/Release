# Company Redesign — Batch 5: Full-System Verification

Date: 2026-08-25
Branch: `company-identity/c1-reconciliation` (worktree `D:\ig-company-identity`), commit `445f54b`
Scope: test the complete Company experience as one system, per the owner's exact checklist — 5 real company profiles, desktop+mobile, tab URL/back-forward, canonical redirects, metadata/JSON-LD, empty states, real cross-entity links, accessibility, median-of-3 performance gate.

## The 5 real profiles used

| Profile | Symbol | Real evidence |
|---|---|---|
| Rich company | RELIANCE | 76 AICompanySignal, 17 real graph relationships, Tier A |
| Moderate company | TCS | 45 AICompanySignal, 7 graph edges, 1 V2 opportunity link, Tier A |
| Newly qualified Tier A | GARFIBRES | 1 AICompanySignal, 5 graph edges — a real company that only qualifies via C4's dynamic evidence gate, not the old static universe |
| Renamed/alias company | TELCO | Real NSE rename chain TELCO → TATAMOTORS → TMPV |
| Sparse Tier B/C | GOLDENTOBC | 0 AICompanySignal, 0 graph edges, real live market data only |

## Findings, by checklist item

**Tab URL/back-forward** — verified on all 5 profiles (desktop): clicking every one of the 6 non-Overview tabs updates the URL with the correct `?tab=` param; real browser back/forward correctly replays tab history. No issues found.

**Canonical redirects** — TELCO still issues a real `308 Permanent Redirect` to `/companies/TMPV` (explicitly re-verified via a raw header check, not just the final destination URL, since Playwright's `page.goto` follows redirects transparently and could otherwise mask a wrong status code).

**Metadata/JSON-LD** — all 5 profiles: real per-company `<title>`, real `rel="canonical"` pointing at the canonical symbol, 9 real JSON-LD blocks present on every profile, `robots` correctly omitted (indexable) for all 5 since all 5 are Tier A/B.

**Empty states** — GARFIBRES and GOLDENTOBC (the two sparse profiles) were checked across every tab. Both correctly show real data where real evidence exists (e.g., GARFIBRES's Intelligence tab shows its 1 real AICompanySignal; its Ripple tab shows its 5 real graph edges) and an honest empty-state message where it doesn't (GARFIBRES's Events/Opportunities tabs; GOLDENTOBC's Intelligence/Opportunities/Ripple tabs). No tab was found rendering blank or fabricating filler content in either direction.

**Real cross-entity links** — from RELIANCE: the Events tab's first real event link (`/events/rupee-logs-weekly-decline-with-rbi-intervention-curbing-losses`) was clicked through with a strict `waitForURL` assertion and confirmed to land on the real event page; the Opportunities tab's first real opportunity link (`/opportunity-radar/25`) was confirmed to resolve with a real `200`. Ripple's real evidence and its `/graph` link were already verified in Batch 4. (One transient false alarm during this check — a looser click-then-fixed-wait test script raced the client-side navigation and read the URL before it settled; re-verified with `page.waitForURL()` and confirmed the real click-through works correctly. Recorded so a future test script doesn't repeat the same race.)

**Mobile** — RELIANCE and GOLDENTOBC checked at a 390px viewport: no horizontal page overflow on any tab including the new Ripple/Peers tabs (`document.body.scrollWidth === document.documentElement.clientWidth` held in every case), tab strip remains horizontally scrollable, tab URL updates correctly on mobile too.

**Accessibility** — a real `@axe-core/playwright` WCAG2A/AA audit (not a hand-rolled check) across 4 real pages (RELIANCE overview/intelligence/ripple, GOLDENTOBC's empty-state Opportunities tab) found 3-4 violation types per page: `button-name` (critical), `color-contrast` (serious), `link-name` (serious), and `nested-interactive` (serious, Intelligence tab only). Traced every violation to its actual source: the icon-only header buttons and the "/" logo link (both in the global `SiteHeader`, unrelated to any Company page code) account for `button-name`/`link-name`/most `color-contrast` instances; `nested-interactive` traces to `components/intelligence/IntelligenceBlock.tsx`, a pre-existing shared component this batch imports but never authored or modified. **None of the violations originate from Batch 0-4's own new code** (the tab strip, `OverviewGrid`, `CompanyScoreContributors`, `RippleTabBody`, `RelatedOpportunitiesList`, `EventsTabBody`). Real, worth fixing eventually, but it's global/shared-component debt, not something to fix inside a Company-page-specific redesign batch — would need a separate, broader pass touching `SiteHeader` and `IntelligenceBlock` (which other pages besides Company also use). Keyboard reachability of the new tab strip itself was confirmed separately: 7 real `<button>` elements, natively focusable, no custom ARIA needed since they're semantic buttons.

**Performance — median-of-3 gate.** Ran the established methodology (real production build, not dev mode) in an isolated git worktree (`git worktree add --detach`) specifically to avoid the documented incident where a `next build` against a live dev server's shared `.next` directory corrupted it — the isolated worktree shares the same commit history but a fully separate `node_modules`/`.next`, so the live local server the owner is using was never touched. Built, started on an unused port, warmed up, then 3 real Lighthouse runs against `/companies/RELIANCE`:

| Run | Performance | LCP | TBT | CLS |
|---|---|---|---|---|
| 1 | 73 | 3746ms | 452ms | 0.000 |
| 2 | 87 | 3789ms | 98ms | 0.000 |
| 3 | 88 | 3703ms | 101ms | 0.000 |
| **Median** | **87** | **3746ms** | **101ms** | **0.000** |

Real production bundle size for the Company route: **20.9 kB** route-specific JS, **187 kB** First Load JS (including shared chunks) — from the build's own output, not estimated.

CLS is perfect (0.000) across every run — no layout shift from the tab architecture. TBT is low (101ms median) once past a noisy first run (the same repeated-run variance this session's own established methodology memo already documented and is why median-of-3 exists, not single-run numbers). **LCP (~3.7s) is a real, worth-noting number, but traced to its actual element**: Lighthouse's own `lcp-breakdown-insight` audit identifies the LCP element as the server-rendered SEO description paragraph in `page.tsx` (`<p class="mt-1.5 ...">`), not anything in the client-rendered tab UI Batches 0-4 built — with `elementRenderDelay` (1295ms) dominating over `timeToFirstByte` (73ms, fast). This points at general page-load/hydration-blocking characteristics of the route as a whole, not the new tab/Ripple architecture specifically. An initial dev-mode (unoptimized `next dev`) Lighthouse pass was also run first and discarded from the final numbers above — it showed extreme run-to-run TBT variance (3.2s-15.5s) purely from dev-mode overhead (unminified React, no production bundling), which is why the production-build re-measurement was done instead of reporting those inflated numbers.

**Ripple-tab weight — the owner's specifically flagged risk, measured precisely.** Real Playwright network-response tracking (not Lighthouse) on RELIANCE's Overview-tab initial load vs after opening the Ripple tab: opening Ripple adds exactly **1 new network request** and **0 new JS chunks** — confirmed via a direct `curl` of the real ripple API response that its actual payload is **8,430 bytes**. The tab architecture's lazy-mount-on-open behavior (established in Batch 1, reused unchanged for Ripple in Batch 4) delivers exactly the outcome the owner asked for: the Ripple tab's real cost is paid only when a user actually opens it, and that cost is a single small JSON fetch with zero additional JavaScript — not a graph-visualization library (reactflow was already removed from this page in Batch 0 and was never added back).

## No structural problems found

Per the owner's explicit instruction, C1-C5 and the information architecture are not reopened — nothing found in this pass rose to that bar. Every finding above is either already-correct behavior being confirmed, or a real but properly-scoped-out issue (global accessibility debt in shared components) that doesn't implicate the redesign's own architecture or data-truth discipline.
