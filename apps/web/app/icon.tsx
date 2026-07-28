import { ImageResponse } from "next/og";
import { readFile } from "node:fs/promises";
import { join } from "node:path";

/**
 * Favicon (Phase 1 SEO fix — see the SEO/Growth audit's Critical Finding
 * #4: the site had no favicon at all). The source mark
 * (public/marketripple-mark.png) is 379×250, not square — letterboxed
 * onto a square black canvas here rather than served as-is, so browser
 * tabs and Google's SERP favicon slot don't crop the M/R glyphs.
 */

export const size = { width: 32, height: 32 };
export const contentType = "image/png";

export default async function Icon() {
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
          alignItems: "center",
          justifyContent: "center",
          background: "#060a14",
        }}
      >
        {/* eslint-disable-next-line @next/next/no-img-element -- ImageResponse's satori renderer requires a plain <img>, not next/image */}
        <img src={markSrc} width={28} height={18.5} alt="" />
      </div>
    ),
    { ...size }
  );
}
