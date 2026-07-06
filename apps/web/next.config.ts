import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  output: "standalone",
  compress: true,
  experimental: {
    // Tree-shake large packages so only used exports are bundled
    optimizePackageImports: ["recharts", "framer-motion", "reactflow"],
  },
  async redirects() {
    return [
      { source: "/stocks",                  destination: "/companies",         permanent: true },
      { source: "/stocks/:symbol",          destination: "/companies/:symbol", permanent: true },
      { source: "/opportunity-radar",       destination: "/radar",             permanent: true },
      { source: "/opportunity-radar/:path*",destination: "/radar/:path*",      permanent: true },
      { source: "/themes",                  destination: "/stories",           permanent: true },
      { source: "/ipo-hub",                 destination: "/radar",             permanent: true },
      // /market-intelligence kept as-is — it's the full tabbed market view; View All links point there
    ];
  },
  async headers() {
    const isDev = process.env.NODE_ENV === "development";
    return [
      {
        // In production, chunks have content hashes so long-term caching is safe.
        // In dev, filenames don't change — immutable cache breaks HMR hot-reloads.
        source: "/_next/static/:path*",
        headers: [{ key: "Cache-Control", value: isDev ? "no-store" : "public, max-age=31536000, immutable" }],
      },
      {
        // Never cache API proxy routes from Next.js
        source: "/api/:path*",
        headers: [{ key: "Cache-Control", value: "no-store" }],
      },
    ];
  },
  images: {
    formats: ["image/avif", "image/webp"],
    minimumCacheTTL: 3600,
  },
};

export default nextConfig;
