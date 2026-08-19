/**
 * Reverse Windows-1252-decoded UTF-8 (mojibake) in DB strings.
 *
 * When UTF-8 bytes (e.g. en-dash: E2 80 93) are stored as Windows-1252 chars
 * they become three wrong Unicode code points (â€") that render literally.
 * This function converts each char back to its CP1252 byte value, then
 * re-decodes the byte array as UTF-8, restoring the original characters.
 * If any char falls outside CP1252 or the bytes are not valid UTF-8, the
 * original string is returned unchanged.
 */

const CP1252_SPECIAL: Map<number, number> = new Map([
  [0x20ac, 0x80], [0x201a, 0x82], [0x0192, 0x83], [0x201e, 0x84],
  [0x2026, 0x85], [0x2020, 0x86], [0x2021, 0x87], [0x02c6, 0x88],
  [0x2030, 0x89], [0x0160, 0x8a], [0x2039, 0x8b], [0x0152, 0x8c],
  [0x017d, 0x8e], [0x2018, 0x91], [0x2019, 0x92], [0x201c, 0x93],
  [0x201d, 0x94], [0x2022, 0x95], [0x2013, 0x96], [0x2014, 0x97],
  [0x02dc, 0x98], [0x2122, 0x99], [0x0161, 0x9a], [0x203a, 0x9b],
  [0x0153, 0x9c], [0x017e, 0x9e], [0x0178, 0x9f],
]);

function toCP1252Byte(cp: number): number | null {
  if (cp < 0x80) return cp;
  if (cp >= 0xa0 && cp <= 0xff) return cp;
  return CP1252_SPECIAL.get(cp) ?? null;
}

export function fixMojibake(s?: string | null): string {
  if (!s) return "";
  try {
    const bytes: number[] = [];
    for (const c of s) {
      const b = toCP1252Byte(c.codePointAt(0)!);
      if (b === null) return s; // non-CP1252 char — string is already correct
      bytes.push(b);
    }
    return new TextDecoder("utf-8", { fatal: true }).decode(new Uint8Array(bytes));
  } catch {
    return s; // invalid UTF-8 byte sequence — leave as-is
  }
}

// Some ingested headlines (e.g. scraped "Stocks in news: ... L&amp;T ...")
// carry literal HTML entities instead of the decoded character — a real,
// separate data-quality issue from mojibake (unambiguous to fix: entity
// decoding has no false-positive risk the way mojibake byte-guessing does).
// Small, fixed table rather than a full HTML-entity library — covers what's
// actually shown up in real ingested text.
const HTML_ENTITIES: Record<string, string> = {
  "&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": "\"",
  "&#39;": "'", "&apos;": "'", "&nbsp;": " ",
};
export function decodeEntities(s?: string | null): string {
  if (!s) return "";
  return s.replace(/&(?:amp|lt|gt|quot|#39|apos|nbsp);/g, (m) => HTML_ENTITIES[m] ?? m);
}

// The combined, safe-to-apply-everywhere cleanup for any AIPE/Opportunity
// Engine text field — fixes both known real data-quality issues in one call.
export function cleanText(s?: string | null): string {
  return decodeEntities(fixMojibake(s));
}

// "Ask AI" CTAs across the site (events hub, event detail, homepage) embed
// a real headline/title into an /ai-search?q= query template — several
// independently embedded the raw, untruncated title, which for an NSE
// announcement can run 200+ characters ("Sanginita Chemicals Limited has
// submitted the Exchange a copy Srutinizers report of..."), producing a
// URL over 200 chars and a robotic-sounding query with a full paragraph
// stuffed into it (both confirmed live, flagged by an SEO crawl). Same
// 80-char/ellipsis truncation events/page.tsx's own `shortTitle` already
// used correctly in one place — centralized so every CTA site gets it.
export function truncateForQuery(text: string, max = 80): string {
  return text.length > max ? text.slice(0, max - 3) + "…" : text;
}

// For <title>/meta description/og:description — unlike truncateForQuery's
// hard character cut (fine for a query string nobody reads character-by-
// character), a title or description that stops mid-word reads as broken,
// not just long. Confirmed live: an intel page's meta description ending
// "...This is amidst a quiet " (no ellipsis, trailing space, dangling
// clause) from a plain slice(0, 155). Trims to the last whole word within
// the limit instead.
export function truncateAtWord(text: string, max: number): string {
  if (text.length <= max) return text;
  const cut = text.slice(0, max);
  const lastSpace = cut.lastIndexOf(" ");
  // Only trim to the word boundary if it doesn't throw away too much —
  // a boundary very early in the string means one unbroken long word, not
  // a normal sentence, so a mid-word cut is the lesser evil there.
  const trimmed = lastSpace > max * 0.6 ? cut.slice(0, lastSpace) : cut;
  return trimmed.trimEnd() + "…";
}

// When the AI can't identify a specific ticker for a vaguely-referenced
// company (e.g. "the multibagger stock" with no name given in the source
// event), it writes a placeholder into the symbol field rather than
// omitting it — real output, but showing "Not Provided" as a ticker chip
// reads as a bug. Filter these out at render time instead of hiding the
// whole company (the name/reason are usually still real and useful).
const PLACEHOLDER_SYMBOLS = new Set(["not provided", "n/a", "na", "unknown", "tbd", "none", ""]);
// A real NSE/BSE ticker is a single bare token — no comma, space, or slash.
// Added 2026-08 (GSC 404 report: /companies/INFY, TCS, WIPRO) — a joined
// multi-symbol display string reaching this same check wherever it's
// already used as a Link href guard.
const INVALID_SYMBOL_CHARS = /[,\s/]/;
export function isRealSymbol(symbol?: string | null): boolean {
  if (!symbol) return false;
  const trimmed = symbol.trim();
  return !PLACEHOLDER_SYMBOLS.has(trimmed.toLowerCase()) && !INVALID_SYMBOL_CHARS.test(trimmed);
}

// Neutralizes the raw analyst-consensus recommendation string (real data
// from Finnhub/yfinance, "strong buy"/"buy"/"hold"/"sell"/"strong sell" —
// see app/api/stocks.py) into non-directive language. MarketRipple doesn't
// issue buy/sell recommendations, so no UI copy should read as one, even
// when quoting third-party analyst consensus. Lives here (not in the
// client-only CompanyPageClient.tsx) so both the client UI and the
// server-rendered company page can share one definition.
export function neutralRating(recommendation?: string | null): string {
  const r = (recommendation || "").toLowerCase().trim();
  if (r === "strong buy") return "Strongly Positive";
  if (r === "buy") return "Positive";
  if (r === "sell") return "Cautious";
  if (r === "strong sell") return "Strongly Cautious";
  return "Neutral";
}

// AI-generated market narratives (morning briefs) and, less often, real
// event data list market indices and macro instruments in the same
// companies_affected / event.companies shape a real company uses ("Sensex"
// / SENSEX, "Nifty 50" / NIFTY) — found live in production ("Stocks to
// Watch" showing SENSEX and NIFTY as if they were tickers), and the same
// pattern recurs anywhere "companies mentioned in this event" gets
// rendered as ticker chips (e.g. After Market's Tomorrow's Watchlist).
// Shared here rather than duplicated per call site since it's the same
// real bug wherever it shows up. Same category of symbol
// live_intelligence.py's anomaly detector already guards against on the
// backend via its own real company-universe lookup, which the frontend
// doesn't have direct access to — this is a blocklist of the specific
// non-company symbols this pipeline actually produces, not a full
// company-universe check.
const NON_COMPANY_SYMBOLS = new Set([
  "SENSEX", "NIFTY", "NIFTY50", "BANKNIFTY", "NIFTYBANK", "INDIAVIX", "VIX",
  "INR", "USDINR", "GOLD", "SILVER", "CRUDE", "BRENT",
]);
export function isRealCompanySymbol(symbol?: string | null): boolean {
  return isRealSymbol(symbol) && !NON_COMPANY_SYMBOLS.has((symbol as string).trim().toUpperCase());
}

// JSON.stringify does not escape "<", so embedding it verbatim inside a
// <script type="application/ld+json"> tag lets a literal "</script>" in any
// string value (e.g. AI-generated or externally-sourced content) close the
// tag early and inject arbitrary HTML — a real stored-XSS path. Escaping
// "<" to its unicode form is the standard fix; it's semantically identical
// once parsed as JSON, so it never changes the resulting structured data.
export function safeJsonLd(data: unknown): string {
  return JSON.stringify(data).replace(/</g, "\\u003c");
}
