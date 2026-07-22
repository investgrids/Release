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
      // /policies merged into /calendar as "Recent Policy Events" section
      { source: "/policies",           destination: "/calendar",               permanent: true },
      // Admin redirect
      { source: "/admin/insights",     destination: "/admin/operations",        permanent: true },

      // AI Newsroom consolidation — /insights, /daily-brief, /themes, and
      // /stories were separate pages/products that either duplicated AIPE
      // content via a different pipeline (MIE-sourced /daily-brief) or were
      // confirmed dead (/stories, backed only by seed data). All real
      // content now lives under /newsroom as views over one
      // IntelligenceArticle/Opportunity model. /intelligence/:slug is
      // deliberately NOT redirected here — it's kept as an internal-only
      // ops preview (can show unpublished drafts via /api/publishing,
      // which the public route can't).
      { source: "/insights",           destination: "/newsroom",                permanent: true },
      { source: "/insights/:slug",     destination: "/newsroom/article/:slug",  permanent: true },
      { source: "/daily-brief",        destination: "/newsroom/daily-brief",    permanent: true },
      { source: "/themes",             destination: "/newsroom/themes",         permanent: true },
      { source: "/themes/:slug",       destination: "/newsroom/themes/:slug",   permanent: true },
      { source: "/stories",            destination: "/newsroom/themes",         permanent: true },
      // No reliable slug mapping exists between the old (dead, seed-only)
      // Story model and the real Opportunity model — send to the list
      // rather than guessing a matching detail page.
      { source: "/stories/:slug",      destination: "/newsroom/themes",         permanent: true },
    ];
  },
  async headers() {
    const isDev = process.env.NODE_ENV === "development";
    // CSP built from the actual origins this app talks to — the backend API
    // (for fetch + the SSE EventSource stream) plus 'self'. 'unsafe-inline'
    // on script-src is required because Next.js hydration and our own
    // JSON-LD <script type="application/ld+json"> tags are inline with no
    // nonce plumbing today; still a large improvement over no CSP at all.
    const apiOrigin = (process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");
    const csp = [
      "default-src 'self'",
      `script-src 'self' 'unsafe-inline'${isDev ? " 'unsafe-eval'" : ""}`,
      "style-src 'self' 'unsafe-inline'",
      "img-src 'self' data: https:",
      "font-src 'self' data:",
      `connect-src 'self' ${apiOrigin}`,
      "frame-ancestors 'self'",
      "base-uri 'self'",
      "form-action 'self'",
    ].join("; ");
    return [
      {
        // Baseline security headers on every response.
        source: "/:path*",
        headers: [
          { key: "Content-Security-Policy",   value: csp },
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
