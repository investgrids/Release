# International Market-Data Provider Evaluation — read-only (2026-10-25)

*Scope: evaluate providers to populate the data-blocked Global Markets sections for US / Europe / Asia-Pacific, measured against the precise Phase A gaps. **No code, no integration, no provider signup.** Prices/limits were web-researched on 2026-10-25; only Twelve Data's tier table was read from its official pricing page — all other figures are third-party and MUST be confirmed with the vendor before any commitment. This is a decision input, not a purchase.*

## 1. The decisive constraint — public display licensing (not call volume)

marketripple.in shows market data **publicly to every visitor**. On every provider researched, that is **"external display" / redistribution**, which is **walled behind a paid commercial tier or a separate written agreement**. Free and "individual/personal" tiers are **uniformly non-commercial** and explicitly forbid public display. This is the *same* wall that already blocks the current yfinance path (see `yahoo_data_licensing_review_2026-10-20.md`) — so switching providers does not avoid a licensing decision; it *is* the licensing decision.

**Implication:** cost is driven by the **display-license tier (a flat monthly fee)**, not by usage. MarketRipple's call volume is tiny — the backend caches 15 min and refreshes a handful of symbols per region — so rate limits are a non-issue; the spend is the display license itself.

## 2. Phase A gaps this must close (the targets)

| Gap | Needed for |
|---|---|
| US equities universe (quotes + gainers/losers) | US movers |
| Europe equities universe | EU movers |
| Asia-Pacific equities universe | APAC movers |
| Sector classification + index membership | Sector heatmaps |
| Stock/market news (US/EU/APAC) | "What's happening" per market |
| Historical prices + volume | Screeners (52w, volume), breadth |
| **Public display/redistribution rights** | Showing any of the above on marketripple.in |

(Index levels + US futures are already covered by the existing yfinance path — no new provider needed for those.)

## 3. Coverage matrix (candidate × gap)

Legend: ✅ supported · ➖ partial / tier-gated · ❓ unconfirmed · 💲 display license = paid/agreement

| Provider | US eq | EU eq | APAC eq | Sector class. | Stock news | Hist. + volume | Public display license |
|---|---|---|---|---|---|---|---|
| **Twelve Data** | ✅ | ➖ (Venture 70+ mkts) | ➖ (Venture/Ultra) | ❓ (profile field) | ❓ (sales add-on) | ✅ | **Venture $149/mo = "external display"** (official) |
| **EODHD** | ✅ | ✅ (60–70+ exch.) | ✅ | ➖ (fundamentals) | ✅ (news+sentiment, top bundle) | ✅ (30y EOD; intraday higher tier) | 💲 B2B license — **confirm** |
| **FMP** | ✅ | ➖ (Ultimate) | ➖ (Ultimate) | ✅ (sector/industry) | ➖ | ✅ | 💲 **separate "Data Display & License Agreement"** required |
| **Finnhub** | ✅ | ➖ (premium) | ➖ (premium) | ➖ | ✅ (company news) | ➖ (1y on free; more paid) | 💲 enterprise/redistribution contract |
| **Polygon → Massive** | ✅ | ❓ (US-centric) | ❓ | ➖ | ➖ | ✅ (US) | 💲 business/redistribution contract (custom) |
| **Marketaux** (news only) | ✅ | ✅ | ✅ (80+ mkts) | — | ✅ (5,000+ sources) | — | ❓ confirm display |
| **marketstack** | ✅ (via Tiingo) | ✅ (70 exch.) | ✅ | ➖ | — | ✅ (30y) | ❓ commercial tier — confirm (upstream Tiingo too) |

## 4. Costs at MarketRipple's expected scale

Because usage is tiny and cached, the cost = the **display tier**, roughly (annual-billing, 2026-10-25; ✱ = third-party, confirm):

- **Twelve Data** — Venture **$149/mo** (external display, 70+ markets, US+major EU+APAC); Enterprise $1,099/mo (all markets + external *distribution*). *Official.* News is a sales add-on (unpriced).
- **EODHD** — All-World ✱€19.99/mo (EOD + delayed); all-in bundle ✱€99.99/mo (adds intraday, fundamentals, **news**) — **cheapest breadth incl. news**, but **display license must be confirmed in writing**.
- **FMP** — Ultimate ✱$99–149/mo for global data, **plus** a separate Data Display agreement (unpriced, sales-led).
- **Finnhub / Polygon(Massive)** — redistribution/global = **enterprise, custom-quoted** (opaque; expect ≫$149/mo).
- **Marketaux** (news only) — ✱$29/mo Basic for news across 80+ markets.

**Realistic entry budget for a compliant public build:** ~**$150–250/mo** for one breadth provider with display rights (+ optionally a dedicated news feed), *contingent on written display-license confirmation.*

## 5. Licensing risks (rank-ordered)

1. **Display rights are the gate, and are often sales-led/opaque** (FMP, Finnhub, Polygon). A plan that technically returns the data does **not** grant the right to show it publicly. Get the display grant **in writing** before building.
2. **"Global" is tier-gated and under-specified** — several vendors don't publish the exact EU/APAC exchange list per tier. Must validate the *specific* exchanges/indices MarketRipple needs are in the purchased tier.
3. **Upstream/exchange sub-licensing** (e.g., marketstack US via Tiingo; real-time exchange fees) can add cost or restrictions beyond the headline price.
4. **Sector classification**: a true GICS taxonomy is MSCI-licensed and expensive; provider "sector" fields are proprietary/approximate — acceptable for a heatmap only if labelled as the provider's classification, not "GICS".
5. **Delayed vs real-time**: real-time exchange data carries per-exchange display fees; **15-min delayed is far cheaper and matches the current cached UX** — recommend delayed.

## 6. Recommendation

**Phase 1 (breadth, one provider):** shortlist **Twelve Data (Venture)** and **EODHD (all-in)** head-to-head.
- *Twelve Data Venture* — clearest, self-serve "external display" grant at a known $149/mo; best licensing transparency; weak on bundled news.
- *EODHD all-in* — widest exchange + historical + **news** breadth at the lowest headline price, **if** its B2B display license is confirmed affordable.
- Pick the one whose **written display license** covers marketripple.in and whose **Venture/all-in tier demonstrably includes the exact US + target EU + APAC exchanges** MarketRipple needs.

**Phase 2 (news):** if the chosen breadth provider's news is weak/absent, add **Marketaux** (~$29/mo, 80+ markets) solely for the "What's happening" sections.

**Phase 3 (sector heatmap):** only after confirming per-constituent **sector tags + index membership + volume** exist in the purchased tier. Label as the provider's sector classification.

**Defer:** advanced screeners (need reliable per-constituent history + corporate actions + volume — validate first).

Start with **US gainers/losers + US news** (highest value, best-covered) behind the existing `NO_STOCK_UNIVERSE`/`NO_MARKET_NEWS` registry slots, then expand EU/APAC per actual confirmed coverage.

## 7. Small validation plan (free trial / sandbox — no paid commitment, no production)

For the 1–2 shortlisted providers, on a **free/trial key**, in a throwaway script (not wired to the app):
1. **Coverage probe** — fetch gainers/losers (or a representative constituent list) + a quote for **US, one EU (e.g. LSE/XETRA), one APAC (e.g. TSE/HKEX)**; record counts, freshness timestamp, currency.
2. **News probe** — fetch recent market/company news for a US + an EU + an APAC symbol; record source, timestamp, link, count.
3. **Historical + volume probe** — fetch daily OHLCV for one symbol per region; confirm volume present, history depth.
4. **Sector probe** — fetch the sector/industry field for 5 symbols/region; confirm present + consistent.
5. **Licensing confirmation (the gate)** — obtain, **in writing**, that the paid tier permits public display on marketripple.in (delayed data); capture the clause.
6. **Decision** — only providers passing 1–5 are eligible; then one recommendation with the confirmed monthly cost.

**No provider is integrated and no plan is purchased during validation.** Output is a one-page go/no-go per provider with the captured licensing clause.

## 8. What NOT to do (per the freeze)
No new provider wired, no plan bought, no code changed, no index-data cards duplicated, no hardcoded/Indian data in non-India sections, no screeners before validated history/volume. The frozen UI slice (selector, futures, honest limitations, §2.5 fix) is unchanged.

## 9. Confidence / unverified
- **Verified official (this session):** Twelve Data tier table + that external display = Venture and external distribution = Enterprise.
- **Third-party, must confirm with vendor:** all FMP / Finnhub / EODHD / Polygon(Massive) / Marketaux / marketstack prices, exact per-tier exchange lists, and every provider's display/redistribution clause. Treat §4 numbers as directional until the §7 validation confirms them.

## Sources
- Twelve Data pricing (official): https://twelvedata.com/pricing
- Financial Modeling Prep FAQ/pricing: https://site.financialmodelingprep.com/faqs
- Finnhub (via third-party summaries): https://finnhub.io/pricing
- EODHD pricing (G2 listing): https://www.g2.com/products/eodhd-financial-data-apis/pricing
- Polygon → Massive rebrand/pricing: https://massive.com/pricing
- Marketaux pricing: https://marketaux.com/pricing
- marketstack FAQ/licensing: https://marketstack.com/faq
