import { Suspense } from "react";
import AISearchClient from "./AISearchClient";

// Server Component wrapper — the actual SEO fix. AISearchClient still needs
// useSearchParams() (for the ?q= auto-search effect) and therefore still
// needs a Suspense boundary, but reading the `searchParams` prop here forces
// this route into per-request dynamic rendering instead of static
// generation. Under static generation, everything inside a
// useSearchParams()-driven Suspense boundary is deferred to the client and
// never reaches crawlers (confirmed live: raw HTML showed only the fallback
// spinner). Under dynamic rendering, the boundary's real content — search
// bar, h1, examples, everything — renders fully on the server for every
// request (verified via `next build` + `next start` + raw curl: the real
// h1 and textarea are present in the HTML, not just the fallback).
export default async function AISearchPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string }>;
}) {
  await searchParams;

  return (
    <Suspense fallback={
      <div className="flex h-32 items-center justify-center">
        <div className="h-5 w-5 animate-spin rounded-full border-2 border-violet-500 border-t-transparent"/>
      </div>
    }>
      <AISearchClient/>
    </Suspense>
  );
}
