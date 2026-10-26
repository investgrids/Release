// Structured source attribution for the Events detail view (2026-10-25).
// PLAIN TEXT only — never a clickable off-site link (existing product policy).
// The URL is appended only when it is a valid http(s) string; missing, empty,
// or invalid URLs are treated as absent. Returns a plain string that callers
// render as text, never as an <a href>.
export function buildSourceDetail(source: string, sourceUrl?: string | null): string {
  const u = (sourceUrl || "").trim();
  const valid = /^https?:\/\//i.test(u) ? u : "";
  return valid ? `${source} — ${valid}` : source;
}
