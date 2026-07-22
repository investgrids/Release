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
