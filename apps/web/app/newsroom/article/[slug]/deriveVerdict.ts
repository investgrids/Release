// Split out of page.tsx (2026-08 fix) — Next.js's App Router type-checks
// page.tsx files against a strict export allowlist (default/metadata/
// generateMetadata/etc.); any other named export fails the generated
// route validator. These types need to be importable from page.tsx, so
// they live here instead.
//
// CD3-D (D7): this file used to also export deriveVerdict() and the
// VerdictCard component it fed (components/article/VerdictCard.tsx) —
// an unhedged Bullish/Bearish/Mixed/Neutral aggregate over these same
// companies/sectors. P0-CD1 (2026-09-01) already suppressed rendering it
// on this page (see page.tsx's own P0-CD1 comment); the CD3-D audit
// confirmed the suppression had gone further than intended -- zero real
// importers of either the function or the component existed anywhere in
// the app. Both deleted outright rather than left as a dormant risk
// ready to be wired to a new page by accident (the audit's own framing)
// -- an unhedged buy/sell-shaped stance with no capability/authorization
// awareness at all would have been the single worst violation of
// everything CD3-D exists to prevent.
// Article V2-F2 (2026-09-14): `impact` is now optional -- V2's own
// companies_affected is deliberately just {symbol, name} (see
// publication_translator.py's own comment on why: manufacturing an
// impact/reason/timeframe the pipeline was never authorized to claim
// would be worse than simply not having one). V1 still always sets it.
export interface CompanyAffected { name: string; symbol: string | null; impact?: "positive" | "negative" | "neutral"; reason?: string; timeframe?: string; }
export interface SectorAffected { name: string; impact?: "positive" | "negative" | "neutral"; magnitude?: "high" | "medium" | "low"; reason?: string; }
