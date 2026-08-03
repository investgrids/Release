import { ImageResponse } from "next/og";
import { readFile } from "node:fs/promises";
import { join } from "node:path";

/**
 * Site-wide default Open Graph image (Phase 1 SEO fix — see the SEO/Growth
 * audit's Critical Finding #4: no page anywhere set an OG image, so every
 * link shared to Slack/WhatsApp/X and every card surfaced in Google
 * Discover rendered with no preview image at all). Next.js's file-based
 * convention means this single file wires into `openGraph.images` for
 * every route that doesn't define its own — no per-page metadata edits
 * needed. Uses the real logo asset (public/marketripple-mark.png), not a
 * placeholder.
 */

export const size = { width: 1200, height: 630 };
export const contentType = "image/png";
export const alt = "MarketRipple — AI-Powered Market Intelligence";

export default async function Image() {
  const markPath = join(process.cwd(), "public", "marketripple-mark.png");
  const markData = await readFile(markPath);
  const markSrc = `data:image/png;base64,${markData.toString("base64")}`;

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          background: "linear-gradient(135deg, #060a14 0%, #0d1024 55%, #150f2e 100%)",
          fontFamily: "sans-serif",
        }}
      >
        {/* eslint-disable-next-line @next/next/no-img-element -- ImageResponse's satori renderer requires a plain <img>, not next/image */}
        <img src={markSrc} width={170} height={170} alt="" />
        <div
          style={{
            marginTop: 36,
            fontSize: 64,
            fontWeight: 800,
            letterSpacing: "-0.02em",
            background: "linear-gradient(90deg, #a389ff 0%, #7c9dfb 100%)",
            backgroundClip: "text",
            color: "transparent",
            display: "flex",
          }}
        >
          MarketRipple
        </div>
        <div style={{ marginTop: 14, fontSize: 28, color: "#9691b8", display: "flex" }}>
          AI-Powered Market Intelligence for Indian Equities
        </div>
      </div>
    ),
    { ...size }
  );
}
