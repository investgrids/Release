"use client";

import NextTopLoader from "nextjs-toploader";

export function NavigationProgress() {
  return (
    <NextTopLoader
      color="#818cf8"
      initialPosition={0.12}
      crawlSpeed={200}
      height={2}
      crawl
      showSpinner={false}
      easing="ease"
      speed={300}
      shadow="0 0 10px #818cf8,0 0 5px #a78bfa"
    />
  );
}
