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
 * documented revalidate window, with no sign of self-clearing. `kind`
 * selects which path set to invalidate, since the two content types are
 * revalidated differently (article's own listing pages vs. the radar
 * list).
 *
 * Best-effort on the caller's side by design — a missed call just means
 * the page catches up at its next natural revalidation, not a broken
 * state, so this doesn't need retries or a queue of its own.
 */
export async function POST(req: NextRequest) {
  const secret = process.env.REVALIDATE_SECRET;
  if (!secret) {
    return NextResponse.json({ error: "revalidation not configured" }, { status: 503 });
  }

  const body = await req.json().catch(() => null);
  const slug = body?.slug;
  if (typeof slug !== "string" || !slug) {
    return NextResponse.json({ error: "slug required" }, { status: 400 });
  }
  if (body?.secret !== secret) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }

  const kind = body?.kind === "opportunity_v2" ? "opportunity_v2" : "article";

  if (kind === "opportunity_v2") {
    revalidatePath(`/opportunity-radar/${slug}`);
    revalidatePath("/opportunity-radar");
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
