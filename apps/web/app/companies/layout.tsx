// Metadata lives entirely in page.tsx now — this file previously defined
// its own title/openGraph/twitter that silently drifted out of sync with
// page.tsx's (Next.js only overrides the top-level keys a child page
// actually sets; page.tsx set title/description but never openGraph or
// twitter, so this layout's stale "Company Intelligence — MarketRipple"
// copy kept shipping in every og:title / twitter:title on /companies,
// while the <title> tag and meta description came from page.tsx —
// confirmed live via curl, the two didn't match). One source of truth
// avoids that drift recurring.
export default function Layout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
