# Yahoo Finance Data — Licensing / Redistribution Review (flagged for resolution)

*2026-10-20 · raised during the Global Markets freshness + crypto enhancement · NOT a legal opinion — a flag for the owner to resolve*

## The concern

All market data on the public MarketRipple site for **non-Indian instruments** comes from **Yahoo Finance via the unofficial `yfinance` library**. `yfinance`'s open-source software license governs the *code*, **not** the right to redistribute Yahoo's underlying market *data*. Yahoo's own terms restrict redistribution of the data it provides. Displaying that data on a public, commercial site is a redistribution-rights question that is **currently unresolved**.

## Where Yahoo data is ALREADY used publicly today (pre-existing exposure)

This is not introduced by this feature — it is already live in production (`cd28ac3`/`80c17e5`):

- **Global Markets tab** (`/api/market/global`) — 10 global equity indices, live via `yfinance`.
- **Commodities page** (`/api/commodities/`) — gold, silver, Brent, WTI, natural gas, live via `yfinance`.
- **US index futures** (ES/NQ/YM), **GIFT Nifty** context, **USD/INR**, and other instruments on the pre-market/live tabs that resolve to `yfinance` tickers.

So the redistribution question applies to the **existing live platform**, not merely to anything new.

## New exposure this feature WOULD add (currently gated OFF)

- **Quote freshness fields** on the existing 10 global indices (timestamp, session, source) — same Yahoo data, richer metadata.
- **Crypto Markets tab** — BTC/ETH/SOL/XRP/BNB prices + 24h change/volume, via the same `yfinance` integration.

Both are behind feature flags that **default OFF** (`global_markets_freshness_enabled`, `crypto_markets_enabled`, and the frontend `NEXT_PUBLIC_CRYPTO_MARKETS_ENABLED`). With the flags off, **production behaviour is unchanged and no new Yahoo data is exposed.** Nothing new goes public until the flags are deliberately turned on.

## What needs confirming (owner / legal)

1. Whether MarketRipple's public, commercial display of Yahoo-sourced data is permitted under Yahoo's terms, for the **existing** surfaces.
2. If not, whether to (a) obtain a licensed/commercial data source for public display, or (b) restrict Yahoo data to non-public/internal use.
3. The crypto additions specifically: whether a crypto-native licensed source (e.g. an exchange API or a provider with redistribution rights) is preferable to Yahoo for a public crypto tab.

## Explicit non-conclusion

The fact that Yahoo data is **already displayed** on MarketRipple is **not** evidence that redistribution is permitted — it only means the question predates this feature. This review raises the flag; it does not resolve it. No deployment of the flagged features should be treated as licensing clearance.
