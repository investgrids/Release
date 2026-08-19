import { NextResponse, type NextRequest } from "next/server";
import { API_BASE_URL as API } from "@/lib/api";

// SEO URL migration — every event already has a real, human-readable slug
// (see event_pipeline.py's _make_unique_slug), but years of already-
// indexed/bookmarked links point at the raw internal id
// ("/events/nse-4cc93acbc1"). The page itself already resolves either
// form (id-or-slug lookup — /api/events/{id}, /api/ripple/event/{id},
// /api/intelligence/event/{id} all accept both now), so nothing here is
// load-bearing for correctness — this exists purely so search engines see
// a real, permanent 301 to the canonical slug URL instead of quietly
// 200-ing on the id form forever. A 301 (not Next.js's own redirect()/
// permanentRedirect(), which issue 307/308) is what search engines
// specifically consolidate ranking signal on.
//
// All 7 raw-id source prefixes (2026-08 SEO audit) — this used to be just
// nse-/bse-, which left fed-/pib-/rbi-/rss-/sebi- ids 200-ing directly with
// their own noindex instead of 301-ing to their real slug (confirmed live:
// /events/fed-b6a5befa779d served 200+noindex despite a real slug existing
// for it). See app/providers/*.py for where each prefix is generated.
const ID_PATTERN = /^(nse-|bse-|fed-|pib-|rbi-|rss-|sebi-)/i;

type Kind = "events" | "ripple" | "intel-event";

async function resolveSlug(kind: Kind, id: string): Promise<string | null> {
  try {
    const url = kind === "events" ? `${API}/api/events/${id}`
      : kind === "ripple" ? `${API}/api/ripple/event/${id}`
      : `${API}/api/intelligence/event/${id}`;
    const res = await fetch(url, { signal: AbortSignal.timeout(5000) });
    if (!res.ok) return null;
    const data = await res.json();
    const slug = kind === "events" ? data?.event?.slug
      : kind === "ripple" ? data?.event_slug
      : data?.slug;
    return typeof slug === "string" && slug ? slug : null;
  } catch {
    return null;
  }
}

export async function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;
  const eventsMatch = pathname.match(/^\/events\/([^/]+)$/);
  const rippleMatch = pathname.match(/^\/ripple\/([^/]+)$/);
  const intelEventMatch = pathname.match(/^\/intel\/event\/([^/]+)$/);
  const match = eventsMatch || rippleMatch || intelEventMatch;
  if (!match) return NextResponse.next();

  const id = match[1];
  if (!ID_PATTERN.test(id)) return NextResponse.next();

  const kind: Kind = eventsMatch ? "events" : rippleMatch ? "ripple" : "intel-event";
  const slug = await resolveSlug(kind, id);
  // No real slug found (unknown id, demo ripple id, no real intelligence
  // synthesis for this event yet, transient backend error) — let the
  // request through unredirected rather than 404ing a request the page
  // itself might still be able to serve (e.g. Ripple's static demo ids
  // "1".."6", or /intel/event/{id}'s own redirect-to-/events/{id} when
  // there's no real content).
  if (!slug || slug === id) return NextResponse.next();

  const url = req.nextUrl.clone();
  url.pathname = kind === "intel-event" ? `/intel/event/${slug}` : `/${kind}/${slug}`;
  return NextResponse.redirect(url, 301);
}

export const config = {
  matcher: ["/events/:id", "/ripple/:id", "/intel/event/:id"],
};
