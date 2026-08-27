# Internal-Linking Architecture Audit — 2026-08-24

Read-only audit. No code changes. Scope: every cross-entity internal link across Event, Company, Opportunity, Ripple, Article/Newsroom, Sector/Theme, and Historical detail pages — building on the earlier `NextSteps` component audit, going further into inline content links, `RelatedContent`'s real backend behavior, and server-rendered vs. client-only crawlability for every link found.

## The full matrix

| Source | Target | Current link | Contextual? | Real relationship? | Rendering | Action |
|---|---|---|---|---|---|---|
| Event | Company | `/companies/{symbol}` (VerdictCard, AffectedCompaniesSummary) | Yes | Yes | SSR | Keep |
| Event | Opportunity | `RelatedContent` → `/opportunity-radar/{id}` | No — global top-4 by score, sector arg dropped | Fake-relevance | SSR | Fix backend (pass sector) |
| Event | Ripple | `/ripple/{slug\|\|id}` | Yes | Yes | SSR | Keep |
| Event | Article | none — News tab shows headlines, no href | — | — | — | Missing |
| Company | Event | `/events/{slug\|\|id}` (EventTimeline, CompanyIntelligenceSection) | Yes | Yes | Mixed (Timeline SSR, Intelligence client) | Keep, fix rendering |
| Company | Opportunity | Two paths: real per-company join (client-only) + generic (client-only, SSR fix defeated by collapsed accordion) | Real one yes; generic one no | Real one yes | **Both client-only — zero crawl value** | Promote the real one to SSR |
| Company | Ripple | `/ripple` generic hub only | No | N/A | SSR | Replace with scoped link |
| Company | Article | `/newsroom/article/{slug}`, `/research/{slug}` | Yes | Yes | Client-only (Wave 3) | Move earlier / SSR |
| Company | Compare | `/companies?tab=compare&a={symbol}` + real inline peer links | Hub link no, peer links yes | Peer links yes | Mixed | Keep peer links, fix hub label |
| Company | Ask AI | Hero + NextSteps real; **two dead-end duplicates** (`AskAI` section, `AISummary` button — no onClick/href) | Real ones yes | Real ones yes | SSR | Remove or wire the dead ones |
| Opportunity | Company | `/companies/{symbol}` (V1 only) | Yes (V1) | Yes (V1); **undefined for V2** | SSR | Fix V2 interface mapping |
| Opportunity | Event | `/events/{event_id}` (V1 only, `primary_event`) | Yes (V1) | Yes (V1); missing for V2 | SSR | Fix V2 interface mapping |
| Opportunity | Ripple | Graph nodes render but aren't clickable; NextSteps generic `/ripple` | No | Real V2 ripple subgraph computed, never reaches frontend | SSR (but non-interactive) | Make graph nodes real links |
| Opportunity | Article | none — real `NewsSchema.url` fetched and discarded | — | Data exists, unused | — | Wire the existing URL |
| Ripple (hub) | Company | none | — | — | — | Missing |
| Ripple (hub) | Opportunity | none | — | — | — | Missing |
| Ripple (hub) | Event | `/events/{top.id}` (NextSteps primary) | Yes | Yes | SSR | Keep |
| Ripple (hub) | Article | none | — | — | — | Missing |
| Ripple (detail) | Company | `/companies/{ticker}` (beneficiaries/losers) | Yes | Yes | SSR (default tab) | Keep |
| Ripple (detail) | Opportunity | Generic `/opportunity-radar` SSR; real entity-specific one exists in `RelatedContent` but trapped behind a non-default tab | Generic no, real one yes | Real one yes | Real one **structurally unreachable by crawlers** | Move out of the tab gate |
| Ripple (detail) | Event | `/events/{event_slug\|\|id}` ×2 | Yes | Yes | SSR | Keep |
| Ripple (detail) | Article | none | — | — | — | Missing |
| Article | Company | `/companies/{symbol}` ×3 paths | Yes | Yes | SSR | Keep |
| Article | Event | none | — | — | — | Missing |
| Article | Opportunity | none — structurally excluded from `ExploreCard`'s type union; article's own real `opportunities[]` field discarded | — | Data exists, unused | — | Add an Opportunity card kind |
| Article | Ripple | `/ripple` generic (ExploreNext wide card) | No | Trigger condition is real, destination isn't | SSR | Deep-link when possible |
| Sector/Theme | Company | `/companies/{symbol}`, real per-company score query | Yes | Yes | SSR | Keep — best-in-class |
| Sector/Theme | Event | `/events/{slug\|\|id}` | Yes | Yes | SSR | Keep |
| Sector/Theme | Article | `/newsroom/article`, `/intelligence/signal`, `/research` — 3 real paths | Yes | Yes | SSR | Keep |
| Sector/Theme | Opportunity | `/opportunity-radar/{id}` | Yes | Yes | SSR | Keep |
| Historical | Company | `/companies/{symbol}` ×3 paths | Yes | Yes | SSR | Keep |
| Historical | Event | none — despite real `event_title`/`event_date` implying a real Event record | — | Implied real, never linked | — | Missing |
| Historical | Current intelligence | Real conditional: `#winners-losers` anchor or Ask-AI fallback | Yes | Yes | SSR | Keep (just fixed) |
| Historical | Article | none | — | — | — | Missing |

**Bonus findings outside the requested matrix, worth recording:**
- Daily Brief and the separate Intelligence-article pipeline (`/intelligence/[slug]`, a genuinely different backend endpoint from Newsroom articles) both lean almost entirely on generic hub links; the Intelligence article has *no* ripple link at all, worse than the Newsroom article.
- `/newsroom/themes/[slug]` is not real sector/theme content — it's the Opportunity Radar detail endpoint (`/api/radar/{id}`) re-skinned as "Theme Intelligence." Two URL trees serving the same underlying data under different branding.
- `/sectors/[sector]/page.tsx` (the real sector page) has no Related-Sectors cross-navigation — a dead end back to the sector index only.
- A dead link: `SmartCTA variant="explore-opportunity"` on Ripple detail points to `/radar`, which has no matching route — a real 404.

## Top 10 internal-linking defects

1. **The Company page's own SSR fix for `RelatedContent` is silently defeated.** `page.tsx` server-fetches `/api/related/company/{symbol}` specifically so "the internal-link web this block builds exists in the initial HTML, not just after hydration" (the code's own comment) — but `RelatedContent` sits inside `{intelOpen && ...}` with `intelOpen` defaulting `false`. The exact same pattern works on Event detail only because its equivalent flag (`deepOpen`) defaults `true`. A deliberate fix that doesn't fire.
2. **Ripple detail's real cross-links are worse — seven components, not one, trapped behind a non-default tab.** `MonitoringChecklist`, `PatternIntelligenceCard`, `InvestmentThesisCard`, `OpportunityLifecycleCard`, `ScenarioAnalysis`, `RelatedContent`, `MultiHorizonOutlookCard` are all inside `{activeTab === "timeline" && ...}`, and the default tab is `"graph"`. Real, server-seeded data, structurally unreachable by any crawler.
3. **Opportunity V2 pages render empty where V1 pages render real data.** The frontend's `OpportunityDetail` interface still expects V1 field names (`companies`, `graph_nodes`, `primary_event`). V2's real `companies_connected`, `ripple.nodes/edges`, and `supporting_evidence` — genuinely computed, evidence-backed — never reach the page. The beneficiary table, event link, and ripple graph all render empty for any slug-based (V2) opportunity.
4. **`RelatedContent`'s "Opportunities" group is never entity-relevant, on any of the three page types that use it.** `_recent_opportunities()` accepts a `sector` argument; every call site (`related.py`, Event/Company/Ripple branches) omits it. One backend fix improves three page types at once.
5. **Two fully dead-end interactive-looking sections on Company detail.** The `AskAI` component and `AISummary`'s "Ask AI about {name}" button both render input fields and buttons with no `onClick`/`href` at all — plus four "Quick Actions" buttons (Watchlist, Price Alert, Compare, Download Report) that are purely decorative.
6. **Article → Opportunity is structurally impossible, not just unpopulated.** `ExploreCard["kind"]`'s type union has no opportunity variant. The article's own real, AI-generated `opportunities[]` field is rendered as plain unlinked cards.
7. **`/newsroom/themes/[slug]` duplicates Opportunity Radar under different branding** — same backend endpoint, same fields, different URL and page title ("Theme Intelligence"). A real duplicate-content problem, not a linking gap.
8. **Ripple hub (the default `/ripple` landing tab) has zero Company and zero Opportunity links**, despite being the page whose entire premise is "how effects ripple across companies and sectors."
9. **A confirmed dead link**: `/radar` (404) from Ripple detail's "explore-opportunity" CTA.
10. **`SimilarCompanies` fabricates its similarity rationale.** Real peer symbols, but the "92%/88%/84%..." scores and reason strings are a hardcoded array matched by position, not computed — makes a real link look evidence-based when it isn't.

## Top 10 missing high-value relationships

1. **Company → Opportunity, made crawlable.** The real relationship already exists (`CompanyIntelligenceSection`'s junction-table join) — this isn't a "build it" task, it's an "stop hiding it" task.
2. **Ripple hub → Company.** A ripple page with no company links is a structural gap in the core chain.
3. **Ripple hub → Opportunity.** Same page, same gap.
4. **Article → Event**, anywhere — zero instances found across both article pipelines.
5. **Article → Opportunity** — needs a real card type in `ExploreNext`, not a workaround.
6. **Historical → Event** — the originating event is implied by real data (`event_title`/`event_date`) and never linked.
7. **Entity-scoped Ripple links from Company and Opportunity** — every current Company/Opportunity → Ripple link is a generic hub link, despite Opportunity V2's API literally computing a real, scoped ripple subgraph server-side.
8. **Sector → Sector** — no related-sectors navigation exists at all on the one genuinely good page type in this audit.
9. **Opportunity V2 → Company/Event**, unblocked — real data, real computation, blocked purely by a stale frontend interface.
10. **Ripple/Opportunity/Historical → Article** — all three page types have zero article links; readers researching a ripple chain, an opportunity, or a historical pattern have no path into the newsroom's actual written analysis.

## The canonical internal-linking rulebook

1. **Never use a specific-sounding anchor for a generic destination.** If the label implies scope ("events affecting X," "companies exposed to Y"), the href must carry that scope. If it can't yet, the label must say so honestly ("Explore market events") until it can.
2. **Real entity relationship > keyword similarity > generic hub link.** In that order, always. A generic hub link is the honest fallback of last resort, not a default.
3. **A server-fetched prop is not SSR value if it's rendered inside a client-side conditional that defaults to collapsed.** This was the single most repeated real bug found across three different page types (Company, Ripple detail). Trace every ancestor conditional's *default* state to the root before calling anything "SSR'd" — server-fetching the data and gating its render are two separate decisions, and this audit found the second one silently overriding the first, twice, independently.
4. **Every clickable-looking element needs a real destination.** Verify `onClick`/`href` exists — don't infer it from the presence of a button, an arrow icon, or an input field.
5. **A relationship-scoping parameter that exists must be passed by every caller.** An accepted-but-unused `sector`/`entity_id` argument that silently degrades to "global top-N" is a correctness bug wearing a personalization costume — and in this codebase it was silently degrading three different page types at once from one shared function.
6. **When two systems compute overlapping data, the frontend consumes the richer, real one — never the generic one by default because an interface wasn't updated.** (`CompanyIntelligenceSection`'s real per-company opportunities vs. `RelatedContent`'s generic top-4; V1 vs. V2 opportunity fields.)
7. **A relevance or similarity number shown next to a real link must be computed, not a placeholder.** A fabricated "92% similar" next to a genuinely real company link is worse than showing no number at all — it makes the real thing look fake.
8. **One canonical URL per entity type — never two URL trees serving the same underlying data under different branding.** Consolidate or redirect, don't let both live.
9. **Every entity-detail page type should be both a source and a target across the core chain** (Event ↔ Company ↔ Opportunity ↔ Ripple ↔ Article). No page type should be a pure sink or pure source — this audit found Ripple hub and Historical trending toward pure-sink.
10. **Anchor text should read like a specific research action, never a category label** — "See companies affected by RBI liquidity changes," never "View More." Confirmed working well everywhere it's actually followed (Event's beneficiary links, Sector's per-company query) and confirmed failing everywhere it isn't (Company's "View events affecting X").

## Explicitly not done here

No code changes. The universal Research Journey system stays deferred to the post-integrity UI phase, as decided in the `NextSteps` audit close-out. This report is the input to that later decision, not an implementation of it.
