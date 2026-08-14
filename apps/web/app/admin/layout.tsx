import type { Metadata } from "next";

// Internal AI-publishing-engine dashboard, not public-facing content —
// was being indexed (robots: index, follow) with no layout.tsx to override
// it, since a "use client" page can't export its own `metadata`. Paired
// with the /admin disallow rule in app/robots.ts.
export const metadata: Metadata = {
  robots: { index: false, follow: false },
};

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
