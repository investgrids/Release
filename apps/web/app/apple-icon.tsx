import { ImageResponse } from "next/og";
import { readFile } from "node:fs/promises";
import { join } from "node:path";

/**
 * Apple touch icon (Phase 1 SEO fix, see icon.tsx's docstring for the full
 * reasoning) — same composition at Apple's requested 180×180.
 */

export const size = { width: 180, height: 180 };
export const contentType = "image/png";

export default async function AppleIcon() {
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
        <img src={markSrc} width={130} height={85.75} alt="" />
      </div>
    ),
    { ...size }
  );
}
