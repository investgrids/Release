import type { NextConfig } from "next";

// Same origin the CSP's img-src/connect-src already trust (see headers()
// below) — computed once here too so next/image's remotePatterns allowlist
// stays in sync with it instead of drifting as a second hardcoded value.
const apiOriginUrl = new URL(process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000");

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
      // /markets was a pre-existing, unlinked duplicate of the commodities
      // page — its richer UI (sparkline charts, AI insights panel, key
      // drivers) has now been merged into /commodities as the one real
      // page, so this becomes a genuine duplicate-content redirect rather
      // than an orphaned dead end.
      { source: "/markets",            destination: "/commodities",            permanent: true },
      // Admin redirect
      { source: "/admin/insights",     destination: "/admin/operations",        permanent: true },

      // Companies hub consolidation (2026-08) — /best-stocks, /compare,
      // /ipo-hub, /sectors were standalone routes whose real content is
      // ALSO rendered, unchanged, as tabs inside /companies (see
      // app/companies/page.tsx's switch statement — it imports and renders
      // these same page components directly, so nothing here is a
      // reimplementation). Two live URLs serving identical content was the
      // problem, not the reused components: bare /companies is the one
      // real canonical destination for this whole product concept now.
      // Query strings (e.g. /compare?a=TCS&b=INFY) are preserved
      // automatically — Next.js appends incoming params not present on the
      // destination. Same proven pattern as /markets → /commodities above,
      // where the redirected-from page.tsx also still exists on disk.
      { source: "/best-stocks",        destination: "/companies?tab=best-stocks", permanent: true },
      { source: "/compare",            destination: "/companies?tab=compare",     permanent: true },
      { source: "/ipo-hub",            destination: "/companies?tab=ipo",         permanent: true },
      { source: "/sectors",            destination: "/companies?tab=sectors",     permanent: true },

      // AI Newsroom consolidation — /insights, /daily-brief, /themes, and
      // /stories were separate pages/products that either duplicated AIPE
      // content via a different pipeline (MIE-sourced /daily-brief) or were
      // confirmed dead (/stories, backed only by seed data). All real
      // content now lives under /newsroom as views over one
      // IntelligenceArticle/Opportunity model. /intelligence/:slug is
      // deliberately NOT redirected here — it's kept as an internal-only
      // ops preview (can show unpublished drafts via /api/publishing,
      // which the public route can't).
      // /newsroom/sources ("Live Sources") existed only to link readers off
      // the site to raw third-party wire copy — the app doesn't do that
      // anywhere else (every other source citation is plain attribution
      // text, never an outbound link), so this page is retired rather than
      // patched.
      { source: "/newsroom/sources",   destination: "/newsroom",                permanent: true },
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

      // Duplicate-article cleanup (2026-08-09) — a bug in plan_extra_angles
      // (content_planner.py) let a single-company event's "primary" article
      // spawn a redundant "per_company" angle for that same, only company:
      // two near-identical articles, two independently AI-guessed slugs.
      // Fixed at the generation source; these 3 already-published pairs
      // (found via a full-catalog scan, not just the one originally
      // reported) still need their old URLs redirected rather than deleted,
      // since they may already be indexed or linked externally.
      { source: "/newsroom/article/advanced-enzyme-technologies-acquisition-meaning-for-advanzen-investors-nse-31cb", destination: "/newsroom/article/advanzens-acquisition-meaning-for-investors-nse-31cb", permanent: true },
      { source: "/newsroom/article/jsw-energy-acquisition-impact-nse-62db",                                          destination: "/newsroom/article/jsw-energy-clean-coal-acquisition-impact-on-investors-nse-62db", permanent: true },
      { source: "/newsroom/article/paytm-block-deal-shares-jump-investors-rss-e261",                                 destination: "/newsroom/article/paytm-block-deal-impact-investors-rss-e261", permanent: true },

      // /whats-new retired (2026-08 audit) — a maintained versioned release
      // history isn't something this team is keeping current going forward;
      // the real, still-accurate "what's recently shipped" content moved to
      // About's own Recent Updates section instead of staying stranded on a
      // standalone page nobody was updating.
      { source: "/whats-new",          destination: "/about#recent-updates",    permanent: true },
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
    // Google Analytics (next/script, gated to production in app/layout.tsx)
    // needs its loader script allowed and its beacon endpoint reachable —
    // without both, gtag's own <script src> tag in the HTML silently gets
    // blocked by CSP and no events ever send, even though the tag is there.
    const csp = [
      "default-src 'self'",
      `script-src 'self' 'unsafe-inline' https://www.googletagmanager.com${isDev ? " 'unsafe-eval'" : ""}`,
      "style-src 'self' 'unsafe-inline'",
      // Explicit apiOrigin (not just "https:") so this holds in local dev
      // too, where the backend is plain http://localhost:8000 — confirmed
      // live during the platform QA sprint: article hero images
      // (/api/media/*.jpg) were silently CSP-blocked on every newsroom
      // article page in dev, since a bare "https:" scheme allowance never
      // matches an http:// origin.
      `img-src 'self' data: ${apiOrigin} https:`,
      "font-src 'self' data:",
      `connect-src 'self' ${apiOrigin} https://www.google-analytics.com https://*.google-analytics.com https://*.analytics.google.com`,
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
    // Backend-served hero images (/api/media/*.jpg) previously couldn't use
    // next/image at all (no allowlisted remote domain), forcing a raw <img>
    // with no width/height — a real, measured CLS source. This is the same
    // origin the CSP already trusts (img-src/connect-src above).
    remotePatterns: [
      {
        protocol: apiOriginUrl.protocol.replace(":", "") as "http" | "https",
        hostname: apiOriginUrl.hostname,
        port: apiOriginUrl.port || undefined,
        pathname: "/api/media/**",
      },
    ],
  },
};

export default nextConfig;
