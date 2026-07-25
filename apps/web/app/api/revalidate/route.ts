import { revalidatePath } from "next/cache";
import { NextRequest, NextResponse } from "next/server";

/**
 * On-demand ISR revalidation — called by the backend's media worker right
 * after a hero image finishes generating (see
 * app/services/media/image_worker.py::_notify_frontend), so the article
 * page swaps from the gradient/icon fallback to the real image immediately
 * instead of waiting out its normal cache window or needing a redeploy.
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

  revalidatePath(`/newsroom/article/${slug}`);
  // The same article also appears as a card on these listing pages — a
  // stale fallback icon there would be just as visible as on the article
  // page itself, so all of them need to drop their cached fetch alongside it.
  revalidatePath("/newsroom");
  revalidatePath("/newsroom/library");
  revalidatePath("/");

  return NextResponse.json({ revalidated: true, slug });
}
