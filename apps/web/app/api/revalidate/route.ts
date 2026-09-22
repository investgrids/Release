import { revalidatePath } from "next/cache";
import { NextRequest, NextResponse } from "next/server";

/**
 * On-demand ISR revalidation — originally for the backend's media worker
 * right after a hero image finishes generating (see
 * app/services/media/image_worker.py::_notify_frontend), so the article
 * page swaps from the gradient/icon fallback to the real image immediately
 * instead of waiting out its normal cache window or needing a redeploy.
 *
 * Extended (2026-09-20) for opportunity-v2-canary-revert: that endpoint
 * flips public_status back to shadow and the backend API correctly 404s
 * immediately, but the opportunity-radar detail page's own `revalidate:
 * 300` fetch cache (page.tsx) had no forced-clear path — real production
 * finding: reverting a canary left its page fully visible with its old
 * (already-rejected) content for well over 5 minutes, past its own
 * documented revalidate window, with no sign of self-clearing.
 *
 * Hardened the same day (real security review, not a hypothetical):
 * - auth moves from a JSON body field to a request header
 *   (X-Revalidate-Secret) -- a secret has no business living next to
 *   ordinary request data or ending up logged as part of a body dump.
 * - the caller never supplies a raw path. `kind` selects a fixed
 *   server-side template (exactly the two routes this app actually
 *   needs to bust: /newsroom/article/{slug} and /opportunity-radar/
 *   {slug}) and `slug` is validated against a strict allowlist pattern
 *   before being interpolated into it -- structurally impossible to
 *   target an arbitrary path or escape the template via `../`, an
 *   encoded slash, or any other traversal attempt, because there is no
 *   code path that ever treats client input as a path itself.
 *
 * Best-effort on the caller's side by design — a missed call just means
 * the page catches up at its next natural revalidation, not a broken
 * state, so this doesn't need retries or a queue of its own.
 *
 * Extended (2026-09-22) for the leaked-seed-fixture content-integrity
 * repair: /events/{slug} had no revalidation path at all, so deleting
 * the 3 fabricated Event rows left their pages serving stale cached
 * HTML with the fabricated content. `kind: "event"` adds exactly that
 * one route, `/events/${slug}` + the `/events` index, same fixed-
 * template/allowlisted-slug pattern as the other two kinds — never a
 * caller-supplied path.
 *
 * Event slugs get their own regex, `_EVENT_SLUG_RE`, rather than
 * widening the shared `_SLUG_RE` article/opportunity_v2 already use:
 * real production event slugs can end in a single trailing hyphen (the
 * slug is `{title-slug}-{id-prefix}` truncated to a fixed length, which
 * can land mid-id-prefix right after a hyphen — confirmed against the
 * actual slug of one of the 3 rows this repair removed). `_SLUG_RE`
 * itself is untouched, so article/opportunity_v2 validation is
 * byte-for-byte unchanged.
 */
const _SLUG_RE = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
const _EVENT_SLUG_RE = /^[a-z0-9]+(?:-[a-z0-9]+)*-?$/;

export async function POST(req: NextRequest) {
  const secret = process.env.REVALIDATE_SECRET;
  if (!secret) {
    return NextResponse.json({ error: "revalidation not configured" }, { status: 503 });
  }

  const provided = req.headers.get("x-revalidate-secret");
  if (!provided || provided !== secret) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }

  const body = await req.json().catch(() => null);
  const slug = body?.slug;
  const kind = body?.kind;

  if (kind !== "opportunity_v2" && kind !== "article" && kind !== "event") {
    return NextResponse.json({ error: "kind must be 'opportunity_v2', 'article', or 'event'" }, { status: 400 });
  }
  if (kind === "event") {
    if (typeof slug !== "string" || !_EVENT_SLUG_RE.test(slug)) {
      return NextResponse.json({ error: "slug must match ^[a-z0-9]+(-[a-z0-9]+)*-?$" }, { status: 400 });
    }
  } else if (typeof slug !== "string" || !_SLUG_RE.test(slug)) {
    return NextResponse.json({ error: "slug must match ^[a-z0-9]+(-[a-z0-9]+)*$" }, { status: 400 });
  }

  if (kind === "opportunity_v2") {
    revalidatePath(`/opportunity-radar/${slug}`);
    revalidatePath("/opportunity-radar");
  } else if (kind === "event") {
    // Both segment types, deliberately: app/events/[id]/page.tsx does its
    // own fetch (revalidate: 300) for the body, but app/events/[id]/
    // layout.tsx's generateMetadata() does a SEPARATE fetch (revalidate:
    // 3600) for <title>/description/OG/Twitter tags — a real, confirmed
    // production gap (2026-09-22): revalidatePath(path, "page") alone
    // correctly cleared the body (it rendered "Page not found"), but left
    // the layout's own metadata cache untouched, so the stale fabricated
    // title/description kept showing above an otherwise-correct 404 body.
    revalidatePath(`/events/${slug}`, "page");
    revalidatePath(`/events/${slug}`, "layout");
    revalidatePath("/events");
  } else {
    revalidatePath(`/newsroom/article/${slug}`);
    // The same article also appears as a card on these listing pages — a
    // stale fallback icon there would be just as visible as on the article
    // page itself, so all of them need to drop their cached fetch alongside it.
    revalidatePath("/newsroom");
    revalidatePath("/newsroom/library");
    revalidatePath("/");
  }

  return NextResponse.json({ revalidated: true, slug, kind });
}
