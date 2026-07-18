import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  compress: true,
  experimental: {
    // Tree-shake large packages so only used exports are bundled
    optimizePackageImports: ["recharts", "framer-motion", "reactflow"],
  },
  async redirects() {
    return [
      // /stocks → /companies (canonical)
      { source: "/stocks",             destination: "/companies",               permanent: true },
      { source: "/stocks/:symbol",     destination: "/companies/:symbol",       permanent: true },
      // /radar → /opportunity-radar (canonical)
      { source: "/radar",              destination: "/opportunity-radar",       permanent: true },
      { source: "/radar/:path*",       destination: "/opportunity-radar/:path*",permanent: true },
      // Old article IDs → stories list (slug format changed)
      { source: "/insights/:id*",      destination: "/stories",                permanent: true },
      // /policies merged into /calendar as "Recent Policy Events" section
      { source: "/policies",           destination: "/calendar",               permanent: true },
      // Admin redirect
      { source: "/admin/insights",     destination: "/operations/intelligence", permanent: true },
    ];
  },
  async headers() {
    const isDev = process.env.NODE_ENV === "development";
    return [
      {
        // Baseline security headers on every response.
        source: "/:path*",
        headers: [
          { key: "X-Frame-Options",           value: "SAMEORIGIN" },
          { key: "X-Content-Type-Options",    value: "nosniff" },
          { key: "Referrer-Policy",           value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy",        value: "camera=(), microphone=(), geolocation=()" },
          { key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains; preload" },
        ],
      },
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
